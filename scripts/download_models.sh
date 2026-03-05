#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p g2pW models/piper

echo "[1/4] Download g2pW model..."
curl -L -o g2pW/g2pw.onnx \
  https://huggingface.co/dkounadis/artificial_intelligence/raw/main/g2pW/g2pw.onnx

echo "[2/4] Download Piper xiaoya model..."
curl -L -o models/piper/zh_CN-xiao_ya-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium/zh_CN-xiao_ya-medium.onnx

echo "[3/4] Download Piper xiaoya config..."
curl -L -o models/piper/zh_CN-xiao_ya-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium/zh_CN-xiao_ya-medium.onnx.json

echo "[4/4] Optional huayan model (comment out if not needed)..."
curl -L -o models/piper/zh_CN-huayan-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx || true
curl -L -o models/piper/zh_CN-huayan-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json || true

echo "Done."
