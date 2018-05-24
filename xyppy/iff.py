import struct

def packHdr(chunk):
    return struct.pack('>4sI', chunk.name, chunk.size)

class Chunk(object):
    @classmethod
    def from_data(cls, data):
        obj = cls()
        obj.name, obj.size = struct.unpack('>4sI', data[:8])
        obj.data = data[8:8+obj.size]
        return obj
    def from_name_and_data(cls, name, data):
        obj = cls()
        obj.name = name
        obj.size = len(data)
        obj.data = data
        return obj
    def __str__(self):
        return self.name + ' - ' + str(self.size)
    def pack(self):
        return packHdr(self) + self.data

def splitChunks(data):
    chunks = []
    while data:
        chunk = Chunk.from_data(data)
        size = chunk.size
        if size & 1:
            size += 1 #extra pad byte if odd size
        data = data[8+size:]
        chunks.append(chunk)
    return chunks

def packChunks(chunks):
    pchunks = bytearray([])
    for chunk in chunks:
        pchunk = bytearray(chunk.pack())
        if chunk.size & 1:
            pchunk.append(0) #extra pad byte if odd size
        pchunks.extend(pchunk)
    return bytes(pchunks)

class FormChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size = chunk.name, chunk.size
        obj.subname = chunk.data[:4]
        obj.data = chunk.data[4:]
        obj.chunks = splitChunks(obj.data)
        return obj
    @classmethod
    def from_chunk_list(cls, subname, chunks):
        obj = cls()
        obj.name = b'FORM'
        obj.subname = subname
        obj.chunks = chunks
        return obj
    def pack(self):
        data = packChunks(self.chunks)
        self.size = len(data) + 4
        return packHdr(self) + self.subname + data

