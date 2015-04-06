import sys

# One of what may be many problems with this:
# Assumes text starts at column 0
def wwrap(text, width=80):
    lines = [text]
    idx = lines[-1].find('\n')
    while idx != -1:
        rest = lines.pop()
        lines += [rest[:idx], rest[idx+1:]]
        idx = lines[-1].find('\n')
    def get_index_of_long_line():
        return [i for i in range(len(lines)) if len(lines[i]) > width]
    idxs = get_index_of_long_line()
    while idxs:
        i = idxs[0]
        line = lines[i]
        last_space = line[:width+1].rfind(' ')
        if line != -1:
            lines = lines[:i]+[line[:last_space],line[last_space+1:]]+lines[i+1:]
        else:
            lines = lines[:i]+[line[:width+1], line[width+1:]]+lines[i+1]
        idxs = get_index_of_long_line()
    return '\n'.join(lines)

def read_packed_string(env, addr):
    packed_string = []
    while True:
        word = env.u16(addr)
        packed_string.append(word)
        if word & 0x8000:
            break
        addr += 2
    return packed_string

def warn(msg):
    sys.stderr.write(msg+'\n')

