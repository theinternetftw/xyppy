from __future__ import print_function

import argparse
import sys

try:
    from xyppy.debug import err
except ImportError:
    print('error: must either build xyppy into a standalone file, or run xyppy as a module, e.g. "python -m xyppy"')
    sys.exit(1)

from xyppy.zenv import Env, step
import xyppy.blorb as blorb
import xyppy.ops as ops
import xyppy.term as term
import xyppy.six.moves.urllib as urllib

def main():

    if len(sys.argv) < 2:
        # I prefer a non-auto-gen'd zero arg screen
        if sys.argv[0].endswith('__main__.py'):
            name = '-m xyppy'
        else:
            name = sys.argv[0]
        print('usage examples:')
        print('    python '+name+' STORY_FILE.z5')
        print('    python '+name+' http://example.com/STORY_FILE.z5')
        print()
        print('    for more, try --help')
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-slow-scroll', action='store_true', help='remove the artificial scrolling delay')
    parser.add_argument('STORY_FILE_OR_URL')
    args = parser.parse_args()

    url = args.STORY_FILE_OR_URL
    if any(map(url.startswith, ['http://', 'https://', 'ftp://'])):
        f = urllib.request.urlopen(url)
        mem = f.read()
        f.close()
    else:
        try:
            with open(url, 'rb') as f:
                mem = f.read()
        except IOError as e:
            err('could not load file:', e)
    if blorb.is_blorb(mem):
        mem = blorb.get_code(mem)
    env = Env(mem, args)

    if env.hdr.version not in [1,2,3,4,5,7,8]:
        err('unsupported z-machine version: '+str(env.hdr.version))

    term.init(env)
    env.screen.first_draw()
    ops.setup_opcodes(env)
    try:
        while True:
            step(env)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
