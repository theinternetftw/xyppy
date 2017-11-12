import sys
import urllib2

from debug import err
from zenv import Env, step
import blorb
import ops
import term

def main():
    if len(sys.argv) != 2:
        print('usage examples:')
        print('    python '+sys.argv[0]+' STORY_FILE.z5')
        print('    python '+sys.argv[0]+' http://example.com/STORY_FILE.z5')
        sys.exit(1)

    url = sys.argv[1]
    if any(map(url.startswith, ['http://', 'https://', 'ftp://'])):
        f = urllib2.urlopen(url)
        mem = f.read()
        f.close()
    else:
        with open(url, 'rb') as f:
            mem = f.read()
    if blorb.is_blorb(mem):
        mem = blorb.get_code(mem)
    env = Env(mem)

    if env.hdr.version not in [3,4,5,7,8]:
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
