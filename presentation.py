import ctypes as C
import json


class Surface(C.Structure):
    _fields_ = [("width", C.c_uint32), ("height", C.c_uint32), ("format", C.c_int32),
                ("pixels", C.c_void_p), ("row_bytes", C.c_size_t),
                ("native", C.c_void_p), ("host", C.c_void_p)]


HEADROOM = C.CFUNCTYPE(C.c_float, C.c_void_p)
ACQUIRE = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_int32, C.POINTER(Surface))
PRESENT = C.CFUNCTYPE(C.c_uint64, C.c_void_p, C.c_char_p, C.POINTER(Surface), C.c_char_p)
DISCARD = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(Surface))


class Presenter(C.Structure):
    _fields_ = [("context", C.c_void_p), ("headroom", HEADROOM), ("acquire", ACQUIRE),
                ("present", PRESENT), ("discard", DISCARD)]


class FrameCapture:
    def __init__(self):
        self.buffers = {}
        self.frames = {}
        self.error = None
        self.presenter = Presenter(None, HEADROOM(lambda _: 5.0), ACQUIRE(self.acquire),
                                   PRESENT(self.present), DISCARD(self.discard))

    def acquire(self, _, width, height, format_id, target):
        try:
            if not 0 < width <= 1920 or not 0 < height <= 1920 or format_id not in (0, 1):
                raise ValueError("Unsupported HDR preview surface.")
            stride = width * (8 if format_id == 1 else 4)
            buffer = C.create_string_buffer(stride * height)
            address = C.addressof(buffer)
            self.buffers[address] = buffer
            target[0] = Surface(width, height, format_id, address, stride, None, None)
            return 0
        except Exception as error:
            self.error = str(error)
            return 1

    def present(self, _, layer, target, info):
        try:
            surface = target.contents
            buffer = self.buffers.pop(surface.pixels)
            self.frames[layer.decode()] = {
                "width": surface.width, "height": surface.height, "format": surface.format,
                "pixels": bytes(buffer)[:surface.row_bytes * surface.height],
                **json.loads(info),
            }
            return len(self.frames)
        except Exception as error:
            self.error = str(error)
            return 0

    def discard(self, _, target):
        self.buffers.pop(target.contents.pixels, None)
