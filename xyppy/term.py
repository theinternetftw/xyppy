# os-specific txt controls

import sys, atexit, ctypes

def init(env):
    if is_windows():
        old_output_mode = ctypes.c_uint32()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleMode(stdout_handle, ctypes.byref(old_output_mode))
        ctypes.windll.kernel32.SetConsoleMode(stdout_handle,
            1 | # ENABLE_PROCESSED_OUTPUT
            2 | # ENABLE_WRAP_AT_EOL_OUTPUT
            4 | # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            8   # DISABLE_NEWLINE_AUTO_RETURN
        )
        atexit.register(lambda: ctypes.windll.kernel32.SetConsoleMode(stdout_handle, old_output_mode.value))

        old_input_mode = ctypes.c_uint32()
        stdin_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-10))
        ctypes.windll.kernel32.GetConsoleMode(stdin_handle, ctypes.byref(old_input_mode))
        res = ctypes.windll.kernel32.SetConsoleMode(stdin_handle,
            0x200 # ENABLE_VIRTUAL_TERMINAL_INPUT
        )
        atexit.register(lambda: ctypes.windll.kernel32.SetConsoleMode(stdin_handle, old_input_mode.value))
    else: # Unix
        import termios, tty
        stdin_fd = sys.stdin.fileno()
        orig = termios.tcgetattr(stdin_fd)
        atexit.register(lambda: termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, orig))
        tty.setcbreak(stdin_fd)
    def on_exit_common():
        home_cursor()
        cursor_down(env.hdr.screen_height_units)
        reset_color()
        show_cursor()
    atexit.register(on_exit_common)
    hide_cursor()

def reset_color():
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

def get_size():
    if is_windows():
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        return cbuf.srWindow.Right-cbuf.srWindow.Left+1, cbuf.srWindow.Bottom-cbuf.srWindow.Top+1
    else:
        import fcntl, termios, struct
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
        h, w, hp, wp = struct.unpack('HHHH', result)
        return w, h

def scroll_down():
    # need to reset color to avoid adding bg at bottom
    sys.stdout.write('\x1b[0m')
    if is_windows():
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

# TODO: any other encodings to check for?
def supports_unicode():
    return sys.stdout.encoding in ['UTF-8', 'UTF-16', 'UTF-32']

is_windows_cached = None
def is_windows():
    global is_windows_cached
    if is_windows_cached == None:
        try:
            import msvcrt
            is_windows_cached = True
        except ImportError:
            is_windows_cached = False
    return is_windows_cached

def getch():
    if is_windows():
        stdin_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-10))
        one_char_buf = ctypes.c_uint32()
        chars_read = ctypes.c_uint32()
        # use ReadConsole to get the VT100 keys our console mode gives us
        # NOTE: W version of this function == ERROR_NOACCESS after text color set in photopia!?
        result = ctypes.windll.kernel32.ReadConsoleA(stdin_handle,
                                                     ctypes.byref(one_char_buf),
                                                     1,
                                                     ctypes.byref(chars_read),
                                                     0)

        if result == 0 or chars_read.value != 1:
            last_err = ctypes.windll.kernel32.GetLastError()
            print('LAST ERR', last_err)
            err('failed to read console')

        c = chr(one_char_buf.value)
        if ord(c) == 3:
            # occurs when ctrl-c is pressed on windows
            raise KeyboardInterrupt
        return c
    else: #Unix
        return sys.stdin.read(1)

def puts(c):
    sys.stdout.write(c)
