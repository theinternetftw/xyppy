from __future__ import print_function

import sys
import struct

from xyppy.iff import Chunk, FormChunk
from xyppy.debug import err

class Resource(object):
    def __init__(self, usage, number, start):
        self.usage = usage
        self.number = number
        self.start = start

class RIdxChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        num_resources = struct.unpack_from('>I', chunk.data)[0]
        obj.resources = []
        for i in range(num_resources):
            usage, number, start = struct.unpack_from('>4sII', chunk.data[4+i*12:])
            obj.resources.append(Resource(usage, number, start))
        return obj

def is_blorb(fdata):
    return fdata[:4] == b'FORM' and fdata[8:12] == b'IFRS'

def get_code_chunk(filedata):
    formChunk = FormChunk.from_chunk(Chunk.from_data(filedata))
    for chunk in formChunk.chunks:
        if chunk.name == b'RIdx':
            rIdxChunk = RIdxChunk.from_chunk(chunk)
            for r in rIdxChunk.resources:
                if r.usage == b'Exec' and r.number == 0:
                    codeChunk = Chunk.from_data(filedata[r.start:])
                    return codeChunk
    return None

"""
def get_type(formChunk, usage_type):
    found = []
    for chunk in formChunk.chunks:
        if chunk.name == b'RIdx':
            for r in rIdxChunk.resources:
                if r.usage == usage_type:
                    found.append(Chunk.from_data(fdata[r.start:]))
    return found

def print_info(filename):
    with open(filename, 'rb') as f:
        fdata = f.read()
        formChunk = FormChunk.from_chunk(Chunk.from_data(fdata))
        for chunk in formChunk.chunks:
            print(chunk.name, chunk.size)
            if chunk.name == b'RIdx':
                rIdxChunk = RIdxChunk.from_chunk(chunk)
                for r in rIdxChunk.resources:
                    print('\t', r.usage, r.number, r.start)
                    print('\t\t', Chunk.from_data(fdata[r.start:]))
            elif chunk.name == b'IFmd':
                print(chunk.data)
        print()

for fname in sys.argv[1:]:
    print(fname[fname.rfind('/'):])
    print_info(fname)
"""
