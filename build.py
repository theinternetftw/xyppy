#! /usr/bin/env python

import os
import zipfile
import StringIO

package_dir = 'xyppy'
python_directive = '#!/usr/bin/env python'

packed = StringIO.StringIO()
packed_writer = zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED)

for fname in os.listdir(package_dir):
    fpath = os.path.join(package_dir, fname)
    if os.path.isfile(fpath):
        packed_writer.write(fpath, fname)
packed_writer.close()

with open(package_dir+'.py', 'wb') as f:
    f.write(python_directive + '\n')
    f.write(packed.getvalue())
