import sys

def wwrap(text, width):
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
            lines = lines[:i] + [line[:last_space],line[last_space+1:]] + lines[i+1:]
        else:
            lines = lines[:i] + [line[:width+1], line[width+1:]] + lines[i+1]
        idxs = get_index_of_long_line()
    return '\n'.join(lines)

def write(env, text):
    width = env.hdr.screen_width_units or 80
    env.output_buffer += text
    if '\n' in env.output_buffer or not env.use_buffered_output:
        wrapped_text = wwrap(env.output_buffer, width)
        sys.stdout.write(wrapped_text)
        env.output_buffer = ''

def read_packed_string(env, addr):
    packed_string = []
    while True:
        word = env.u16(addr)
        packed_string.append(word)
        if word & 0x8000:
            break
        addr += 2
    return packed_string

# emulate print()'s functionality (for now?)
def warn(*args, **kwargs):
    if 'sep' not in kwargs:
        kwargs['sep'] = ' '
    if 'end' not in kwargs:
        kwargs['end'] = '\n'
    sep, end = kwargs['sep'], kwargs['end']

    msg = ''
    if args:
        msg += str(args[0])
    for arg in args[1:]:
        msg += sep + str(arg)
    msg += end
    sys.stderr.write(msg)

def err(msg):
    sys.stderr.write('error: '+msg+'\n')
    sys.exit()

