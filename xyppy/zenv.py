from __future__ import print_function
from array import array
import sys

from xyppy import ops, ops_decode, term, vterm
from xyppy.zmath import to_signed_word
from xyppy.debug import DBG, warn, err

def b16_setter(base):
    def setter(self, val):
        val &= 0xffff
        self.env.mem[base] = val >> 8
        self.env.mem[base+1] = val & 0xff
    return setter

def u16_prop(base):
    def getter(self): return self.env.u16(base)
    return property(fget=getter, fset=b16_setter(base))

def u8_prop(base):
    def getter(self): return self.env.mem[base]
    def setter(self, val): self.env.mem[base] = val & 0xff
    return property(fget=getter, fset=setter)

class Header(object):

    # use *_prop for dyn values
    # and just set others from mem
    # in __init__

    def __init__(self, env):
        self.env = env

        self.version = env.mem[0x0]

        self.release = env.u16(0x2)
        self.high_mem_base = env.u16(0x4)
        self.pc = env.u16(0x6)
        self.dict_base = env.u16(0x8)
        self.obj_tab_base = env.u16(0xA)
        self.global_var_base = env.u16(0xC)
        self.static_mem_base = env.u16(0xE)

        self.serial = bytes(bytearray(env.mem[0x12:0x18]))

        self.abbrev_base = env.u16(0x18)
        self.file_len = env.u16(0x1A)
        self.checksum = env.u16(0x1C)

        #everything after 1C is after v3

        self.routine_offset = env.u16(0x28) #div'd by 8
        self.string_offset = env.u16(0x2A) #div'd by 8

        self.term_chars_base = env.u16(0x2E)
        self.alpha_tab_base = env.u16(0x34)
        self.hdr_ext_tab_base = env.u16(0x36)

        self.unicode_tab_base = 0
        self.hdr_ext_tab_length = 0
        if self.hdr_ext_tab_base:
            self.hdr_ext_tab_length = env.u16(self.hdr_ext_tab_base)
            if self.hdr_ext_tab_length >= 3:
                self.unicode_tab_base = env.u16(self.hdr_ext_tab_base+3)

    flags1 = u8_prop(0x1)
    flags2 = u16_prop(0x10)

    #everything after 1C is after v3

    interp_number = u8_prop(0x1E)
    interp_version = u8_prop(0x1F)

    screen_height_lines = u8_prop(0x20)
    screen_width_chars = u8_prop(0x21)
    screen_width_units = u16_prop(0x22)
    screen_height_units = u16_prop(0x24)

    font_width_units = u8_prop(0x26)
    font_height_units = u8_prop(0x27)

    default_bg_color = u8_prop(0x2C)
    default_fg_color = u8_prop(0x2D)

    std_rev_number = u16_prop(0x32)

def set_standard_flags(env):
    hdr = env.hdr

    if hdr.version < 4:
        # no variable-spaced font (bit 6 = 0)
        # no status line (bit 4 = 0)
        hdr.flags1 &= 0b10101111
        # screen splitting available (bit 5 = 1)
        hdr.flags1 |= 0b00100000
    else:
        # no timed keyboard events available (bit 7 = 0)
        # no sound effects available (bit 5 = 0)
        # no italic available (bit 3 = 0)
        # no boldface available (bit 2 = 0)
        # no picture display available (bit 1 = 0)
        hdr.flags1 &= 0b01010000
        # fixed-space font available (bit 4 = 1)
        # color available (bit 0 = 1)
        hdr.flags1 |= 0b00010001

    # uncheck stuff we don't support in flags 2
    # menus (bit 8)
    # sound effects (bit 7)
    # mouse (bit 5)
    # undo (bit 4)
    # and pictures (bit 3)
    hdr.flags2 &= 0b1111111001000111

    # use the apple 2e interp # to fix Beyond Zork compat
    hdr.interp_number = 2

    MAXIMUM_WIDTH = 80
    term_w, term_h = term.get_size()
    if term_w > 1:
        # FIXME: (?) inform games or bash or something (me?) seems to have
        # trouble pushing all the way to the edge of terminals. Saving a
        # column is also handy for having a spot for the scroll-pause symbol,
        # which, take NOTE, *doesn't* have trouble being drawn at the edge.
        term_w -= 1

    hdr.screen_width_units = min(MAXIMUM_WIDTH, term_w)
    hdr.screen_height_units = term_h

    hdr.screen_width_chars = hdr.screen_width_units
    hdr.screen_height_lines = hdr.screen_height_units

    hdr.font_width_units = 1
    hdr.font_height_units = 1

    hdr.default_fg_color = 9
    hdr.default_bg_color = 2

    # clear flags 3 (S 11.1.7.4.1)
    if hdr.hdr_ext_tab_length >= 4:
        env.mem[hdr.hdr_ext_tab_base + 4] = 0

class Env:
    def __init__(self, mem, options):
        self.orig_mem = mem
        self.mem = array('B', mem)

        self.options = options

        self.hdr = Header(self)
        set_standard_flags(self)

        self.pc = self.hdr.pc
        self.callstack = [ops.Frame(0)]
        self.icache = {}
        self.fncache = {}

        self.fg_color = self.hdr.default_fg_color
        self.bg_color = self.hdr.default_bg_color

        # to make quetzal saves easier
        self.last_pc_branch_var = None
        self.last_pc_store_var = None

        self.output_buffer = {
            1: vterm.Screen(self),
            2: '', # transcript
            3: '', # mem
            4: ''  # player input (not impld atm)
        }
        self.screen = self.output_buffer[1]
        self.cursor = {
            0:(0,0),
            1:(0,0)
        }
        if self.hdr.version <= 4:
            self.cursor[0] = (self.hdr.screen_height_units-1, 0)

        self.text_style = 'normal'

        self.selected_ostreams = set([1])
        self.memory_ostream_stack = []
        self.use_buffered_output = True

        self.current_window = 0
        self.top_window_height = 0

    def fixup_after_restore(self):
        # make sure our standard flags are set after load
        set_standard_flags(self)

    def u16(self, i):
        return (self.mem[i] << 8) | self.mem[i+1]
    def check_dyn_mem(self, i):
        if i >= self.hdr.static_mem_base:
            err('game tried to write in static mem: '+str(i))
        elif i <= 0x36 and i != 0x10:
            err('game tried to write in non-dyn header bytes: '+str(i))
    def write16(self, i, val):
        self.check_dyn_mem(i)
        self.mem[i] = (val >> 8) & 0xff
        self.mem[i+1] = val & 0xff
    def write8(self, i, val):
        self.check_dyn_mem(i)
        self.mem[i] = val & 0xff
    def reset(self):
        # only the bottom two bits of flags2 survive reset
        # (transcribe to printer & fixed pitch font)
        bits_to_save = self.hdr.flags2 & 3
        self.__init__(self.orig_mem, self.options)
        self.hdr.flags2 &= ~3
        self.hdr.flags2 |= bits_to_save
    def quit(self):
        self.screen.flush()
        sys.exit()

def step(env):

    pc, icache = env.pc, env.icache
    if pc in icache:
        op, opinfo, env.pc = icache[pc]
    else:
        op, opinfo, env.pc = ops_decode.decode(env, pc)
        if pc >= env.hdr.static_mem_base:
            icache[pc] = op, opinfo, env.pc

    # fixup dynamic operands
    if opinfo.has_dynamic_operands:
        for i, var_num in opinfo.var_op_info:
            opinfo.operands[i] = ops.get_var(env, var_num)

    # for Quetzal
    if opinfo.last_pc_branch_var:
        env.last_pc_branch_var = opinfo.last_pc_branch_var
    if opinfo.last_pc_store_var:
        env.last_pc_store_var = opinfo.last_pc_store_var

    if DBG:
        warn(hex(pc))
        warn('op:', op.__name__)
        warn('    operands', dbg_decode_operands(env, op.__name__, opinfo.operands))
        if opinfo.branch_offset != None:
            warn('    branch_offset', opinfo.branch_offset)
            warn('    branch_to', dbg_decode_branch(env, opinfo.branch_offset))
            warn('    branch_on', opinfo.branch_on)

        op(env, opinfo)

        if opinfo.store_var:
            warn(    'store_var', ops.get_var_name(opinfo.store_var))
            warn(    'stored_result', dbg_decode_result(env, op.__name__, opinfo.store_var))
    else:
        op(env, opinfo)

def dbg_decode_branch(env, offset):
    if offset == 0 or offset == 1:
        return env.callstack[-1].return_addr
    return env.pc + offset - 2

def dbg_decode_operands(env, opname, operands):
    if opname in ['add', 'sub', 'mul', 'div', 'mod', 'jump', 'random_', 'print_num']:
        return map(to_signed_word, operands)
    elif opname in ['loadw', 'loadb', 'storew', 'storeb', 'inc_chk', 'dec_chk']:
        return [operands[0], to_signed_word(operands[1])] + operands[2:]
    elif opname in ['print_', 'print_ret']:
        result = ops.unpack_string(env, operands)
        if len(result) > 40:
            return repr(result[:40] + '...')
        return result
    return operands

def dbg_decode_result(env, opname, store_var):
    if 'call' in opname:
        return 'unknown (just called)'
    var = ops.get_var(env, store_var, pop_stack=False)
    if opname in ['add', 'sub', 'mul', 'div', 'mod']:
        return to_signed_word(var)
    return var

def dbg_dump_dictionary(env):
    dict_base = env.hdr.dict_base
    num_word_seps = env.mem[dict_base]
    entry_length = env.mem[dict_base+1+num_word_seps]
    num_entries = env.u16(dict_base+1+num_word_seps+1)
    entries_start = dict_base+1+num_word_seps+1+2
    env.screen.write('\n')
    for i in range(num_entries):
        entry_addr = entries_start+i*entry_length
        entry = [env.u16(entry_addr),
                 env.u16(entry_addr+2)]
        entry_unpacked = ops.unpack_string(env, entry, warn_unknown_char=False)
        raw_hex = ' '.join(map(hex, entry))
        env.screen.write(raw_hex + ' ' + repr(entry_unpacked) + '\n')
        env.screen.flush()
