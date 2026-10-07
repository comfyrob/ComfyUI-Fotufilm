import ctypes as C
import json
import os
import sys
import threading
from pathlib import Path

from .presentation import FrameCapture, Presenter
from .runtime_paths import library_path, stocks_path

REVISION = "f602857a031a6a9c9b0966284ff989eb3046c323"


class Answer(C.Structure):
    _fields_ = [("json", C.c_void_p), ("payload", C.c_void_p), ("length", C.c_size_t)]


class Target(C.Structure):
    _fields_ = [("max_edge", C.c_uint32), ("format", C.c_int32),
                ("pixels", C.c_void_p), ("row_bytes", C.c_size_t), ("capacity", C.c_size_t)]


class Info(C.Structure):
    _fields_ = [("width", C.c_uint32), ("height", C.c_uint32), ("milliseconds", C.c_double)]


PROGRESS = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p)


class Engine:
    def __init__(self):
        path = library_path()
        os.environ.setdefault("FOTUFILM_STOCKS", str(stocks_path()))
        if sys.platform == 'linux':
            packaged = Path(__file__).parent / 'linux-runtime'
            if path.parent == packaged:
                os.environ.setdefault('FOTUFILM_RESOURCES', str(packaged / 'resources'))
                os.environ.setdefault('FOTUFILM_STOCKS', str(packaged / 'resources/Stocks'))
                os.environ.setdefault('LIBHEIF_PLUGIN_PATH', str(packaged / 'heif-plugins'))
                pending = (list(packaged.glob('lib*.so*')) + list((packaged / 'ffmpeg6').glob('lib*.so*'))
                           + list((packaged / 'system').glob('lib*.so*')))
                pending.remove(path)
                while pending:
                    loaded = []
                    for dependency in pending:
                        try:
                            C.CDLL(str(dependency), mode=C.RTLD_LOCAL)
                            loaded.append(dependency)
                        except OSError:
                            pass
                    if not loaded:
                        raise RuntimeError('Unresolved Fotufilm runtime libraries: ' + ', '.join(p.name for p in pending))
                    pending = [p for p in pending if p not in loaded]
        if not path.is_file():
            raise RuntimeError("The pinned Fotufilm native library is missing. Run python install.py; see ComfyUI-Fotufilm README.md.")
        self.lib = C.CDLL(str(path))
        signatures = {
            "fotufilm_api_version": (C.c_int32, []),
            "fotufilm_engine_create": (C.c_void_p, [C.POINTER(C.c_void_p)]),
            "fotufilm_engine_destroy": (None, [C.c_void_p]),
            "fotufilm_engine_set_presenter": (None, [C.c_void_p, C.POINTER(Presenter)]),
            "fotufilm_engine_cancel": (None, [C.c_void_p]),
            "fotufilm_free": (None, [C.c_void_p]),
            "fotufilm_capabilities": (C.c_void_p, []),
            "fotufilm_engine_describe": (C.c_void_p, [C.c_void_p]),
            "fotufilm_host_call_progress": (C.c_int32, [C.c_void_p, C.c_char_p, C.c_char_p,
                C.c_void_p, C.c_size_t, PROGRESS, C.c_void_p, C.POINTER(Answer), C.POINTER(C.c_void_p)]),
            "fotufilm_answer_free": (None, [C.POINTER(Answer)]),
            "fotufilm_image_open": (C.c_void_p, [C.c_void_p, C.c_char_p, C.POINTER(C.c_void_p)]),
            "fotufilm_image_release": (None, [C.c_void_p]),
            "fotufilm_render": (C.c_int32, [C.c_void_p, C.c_void_p, C.c_char_p,
                C.POINTER(Target), C.POINTER(Info), C.POINTER(C.c_void_p)]),
        }
        for name, (result, args) in signatures.items():
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = result, args
        if self.lib.fotufilm_api_version() != 1:
            raise RuntimeError("Unsupported Fotufilm C API. Install the pinned version.")
        self.lock = threading.RLock()
        error = C.c_void_p()
        self.handle = self.lib.fotufilm_engine_create(C.byref(error))
        if not self.handle:
            self.raise_error(error)

    def raise_error(self, error):
        message = C.string_at(error).decode() if error.value else "Fotufilm failed or was cancelled."
        self.lib.fotufilm_free(error)
        raise RuntimeError(message)

    def call(self, method, params=None, payload=None, progress=None):
        with self.lock:
            answer, error = Answer(), C.c_void_p()
            buffer = C.create_string_buffer(payload) if payload else None
            callback = PROGRESS(lambda _, value: progress(json.loads(value)) if progress else None)
            status = self.lib.fotufilm_host_call_progress(
                self.handle, method.encode(), json.dumps(params or {}).encode(),
                buffer, len(payload) if payload else 0, callback, None, C.byref(answer), C.byref(error))
            try:
                if status:
                    self.raise_error(error)
                data = json.loads(C.string_at(answer.json))
                binary = C.string_at(answer.payload, answer.length) if answer.length else b""
                images = {key: binary[offset:offset + size]
                          for key, (offset, size) in data.pop("payloads", {}).items()}
                return data, images
            finally:
                self.lib.fotufilm_answer_free(C.byref(answer))

    def present(self, request):
        with self.lock:
            capture = FrameCapture()
            self.lib.fotufilm_engine_set_presenter(self.handle, C.byref(capture.presenter))
            try:
                self.call("render", {**request, "present": {"slot": "preview", "scope": "film-finish"}})
                if capture.error:
                    raise RuntimeError(capture.error)
                return capture.frames["preview"]
            finally:
                self.lib.fotufilm_engine_set_presenter(self.handle, None)

    def render_float(self, path, width, height, request):
        import numpy as np
        with self.lock:
            error = C.c_void_p()
            image = self.lib.fotufilm_image_open(self.handle, os.fsencode(path), C.byref(error))
            if not image:
                self.raise_error(error)
            pixels = np.empty((height, width, 4), dtype=np.float32)
            target = Target(0, 1, pixels.ctypes.data, width * 16, pixels.nbytes)
            info = Info()
            try:
                status = self.lib.fotufilm_render(self.handle, image, json.dumps(request).encode(),
                                                 C.byref(target), C.byref(info), C.byref(error))
                if status:
                    self.raise_error(error)
                return pixels[:, :, :3].copy()
            finally:
                self.lib.fotufilm_image_release(image)

    def cancel(self):
        self.lib.fotufilm_engine_cancel(self.handle)

    def close(self):
        with self.lock:
            if self.handle:
                self.lib.fotufilm_engine_destroy(self.handle)
                self.handle = None
