from debug import warn, err

def get_cursor_loc_after_erase(env, cleared_window):
    if env.hdr.version >= 5:
        return 0, 0
    if cleared_window == 0:
        return env.hdr.screen_height_units - 1, 0
    return 0, 0

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
        env.write8(obj_addr+4, num)
    else:
        env.write16(obj_addr+6, num)

def set_sibling_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        env.write8(obj_addr+5, num)
    else:
        env.write16(obj_addr+8, num)

def set_child_num(env, obj, num):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        env.write8(obj_addr+6, num)
    else:
        env.write16(obj_addr+10, num)

def get_obj_desc_addr(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        desc_addr = obj_addr+7
    else:
        desc_addr = obj_addr+12
    return env.u16(desc_addr)+1 # past len byte

Default_A0 = 'abcdefghijklmnopqrstuvwxyz'
Default_A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
Default_A2 = ' \n0123456789.,!?_#\'"/\-:()'

#needs_compat_pass (i think only for v1/v2)
def unpack_string(env, packed_text, warn_unknown_char=True):

    split_text = []
    for word in packed_text:
        split_text += [word >> 10 & 0x1f,
                       word >> 5 & 0x1f,
                       word & 0x1f]

    #check the differences between v1/v2 and v3 here
    #going w/ v3 compat only atm
    if env.hdr.version >= 5 and env.hdr.alpha_tab_base:
        base = env.hdr.alpha_tab_base
        A0 = ''.join(map(chr, list(env.mem[base+0*26:base+1*26])))
        A1 = ''.join(map(chr, list(env.mem[base+1*26:base+2*26])))
        A2 = ''.join(map(chr, list(env.mem[base+2*26:base+3*26])))
    else:
        A0 = Default_A0
        A1 = Default_A1
        A2 = Default_A2

    text = []
    currentAlphabet = A0
    abbrevShift = 0
    current_10bit = 0
    mode = 'NONE'
    for i in xrange(len(split_text)):
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
            text += zscii_to_ascii([current_10bit], warn_unknown_char)
        elif char == 0:
            text.append(' ')
            currentAlphabet = A0
        elif char == 4:
            currentAlphabet = A1
        elif char == 5:
            currentAlphabet = A2
        elif char == 6 and currentAlphabet == A2: # override any custom alpha with escape seq start
            mode = '10BIT_HIGH'
            currentAlphabet = A0
        elif char == 7 and currentAlphabet == A2: # override any custom alpha with newline
            text.append('\n')
        elif char in [1,2,3]:
            abbrevShift = char
            currentAlphabet = A0
        else:
            text.append(currentAlphabet[char-6])
            currentAlphabet = A0
    return ''.join(text)

def unpack_addr(addr, version, offset=0):
    if version < 4:
        return addr * 2
    elif version < 6:
        return addr * 4
    elif version < 8:
        return addr * 4 + offset * 8
    else: #z8
        return addr * 8

def unpack_addr_call(env, addr):
    version = env.hdr.version
    if version == 7:
        return unpack_addr(addr, version, env.hdr.routine_offset)
    else:
        return unpack_addr(addr, version)

def unpack_addr_print_paddr(env, addr):
    version = env.hdr.version
    if version == 7:
        return unpack_addr(addr, version, env.hdr.string_offset)
    else:
        return unpack_addr(addr, version)

#std: 3.8
#needs_compat_pass
def zscii_to_ascii(clist, warn_unknown_char=True):
    result = ''
    for c in clist:
        if c == 0:
            # 0 == no effect in zscii
            continue
        if c == ord('\r'):
            result += '\n'
        elif c > 31 and c < 127:
            result += chr(c)
        elif warn_unknown_char:
           warn('this zscii char not yet implemented: '+str(c))
    return result

#std: 3.8
#needs_compat_pass
def ascii_to_zscii(string):
    result = []
    for c in string:
        if c == '\n':
            result.append(ord('\r'))
        # NOTE: gargoyle just ignores the tab key,
        # S 3.8.2.3 says output only. But I'd like
        # to keep readline enabled on linux, so, for
        # the moment, I make this compromise.
        elif c == '\t':
            result.append(ord(' '))
        elif c in ('\r','\b') or (ord(c) > 31 and ord(c) < 127):
            result.append(ord(c))
        else:
           warn('this ascii char not yet implemented in zscii: '+str(c)+' / '+str(ord(c)))
           result.append(ord('?'))
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
                msg = 'malformed prop size byte: '+bin(size_byte)
                msg += ' - first_byte:'+bin(first_byte)
                msg += ' - prop_ptr:'+hex(prop_ptr)
                err(msg)
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
    warn('   ',obj,'-',get_obj_str(env, obj)+':')
    ptr = get_prop_list_start(env, obj)
    while env.u8(ptr):
        num = get_prop_num(env, ptr)
        size = get_prop_size(env, ptr)
        data_ptr = get_prop_data_ptr(env, ptr)
        warn('    prop #',num,' - size',size, end='')
        for i in xrange(size):
            warn('   ',hex(env.u8(data_ptr+i)), end='')
        warn()
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

def parse_call_header(env, call_addr):
    num_locals = env.u8(call_addr)

    if num_locals > 15:
        err('calling a non-function (more than 15 local vars)')

    if env.hdr.version < 5:
        locals_ptr = call_addr + 1
        locals = []
        for i in xrange(num_locals):
            locals.append(env.u16(locals_ptr))
            locals_ptr += 2
        code_ptr = locals_ptr
    else:
        locals = [0] * num_locals
        code_ptr = call_addr + 1

    return locals, code_ptr

def fill_text_buffer(env, user_input, text_buffer):

    text_buf_len = env.u8(text_buffer)
    if text_buf_len < 2:
        err('read error: malformed text buffer')

    text_buf_ptr = text_buffer + 1

    if env.hdr.version >= 5:
        # input may already exist, may have to append to it
        if env.u8(text_buf_ptr):
            text_buf_ptr += env.u8(text_buf_ptr)+1
        else:
            text_buf_ptr += 1

    i = 0
    max_len = text_buf_len-(text_buf_ptr-text_buffer)
    while i < min(len(user_input), max_len):
        env.write8(text_buf_ptr + i, user_input[i])
        i += 1

    if env.hdr.version >= 5:
        env.write8(text_buffer + 1, (text_buf_ptr+i)-text_buffer-2)
    else:
        # the below is why I can't use a python for loop
        # (it wouldn't set i properly on 0-char input)
        env.write8(text_buf_ptr + i, 0)

def get_used_tbuf_len(env, text_buffer):
    if env.hdr.version >= 5:
        return env.mem[text_buffer + 1]
    else:
        ptr = text_buffer+1
        while env.u8(ptr):
            ptr += 1
        return ptr - text_buffer - 1

def get_text_scan_ptr(env, text_buffer):
    if env.hdr.version < 5:
        return text_buffer + 1
    else:
        return text_buffer + 2

def clip_word_list(env, words):
    if env.hdr.version <= 3:
        MAX_WORD_LEN = 6
    else:
        MAX_WORD_LEN = 9
    for i in xrange(len(words)):
        if len(words[i]) > MAX_WORD_LEN:
            words[i] = words[i][:MAX_WORD_LEN]
    return words

def handle_parse(env, text_buffer, parse_buffer, dict_base=0, skip_unknown_words=0):

    used_tbuf_len = get_used_tbuf_len(env, text_buffer)
    parse_buf_len = env.u8(parse_buffer)
    if parse_buf_len < 1:
        err('read error: malformed parse buffer')

    word_separators = []
    if dict_base == 0:
        dict_base = env.hdr.dict_base
    num_word_seps = env.u8(dict_base)
    for i in xrange(num_word_seps):
        word_separators.append(env.u8(dict_base+1+i))

    word = []
    words = []
    word_locs = []
    word_len = 0
    word_lens = []
    scan_ptr = get_text_scan_ptr(env, text_buffer)
    for i in xrange(used_tbuf_len):

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

    words = clip_word_list(env, words)

    # limit to parse_buf_len (which is num words)
    words = words[:parse_buf_len]
    word_locs = word_locs[:parse_buf_len]
    word_lens = word_lens[:parse_buf_len]

    # HEY THIS IS SUB-OPTIMAL!
    # Actual system should be:
    # 1) Convert words to packed Z-Chars
    # 2) Truncate at correct # bytes
    # 3) Do numerical compare against dict
    #    * this can be a binary search for read() opcodes
    #    * but dictionaries for tokenize() can be unsorted
    #       * so maybe just do regular compare always
    #          * if speed is never an issue these days
    #
    # 1) and 2) are also necessary for correctness.
    # Dict entries can have half a byte of a 2-byte
    # 10-bit ZSCII char that was truncated in the
    # entry creation process. That truncation should
    # be recreated on user input to match those chars.

    dict_base = env.hdr.dict_base
    num_word_seps = env.u8(dict_base)

    entry_length = env.u8(dict_base+1+num_word_seps)
    num_entries = env.u16(dict_base+1+num_word_seps+1)
    # this can be negative to signify dictionary is unsorted
    num_entries = abs(num_entries)
    entries_start = dict_base+1+num_word_seps+1+2

    env.write8(parse_buffer+1, len(words))
    parse_ptr = parse_buffer+2
    for word,wloc,wlen in zip(words, word_locs, word_lens):
        wordstr = ''.join(map(chr, word))
        dict_addr = 0
        for i in xrange(num_entries):
            entry_addr = entries_start+i*entry_length
            if match_dict_entry(env, entry_addr, wordstr):
                dict_addr = entry_addr
                break
        if dict_addr != 0 or skip_unknown_words == 0:
            env.write16(parse_ptr, dict_addr)
            env.write8(parse_ptr+2, wlen)
            env.write8(parse_ptr+3, wloc)
        parse_ptr += 4

def match_dict_entry(env, entry_addr, wordstr):
    if env.hdr.version <= 3:
        entry = [env.u16(entry_addr),
                 env.u16(entry_addr+2)]
    else:
        entry = [env.u16(entry_addr),
                 env.u16(entry_addr+2),
                 env.u16(entry_addr+4)]
    entry_unpacked = unpack_string(env, entry, warn_unknown_char=False)
    return wordstr == entry_unpacked

# not based on z-version, but here for convenience
def read_packed_string(env, addr):
    packed_string = []
    while True:
        word = env.u16(addr)
        packed_string.append(word)
        if word & 0x8000:
            break
        addr += 2
    return packed_string
