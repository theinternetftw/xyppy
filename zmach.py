import sys

import ops

def err(msg):
    sys.stderr.write('err: '+msg+'\n')
    sys.exit()

def to_signed_word(word):
    if word & 0x8000:
        return -((~word & 0xffff)+1)
    return word
def to_signed_char(char):
    if char & 0x80:
        return -((~char & 0xff)+1)
    return char

def b16_setter(base):
    def setter(self, val):
        val &= 0xffff
        self.env.mem[base] = val >> 0xff
        self.env.mem[base+1] = val & 0xff
    return setter

def u16_prop(base):
    def getter(self): return self.env.u16(base)
    return property(fget=getter, fset=b16_setter(base))

def s16_prop(base):
    def getter(self): return self.env.s16(base)
    return property(fget=getter, fset=b16_setter(base))

def u8_prop(base):
    def getter(self): return self.env.u8(base)
    def setter(self, val): self.env.mem[base] = val & 0xff
    return property(fget=getter, fset=setter)

class Header(object):
        
    def __init__(self, env):
        self.env = env

    version = u8_prop(0x0)
    flags1 = u8_prop(0x1)
    release = u16_prop(0x2)
    high_mem_base = u16_prop(0x4)
    pc = u16_prop(0x6)
    dict_base = u16_prop(0x8)
    obj_tab_base = u16_prop(0xA)
    global_var_base = u16_prop(0xC)
    static_mem_base = u16_prop(0xE)
    flags2 = u16_prop(0x10)

    def serial_getter(self): return self.env.mem[0x12:0x18]
    def serial_setter(self, val): self.env.mem[0x12:0x18] = val
    serial = property(fget=serial_getter, fset=serial_setter)

    abbrev_base = u16_prop(0x18)
    file_len = u16_prop(0x1A)
    file_checksum = u16_prop(0x1C)
    interp_number = u8_prop(0x1E)
    interp_version = u8_prop(0x1F)

    # everything from 0x20 to 0x36 is past V3

class VarForm:
    pass
class ShortForm:
    pass
class ExtForm:
    pass
class LongForm:
    pass

class ZeroOperand:
    pass
class OneOperand:
    pass
class TwoOperand:
    pass
class VarOperand:
    pass

def get_opcode_form(opcode):
    sel = (opcode & 0xc0) >> 6
    if sel == 0b11:
        return VarForm
    elif sel == 0b10:
        return ShortForm
    elif opcode == 190: # and version >= 5
        return ExtForm
    else:
        return LongForm

def get_operand_count(opcode, form):
    if form == VarForm:
        if (opcode >> 5) & 1:
            return VarOperand
        return TwoOperand
    if form == ShortForm:
        if (opcode >> 4) & 3 == 3:
            return ZeroOperand
        return OneOperand
    if form == ExtForm:
        return VarOperand
    return TwoOperand # LongForm

def get_opcode_number(opcode, form, env):
    if form == ShortForm:
        return opcode & 0xf
    if form == ExtForm:
        return env.u8(env.pc+1)
    return opcode & 0x1f

class WordSize:
    pass
class ByteSize:
    pass
class VarSize:
    pass

def get_operand_sizes(szbyte):
    sizes = []
    offset = 6
    while offset >= 0 and (szbyte >> offset) & 3 != 3:
        size = (szbyte >> offset) & 3
        if size == 0b00:
            sizes.append(WordSize)
        elif size == 0b01:
            sizes.append(ByteSize)
        else: # 0b10
            sizes.append(VarSize)
        offset -= 2
    return sizes

class Env:
    def __init__(self, mem):
        self.mem = map(ord,list(mem))
        self.hdr = Header(self)
        self.pc = self.hdr.pc
        self.callstack = [ops.Frame(0)] # dummy frame only for v3
    def u16(self, i):
        high = self.u8(i)
        return (high << 8) | self.u8(i+1)
    def s16(self, i):
        w = self.u16(i)
        return to_signed_word(w)
    def u8(self, i):
        return self.mem[i]
    def s8(self, i):
        c = self.u8(i)
        return to_signed_char(c)

class OpInfo:
    def __init__(self, operands, store_var=None, branch_offset=None, branch_on=None, text=None):
        self.operands = operands
        self.store_var = store_var
        self.branch_offset = branch_offset
        self.branch_on = branch_on
        self.text = text

def step(env):

    opcode = env.u8(env.pc)
    form = get_opcode_form(opcode)
    count = get_operand_count(opcode, form)
    opnum = get_opcode_number(opcode, form, env)

    if form == ShortForm:
        szbyte = (opcode >> 4) & 3
        szbyte = (szbyte << 6) | 0x3f
        operand_ptr = env.pc+1
        sizes = get_operand_sizes(szbyte)
    elif form == VarForm:
        szbyte = env.u8(env.pc+1)
        operand_ptr = env.pc+2
        sizes = get_operand_sizes(szbyte)
    elif form == ExtForm:
        szbyte = env.u8(env.pc+2)
        operand_ptr = env.pc+3
        sizes = get_operand_sizes(szbyte)
    elif form == LongForm:
        operand_ptr = env.pc+1
        sizes = []
        for offset in [6,5]:
            if (opcode >> offset) & 1:
                sizes.append(VarSize)
            else:
                sizes.append(ByteSize)
    else:
        err('unknown opform specified: ' + str(form))

    operands = []
    foundVarStr = ''
    for i in range(len(sizes)):
        if sizes[i] == WordSize:
            operands.append(env.u16(operand_ptr))
            operand_ptr += 2
        elif sizes[i] == ByteSize:
            operands.append(env.u8(operand_ptr))
            operand_ptr += 1
        elif sizes[i] == VarSize:
            var_loc = env.u8(operand_ptr)
            var_value = ops.get_var(env, var_loc)
            operands.append(var_value)
            varname = ops.get_var_name(var_loc)
            foundVarStr += '      found '+str(var_value)+' in '+varname + '\n'
            operand_ptr += 1
        else:
            err('unknown operand size specified: ' + str(sizes[i]))

    opinfo = OpInfo(operands)

    if ops.has_store_var[opcode]:
        opinfo.store_var = env.u8(operand_ptr)
        operand_ptr += 1

    if ops.has_branch_var[opcode]: # std:4.7
        branch_info = env.u8(operand_ptr)
        operand_ptr += 1
        opinfo.branch_on = (branch_info & 128) == 128
        if branch_info & 64:
            opinfo.branch_offset = branch_info & 0x3f
        else:
            branch_offset = branch_info & 0x3f
            branch_offset <<= 8
            branch_offset |= env.u8(operand_ptr)
            operand_ptr += 1
            # sign extend 14b # to 16b
            if branch_offset & 0x2000:
                branch_offset |= 0xc000
            opinfo.branch_offset = to_signed_word(branch_offset)

    if ops.has_text[opcode]:
        while True:
            word = env.u16(operand_ptr)
            operand_ptr += 2
            operands.append(word)
            if word & 0x8000:
                break

    prev_pc = env.pc

    # After all that, operand_ptr should now point to next op
    env.pc = operand_ptr

    def hex_out(bytes):
        s = ''
        for b in bytes:
            s += hex(b) + ' '
        return s
    op_hex = hex_out(env.mem[prev_pc:env.pc])

    if DBG:
        print 'step: pc', hex(prev_pc)
        print '      opcode', opcode
        print '      form', form
        print '      count', count
        print '      opnum', opnum
        if opinfo.store_var:
            print '      store_var', ops.get_var_name(opinfo.store_var)
        if foundVarStr:
            print foundVarStr,
        print '      sizes', sizes
        print '      operands', opinfo.operands
        print '      next_pc', hex(env.pc)
        #print '      bytes', op_hex

    # TODO: decide if opcode should be passed or opnum
    # (i.e. is opnum specific enough, b/c that would simplify things)
    # (also, do we need to know operand types even after fetching them?)
    ops.dispatch[opcode](env, opinfo)

DBG = 0

def main():

    with open(sys.argv[1], 'rb') as f:
        mem = f.read()
        env = Env(mem)
    
    i=0
    while True:
        i += 1
        if DBG:
            print i
        step(env)

if __name__ == '__main__':
    main()

