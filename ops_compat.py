from txt import *

def get_obj_addr(env, obj):
    tab = env.hdr.obj_tab_base
    tab += 31*2 # go past default props
    return tab + 9*(obj-1)

def get_parent_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    return env.u8(obj_addr+4)

def get_sibling_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    return env.u8(obj_addr+5)

def get_child_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    return env.u8(obj_addr+6)

def set_parent_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    env.mem[obj_addr+4] = num

def set_sibling_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    env.mem[obj_addr+5] = num

def set_child_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    env.mem[obj_addr+6] = num

def get_obj_desc_addr(env, obj):
    obj_addr = get_obj_addr(env, obj)
    obj_desc_addr = env.u16(obj_addr+7)+1
    return obj_desc_addr

# once again, prop_data_addr is right past the size_num field
def get_sizenum_from_addr(env, prop_data_addr):
    size_and_num = env.u8(prop_data_addr-1)
    size = (size_and_num >> 5) + 1
    num = size_and_num & 31
    return size, num

A0 = 'abcdefghijklmnopqrstuvwxyz'
A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
A2 = ' \n0123456789.,!?_#\'"/\-:()'

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

def unpack_addr(addr, version, offset):
    if version < 4:
        return addr * 2
    elif version < 6:
        return addr * 4
    elif version < 8:
        return addr * 4 + offset * 8
    else: #j8
        return addr * 8

def unpack_addr_call(env, addr):
    version = env.hdr.version
    offset = env.hdr.routine_offset
    return unpack_addr(addr, version, offset)

def unpack_addr_print_paddr(env, addr):
    version = env.hdr.version
    offset = env.hdr.string_offset
    return unpack_addr(addr, version, offset)

#std: 3.8
def zscii_to_ascii(clist):
    result = ''
    for c in clist:
        if c > 31 and c < 127:
            result += chr(c)
        else:
           err('this zscii char not yet implemented: '+str(c))
    return result

def get_prop_list_start(env, obj):
    prop_tab_addr = env.u16(get_obj_addr(env, obj)+7)
    obj_text_len_words = env.u8(prop_tab_addr)
    return prop_tab_addr + 1 + 2*obj_text_len_words

# points straight to data, so past size/num
def _get_prop_addr(env, obj, prop_num):
    prop_ptr = get_prop_list_start(env, obj)
    while env.u8(prop_ptr):
        size_and_num = env.u8(prop_ptr)
        num = size_and_num & 31
        size = (size_and_num >> 5) + 1
        if num == prop_num:
            return prop_ptr+1
        prop_ptr += 1 + size
    return 0

def _get_next_prop(env, obj, prop_num):
    if prop_num == 0:
        prop_start = get_prop_list_start(env, obj)
        next_prop_num = env.u8(prop_start) & 31
    else:
        prop_addr = _get_prop_addr(env, obj, prop_num)
        if prop_addr == 0:
            msg = 'get_next_prop: passed nonexistant prop '
            msg += str(prop_num)+' for obj '+str(obj)+' ('+get_obj_str(env,obj)+')'
            print_prop_list(env, obj)
            err(msg)
        size = (env.u8(prop_addr-1) >> 5) + 1
        next_prop_num = env.u8(prop_addr + size) & 31
    return next_prop_num

def print_prop_list(env, obj):
    print '   ',obj,'-',get_obj_str(env, obj)+':'
    ptr = get_prop_list_start(env, obj)
    while env.u8(ptr):
        size_and_num = env.u8(ptr)
        num = size_and_num & 31
        size = (size_and_num >> 5) + 1
        print '    prop #',num,' - size',size,
        for i in range(size):
            print '   ',hex(env.u8(ptr+1+i)),
        print
        ptr += 1 + size

def get_default_prop(env, prop_num):
    base = env.hdr.obj_tab_base
    return env.u16(base + 2*(prop_num-1))

def setup_locals(env, call_addr):
    num_locals = env.u8(call_addr)

    if env.hdr.version < 5:
        locals_ptr = call_addr + 1
        locals = []
        for i in range(num_locals):
            locals.append(env.u16(locals_ptr))
            locals_ptr += 2
    else:
        locals = [0] * num_locals

    return locals

def get_code_ptr(env, call_addr):
    num_locals = env.u8(call_addr)
    # v1-v4 behavior:
    return call_addr + 2*num_locals + 1

def fill_text_buffer(env, user_input, text_buffer, text_buf_len):

    text_buf_ptr = text_buffer + 1

    '''
    # this is for v5's fill_text_buffer
    # (remember to go back and write the length, too)
    if env.u8(text_buf_ptr):
        text_buf_ptr += env.u8(text_buf_ptr)+1
    '''

    i = 0
    max_len = text_buf_len-(text_buf_ptr-text_buffer)
    while i < min(len(user_input), max_len):
        c = user_input[i]
        if ord(c) > 126 or ord(c) < 32:
            warn('read: this char not impl\'d yet: '+c+' / '+str(ord(c)))
            continue
        env.mem[text_buf_ptr + i] = ord(c.lower())
        i += 1
    # the below is why I can't use a python for loop
    # (it wouldn't set i properly on 0-char input)
    env.mem[text_buf_ptr + i] = 0
    return i

def get_text_scan_ptr(text_buffer):
    return text_buffer + 1

def clip_word_list(words):
    MAX_WORD_LEN = 6
    for i in range(len(words)):
        if len(words[i]) > MAX_WORD_LEN:
            words[i] = words[i][:MAX_WORD_LEN]
    return words

def match_dict_entry(env, entry_addr, wordstr):
    entry = [env.u16(entry_addr), env.u16(entry_addr+2)]
    entry_unpacked = unpack_string(env, entry)
    return wordstr == entry_unpacked

