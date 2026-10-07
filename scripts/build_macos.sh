#!/usr/bin/env bash
set -euo pipefail
film_app="$(cd "$(dirname "$0")/.." && pwd)"
cd "$film_app"
film_commit="$(python3 -c 'import json; print(json.load(open("upstream/fotufilm.lock.json"))["commit"])')"
comfy_commit=b0b743566f65daafc423b4fea8a2fbda94b3384a
mkdir -p .runtime
if [ ! -d .runtime/fotufilm/.git ]; then
  git clone --filter=blob:none https://github.com/DhaliwalX/fotufilm-engine .runtime/fotufilm
  git -C .runtime/fotufilm checkout --detach "$film_commit"
fi
if [ "$(git -C .runtime/fotufilm rev-parse HEAD)" != "$film_commit" ]; then
  echo 'Fotufilm checkout differs from the lock file. Use a clean pinned checkout.' >&2
  exit 1
fi
if [ -z "${HALIDE_ROOT:-}" ]; then
  if [ -f .runtime/halide-bottle/halide/21.0.0_2/include/Halide.h ]; then
    export HALIDE_ROOT="$film_app/.runtime/halide-bottle/halide/21.0.0_2"
  elif command -v brew >/dev/null && brew --prefix halide >/dev/null 2>&1; then
    export HALIDE_ROOT="$(brew --prefix halide)"
  fi
fi
if [ ! -f "${HALIDE_ROOT:-/nonexistent}/include/Halide.h" ]; then
  echo 'Install Halide (brew install halide) or set HALIDE_ROOT to a Halide installation.' >&2
  exit 1
fi
swift build --package-path .runtime/fotufilm -c release --product FotufilmHost --jobs 6 --scratch-path .runtime/native-build
