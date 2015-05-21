import sys
import struct

from iff import Chunk, FormChunk
from quetzal import IFhdChunk
from txt import err, warn

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
    return fdata[:4] == 'FORM' and fdata[8:12] == 'IFRS'

def get_code(filedata):
    formChunk = FormChunk.from_chunk(Chunk.from_data(filedata))
    for chunk in formChunk.chunks:
        if chunk.name == 'RIdx':
            rIdxChunk = RIdxChunk.from_chunk(chunk)
            for r in rIdxChunk.resources:
                if r.usage == 'Exec' and r.number == 0:
                    codeChunk = Chunk.from_data(filedata[r.start:])
                    if codeChunk.name == 'ZCOD':
                        return codeChunk.data
    err('no ZCOD chunk found in blorb resource index')

"""
def get_type(formChunk, usage_type):
    found = []
    for chunk in formChunk.chunks:
        if chunk.name == 'RIdx':
            for r in rIdxChunk.resources:
                if r.usage == usage_type:
                    found.append(Chunk.from_data(fdata[r.start:]))
    return found

def print_info(filename):
    with open(filename, 'rb') as f:
        fdata = f.read()
        formChunk = FormChunk.from_chunk(Chunk.from_data(fdata))
        for chunk in formChunk.chunks:
            print chunk.name, chunk.size
            if chunk.name == 'RIdx':
                rIdxChunk = RIdxChunk.from_chunk(chunk)
                for r in rIdxChunk.resources:
                    print '\t', r.usage, r.number, r.start
                    print '\t\t', Chunk.from_data(fdata[r.start:])
            elif chunk.name == 'IFmd':
                print chunk.data
        print

for fname in sys.argv[1:]:
    print fname[fname.rfind('/'):]
    print_info(fname)
"""
