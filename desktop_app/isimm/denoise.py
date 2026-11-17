"""Petit hôte LADSPA mono. Le modèle DeepFilterNet est embarqué dans le plugin."""

import ctypes as C
import numpy as np

FloatPtr = C.POINTER(C.c_float)
Handle = C.c_void_p
Port = C.c_ulong


class Descriptor(C.Structure):
    pass


Descriptor._fields_ = [
    ("id", Port),
    ("label", C.c_char_p),
    ("properties", C.c_int),
    ("name", C.c_char_p),
    ("maker", C.c_char_p),
    ("copyright", C.c_char_p),
    ("count", Port),
    ("types", C.POINTER(C.c_int)),
    ("names", C.POINTER(C.c_char_p)),
    ("hints", Handle),
    ("data", Handle),
    ("instantiate", C.CFUNCTYPE(Handle, C.POINTER(Descriptor), Port)),
    ("connect", C.CFUNCTYPE(None, Handle, Port, FloatPtr)),
    ("activate", C.CFUNCTYPE(None, Handle)),
    ("run", C.CFUNCTYPE(None, Handle, Port)),
    ("run_adding", Handle),
    ("set_gain", Handle),
    ("deactivate", C.CFUNCTYPE(None, Handle)),
    ("cleanup", C.CFUNCTYPE(None, Handle)),
]


class DeepFilter:
    def __init__(self, library):
        self.lib = C.CDLL(str(library))
        lookup = self.lib.ladspa_descriptor
        lookup.argtypes = [Port]
        lookup.restype = C.POINTER(Descriptor)
        for i in range(16):
            ptr = lookup(i)
            if not ptr:
                raise ValueError("Plugin DeepFilterNet mono introuvable")
            if ptr.contents.label == b"deep_filter_mono":
                break
        self.desc = ptr.contents
        self.handle = self.desc.instantiate(ptr, 48000)
        if not self.handle:
            raise RuntimeError("Initialisation DeepFilterNet impossible")
        self.controls = []
        # Ordre des commandes du descripteur de la version 0.5.6.
        defaults = iter([18.0, -10.0, 30.0, 20.0, 2.0, 0.0])
        for i in range(self.desc.count):
            flags = self.desc.types[i]
            if flags & 8:
                if flags & 1:
                    self.input = i
                else:
                    self.output = i
            else:
                val = C.c_float(next(defaults, 0.0))
                self.controls.append(val)
                self.desc.connect(self.handle, i, C.pointer(val))
        if self.desc.activate:
            self.desc.activate(self.handle)

    def process(self, data):
        data = np.ascontiguousarray(data, dtype="float32")
        out = np.empty_like(data)
        self.desc.connect(self.handle, self.input, data.ctypes.data_as(FloatPtr))
        self.desc.connect(self.handle, self.output, out.ctypes.data_as(FloatPtr))
        self.desc.run(self.handle, len(data))
        return np.clip(out, -1.0, 1.0)

    def close(self):
        if self.handle:
            if self.desc.deactivate:
                self.desc.deactivate(self.handle)
            self.desc.cleanup(self.handle)
            self.handle = None
