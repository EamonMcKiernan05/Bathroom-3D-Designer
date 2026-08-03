# ────────────────────────────────────────────────────────────────────────────
# Bathroom 3D — fully-automated local OCR/vision engine (Vulkan) — PowerShell.
# Right-click -> "Run with PowerShell", or the app calls this. First run
# downloads llama.cpp (Vulkan) + Unlimited-OCR (~2.6GB), then starts the server
# on 127.0.0.1:9333. Idempotent; safe to re-run.
# ────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$LLAMA_VERSION = if ($env:LLAMA_VERSION) { $env:LLAMA_VERSION } else { "b10240" }
$OCR_PORT      = if ($env:OCR_PORT)      { $env:OCR_PORT }      else { 9333 }
$HOST          = "127.0.0.1"
$DEFAULT_RUNTIME = Join-Path $env:LOCALAPPDATA "bathroom-3d-ocr"
$RUNTIME  = if ($env:OCR_RUNTIME) { $env:OCR_RUNTIME } else { $DEFAULT_RUNTIME }
$LLAMA_DIR = Join-Path $RUNTIME "llama"
$MODEL_DIR = Join-Path $RUNTIME "models"
New-Item -ItemType Directory -Force -Path $LLAMA_DIR, $MODEL_DIR | Out-Null
$LLAMA_EXE = Join-Path $LLAMA_DIR "llama-server.exe"
# Choose engine vision model: gemma (default, instruction-following VLM) or ocr (Unlimited-OCR).
$OCR_MODEL = if ($env:OCR_MODEL) { $env:OCR_MODEL } else { "gemma" }
if ($OCR_MODEL -eq "ocr") {
  $TEXT_Q = "Unlimited-OCR-Q4_K_M.gguf"; $PROJ_Q = "mmproj-Unlimited-OCR-F16.gguf"; $MODEL_REPO = "sahilchachra/Unlimited-OCR-GGUF"
} else {
  $TEXT_Q = "gemma-4-E4B-it-Q4_K_M.gguf"; $PROJ_Q = "mmproj-gemma-4-E4B-F16.gguf"; $MODEL_REPO = "unsloth/gemma-4-E4B-it-GGUF"
}

function Test-Online { param([int]$Port) try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://${HOST}:${Port}/v1/models").StatusCode -eq 200 } catch { $false } }
function Get-FileIfMissing { param([string]$Dest, [string]$Url, [string]$Name) if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 100MB)) { Write-Host "[ocr] present: $Name" } else { Write-Host "[ocr] downloading $Name ..."; Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Dest } }

if (-not (Test-Path $LLAMA_EXE)) {
  Write-Host "[ocr] downloading llama.cpp $LLAMA_VERSION Vulkan ..."
  $zip = Join-Path $RUNTIME "llama-$LLAMA_VERSION.zip"
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_VERSION/llama-$LLAMA_VERSION-bin-win-vulkan-x64.zip" -OutFile $zip
  Expand-Archive -Force -Path $zip -DestinationPath $LLAMA_DIR
  Remove-Item $zip -Force
  if (-not (Test-Path $LLAMA_EXE)) {
    $found = Get-ChildItem -Path $LLAMA_DIR -Recurse -Filter llama-server.exe | Select-Object -First 1
    if ($found) { Copy-Item $found.FullName $LLAMA_EXE } else { throw "llama-server.exe not found after extraction" }
  }
} else { Write-Host "[ocr] llama-server present" }

Get-FileIfMissing (Join-Path $MODEL_DIR $TEXT_Q) "https://huggingface.co/$MODEL_REPO/resolve/main/$TEXT_Q" $TEXT_Q
Get-FileIfMissing (Join-Path $MODEL_DIR $PROJ_Q) "https://huggingface.co/$MODEL_REPO/resolve/main/$PROJ_Q" $PROJ_Q

if (Test-Online $OCR_PORT) {
  Write-Host "[ocr] engine already running on ${HOST}:${OCR_PORT}."
  exit 0
}
Write-Host "[ocr] launching llama-server (Vulkan) on ${HOST}:${OCR_PORT} ..."
$log = Join-Path $RUNTIME "server.log"
$p = Start-Process -FilePath $LLAMA_EXE -ArgumentList "-m",(Join-Path $MODEL_DIR $TEXT_Q),"--mmproj",(Join-Path $MODEL_DIR $PROJ_Q),"-ngl","999","-c","8192","--host",$HOST,"--port",$OCR_PORT -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden -PassThru
for ($i = 0; $i -lt 90; $i++) { if (Test-Online $OCR_PORT) { Write-Host "[ocr] engine ONLINE (~${i}s). Ready for photo->plan import."; exit 0 }; Start-Sleep -Seconds 1 }
Write-Host "[ocr] engine failed to come online. Check $log $log.err"
exit 5
