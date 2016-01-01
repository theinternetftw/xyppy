import sys

def wwrap(text, width):
    lines = [text]
    idx = lines[-1].find('\n')
    while idx != -1:
        rest = lines.pop()
        lines += [rest[:idx], rest[idx+1:]]
        idx = lines[-1].find('\n')
    def get_index_of_long_line():
        return [i for i in range(len(lines)) if len(lines[i]) > width]
    idxs = get_index_of_long_line()
    while idxs:
        i = idxs[0]
        line = lines[i]
        last_space = line[:width].rfind(' ')
        if last_space != -1:
            lines = lines[:i] + [line[:last_space],line[last_space+1:]] + lines[i+1:]
        else:
            lines = lines[:i] + [line[:width], line[width:]] + lines[i+1:]
        idxs = get_index_of_long_line()
    lines = '\n'.join(lines)
    return lines

def finish_writing_colors(env):
    pass

def blank_top_win(env):
    pass
def blank_bottom_win(env):
    pass

class Screen:
    def __init__(self, env):
        self.env = env
        self.last_top_window = ''
        self.init_bufs()

    def init_bufs(self):
        self.textBuf = self.make_screen_buf(' ')
        self.fgColorBuf = self.make_screen_buf(self.env.fg_color)
        self.bgColorBuf = self.make_screen_buf(self.env.bg_color)

    def make_screen_buf(self, default_val):
        buf = []
        for i in xrange(self.env.hdr.screen_height_units):
            buf.append(self.make_buf_line(default_val))
        return buf

    def make_buf_line(self, default_val):
        line = []
        for i in xrange(self.env.hdr.screen_width_units):
            line.append(default_val)
        return line

    def append_buf_line(self):
        self.textBuf.append(self.make_buf_line(' '))
        self.fgColorBuf.append(self.make_buf_line(self.env.fg_color))
        self.bgColorBuf.append(self.make_buf_line(self.env.bg_color))

    def write(self, text):
        if self.env.use_buffered_output:
            self.write_wrapped(text)
        else:
            self.write_unwrapped(text)

    def new_line(self):
        env = self.env
        hdr = self.env.hdr
        h = hdr.screen_height_units
        w = hdr.screen_width_units
        win = env.current_window
        row, col = env.cursor[win]
        while col < w-1:
            self.write_unwrapped(' ') # for bg_color
            row, col = env.cursor[win]
        if win == 0 or row+1 < h:
            env.cursor[win] = row+1, 0
            while row+1 >= len(self.textBuf):
                self.append_buf_line()
        else:
            env.cursor[win] = row, 0

    def write_wrapped(self, text):
        env = self.env
        win = env.current_window
        w = env.hdr.screen_width_units
        while text:
            if text[0] == '\n':
                self.new_line()
                text = text[1:]
            elif text[0] == ' ':
                space_len = 0
                while text[space_len] == ' ':
                    space_len += 1
                    if space_len == len(text):
                        break
                spaces = text[:space_len]
                text = text[space_len:]
                self.write_unwrapped(spaces)
                # NOTE: should I add another "fix spaces at beginning of lines"
                # check here (see at the end of the else below)
            else:
                first_space = text.find(' ')
                if first_space == -1:
                    first_space = len(text)
                first_nl = text.find('\n')
                if first_nl == -1:
                    first_nl = len(text)
                word = text[:min(first_space, first_nl)]
                text = text[min(first_space, first_nl):]
                if len(word) > w:
                    self.write_unwrapped(word)
                elif env.cursor[win][1] + len(word) > w:
                    self.new_line()
                    self.write_unwrapped(word)
                else:
                    self.write_unwrapped(word)
                # avoid pushing spaces to beginning of line
                if env.cursor[win][1] == 0:
                    while len(text) > 0 and text[0] == ' ':
                        text = text[1:]

    # NOTE/TODO?: spec *suggests* just staying at
    # bottom right when you run out of space in top
    # window. That keeps you from overwriting what
    # you just wrote. Right now we jump left with
    # every newline and start overwriting that line.
    def write_unwrapped(self, text):
        env = self.env
        win = env.current_window
        w = env.hdr.screen_width_units
        while len(self.textBuf) < env.cursor[win][0]:
            self.append_buf_line()
        for c in text:
            if c == '\n':
                self.new_line()
            else:
                y, x = env.cursor[win]
                self.textBuf[y][x] = c
                self.fgColorBuf[y][x] = env.fg_color
                self.bgColorBuf[y][x] = env.bg_color
                env.cursor[win] = y, x+1
                if x+1 >= w:
                    self.new_line()

    def top_window_is_old(self):
        top_window_buf = self.textBuf[:self.env.top_window_height]
        top_window_lines = map(lambda x: ''.join(x), top_window_buf)
        top_window = '\n'.join(top_window_lines)
        if top_window == self.last_top_window:
            return True
        self.last_top_window = top_window
        return False

    # FIXME: Color, (set term cursor? would fix bureaucracy...)
    def flush(self):
        buf = trim_buf(self.textBuf)
        fgBuf = self.fgColorBuf[:len(buf)]
        bgBuf = self.bgColorBuf[:len(buf)]
        # be conducive to our printing style by not
        # repeating the same top window over and over.
        if self.top_window_is_old():
            buf = buf[self.env.top_window_height:]
            fgBuf = self.fgColorBuf[self.env.top_window_height:]
            bgBuf = self.bgColorBuf[self.env.top_window_height:]
        if len(buf) > 0:
            # hack? better to set term cursor manually?
            buf[-1] = buf[-1][:self.env.cursor[0][1]]
            fg = fgBuf[0][0]
            bg = bgBuf[0][0]
            set_term_color(fg, bg)
            sys.stdout.write('\n')
            for x in range(self.env.hdr.screen_width_units):
                set_term_color(fg, bg)
                sys.stdout.write(' ')
            set_term_color(fg, bg)
            sys.stdout.write('\n')
        for i in xrange(len(buf)):
            for j in xrange(len(buf[i])):
                fg, bg = fgBuf[i][j], bgBuf[i][j]
                set_term_color(fg, bg)
                sys.stdout.write(buf[i][j])
            if i < len(buf) - 1:
                sys.stdout.write('\n')
        self.init_bufs()
        self.env.cursor[0] = (self.env.top_window_height, 0)

def line_empty(line):
    for c in line:
        if c != ' ':
            return False
    return True

def trim_buf(buf):
    trimmed_buf = buf[:]
    while len(trimmed_buf) > 0 and line_empty(trimmed_buf[-1]):
        trimmed_buf = trimmed_buf[:-1]
    return trimmed_buf

def write(env, text):

    # stream 3 overrides all other output
    if 3 in env.selected_ostreams:
        env.output_buffer[3] += text
        return

    for stream in env.selected_ostreams:
        if stream == 1:
            env.output_buffer[stream].write(text)
        else:
            env.output_buffer[stream] += text

def flush(env):
    #print '\nFLUSH!'
    if 3 not in env.selected_ostreams:
        if 1 in env.selected_ostreams:

            env.output_buffer[1].flush()

'''
            # FIXME: get this working again if it's not?

            # throw away excess top window *only* after flush
            # (to enable stuff like trinity's quotes)
            for line in env.output_buffer[1][1].keys():
                if line >= env.top_window_height:
                    del env.output_buffer[1][1][line]
'''

def read_packed_string(env, addr):
    packed_string = []
    while True:
        word = env.u16(addr)
        packed_string.append(word)
        if word & 0x8000:
            break
        addr += 2
    return packed_string

# emulate print()'s functionality (for now?)
def warn(*args, **kwargs):
    if 'sep' not in kwargs:
        kwargs['sep'] = ' '
    if 'end' not in kwargs:
        kwargs['end'] = '\n'
    sep, end = kwargs['sep'], kwargs['end']

    msg = ''
    if args:
        msg += str(args[0])
    for arg in args[1:]:
        msg += sep + str(arg)
    msg += end

    # for the same weird issue as mentioned in flush()
    msg = msg.replace('\n','\r\n')

    sys.stderr.write(msg)

def err(msg):
    sys.stderr.write('error: '+msg+'\n')
    sys.exit()

def reset_term_color():
    if isWindows():
        from ctypes import windll, c_ulong, byref
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 7)
    else:
        sys.stdout.write('\x1b[0m')

import atexit
atexit.register(reset_term_color)

def set_term_color(fg_col, bg_col):
    if isWindows():
        from ctypes import windll, c_ulong
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))

        '''
        if fg_col == 2:
            # so real bg_color works on windows by padding every line with
            # spaces to SCREEN_WIDTH and resetting the cursor to where
            # input should be put (after filling that line with spaces
            # too).  A quick attempt showed several corner cases, so
            # I'm gonna leave it until I fix input cursor control (if
            # I ever actually do: haven't run into too many things that
            # need it). Til then, black text becomes white + no bg_col.
            fg_col = 9
        '''
        colormap = {
            2: 0,
            3: 8|4,
            4: 8|2,
            5: 8|6,
            6: 8|1,
            7: 8|5,
            8: 8|3,
            9: 7 # do 8|7 (15) for bright white, but since cmd.exe uses 7 I will too...
        }
        # this doesn't handle "leave alone" colors yet
        # to do that with windows, will have to save current cols
        # and reapply them here if fg_col or bg_col are 0!
        # also see comment above for why bg_col is commented out
        col = colormap[fg_col] # | (colormap[bg_col] << 4)
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, col)
    else:
        # assuming VT100 compat
        if fg_col != 0:
            color = str(fg_col + 28)
            sys.stdout.write('\x1b['+color+'m')
        if bg_col != 0:
            color = str(bg_col + 38)
            sys.stdout.write('\x1b['+color+'m')

is_windows_cached = None
def isWindows():
    global is_windows_cached
    if is_windows_cached != None:
        return is_windows_cached
    try:
        import msvcrt
        is_windows_cached = True
    except ImportError:
        is_windows_cached = False
    return is_windows_cached

# mostly from http://code.activestate.com/recipes/134892/
def getch():
    """Gets a single character from standard input.  Does not echo to the screen."""
    if isWindows():
        import msvcrt
        return msvcrt.getch()
    else: #Unix
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

