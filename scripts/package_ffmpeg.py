"""Bundle FFmpeg 6 libraries for Fotufilm without replacing ComfyUI's PyAV.

The official PyAV 12.3 wheel carries FFmpeg's exact required ABI. Auditwheel
hashes library names; normalize only the five FFmpeg SONAMEs and their dynamic
references to the standard names used by Fotufilm's dlopen calls. All replacements
are shorter, preserving ELF offsets and executable code. Other libraries retain
private hashed names. No model weights or system packages are installed.
"""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from elftools.elf.elffile import ELFFile

APP = Path(__file__).resolve().parents[1]


def bundle(destination):
    lock = json.loads((APP / 'runtime/ffmpeg-lock.json').read_text())
    wheel = APP / '.runtime' / lock['filename']
    with wheel.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == lock['digests']['sha256']
    with zipfile.ZipFile(wheel) as archive:
        libraries = {Path(n).name: archive.read(n) for n in archive.namelist() if n.startswith('av.libs/') and '.so.' in n}
        aliases = {}
        for name in libraries:
            match = re.fullmatch(r'(lib(?:avcodec|avformat|avutil|swscale|swresample))-[a-f0-9]+\.so\.(\d+)(?:\..*)?', name)
            if match:
                aliases[name] = f'{match[1]}.so.{match[2]}'
        assert set(aliases.values()) == {'libavcodec.so.60', 'libavformat.so.60', 'libavutil.so.58', 'libswscale.so.7', 'libswresample.so.4'}
        required = set(aliases)
        pending = list(required)
        while pending:
            name = pending.pop()
            elf = ELFFile(io.BytesIO(libraries[name]))
            for tag in elf.get_section_by_name('.dynamic').iter_tags():
                if tag.entry.d_tag == 'DT_NEEDED' and tag.needed in libraries and tag.needed not in required:
                    required.add(tag.needed)
                    pending.append(tag.needed)
        destination.mkdir(parents=True, exist_ok=True)
        external = set()
        for name in sorted(required):
            data = bytearray(libraries[name])
            elf = ELFFile(io.BytesIO(data))
            table_offset = elf.get_section_by_name('.dynstr')['sh_offset']
            for tag in elf.get_section_by_name('.dynamic').iter_tags():
                if tag.entry.d_tag not in ('DT_NEEDED', 'DT_SONAME'):
                    continue
                value = tag.needed if tag.entry.d_tag == 'DT_NEEDED' else tag.soname
                if tag.entry.d_tag == 'DT_NEEDED' and value not in libraries:
                    external.add(value)
                if value not in aliases:
                    continue
                old, new = value.encode(), aliases[value].encode()
                assert len(new) <= len(old)
                offset = table_offset + tag.entry.d_val
                assert data[offset:offset + len(old) + 1] == old + b'\0'
                data[offset:offset + len(old) + 1] = new + b'\0' * (len(old) - len(new) + 1)
            (destination / aliases.get(name, name)).write_bytes(data)
        (destination / 'PyAV-LICENSE.txt').write_bytes(archive.read('av-12.3.0.dist-info/LICENSE.txt'))
    provenance = {**lock, 'source': 'https://github.com/PyAV/PyAV/tree/v12.3.0',
                  'ffmpegSources': 'https://github.com/PyAV/FFmpeg',
                  'modification': 'Dynamic SONAME / NEEDED spelling only; no executable code changed.',
                  'aliases': aliases, 'systemLibraries': sorted(external)}
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    print(f'Bundled {len(required)} FFmpeg/codec libraries; system dependencies: {sorted(external)}')
