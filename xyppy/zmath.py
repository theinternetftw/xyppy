def to_signed_word(word):
    if word & 0x8000:
        return (word & 0x7fff) - 0x8000
    return word & 0xffff
