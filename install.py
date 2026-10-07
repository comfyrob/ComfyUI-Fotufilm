"""Install the pinned native runtime, without downloading any AI models."""
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    if sys.platform == 'linux' and platform.machine() in ('x86_64', 'AMD64'):
        subprocess.run([sys.executable, str(ROOT / 'scripts/install_linux.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts/check_runtime.py')], check=True)
    elif sys.platform == 'darwin':
        print('Nodes installed. Build the native runtime with bash scripts/build_macos.sh, '
              'or configure an existing pinned library in runtime.local.json. See README.md.')
    else:
        raise SystemExit('Native runtime supported on Linux x86-64 and macOS. Windows/WSL ARM are not supported.')
