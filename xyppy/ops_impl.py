# ops_impl.py (as in this file implements the opcodes)
#
# the goal here is to have no z-machine version control flow in here,
# i.e. no 'if *.z5 then X else Y'. All that should be in ops_impl_compat.py

import random

from xyppy.debug import DBG, warn, err
from xyppy.zmath import to_signed_word

from xyppy.ops_impl_compat import *

import xyppy.quetzal as quetzal

def get_var(env, var_num, pop_stack=True):
    # if DBG:
    #     warn('    get_var(', get_var_name(var_num), ', pop_stack =', pop_stack, ')')

    if var_num == 0:
        frame = env.callstack[-1]
        if pop_stack:
            return frame.stack.pop()
        else:
            return frame.stack[-1]
    elif var_num < 16:
        frame = env.callstack[-1]
        return frame.locals[var_num - 1]
    elif var_num < 256:
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        return env.u16(g_base + 2*g_idx)
    else:
        err('illegal var num: '+str(var_num))


def set_var(env, var_num, result, push_stack=True):
    # if DBG:
    #     warn('    set_var(', get_var_name(var_num), ',', result, ', push_stack =', push_stack, ')')

    result &= 0xffff

    if var_num == 0:
        frame = env.callstack[-1]
        if push_stack:
            frame.stack.append(result)
        else:
            frame.stack[-1] = result
    elif var_num < 16:
        frame = env.callstack[-1]
        frame.locals[var_num - 1] = result
    elif var_num < 256:
        g_idx = var_num - 16
        g_base = env.hdr.global_var_base
        env.write16(g_base + 2*g_idx, result)
    else:
        err('set_var: illegal var_num: '+str(var_num))


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

def sub(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a-b
    set_var(env, opinfo.store_var, result)

def mul(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a*b
    set_var(env, opinfo.store_var, result)

def div(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    num_neg = (a < 0) + (b < 0)
    result = abs(a) // abs(b)
    if num_neg == 1:
        result = -result
    set_var(env, opinfo.store_var, result)

def mod(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = abs(a) % abs(b)
    if a < 0: # spec says a determines sign
        result = -result
    set_var(env, opinfo.store_var, result)

def load(env, opinfo):
    var = opinfo.operands[0]
    val = get_var(env, var, pop_stack=False)
    set_var(env, opinfo.store_var, val)

def jz(env, opinfo):
    result = opinfo.operands[0] == 0

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def je(env, opinfo):
    result = False
    first = opinfo.operands[0]
    for op in opinfo.operands[1:]:
        if first == op:
            result = True
            break

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def jl(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a < b

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def jg(env, opinfo):
    a = to_signed_word(opinfo.operands[0])
    b = to_signed_word(opinfo.operands[1])
    result = a > b

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

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

def loadw(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = to_signed_word(opinfo.operands[1])
    word_loc = 0xffff & (array_addr + 2*word_index)

    set_var(env, opinfo.store_var, env.u16(word_loc))

def loadb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = to_signed_word(opinfo.operands[1])
    byte_loc = 0xffff & (array_addr + byte_index)

    set_var(env, opinfo.store_var, env.mem[byte_loc]) 

def storeb(env, opinfo):
    array_addr = opinfo.operands[0]
    byte_index = to_signed_word(opinfo.operands[1])
    val = opinfo.operands[2] & 0xff
    mem_loc = 0xffff & (array_addr + byte_index)

    env.write8(mem_loc, val)

def storew(env, opinfo):
    array_addr = opinfo.operands[0]
    word_index = to_signed_word(opinfo.operands[1])
    val = opinfo.operands[2]
    word_loc = 0xffff & (array_addr + 2*word_index)

    env.write16(word_loc, val)

def store(env, opinfo):
    var = opinfo.operands[0]
    val = opinfo.operands[1]
    set_var(env, var, val, push_stack=False)

def and_(env, opinfo):
    acc = 0xffff
    for operand in opinfo.operands:
        acc &= operand
    set_var(env, opinfo.store_var, acc)

def or_(env, opinfo):
    acc = 0
    for operand in opinfo.operands:
        acc |= operand
    set_var(env, opinfo.store_var, acc)

def inc(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    set_var(env, var_num, var_val+1)

def dec(env, opinfo):
    var_num = opinfo.operands[0]
    var_val = to_signed_word(get_var(env, var_num))
    set_var(env, var_num, var_val-1)

def inc_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = to_signed_word(opinfo.operands[1])

    var_val = to_signed_word(get_var(env, var_loc) + 1)
    set_var(env, var_loc, var_val)

    result = var_val > chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def dec_chk(env, opinfo):
    var_loc = opinfo.operands[0]
    chk_val = to_signed_word(opinfo.operands[1])

    var_val = to_signed_word(get_var(env, var_loc) - 1)
    set_var(env, var_loc, var_val)

    result = var_val < chk_val
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def test(env, opinfo):
    bitmap = opinfo.operands[0]
    flags = opinfo.operands[1]
    result = bitmap & flags == flags

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    bitmap', bin(bitmap))
        warn('    flags', bin(flags))

def push(env, opinfo):
    value = opinfo.operands[0]
    frame = env.callstack[-1]
    frame.stack.append(value)

def random_(env, opinfo):
    rand_max = to_signed_word(opinfo.operands[0])
    if rand_max < 0:
        random.seed(rand_max)
        result = 0
    elif rand_max == 0:
        random.seed()
        result = 0
    else:
        result = random.randint(1, rand_max)
    set_var(env, opinfo.store_var, result)

def jin(env, opinfo):
    obj1 = opinfo.operands[0]
    obj2 = opinfo.operands[1]

    result = get_parent_num(env, obj1) == obj2

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    obj1', obj1, '(',get_obj_str(env,obj1),')')
        warn('    obj2', obj2, '(',get_obj_str(env,obj2),')')
        warn('    is_parent?', result)

def get_child(env, opinfo):
    obj = opinfo.operands[0]

    child_num = get_child_num(env, obj)
    set_var(env, opinfo.store_var, child_num)

    result = child_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    child', child_num, '(',get_obj_str(env, child_num),')')

def get_sibling(env, opinfo):
    obj = opinfo.operands[0]

    sibling_num = get_sibling_num(env, obj)
    set_var(env, opinfo.store_var, sibling_num)

    result = sibling_num != 0
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    sibling', sibling_num, '(',get_obj_str(env, sibling_num),')')

def get_parent(env, opinfo):
    obj = opinfo.operands[0]

    parent_num = get_parent_num(env, obj)
    set_var(env, opinfo.store_var, parent_num)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env, obj),')')
        warn('    parent', parent_num, '(',get_obj_str(env, parent_num),')')

def handle_return(env, return_val):
    frame = env.callstack.pop()
    if frame.return_addr == 0:
        err('returned from unreturnable/nonexistant function!')
    if frame.return_val_loc != None:
        set_var(env, frame.return_val_loc, return_val)
    env.pc = frame.return_addr

    if DBG:
        warn('    helper: handle_return')
        warn('        return_val', return_val)
        if frame.return_val_loc:
            warn('        return_val_loc', get_var_name(frame.return_val_loc))
        else:
            warn('        return_val_loc None')
        warn('        return_addr', hex(frame.return_addr))

def ret(env, opinfo):
    return_val = opinfo.operands[0]
    handle_return(env, return_val)

def rtrue(env, opinfo):
    handle_return(env, 1)

def rfalse(env, opinfo):
    handle_return(env, 0)

def ret_popped(env, opinfo):
    frame = env.callstack[-1]
    ret_val = frame.stack.pop()
    handle_return(env, ret_val)

def quit(env, opinfo):
    env.quit()

def print_(env, opinfo):
    string = unpack_string(env, opinfo.operands)
    write(env, string)

def print_ret(env, opinfo):
    string = unpack_string(env, opinfo.operands)+'\n'
    write(env, string)
    handle_return(env, 1)

def print_paddr(env, opinfo):
    addr = unpack_addr_print_paddr(env, opinfo.operands[0])
    _print_addr(env, addr)

def _print_addr(env, addr):
    packed_string = read_packed_string(env, addr)
    string = unpack_string(env, packed_string)
    write(env, string)

    if DBG:
        warn('    helper: _print_addr')
        warn('            addr', addr)

def print_addr(env, opinfo):
    addr = opinfo.operands[0]
    _print_addr(env, addr)

def new_line(env, opinfo):
    write(env, '\n')

def print_num(env, opinfo):
    num = to_signed_word(opinfo.operands[0])
    write(env, str(num))

def print_obj(env, opinfo):
    obj = opinfo.operands[0]
    string = get_obj_str(env, obj)
    write(env, string)

    if DBG:
        warn('    obj', obj, '(', get_obj_str(env, obj), ')')

def print_char(env, opinfo):
    char = zscii_to_ascii(env, [opinfo.operands[0]])
    write(env, char)

def get_prop_len(env, opinfo):
    prop_data_ptr = opinfo.operands[0]
    if prop_data_ptr == 0: # to spec
        size = 0
    else:
        sizenum_ptr = get_sizenum_ptr(env, prop_data_ptr)
        size = get_prop_size(env, sizenum_ptr)
    set_var(env, opinfo.store_var, size)

# seems to be needed for practicality
# test case:
# Delusions (input: any_key, e, wait)
FORGIVING_GET_PROP = True

def get_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    prop_data_ptr = get_prop_data_ptr_from_obj(env, obj, prop_num)
    is_default_prop = prop_data_ptr == 0
    if is_default_prop:
        base = env.hdr.obj_tab_base
        result = env.u16(base + 2*(prop_num-1))
    else:
        sizenum_ptr = get_sizenum_ptr(env, prop_data_ptr)
        size = get_prop_size(env, sizenum_ptr)
        if size == 1:
            result = env.mem[prop_data_ptr]
        elif size == 2 or FORGIVING_GET_PROP:
            result = env.u16(prop_data_ptr)
        else:
            msg = 'illegal op: get_prop on outsized prop (not 1-2 bytes)'
            msg += ' - prop '+str(prop_num)
            msg += ' of obj '+str(obj)+' ('+get_obj_str(env, obj)+')'
            msg += ' (sized at '+str(size)+' bytes)'
            print_prop_list(env, obj)
            err(msg)

    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    result', result)
        warn('    is_default_prop', is_default_prop)
        print_prop_list(env, obj)

def put_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]
    val = opinfo.operands[2]

    prop_data_ptr = get_prop_data_ptr_from_obj(env, obj, prop_num)
    if prop_data_ptr == 0:
        msg = 'illegal op: put_prop on nonexistant property'
        msg += ' - prop '+str(prop_num)
        msg += ' not found on obj '+str(obj)+' ('+get_obj_str(env, obj)+')' 
        err(msg)

    sizenum_ptr = get_sizenum_ptr(env, prop_data_ptr)
    size = get_prop_size(env, sizenum_ptr)
    if size == 2:
        env.write16(prop_data_ptr, val)
    elif size == 1:
        env.write8(prop_data_ptr, val & 0xff)
    else:
        msg = 'illegal op: put_prop on outsized prop (not 1-2 bytes)'
        msg += ' - prop '+str(prop_num)
        msg += ' of obj '+str(obj)+' ('+get_obj_str(obj)+')'
        msg += ' (sized at '+size+' bytes)'
        err(msg)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    val', val)
        print_prop_list(env, obj)

def get_prop_addr(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    if obj == 0:
        # from testing, this seems
        # to be the expected behavior
        result = 0
    else:
        result = get_prop_data_ptr_from_obj(env, obj, prop_num)
    set_var(env, opinfo.store_var, result)

    if DBG:
        warn('    obj', obj,'(',get_obj_str(env,obj),')')
        warn('    prop_num', prop_num)
        warn('    result', result)
        if obj:
            print_prop_list(env, obj)

def get_next_prop(env, opinfo):
    obj = opinfo.operands[0]
    prop_num = opinfo.operands[1]

    next_prop_num = 0
    if obj:
        if prop_num == 0:
            prop_start = get_prop_list_start(env, obj)
            next_prop_num = get_prop_num(env, prop_start)
        else:
            prop_data_ptr = get_prop_data_ptr_from_obj(env, obj, prop_num)
            if prop_data_ptr == 0:
                msg = 'get_next_prop: passed nonexistant prop '
                msg += str(prop_num)+' for obj '+str(obj)+' ('+get_obj_str(env,obj)+')'
                print_prop_list(env, obj)
                err(msg)
            sizenum_ptr = get_sizenum_ptr(env, prop_data_ptr)
            size = get_prop_size(env, sizenum_ptr)
            next_prop_num = get_prop_num(env, prop_data_ptr + size)
    set_var(env, opinfo.store_var, next_prop_num)

    if DBG:
        warn('    prop_num', prop_num)
        warn('    next_prop_num', next_prop_num)
        print_prop_list(env, obj)

def not_(env, opinfo):
    val = ~(opinfo.operands[0])
    set_var(env, opinfo.store_var, val)

def insert_obj(env, opinfo):
    obj = opinfo.operands[0]
    dest = opinfo.operands[1]

    if not obj or not dest:
        return

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
        warn('    helper: _remove_obj')
        warn('        obj', obj, '(', get_obj_str(env,obj), ')')
        warn('        parent', parent, '(', get_obj_str(env,parent), ')')

def remove_obj(env, opinfo):
    obj = opinfo.operands[0]
    if obj:
        _remove_obj(env, obj)

def set_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    if obj:
        obj_addr = get_obj_addr(env, obj)

        attr_byte = attr // 8
        mask = 2**(7-attr%8)
        old_val = env.mem[obj_addr+attr_byte]
        env.write8(obj_addr+attr_byte, old_val|mask)

    if DBG:
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)

def clear_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    if obj:
        obj_addr = get_obj_addr(env, obj)

        attr_byte = attr // 8
        mask = 2**(7-attr%8)
        old_val = env.mem[obj_addr+attr_byte]
        env.write8(obj_addr+attr_byte, old_val & ~mask)

    if DBG:
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)

def test_attr(env, opinfo):
    obj = opinfo.operands[0]
    attr = opinfo.operands[1]

    if obj:
        obj_addr = get_obj_addr(env, obj)

        attr_byte = attr // 8
        shift_amt = 7 - attr%8
        attr_val = (env.mem[obj_addr+attr_byte] >> shift_amt) & 1
        result = attr_val == 1
    else:
        result = False
    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    obj', obj, '(', get_obj_str(env,obj), ')')
        warn('    attr', attr)

class Frame:
    def __init__(self, return_addr, num_args=0, locals=[], return_val_loc=None, stack=[]):
        self.return_addr = return_addr
        self.num_args = num_args
        self.locals = locals
        self.stack = stack
        self.return_val_loc = return_val_loc

# in xyppy, call does the job of all other call_* variants, as
# decode handles their differentiation.
def call(env, opinfo):
    packed_addr = opinfo.operands[0]

    if packed_addr == 0:
        if opinfo.store_var != None:
            set_var(env, opinfo.store_var, 0)
        if DBG:
            warn('op: calling 0 (returns false)')
        return

    return_addr = env.pc

    fncache = env.fncache
    if packed_addr in fncache:
        call_addr, local_vars, code_ptr = fncache[packed_addr]
        local_vars = local_vars[:] # leave cached vars for later hits
    else:
        call_addr = unpack_addr_call(env, packed_addr)
        local_vars, code_ptr = parse_call_header(env, call_addr)
        if call_addr >= env.hdr.static_mem_base:
            fncache[packed_addr] = call_addr, local_vars, code_ptr
            local_vars = local_vars[:] # leave cached vars for later hits

    # args dropped if past len of locals arr
    num_args = min(len(opinfo.operands)-1, len(local_vars))
    local_vars[:num_args] = opinfo.operands[1:num_args+1]

    env.callstack.append(Frame(return_addr,
                               num_args,
                               local_vars,
                               opinfo.store_var))
    env.pc = code_ptr

    if DBG:
        warn('        calling', hex(call_addr))
        warn('        returning to', hex(return_addr))
        warn('        using args', opinfo.operands[1:])
        if opinfo.store_var == None:
            warn('        return val will be discarded')
        else:
            warn('        return val will be placed in', get_var_name(opinfo.store_var))
        warn('        num locals:', env.mem[call_addr])
        warn('        local vals:', local_vars)
        warn('        code ptr:', hex(code_ptr))
        warn('        first inst:', env.mem[code_ptr])

def check_arg_count(env, opinfo):
    arg_num = opinfo.operands[0]
    frame = env.callstack[-1]
    result = frame.num_args >= arg_num

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    arg_num', arg_num)
        warn('    num args in frame', frame.num_args)
        warn('    branch_offset', opinfo.branch_offset)
        warn('    branch_on', opinfo.branch_on)
        warn('    result', result)

def handle_read(env, text_buffer, parse_buffer, time=0, routine=0):

    if time != 0 or routine != 0:
        if DBG:
            err('interrupts requested but not impl\'d yet!')

    prefilled = get_text_buffer_as_str(env, text_buffer)
    user_input = ascii_to_zscii(env.screen.get_line_of_input(prompt='', prefilled=prefilled).lower())

    fill_text_buffer(env, user_input, text_buffer)

    if env.hdr.version < 5 or parse_buffer != 0:
        handle_parse(env, text_buffer, parse_buffer)

    # return ord('\r') as term char for now... 
    # TODO: the right thing 
    return ord('\r')

def aread(env, opinfo):
    text_buffer = opinfo.operands[0]
    if len(opinfo.operands) > 1:
        parse_buffer = opinfo.operands[1]
    else:
        parse_buffer = 0
    if len(opinfo.operands) == 4:
        time, routine = opinfo.operands[2:4]
    else:
        time, routine = 0, 0

    end_char = handle_read(env, text_buffer, parse_buffer, time, routine)
    set_var(env, opinfo.store_var, end_char)

def sread(env, opinfo):
    text_buffer = opinfo.operands[0]
    if len(opinfo.operands) > 1:
        parse_buffer = opinfo.operands[1]
    else:
        parse_buffer = 0
    if len(opinfo.operands) == 4:
        time, routine = opinfo.operands[2:4]
    else:
        time, routine = 0, 0

    handle_read(env, text_buffer, parse_buffer, time, routine)

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

def read_char(env, opinfo):
    # NOTE: operands[0] must be 1, but I ran into a z5 that passed no operands
    # (strictz) so let's just ignore the first operand instead...
    if len(opinfo.operands) > 1:
        if len(opinfo.operands) != 3:
            err('read_char: num operands must be 1 or 3')
        if opinfo.operands[1] != 0 or opinfo.operands[2] != 0:
            if DBG:
                warn('read_char: interrupts not impl\'d yet!')
    c = ascii_to_zscii(env.screen.getch_or_esc_seq())[0]
    set_var(env, opinfo.store_var, c)

def set_font(env, opinfo):
    font_num = opinfo.operands[0]
    if font_num == 0:
        set_var(env, opinfo.store_var, 1)
    if font_num != 1:
        set_var(env, opinfo.store_var, 0)
    else:
        set_var(env, opinfo.store_var, 1)

def pop(env, opinfo):
    frame = env.callstack[-1]
    frame.stack.pop()

def pull(env, opinfo):
    var = opinfo.operands[0]

    frame = env.callstack[-1]
    result = frame.stack.pop()
    set_var(env, var, result, push_stack=False)

def buffer_mode(env, opinfo):
    env.screen.finish_wrapping()

    flag = opinfo.operands[0]
    env.use_buffered_output = (flag == 1)

def output_stream(env, opinfo):
    stream = to_signed_word(opinfo.operands[0])
    if stream < 0:
        stream = abs(stream)
        if stream == 3:
            table_addr = env.memory_ostream_stack.pop()
            zscii_buffer = ascii_to_zscii(env.output_buffer[stream])
            buflen = len(zscii_buffer)
            env.write16(table_addr, buflen)
            for i in range(len(zscii_buffer)):
                env.write8(table_addr+2+i, zscii_buffer[i])
            env.output_buffer[stream] = ''
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

def restart(env, opinfo):
    env.reset()

def log_shift(env, opinfo):
    number = opinfo.operands[0]
    places = to_signed_word(opinfo.operands[1])
    if places < 0:
        result = number >> abs(places)
    else:
        result = number << places
    set_var(env, opinfo.store_var, result)

def art_shift(env, opinfo):
    number = to_signed_word(opinfo.operands[0])
    places = to_signed_word(opinfo.operands[1])
    if places < 0:
        result = number >> abs(places)
    else:
        result = number << places
    set_var(env, opinfo.store_var, result)

def get_file_len(env):
    if env.hdr.version < 4:
        return 2*env.hdr.file_len
    elif env.hdr.version < 6:
        return 4*env.hdr.file_len
    else:
        return 8*env.hdr.file_len

def verify(env, opinfo):
    vsum = 0
    for i in range(0x40, get_file_len(env)):
        vsum += env.orig_mem[i]
    vsum &= 0xffff
    result = vsum == env.hdr.checksum

    if result == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    vsum', vsum)
        warn('    checksum in header', env.hdr.checksum)
        warn('    branch_on', opinfo.branch_on)
        warn('    result', result)

def piracy(env, opinfo):
    handle_branch(env, opinfo.branch_offset)

def copy_table(env, opinfo):
    first = opinfo.operands[0]
    second = opinfo.operands[1]
    size = to_signed_word(opinfo.operands[2])
    if second == 0:
        # zeros out first
        size = abs(size)
        for i in range(size):
            env.write8(first+i, 0)
    elif size > 0:
        # protects against corruption of overlapping tables
        tab = env.mem[first:first+size]
        for i in range(size):
            env.write8(second+i, tab[i])
    elif size < 0:
        # allows for the corruption of overlapping tables
        size = abs(size)
        for i in range(size):
            env.write8(second+i, env.mem[first+i])

def scan_table(env, opinfo):
    val = opinfo.operands[0]
    tab_addr = opinfo.operands[1]
    tab_len = opinfo.operands[2]
    if len(opinfo.operands) > 3:
        form = opinfo.operands[3]
    else:
        form = 0x82
    val_size = (form >> 7) + 1 # word or byte
    field_len = form & 127

    addr = 0
    for i in range(tab_len):
        test_addr = tab_addr + i*field_len
        if val_size == 2:
            test_val = env.u16(test_addr)
        else:
            test_val = env.mem[test_addr]
        if val == test_val:
            addr = test_addr
            break
    found = addr != 0
    set_var(env, opinfo.store_var, addr)
    if found == opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

    if DBG:
        warn('    found', found)
        warn('    addr', addr)

# TODO: make sure this actually works
def print_table(env, opinfo):
    env.screen.finish_wrapping()

    tab_addr = opinfo.operands[0]
    width = opinfo.operands[1]

    if len(opinfo.operands) > 2:
        height = opinfo.operands[2]
    else:
        height = 1

    if len(opinfo.operands) > 3:
        skip = opinfo.operands[3]
    else:
        skip = 0

    col = env.cursor[env.current_window][1]
    for i in range(height):
        row = env.cursor[env.current_window][0]
        line = [env.mem[tab_addr + i*(width+skip) + j] for j in range(width)]
        write(env, zscii_to_ascii(env, line))
        if i < height - 1:
            env.screen.finish_wrapping()
            if (env.current_window == 0 and row < env.hdr.screen_height_units-1 or
              env.current_window == 1 and row < env.top_window_height-1):
                env.cursor[env.current_window] = row+1, col
            else:
                env.cursor[env.current_window] = row, col

def nop(env, opinfo):
    # what'd you expect?
    return

def erase_window(env, opinfo):
    env.screen.finish_wrapping()

    window = to_signed_word(opinfo.operands[0])

    if window in [0, -1, -2]:
        env.screen.blank_bottom_win()
    if window in [1, -1, -2]:
        env.screen.blank_top_win()

    if window == -1:
        env.top_window_height = 0
        env.current_window = 0

    if window in [0, -1, -2]:
        env.cursor[0] = get_cursor_loc_after_erase(env, 0)
    if window in [1, -1, -2]:
        env.cursor[1] = get_cursor_loc_after_erase(env, 1)

def split_window(env, opinfo):
    env.screen.finish_wrapping()

    old_height = env.top_window_height

    # an unfortunate hack, but makes Inform games look better,
    # as they intentionally don't fill up the entire status bar (so
    # this is me trying to keep the Trinity trick and those bars both
    # looking good). only doing it on 0 to 1-bar transitions,
    # because those sound like status bars being made, right?
    if opinfo.operands[0] == 1 and env.top_window_height == 0:
        env.screen.scroll_top_line_only()

    env.top_window_height = opinfo.operands[0]
    if env.top_window_height > env.hdr.screen_height_units:
        err('split_window: requested split bigger than screen:', env.top_window_height)

    # the spec suggests pushing the bottom window cursor down.
    # to allow for more trinity-style tricks, we'll do that only
    # when it's being written to (see env.screen.write).

def set_window(env, opinfo):
    env.screen.finish_wrapping()

    env.current_window = opinfo.operands[0]
    if env.current_window == 1:
        env.cursor[1] = (0,0)

    if env.current_window not in [0,1]:
        err('set_window: requested unknown window:', env.current_window)

def restore_z3(env, opinfo):
    filename = env.screen.get_line_of_input('input save filename: ')
    loaded = quetzal.load_to_env(env, filename)
    if loaded:
        # move past save inst's branch byte(s)
        # (which quetzal gives as the PC)
        env.pc += 1 if env.mem[env.pc] & 64 else 2

def restore(env, opinfo):
    # TODO handle optional operands
    if len(opinfo.operands) > 0:
        if DBG:
            warn('restore: found operands (not yet impld): '+str(opinfo.operands))
        set_var(env, opinfo.store_var, 0)
        return

    filename = env.screen.get_line_of_input('input save filename: ')
    loaded = quetzal.load_to_env(env, filename)
    if loaded:
        # set and move past save inst's svar byte
        # (which quetzal gives as the PC)
        set_var(env, env.mem[env.pc], 2)
        env.pc += 1
    else:
        set_var(env, opinfo.store_var, 0)

def save_z3(env, opinfo):
    filename = env.screen.get_line_of_input('input save filename: ')
    saved = quetzal.write(env, filename)
    if saved and opinfo.branch_on:
        handle_branch(env, opinfo.branch_offset)

def save(env, opinfo):
    # TODO handle optional operands
    if len(opinfo.operands) > 0:
        if DBG:
            warn('restore: found operands (not yet impld): '+str(opinfo.operands))
        set_var(env, opinfo.store_var, 0)
        return

    filename = env.screen.get_line_of_input('input save filename: ')
    if quetzal.write(env, filename):
        set_var(env, opinfo.store_var, 1)
    else:
        set_var(env, opinfo.store_var, 0)

def set_cursor(env, opinfo):
    env.screen.finish_wrapping()

    row = to_signed_word(opinfo.operands[0])
    col = to_signed_word(opinfo.operands[1])
    if row < 1: # why do we not error out here?
        row = 1
    if col < 1: # same question
        col = 1

    # ignores win 0 (S 8.7.2.3)
    if env.current_window == 1:
        if col > env.hdr.screen_width_units:
            if DBG:
                warn('set_cursor: set outside screen width', col)
            col = env.hdr.screen_width_units
        if row > env.hdr.screen_height_units:
            if DBG:
                warn('set_cursor: set outside screen height', row)
            row = env.hdr.screen_height_units
        # see 3rd to last note at bottom of section 8
        env.top_window_height = max(env.top_window_height, row-1)
        # fix that row,col have a 1,1 origin
        env.cursor[env.current_window] = row-1, col-1

def set_colour(env, opinfo):
    fg_col = opinfo.operands[0]
    bg_col = opinfo.operands[1]
    if fg_col > 9 or bg_col > 9 or fg_col < 0 or bg_col < 0:
        err('set_color attempted illegal color')
    if fg_col == 1:
        fg_col = env.hdr.default_fg_color
    if fg_col != 0:
        env.fg_color = fg_col
    if bg_col == 1:
        bg_col = env.hdr.default_bg_color
    if bg_col != 0:
        env.bg_color = bg_col

def print_unicode(env, opinfo):
    ucode = opinfo.operands[0]
    if ucode < 128:
        write(env, chr(ucode))
    else:
        write(env, translate_unicode(ucode))

def check_unicode(env, opinfo):
    if opinfo.operands[0] < 128:
        result = 3
    else:
        result = 0
    set_var(env, opinfo.store_var, result)

def catch(env, opinfo):
    set_var(env, opinfo.store_var, len(env.callstack))

def throw(env, opinfo):
    ret_val = opinfo.operands[0]
    callstack_len = opinfo.operands[1]

    while len(env.callstack) > callstack_len:
        env.callstack.pop()

    handle_return(env, ret_val)

def show_status(env, opinfo):
    if DBG:
        warn('    (not impld)')

def set_text_style(env, opinfo):
    style = opinfo.operands[0]
    if style == 0:
        env.text_style = 'normal'
    if style & 1:
        env.text_style = 'reverse_video'
    # TODO: (?) these text styles? multiple text styles at once?
    # if style & 2:
    #     env.text_style = 'bold'
    # if style & 4:
    #     env.text_style = 'italic'
    # if style & 8:
    #     env.text_style = 'fixed_pitch'

def sound_effect(env, opinfo):
    if DBG:
        warn('    (not impld)')

def save_undo(env, opinfo):
    set_var(env, opinfo.store_var, -1)
    if DBG:
        warn('    (not impld for now)')
        warn('    (but at least I can notify the game of that)')

def write(env, text):
    # stream 3 overrides all other output
    if 3 in env.selected_ostreams:
        env.output_buffer[3] += text
        return
    # TODO: (if I so choose): stream 2 (transcript stream)
    # should also be able to wordwrap if buffer is on
    for stream in env.selected_ostreams:
        if stream == 1:
            env.screen.write(text)
        else:
            env.output_buffer[stream] += text
