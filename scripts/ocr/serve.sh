#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Bathroom 3D — fully-automated local OCR/vision engine (Vulkan).
# Zero-knowledge: installs llama.cpp (Vulkan) + the Unlimited-OCR model on first
# run, launches llama-server --mmproj on 127.0.0.1:9333, verifies it, and only
# then exits 0. Safe to run repeatedly (idempotent).
#
#   Optional overrides:
#     OCR_RUNTIME   cache dir            (default: $LOCALAPPDATA/bathroom-3d-ocr)
#     LLAMA_VERSION prebuilt release tag (default b10240)
#     OCR_PORT      server port          (default 9333)
#
# On Windows run this from git-bash, or use scripts/ocr/serve.ps1.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

LLAMA_VERSION="${LLAMA_VERSION:-b10240}"
OCR_PORT="${OCR_PORT:-9333}"
WIN_ARCH="win-vulkan-x64"
HOST="127.0.0.1"

# Choose the engine's vision model.
#   OCR_MODEL=gemma  (default) -> Gemma 4 E4B it (general instruction-following VLM;
#        best fit for "understand plan -> emit room JSON").
#   OCR_MODEL=ocr    -> Unlimited-OCR (DeepSeek-OCR). SOTA text-region OCR, but outputs
#        OCR token streams, NOT room JSON — only useful if you re-parse regions yourself.
OCR_MODEL="${OCR_MODEL:-gemma}"
case "$OCR_MODEL" in
  gemma)
    MODEL_REPO="unsloth/gemma-4-E4B-it-GGUF"
    TEXT_Q="gemma-4-E4B-it-Q4_K_M.gguf"
    PROJ_Q="mmproj-gemma-4-E4B-F16.gguf"
    ;;
  ocr)
    MODEL_REPO="sahilchachra/Unlimited-OCR-GGUF"
    TEXT_Q="Unlimited-OCR-Q4_K_M.gguf"
    PROJ_Q="mmproj-Unlimited-OCR-F16.gguf"
    ;;
  *)
    echo "[ocr] unknown OCR_MODEL '$OCR_MODEL' (use gemma or ocr)"; exit 6 ;;
esac

if [ -n "${LOCALAPPDATA:-}" ]; then
  DEFAULT_RUNTIME="$LOCALAPPDATA/bathroom-3d-ocr"
else
  DEFAULT_RUNTIME="$HOME/.local/share/bathroom-ocr"
fi
RUNTIME="${OCR_RUNTIME:-$DEFAULT_RUNTIME}"
LLAMA_DIR="$RUNTIME/llama"
LLAMA_EXE="$LLAMA_DIR/llama-server.exe"
MODEL_DIR="$RUNTIME/models"

# fail gracefully: missing curl/unzip
for tool in curl unzip; do command -v "$tool" >/dev/null 2>&1 || { echo "[ocr] missing '$tool' — install it (git-bash has both)."; exit 3; }; done

ensure_llama() {
  if [ -x "$LLAMA_EXE" ]; then
    echo "[ocr] llama-server present: $LLAMA_EXE"
    return 0
  fi
  echo "[ocr] downloading llama.cpp $LLAMA_VERSION Vulkan (prebuilt, no build needed)..."
  mkdir -p "$LLAMA_DIR"
  local zip="$RUNTIME/llama-${LLAMA_VERSION}-${WIN_ARCH}.zip"
  curl -sL -o "$zip" "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_VERSION}/llama-${LLAMA_VERSION}-bin-${WIN_ARCH}.zip"
  unzip -o -q "$zip" -d "$LLAMA_DIR"
  rm -f "$zip"
  if [ ! -x "$LLAMA_EXE" ]; then
    # zip may extract into a subdir — find it
    local found; found="$(find "$LLAMA_DIR" -name llama-server.exe | head -1)"
    if [ -n "$found" ]; then
      cp "$found" "$LLAMA_DIR/llama-server.exe"
    else
      echo "[ocr] llama-server.exe not found after extraction"; exit 4
    fi
  fi
}

ensure_models() {
  mkdir -p "$MODEL_DIR"
  for f in "$TEXT_Q" "$PROJ_Q"; do
    if [ ! -f "$MODEL_DIR/$f" ] || [ "$(stat -c%s "$MODEL_DIR/$f" 2>/dev/null || echo 0)" -lt 100000000 ]; then
      echo "[ocr] downloading model file $f ..."
      curl -sL -o "$MODEL_DIR/$f" "https://huggingface.co/${MODEL_REPO}/resolve/main/${f}"
    fi
  done
  echo "[ocr] models ready: $TEXT_Q + $PROJ_Q"
}

already_online() {
  curl -s --max-time 2 "http://${HOST}:${OCR_PORT}/v1/models" >/dev/null 2>&1
}

ensure_llama
ensure_models

if already_online; then
  echo "[ocr] engine already running on ${HOST}:${OCR_PORT}."
else
  echo "[ocr] launching llama-server (Vulkan) on ${HOST}:${OCR_PORT}..."
  LOG="$RUNTIME/server.log"
  # Detach so it survives this script (Windows git-bash friendly).
  ( cd "$MODEL_DIR" && nohup "$LLAMA_EXE" -m "$MODEL_DIR/$TEXT_Q" --mmproj "$MODEL_DIR/$PROJ_Q" \
        -ngl 999 -c 8192 --host "$HOST" --port "$OCR_PORT" > "$LOG" 2>&1 & )
  # wait for readiness (Vulkan init + model load can take 10-60s)
  for i in $(seq 1 90); do
    if already_online; then
      echo "[ocr] engine ONLINE after ~${i}s. Ready for photo->plan import."
      exit 0
    fi
    sleep 1
  done
  echo "[ocr] engine failed to come online. Last log lines:"
  tail -30 "$LOG" 2>/dev/null || true
  exit 5
fi
