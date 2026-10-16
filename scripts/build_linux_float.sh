#!/usr/bin/env bash
# Build on a Linux x86-64 worker with Swift 6.2 and Halide 21.0.0 installed.
set -euo pipefail
film_pack="$(cd "$(dirname "$0")/.." && pwd)"
film_checkout="${1:?Pass a clean supported Fotufilm checkout}"
: "${HALIDE_ROOT:?Set HALIDE_ROOT to the Halide 21.0.0 SDK}"
if [ ! -f "$film_checkout/.comfy-float-input-v1" ]; then
  python3 "$film_pack/scripts/prepare_float_engine.py" "$film_checkout"
fi
(cd "$film_checkout" && bash cef/build-engine-linux.sh)
mkdir -p "$film_pack/linux-runtime"
cp "$film_checkout/build/cef-engine/libfotufilm.so" "$film_pack/linux-runtime/libfotufilm-float.so"
mkdir -p "$film_pack/linux-runtime/float-resources"
cp -a "$film_checkout/build/cef-engine/Resources/." "$film_pack/linux-runtime/float-resources/"
git -C "$film_checkout" rev-parse HEAD | python3 -c 'import json,sys; json.dump({"upstreamCommit":sys.stdin.read().strip()},open(sys.argv[1],"w"))' "$film_pack/linux-runtime/float-engine-provenance.json"
printf '%s\n' 'Built the CUDA float-input extension. Run install.py first for stock resources and dependencies.'
