from txt_os import getch, write_char_with_color

# warning: hack filled nonsense follows, since I'm
# converting a system that expects full control over
# the screen to something that prints linearly in
# the terminal

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
        while env.cursor[win][0] > len(self.textBuf) - 1:
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
        buf = self.trim_buf()
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
            cursor_left = self.env.cursor[0][1]
            if cursor_left != 0 and line_empty(buf[-1][cursor_left:]):
                buf[-1] = buf[-1][:self.env.cursor[0][1]]

        for i in xrange(len(buf)):
            for j in xrange(len(buf[i])):
                fg, bg = fgBuf[i][j], bgBuf[i][j]
                write_char_with_color(buf[i][j], fg, bg)
            if i < len(buf) - 1:
                write_char_with_color('\n', fg, bg)

        if len(buf) > 0:
            # if cursor's at zero or edge, move it to bottom otherwise it looks weird.
            cursor_top = self.env.cursor[0][0]
            cursor_left = self.env.cursor[0][1]
            if cursor_left == 0 or cursor_left == self.env.hdr.screen_width_units-1:
                fg = self.fgColorBuf[cursor_top][cursor_left]
                bg = self.bgColorBuf[cursor_top][cursor_left]
                write_char_with_color('\n', fg, bg)

                # in fact, let's add a little more breathing room
                for x in xrange(self.env.hdr.screen_width_units):
                    write_char_with_color(' ', fg, bg)
                write_char_with_color('\n', fg, bg)

        self.init_bufs()
        self.env.cursor[0] = (self.env.top_window_height, 0)

    def trim_buf(self):
        b = self.textBuf[:]
        while len(b) > 0 and len(b) > self.env.top_window_height and line_empty(b[-1]):
            b = b[:-1]
        return b

def line_empty(line):
    for c in line:
        if c != ' ':
            return False
    return True

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
    if 3 not in env.selected_ostreams:
        if 1 in env.selected_ostreams:
            env.output_buffer[1].flush()

'''
            # FIXME: get this working again if it's not?
            # (it *almost* is...)

            # throw away excess top window *only* after flush
            # (to enable stuff like trinity's quotes)
            for line in env.output_buffer[1][1].keys():
                if line >= env.top_window_height:
                    del env.output_buffer[1][1][line]
'''
