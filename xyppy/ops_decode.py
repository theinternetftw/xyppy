from xyppy.debug import DBG, warn, err
from xyppy.zmath import to_signed_word
import xyppy.ops as ops

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
    def __init__(self, operands, var_op_info):

        self.opcode = None # for debug/tools
        self.is_extended = False # for debug/tools
        self.store_var = None
        self.branch_offset = None
        self.branch_on = None
        self.last_pc_branch_var = None
        self.last_pc_store_var = None

        self.operands = operands
        self.var_op_info = var_op_info
        self.has_dynamic_operands = len(var_op_info) > 0

def decode(env, pc):

    opcode = env.mem[pc]
    form = get_opcode_form(env, opcode)
    count = get_operand_count(opcode, form)

    if form == ExtForm:
        opcode = env.mem[pc+1]

    if form == ShortForm:
        szbyte = (opcode >> 4) & 3
        szbyte = (szbyte << 6) | 0x3f
        operand_ptr = pc+1
        sizes = get_operand_sizes(szbyte)
    elif form == VarForm:
        szbyte = env.mem[pc+1]
        operand_ptr = pc+2
        sizes = get_operand_sizes(szbyte)
        # handle call_vn2/vs2's extra szbyte
        if opcode in (236, 250):
            szbyte2 = env.mem[pc+2]
            sizes += get_operand_sizes(szbyte2)
            operand_ptr = pc+3
    elif form == ExtForm:
        szbyte = env.mem[pc+2]
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
    var_op_info = []
    for i in range(len(sizes)):
        size = sizes[i]
        if size == WordSize:
            operands.append(env.u16(operand_ptr))
            operand_ptr += 2
        elif size == ByteSize:
            operands.append(env.mem[operand_ptr])
            operand_ptr += 1
        elif size == VarSize:
            operands.append(None) #this is fixedup after every load from icache
            var_num = env.mem[operand_ptr]
            var_op_info.append( (i,var_num) )
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

    opinfo = OpInfo(operands, var_op_info)

    opinfo.opcode = opcode
    opinfo.is_extended = form == ExtForm

    if has_store_var[opcode]:
        opinfo.store_var = env.mem[operand_ptr]
        opinfo.last_pc_store_var = operand_ptr # to make quetzal saves easier
        operand_ptr += 1

    if has_branch_var[opcode]: # std:4.7
        branch_info = env.mem[operand_ptr]
        opinfo.last_pc_branch_var = operand_ptr # to make quetzal saves easier
        operand_ptr += 1
        opinfo.branch_on = (branch_info & 128) == 128
        if branch_info & 64:
            opinfo.branch_offset = branch_info & 0x3f
        else:
            branch_offset = branch_info & 0x3f
            branch_offset <<= 8
            branch_offset |= env.mem[operand_ptr]
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

    opfn = dispatch[opcode]
    if not opfn:
        ext_info = ' (extended)' if dispatch == ops.ext_dispatch else ''
        err('unknown z-machine opcode: {}{}'.format(opcode, ext_info))

    return opfn, opinfo, next_pc

