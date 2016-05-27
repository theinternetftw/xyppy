# os-specific txt controls

import sys, atexit, ctypes

def init(env):
    if isWindows():
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.SetConsoleMode(stdout_handle, 7)
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
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.SetConsoleTextAttribute(stdout_handle, 7)
    else:
        sys.stdout.write('\x1b[0m')

def write_char_with_color(char, fg_col, bg_col):
    set_color(fg_col, bg_col)
    if char == '\n':
        fill_to_eol_with_bg_color() # insure bg_col covers rest of line
    sys.stdout.write(char)

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short),
                ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", ctypes.c_ushort),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD)]

def scroll_down():
    # need to reset color to avoid adding bg at bottom
    sys.stdout.write('\x1b[0m')
    if isWindows():
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        if cbuf.srWindow.Bottom < cbuf.dwSize.Y - 1:
            cbuf.srWindow.Bottom += 1
            cbuf.srWindow.Top += 1
            ctypes.windll.kernel32.SetConsoleWindowInfo(stdout_handle, 1, ctypes.byref(cbuf.srWindow))
    else:
        sys.stdout.write('\x1b[S')
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
def clear_line():
    sys.stdout.write('\x1b[2K')
def hide_cursor():
    sys.stdout.write('\x1b[?25l')
def show_cursor():
    sys.stdout.write('\x1b[?25h')
def clear_screen():
    sys.stdout.write('\x1b[2J')
def home_cursor():
    sys.stdout.write('\x1b[H')

def set_color(fg_col, bg_col):
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
