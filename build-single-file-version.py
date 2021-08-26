#! /usr/bin/env python

import os
import stat
import zipfile

try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

package_dir = 'xyppy'
python_directive = '#!/usr/bin/env python'

packed = StringIO()
packed_writer = zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED)
for dirpath, dirnames, filenames in os.walk(package_dir):
    for fname in filenames:
        fpath = os.path.join(dirpath, fname)
        if os.path.isfile(fpath):
            packed_writer.write(fpath)
packed_writer.writestr('__main__.py', '''
from xyppy import __main__
if __name__ == '__main__':
    __main__.main()
''')
packed_writer.close()

pyfile = package_dir + '.py'
with open(pyfile, 'wb') as f:
    shebang = bytes((python_directive + '\n').encode('ascii'))
    f.write(shebang)
    f.write(packed.getvalue())
os.chmod(pyfile, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
