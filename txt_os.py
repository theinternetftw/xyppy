
# os-specific txt controls

import sys

def reset_term_color():
    if isWindows():
        from ctypes import windll, c_ulong, byref
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 7)
    else:
        sys.stdout.write('\x1b[0m')

import atexit
atexit.register(reset_term_color)

def write_char_with_color(char, fg_col, bg_col):
    set_term_color(fg_col, bg_col)
    if not isWindows() and char == '\n':
        sys.stdout.write('\x1b[K') # insure bg_col covers rest of line
    sys.stdout.write(char)

def set_term_color(fg_col, bg_col):
    if isWindows():
        from ctypes import windll, c_ulong
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))

        # having trouble with white bg, black text.
        # let's leave that out for now.
        if fg_col == 2:
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
        color = str(fg_col + 28)
        sys.stdout.write('\x1b['+color+'m')
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

# at this point pretty different from http://code.activestate.com/recipes/134892/
# instead now mostly from https://docs.python.org/2/library/termios.html
def getch():
    """Gets a single character from standard input.  Does not echo to the screen."""
    if isWindows():
        import msvcrt
        return msvcrt.getch()
    else: #Unix
        import sys, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO # [3] == lflags
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, new)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

