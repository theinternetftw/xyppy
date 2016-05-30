from debug import DBG, warn, err
from zmath import to_signed_word

import ops

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

def get_opcode_form(env, opcode):
    if opcode == 190:
        return ExtForm
    sel = (opcode & 0xc0) >> 6
    if sel == 0b11:
        return VarForm
    elif sel == 0b10:
        return ShortForm
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

class OpInfo:
    def __init__(self, operands=[], sizes=[], store_var=None, branch_offset=None, branch_on=None, text=None):
        self.operands = operands
        self.store_var = store_var
        self.branch_offset = branch_offset
        self.branch_on = branch_on
        self.text = text
        self.has_dynamic_operands = VarSize in sizes
        self.last_pc_branch_var = None
        self.last_pc_store_var = None
        if self.has_dynamic_operands:
            self.var_op_info = []
            for i in xrange(len(sizes)):
                if sizes[i] == VarSize:
                    pair = i, operands[i]
                    self.var_op_info.append(pair)
    def fixup_dynamic_operands(self, env):
        for i, var_num in self.var_op_info:
            self.operands[i] = ops.get_var(env, var_num)

def decode(env, pc):

    opcode = env.u8(pc)
    form = get_opcode_form(env, opcode)
    count = get_operand_count(opcode, form)

    if form == ExtForm:
        opcode = env.u8(pc+1)

    if form == ShortForm:
        szbyte = (opcode >> 4) & 3
        szbyte = (szbyte << 6) | 0x3f
        operand_ptr = pc+1
        sizes = get_operand_sizes(szbyte)
    elif form == VarForm:
        szbyte = env.u8(pc+1)
        operand_ptr = pc+2
        sizes = get_operand_sizes(szbyte)
        # handle call_vn2/vs2's extra szbyte
        if opcode in (236, 250):
            szbyte2 = env.u8(pc+2)
            sizes += get_operand_sizes(szbyte2)
            operand_ptr = pc+3
    elif form == ExtForm:
        szbyte = env.u8(pc+2)
        operand_ptr = pc+3
        sizes = get_operand_sizes(szbyte)
    elif form == LongForm:
        operand_ptr = pc+1
        sizes = []
        for offset in (6,5):
            if (opcode >> offset) & 1:
                sizes.append(VarSize)
            else:
                sizes.append(ByteSize)
    else:
        err('unknown opform specified: ' + str(form))

    operands = []
    for size in sizes:
        if size == WordSize:
            operands.append(env.u16(operand_ptr))
            operand_ptr += 2
        elif size == ByteSize:
            operands.append(env.u8(operand_ptr))
            operand_ptr += 1
        elif size == VarSize:
            var_loc = env.u8(operand_ptr)
            operands.append(var_loc) #this is fixedup to real val later by OpInfo class
            operand_ptr += 1
        else:
            err('unknown operand size specified: ' + str(size))

    if form == ExtForm:
        dispatch = ops.ext_dispatch
        has_store_var = ops.ext_has_store_var
        has_branch_var = ops.ext_has_branch_var
    else:
        dispatch = ops.dispatch
        has_store_var = ops.has_store_var
        has_branch_var = ops.has_branch_var

    opinfo = OpInfo(operands, sizes)

    if has_store_var[opcode]:
        opinfo.store_var = env.u8(operand_ptr)
        opinfo.last_pc_store_var = operand_ptr # to make quetzal saves easier
        operand_ptr += 1

    if has_branch_var[opcode]: # std:4.7
        branch_info = env.u8(operand_ptr)
        opinfo.last_pc_branch_var = operand_ptr # to make quetzal saves easier
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

    # handle print_ and print_ret's string operand
    if form != ExtForm and opcode in (178, 179):
        while True:
            word = env.u16(operand_ptr)
            operand_ptr += 2
            operands.append(word)
            if word & 0x8000:
                break

    # After all that, operand_ptr should point to the next opcode
    next_pc = operand_ptr

    if DBG:
        def hex_out(bytes):
            s = ''
            for b in bytes:
                s += hex(b) + ' '
            return s
        op_hex = hex_out(env.mem[pc:next_pc])

        warn('decode: pc', hex(pc))
        warn('      opcode', opcode)
        warn('      form', form)
        warn('      count', count)
        if opinfo.store_var:
            warn('      store_var', ops.get_var_name(opinfo.store_var))
        warn('      sizes', sizes)
        warn('      operands', opinfo.operands)
        warn('      next_pc', hex(next_pc))
        #warn('      bytes', op_hex)

    if opinfo.has_dynamic_operands:
        opinfo.fixup_dynamic_operands(env)

    return dispatch[opcode], opinfo, next_pc

