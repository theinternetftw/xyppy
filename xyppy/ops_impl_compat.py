from xyppy.debug import warn, err, DBG
import xyppy.term as term

def get_cursor_loc_after_erase(env, cleared_window):
    if cleared_window == 0:
        if env.hdr.version >= 5:
            return env.top_window_height, 0
        else:
            return env.hdr.screen_height_units - 1, 0
    else:
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
        return env.mem[obj_addr+4]
    else:
        return env.u16(obj_addr+6)

def get_sibling_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        return env.mem[obj_addr+5]
    else:
        return env.u16(obj_addr+8)

def get_child_num(env, obj):
    obj_addr = get_obj_addr(env, obj)
    if env.hdr.version < 4:
        return env.mem[obj_addr+6]
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
Default_A2 = ' \n0123456789.,!?_#\'"/\\-:()'

Default_A2_for_z1 = ' 0123456789.,!?_#\'"/\\<-:()'

#needs_compat_pass (i think only for v1/v2)
def unpack_string(env, packed_text):

    split_text = []
    for word in packed_text:
        split_text += [word >> 10 & 0x1f,
                       word >> 5 & 0x1f,
                       word & 0x1f]

    if env.hdr.version >= 5 and env.hdr.alpha_tab_base:
        base = env.hdr.alpha_tab_base
        A0 = ''.join(map(chr, list(env.mem[base+0*26:base+1*26])))
        A1 = ''.join(map(chr, list(env.mem[base+1*26:base+2*26])))
        A2 = ''.join(map(chr, list(env.mem[base+2*26:base+3*26])))
    else:
        A0 = Default_A0
        A1 = Default_A1
        A2 = Default_A2

    if env.hdr.version == 1:
        A2 = Default_A2_for_z1

    shiftTable = {
            2: {A0:A1, A1:A2, A2:A0},
            3: {A0:A2, A1:A0, A2:A1},

            4: {A0:A1, A1:A2, A2:A0},
            5: {A0:A2, A1:A0, A2:A1},
    }

    text = []
    currentAlphabet = A0
    lastAlphabet = A0
    tempShift = 0
    abbrevShift = 0
    current_10bit = 0
    mode = 'NONE'
    for char in split_text:
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
            text += zscii_to_ascii(env, [current_10bit])
        elif char == 0:
            text.append(' ')
        elif char == 6 and currentAlphabet == A2: # override any custom alpha with escape seq start
            mode = '10BIT_HIGH'
        elif env.hdr.version > 1 and char == 7 and currentAlphabet == A2: # override any custom alpha with newline
            text.append('\n')
        elif env.hdr.version < 3:
            if char == 1:
                if env.hdr.version == 1:
                    text.append('\n')
                else:
                    abbrevShift = char
            elif char in [2,3,4,5]:
                lastAlphabet = currentAlphabet
                currentAlphabet = shiftTable[char][currentAlphabet]
                if char in [2,3]:
                    tempShift = 1
                else:
                    tempShift = 0 # don't unshift when shift locking, even if preceded by tempShift
            else:
                text.append(currentAlphabet[char-6])
        else:
            if char in [1,2,3]:
                abbrevShift = char
            elif char == 4:
                currentAlphabet = A1
                tempShift = 1
            elif char == 5:
                currentAlphabet = A2
                tempShift = 1
            else:
                text.append(currentAlphabet[char-6])

        if tempShift == 2:
            if env.hdr.version < 3:
                currentAlphabet = lastAlphabet
            else:
                currentAlphabet = A0
            tempShift = 0
        elif tempShift > 0:
            tempShift += 1

    return ''.join(text)

def make_dict_string(env, text):

    if env.hdr.version >= 5 and env.hdr.alpha_tab_base:
        base = env.hdr.alpha_tab_base
        A0 = ''.join(map(chr, list(env.mem[base+0*26:base+1*26])))
        A1 = ''.join(map(chr, list(env.mem[base+1*26:base+2*26])))
        A2 = ''.join(map(chr, list(env.mem[base+2*26:base+3*26])))
    else:
        A0 = Default_A0
        A1 = Default_A1
        A2 = Default_A2

    if env.hdr.version == 1:
        A2 = Default_A2_for_z1

    # TODO: S 3.7.1, which expects 4,5 for len-2 shift
    # seqs (not full lock) and works this way only for
    # dict lookups? Still unclear to me, can find no
    # examples of this.

    if env.hdr.version <= 3:
        KEY_LEN = 6
    else:
        KEY_LEN = 9
    text = text[:KEY_LEN] # will truncate again later, but shortens the loop

    ztext = []
    for char in text:
        if char in A0:
            ztext.append(A0.index(char)+6)
        elif char in A1:
            # only can be custom alphabets, no version 1/2 code needed
            ztext.append(4)
            ztext.append(A1.index(char)+6)
        elif char in A2 and A2.index(char) != 0 and (env.hdr.version == 1 or A2.index(char) != 1):
            if env.hdr.version <= 2:
                ztext.append(3)
            else:
                ztext.append(5)
            ztext.append(A2.index(char)+6)
        else:
            # 10-bit ZSCII (only 8 bits ever used)
            ztext.append(ord(char) >> 5) # top 3 bits
            ztext.append(ord(char) & 0x1f) # bottom 5 bits

    ztext = ztext[:KEY_LEN] # truncating multi-byte chars here
    while len(ztext) < KEY_LEN:
        ztext.append(5)

    packed_text = []
    for i in range(0, len(ztext), 3):
        c, c1, c2 = ztext[i:i+3]
        packed_text.append((c << 10) | (c1 << 5) | c2)
    packed_text[-1] |= 0x8000
    return packed_text

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

# non-standardized second table, just for xyppy
# TODO: add backwards single/double quotes, etc.
extra_unicode_fallback_table = {
    0x2014: '-'
}

def to_unicode_fallback(c):
    if c in default_unicode_fallback_table:
        return default_unicode_fallback_table[c]
    if c in extra_unicode_fallback_table:
        return extra_unicode_fallback_table[c]
    return '?'

def _make_to_unicode():
    try:
        # python 3 check
        chr(8212)
        return chr
    except ValueError:
        return unichr
to_unicode = _make_to_unicode()

def _make_translate_unicode():
    if term.supports_unicode():
        return to_unicode
    else:
        return to_unicode_fallback
translate_unicode = _make_translate_unicode()

default_unicode_table = {}
default_unicode_fallback_table = {}

def build_default_unicode_tables(*triples):
    for triple in triples:
        znum, unum, fallback = triple
        default_unicode_table[znum] = unum
        default_unicode_fallback_table[unum] = fallback

build_default_unicode_tables(
    (155, 0xe4, "ae"), (156, 0xf6, "oe"), (157, 0xfc, "ue"),
    (158, 0xc4, "Ae"), (159, 0xd6, "Oe"), (160, 0xdc, "Ue"),
    (161, 0xdf, "ss"), (162, 0xbb, ">>"), (163, 0xab, "<<"),
    (164, 0xeb, "e"), (165, 0xef, "i"), (166, 0xff, "y"),
    (167, 0xcb, "E"), (168, 0xcf, "I"),
    (169, 0xe1, "a"), (170, 0xe9, "e"), (171, 0xed, "i"), (172, 0xf3, "o"), (173, 0xfa, "u"), (174, 0xfd, "y"),
    (175, 0xc1, "A"), (176, 0xc9, "E"), (177, 0xcd, "I"), (178, 0xd3, "O"), (179, 0xda, "U"), (180, 0xdd, "Y"),
    (181, 0xe0, "a"), (182, 0xe8, "e"), (183, 0xec, "i"), (184, 0xf2, "o"), (185, 0xf9, "u"),
    (186, 0xc0, "A"), (187, 0xc8, "E"), (188, 0xcc, "I"), (189, 0xd2, "O"), (190, 0xd9, "U"),
    (191, 0xe2, "a"), (192, 0xea, "e"), (193, 0xee, "i"), (194, 0xf4, "o"), (195, 0xfb, "u"),
    (196, 0xc2, "A"), (197, 0xca, "E"), (198, 0xce, "I"), (199, 0xd4, "O"), (200, 0xdb, "U"),
    (201, 0xe5, "a"), (202, 0xc5, "A"), (203, 0xf8, "o"), (204, 0xd8, "O"),
    (205, 0xe3, "a"), (206, 0xf1, "n"), (207, 0xf5, "o"),
    (208, 0xc3, "A"), (209, 0xd1, "N"), (210, 0xd5, "O"),
    (211, 0xe6, "ae"), (212, 0xc6, "AE"), (213, 0xe7, "c"), (214, 0xc7, "C"),
    (215, 0xfe, "th"), (216, 0xf0, "th"), (217, 0xde, "Th"), (218, 0xd0, "Th"),
    (219, 0xa3, "L"),
    (220, 0x153, "oe"), (221, 0x152, "OE"),
    (222, 0xa1, "!"), (223, 0xbf, "?")
)

#std: 3.8
#needs_compat_pass
def zscii_to_ascii(env, clist):
    result = []
    for c in clist:
        if c == 0:
            # 0 == no effect in zscii (S 3.8.2.1)
            continue
        if c == ord('\r'):
            result.append('\n')
        elif c >= 32 and c <= 126:
            result.append(chr(c))
        elif c >= 155 and c <= 251:
            if env.hdr.unicode_tab_base:
                unitable_len = env.mem[env.hdr.unicode_tab_base]
                if (c-155) < len(unitable_len):
                    result.append(translate_unicode(env.u16(env.hdr.unicode_tab_base+(c-155))))
                else:
                    # err('sent unitable zscii that doesn\'t fit in custom table!', c-155, 'vs', unitable_len)
                    result.append('?')
            else:
                if c in default_unicode_table:
                    result.append(translate_unicode(default_unicode_table[c]))
                else:
                    # err('sent unitable zscii that\'s not in default table', c)
                    result.append('?')
        elif (c >= 0 and c <= 12) or (c >= 14 and c <= 31) or (c >= 127 and c <= 154) or (c >= 252):
            # err('sent zscii to print that\'s not defined for output!', c)
            pass
    return ''.join(result)

# std: 3.8
def ascii_to_zscii(string):
    result = []
    i = 0
    while i < len(string):
        c = string[i]
        if c == '\n':
            result.append(ord('\r'))
        # NOTE: gargoyle just ignores the tab key, S 3.8.2.3 says
        # output only. But since I want to keep expected tab behavior,
        # I make this compromise.
        elif c == '\t':
            result.append(ord(' '))
        elif c in ('\r','\b') or (len(c) == 1 and ord(c) > 31 and ord(c) < 127):
            result.append(ord(c))
            # TODO (?): unicode for input (translate codes to zscii using the unicode table(s))
            # TODO: keypad digits
        elif c == '\x1b':
            esc_key_tbl = {
                # arrow keys
                '[A': 129, '[B': 130, '[C': 132, '[D':131,
                # fkeys
                'OP': 133, 'OQ': 134, 'OR': 135, 'OS': 136, '[15~': 137,
                '[17~': 138, '[18~': 139, '[19~' :140, '[20~': 141,
                '[21~': 142, '[23~': 143, '[24~': 144,
            }
            found = False
            next_few = string[i+1:i+5]
            for seq in esc_key_tbl:
                if next_few.startswith(seq):
                    result.append(esc_key_tbl[seq])
                    i += len(seq)
                    found = True
                    break
            if not found:
                result.append(ord(c))
        else:
            if DBG:
                term.puts('\nthis ascii char not yet implemented in zscii: '+str(c)+' / '+str(ord(c)) + '\n')
                term.puts('\nHIT ENTER TO CONTINUE\n')
                term.getch_or_esc_seq()
            result.append(ord('?'))
        i += 1
    return result

# returns the first sizenum_ptr
def get_prop_list_start(env, obj):
    if env.hdr.version < 4:
        offset = 7
    else:
        offset = 12
    prop_tab_addr = env.u16(get_obj_addr(env, obj)+offset)
    obj_text_len_words = env.mem[prop_tab_addr]
    return prop_tab_addr + 1 + 2*obj_text_len_words

def get_prop_size(env, sizenum_ptr):
    if env.hdr.version < 4:
        return (env.mem[sizenum_ptr] >> 5) + 1
    else:
        first_byte = env.mem[sizenum_ptr]
        if first_byte & 128:
            size_byte = env.mem[sizenum_ptr+1]
            if not (size_byte & 128):
                msg = 'malformed prop size byte: '+bin(size_byte)
                msg += ' - first_byte:'+bin(first_byte)
                msg += ' - sizenum_ptr:'+hex(sizenum_ptr)
                err(msg)
            return (size_byte & 63) or 64 # zero len == 64
        if first_byte & 64:
            return 2
        return 1

def get_prop_num(env, sizenum_ptr):
    num_byte = env.mem[sizenum_ptr]
    if env.hdr.version < 4:
        return num_byte & 31
    else:
        return num_byte & 63

def get_prop_data_ptr(env, sizenum_ptr):
    if env.hdr.version < 4:
        return sizenum_ptr+1
    else:
        if env.mem[sizenum_ptr] & 128:
            return sizenum_ptr+2
        return sizenum_ptr+1

def get_prop_data_ptr_from_obj(env, obj, prop_num):
    sizenum_ptr = get_prop_list_start(env, obj)
    while env.mem[sizenum_ptr]:
        num = get_prop_num(env, sizenum_ptr)
        data_ptr = get_prop_data_ptr(env, sizenum_ptr)
        if num == prop_num:
            return data_ptr
        sizenum_ptr = data_ptr + get_prop_size(env, sizenum_ptr)
    return 0 # not found

def get_sizenum_ptr(env, prop_data_ptr):
    if env.hdr.version < 4:
        return prop_data_ptr-1
    else:
        if env.mem[prop_data_ptr-1] & 128:
            return prop_data_ptr-2
        return prop_data_ptr-1

def print_prop_list(env, obj):
    warn('   ',obj,'-',get_obj_str(env, obj)+':')
    ptr = get_prop_list_start(env, obj)
    while env.mem[ptr]:
        num = get_prop_num(env, ptr)
        size = get_prop_size(env, ptr)
        data_ptr = get_prop_data_ptr(env, ptr)
        warn('    prop #',num,' - size',size, end='')
        for i in range(size):
            warn('   ',hex(env.mem[data_ptr+i]), end='')
        warn()
        ptr = data_ptr + size

def parse_call_header(env, call_addr):
    num_locals = env.mem[call_addr]

    if num_locals > 15:
        err('calling a non-function (more than 15 local vars)')

    if env.hdr.version < 5:
        locals_ptr = call_addr + 1
        locals = []
        for i in range(num_locals):
            locals.append(env.u16(locals_ptr))
            locals_ptr += 2
        code_ptr = locals_ptr
    else:
        locals = [0] * num_locals
        code_ptr = call_addr + 1

    return locals, code_ptr

def get_text_buffer_as_str(env, text_buffer):

    text_buf_len = env.mem[text_buffer]
    if text_buf_len < 2:
        err('read error: malformed text buffer')

    text_buf_ptr = text_buffer + 1

    # does input exist?
    if env.hdr.version >= 5 and env.mem[text_buf_ptr]:
        input_len = env.mem[text_buf_ptr]
        text_buf_ptr += 1
        chars = env.mem[text_buf_ptr:text_buf_ptr+input_len]
        return ''.join(map(chr, chars))
    return ''

def fill_text_buffer(env, user_input, text_buffer):

    text_buf_len = env.mem[text_buffer]
    if text_buf_len < 2:
        err('read error: malformed text buffer')

    text_buf_ptr = text_buffer + 1

    # TODO: make sure I'm interpreting this right.
    # Finding in test suites that you should be able
    # to edit the prefilled text, despite spec seeming
    # to say that any new input goes after prefilled
    # input. Maybe that directive includes ^H's?
    if env.hdr.version >= 5:
        text_buf_ptr += 1

    max_len = text_buf_len-(text_buf_ptr-text_buffer)
    text_len = min(len(user_input), max_len)
    for i in range(text_len):
        env.write8(text_buf_ptr, user_input[i])
        text_buf_ptr += 1

    if env.hdr.version >= 5:
        env.write8(text_buffer + 1, text_buf_ptr-text_buffer-2)
    else:
        env.write8(text_buf_ptr, 0)

def get_used_tbuf_len(env, text_buffer):
    if env.hdr.version >= 5:
        return env.mem[text_buffer + 1]
    else:
        ptr = text_buffer+1
        while env.mem[ptr]:
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
    for i in range(len(words)):
        if len(words[i]) > MAX_WORD_LEN:
            words[i] = words[i][:MAX_WORD_LEN]
    return words

def handle_parse(env, text_buffer, parse_buffer, dict_base=0, skip_unknown_words=0):

    used_tbuf_len = get_used_tbuf_len(env, text_buffer)
    parse_buf_len = env.mem[parse_buffer]
    if parse_buf_len < 1:
        err('read error: malformed parse buffer')

    word_separators = []
    if dict_base == 0:
        dict_base = env.hdr.dict_base
    num_word_seps = env.mem[dict_base]
    for i in range(num_word_seps):
        word_separators.append(env.mem[dict_base+1+i])

    word = []
    words = []
    word_locs = []
    word_len = 0
    word_lens = []
    scan_ptr = get_text_scan_ptr(env, text_buffer)
    for i in range(used_tbuf_len):

        c = env.mem[scan_ptr]

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

    # NOTE: This could be a binary search for read() opcodes,
    # but dictionaries for tokenize() can be unsorted. So maybe
    # just always do a linear search if speed is never an issue
    # these days?

    dict_base = env.hdr.dict_base
    num_word_seps = env.mem[dict_base]

    entry_length = env.mem[dict_base+1+num_word_seps]
    num_entries = env.u16(dict_base+1+num_word_seps+1)
    # this can be negative to signify dictionary is unsorted
    num_entries = abs(num_entries)
    entries_start = dict_base+1+num_word_seps+1+2

    env.write8(parse_buffer+1, len(words))
    parse_ptr = parse_buffer+2
    for word,wloc,wlen in zip(words, word_locs, word_lens):

        wordstr = ''.join(map(chr, word))
        packed_word = make_dict_string(env, wordstr)

        dict_addr = 0
        for i in range(num_entries):
            entry_addr = entries_start+i*entry_length
            if match_dict_entry(env, entry_addr, packed_word):
                dict_addr = entry_addr
                break
        if dict_addr != 0 or skip_unknown_words == 0:
            env.write16(parse_ptr, dict_addr)
            env.write8(parse_ptr+2, wlen)
            env.write8(parse_ptr+3, wloc)
        parse_ptr += 4

def match_dict_entry(env, entry_addr, packed_word):
    if env.hdr.version <= 3:
        entry = [env.u16(entry_addr),
                 env.u16(entry_addr+2)]
    else:
        entry = [env.u16(entry_addr),
                 env.u16(entry_addr+2),
                 env.u16(entry_addr+4)]
    return packed_word == entry

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
