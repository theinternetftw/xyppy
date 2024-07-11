from __future__ import print_function

import argparse
import sys

try:
    from xyppy.debug import err
except ImportError:
    print('error: must either build xyppy into a standalone file, or run xyppy as a module, e.g. "python -m xyppy"')
    sys.exit(1)

from xyppy import zenv, blorb, ops, term
import urllib.request

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
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'xyppy/0.0.0')
        f = urllib.request.urlopen(req)
        mem = f.read()
        f.close()
    else:
        try:
            with open(url, 'rb') as f:
                mem = f.read()
        except IOError as e:
            err('could not load file:', e)

    # TODO: get this by inspecting data (using blorb desigs for now)
    vm_type = b'ZCOD'

    if blorb.is_blorb(mem):
        codeChunk = blorb.get_code_chunk(mem)
        if not codeChunk:
            err('no runnable game code found in blorb file')
        mem = codeChunk.data
        vm_type = codeChunk.name

    if vm_type == b'ZCOD':
        run_zmach(mem, args)
    elif vm_type == b'GLUL':
        run_gmach(mem, args)
    else:
        err('unknown game vm type: {}'.format(repr(vm_type)))


def run_zmach(mem, args):
    env = zenv.Env(mem, args)
    if env.hdr.version not in [1,2,3,4,5,7,8]:
        err('unsupported z-machine version: '+str(env.hdr.version))

    term.init()
    env.screen.first_draw()
    ops.setup_opcodes(env)
    try:
        while True:
            zenv.step(env)
    except KeyboardInterrupt:
        pass

def run_gmach(mem, args):
    err('glulx games not yet supported')

if __name__ == '__main__':
    main()
