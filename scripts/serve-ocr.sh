#!/usr/bin/env bash
# Serve the Unlimited-OCR vision model locally for bathroom photo->plan scanning.
#   - Downloads the GGUF + mmproj from HuggingFace (MIT) if not already present.
#   - Launches llama-server with --mmproj on port 9333 (OpenAI-compatible).
#
# Licensing: llama.cpp is MIT (ggml authors); Unlimited-OCR is MIT (baidu/DeepSeek).
# IMPORTANT: Unlimited-OCR uses the DeepSeek-OCR architecture and needs a llama.cpp
# build with that support (PR #17400, not yet in upstream main). Your llama-server
# binary must be built from that branch, e.g.:
#   git fetch origin pull/24975/head:pr24975 && git checkout pr24975
#   cmake -B build -DGGML_CUDA=ON && cmake --build build -j --target llama-server
# Point LLAMA_SERVER below at that binary. If you'd rather use a stock build, swap
# PLAN_VISION_MODEL in the app to a Gemma 4 E2B/12B GGUF (same OpenAI interface).
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-llama-server}"
MODEL_DIR="${MODEL_DIR:-$HOME/.local/share/bathroom-ocr}"
PORT="${OCR_PORT:-9333}"

REPO_OWNER_MODEL="sahilchachra/Unlimited-OCR-GGUF"
TEXT_Q="Unlimited-OCR-Q4_K_M.gguf"      # ~1.8GB, recommended default
PROJ_Q="mmproj-Unlimited-OCR-F16.gguf"  # required, 774MB

mkdir -p "$MODEL_DIR"
cd "$MODEL_DIR"

if [[ ! -f "$TEXT_Q" ]]; then
  echo "[serve-ocr] Downloading $TEXT_Q (~1.8GB, MIT)..."
  curl -L -o "$TEXT_Q" "https://huggingface.co/$REPO_OWNER_MODEL/resolve/main/$TEXT_Q?download=true"
fi
if [[ ! -f "$PROJ_Q" ]]; then
  echo "[serve-ocr] Downloading $PROJ_Q (~774MB)..."
  curl -L -o "$PROJ_Q" "https://huggingface.co/$REPO_OWNER_MODEL/resolve/main/$PROJ_Q?download=true"
fi

echo "[serve-ocr] Starting llama-server (vision) on port $PORT..."
exec "$LLAMA_SERVER" \
  -m "$MODEL_DIR/$TEXT_Q" \
  --mmproj "$MODEL_DIR/$PROJ_Q" \
  -c 8192 --host 127.0.0.1 --port "$PORT"
