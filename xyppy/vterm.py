import random
import time

import xyppy.term as term
from xyppy.debug import warn

# warning: hack filled nonsense follows, since I'm
# converting a system that expects full control over
# the screen to something that prints linearly in
# the terminal

def write_char(c, fg_col, bg_col, style):
    # '\n' check b/c reverse video col isn't suppose to stretch across window
    # guessing that based on S 8.7.3.1
    if style == 'reverse_video' and c != '\n':
        fg_col, bg_col = bg_col, fg_col
    # no other styling for now
    term.write_char_with_color(c, fg_col, bg_col)

class ScreenChar(object):
    def __init__(self, char, fg_color, bg_color, text_style):
        self.char = char
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.text_style = text_style
    def __str__(self):
        return self.char
    def __eq__(self, sc2):
        return (self.char == sc2.char and
                self.fg_color == sc2.fg_color and
                self.bg_color == sc2.bg_color and
                self.text_style == sc2.text_style)

def sc_line_to_string(line):
    return repr(''.join(map(lambda x: x.char, line)))

# so we can hash it
class ScreenLine(object):
    def __init__(self, line):
        self.line = line
        self.inithash = random.randint(0, 0xffffffff)
    def __getitem__(self, idx):
        return self.line[idx]
    def __setitem__(self, idx, val):
        self.line[idx] = val
    def __len__(self):
        return len(self.line)
    def __iter__(self):
        return self.line.__iter__()
    def __hash__(self):
        return self.inithash

class Screen(object):
    def __init__(self, env):
        self.env = env
        self.textBuf = self.make_screen_buf()
        self.seenBuf = {line: True for line in self.textBuf}
        self.wrapBuf = []
        self.haveNotScrolled = True

    def make_screen_buf(self):
        return [self.make_screen_line() for i in range(self.env.hdr.screen_height_units)]

    def make_screen_line(self):
        c, fg, bg, style = ' ', self.env.fg_color, self.env.bg_color, 'normal'
        return ScreenLine([ScreenChar(c, fg, bg, style) for i in range(self.env.hdr.screen_width_units)])

    def blank_top_win(self):
        env = self.env
        term.home_cursor()
        for i in range(env.top_window_height):
            write_char('\n', env.fg_color, env.bg_color, env.text_style)
            self.textBuf[i] = self.make_screen_line()
            self.seenBuf[self.textBuf[i]] = False

    def blank_bottom_win(self):
        for i in range(self.env.top_window_height, self.env.hdr.screen_height_units):
            self.scroll()

    def write(self, text):
        env = self.env

        # the spec suggests pushing the bottom window cursor down.
        # to allow for more trinity box tricks (admittedly only seen so
        # far in baby_tree.zblorb), we'll do that only when it's
        # being written to.
        if env.current_window == 0 and env.cursor[0][0] < env.top_window_height:
            env.cursor[0] = env.top_window_height, env.cursor[0][1]

        as_screenchars = map(lambda c: ScreenChar(c, env.fg_color, env.bg_color, env.text_style), text)
        if env.current_window == 0 and env.use_buffered_output:
            self.write_wrapped(as_screenchars)
        else:
            self.write_unwrapped(as_screenchars)

    # for when it's useful to make a hole in the scroll text
    # e.g. moving already written text around to make room for
    # what's about to become a new split window
    def scroll_top_line_only(self):
        env = self.env
        old_line = self.textBuf[env.top_window_height]

        # avoid some moderately rare shifting text glitches (when possible)
        if self.haveNotScrolled and line_empty(old_line):
            return

        if not self.seenBuf[old_line] and not line_empty(old_line):
            self.pause_scroll_for_user_input()

        term.home_cursor()
        self.overwrite_line_with(old_line)
        term.scroll_down()

        new_line = self.make_screen_line()
        self.textBuf[env.top_window_height] = new_line
        self.seenBuf[new_line] = False

        self.haveNotScrolled = False

    def scroll(self, count_lines=True):
        env = self.env

        if not self.seenBuf[self.textBuf[env.top_window_height]]:
            if not buf_empty(self.textBuf[env.top_window_height:]):
                self.pause_scroll_for_user_input()

        old_line = self.textBuf.pop(env.top_window_height)

        term.home_cursor()
        self.overwrite_line_with(old_line)
        term.scroll_down()

        new_line = self.make_screen_line()
        self.textBuf.append(new_line)
        self.seenBuf[new_line] = False

        self.haveNotScrolled = False

        self.slow_scroll_effect()

    def update_seen_lines(self):
        self.seenBuf = {line: True for line in self.textBuf}

    def pause_scroll_for_user_input(self):
        # TODO: mark last paused line, set it up so such lines get
        # marked with a plus when still in the buffer, to help your
        # eye track the scroll.
        self.flush()
        if not buf_empty(self.textBuf):
            term_width, term_height = term.get_size()
            if term_width - self.env.hdr.screen_width_units > 0:
                term.home_cursor()
                term.cursor_down(term_height-1)
                # we reserve a one unit right margin for this status char
                term.cursor_right(self.env.hdr.screen_width_units)
                term.write_char_with_color('+', self.env.fg_color, self.env.bg_color)
            term.getch_or_esc_seq()
        self.update_seen_lines()

    def overwrite_line_with(self, new_line):
        term.clear_line()
        for c in new_line:
            write_char(c.char, c.fg_color, c.bg_color, c.text_style)
        term.fill_to_eol_with_bg_color()

    # TODO: fun but slow, make a config option
    def slow_scroll_effect(self):
        if not self.env.options.no_slow_scroll:
            if not term.is_windows: # windows is slow enough, atm :/
                self.flush()
                time.sleep(0.002)

    def new_line(self):
        env, win = self.env, self.env.current_window
        row, col = env.cursor[win]
        if win == 0:
            if row+1 == env.hdr.screen_height_units:
                self.scroll()
                env.cursor[win] = row, 0
            else:
                self.slow_scroll_effect()
                env.cursor[win] = row+1, 0
        else:
            if row+1 < env.top_window_height:
                env.cursor[win] = row+1, 0
            else:
                env.cursor[win] = row, col-1 # as suggested by spec

    def write_wrapped(self, text_as_screenchars):
        self.wrapBuf += text_as_screenchars

    # for bg_color propagation (only happens when a newline comes in via wrapping, it seems)
    def new_line_via_spaces(self, fg_color, bg_color, text_style):
        env, win = self.env, self.env.current_window
        row, col = env.cursor[win]
        self.write_unwrapped([ScreenChar(' ', fg_color, bg_color, text_style)])
        while env.cursor[win][1] > col:
            self.write_unwrapped([ScreenChar(' ', fg_color, bg_color, text_style)])

    def finish_wrapping(self):
        env = self.env
        win = env.current_window
        text = self.wrapBuf
        self.wrapBuf = []
        def find_char_or_return_len(cs, c):
            for i in range(len(cs)):
                if cs[i].char == c:
                    return i
            return len(cs)
        def collapse_on_newline(cs):
            if env.cursor[win][1] == 0:
                # collapse all spaces
                while len(cs) > 0 and cs[0].char == ' ':
                    cs = cs[1:]
                # collapse the first newline (as we just generated one)
                if len(cs) > 0 and cs[0].char == '\n':
                    cs = cs[1:]
            return cs
        while text:
            if text[0].char == '\n':
                self.new_line_via_spaces(text[0].fg_color, text[0].bg_color, text[0].text_style)
                text = text[1:]
            elif text[0].char == ' ':
                self.write_unwrapped([text[0]])
                text = text[1:]
                text = collapse_on_newline(text)
            else:
                first_space = find_char_or_return_len(text, ' ')
                first_nl = find_char_or_return_len(text, '\n')
                word = text[:min(first_space, first_nl)]
                text = text[min(first_space, first_nl):]
                if len(word) > env.hdr.screen_width_units:
                    self.write_unwrapped(word)
                elif env.cursor[win][1] + len(word) > env.hdr.screen_width_units:
                    self.new_line_via_spaces(word[0].fg_color, word[0].bg_color, word[0].text_style)
                    self.write_unwrapped(word)
                else:
                    self.write_unwrapped(word)
                text = collapse_on_newline(text)

    def write_unwrapped(self, text_as_screenchars, already_seen=False):
        env = self.env
        win = env.current_window
        w = env.hdr.screen_width_units
        for c in text_as_screenchars:
            if c.char == '\n':
                self.new_line()
            else:
                y, x = env.cursor[win]
                oldc = self.textBuf[y][x]
                self.textBuf[y][x] = c
                if c != oldc and not already_seen:
                    self.seenBuf[self.textBuf[y]] = False
                env.cursor[win] = y, x+1
                if x+1 == w:
                    self.new_line()

    def flush(self):
        self.finish_wrapping()
        term.home_cursor()
        buf = self.textBuf
        for i in range(len(buf)):
            for j in range(len(buf[i])):
                c = buf[i][j]
                write_char(c.char, c.fg_color, c.bg_color, c.text_style)
            if i < len(buf) - 1:
                write_char('\n', c.fg_color, c.bg_color, c.text_style)
            else:
                term.fill_to_eol_with_bg_color()
        term.flush()

    def get_line_of_input(self, prompt='', prefilled=''):
        env = self.env

        for c in prompt:
            self.write_unwrapped([ScreenChar(c, env.fg_color, env.bg_color, env.text_style)], already_seen=True)
        self.flush()
        self.update_seen_lines()

        row, col = env.cursor[env.current_window]

        term.home_cursor()
        term.cursor_down(row)
        term.cursor_right(col)
        term.set_color(env.fg_color, env.bg_color)
        if line_empty(self.textBuf[row][col:]):
            term.fill_to_eol_with_bg_color()
        term.show_cursor()

        col = max(0, col-len(prefilled)) # TODO: prefilled is a seldom-used old and crusty feature, but make unicode safe
        env.cursor[env.current_window] = row, col

        class CursorLine(object):
            def __init__(self, cursor_start, chars):
                self.cursor = cursor_start
                self.chars = chars

            def backspace(self):
                if self.cursor == 0:
                    return
                self.left()
                self.delete_char()

            def delete_char(self):
                del self.chars[self.cursor : self.cursor+1]
                self.refresh_rest_of_line(is_delete=True)

            def refresh_rest_of_line(self, is_delete=False):
                rest = self.chars[self.cursor:]
                term.puts(''.join(rest))
                to_back_up = len(rest)
                if is_delete:
                    term.puts(' ')
                    to_back_up += 1
                if to_back_up:
                    term.cursor_left(to_back_up)

            def left(self):
                if self.cursor > 0:
                    self.cursor -= 1
                    term.cursor_left()

            def right(self):
                if self.cursor < len(self.chars):
                    self.cursor += 1
                    term.cursor_right()

            def home(self):
                while self.cursor > 0:
                    self.left()

            def end(self):
                while self.cursor != len(self.chars):
                    self.right()

            def kill_left(self):
                while self.chars[:self.cursor]:
                    self.backspace()

            def kill_right(self):
                while self.chars[self.cursor:]:
                    self.delete_char()

            def insert(self, c):
                self.chars.insert(self.cursor, c)
                term.puts(c)
                self.cursor += 1
                self.refresh_rest_of_line()

        cursor_start = len(prefilled)
        cursor_line = CursorLine(cursor_start, [c for c in prefilled])

        max_input_len = 120 # 120 char limit seen on gargoyle
        c = term.getch_or_esc_seq()
        while c != '\n' and c != '\r':
            if c == '\b' or c == '\x7f':
                cursor_line.backspace()

            # normal edit keys and a bit of readline flavor

            # left arrow or C-b
            elif c == '\x1b[D' or c == '\x02':
                cursor_line.left()

            # right arrow or C-f
            elif c == '\x1b[C' or c == '\x06':
                cursor_line.right()

            # home or C-a
            elif c == '\x1b[H' or c == '\x01':
                cursor_line.home()

            # end or C-e
            elif c == '\x1b[F' or c == '\x05':
                cursor_line.end()

            # delete or C-d
            elif c == '\x1b[3~' or c == '\x04':
                cursor_line.delete_char()

            # C-u, kill left of cursor
            elif c == '\x15':
                cursor_line.kill_left()

            # C-k, kill right of cursor
            elif c == '\x0b':
                cursor_line.kill_right()

            else:
                if is_valid_inline_char(c) and len(cursor_line.chars) < max_input_len:
                    if c == '\t':
                        if len(cursor_line.chars) + 4 <= max_input_len:
                            for i in range(4):
                                cursor_line.insert(' ')
                    else:
                        cursor_line.insert(c)

            c = term.getch_or_esc_seq()

        term.hide_cursor()
        term.flush()
        for c in cursor_line.chars:
            self.write_unwrapped([ScreenChar(c, env.fg_color, env.bg_color, env.text_style)], already_seen=True)
        self.new_line_via_spaces(env.fg_color, env.bg_color, env.text_style)
        term.home_cursor()
        return ''.join(cursor_line.chars)

    def first_draw(self):
        env = self.env
        for i in range(env.hdr.screen_height_units-1):
            write_char('\n', env.fg_color, env.bg_color, env.text_style)
        term.fill_to_eol_with_bg_color()
        term.home_cursor()

    def getch_or_esc_seq(self):
        self.flush()
        c = term.getch_or_esc_seq()
        self.update_seen_lines()
        if c == '\x7f': #delete should be backspace
            c = '\b'
        if not is_valid_getch_char(c):
            return '?'
        return c

    # for save game error messages and such
    # TODO: better formatting here (?)
    def msg(self, text):
        self.write(text)
        self.write('[press any key to continue]\n')
        self.flush()
        term.getch_or_esc_seq()

def buf_empty(buf):
    for line in buf:
        if not line_empty(line):
            return False
    return True

def line_empty(line):
    for c in line:
        if c.char != ' ':
            return False
    return True

def is_valid_getch_char(c):
    # TODO: unicode input?
    return (
        c in ['\n', '\t', '\r', '\b', '\x1b'] or
        term.is_zscii_special_key(c) or
        (len(c) == 1 and ord(c) > 31 and ord(c) < 127)
    )

def is_valid_inline_char(c):
    # TODO: unicode input?
    return c in ['\n', '\t', '\r', '\b'] or (len(c) == 1 and ord(c) > 31 and ord(c) < 127)
