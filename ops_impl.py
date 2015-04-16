# ops_impl.py (as in this file implements the opcodes)
#
# the goal here is to have no z-machine version control flow in here,
# i.e. no 'if *.z5 then X else Y'. All that should be in ops_compat.py

import random
import sys

from zmach import to_signed_word, DBG
from ops_compat import *
from txt import *

def get_var(env, var_num, pop_stack=True):
    frame = env.callstack[-1]
    if var_num < 0 or var_num > 0xff:
        err('illegal var num: '+str(var_num))

    if var_num == 0:
        if pop_stack:
            return frame.stack.pop()
        else:
            return frame.stack[-1]
    elif var_num < 16:
        return frame.locals[var_num - 1]
    else: # < 0xff
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        return env.u16(g_base + 2*g_idx)

def set_var(env, var_num, result, push_stack=True):
    result &= 0xffff

    if var_num < 0 or var_num > 0xff:
        err('set_var: illegal var_num: '+str(var_num))

    if var_num == 0:
        frame = env.callstack[-1]
        if push_stack:
            frame.stack.append(result)
        else:
            frame.stack[-1] = result
    elif var_num < 16:
        frame = env.callstack[-1]
        frame.locals[var_num - 1] = result
    else: # < 0xff
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        env.write16(g_base + 2*g_idx, result)

def get_var_name(var_num):
    if var_num == 0:
        return 'SP'
    elif var_num < 16:
        return 'L'+hex(var_num-1)[2:].zfill(2)
    else:
        return 'G'+hex(var_num-16)[2:].zfill(2)

def add(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a+b
    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('op: adding',a,'and',b)
        warn('    storing',result,'in',get_var_name(opinfo.store_var))

def sub(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a-b
    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('op: subtracting',a,'and',b)
        warn('    storing',result,'in',get_var_name(opinfo.store_var))

def mul(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a*b
    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('op: multiplying',a,'and',b)
        warn('    storing',result,'in',get_var_name(opinfo.store_var))

def div(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    num_neg = (a < 0) + (b < 0)
    result = abs(a) // abs(b)
    if num_neg == 1:
        result = -result
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        warn('op: diving',a,'and',b)
        warn('    storing',result,'in',get_var_name(opinfo.store_var))

def mod(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    num_neg = (a < 0) + (b < 0)
    result = abs(a) % abs(b)
    if num_neg == 1:
        result = -result
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        warn('op: modding',a,'and',b)
        warn('    storing',result,'in',get_var_name(opinfo.store_var))

def load(env, opinfo):
    var = opinfo.operands[0]
    val = get_var(env, var, pop_stack=False)
    set_var(env, opinfo.store_var, val)

    if DBG:
        warn('op: load')
        warn('    loaded',val,'from',var,'to',opinfo.store_var)

def jz(env, opinfo):
    result = opinfo.operands[0] == 0

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        warn('op: jump zero (jz) ('+jump_info_txt+')')
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

def je(env, opinfo):
    first = opinfo.operands[0]
    result = False
    for operand in opinfo.operands[1:]:
        if first == operand:
            result = True
            break

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        warn('op: jump equal (je) ('+jump_info_txt+')')
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

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
        warn('op: jump less than (jl) ('+jump_info_txt+')')
        warn('    a', a)
        warn('    b', b)
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

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
        warn('op: jump greater than (jg) ('+jump_info_txt+')')
        warn('    a', a)
        warn('    b', b)
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

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
        warn('op: jump')
        warn('    offset', offset)

def loadw(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = opinfo.operands[1]
    word_loc = array_addr + 2*word_index

    set_var(env, opinfo.store_var, env.u16(word_loc))

    if DBG:
        warn('op: loadw')
        warn('    array_addr', array_addr)
        warn('    word_index', word_index)
        warn('    value', env.u16(word_loc))
        warn('    store_var', get_var_name(opinfo.store_var))

def loadb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = opinfo.operands[1]
    byte_loc = array_addr + byte_index

    set_var(env, opinfo.store_var, env.u8(byte_loc))
    
    if DBG:
        warn('op: loadb')
        warn('    array_addr', array_addr)
        warn('    byte_index', byte_index)
        warn('    value', env.u8(byte_loc))
        warn('    store_var', get_var_name(opinfo.store_var))

def storeb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = opinfo.operands[1]
    val = opinfo.operands[2] & 0xff

    env.mem[array_addr+byte_index] = val

    if DBG:
        warn('op: storeb')
        warn('    array_addr', array_addr)
        warn('    byte_index', byte_index)
        warn('    value', val)

def storew(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = opinfo.operands[1]
    val = opinfo.operands[2]

    word_loc = array_addr + 2*word_index
    env.write16(word_loc, val)

    if DBG:
        warn('op: storew')
        warn('    array_addr', array_addr)
        warn('    word_index', word_index)
        warn('    value', val)

def store(env, opinfo):
    var = opinfo.operands[0]
    val = opinfo.operands[1]
    set_var(env, var, val, push_stack=False)
    if DBG:
        warn('op: store', val, 'in', get_var_name(var))

def and_(env, opinfo):
    acc = opinfo.operands[0]
    for operand in opinfo.operands[1:]:
        acc &= operand
    set_var(env, opinfo.store_var, acc)
    if DBG:
        warn('op: and')
        warn('    operands', opinfo.operands)
        warn('    result', acc)

def or_(env, opinfo):
    acc = opinfo.operands[0]
    for operand in opinfo.operands[1:]:
        acc |= operand
    set_var(env, opinfo.store_var, acc)
    if DBG:
        warn('op: or')
        warn('    operands', opinfo.operands)
        warn('    result', acc)

def inc(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    var_val = var_val+1 & 0xffff
    set_var(env, var_num, var_val)

    if DBG:
        warn('op: inc')
        warn('    var', get_var_name(var_num))
        warn('    new_val', to_signed_word(var_val))

def dec(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    var_val = var_val-1 & 0xffff
    set_var(env, var_num, var_val)

    if DBG:
        warn('op: dec')
        warn('    var_num', var_num)
        warn('    new_val', to_signed_word(var_val))

def inc_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = to_signed_word(opinfo.operands[1])

    var_val = to_signed_word(get_var(env, var_loc))
    var_val = var_val+1 & 0xffff
    set_var(env, var_loc, var_val)
    var_val = to_signed_word(var_val)
    result = var_val > chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: inc_chk ( branched =',(result==opinfo.branch_on),')')
        warn('    chk_val', chk_val)
        warn('    var_loc', get_var_name(var_loc))
        warn('    var_val', var_val)
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

def dec_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = to_signed_word(opinfo.operands[1])

    var_val = to_signed_word(get_var(env, var_loc))
    var_val = var_val-1 & 0xffff
    set_var(env, var_loc, var_val)
    var_val = to_signed_word(var_val)
    result = var_val < chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: dec_chk ( branched =',(result==opinfo.branch_on),')')
        warn('    chk_val', chk_val)
        warn('    var_loc', get_var_name(var_loc))
        warn('    var_val', var_val)
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

def test(env, opinfo):
    bitmap = opinfo.operands[0]
    flags = opinfo.operands[1]
    result = bitmap & flags == flags

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: test ( branched =',(result==opinfo.branch_on),')')
        warn('    bitmap', bin(bitmap))
        warn('    flags', bin(flags))
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

def push(env, opinfo):
    value = opinfo.operands[0]
    frame = env.callstack[-1]
    frame.stack.append(value)
    if DBG:
        warn('op: push')
        warn('    value', value)

def random_(env, opinfo):
    range = to_signed_word(opinfo.operands[0])
    if range < 0:
        random.seed(range)
        result = 0
    elif range == 0:
        random.seed()
        result = 0
    else:
        result = random.randint(1, range)
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        warn('op: random')
        warn('    range', range)
        warn('    result', result)

def jin(env, opinfo):
    obj1 = opinfo.operands[0]
    obj2 = opinfo.operands[1]

    result = get_parent_num(env, obj1) == obj2

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: jin ( branch =',(result==opinfo.branch_on),')')
        warn('    obj1', obj1, '(',get_obj_str(env,obj1),')')
        warn('    obj2', obj2, '(',get_obj_str(env,obj2),')')
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

def get_child(env, opinfo):
    obj = opinfo.operands[0]

    child_num = get_child_num(env, obj)
    set_var(env, opinfo.store_var, child_num)

    result = child_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: get_child ( branched =',(result==opinfo.branch_on),')')
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    child', child_num, '(',get_obj_str(env, child_num),')')
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

def get_sibling(env, opinfo):
    obj = opinfo.operands[0]

    sibling_num = get_sibling_num(env, obj)
    set_var(env, opinfo.store_var, sibling_num)

    result = sibling_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: get_sibling ( branched =',(result==opinfo.branch_on),')')
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    sibling', sibling_num, '(',get_obj_str(env, sibling_num),')')
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

def get_parent(env, opinfo):
    obj = opinfo.operands[0]

    parent_num = get_parent_num(env, obj)
    set_var(env, opinfo.store_var, parent_num)

    if DBG:
        warn('op: get_parent')
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    parent', parent_num, '(',get_obj_str(env, parent_num),')')

def handle_return(env, return_val):
    frame = env.callstack.pop()
    if len(env.callstack) == 0:
        err('returned from unreturnable/nonexistant function!')
    if frame.return_val_loc != None:
        set_var(env, frame.return_val_loc, return_val)
    env.pc = frame.return_addr

    if DBG:
        warn('helper: handle_return')
        warn('    return_val', return_val)
        warn('    return_val_loc', frame.return_val_loc)
        warn('    return_addr', hex(frame.return_addr))

def ret(env, opinfo):
    return_val = opinfo.operands[0]
    handle_return(env, return_val)

    if DBG:
        warn('op: ret')

def rtrue(env, opinfo):
    handle_return(env, 1)

    if DBG:
        warn('op: rtrue')

def rfalse(env, opinfo):
    handle_return(env, 0)

    if DBG:
        warn('op: rfalse')

def ret_popped(env, opinfo):
    frame = env.callstack[-1]
    ret_val = frame.stack.pop()
    handle_return(env, ret_val)

    if DBG:
        warn('op: ret_popped')
        warn('    ret_val', ret_val)

def quit(env, opinfo):
    if DBG:
        warn('op: quit')
    sys.exit()

def print_(env, opinfo):
    string = unpack_string(env, opinfo.operands)
    write(env, string)

    if DBG:
        warn()
        warn('op: print')
        warn('    packed_len', len(opinfo.operands))

def print_ret(env, opinfo):
    string = unpack_string(env, opinfo.operands)+'\n'
    write(env, string)
    handle_return(env, 1)

    if DBG:
        warn()
        warn('op: print_ret')
        warn('    packed_len', len(opinfo.operands))

def print_paddr(env, opinfo):
    addr = unpack_addr_print_paddr(env, opinfo.operands[0])
    _print_addr(env, addr)

    if DBG:
        warn()
        warn('op: print_paddr')

def _print_addr(env, addr):
    packed_string = read_packed_string(env, addr)
    string = unpack_string(env, packed_string)
    write(env, string)
    if DBG:
        warn()
        warn('helper: _print_addr')
        warn('        addr', addr)

def print_addr(env, opinfo):
    addr = opinfo.operands[0]
    _print_addr(env, addr)

    if DBG:
        warn()
        warn('op: print_addr')

def new_line(env, opinfo):
    write(env, '\n')
    if DBG:
        warn()
        warn('op: new_line')

def print_num(env, opinfo):
    num = to_signed_word(opinfo.operands[0])
    write(env, str(num))
    if DBG:
        warn()
        warn('op: print_num')
        warn('    num', num)

def print_obj(env, opinfo):
    obj = opinfo.operands[0]
    string = get_obj_str(env, obj)
    write(env, string)

    if DBG:
        warn()
        warn('op: print_obj')
        warn('    obj', obj, '(', get_obj_str(env, obj), ')')

def print_char(env, opinfo):
    char = zscii_to_ascii([opinfo.operands[0]])
    write(env, char)
    if DBG:
        warn()
        warn('op: print_char')

def get_prop_len(env, opinfo):
    prop_data_addr = opinfo.operands[0]
    size, num = get_sizenum_from_addr(env, prop_data_addr)
    set_var(env, opinfo.store_var, size)
    if DBG:
        warn('op: get_prop_len')
        warn('    addr', prop_data_addr)
        warn('    size', size)

def get_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    prop_addr = compat_get_prop_addr(env, obj, prop_num)
    got_default_prop = prop_addr == 0
    if got_default_prop:
        result = get_default_prop(env, prop_num)
    else:
        size, num = get_sizenum_from_addr(env, prop_addr)
        if size == 2:
            result = env.u16(prop_addr)
        elif size == 1:
            result = env.u8(prop_addr)
        else:
            msg = 'illegal op: get_prop on outsized prop (not 1-2 bytes)'
            msg += ' - prop '+str(prop_num)
            msg += ' of obj '+str(obj)+' ('+get_obj_str(env, obj)+')'
            msg += ' (sized at '+str(size)+' bytes)'
            print_prop_list(env, obj)
            err(msg)

    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('op: get_prop')
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    result', result)
        warn('    got_default_prop', got_default_prop)
        print_prop_list(env, obj)

def put_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]
    val = opinfo.operands[2]

    prop_addr = compat_get_prop_addr(env, obj, prop_num)
    if prop_addr == 0:
        msg = 'illegal op: put_prop on nonexistant property'
        msg += ' - prop '+str(prop_num)
        msg += ' not found on obj '+str(obj)+' ('+get_obj_str(env, obj)+')' 
        err(msg)
    
    size, num = get_sizenum_from_addr(env, prop_addr)
    if size == 2:
        env.write16(prop_addr, val)
    elif size == 1:
        env.mem[prop_addr] = val & 0xff
    else:
        msg = 'illegal op: put_prop on outsized prop (not 1-2 bytes)'
        msg += ' - prop '+str(prop_num)
        msg += ' of obj '+str(obj)+' ('+get_obj_str(obj)+')'
        msg += ' (sized at '+size+' bytes)'
        err(msg)

    if DBG:
        warn('op: put_prop')
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    val', val)
        print_prop_list(env, obj)

def get_prop_addr(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    result = compat_get_prop_addr(env, obj, prop_num)
    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('op: get_prop_addr')
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    result', result)
        print_prop_list(env, obj)

def get_next_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    next_prop_num = compat_get_next_prop(env, obj, prop_num)
    set_var(env, opinfo.store_var, next_prop_num)

    if DBG:
        warn('op: get_next_prop')
        warn('    prop_num', prop_num)
        warn('    next_prop_num', next_prop_num)
        print_prop_list(env, obj)

def not_(env, opinfo):
    val = ~(opinfo.operands[0])
    set_var(env, opinfo.store_var, val)
    if DBG:
        warn('op: not')

def insert_obj(env, opinfo):
    obj = opinfo.operands[0]
    dest = opinfo.operands[1]

    # it doesn't say explicitly to make obj's parent
    # field say dest, but *surely* that's the right
    # thing to do. Right? 
    # (based on what the ops seems to expect, I think so)

    # Also, should I remove it from its old parent?
    # Looks like, based on the current bug I have.
    _remove_obj(env, obj)
    # Ok, Yep. That totally fixed things.

    dest_child = get_child_num(env, dest)

    set_parent_num(env, obj, dest)
    set_sibling_num(env, obj, dest_child)
    set_child_num(env, dest, obj)

    if DBG:
        warn('op: insert_obj')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    dest', dest, '(', get_obj_str(env,dest), ')')

def _remove_obj(env, obj):
    obj_addr = get_obj_addr(env, obj)

    parent = get_parent_num(env, obj)
    sibling = get_sibling_num(env, obj)

    set_parent_num(env, obj, 0)
    set_sibling_num(env, obj, 0)
    if parent == 0:
        return

    child_num = get_child_num(env, parent)
    if child_num == obj:
        set_child_num(env, parent, sibling)
    else:
        sibling_num = get_sibling_num(env, child_num)
        while sibling_num and sibling_num != obj:
            child_num = sibling_num
            sibling_num = get_sibling_num(env, child_num)
        if sibling_num != 0:
            set_sibling_num(env, child_num, sibling)

    if DBG:
        warn('helper: _remove_obj')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    parent', parent, '(', get_obj_str(env,parent), ')')

def remove_obj(env, opinfo):
    obj = opinfo.operands[0]
    _remove_obj(env, obj)

    if DBG:
        warn('op: remove_obj')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')

def set_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    mask = 2**(7-attr%8)
    env.mem[obj_addr+attr_byte] |= mask

    if DBG:
        warn('op: set_attr')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)
        warn('    attr_byte', attr_byte)
        warn('    mask', mask)

def clear_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    mask = 2**(7-attr%8)
    old_val = env.mem[obj_addr+attr_byte]
    env.mem[obj_addr+attr_byte] &= ~mask

    if DBG:
        warn('op: clear_attr')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)
        warn('    attr_byte', attr_byte)
        warn('    mask', mask)
        warn('    old_val', bin(old_val))
        warn('    new_byte_val', bin(env.mem[obj_addr+attr_byte]))

def test_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    obj_addr = get_obj_addr(env, obj)

    attr_byte = attr // 8
    shift_amt = 7-attr%8
    attr_val = env.mem[obj_addr+attr_byte] >> shift_amt & 1
    result = attr_val == 1
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('op: test_attr ( branch =', (result==opinfo.branch_on), ')')
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)
        warn('    attr_byte', attr_byte)
        warn('    shift_amt', shift_amt)
        warn('    attr_byte_val', env.mem[obj_addr+attr_byte])
        warn('    attr_val', attr_val)
        warn('    branch_on', opinfo.branch_on)
        warn('    branch_offset', opinfo.branch_offset)

class Frame:
    def __init__(self, return_addr, num_args=0, locals=[], return_val_loc=None):
        self.return_addr = return_addr
        self.num_args = num_args
        self.locals = locals
        self.stack = []
        self.return_val_loc = return_val_loc

def handle_call(env, packed_addr, args, store_var):

    if packed_addr == 0:
        if store_var != None:
            set_var(env, store_var, 0)
        if DBG:
            warn('op: calling 0 (returns false)')
        return

    return_addr = env.pc
    call_addr = unpack_addr_call(env, packed_addr)
    locals = setup_locals(env, call_addr)
    code_ptr = get_code_ptr(env, call_addr)

    # args dropped if past len of locals arr
    num_args = min(len(args), len(locals))
    for i in range(num_args):
        locals[i] = args[i]

    env.callstack.append(Frame(return_addr,
                               len(args),
                               locals,
                               return_val_loc=store_var))
    env.pc = code_ptr

    if DBG:
        warn('helper: handle_call is calling', hex(call_addr))
        warn('    returning to', hex(return_addr))
        warn('    using args', args)
        if store_var == None:
            warn('    return val will be discarded')
        else:
            warn('    return val will be placed in', get_var_name(store_var))
        warn('    num locals:', env.u8(call_addr))
        warn('    local vals:', locals)
        warn('    code ptr:', hex(code_ptr))
        warn('    first inst:', env.u8(code_ptr))

# known as "call" *and* "call_vs" in the docs
# also does the job of call_vs2
def call(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = opinfo.operands[1:]
    handle_call(env, packed_addr, args, opinfo.store_var)
    if DBG:
        warn('op: call')

def call_2s(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = [opinfo.operands[1]]
    handle_call(env, packed_addr, args, opinfo.store_var)
    if DBG:
        warn('op: call_2s')

def call_2n(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = [opinfo.operands[1]]
    handle_call(env, packed_addr, args, store_var=None)
    if DBG:
        warn('op: call_2n')

# also does the job of call_vn2
def call_vn(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = opinfo.operands[1:]
    handle_call(env, packed_addr, args, store_var=None)
    if DBG:
        warn('op: call_vn')

def call_1s(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = []
    handle_call(env, packed_addr, args, opinfo.store_var)
    if DBG:
        warn('op: call_1s')

def call_1n(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = []
    handle_call(env, packed_addr, args, store_var=None)
    if DBG:
        warn('op: call_1n')

def check_arg_count(env, opinfo):
    arg_num = opinfo.operands[0]
    frame = env.callstack[-1]
    result = frame.num_args >= arg_num

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)
        jump_info_txt = 'taken'
    else:
        jump_info_txt = 'not taken'

    if DBG:
        warn('op: check_arg_count ('+jump_info_txt+')')
        warn('    arg_num', arg_num)
        warn('    num args in frame', frame.num_args)
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)

def ascii_to_zscii_char(c):
    if ord(c) > 126 or ord(c) < 32:
        #warn('read: this char not impl\'d yet: '+c+' / '+str(ord(c)))
        return '?'
    return c

def get_line_of_input():
    # this will need to be more sophisticated at some point...
    return ''.join(map(ascii_to_zscii_char, raw_input()))

def handle_read(env, text_buffer, parse_buffer, time=0, routine=0):

    if time != 0 or routine != 0:
        warn('warning: interrupts requested but not impl\'d yet!')

    flush(env) # all output needs to be pushed before read

    user_input = get_line_of_input()

    fill_text_buffer(env, user_input, text_buffer)

    if env.hdr.version < 5 or parse_buffer != 0:
        handle_parse(env, text_buffer, parse_buffer)

    # return ord('\r') as term char for now... 
    # TODO: the right thing 
    return ord('\r')

def aread(env, opinfo):
    text_buffer = opinfo.operands[0]
    parse_buffer = opinfo.operands[1]

    end_char = handle_read(env, text_buffer, parse_buffer)
    set_var(env, opinfo.store_var, end_char)

    if DBG:
        warn('op: aread')
        warn('    user_input', user_input)

def sread(env, opinfo):
    text_buffer = opinfo.operands[0]
    parse_buffer = opinfo.operands[1]
    if len(opinfo.operands) == 4:
        time, routine = opinfo.operands[2:4]
    else:
        time, routine = 0, 0

    handle_read(env, text_buffer, parse_buffer)

    if DBG:
        warn('op: sread')
        warn('    user_input', user_input)

def tokenize(env, opinfo):
    text_buffer = opinfo.operands[0]
    parse_buffer = opinfo.operands[1]

    if len(opinfo.operands) > 2:
        dictionary = opinfo.operands[2]
    else:
        dictionary = 0

    if len(opinfo.operands) > 3:
        skip_unknown_words = opinfo.operands[3]
    else:
        skip_unknown_words = 0

    handle_parse(env, text_buffer, parse_buffer, dictionary, skip_unknown_words)
    if DBG:
        warn('op: tokenize')
        warn('    operands', opinfo.operands)

def read_char(env, opinfo):
    device = opinfo.operands[0]
    if device != 1:
        err('read_char: first operand must be 1')
    if len(opinfo.operands) > 1:
        if len(opinfo.operands) != 3:
            err('read_char: num operands must be 1 or 3')
        if opinfo.operands[1] != 0 or opinfo.operands[2] != 0:
            warn('read_char: interrupts not impl\'d yet!')
    flush(env) # all output needs to be pushed before read
    c = ord(ascii_to_zscii(getch()))
    set_var(env, opinfo.store_var, c)
    if DBG:
        warn('op: read_char')

def set_font(env, opinfo):
    font_num = opinfo.operands[0]
    if font_num == 0:
        set_var(env, opinfo.store_var, 1)
    elif font_num != 1:
        set_var(env, opinfo.store_var, 0)
    if DBG:
        warn('op: set_font')
        warn('    font_num', font_num)

def pop(env, opinfo):
    frame = env.callstack[-1]
    frame.stack.pop()
    if DBG:
        warn('op: pop')

def pull(env, opinfo):
    var = opinfo.operands[0]

    frame = env.callstack[-1]
    if len(frame.stack) == 0:
        err('illegal op: attempted to pull from empty stack')

    result = frame.stack.pop()
    set_var(env, var, result)

    if DBG:
        warn('op: pull')
        warn('    result', result)
        warn('    dest', get_var_name(var))

def buffer_mode(env, opinfo):
    flag = opinfo.operands[0]
    env.use_buffered_output = (flag == 1)
    if DBG:
        warn('op: buffer_mode')
        warn('    flag', flag)

def output_stream(env, opinfo):
    flush(env)
    stream = to_signed_word(opinfo.operands[0])
    if stream < 0:
        stream = abs(stream)
        if stream == 3:
            table_addr = env.memory_ostream_stack.pop()
            env.output_buffer = ascii_to_zscii(env.output_buffer)
            buflen = len(env.output_buffer)
            env.write16(table_addr, buflen)
            for i in range(buflen):
                env.mem[table_addr+2+i] = env.output_buffer[i]
            env.output_buffer = ''
            if len(env.memory_ostream_stack) == 0:
                env.selected_ostreams.discard(stream)
        else:
            env.selected_ostreams.discard(stream)
    elif stream > 0:
        env.selected_ostreams.add(stream)
        if stream == 3:
            table_addr = opinfo.operands[1]
            if len(env.memory_ostream_stack) == 16:
                err('too many memory-based ostreams (>16)')
            env.memory_ostream_stack.append(table_addr)
    if DBG:
        warn('op: output_stream')
        warn('    operands', opinfo.operands)

def erase_window(env, opinfo):
    write(env, '\n') # temp(?) fix for clarity
    if DBG:
        warn('op: erase_window (not impld)')

def split_window(env, opinfo):
    env.top_window_height = opinfo.operands[0]
    if DBG:
        warn('op: split_window (not impld)')
        warn('    height', env.top_window_height)

def set_window(env, opinfo):
    env.current_window = opinfo.operands[0]
    if DBG:
        warn('op: set_window (not impld)')
        warn('    window:', env.current_window)

def set_cursor(env, opinfo):
    write(env, '\n') # temp(?) fix for clarity
    if DBG:
        warn('op: set_cursor (not impld)')

def show_status(env, opinfo):
    if DBG:
        warn('op: show_status (not impld)')

def set_text_style(env, opinfo):
    if DBG:
        warn('op: set_text_style (not impld)')

def sound_effect(env, opinfo):
    if DBG:
        warn('op: sound_effect (not impld)')

def save_undo(env, opinfo):
    set_var(env, opinfo.store_var, -1)
    if DBG:
        warn('op: save_undo (not impld for now)')
        warn('    (but at least I can notify the game of that)')

