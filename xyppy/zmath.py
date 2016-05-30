def to_signed_word(word):
    if word & 0x8000:
        return -((~word & 0xffff)+1)
    return word

def to_signed_char(char):
    if char & 0x80:
        return -((~char & 0xff)+1)
    return char

