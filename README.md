# zhihu_video_bot

知乎话题短视频生成工具：自动抓取回答 → 离线中文 TTS → 配图 → 合成竖屏视频

---

## 快速开始

```bash
# 1. 创建 Conda 环境
conda env create -f environment.yml
conda activate zhihu-video-bot

# 2. 安装 Playwright
python -m playwright install chromium

# 3. 下载大模型（必做）
bash scripts/download_models.sh

# 4. 首次登录知乎（必做）
python main.py --login
# 会弹出浏览器，在浏览器中登录知乎，然后关闭浏览器窗口即可

# 5. 运行生成视频
python main.py
# 产物：output/sample_*.mp4
```

---

## 依赖

- Python 3.11 + Conda
- ffmpeg（视频合成）
- 主要依赖：`playwright`, `piper-tts`, `duckduckgo-search`, `moviepy`, `Pillow`

---

## 配置（config.yaml）

```yaml
run:
  topic_url: "https://www.zhihu.com/topic/19554298/hot"  # 话题地址
  max_answers: 3                                          # 抓取回答数

video:
  width: 1080
  height: 1920
  fps: 30
```

---

## 命令

| 命令 | 说明 |
|------|------|
| `python main.py --login` | 首次登录知乎（打开浏览器手动登录） |
| `python main.py` | 运行完整流程生成视频 |

---

## 输出

- 最终视频：`output/sample_*.mp4`
- 中间文件：`data/` 目录

---

## 故障排查

- **卡住不动**：网络或知乎反爬，等待或换 VPN
- **登录失效**：重新运行 `python main.py --login`
- **TTS 报错**：确认模型文件已下载（`scripts/download_models.sh`）
