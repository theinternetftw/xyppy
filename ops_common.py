# op functions shared between all z machine versions
from zmach import to_signed_word, err, DBG
from ops_compat import _get_prop_addr, _get_next_prop
from ops_compat import *
from txt import *
import random
import sys

def get_var(env, var_num):
    frame = env.callstack[-1]
    if var_num < 0 or var_num > 0xff:
        err('illegal var num: '+str(var_num))

    if var_num == 0:
        return frame.stack.pop()
    elif var_num < 16:
        return frame.locals[var_num - 1]
    else: # < 0xff
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        return env.u16(g_base + 2*g_idx)

def set_var(env, var_num, result):
    result &= 0xffff

    if var_num < 0 or var_num > 0xff:
        err('set_var: illegal var_num: '+str(var_num))

    if var_num == 0:
        frame = env.callstack[-1]
        frame.stack.append(result)
    elif var_num < 16:
        frame = env.callstack[-1]
        frame.locals[var_num - 1] = result
    else: # < 0xff
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        env.mem[g_base + 2*g_idx] = result >> 8
        env.mem[g_base + 2*g_idx + 1] = result & 0xff

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
        print 'op: adding',a,'and',b
        print '    storing',result,'in',get_var_name(opinfo.store_var)

def sub(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a-b
    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: subtracting',a,'and',b
        print '    storing',result,'in',get_var_name(opinfo.store_var)

def mul(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a*b
    set_var(env, opinfo.store_var, result)

    if DBG:
        print 'op: multiplying',a,'and',b
        print '    storing',result,'in',get_var_name(opinfo.store_var)

def div(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    num_neg = (a < 0) + (b < 0)
    result = abs(a) // abs(b)
    if num_neg == 1:
        result = -result
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        print 'op: diving',a,'and',b
        print '    storing',result,'in',get_var_name(opinfo.store_var)

def mod(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    num_neg = (a < 0) + (b < 0)
    result = abs(a) % abs(b)
    if num_neg == 1:
        result = -result
    set_var(env, opinfo.store_var, result)
    
    if DBG:
        print 'op: modding',a,'and',b
        print '    storing',result,'in',get_var_name(opinfo.store_var)

def load(env, opinfo):
    var = opinfo.operands[0]
    val = get_var(env, var)
    set_var(env, opinfo.store_var, val)

    if DBG:
        print 'op: load'
        print '    loaded',val,'from',var,'to',opinfo.store_var

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
        print '    store_var', get_var_name(opinfo.store_var)

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
        print '    store_var', get_var_name(opinfo.store_var)

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
    var = opinfo.operands[0]
    val = opinfo.operands[1]
    set_var(env, var, val)
    if DBG:
        print 'op: store', val, 'in', get_var_name(var)

def and_(env, opinfo):
    acc = opinfo.operands[0]
    for operand in opinfo.operands[1:]:
        acc &= operand
    set_var(env, opinfo.store_var, acc)
    if DBG:
        print 'op: and'
        print '    operands', opinfo.operands
        print '    result', acc

def or_(env, opinfo):
    acc = opinfo.operands[0]
    for operand in opinfo.operands[1:]:
        acc |= operand
    set_var(env, opinfo.store_var, acc)
    if DBG:
        print 'op: or'
        print '    operands', opinfo.operands
        print '    result', acc

def inc(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    var_val = var_val+1 & 0xffff
    set_var(env, var_num, var_val)

    if DBG:
        print 'op: inc'
        print '    var', get_var_name(var_num)
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
    chk_val = to_signed_word(opinfo.operands[1])

    var_val = to_signed_word(get_var(env, var_loc))
    var_val = var_val+1 & 0xffff
    set_var(env, var_loc, var_val)
    var_val = to_signed_word(var_val)
    result = var_val > chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: inc_chk ( branched =',(result==opinfo.branch_on),')'
        print '    chk_val', chk_val
        print '    var_loc', get_var_name(var_loc)
        print '    var_val', var_val
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

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
        print 'op: dec_chk ( branched =',(result==opinfo.branch_on),')'
        print '    chk_val', chk_val
        print '    var_loc', get_var_name(var_loc)
        print '    var_val', var_val
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def test(env, opinfo):
    bitmap = opinfo.operands[0]
    flags = opinfo.operands[1]
    result = bitmap & flags == flags

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: test ( branched =',(result==opinfo.branch_on),')'
        print '    bitmap', bin(bitmap)
        print '    flags', bin(flags)
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def push(env, opinfo):
    value = opinfo.operands[0]
    frame = env.callstack[-1]
    frame.stack.append(value)
    if DBG:
        print 'op: push'
        print '    value', value

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
        print 'op: random'
        print '    range', range
        print '    result', result

def jin(env, opinfo):
    obj1 = opinfo.operands[0]
    obj2 = opinfo.operands[1]

    result = get_parent_num(env, obj1) == obj2

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: jin ( branch =',(result==opinfo.branch_on),')'
        print '    obj1', obj1, '(',get_obj_str(env,obj1),')'
        print '    obj2', obj2, '(',get_obj_str(env,obj2),')'
        print '    branch_offset', opinfo.branch_offset
        print '    branch_on', opinfo.branch_on

def get_child(env, opinfo):
    obj = opinfo.operands[0]

    child_num = get_child_num(env, obj)
    set_var(env, opinfo.store_var, child_num)

    result = child_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: get_child ( branched =',(result==opinfo.branch_on),')'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    child', child_num, '(',get_obj_str(env, child_num),')'
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def get_sibling(env, opinfo):
    obj = opinfo.operands[0]

    sibling_num = get_sibling_num(env, obj)
    set_var(env, opinfo.store_var, sibling_num)

    result = sibling_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        print 'op: get_sibling ( branched =',(result==opinfo.branch_on),')'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    sibling', sibling_num, '(',get_obj_str(env, sibling_num),')'
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

def get_parent(env, opinfo):
    obj = opinfo.operands[0]

    parent_num = get_parent_num(env, obj)
    set_var(env, opinfo.store_var, parent_num)

    if DBG:
        print 'op: get_parent'
        print '    obj', obj,'(',get_obj_str(env, obj),')'
        print '    parent', parent_num, '(',get_obj_str(env, parent_num),')'

def handle_return(env, return_val):
    frame = env.callstack.pop()
    if frame.return_val_loc != None:
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

def quit(env, opinfo):
    if DBG:
        print 'op: quit'
    sys.exit()

def print_(env, opinfo):
    string = wwrap(unpack_string(env, opinfo.operands))
    sys.stdout.write(string)

    if DBG:
        print
        print 'op: print'
        print '    packed_len', len(opinfo.operands)

def print_ret(env, opinfo):
    string = wwrap(unpack_string(env, opinfo.operands)+'\n')
    sys.stdout.write(string)
    handle_return(env, 1)

    if DBG:
        print
        print 'op: print_ret'
        print '    packed_len', len(opinfo.operands)

def print_paddr(env, opinfo):
    addr = unpack_addr(opinfo.operands[0])
    _print_addr(env, addr)

    if DBG:
        print
        print 'op: print_paddr'

def _print_addr(env, addr):
    packed_string = read_packed_string(env, addr)
    string = wwrap(unpack_string(env, packed_string))
    sys.stdout.write(string)
    if DBG:
        print
        print 'helper: _print_addr'
        print '        addr', addr

def print_addr(env, opinfo):
    addr = opinfo.operands[0]
    _print_addr(env, addr)

    if DBG:
        print
        print 'op: print_addr'

def new_line(env, opinfo):
    sys.stdout.write('\n')
    if DBG:
        print
        print 'op: new_line'

def print_num(env, opinfo):
    num = to_signed_word(opinfo.operands[0])
    sys.stdout.write(str(num))
    if DBG:
        print
        print 'op: print_num'
        print '    num', num

def get_obj_str(env, obj):
    obj_desc_addr = get_obj_desc_addr(env, obj)
    obj_desc_packed = read_packed_string(env, obj_desc_addr)
    return unpack_string(env, obj_desc_packed)

def print_obj(env, opinfo):
    obj = opinfo.operands[0]
    string = wwrap(get_obj_str(env, obj))
    sys.stdout.write(string)

    if DBG:
        print
        print 'op: print_obj'
        print '    obj', obj, '(', get_obj_str(env, obj), ')'

def print_char(env, opinfo):
    char = zscii_to_ascii([opinfo.operands[0]])
    sys.stdout.write(char)
    if DBG:
        print
        print 'op: print_char'

def get_prop_len(env, opinfo):
    prop_data_addr = opinfo.operands[0]
    size, num = get_sizenum_from_addr(env, prop_data_addr)
    set_var(env, opinfo.store_var, size)
    if DBG:
        print 'op: get_prop_len'
        print '    addr', prop_data_addr
        print '    size_and_num', size_and_num
        print '    size', size

def get_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    prop_addr = _get_prop_addr(env, obj, prop_num)
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
        print_prop_list(env, obj)

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
    
    size, num = get_sizenum_from_addr(env, prop_addr)
    if size == 2:
        env.mem[prop_addr] = val >> 8
        env.mem[prop_addr+1] = val & 0xff
    elif size == 1:
        env.mem[prop_addr] = val & 0xff
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
        print_prop_list(env, obj)

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
        print_prop_list(env, obj)

def get_next_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    next_prop_num = _get_next_prop(env, obj, prop_num)
    set_var(env, opinfo.store_var, next_prop_num)

    if DBG:
        print 'op: get_next_prop'
        print '    prop_num', prop_num
        print '    next_prop_num', next_prop_num
        print_prop_list(env, obj)

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
        print 'op: insert_obj'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    dest', dest, '(', get_obj_str(env,dest), ')'

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
        print 'helper: _remove_obj'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    parent', parent, '(', get_obj_str(env,parent), ')'

def remove_obj(env, opinfo):
    obj = opinfo.operands[0]
    _remove_obj(env, obj)

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
    old_val = env.mem[obj_addr+attr_byte]
    env.mem[obj_addr+attr_byte] &= ~mask

    if DBG:
        print 'op: clear_attr'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    attr', attr
        print '    attr_byte', attr_byte
        print '    mask', mask
        print '    old_val', bin(old_val)
        print '    new_byte_val', bin(env.mem[obj_addr+attr_byte])

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
        print 'op: test_attr ( branch =', (result==opinfo.branch_on), ')'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'
        print '    attr', attr
        print '    attr_byte', attr_byte
        print '    shift_amt', shift_amt
        print '    attr_byte_val', env.mem[obj_addr+attr_byte]
        print '    attr_val', attr_val
        print '    branch_on', opinfo.branch_on
        print '    branch_offset', opinfo.branch_offset

class Frame:
    def __init__(self, return_addr, locals=[], return_val_loc=None):
        self.return_addr = return_addr
        self.locals = locals
        self.stack = []
        self.return_val_loc = return_val_loc

def handle_call(env, packed_addr, args, store_var):

    if packed_addr == 0:
        if store_var != None:
            set_var(env, store_var, 0)
        if DBG:
            print 'op: calling 0 (returns false)'
        return

    return_addr = env.pc
    call_addr = unpack_addr(packed_addr)
    locals = setup_locals(env, call_addr)
    code_ptr = get_code_ptr(env, call_addr)

    # args dropped if past len of locals arr
    num_args = min(len(args), len(locals))
    for i in range(num_args):
        locals[i] = args[i]

    env.callstack.append(Frame(return_addr, locals, store_var))
    env.pc = code_ptr

    if DBG:
        print 'helper: handle_call is calling', hex(call_addr)
        print '    returning to', hex(return_addr)
        print '    using args', args
        print '    return val will be placed in', get_var_name(store_var)
        print '    num locals:', env.u8(call_addr)
        print '    local vals:', locals
        print '    code ptr:', hex(code_ptr)
        print '    first inst:', env.u8(code_ptr)

def call(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = opinfo.operands[1:]
    handle_call(env, packed_addr, args, opinfo.store_var)
    if DBG:
        print 'op: call'

def call_2s(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = [opinfo.operands[1]]
    handle_call(env, packed_addr, args, opinfo.store_var)
    if DBG:
        print 'op: call_2s'

def call_vn(env, opinfo):
    packed_addr = opinfo.operands[0]
    args = opinfo.operands[1:]
    handle_call(env, packed_addr, args, store_var=None)
    if DBG:
        print 'op: call_vn'

    if DBG:
        print 'op: remove_obj'
        print '    obj', obj, '(', get_obj_str(env,obj), ')'

def read(env, opinfo):
    text_buffer = opinfo.operands[0]
    parse_buffer = opinfo.operands[1]

    text_buf_len = env.u8(text_buffer)
    parse_buf_len = env.u8(parse_buffer)

    if text_buf_len < 2:
        err('read error: malformed text buffer')
    if parse_buf_len < 1:
        err('read error: malformed parse buffer')

    # this will need to be more sophisticated at some point...
    user_input = raw_input()

    used_buf_len = fill_text_buffer(env, user_input, text_buffer, text_buf_len)

    word_separators = []
    dict_base = env.hdr.dict_base
    num_word_seps = env.u8(dict_base)
    for i in range(num_word_seps):
        word_separators.append(env.u8(dict_base+1+i))

    word = []
    words = []
    word_locs = []
    word_len = 0
    word_lens = []
    scan_ptr = get_text_scan_ptr(text_buffer)
    for i in range(used_buf_len):

        c = env.u8(scan_ptr)

        if c == ord(' '):
            if word:
                word_lens.append(word_len)
                word_len = 0
                words.append(word)
                word = []
            scan_ptr += 1

        elif c in word_separators:
            if word:
                word_lens.append(word_len)
                word_len = 0
                words.append(word)
                word = []
            word_locs.append(scan_ptr-text_buffer)
            word_lens.append(1)
            words.append([c])
            scan_ptr += 1

        else:
            if not word:
                word_locs.append(scan_ptr-text_buffer)
            word.append(c)
            word_len += 1
            scan_ptr += 1

    if word:
        word_lens.append(word_len)
        words.append(word)

    words = clip_word_list(words)

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

    # limit to parse_buf_len (which is num words)
    words = words[:parse_buf_len]
    word_locs = word_locs[:parse_buf_len]
    word_lens = word_lens[:parse_buf_len]

    env.mem[parse_buffer+1] = len(words)
    parse_ptr = parse_buffer+2
    for word,wloc,wlen in zip(words, word_locs, word_lens):
        wordstr = ''.join(map(chr, word))
        dict_addr = 0
        for i in range(num_entries):
            entry_addr = entries_start+i*entry_length
            if match_dict_entry(env, entry_addr, wordstr):
                dict_addr = entry_addr
                break
        env.mem[parse_ptr] = dict_addr >> 8 & 0xff
        env.mem[parse_ptr+1] = dict_addr & 0xff
        env.mem[parse_ptr+2] = wlen
        env.mem[parse_ptr+3] = wloc
        parse_ptr += 4

    if DBG:
        print 'op: read'
        print '    user_input', user_input

# below this line are ops that haven't yet been
# cleared as common to all z-machines

def show_status(env, opinfo):
    if DBG:
        print 'op: show_status (not yet impld)'
        print '    operands', opinfo.operands

def sound_effect(env, opinfo):
    if DBG:
        print 'op: sound_effect (not yet impld)'
        print '    operands', opinfo.operands

def pop(env, opinfo):
    frame = env.callstack[-1]
    frame.stack.pop()
    if DBG:
        print 'op: pop'

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
        print '    dest', get_var_name(var)
