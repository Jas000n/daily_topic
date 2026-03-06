# daily_topic

给一个知乎问题 URL，自动生成竖屏解说视频。

流程：抓回答 → 切句 → TTS → 配图 → 合成视频

---

## 0) 克隆仓库

```bash
git clone https://github.com/Jas000n/daily_topic.git
cd daily_topic
```

> 注意：`git clone` 后目录名是 `daily_topic`（不是旧的本地打包目录名）。

---

## 1) 一键准备环境

```bash
zsh scripts/setup_with_conda.sh
```

---

## 2) 登录知乎（首次或风控后）

```bash
zsh scripts/run_with_conda.sh --login --url "https://www.zhihu.com/question/48510028"
```

完成登录/验证后关闭浏览器。

---

## 3) 生成视频（推荐命令行传 URL）

```bash
zsh scripts/run_with_conda.sh --force-crawl --url "https://www.zhihu.com/question/48510028"
```

输出在：`output/sample_*.mp4`

---

## 常用配置（config.yaml）

```yaml
run:
  max_answers: 3
  keep_intermediate: false

workers: 8

video:
  fps: 30
  speech_speed: 1.15
  audio_bitrate: "96k"
  audio_fps: 22050
  audio_channels: 1

images:
  provider: "google"      # google | ddg | google_html
  google_api_key: ""      # 或环境变量 GOOGLE_API_KEY
  google_cse_cx: ""       # 或环境变量 GOOGLE_CSE_CX
```

图片检索自动兜底：

1. Google CSE
2. DDG
3. Google HTML
4. 本地兜底图

---

## 可选：配置 Google 图片 API

```bash
export GOOGLE_API_KEY="你的key"
export GOOGLE_CSE_CX="你的cx"
```

不配置也能跑，会自动回退到 DDG / HTML。

---

## 常见问题

### 40362 风控

```bash
zsh scripts/run_with_conda.sh --login --url "https://www.zhihu.com/question/48510028"
zsh scripts/run_with_conda.sh --force-crawl --url "https://www.zhihu.com/question/48510028"
```

建议同一网络连续执行。

### 配图经常兜底
- 把 `workers` 降到 4
- 配置 Google CSE key/cx

### 依赖缺失

```bash
zsh scripts/setup_with_conda.sh
```
