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
    sys.stderr.write(msg)

def err(msg):
    sys.stderr.write('error: '+msg+'\n')
    sys.exit()

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

