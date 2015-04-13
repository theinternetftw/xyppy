from txt import *
from zmach import err

def get_obj_addr(env, obj):
    tab = env.hdr.obj_tab_base
    if env.hdr.version < 4:
        tab += 31*2 # go past default props
        return tab + 9*(obj-1)
    else:
        tab += 63*2 # go past default props
        return tab + 14*(obj-1)

def get_obj_str(env, obj):
    obj_desc_addr = get_obj_desc_addr(env, obj)
    obj_desc_packed = read_packed_string(env, obj_desc_addr)
    return unpack_string(env, obj_desc_packed)

def get_parent_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        return env.u8(obj_addr+4)
    else:
        return env.u16(obj_addr+6)

def get_sibling_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        return env.u8(obj_addr+5)
    else:
        return env.u16(obj_addr+8)

def get_child_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        return env.u8(obj_addr+6)
    else:
        return env.u16(obj_addr+10)

def set_parent_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        env.mem[obj_addr+4] = num
    else:
        env.write16(obj_addr+6, num)

def set_sibling_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        env.mem[obj_addr+5] = num
    else:
        env.write16(obj_addr+8, num)

def set_child_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        env.mem[obj_addr+6] = num
    else:
        env.write16(obj_addr+10, num)

def get_obj_desc_addr(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        desc_addr = obj_addr+7
    else:
        desc_addr = obj_addr+12
    return env.u16(desc_addr)+1 # past len byte

A0 = 'abcdefghijklmnopqrstuvwxyz'
A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
A2 = ' \n0123456789.,!?_#\'"/\-:()'

#needs_compat_pass (i think only for v1/v2)
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
#needs_compat_pass
def zscii_to_ascii(clist):
    result = ''
    for c in clist:
        if c > 31 and c < 127:
            result += chr(c)
        else:
           err('this zscii char not yet implemented: '+str(c))
    return result

def get_prop_list_start(env, obj):
    if env.hdr.version < 4:
        offset = 7
    else:
        offset = 12
    prop_tab_addr = env.u16(get_obj_addr(env, obj)+offset)
    obj_text_len_words = env.u8(prop_tab_addr)
    return prop_tab_addr + 1 + 2*obj_text_len_words

# points at size/num
def get_prop_size(env, prop_ptr):
    if env.hdr.version < 4:
        return (env.u8(prop_ptr) >> 5) + 1
    else:
        first_byte = env.u8(prop_ptr)
        if first_byte & 128:
            size_byte = env.u8(prop_ptr+1)
            if not (size_byte & 128):
                err('malformed prop size byte: '+bin(num_byte))
            return (size_byte & 63) or 64 # zero len == 64
        if first_byte & 64:
            return 2
        return 1

# points at size/num
def get_prop_num(env, prop_ptr):
    num_byte = env.u8(prop_ptr)
    if env.hdr.version < 4:
        return num_byte & 31
    else:
        return num_byte & 63

# points at size/num
def get_prop_data_ptr(env, prop_ptr):
    if env.hdr.version < 4:
        return prop_ptr+1
    else:
        if env.u8(prop_ptr) & 128:
            return prop_ptr+2
        return prop_ptr+1

# points straight to data, so past size/num
def compat_get_prop_addr(env, obj, prop_num):
    prop_ptr = get_prop_list_start(env, obj)
    while env.u8(prop_ptr):
        num = get_prop_num(env, prop_ptr)
        size = get_prop_size(env, prop_ptr)
        data_ptr = get_prop_data_ptr(env, prop_ptr)
        if num == prop_num:
            return data_ptr
        prop_ptr = data_ptr + size
    return 0 # not found

def get_sizenum_ptr(env, prop_data_ptr):
    if env.hdr.version < 4:
        return prop_data_ptr-1
    else:
        if env.u8(prop_data_ptr-1) & 128:
            return prop_data_ptr-2
        return prop_data_ptr-1

def compat_get_next_prop(env, obj, prop_num):
    if prop_num == 0:
        prop_start = get_prop_list_start(env, obj)
        next_prop_num = get_prop_num(env, prop_start)
    else:
        prop_data_addr = compat_get_prop_addr(env, obj, prop_num)
        if prop_data_addr == 0:
            msg = 'get_next_prop: passed nonexistant prop '
            msg += str(prop_num)+' for obj '+str(obj)+' ('+get_obj_str(env,obj)+')'
            print_prop_list(env, obj)
            err(msg)
        sizenum_ptr = get_sizenum_ptr(env, prop_data_addr)
        size = get_prop_size(env, sizenum_ptr)
        next_prop_num = get_prop_num(env, prop_data_addr + size)
    return next_prop_num

def print_prop_list(env, obj):
    print '   ',obj,'-',get_obj_str(env, obj)+':'
    ptr = get_prop_list_start(env, obj)
    while env.u8(ptr):
        num = get_prop_num(env, ptr)
        size = get_prop_size(env, ptr)
        data_ptr = get_prop_data_ptr(env, ptr)
        print '    prop #',num,' - size',size,
        for i in range(size):
            print '   ',hex(env.u8(data_ptr+i)),
        print
        ptr = data_ptr + size

def get_default_prop(env, prop_num):
    base = env.hdr.obj_tab_base
    return env.u16(base + 2*(prop_num-1))

# prop_data_addr is right past the size_num field
def get_sizenum_from_addr(env, prop_data_addr):
    sizenum_ptr = get_sizenum_ptr(env, prop_data_addr)
    size = get_prop_size(env, sizenum_ptr)
    num = get_prop_num(env, sizenum_ptr)
    return size, num

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
    if env.hdr.version < 5:
        return call_addr + 2*num_locals + 1
    else:
        return call_addr + 1

#needs_compat_pass
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

#needs_compat_pass
def get_text_scan_ptr(text_buffer):
    return text_buffer + 1

#needs_compat_pass
def clip_word_list(words):
    MAX_WORD_LEN = 6
    for i in range(len(words)):
        if len(words[i]) > MAX_WORD_LEN:
            words[i] = words[i][:MAX_WORD_LEN]
    return words

#needs_compat_pass
def match_dict_entry(env, entry_addr, wordstr):
    entry = [env.u16(entry_addr), env.u16(entry_addr+2)]
    entry_unpacked = unpack_string(env, entry)
    return wordstr == entry_unpacked

