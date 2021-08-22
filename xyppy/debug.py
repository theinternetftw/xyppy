from __future__ import print_function
import sys

DBG = 0

# just do print()'s functionality (for now?)
def warn(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def err(*args, **kwargs):
    print('\nerror:', *args, file=sys.stderr, **kwargs)
    sys.exit(1)

