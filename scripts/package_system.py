"""Bundle pinned Ubuntu libraries omitted by the GPU worker's base image.

Downloads official archive packages, verifies package-index SHA-256, extracts
only shared libraries and copyright notices. Never installs packages on macOS.
The generated lock is reused on subsequent builds.
"""
import hashlib
import io
import json
import lzma
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
BASE = 'https://archive.ubuntu.com/ubuntu/'
CACHE = APP / '.runtime/ubuntu-libs'
LOCK = APP / 'runtime/system-libraries-lock.json'
# These are the worker's existing compiler/libc ABI; never bundle another libc.
BASE_PACKAGES = {'libc6', 'libgcc-s1', 'libstdc++6', 'gcc-14-base', 'gcc-13-base',
                 'zlib1g', 'ca-certificates', 'debconf', 'debconf-2.0', 'krb5-config'}


def fetch(url, target):
    if not target.exists():
        with urllib.request.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
    return target.read_bytes()


def package_lock():
    if LOCK.is_file() and '--refresh' not in sys.argv:
        return json.loads(LOCK.read_text())
    packages = {}
    # Updates includes the security pocket's published fixes.
    for suite in ('noble', 'noble-security', 'noble-updates'):
        for section in ('main', 'universe'):
            name = f'dists/{suite}/{section}/binary-amd64/Packages.xz'
            data = lzma.decompress(fetch(BASE + name, CACHE / f'{suite}-{section}.xz')).decode()
            for block in data.split('\n\n'):
                fields = dict(line.split(': ', 1) for line in block.splitlines()
                              if ': ' in line and not line.startswith(' '))
                if 'Package' in fields:
                    packages[fields['Package']] = fields
    providers = {}
    for name, item in packages.items():
        for provided in item.get('Provides', '').split(','):
            if provided.strip():
                providers[re.split(r'[ (:\[]', provided.strip())[0]] = name
    todo = ['libtiff6', 'libsharpyuv0', 'libcurl4t64']
    result = {}
    while todo:
        name = todo.pop()
        if name in result or name in BASE_PACKAGES:
            continue
        if name not in packages:
            name = providers[name]
        if name in result or name in BASE_PACKAGES:
            continue
        item = packages[name]
        result[name] = {key: item[key] for key in ('Version', 'Filename', 'SHA256')}
        for dependency in item.get('Depends', '').split(','):
            if dependency.strip():
                todo.append(re.split(r'[ (:\[]', dependency.strip())[0])
    LOCK.write_text(json.dumps(result, indent=2) + '\n')
    return result


def deb_data(blob):
    assert blob.startswith(b'!<arch>\n')
    offset = 8
    while offset + 60 <= len(blob):
        header = blob[offset:offset + 60]
        size = int(header[48:58]); name = header[:16].decode().strip().rstrip('/')
        payload = blob[offset + 60:offset + 60 + size]
        if name.startswith('data.tar'):
            if name.endswith('.zst'):
                import zstandard
                return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(payload)).read()
            return payload
        offset += 60 + size + size % 2
    raise ValueError('Debian package has no data archive')


def bundle(destination):
    CACHE.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    lock = package_lock()
    for previous in destination.glob('*.so*'):
        previous.unlink()
    count = 0
    for name, item in lock.items():
        archive = fetch(BASE + item['Filename'], CACHE / Path(item['Filename']).name)
        assert hashlib.sha256(archive).hexdigest() == item['SHA256'], name
        with tarfile.open(fileobj=io.BytesIO(deb_data(archive))) as tar:
            for member in tar:
                if not member.isfile():
                    continue
                path = Path(member.name)
                if '.so' in path.name and ('/lib/' in member.name or member.name.startswith('./lib/')):
                    target = destination / path.name
                    count += 1
                elif path.name == 'copyright' and '/share/doc/' in member.name:
                    target = destination / 'licenses' / (name + '.copyright')
                else:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    (destination / 'provenance.json').write_text(json.dumps({'archive': BASE, 'distribution': 'noble', 'packages': lock}, indent=2))
    print(f'Bundled {count} system shared libraries from {len(lock)} checksum-pinned Ubuntu packages.')
