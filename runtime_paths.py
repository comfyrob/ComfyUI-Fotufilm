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
    else:
        default = ROOT / '.runtime/native-build/release/libFotufilmHost.dylib'
    return configured_path('FOTUFILM_LIBRARY', default)


def stocks_path():
    default = (ROOT / 'linux-runtime/resources/Stocks' if sys.platform == 'linux'
               else ROOT / '.runtime/fotufilm/Sources/FotufilmCore/Stocks')
    return configured_path('FOTUFILM_STOCKS', default)
