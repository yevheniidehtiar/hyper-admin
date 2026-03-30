#!/usr/bin/env bash
# Sync host memory snapshot (baked at build time) into the named volume.
#
# At build time, the justfile stages the host's Claude Code project memory
# into /image-memory/ inside the image.  At container start, this script
# copies those files into the volume-backed memory directory so that Claude
# Code inside the container can read/write them.
#
# Uses `cp -u` (update) so container-written entries are not overwritten by
# an older build snapshot on restart.

set -euo pipefail

IMAGE_MEMORY="/image-memory"
VOLUME_MEMORY="/root/.claude/projects/-app/memory"

MD_COUNT=$(find "$IMAGE_MEMORY" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$MD_COUNT" -gt 0 ]; then
    mkdir -p "$VOLUME_MEMORY"
    cp -u "$IMAGE_MEMORY"/*.md "$VOLUME_MEMORY/" 2>/dev/null || true
    echo "[memory] Synced $MD_COUNT memory files from build snapshot" >&2
else
    echo "[memory] No build-time memory snapshot — container starts fresh" >&2
fi
