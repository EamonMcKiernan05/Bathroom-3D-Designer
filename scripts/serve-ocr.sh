#!/usr/bin/env bash
# Deprecated thin wrapper — delegates to the robust, automated provisioner at
# scripts/ocr/serve.sh (downloads a prebuilt Vulkan llama.cpp + Unlimited-OCR,
# launches on 127.0.0.1:9333). Kept so old README instructions still work.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/ocr/serve.sh" "$@"
