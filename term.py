# os-specific txt controls

import sys, atexit

def init(env):
    if isWindows():
        pass
    else: #Unix
        import termios
        fd = sys.stdin.fileno()
        orig = termios.tcgetattr(fd)
        atexit.register(lambda: termios.tcsetattr(fd, termios.TCSAFLUSH, orig))
    atexit.register(reset_color)
    atexit.register(lambda: cursor_down(env.hdr.screen_height_units))
    atexit.register(show_cursor)

def reset_color():
    if isWindows():
        from ctypes import windll, c_ulong, byref
        stdout_handle = windll.kernel32.GetStdHandle(c_ulong(-11))
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 7)
    else:
        sys.stdout.write('\x1b[0m')

def write_char_with_color(char, fg_col, bg_col):
    set_color(fg_col, bg_col)
    if char == '\n':
        fill_to_eol_with_bg_color() # insure bg_col covers rest of line
    sys.stdout.write(char)

# TODO: Windows
def fill_to_eol_with_bg_color():
    sys.stdout.write('\x1b[K') # insure bg_col covers rest of line
def cursor_to_left_side():
    sys.stdout.write('\x1b[G')
def cursor_up(count=1):
    sys.stdout.write('\x1b['+str(count)+'A')
def cursor_down(count=1):
    sys.stdout.write('\x1b['+str(count)+'B')
def cursor_right(count=1):
    sys.stdout.write('\x1b['+str(count)+'C')
def cursor_left(count=1):
    sys.stdout.write('\x1b['+str(count)+'D')
def scroll_down():
    # need to reset color to avoid adding bg at bottom
    sys.stdout.write('\x1b[0m')
    sys.stdout.write('\x1b[S')
def clear_line():
    sys.stdout.write('\x1b[2K')
def hide_cursor():
    sys.stdout.write('\x1b[?25l')
def show_cursor():
    sys.stdout.write('\x1b[?25h')
def clear_screen():
    sys.stdout.write('\x1b[2J')
def home_cursor():
    sys.stdout.write('\x1b[f')

def set_color(fg_col, bg_col):
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
    if is_windows_cached == None:
        try:
            import msvcrt
            is_windows_cached = True
        except ImportError:
            is_windows_cached = False
    return is_windows_cached

def getch():
    if isWindows():
        import msvcrt
        return msvcrt.getch()
    else: #Unix
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)
        return ch
