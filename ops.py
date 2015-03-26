# this can always be changed
# to a list if for some reason
# dict lookup is too slow

import sys

from zmach import to_signed_word, to_signed_char, err, DBG

class Frame:
    def __init__(self, return_addr, locals=[], return_val_loc=None):
        self.return_addr = return_addr
        self.locals = locals
        self.stack = []
        self.return_val_loc = return_val_loc

def get_var(env, var_num, auto_pop_stack=True):
    frame = env.callstack[-1]
    if var_num < 0 or var_num > 0xff:
        err('illegal var num: '+str(var_num))

    if var_num == 0:
        if auto_pop_stack:
            return frame.stack.pop()
        else:
            return frame.stack[-1]
    elif var_num < 16:
        return frame.locals[var_num - 1]
    else: # < 0xff
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        return env.u16(g_base + 2*g_idx)

def set_var(env, store_var, result):
    result &= 0xffff

    if store_var < 0 or store_var > 0xff:
        err('illegal store var: '+str(store_var))

    if store_var == 0:
        frame = env.callstack[-1]
        frame.stack.append(result)
    elif store_var < 16:
        frame = env.callstack[-1]
        frame.locals[store_var - 1] = result
    else: # < 0xff
        g_idx = store_var - 16
        g_base = env.hdr.global_var_base
        env.mem[g_base + 2*g_idx] = result >> 0xff
        env.mem[g_base + 2*g_idx + 1] = result & 0xff

def sub(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    set_var(env, opinfo.store_var, a-b)

    if DBG:
        print 'op: subtracting',a,'and',b
        print '    storing',(a-b),'in',opinfo.store_var

def add(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    set_var(env, opinfo.store_var, a+b)

    if DBG:
        print 'op: adding',a,'and',b
        print '    storing',(a+b),'in',opinfo.store_var

def call(env, opinfo):
    return_addr = env.pc
    call_addr = env.unpack_addr(opinfo.operands[0])
    num_locals = env.u8(call_addr)

    # this read only necessary in v1-v4
    # v5 and later auto-set them to zero
    locals_ptr = call_addr + 1
    locals = []
    for i in range(num_locals):
        locals.append(env.u16(locals_ptr))
        locals_ptr += 2

    code_ptr = locals_ptr

    args = opinfo.operands[1:]
    # args dropped if past len of locals arr
    num_args = min(len(args), len(locals))
    for i in range(num_args):
        locals[i] = args[i]

    env.callstack.append(Frame(return_addr, locals, opinfo.store_var))
    env.pc = code_ptr

    if DBG:
        print 'op: calling', hex(call_addr)
        print '    returning to', hex(return_addr)
        print '    using args', args
        print '    return val will be placed in', opinfo.store_var
        print '    num locals:', env.u8(call_addr)
        print '    local vals:', locals
        print '    code ptr:', hex(code_ptr)
        print '    first inst:', env.u8(code_ptr)

def ret(env, opinfo):
    return_val = opinfo.operands[0]
    frame = env.callstack.pop()
    set_var(env, frame.return_val_loc, return_val)
    env.pc = frame.return_addr

    if DBG:
        print 'op: ret'
        print '    return_val', return_val
        print '    return_val_loc', frame.return_val_loc
        print '    return_addr', hex(frame.return_addr)

def jz(env, opinfo):
    result = opinfo.operands[0] == 0

    if result != opinfo.branch_on:
        if DBG:
            print 'op: jump zero (zero) (not taken)'
            print '    operand', opinfo.operands[0]
            print '    branch_on', opinfo.branch_on
        return

    postjmp_addr = env.pc + opinfo.branch_offset - 2
    postjmp_inst = env.u8(postjmp_addr)

    if opinfo.branch_offset == 0:
        err('should return false here (jz shortcut)')
    if opinfo.branch_offset == 1:
        err('should return true here (jz shortcut)')

    env.pc = postjmp_addr

    if DBG:
        print 'op: jump zero (jz) (taken)'
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on
        print '    postjmp_addr', hex(postjmp_addr)

def je(env, opinfo):
    first = opinfo.operands[0]
    result = True
    for operand in opinfo.operands[1:]:
        if first != operand:
            result = False
            break

    if result != opinfo.branch_on:
        if DBG:
            print 'op: jump equal (je) (not taken)'
            print '    operands', opinfo.operands
            print '    branch_on', opinfo.branch_on
        return

    postjmp_addr = env.pc + opinfo.branch_offset - 2
    postjmp_inst = env.u8(postjmp_addr)

    if opinfo.branch_offset == 0:
        err('should return false here (je shortcut)')
    if opinfo.branch_offset == 1:
        err('should return true here (je shortcut)')

    env.pc = postjmp_addr

    if DBG:
        print 'op: jump equal (je) (taken)'
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on
        print '    postjmp_addr', hex(postjmp_addr)

def jump(env, opinfo):
    offset = to_signed_word(opinfo.operands[0])
    env.pc += offset - 2

    if DBG:
        print 'op: jump'
        print '    offset', offset
        print '    new pc', hex(env.pc)

def loadw(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = opinfo.operands[1]
    word_loc = array_addr + 2*word_index

    set_var(env, opinfo.store_var, env.u16(word_loc))
    
    if DBG:
        print 'op: loadw'
        print '    array_addr', array_addr
        print '    word_index', word_index
        print '    value', env.u16(word_loc)
        print '    store_var', opinfo.store_var

def loadb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = opinfo.operands[1]
    byte_loc = array_addr + byte_index

    set_var(env, opinfo.store_var, env.u8(byte_loc))
    
    if DBG:
        print 'op: loadb'
        print '    array_addr', array_addr
        print '    byte_index', byte_index
        print '    value', env.u8(byte_loc)
        print '    store_var', opinfo.store_var

def storew(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = opinfo.operands[1]
    val = opinfo.operands[2] & 0xffff
    word_loc = array_addr + 2*word_index

    env.mem[word_loc] = val >> 8
    env.mem[word_loc+1] = val & 0xff
    
    if DBG:
        print 'op: storew'
        print '    array_addr', array_addr
        print '    word_index', word_index
        print '    value', val

def store(env, opinfo):
    dest = opinfo.operands[0]
    val = opinfo.operands[1]
    set_var(env, dest, val)
    if DBG:
        print 'op: store', val, 'in', dest

def insert_obj(env, opinfo):
    obj = opinfo.operands[0]
    dest = opinfo.operands[1]

    tab = env.hdr.obj_tab_base
    tab += 31*2 # go past default props

    obj_loc = tab + 9*(obj-1)
    dest_loc = tab + 9*(dest-1)
    dest_child = env.u8(dest_loc+6)

    env.mem[obj_loc+5] = dest_child
    env.mem[dest_loc+6] = obj

    if DBG:
        print 'op: insert_obj'
        print '    obj after insert:', env.mem[obj_loc:obj_loc+9]
        print '    dest after insert:', env.mem[dest_loc:dest_loc+9]

A0 = 'abcdefghijklmnopqrstuvwxyz'
A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
A2 = ' \n0123456789.,!?_#\'"/\-:()'

def read_packed_string(env, addr):
    packed_string = []
    while True:
        word = env.u16(addr)
        packed_string.append(word)
        if word & 0x8000:
            break
        addr += 2
    return packed_string

def unpack_text(env, packed_text):

    split_text = []
    for word in packed_text:
        split_text += [word >> 10 & 0x1f,
                       word >> 5 & 0x1f,
                       word & 0x1f]

    #check the differences between v1/v2 and v3 here
    #going w/ v3 compat only atm

    text = []
    currentAlphabet = A0
    abbrevShift = 0
    current_10bit = 0
    mode = 'NONE'
    for i in range(len(split_text)):
        char = split_text[i]
        if abbrevShift > 0:
            table_addr = env.hdr.abbrev_base
            entry_addr = table_addr + 2*(32*(abbrevShift-1) + char)
            word_addr = env.u16(entry_addr)
            packed_string = read_packed_string(env, word_addr*2)
            text += unpack_text(env, packed_string)
            abbrevShift = 0
        elif mode == '10BIT_HIGH':
            mode = '10BIT_LOW'
            current_10bit = char << 5
        elif mode == '10BIT_LOW':
            mode = 'NONE'
            current_10bit |= char
            print current_10bit
        elif char == 0:
            text.append(' ')
            currentAlphabet = A0
        elif char == 4:
            currentAlphabet = A1
        elif char == 5:
            currentAlphabet = A2
        elif char == 6 and currentAlphabet == A2:
            mode = '10BIT_HIGH'
            currentAlphabet = A0
        elif char in [1,2,3]:
            abbrevShift = char
            currentAlphabet = A0
        else:
            text.append(currentAlphabet[char-6])
            currentAlphabet = A0

    return ''.join(text)

def _print(env, opinfo):
    sys.stdout.write(unpack_text(env, opinfo.operands))

    if DBG:
        print
        print 'op: print'
        print '    packed_len', len(opinfo.operands)

# for higher version compat one day maybe
def unpack_addr(addr):
    return addr * 2 #just v3 for now

def print_paddr(env, opinfo):
    addr = unpack_addr(opinfo.operands[0])
    packed_text = []
    while True:
        word = env.u16(addr)
        addr += 2
        packed_text.append(word)
        if word & 0x8000:
            break

    sys.stdout.write(unpack_text(env, packed_text))

    if DBG:
        print
        print 'op: print_paddr'

def new_line(env, opinfo):
    sys.stdout.write('\n')
    if DBG:
        print
        print 'op: new_line'

def _and(env, opinfo):
    acc = opinfo.operands[0]
    for operand in opinfo.operands[1:]:
        acc &= operand
    set_var(env, opinfo.store_var, acc)
    if DBG:
        print 'op: and'
        print '    operands', opinfo.operands
        print '    result', acc

def print_num(env, opinfo):
    num = opinfo.operands[0]
    sys.stdout.write(str(num))
    if DBG:
        print
        print 'op: print_num'
        print '    num', num

def inc_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = opinfo.operands[1]

    var_val = get_var(env, var_loc) + 1
    set_var(env, var_loc, var_val)
    result = var_val > chk_val
    if result == opinfo.branch_on:
        env.pc += opinfo.branch_offset

    if DBG:
        print
        print 'op: inc_chk ( branched =',(result==opinfo.branch_on),')'
        print '    chk_val', chk_val
        print '    var_loc', var_loc
        print '    var_val', var_val
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

#std: 3.8
def zscii_to_ascii(clist):
    result = ''
    for c in clist:
        if c > 31 and c < 127:
            result += chr(c)
        else:
            err('rest of zscii not yet implemented')
    return result

def print_char(env, opinfo):
    char = zscii_to_ascii([opinfo.operands[0]])
    sys.stdout.write(char)
    if DBG:
        print
        print 'op print_char'

dispatch = {}
has_branch_var = {}
has_store_var = {}
has_text = {}

def op(opcode, f, svar=False, bvar=False, txt=False):
    dispatch[opcode] = f
    has_store_var[opcode] = svar
    has_branch_var[opcode] = bvar
    has_text[opcode] = txt

op(5,   inc_chk,                  bvar=True)
op(13,  store)
op(15,  loadw,       svar=True)
op(48,  loadb,       svar=True)
op(79,  loadw,       svar=True)
op(84,  add,         svar=True)
op(85,  sub,         svar=True)
op(97,  je,                       bvar=True)
op(110, insert_obj)
op(116, add,         svar=True)
op(140, jump)
op(160, jz,                       bvar=True)
op(171, ret)
op(173, print_paddr)
op(178, _print,                                txt=True)
op(187, new_line)
op(201, _and,        svar=True)
op(224, call,        svar=True)
op(225, storew)
op(229, print_char)
op(230, print_num)

