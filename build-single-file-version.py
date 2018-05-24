#! /usr/bin/env python

import os
import stat
import zipfile
import StringIO

package_dir = 'xyppy'
python_directive = '#!/usr/bin/env python'

packed = StringIO.StringIO()
packed_writer = zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED)
for fname in os.listdir(package_dir):
    fpath = os.path.join(package_dir, fname)
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
    f.write(python_directive + '\n')
    f.write(packed.getvalue())
os.chmod(pyfile, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
