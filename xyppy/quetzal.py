from __future__ import print_function

import os
import sys
import struct

from xyppy.iff import Chunk, FormChunk, packHdr

class IFhdChunk(Chunk):
    @classmethod
    def from_chunk(cls, chunk):
        obj = cls()
        obj.name, obj.size, obj.data = chunk.name, chunk.size, chunk.data
        obj.release = struct.unpack('>H', chunk.data[:2])[0]
        obj.serial = bytes(bytearray(chunk.data[2:8]))
        obj.checksum = struct.unpack('>H', chunk.data[8:10])[0]
        pc_bytearray = bytearray([0,0,0,0])
        pc_bytearray[1:] = bytearray(chunk.data[10:13])
        pc_bytes = bytes(pc_bytearray)
        obj.pc = struct.unpack('>I', pc_bytes)[0]
        return obj
    @classmethod
    def from_env(cls, env):
        obj = cls()
        obj.name = b'IFhd'
        obj.size = 13
        obj.release = env.hdr.release
        obj.serial = bytes(bytearray(env.hdr.serial))
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
    bigmem = []
    i = 0
    while i < len(mem):
        bigmem.append(mem[i])
        if mem[i] == 0:
            bigmem.extend([0] * mem[i+1])
            i += 2
        else:
            i += 1
    return bytes(bytearray(bigmem))

def encRLE(mem):
    small_mem = []
    i = 0
    while i < len(mem):
        small_mem.append(mem[i])
        if mem[i] == 0:
            zero_run = 0
            i += 1
            while i < len(mem) and mem[i] == 0 and zero_run < 255:
                zero_run += 1
                i += 1
            small_mem.append(zero_run)
        else:
            i += 1
    return bytes(bytearray(small_mem))

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
        obj.name = b'CMem'
        obj.mem = env.mem[:env.hdr.static_mem_base]
        for i in range(len(obj.mem)):
            obj.mem[i] ^= env.orig_mem[i]
        while obj.mem[-1] == 0:
            obj.mem.pop()
        obj.mem = bytes(bytearray(obj.mem))
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
        obj.name = b'UMem'
        obj.mem = env.mem[:env.hdr.static_mem_base]
        obj.mem= bytes(bytearray(obj.mem))
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
        ret_addr_bytearray = bytearray([0,0,0,0])
        ret_addr_bytearray[1:] = bytearray(data[:3])
        ret_addr_bytes = bytes(ret_addr_bytearray)
        obj.return_addr = struct.unpack('>I', ret_addr_bytes)[0]
        flags = data[3]
        num_locals = flags & 15
        if flags & 16:
            # discard return val
            obj.return_val_loc = None
        else:
            obj.return_val_loc = data[4]

        # this should never have non-consecutive ones, right?
        # i.e. you can't have arg 3 without having args 1 and 2 (right?)
        args_flag = data[5]
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
        return bytes(struct.pack('>I', self.return_addr)[1:] +
                     bytearray([flags]) +
                     bytearray([self.return_val_loc or 0]) +
                     bytearray([args_byte]) +
                     packWords([len(self.stack)]) +
                     packWords(self.locals) +
                     packWords(self.stack))
               
def packWords(words):
    out = []
    for word in words:
        out.append(word >> 8)
        out.append(word & 0xff)
    return bytearray(out)

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
        obj.name = b'Stks'
        obj.frames = [QFrame.from_frame(f) for f in env.callstack]
        return obj
    def pack(self):
        framelist_flat = bytearray()
        for f in self.frames:
            framelist_flat.extend(f.pack())
        framebytes = bytes(framelist_flat)
        self.size = len(framebytes)
        return packHdr(self) + framebytes

def read(filename):
    if os.path.exists(filename + '.sav'):
        filename += '.sav'
    with open(filename, 'rb') as f:
        formChunk = FormChunk.from_chunk(Chunk.from_data(f.read()))
        for chunk in formChunk.chunks:
            if chunk.name == b'IFhd':
                hdChunk = IFhdChunk.from_chunk(chunk)
            if chunk.name == b'CMem':
                memChunk = CMemChunk.from_chunk(chunk)
            if chunk.name == b'UMem':
                memChunk = UMemChunk.from_chunk(chunk)
            if chunk.name == b'Stks':
                stksChunk = StksChunk.from_chunk(chunk)
    return formChunk.subname, hdChunk, memChunk, stksChunk.frames

def write(env, filename):
    if not filename.endswith('.sav'):
        filename += '.sav'
    try:
        with open(filename, 'wb') as f:
            chunks = [IFhdChunk.from_env(env),
                      CMemChunk.from_env(env),
                      StksChunk.from_env(env)]
            formChunk = FormChunk.from_chunk_list(b'IFZS', chunks)
            f.write(formChunk.pack())
        return True
    except IOError as ioerr:
        env.screen.msg('error writing save file: '+str(ioerr)+'\n')
        return False

def load_to_env(env, filename):
    msg = env.screen.msg
    try:
        subname, hdrChunk, memChunk, frames = read(filename)
    except IOError as ioerr:
        env.screen.msg('error reading file: '+str(ioerr)+'\n')
        return False

    if subname != b'IFZS':
        msg('not a quetzal save file\n')
    if env.hdr.release != hdrChunk.release:
        msg('release doesn\'t match\n')
    elif env.hdr.serial != hdrChunk.serial:
        msg('serial doesn\'t match\n')
    elif env.hdr.checksum != hdrChunk.checksum:
        msg('checksum does\'t match\n')
    else:
        env.reset()
        for i in range(len(memChunk.mem)):
            if memChunk.compressed:
                env.mem[i] ^= memChunk.mem[i]
            else:
                env.mem[i] = memChunk.mem[i]
        env.fixup_after_restore()
        env.pc = hdrChunk.pc
        env.callstack = frames

        # pc is now in wrong place:
        # must fix based on z version
        # after this func returns!
        return True
    return False

