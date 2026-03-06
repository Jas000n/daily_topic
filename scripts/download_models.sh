#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p g2pW models/piper

echo "[1/4] Download g2pW model..."
# g2pw.onnx 需要 152MB，可从以下地址下载（如果链接失效请自行搜索）
# curl -L -o g2pW/g2pw.onnx https://your-mirror-url/g2pw.onnx
echo "请手动复制 g2pw.onnx 到 g2pW/ 目录（152MB）"

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
