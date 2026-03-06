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

echo "[1/4] 创建/更新 Conda 环境: $ENV_NAME"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda env update -n "$ENV_NAME" -f environment.yml --prune
else
  conda env create -f environment.yml
fi

echo "[2/4] 安装 Playwright Chromium"
conda run -n "$ENV_NAME" python -m playwright install chromium

echo "[3/4] 下载模型"
bash scripts/download_models.sh

echo "[4/4] 完成。首次使用请执行："
echo "  zsh scripts/run_with_conda.sh --login"
echo "然后执行："
echo "  zsh scripts/run_with_conda.sh --force-crawl"
