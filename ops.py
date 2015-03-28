# this can always be changed
# to a list if for some reason
# dict lookup is too slow

import sys
import random

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
    result = a-b
    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: subtracting',a,'and',b
        print '    storing',result,'in',opinfo.store_var

def add(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a+b
    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: adding',a,'and',b
        print '    storing',result,'in',opinfo.store_var

def div(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a // b
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        print 'op: diving',a,'and',b
        print '    storing',result,'in',opinfo.store_var

def call(env, opinfo):

    packed_addr = opinfo.operands[0]
    if packed_addr == 0:
        set_var(env, opinfo.store_var, 0)
        if DBG:
            print 'op: calling 0 (returns false)'
        return

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

def handle_return(env, return_val):
    frame = env.callstack.pop()
    set_var(env, frame.return_val_loc, return_val)
    env.pc = frame.return_addr

    if DBG:
        print 'helper: handle_return'
        print '    return_val', return_val
        print '    return_val_loc', frame.return_val_loc
        print '    return_addr', hex(frame.return_addr)

def ret(env, opinfo):
    return_val = opinfo.operands[0]
    handle_return(env, return_val)

    if DBG:
        print 'op: ret'

def rtrue(env, opinfo):
    handle_return(env, 1)

    if DBG:
        print 'op: rtrue'

def rfalse(env, opinfo):
    handle_return(env, 0)

    if DBG:
        print 'op: rfalse'

def ret_popped(env, opinfo):
    frame = env.callstack[-1]
    ret_val = frame.stack.pop()
    handle_return(env, ret_val)

    if DBG:
        print 'op: ret_popped'
        print '    ret_val', ret_val

def jz(env, opinfo):
    result = opinfo.operands[0] == 0

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        print 'op: jump zero (jz) ('+jump_info_txt+')'
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on

def je(env, opinfo):
    first = opinfo.operands[0]
    result = True
    for operand in opinfo.operands[1:]:
        if first != operand:
            result = False
            break

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        print 'op: jump equal (je) ('+jump_info_txt+')'
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on

def jl(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a < b

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        print 'op: jump less than (jl) ('+jump_info_txt+')'
        print '    a', a
        print '    b', b
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on

def jg(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a > b

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        print 'op: jump greater than (jg) ('+jump_info_txt+')'
        print '    a', a
        print '    b', b
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on

def handle_branch(env, offset):
    if offset == 0:
        handle_return(env, 0)
    elif offset == 1:
        handle_return(env, 1)
    else:
        env.pc += offset - 2

def jump(env, opinfo):
    offset = to_signed_word(opinfo.operands[0])
    env.pc += offset - 2

    if DBG:
        print 'op: jump'
        print '    offset', offset

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

def storeb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = opinfo.operands[1]
    val = opinfo.operands[2] & 0xff

    env.mem[array_addr+byte_index] = val
    
    if DBG:
        print 'op: storeb'
        print '    array_addr', array_addr
        print '    byte_index', byte_index
        print '    value', val

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

    # it doesn't say explicitly to make obj's parent
    # field say dest, but *surely* that's the right
    # thing to do. Right?

    env.mem[obj_loc+4] = dest
    env.mem[obj_loc+5] = dest_child
    env.mem[dest_loc+6] = obj

    if DBG:
        print 'op: insert_obj'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    dest', dest, '(', get_obj_str(env,dest), ')'
        print '    obj after insert:', env.mem[obj_loc:obj_loc+9]
        print '    dest after insert:', env.mem[dest_loc:dest_loc+9]

def get_obj_addr(env, obj):
    tab = env.hdr.obj_tab_base
    tab += 31*2 # go past default props
    return tab + 9*(obj-1)

# split these off to suggest structure for future compat...
def get_parent_num(env, obj_addr):
    return env.u8(obj_addr+4)

def get_sibling_num(env, obj_addr):
    return env.u8(obj_addr+5)

def get_child_num(env, obj_addr):
    return env.u8(obj_addr+6)

def get_child(env, opinfo):
    obj = opinfo.operands[0]

    obj_addr = get_obj_addr(env, obj)
    child_num = get_child_num(env, obj_addr)
    set_var(env, opinfo.store_var, child_num)

    result = child_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: get_child ( branched =',(result==opinfo.branch_on),')'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    child_num', child_num
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def get_sibling(env, opinfo):
    obj = opinfo.operands[0]

    obj_addr = get_obj_addr(env, obj)
    sibling_num = get_sibling_num(env, obj_addr)
    set_var(env, opinfo.store_var, sibling_num)

    result = sibling_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: get_sibling ( branched =',(result==opinfo.branch_on),')'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    sibling_num', sibling_num
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def get_parent(env, opinfo):
    obj = opinfo.operands[0]

    obj_addr = get_obj_addr(env, obj)
    parent_num = get_parent_num(env, obj_addr)
    set_var(env, opinfo.store_var, parent_num)

    if DBG:
        print 'op: get_parent'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    parent_num', parent_num

def jin(env, opinfo):
    obj1 = opinfo.operands[0]
    obj2 = opinfo.operands[1]

    obj1_addr = get_obj_addr(env, obj1)
    
    result = env.mem[obj1_addr+4] == obj2

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: jin ( branch =',(result==opinfo.branch_on),')'
        print '    obj1', obj1, '(',get_obj_str(env,obj1),')'
        print '    obj2', obj2, '(',get_obj_str(env,obj2),')'

def get_obj_str(env, obj):
    obj_addr = get_obj_addr(env, obj)
    obj_desc_addr = env.u16(obj_addr+7)+1
    obj_desc_packed = read_packed_string(env, obj_desc_addr)

    return unpack_string(env, obj_desc_packed)

def print_obj(env, opinfo):
    obj = opinfo.operands[0]
    sys.stdout.write(get_obj_str(env, obj))

    if DBG:
        print
        print 'op: print_obj'
        print '    obj', obj, '(', get_obj_str(env, obj), ')'

def set_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    mask = 2**(7-attr%8)
    env.mem[obj_addr+attr_byte] |= mask

    if DBG:
        print 'op: set_attr'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    attr', attr
        print '    attr_byte', attr_byte
        print '    mask', mask

def clear_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    mask = 2**(7-attr%8)
    env.mem[obj_addr+attr_byte] &= ~mask

    if DBG:
        print 'op: clear_attr'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    attr', attr
        print '    attr_byte', attr_byte
        print '    mask', mask
        print '    new_byte_val', env.mem[obj_addr+attr_byte]

def test_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    attr_val = env.mem[obj_addr+attr_byte] >> 7-attr%8 & 1
    result = attr_val == 1
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: test_attr ( branch =', (result==opinfo.branch_on), ')'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    attr', attr
        print '    attr_byte', attr_byte
        print '    attr_byte_val', env.mem[obj_addr+attr_byte]
        print '    attr_val', attr_val
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def get_prop_list_start(env, obj):
    prop_tab_addr = env.u16(get_obj_addr(env, obj)+7)
    obj_text_len_words = env.u8(prop_tab_addr)
    return prop_tab_addr + 1 + 2*obj_text_len_words

def print_prop_list(env, obj):
    print obj,'-',get_obj_str(env, obj)+':'
    ptr = get_prop_list_start(env, obj)
    while env.u8(ptr):
        size_and_num = env.u8(ptr)
        num = size_and_num & 31
        size = (size_and_num >> 5) + 1
        print 'prop #',num,' - size',size,
        for i in range(size):
            print hex(env.u8(ptr+1+i)),
        print
        ptr += 1 + size

def get_default_prop(env, prop_num):
    base = env.hdr.obj_tab_base
    return env.u16(base + 2*prop_num)

def put_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]
    val = opinfo.operands[2]

    prop_addr = _get_prop_addr(env, obj, prop_num)
    if prop_addr == 0:
        msg = 'illegal op: put_prop on nonexistant property'
        msg += ' - prop '+str(prop_num)
        msg += ' not found on obj '+str(obj)+' ('+get_obj_str(env, obj)+')' 
        err(msg)
    
    size_and_num = env.u8(prop_addr)
    size = (size_and_num >> 5) + 1
    if size == 2:
        env.mem[prop_addr+1] = val >> 8
        env.mem[prop_addr+2] = val & 0xff
    elif size == 1:
        env.mem[prop_addr+1] = val & 0xff
    else:
        msg = 'illegal op: put_prop on outsized prop (not 1-2 bytes)'
        msg += ' - prop '+str(prop_num)
        msg += ' of obj '+str(obj)+' ('+get_obj_str(obj)+')'
        msg += ' (sized at '+size+' bytes)'
        err(msg)

    if DBG:
        print 'op: put_prop'
        print '    obj', obj,'(',get_obj_str(env,obj),')'
        print '    prop_num', prop_num
        print '    val', val

def _get_prop_addr(env, obj, prop_num):
    prop_ptr = get_prop_list_start(env, obj)
    while env.u8(prop_ptr):
        size_and_num = env.u8(prop_ptr)
        num = size_and_num & 31
        size = (size_and_num >> 5) + 1
        if num == prop_num:
            return prop_ptr
        prop_ptr += 1 + size
    return 0

def get_prop_addr(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    result = _get_prop_addr(env, obj, prop_num)
    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: get_prop_addr'
        print '    obj', obj,'(',get_obj_str(env,obj),')'
        print '    prop_num', prop_num
        print '    result', result

def get_prop_len(env, opinfo):
    prop_data_addr = opinfo.operands[0]
    size_and_num = env.u8(prop_data_addr-1)
    size = (size_and_num >> 5) + 1
    set_var(env, opinfo.store_var, size)
    if DBG:
        print 'op: get_prop_len'
        print '    len', size

def get_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    prop_addr = _get_prop_addr(env, obj, prop_num)
    got_default_prop = prop_addr == 0
    if got_default_prop:
        result = get_default_prop(env, prop_num)
    else:
        size_and_num = env.u8(prop_addr)
        size = (size_and_num >> 5) + 1
        if size == 2:
            result = env.u16(prop_addr+1)
        elif size == 1:
            result = env.u8(prop_addr+1)
        else:
            msg = 'illegal op: get_prop on outsized prop (not 1-2 bytes)'
            msg += ' - prop '+str(prop_num)
            msg += ' of obj '+str(obj)+' ('+get_obj_str(obj)+')'
            msg += ' (sized at '+size+' bytes)'
            err(msg)

    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: get_prop'
        print '    obj', obj,'(',get_obj_str(env,obj),')'
        print '    prop_num', prop_num
        print '    result', result
        print '    got_default_prop', got_default_prop

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

def unpack_string(env, packed_text):

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
            text += unpack_string(env, packed_string)
            abbrevShift = 0
        elif mode == '10BIT_HIGH':
            mode = '10BIT_LOW'
            current_10bit = char << 5
        elif mode == '10BIT_LOW':
            mode = 'NONE'
            current_10bit |= char
            text += zscii_to_ascii([current_10bit])
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
    sys.stdout.write(unpack_string(env, opinfo.operands))

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

    sys.stdout.write(unpack_string(env, packed_text))

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

def inc(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    var_val = var_val+1 & 0xffff
    set_var(env, var_num, var_val)

    if DBG:
        print 'op: inc'
        print '    var_num', var_num
        print '    new_val', to_signed_word(var_val)

def dec(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    var_val = var_val-1 & 0xffff
    set_var(env, var_num, var_val)

    if DBG:
        print 'op: dec'
        print '    var_num', var_num
        print '    new_val', to_signed_word(var_val)

def inc_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = opinfo.operands[1]

    var_val = to_signed_word(get_var(env, var_loc))
    var_val = var_val+1 & 0xffff
    set_var(env, var_loc, var_val)
    result = var_val > chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
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
           err('this zscii char not yet implemented: '+str(c))
    return result

def print_char(env, opinfo):
    char = zscii_to_ascii([opinfo.operands[0]])
    sys.stdout.write(char)
    if DBG:
        print
        print 'op: print_char'

def pop(env, opinfo):
    frame = env.callstack[-1]
    frame.stack.pop()
    if DBG:
        print 'op: pop'

def push(env, opinfo):
    value = opinfo.operands[0]
    frame = env.callstack[-1]
    frame.stack.append(value)
    if DBG:
        print 'op: push'
        print '    value', value

def pull(env, opinfo):
    var = opinfo.operands[0]

    frame = env.callstack[-1]
    if len(frame.stack) == 0:
        err('illegal op: attempted to pull from empty stack')

    result = frame.stack.pop()
    set_var(env, var, result)

    if DBG:
        print 'op: pull'
        print '    result', result

def _random(env, opinfo):
    range = to_signed_word(opinfo.operands[0])
    if range < 0:
        random.seed(range)
        result = 0
    elif range == 0:
        random.seed()
        result = 0
    else:
        result = random.randint(1, range)

def show_status(env, opinfo):
    if DBG:
        print 'op: show_status (not yet impld)'
        print '    operands', opinfo.operands

def sound_effect(env, opinfo):
    if DBG:
        print 'op: sound_effect (not yet impld)'
        print '    operands', opinfo.operands

def read(env, opinfo):
    text_buffer = opinfo.operands[0]
    parse_buffer = opinfo.operands[1]

    user_input = raw_input()
    if DBG:
        print 'op: read'
        print '    user_input', user_input

    text_buf_len = env.u8(text_buffer)
    parse_buf_len = env.u8(text_buffer)
    if text_buf_len < 2 or parse_buf_len < 1:
        err('read error: malformed text or parse buffer')

    text_buf_ptr = text_buffer + 1
    while env.u8(text_buf_ptr):
        text_buf_ptr += 1
        if text_buf_ptr - text_buffer >= text_buf_len:
            err('read error: buffer already full')

    input_len = len(user_input)
    max_len = text_buf_len-(text_buf_ptr-text_buffer)
    for i in range(min(input_len, max_len)):
        c = user_input[i]
        if ord(c) > 126 or ord(c) < 32:
            err('read: this char not impl\'d yet: '+c)
        env.mem[text_buf_ptr + i] = ord(c.lower())
    env.mem[text_buf_ptr + i + 1] = 0

    word_separators = []
    dict_base = env.hdr.dict_base
    num_word_seps = env.u8(dict_base)
    for i in range(num_word_seps):
        word_separators.append(env.u8(dict_base+1+i))
    
    word = []
    words = []
    MAX_WORD_LEN = 6
    scan_ptr = text_buffer + 1
    while True:
        c = env.u8(scan_ptr)

        if c == 0:
            if word:
                words.append(word)
                word = []
            break

        if c == ord(' '):
            if word:
                words.append(word)
                word = []
            scan_ptr += 1

        elif c in word_separators:
            if word:
                words.append(word)
                word = []
            words.append([c])
            scan_ptr += 1

        else:
            word.append(c)
            if len(word) == MAX_WORD_LEN:
                words.append(word)
                word = []
                scan_ptr += 1
                c = env.u8(scan_ptr)
                while (c != 0 and
                       c != ord(' ') and
                       c not in word_separators):
                    scan_ptr += 1
                    c = env.u8(scan_ptr)
            else:
                scan_ptr += 1

    # Ok, this will be super-sub-optimal, just
    # to get a working system up fast.
    # Actual system should be:
    # 1) Convert words to packed Z-Chars
    # 2) Do binary search against dict
    #
    # The above is also necessary for correctness.
    # Dict entries can have half a byte of a 2-byte
    # 10-bit ZSCII char that was truncated in the
    # entry creation process. That truncation should
    # be recreated on user input to match those chars.

    entry_length = env.u8(dict_base+1+num_word_seps)
    num_entries = env.u16(dict_base+1+num_word_seps+1)
    entries_start = dict_base+1+num_word_seps+1+2

    for word in words:
        wordstr = ''.join(map(chr, word))
        for i in range(num_entries):
            entry_addr = entries_start+i*entry_length
            entry = [env.u16(entry_addr), env.u16(entry_addr+2)]
            entry_unpacked = unpack_string(env, entry)
            if wordstr == entry_unpacked:
                print 'MATCH!: ',entry_unpacked
    
    sys.exit()

dispatch = {}
has_branch_var = {}
has_store_var = {}
has_text = {}

def op(opcode, f, svar=False, bvar=False, txt=False):
    dispatch[opcode] = f
    has_store_var[opcode] = svar
    has_branch_var[opcode] = bvar
    has_text[opcode] = txt

op(1,   je,                         bvar=True)
op(2,   jl,                         bvar=True)
op(3,   jg,                         bvar=True)
op(5,   inc_chk,                    bvar=True)
op(6,   jin,                        bvar=True)
op(9,   _and,          svar=True)
op(10,  test_attr,                  bvar=True)
op(11,  set_attr)
op(12,  clear_attr)
op(13,  store)
op(14,  insert_obj)
op(15,  loadw,         svar=True)
op(16,  loadb,         svar=True)
op(17,  get_prop,      svar=True)
op(18,  get_prop_addr, svar=True)
op(20,  add,           svar=True)
op(21 , sub,           svar=True)
op(23,  div,           svar=True)

op(33,  je,                         bvar=True)
op(34,  jl,                         bvar=True)
op(35,  jg,                         bvar=True)
op(37,  inc_chk,                    bvar=True)
op(38,  jin,                        bvar=True)
op(41,  _and,          svar=True)
op(42,  test_attr,                  bvar=True)
op(43,  set_attr)
op(44,  clear_attr)
op(45,  store)
op(46,  insert_obj)
op(47,  loadw,         svar=True)
op(48,  loadb,         svar=True)
op(49,  get_prop,      svar=True)
op(50,  get_prop_addr, svar=True)
op(52,  add,           svar=True)
op(53,  sub,           svar=True)
op(55,  div,           svar=True)

op(65,  je,                         bvar=True)
op(66,  jl,                         bvar=True)
op(67,  jg,                         bvar=True)
op(69,  inc_chk,                    bvar=True)
op(70,  jin,                        bvar=True)
op(73,  _and,          svar=True)
op(74,  test_attr,                  bvar=True)
op(75,  set_attr)
op(76,  clear_attr)
op(77,  store)
op(78,  insert_obj)
op(79,  loadw,         svar=True)
op(80,  loadb,         svar=True)
op(81,  get_prop,      svar=True)
op(82,  get_prop_addr, svar=True)
op(84,  add,           svar=True)
op(85,  sub,           svar=True)
op(87,  div,           svar=True)

op(97,  je,                         bvar=True)
op(98,  jl,                         bvar=True)
op(99,  jg,                         bvar=True)
op(101, inc_chk,                    bvar=True)
op(102, jin,                        bvar=True)
op(105, _and,          svar=True)
op(106, test_attr,                  bvar=True)
op(107, set_attr)
op(108, clear_attr)
op(109, store)
op(110, insert_obj)
op(111, loadw,         svar=True)
op(112, loadb,         svar=True)
op(113, get_prop,      svar=True)
op(114, get_prop_addr, svar=True)
op(116, add,           svar=True)
op(117, sub,           svar=True)
op(119, div,           svar=True)

op(128, jz,                         bvar=True)
op(129, get_sibling,   svar=True,   bvar=True)
op(130, get_child,     svar=True,   bvar=True)
op(131, get_parent,    svar=True)
op(133, inc)
op(134, dec)
op(138, print_obj)
op(139, ret)
op(140, jump)
op(141, print_paddr)

op(144, jz,                         bvar=True)
op(145, get_sibling,   svar=True,   bvar=True)
op(146, get_child,     svar=True,   bvar=True)
op(147, get_parent,    svar=True)
op(149, inc)
op(150, dec)
op(154, print_obj)
op(155, ret)
op(156, jump)
op(157, print_paddr)

op(160, jz,                         bvar=True)
op(161, get_sibling,   svar=True,   bvar=True)
op(162, get_child,     svar=True,   bvar=True)
op(163, get_parent,    svar=True)
op(164, get_prop_len,  svar=True)
op(165, inc)
op(166, dec)
op(170, print_obj)
op(171, ret)
op(172, jump)
op(173, print_paddr)  

op(176, rtrue)
op(177, rfalse)
op(178, _print,                                  txt=True)
op(184, ret_popped)
op(185, pop)
op(187, new_line)
op(188, show_status)

op(193, je,                         bvar=True)
op(194, jl,                         bvar=True)
op(195, jg,                         bvar=True)
op(197, inc_chk,                    bvar=True)
op(198, jin,                        bvar=True)
op(201, _and,          svar=True)
op(202, test_attr,                  bvar=True)
op(203, set_attr)
op(204, clear_attr)
op(205, store)
op(206, insert_obj)
op(207, loadw,         svar=True)
op(208, loadb,         svar=True)
op(209, get_prop,      svar=True)
op(210, get_prop_addr, svar=True)
op(212, add,           svar=True)
op(213, sub,           svar=True)
op(215, div,           svar=True)

op(224, call,          svar=True)
op(225, storew)
op(226, storeb)
op(227, put_prop)
op(228, read)
op(229, print_char)
op(230, print_num)
op(231, _random)
op(232, push)
op(233, pull)
op(245, sound_effect)

