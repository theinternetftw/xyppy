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

def write(env, text):

    # stream 3 overrides all other output
    if 3 in env.selected_ostreams:
        env.output_buffer[3] += text
        return

    for stream in env.selected_ostreams:
        if stream == 1:
            win = env.current_window
            out = env.output_buffer[stream][win]
            line, col = env.cursor[win]
            while text:
                if line not in out:
                    out[line] = []
                c = text[0]
                if c == '\n':
                    line += 1
                    col = 0
                # do I need to skip e.g. \r's?
                # or should there only be \r's at this stage
                # and no \n's?  Check the spec again.
                else:
                    while len(out[line]) < col+1:
                        out[line].append(' ')
                    out[line][col] = c
                    col += 1
                text = text[1:]
            env.cursor[win] = line, col
        else:
            env.output_buffer[stream] += text

def flush(env):
    #print '\nFLUSH!'
    if 3 not in env.selected_ostreams:
        if 1 in env.selected_ostreams:

            win1 = []
            # window 1 is never wrapped
            for line in sorted(env.output_buffer[1][1].keys()):
                win1 += [''.join(env.output_buffer[1][1][line])]

            while len(win1) < env.top_window_height:
                win1 += ['']

            win0 = []
            for line in sorted(env.output_buffer[1][0].keys()):
                win0 += [''.join(env.output_buffer[1][0][line])]

            width = env.hdr.screen_width_units or 80
            out = ('\n' +
                   '\n'.join(win1) + '\n' +
                   '\n' +
                    wwrap('\n'.join(win0), width))
            # really weird things are happening with bare '\n's
            # even in a unix env. wtf.
            out = out.replace('\n','\r\n')
            sys.stdout.write(out)

            env.output_buffer[1][0] = {}
            # throw away excess top window *only* after flush
            # (to enable stuff like trinity's quotes)
            for line in env.output_buffer[1][1].keys():
                if line >= env.top_window_height:
                    del env.output_buffer[1][1][line]

def blank_top_win(env):
    env.output_buffer[1][1] = {}

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
    if fg_col == 1: # default (white)
        fg_col = 9
    if bg_col == 1: # default (black)
        bg_col = 2
    if isWindows():
        from ctypes import windll, c_ulong
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))

        if fg_col == 2:
            # so real bg_color works on windows by padding every line with
            # spaces to SCREEN_WIDTH and resetting the cursor to where
            # input should be put (after filling that line with spaces
            # too).  A quick attempt showed several corner cases, so
            # I'm gonna leave it until I fix input cursor control (if
            # I ever actually do: haven't run into too many things that
            # need it). Til then, black text becomes white + no bg_col.
            fg_col = 9
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

def isWindows():
    try:
        import msvcrt
        return True
    except ImportError:
        return False

# right from http://code.activestate.com/recipes/134892/
class _Getch:
    """Gets a single character from standard input.  Does not echo to the
screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()

class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

getch = _Getch()

