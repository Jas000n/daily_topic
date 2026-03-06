#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ENV_NAME="zhihu-video-bot"

ensure_conda() {
  if command -v conda >/dev/null 2>&1; then
    return 0
  fi

  # 兼容 zsh / 非交互 shell：尝试手动加载 conda.sh
  for base in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/anaconda3" "/opt/homebrew/Caskroom/miniforge/base"; do
    if [ -f "$base/etc/profile.d/conda.sh" ]; then
      # shellcheck disable=SC1090
      source "$base/etc/profile.d/conda.sh"
      break
    fi
  done

  command -v conda >/dev/null 2>&1
}

if ! ensure_conda; then
  echo "[ERROR] conda 不可用（zsh 下常见于 conda 未初始化）。"
  echo "请先执行：conda init zsh && exec zsh"
  exit 1
fi

# 实时输出日志：--no-capture-output + python -u，避免“看起来卡住”
conda run --no-capture-output -n "$ENV_NAME" env PYTHONUNBUFFERED=1 python -u main.py "$@"
