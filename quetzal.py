import sys
import struct
from iff import Chunk, FormChunk, packHdr

class IFhdChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        obj.release = struct.unpack('>H', chunk.data[:2])[0]
        obj.serial = map(ord, chunk.data[2:8])
        obj.checksum = struct.unpack('>H', chunk.data[8:10])[0]
        obj.pc = struct.unpack('>I', '\0'+chunk.data[10:13])[0]
        return obj
    @classmethod
    def from_env(cls, env):
        obj = cls()
        obj.name = 'IFhd'
        obj.size = 13
        obj.release = env.hdr.release
        obj.serial = ''.join(map(chr, env.hdr.serial))
        obj.checksum = env.hdr.checksum
        if env.hdr.version < 4:
            obj.pc = env.last_pc_branch_var
        else:
            obj.pc = env.last_pc_store_var
        return obj
    def pack(self):
        return (packHdr(self) +
                struct.pack('>H6sH', self.release, self.serial, self.checksum) +
                struct.pack('>I', self.pc)[1:])

def decRLE(mem):
    bigmem = ''
    i = 0
    while i < len(mem):
        bigmem += mem[i]
        if mem[i] == '\0':
            bigmem += '\0' * ord(mem[i+1])
            i += 2
        else:
            i += 1
    return bigmem

def encRLE(mem):
    small_mem = ''
    i = 0
    while i < len(mem):
        small_mem += mem[i]
        if mem[i] == '\0':
            zero_run = 0
            i += 1
            while i < len(mem) and mem[i] == '\0' and zero_run < 255:
                zero_run += 1
                i += 1
            small_mem += chr(zero_run)
        else:
            i += 1
    return small_mem

class CMemChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        obj.mem = decRLE(obj.data)
        obj.compressed = True
        return obj
    @classmethod
    def from_env(cls, env):
        obj = cls()
        obj.name = 'CMem'
        obj.mem = env.mem[:env.hdr.static_mem_base]
        for i in range(len(obj.mem)):
            obj.mem[i] ^= ord(env.orig_mem[i])
        while obj.mem[-1] == 0:
            obj.mem.pop()
        obj.mem = ''.join(map(chr, obj.mem))
        obj.compressed = True
        return obj
    def pack(self):
        packedMem = encRLE(self.mem)
        self.size = len(packedMem)
        return packHdr(self) + packedMem

class UMemChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        obj.mem = obj.data
        obj.compressed = False
        return obj
    @classmethod
    def from_env(cls, env):
        obj = cls()
        obj.name = 'UMem'
        obj.mem = env.mem[:env.hdr.static_mem_base]
        obj.mem= ''.join(map(chr, obj.mem))
        obj.compressed = False
        return obj
    def pack(self):
        self.size = len(self.mem)
        return packHdr(self) + self.mem

# duck-typing compatible with ops_impl's Frame class
class QFrame(object):
    @classmethod
    def from_packed(cls, data):
        obj = cls()
        obj.return_addr = struct.unpack('>I', '\0'+data[:3])[0]
        flags = ord(data[3])
        num_locals = flags & 15
        if flags & 16:
            # discard return val
            obj.return_val_loc = None
        else:
            obj.return_val_loc = ord(data[4])

        # this should never have non-consecutive ones, right?
        # i.e. you can't have arg 3 without having args 1 and 2 (right?)
        args_flag = ord(data[5])
        obj.num_args = 0
        for i in range(7):
            if args_flag >> i:
                obj.num_args += 1

        used_stack_size = struct.unpack('>H', data[6:8])[0]
        obj.locals = []
        for i in range(num_locals):
            addr = 8+i*2
            local = struct.unpack('>H', data[addr:addr+2])[0]
            obj.locals.append(local)
        obj.stack = []
        for i in range(used_stack_size):
            addr = 8+num_locals*2+i*2
            word = struct.unpack('>H', data[addr:addr+2])[0]
            obj.stack.append(word)
        obj.size = 8+num_locals*2+used_stack_size*2
        return obj
    @classmethod
    def from_frame(cls, frame):
        obj = cls()
        obj.return_val_loc = frame.return_val_loc
        obj.return_addr = frame.return_addr
        obj.num_args = frame.num_args
        obj.locals = frame.locals
        obj.stack = frame.stack
        return obj
    def pack(self):
        flags = len(self.locals)
        if self.return_val_loc == None:
            flags |= 16
        args_byte = 2**self.num_args - 1
        return (struct.pack('>I', self.return_addr)[1:] +
                chr(flags) +
                chr(self.return_val_loc or 0) +
                chr(args_byte) +
                packWords([len(self.stack)]) +
                packWords(self.locals) +
                packWords(self.stack))
               
def packWords(words):
    out = ''
    for word in words:
        out += chr(word >> 8) + chr(word & 0xff)
    return out

def getFrames(data):
    frames = []
    while data:
        frame = QFrame.from_packed(data)
        data = data[frame.size:]
        frames.append(frame)
    return frames

class StksChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        obj.frames = getFrames(obj.data)
        return obj
    @classmethod
    def from_env(cls, env):
        obj = cls()
        obj.name = 'Stks'
        obj.frames = [QFrame.from_frame(f) for f in env.callstack]
        return obj
    def pack(self):
        framestr = ''.join([f.pack() for f in self.frames])
        self.size = len(framestr)
        return packHdr(self) + framestr

def read(filename):
    with open(filename) as f:
        formChunk = FormChunk.from_chunk(Chunk.from_data(f.read()))
        for chunk in formChunk.chunks:
            if chunk.name == 'IFhd':
                hdChunk = IFhdChunk.from_chunk(chunk)
            if chunk.name == 'CMem':
                memChunk = CMemChunk.from_chunk(chunk)
            if chunk.name == 'UMem':
                memChunk = UMemChunk.from_chunk(chunk)
            if chunk.name == 'Stks':
                stksChunk = StksChunk.from_chunk(chunk)
    return formChunk.subname, hdChunk, memChunk, stksChunk.frames

def write(env, filename):
    with open(filename, 'w') as f:
        chunks = [IFhdChunk.from_env(env),
                  CMemChunk.from_env(env),
                  StksChunk.from_env(env)]
        formChunk = FormChunk.from_chunk_list('IFZS', chunks)
        f.write(formChunk.pack())

def load_to_env(env, filename):
    try:
        subname, hdrChunk, memChunk, frames = read(filename)
    except IOError as (errno, strerror):
        print 'error reading file: '+strerror
        return False
    except:
        print 'error decoding quetzal save file'
        return False

    if subname != 'IFZS':
        print 'not a quetzal save file'
    if env.hdr.release != hdrChunk.release:
        print 'release doesn\'t match'
    elif env.hdr.serial != hdrChunk.serial:
        print 'serial doesn\'t match'
    elif env.hdr.checksum != hdrChunk.checksum:
        print 'checksum does\'t match'
    else:
        env.reset()
        env.callstack = frames
        if memChunk.compressed:
            memDiff = memChunk.mem
            for i in range(len(memDiff)):
                env.mem[i] ^= ord(memDiff[i])
        else:
            dmLen = len(memChunk.mem)
            env.mem[:dmLen] = memChunk.mem
        env.pc = hdrChunk.pc
        # pc is now in wrong place:
        # must fix based on z version
        # after this func returns!
        return True
    return False

