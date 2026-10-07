"""Assemble the pinned Linux runtime from checksum-verified upstream artifacts."""
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from PySquashfsImage import SquashFsImage
from PySquashfsImage.file import RegularFile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.runtime'
URL = 'https://github.com/DhaliwalX/fotufilm-engine/releases/download/v1.11/Fotufilm-Linux-x86_64.AppImage'
SHA256 = 'b0ff8a457a297aa8d09e322ea0b0d1bb1e09587cce52736293bbb3b52083f89f'


def fetch(url, destination, sha256):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        with destination.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() == sha256:
                return destination
    partial = destination.with_suffix(destination.suffix + '.part')
    try:
        with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as target:
            shutil.copyfileobj(response, target)
        with partial.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != sha256:
                raise ValueError(f'Checksum mismatch: {destination.name}')
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def install():
    marker = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in (
        'scripts/install_linux.py', 'scripts/package_ffmpeg.py', 'scripts/package_system.py',
        'runtime/ffmpeg-lock.json', 'runtime/system-libraries-lock.json'))).hexdigest()
    destination = ROOT / 'linux-runtime'
    if (destination / '.installed').is_file() and (destination / '.installed').read_text() == marker:
        print('Pinned Fotufilm native runtime already installed.')
        return
    archive = fetch(URL, CACHE / 'Fotufilm-Linux-x86_64.AppImage', SHA256)
    lock = json.loads((ROOT / 'runtime/ffmpeg-lock.json').read_text())
    fetch(lock['url'], CACHE / lock['filename'], lock['digests']['sha256'])
    blob = archive.read_bytes()
    offset = 0
    while True:
        offset = blob.find(b'hsqs', offset)
        if offset < 0:
            raise ValueError('No valid SquashFS in the pinned AppImage')
        try:
            image = SquashFsImage.from_file(archive, offset)
            break
        except OSError:
            offset += 4
    del blob
    with tempfile.TemporaryDirectory(prefix='fotufilm-install-', dir=CACHE) as directory:
        stage = Path(directory) / 'linux-runtime'
        stage.mkdir()
        for item in image:
            relative = item.path.removeprefix('/usr/lib/fotufilm/')
            keep = item.path.startswith('/usr/lib/fotufilm/') and (
                (relative.startswith('lib') and '/' not in relative and relative not in
                 ('libcef.so', 'libvk_swiftshader.so', 'libvulkan.so.1'))
                or relative.startswith(('resources/', 'heif-plugins/')))
            if item.path.startswith('/usr/share/doc/'):
                relative = 'licenses/' + item.path.removeprefix('/usr/share/doc/')
                keep = True
            if not keep or not isinstance(item, RegularFile):
                continue
            target = stage / relative
            if not target.resolve().is_relative_to(stage.resolve()):
                raise ValueError('Unsafe archive member')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('wb') as output:
                for block in item.iter_bytes():
                    output.write(block)
        from package_ffmpeg import bundle as ffmpeg_bundle
        from package_system import bundle as system_bundle
        ffmpeg_bundle(stage / 'ffmpeg6')
        system_bundle(stage / 'system')
        provided, required = set(), set()
        for library in stage.rglob('lib*.so*'):
            with library.open('rb') as source:
                tags = list(ELFFile(source).get_section_by_name('.dynamic').iter_tags())
                provided.update(t.soname for t in tags if t.entry.d_tag == 'DT_SONAME')
                required.update(t.needed for t in tags if t.entry.d_tag == 'DT_NEEDED')
        abi = {'ld-linux-x86-64.so.2', 'libc.so.6', 'libdl.so.2', 'libgcc_s.so.1',
               'libm.so.6', 'libpthread.so.0', 'libresolv.so.2', 'librt.so.1',
               'libstdc++.so.6', 'libz.so.1'}
        if missing := required - provided - abi:
            raise RuntimeError('Unbundled native libraries: ' + ', '.join(sorted(missing)))
        (stage / 'provenance.json').write_text(json.dumps({
            **json.loads((ROOT / 'upstream/fotufilm.lock.json').read_text()),
            'artifact': URL, 'sha256': SHA256}, indent=2))
        (stage / '.installed').write_text(marker)
        if destination.exists():
            shutil.rmtree(destination)
        stage.replace(destination)
    print('Installed Fotufilm v1.11 native runtime, profiles and codec dependencies. No AI models downloaded.')


if __name__ == '__main__':
    install()
