import ctypes as C
import json
import os
import sys
import threading
from pathlib import Path

from .presentation import FrameCapture, Presenter
from .runtime_paths import library_path, stocks_path, resources_path

LEGACY_REVISION = "f602857a031a6a9c9b0966284ff989eb3046c323"
REVISION = "9242d189b6f8321a27c6f6a345aeb4e5991da569"


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
        packaged = Path(__file__).parent / 'linux-runtime'
        if path == (packaged / 'libfotufilm-float.so').resolve():
            import hashlib
            lock = json.loads((Path(__file__).parent / 'runtime/float-engine-lock.json').read_text())
            if not path.is_file() or not resources_path().is_dir():
                raise RuntimeError('The pinned CUDA engine or matching profiles are missing. Run python install.py and restart ComfyUI.')
            with path.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != lock['librarySha256']:
                    raise RuntimeError('The CUDA engine is from a different release. Run python install.py and restart ComfyUI.')
        os.environ.setdefault("FOTUFILM_STOCKS", str(stocks_path()))
        if sys.platform == 'linux':
            packaged = Path(__file__).parent / 'linux-runtime'
            if packaged.is_dir():
                os.environ.setdefault('FOTUFILM_RESOURCES', str(resources_path()))
                os.environ.setdefault('FOTUFILM_STOCKS', str(packaged / 'resources/Stocks'))
                os.environ.setdefault('LIBHEIF_PLUGIN_PATH', str(packaged / 'heif-plugins'))
                pending = list(path.parent.glob('lib*.so*'))
                if path.parent == packaged:
                    pending += list((packaged / 'ffmpeg6').glob('lib*.so*')) + list((packaged / 'system').glob('lib*.so*'))
                if path in pending: pending.remove(path)
                pending = [p for p in pending if not p.name.startswith(('libfotufilm', 'libFotufilm'))]
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
        self.memory_input = getattr(self.lib, 'fotufilm_image_from_rgba32f', None)
        if self.memory_input is not None:
            self.memory_input.restype = C.c_void_p
            self.memory_input.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_size_t, C.POINTER(C.c_void_p)]
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

    def render_rgb(self, rgb, request):
        """No encoder/decoder or filesystem round trip. Exact pinned film engine."""
        import numpy as np
        if self.memory_input is None:
            raise RuntimeError('This runtime does not expose the float-memory input extension.')
        height, width, channels = rgb.shape
        if channels != 3 or not np.isfinite(rgb).all():
            raise ValueError('Expected finite linear Rec.2020 RGB pixels.')
        rgba = np.ones((height, width, 4), dtype=np.float32)
        rgba[..., :3] = rgb
        with self.lock:
            error = C.c_void_p()
            image = self.memory_input(rgba.ctypes.data, width, height, rgba.size, C.byref(error))
            if not image:
                self.raise_error(error)
            pixels = np.empty_like(rgba)
            target = Target(0, 1, pixels.ctypes.data, width * 16, pixels.nbytes)
            info = Info()
            try:
                status = self.lib.fotufilm_render(self.handle, image, json.dumps(request).encode(),
                    C.byref(target), C.byref(info), C.byref(error))
                if status:
                    self.raise_error(error)
                return pixels[..., :3].copy()
            finally:
                self.lib.fotufilm_image_release(image)

    def cancel(self):
        self.lib.fotufilm_engine_cancel(self.handle)

    def close(self):
        with self.lock:
            if self.handle:
                self.lib.fotufilm_engine_destroy(self.handle)
                self.handle = None
