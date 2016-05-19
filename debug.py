import sys

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

    # for the same weird issue as mentioned in flush()
    msg = msg.replace('\n','\r\n')

    sys.stderr.write(msg)

def err(msg):
    sys.stderr.write('error: '+msg+'\n')
    sys.exit()

