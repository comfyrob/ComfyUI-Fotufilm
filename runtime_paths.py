"""Portable native runtime locations; machine-specific overrides are never committed."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def configured_path(name, default):
    config = ROOT / 'runtime.local.json'
    values = json.loads(config.read_text()) if config.is_file() else {}
    return Path(os.environ.get(name) or values.get(name) or default).expanduser().resolve()


def library_path():
    if sys.platform == 'linux':
        default = ROOT / 'linux-runtime/libfotufilm.so'
        extended = ROOT / 'linux-runtime/libfotufilm-float.so'
        device = os.environ.get('FOTUFILM_GPU_DEVICE', 'auto').lower()
        if extended.is_file() and device not in ('cpu', 'vulkan'):
            import torch
            if device == 'cuda' or torch.cuda.is_available():
                default = extended
    else:
        default = ROOT / '.runtime/native-build/release/libFotufilmHost.dylib'
    return configured_path('FOTUFILM_LIBRARY', default)


def resources_path():
    extended = ROOT / 'linux-runtime/float-resources'
    default = ROOT / 'linux-runtime/resources'
    if library_path() == (ROOT / 'linux-runtime/libfotufilm-float.so').resolve():
        default = extended
    return configured_path('FOTUFILM_RESOURCES', default)


def runtime_revision():
    """Report the installed renderer separately from a recipe's authored revision."""
    library = library_path()
    if library == (ROOT / 'linux-runtime/libfotufilm-float.so').resolve():
        installed = ROOT / 'linux-runtime/float-engine-provenance.json'
        return json.loads(installed.read_text())['upstreamCommit'] if installed.is_file() else 'unverified-runtime'
    if library in ((ROOT / 'linux-runtime/libfotufilm.so').resolve(),
                   (ROOT / '.runtime/native-build/release/libFotufilmHost.dylib').resolve()):
        return json.loads((ROOT / 'upstream/fotufilm.lock.json').read_text())['commit']
    return 'external-runtime'


def stocks_path():
    default = (resources_path() / 'Stocks' if sys.platform == 'linux'
               else ROOT / '.runtime/fotufilm/Sources/FotufilmCore/Stocks')
    return configured_path('FOTUFILM_STOCKS', default)


def stock_catalogue():
    """Inventory the installed profile bundle without starting the native renderer."""
    profiles = []
    for path in sorted(stocks_path().glob('*.json')):
        try:
            data = json.loads(path.read_text())
            if data.get('id') == path.stem:
                profiles.append(path.stem)
        except (OSError, ValueError, AttributeError):
            continue
    return {'engine': runtime_revision(), 'stocks': profiles}
