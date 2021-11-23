import os, ctypes, platform

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

def errcheck(ret, func, args):
    if ret != 0:
        import os
        raise OSError(ret, os.strerror(ret))
    return ret

create_shared_memory = Ipc['create_shared_memory']
create_shared_memory.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(C_SharedMemory)]
create_shared_memory.restype = ctypes.c_int
create_shared_memory.errcheck = errcheck

open_shared_memory = Ipc['open_shared_memory']
open_shared_memory.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(C_SharedMemory)]
open_shared_memory.restype = ctypes.c_int
open_shared_memory.errcheck = errcheck

close_shared_memory = Ipc['close_shared_memory']
close_shared_memory.argtypes = [C_SharedMemory, ctypes.c_bool]
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
    """
    A buffer shared between main process and server side process.
    A SharedBuffer instance can be send to server side process via Bridge.
    """

    _GARBAGE = []
    
    @classmethod
    def GC(cls):
        from copy import copy
        for buffer, release_flag in copy(cls._GARBAGE):
            if ctypes.c_bool.from_address(release_flag.data).value == True:
                close_shared_memory(buffer, True)
                close_shared_memory(release_flag, True)
                cls._GARBAGE.remove((buffer, release_flag))

    def __init__(self, ctype, size):
        import random, string
        self._ctype = ctype
        self._size = size
        self.id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        self._buffer = C_SharedMemory()
        create_shared_memory(('MALT_SHARED_'+self.id).encode('ascii'), self.size_in_bytes(), ctypes.byref(self._buffer))
        self._release_flag = C_SharedMemory()
        create_shared_memory(('MALT_FLAG_'+self.id).encode('ascii'), ctypes.sizeof(ctypes.c_bool), ctypes.byref(self._release_flag))
        ctypes.c_bool.from_address(self._release_flag.data).value = False
        self._is_owner = True  # main process side SharedBuffer has ownership
    
    # Called when a SharedBuffer is sent to a new Process via Bridge
    def __getstate__(self):
        assert(self._is_owner)
        assert(ctypes.c_bool.from_address(self._release_flag.data).value == False)
        state = self.__dict__.copy()
        state['_buffer'] = None
        state['_release_flag'] = None
        return state

    # Called when a SharedBuffer is sent to a new Process via Bridge
    def __setstate__(self, state):
        self.__dict__.update(state)
        self._is_owner = False  # server side process SharedBuffer has no ownership
        self._buffer = C_SharedMemory()
        open_shared_memory(('MALT_SHARED_'+self.id).encode('ascii'), self.size_in_bytes(), ctypes.byref(self._buffer))
        self._release_flag = C_SharedMemory()
        open_shared_memory(('MALT_FLAG_'+self.id).encode('ascii'), ctypes.sizeof(ctypes.c_bool), ctypes.byref(self._release_flag))
    
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
        if self._is_owner == False or ctypes.c_bool.from_address(self._release_flag.data).value == True:
            # When server side SharedBuffer is deleted,
            # OR main process side SharedBuffer deleted with release flag
            ctypes.c_bool.from_address(self._release_flag.data).value = True
            close_shared_memory(self._buffer, self._is_owner)
            close_shared_memory(self._release_flag, self._is_owner)
        else:
            # main process side SharedBuffer deleted without release flag
            buffer_copy = C_SharedMemory()
            ctypes.memmove(ctypes.addressof(buffer_copy), ctypes.addressof(self._buffer), ctypes.sizeof(C_SharedMemory))
            flag_copy = C_SharedMemory()
            ctypes.memmove(ctypes.addressof(flag_copy), ctypes.addressof(self._release_flag), ctypes.sizeof(C_SharedMemory))
            self._GARBAGE.append((buffer_copy, flag_copy))
            self.GC()


