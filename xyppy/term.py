# os-specific txt controls

from __future__ import print_function

import atexit
import ctypes
import sys
import time

from collections import deque
from threading import Thread

from xyppy.debug import err, warn

unix_in_tstp_signal = False
unix_screen_is_reset = False

stdin_is_tty = sys.stdin.isatty()
stdout_is_tty = sys.stdout.isatty()

def init():
    if is_windows:
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        win_original_attributes = cbuf.wAttributes # TODO: use if needed

        old_output_mode = ctypes.c_uint32()
        ctypes.windll.kernel32.GetConsoleMode(stdout_handle, ctypes.byref(old_output_mode))
        ctypes.windll.kernel32.SetConsoleMode(stdout_handle,
            1 | # ENABLE_PROCESSED_OUTPUT
            2 | # ENABLE_WRAP_AT_EOL_OUTPUT
            4 | # ENABLE_VIRTUAL_TERMINAL_PROCESSING win 10+ only
            8   # DISABLE_NEWLINE_AUTO_RETURN        win 10+ only
        )
        atexit.register(lambda: ctypes.windll.kernel32.SetConsoleMode(stdout_handle, old_output_mode.value))

        old_input_mode = ctypes.c_uint32()
        stdin_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-10))
        ctypes.windll.kernel32.GetConsoleMode(stdin_handle, ctypes.byref(old_input_mode))
        res = ctypes.windll.kernel32.SetConsoleMode(stdin_handle,
            0x200 # ENABLE_VIRTUAL_TERMINAL_INPUT    win 10+ only
        )
        atexit.register(lambda: ctypes.windll.kernel32.SetConsoleMode(stdin_handle, old_input_mode.value))
    else: # Unix
        import os, signal, termios, tty
        if stdin_is_tty:
            stdin_fd = sys.stdin.fileno()
            orig = termios.tcgetattr(stdin_fd)
            atexit.register(lambda: termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, orig))
            tty.setcbreak(stdin_fd)

        def on_tstp_sig(signum, stack_frame):
            unix_in_tstp_signal = True
            on_exit_common()
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
        def on_cont_sig(signum, stack_frame):
            if stdin_is_tty:
                stdin_fd = sys.stdin.fileno()
                tty.setcbreak(stdin_fd)
            unix_in_tstp_signal = False
            if len(stored_chars):
                # thread will eat the first char
                # pressed after Ctrl-z
                # TODO: fix this? hard since select/poll
                # doesn't work right on cygwin.
                stored_chars.pop()
            unix_screen_is_reset = True
            signal.signal(signal.SIGTSTP, on_tstp_sig)
        signal.signal(signal.SIGTSTP, on_tstp_sig)
        signal.signal(signal.SIGCONT, on_cont_sig)

    def on_exit_common():
        w, h = get_size()
        home_cursor()
        cursor_down(h)
        reset_color()
        show_cursor()
        sys.stdout.flush()
    atexit.register(on_exit_common)
    hide_cursor()
    start_char_loop_thread()

def reset_color():
    global last_fg_col
    global last_bg_col
    last_fg_col = 999 # force explicit set next color use
    last_bg_col = 999 # force explicit set next color use
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

class CONSOLE_CURSOR_INFO(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32),
                ("bVisible", ctypes.c_int)]

class char_union(ctypes.Union):
    _fields_ = [("UnicodeChar", ctypes.c_uint16),
                ("AsciiChar", ctypes.c_char)]
class CHAR_INFO(ctypes.Structure):
    _fields_ = [("Char", char_union),
                ("Attributes", ctypes.c_uint16)]

DEFAULT_GET_SIZE = 80, 40
def get_size():
    if not stdout_is_tty:
        result = DEFAULT_GET_SIZE
    elif is_windows:
        cbuf = CONSOLE_SCREEN_BUFFER_INFO()
        stdout_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-11))
        ctypes.windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(cbuf))
        result = cbuf.srWindow.Right-cbuf.srWindow.Left+1, cbuf.srWindow.Bottom-cbuf.srWindow.Top+1
    else:
        import fcntl, termios, struct
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
        h, w, hp, wp = struct.unpack('HHHH', result)
        result = w, h
    last_get_size = result
    return result

def scroll_down():
    reset_color() # avoid adding bg at bottom
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

last_fg_col = 999
last_bg_col = 999
def rgb3_to_bgr3(col):
    return ((col >> 2) & 1) | (col & 2) | ((col << 2) & 4)
def set_color(fg_col, bg_col):
    global last_fg_col
    global last_bg_col
    if fg_col == last_fg_col and bg_col == last_bg_col:
        return
    last_fg_col = fg_col
    last_bg_col = bg_col
    color = str(fg_col + 28)
    sys.stdout.write('\x1b['+color+'m')
    color = str(bg_col + 38)
    sys.stdout.write('\x1b['+color+'m')

# TODO: any other encodings to check for?
def supports_unicode():
    return sys.stdout.encoding.upper() in ['UTF-8', 'UTF-16', 'UTF-32']

def set_is_windows():
    try:
        import msvcrt
        return True
    except ImportError:
        return False
is_windows = set_is_windows()

def getch_impl():
    # TODO: This windows impl keeps pipes/redirects from working. Need ReadFile for that,
    # with more complicated handling (personally, I'm just going to keep using unix/cygwin
    # for pipe-y debug stuff...)
    if is_windows:
        stdin_handle = ctypes.windll.kernel32.GetStdHandle(ctypes.c_ulong(-10))
        one_char_buf = ctypes.c_uint32()
        chars_read = ctypes.c_uint32()
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

        return chr(one_char_buf.value)
    else: #Unix
        return sys.stdin.read(1)

stored_chars = deque()
def eat_char_loop():
    global stored_chars
    while True:
        if len(stored_chars) < 32 and not unix_in_tstp_signal:
            # safe, b/c only one thread pushes
            stored_chars.append(getch_impl())
        else:
            time.sleep(0.005)
def start_char_loop_thread():
    t = Thread(target=eat_char_loop, args=[])
    t.daemon = True
    t.start()

used_esc_char_list = [
    # arrow keys
    '[A', '[B', '[C', '[D',
    # fkeys
    'OP', 'OQ', 'OR', 'OS', '[15~', '[17~',
    '[18~', '[19~', '[20~', '[21~', '[23~', '[24~',
]
non_zscii_esc_char_list = [
    # home/end
    '[H', '[F',
    # ins/del, pgup/pgdn, alt home/end
    '[2~', '[3~', '[5~', '[6~', '[1~', '[4~',
]
esc_char_list = used_esc_char_list + non_zscii_esc_char_list
def could_be_escape(seq):
    return any(x.startswith(seq) for x in esc_char_list)
def is_zscii_special_key(seq):
    return seq[0] == '\x1b' and seq[1:] in used_esc_char_list

# only run these on the main thread
def getch_or_esc_seq():
    global stored_chars
    sys.stdout.flush()
    while len(stored_chars) == 0:
        time.sleep(0.005)

    # safe, b/c only one thread pops
    c = stored_chars.popleft()

    if ord(c) == 3:
        # 0x03 == ctrl-c is pressed on windows. checked here
        # to keep the raise on the main thread (avoid hang).
        raise KeyboardInterrupt

    if c == '\x1b':
        time.sleep(0.005)
        if peekch():
            seq = ''
            while peekch() and could_be_escape(seq + peekch()):
                seq += stored_chars.popleft()
                time.sleep(0.005)
            if seq not in esc_char_list:
                for s in seq[::-1]:
                    # hurray for threadsafe queues!
                    # preserves order because only this
                    # thread touches the lefthand side.
                    stored_chars.appendleft(s)
            else:
                c += seq

    # puts('\n' + repr(c) + '\n')

    return c

def peekch():
    if len(stored_chars):
        # safe, b/c only one thread peeks/pops
        return stored_chars[0]
    return ''

def puts(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def flush():
    sys.stdout.flush()
