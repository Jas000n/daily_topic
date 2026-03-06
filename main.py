from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from src.clip_builder import build_clips
from src.crawler_zhihu import crawl_topic
from src.image_fetcher import fetch_images_for_sentences
from src.sentence_splitter import build_sentence_manifest
from src.state_manager import StateManager
from src.tts_local import tts_batch
from src.video_assembler import assemble_video


def load_cfg(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _reset_pipeline_state(state: StateManager) -> None:
    defaults = {
        "zhihu_crawled": False,
        "answers_count": 0,
        "sentences_ready": False,
        "answer_groups": 0,
        "tts_done": False,
        "tts_count": 0,
        "images_done": False,
        "images_count": 0,
        "clips_done": False,
        "clips_count": 0,
        "final_video_done": False,
        "final_video": "",
    }
    for k, v in defaults.items():
        state.set(k, v)


def run(cfg: dict, force_crawl: bool = False, topic_url_override: str | None = None):
    print("[START] 开始执行视频生成流程")
    base = Path(__file__).parent
    data = base / "data"
    manifests = data / "manifests"
    state = StateManager(manifests / "job_state.json")

    raw_answers_path = data / "raw" / "answers.json"
    sentence_path = data / "clean" / "sentences.json"
    audio_manifest_path = manifests / "audio_manifest.json"
    image_manifest_path = manifests / "image_manifest.json"
    clip_manifest_path = manifests / "clip_manifest.json"

    topic_url = (topic_url_override or cfg["run"]["topic_url"]).strip()
    if topic_url_override:
        print(f"[cfg] 使用命令行传入 URL: {topic_url}")

    resume = cfg.get("run", {}).get("resume", True)
    if not resume:
        _reset_pipeline_state(state)

    need_recrawl = force_crawl or (not state.get("zhihu_crawled")) or (state.get("answers_count", 0) == 0)

    if need_recrawl:
        print("[1/6] 正在抓取知乎回答...")
        answers = crawl_topic(
            topic_url,
            raw_answers_path,
            cfg["run"].get("max_answers", 3),
            cfg["browser"],
        )
        print(f"[1/6] 抓取完成：{len(answers)} 条")
        state.set("zhihu_crawled", True)
        state.set("answers_count", len(answers))

        # 若重新抓取，后续步骤必须重建
        for k in ["sentences_ready", "tts_done", "images_done", "clips_done", "final_video_done"]:
            state.set(k, False)
    else:
        print(f"[1/6] 使用缓存回答：{state.get('answers_count', 0)} 条")

    if not state.get("sentences_ready"):
        print("[2/6] 正在切分文案...")
        sent_manifest = build_sentence_manifest(raw_answers_path, sentence_path)
        state.set("sentences_ready", True)
        state.set("answer_groups", len(sent_manifest))
        print(f"[2/6] 切分完成：{len(sent_manifest)} 组")
    else:
        import json

        sent_manifest = json.loads(sentence_path.read_text(encoding="utf-8"))

    if not sent_manifest:
        sent_manifest = [
            {
                "answer_id": "demo_001",
                "author": "system",
                "upvotes": 0,
                "source_url": "demo://fallback",
                "sentences": [
                    "机器人与人工智能正在从实验室走向真实产业场景。",
                    "在制造业里，机器人负责重复动作，人工智能负责感知与决策。",
                    "当视觉识别、路径规划和实时控制结合时，系统效率会显著提升。",
                    "未来的关键不是机器人替代人，而是人机协作重构工作流程。",
                ],
            }
        ]

    workers = int(cfg.get("workers", cfg.get("tts", {}).get("workers", 1)))

    if not state.get("tts_done"):
        print(f"[3/6] 正在生成语音... (workers={workers})")
        tts_cfg = dict(cfg["tts"])
        tts_cfg["workers"] = workers
        audio_rows = tts_batch(sent_manifest, data / "audio", audio_manifest_path, tts_cfg)
        state.set("tts_done", True)
        state.set("tts_count", len(audio_rows))
        print(f"[3/6] 语音完成：{len(audio_rows)} 条")
    else:
        import json

        audio_rows = json.loads(audio_manifest_path.read_text(encoding="utf-8"))

    if not state.get("images_done"):
        print(f"[4/6] 正在抓取配图... (workers={workers})")
        images_cfg = dict(cfg["images"])
        images_cfg["workers"] = workers
        image_rows = fetch_images_for_sentences(audio_rows, data / "images", image_manifest_path, images_cfg, cfg["video"])
        state.set("images_done", True)
        state.set("images_count", len(image_rows))
        print(f"[4/6] 配图完成：{len(image_rows)} 张")
    else:
        import json

        image_rows = json.loads(image_manifest_path.read_text(encoding="utf-8"))

    if not state.get("clips_done"):
        print(f"[5/6] 正在合成分镜... (workers={workers})")
        video_cfg = dict(cfg["video"])
        video_cfg["workers"] = workers
        clip_rows = build_clips(image_rows, data / "clips", clip_manifest_path, video_cfg)
        state.set("clips_done", True)
        state.set("clips_count", len(clip_rows))
        print(f"[5/6] 分镜完成：{len(clip_rows)} 段")
    else:
        import json

        clip_rows = json.loads(clip_manifest_path.read_text(encoding="utf-8"))

    if not state.get("final_video_done"):
        print("[6/6] 正在拼接最终视频...")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = base / "output" / f"{cfg['run'].get('output_name', 'sample')}_{ts}.mp4"
        final_path = assemble_video(
            clip_rows,
            output,
            fps=cfg["video"].get("fps", 30),
            audio_bitrate=str(cfg["video"].get("audio_bitrate", "96k")),
            audio_fps=int(cfg["video"].get("audio_fps", 22050)),
            audio_channels=int(cfg["video"].get("audio_channels", 1)),
        )
        state.set("final_video_done", True)
        state.set("final_video", final_path)

    if not bool(cfg.get("run", {}).get("keep_intermediate", False)):
        print("[cleanup] 清理中间产物（audio/images/clips）...")
        for p in [data / "audio", data / "images", data / "clips"]:
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)

    print("[DONE]", state.get("final_video"))


def login_zhihu(cfg: dict, url_override: str | None = None):
    """首次运行：打开浏览器让用户手动登录知乎，之后会保存登录态"""
    from src.crawler_zhihu import open_browser_for_login

    login_url = (url_override or cfg["run"]["topic_url"]).strip()
    open_browser_for_login(login_url, cfg["browser"])
    print("已保存登录态。下次运行将自动使用该登录态。")


def main():
    parser = argparse.ArgumentParser(description="知乎视频生成工具")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--login", action="store_true", help="仅打开浏览器进行知乎登录（首次必做）")
    parser.add_argument("--force-crawl", action="store_true", help="忽略缓存，强制重新抓取知乎回答")
    parser.add_argument("--url", help="运行时传入知乎链接（问题/话题），优先级高于 config.yaml")
    args = parser.parse_args()

    cfg = load_cfg(args.config)

    if args.login:
        login_zhihu(cfg, url_override=args.url)
    else:
        run(cfg, force_crawl=args.force_crawl, topic_url_override=args.url)


if __name__ == "__main__":
    main()
