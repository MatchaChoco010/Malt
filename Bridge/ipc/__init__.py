import copy
import subprocess
import os
import ctypes

import platform

src_dir = os.path.abspath(os.path.dirname(__file__))

library = 'libIpc.so'
if platform.system() == 'Windows': library = 'Ipc.dll'
if platform.system() == 'Darwin': library = 'libIpc.dylib'

Ipc = ctypes.CDLL(os.path.join(src_dir, library))

class C_SharedMemory(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),
        ('data', ctypes.c_void_p),
        ('size', ctypes.c_size_t),
        ('handle', ctypes.c_void_p),
        ('int', ctypes.c_int),
    ]

create_shared_memory = Ipc['create_shared_memory']
create_shared_memory.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
create_shared_memory.restype = C_SharedMemory

open_shared_memory = Ipc['open_shared_memory']
open_shared_memory.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
open_shared_memory.restype = C_SharedMemory

close_shared_memory = Ipc['close_shared_memory']
close_shared_memory.argtypes = [C_SharedMemory]
close_shared_memory.restype = None

# https://numpy.org/doc/stable/reference/arrays.interface.html
class Array_Interface():
    def __init__(self, pointer, typestr, shape, read_only=False):
        self.__array_interface__ = {
            'data': (pointer, read_only),
            'typestr': typestr,
            'shape': shape
        }

class SharedBuffer():

    _GARBAGE = []
    _REF_COUNT = None
    _LOCK = None

    @classmethod
    def setup_class(cls, shared_dict, lock):
        cls._REF_COUNT = shared_dict
        cls._LOCK = lock
        cls.GC()
    
    @classmethod
    def GC(cls):
        from copy import copy
        with cls._LOCK:
            for buffer in copy(cls._GARBAGE):
                if buffer.name not in cls._REF_COUNT.keys() or cls._REF_COUNT[buffer.name] == 0:
                    print('GC ', buffer.name)
                    close_shared_memory(buffer)
                    cls._GARBAGE.remove(buffer)
                    cls._REF_COUNT.pop(buffer.name, None)

    def __init__(self, ctype, size):
        import random, string
        self._ctype = ctype
        self._size = size
        name = 'MALT_SHARED_' + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        self._buffer = create_shared_memory(name.encode('ascii'), self.size_in_bytes())
        self._name = self._buffer.name
        with self._LOCK:
            self._REF_COUNT[self._name] = 1
    
    def __getstate__(self):
        print('GET ', self._name, self)
        with self._LOCK:
            self._REF_COUNT[self._name] += 1
        state = self.__dict__.copy()
        state['_buffer'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._buffer = open_shared_memory(self._name, self.size_in_bytes())
        print('SET ', self._name, self)
    
    def size_in_bytes(self):
        return ctypes.sizeof(self._ctype) * self._size
    
    def buffer(self):
        return (self._ctype*self._size).from_address(self._buffer.data)
    
    def as_array_interface(self):
        type_map = {
            ctypes.c_float : 'f',
            ctypes.c_int : 'i',
            ctypes.c_uint : 'u',
            ctypes.c_bool : 'b',
        }
        return Array_Interface(self._buffer.data, type_map[self._ctype], (self._size,))
    
    def as_np_array(self):
        import numpy as np
        return np.array(self.as_array_interface(), copy=False)

    def __del__(self):
        print('DEL ', self._name, self)
        with self._LOCK:
            self._REF_COUNT[self._name] -= 1
        copy = C_SharedMemory()
        ctypes.memmove(ctypes.addressof(copy), ctypes.addressof(self._buffer), ctypes.sizeof(C_SharedMemory))
        self._GARBAGE.append(copy)
        self.GC() 


__BUFFERS = {}
class SharedMemory(object):
    def __init__(self, name, size, gen):
        self.name = ('MALT_SHARED_MEM_' + name + '_GEN_' + str(gen)).encode('ascii')
        self.size = size
        self.gen = gen
        self.c = create_shared_memory(self.name, self.size)
    
    def __del__(self):
        close_shared_memory(self.c)

class SharedMemoryRef(object):
    def __init__(self, full_name, size):
        self.name = full_name
        self.size = size
        self.c = open_shared_memory(self.name, self.size)
    
    def __del__(self):
        #TODO: Investigate. Seems like Windows ref counts but Linux doesn't?
        if platform.system() == 'Windows':
            close_shared_memory(self.c)

def load_shared_buffer(name, ctype, size):
    total_size = ctypes.sizeof(ctype) * size
    if name not in __BUFFERS:
        __BUFFERS[name] = SharedMemory(name, total_size, 0)
    elif total_size > __BUFFERS[name].size:
        old = __BUFFERS[name]
        __BUFFERS[name] = SharedMemory(name, total_size, old.gen + 1)
        del old
    
    return (ctype * size).from_address(__BUFFERS[name].c.data)

def get_shared_buffer_full_name(name):
    return __BUFFERS[name].name


