"""Worker-owned native engine and bounded, lossless float caches.

Only the Studio preview worker uses these resources. Graph executions keep
their own lifetime. No display-encoded pixels enter the intermediate cache.
"""
import hashlib
import json
import os
from collections import OrderedDict
from pathlib import Path

import numpy as np

from .native import Engine


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class FloatLRU:
    def __init__(self, limit):
        self.limit = limit
        self.bytes = 0
        self.items = OrderedDict()

    def get(self, key):
        value = self.items.get(key)
        if value is not None:
            self.items.move_to_end(key)
        return value

    def put(self, key, value):
        if value.nbytes > self.limit:
            return
        previous = self.items.pop(key, None)
        if previous is not None:
            self.bytes -= previous.nbytes
        value = np.ascontiguousarray(value, dtype=np.float32).copy()
        value.flags.writeable = False
        self.items[key] = value
        self.bytes += value.nbytes
        while self.bytes > self.limit:
            _, old = self.items.popitem(last=False)
            self.bytes -= old.nbytes

    def clear(self):
        self.items.clear()
        self.bytes = 0


class FloatDiskCache:
    """Uncompressed NPY keeps float32 bits; atomic files never expose partial frames."""
    def __init__(self, root, limit=4 * 1024**3):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.limit = limit
        self.files = OrderedDict((p.name, p.stat().st_size) for p in
                                 sorted(self.root.glob('*.npy'), key=lambda p: p.stat().st_mtime))
        self.bytes = sum(self.files.values())
        self._prune()

    def _prune(self):
        while self.bytes > self.limit and self.files:
            name, size = self.files.popitem(last=False)
            (self.root / name).unlink(missing_ok=True)
            self.bytes -= size

    def get(self, key):
        name = key + '.npy'
        if name not in self.files:
            return None
        try:
            value = np.load(self.root / name, allow_pickle=False)
            if value.dtype != np.float32 or value.ndim != 3 or value.shape[-1] != 3:
                raise ValueError('Invalid cached frame')
        except (OSError, ValueError, EOFError):
            self.bytes -= self.files.pop(name)
            (self.root / name).unlink(missing_ok=True)
            return None
        self.files.move_to_end(name)
        value.flags.writeable = False
        return value

    def put(self, key, value):
        if value.nbytes + 256 > self.limit:
            return
        name = key + '.npy'
        path = self.root / name
        temporary = path.with_suffix('.part')
        try:
            with temporary.open('wb') as handle:
                np.save(handle, np.asarray(value, dtype=np.float32), allow_pickle=False)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        self.bytes -= self.files.pop(name, 0)
        self.files[name] = path.stat().st_size
        self.bytes += self.files[name]
        self._prune()


class SourceCursor:
    """Decode sequential misses once, and skip decoding entirely for cached film frames."""
    def __init__(self, source, edge):
        self.source, self.edge = source, edge
        self.iterator = None
        self.last = -1

    def read(self, index):
        if self.iterator is None or index <= self.last:
            self.close()
            self.iterator = self.source.frames(index, edge=self.edge)
        for number, rgb in self.iterator:
            self.last = number
            if number == index:
                return rgb
        raise ValueError('Source ended before its reported frame count.')

    def close(self):
        if self.iterator is not None:
            self.iterator.close()
            self.iterator = None


class PreviewRuntime:
    def __init__(self, root, signature, disk_limit=4 * 1024**3, memory_limit=192 * 1024**2):
        self.signature = signature
        self.source_cache = FloatLRU(memory_limit * 2 // 3)
        self.film_cache = FloatLRU(memory_limit // 3)
        self.disk = FloatDiskCache(root, disk_limit)
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = Engine()
        return self._engine

    def key(self, source, fingerprint, index, edge):
        effective_edge = min(edge or max(source.info['width'], source.info['height']),
                             max(source.info['width'], source.info['height']))
        return digest([self.signature, fingerprint, index, effective_edge])

    def source_frame(self, cursor, fingerprint, index, stats):
        key = self.key(cursor.source, fingerprint, index, cursor.edge)
        rgb = self.source_cache.get(key)
        if rgb is None:
            rgb = cursor.read(index)
            self.source_cache.put(key, rgb)
            stats['decodedFrames'] += 1
        else:
            stats['sourceCacheHits'] += 1
        return rgb

    def finished_frame(self, cursor, fingerprint, index, finisher, stats, source_rgb=None):
        key = digest([self.key(cursor.source, fingerprint, index, cursor.edge), finisher.film_signature])
        developed = self.film_cache.get(key)
        memory_hit = developed is not None
        if developed is None:
            developed = self.disk.get(key)
        if developed is None:
            rgb = source_rgb if source_rgb is not None else self.source_frame(cursor, fingerprint, index, stats)
            developed = finisher.develop(rgb, index)
            if not np.isfinite(developed).all():
                raise ValueError('Non-finite rendered pixels.')
            self.disk.put(key, developed)
            stats['filmRenderedFrames'] += 1
        else:
            stats['filmCacheHits'] += 1
        if not memory_hit:
            self.film_cache.put(key, developed)
        return finisher.finish(developed)

    def close(self):
        if self._engine is not None:
            self._engine.close()
            self._engine = None
        self.source_cache.clear()
        self.film_cache.clear()


def render_stats():
    return dict(decodedFrames=0, sourceCacheHits=0, filmRenderedFrames=0, filmCacheHits=0)
