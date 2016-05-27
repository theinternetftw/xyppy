from __future__ import print_function
import sys

# just do print()'s functionality (for now?)
def warn(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def err(msg):
    sys.stderr.write('error: '+msg+'\n')
    sys.exit()

