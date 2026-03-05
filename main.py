from __future__ import annotations

import argparse
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


def run(cfg: dict):
    base = Path(__file__).parent
    data = base / "data"
    manifests = data / "manifests"
    state = StateManager(manifests / "job_state.json")

    raw_answers_path = data / "raw" / "answers.json"
    sentence_path = data / "clean" / "sentences.json"
    audio_manifest_path = manifests / "audio_manifest.json"
    image_manifest_path = manifests / "image_manifest.json"
    clip_manifest_path = manifests / "clip_manifest.json"

    if not state.get("zhihu_crawled"):
        answers = crawl_topic(
            cfg["run"]["topic_url"],
            raw_answers_path,
            cfg["run"].get("max_answers", 3),
            cfg["browser"],
        )
        state.set("zhihu_crawled", True)
        state.set("answers_count", len(answers))

    if not state.get("sentences_ready"):
        sent_manifest = build_sentence_manifest(raw_answers_path, sentence_path)
        state.set("sentences_ready", True)
        state.set("answer_groups", len(sent_manifest))
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

    if not state.get("tts_done"):
        audio_rows = tts_batch(sent_manifest, data / "audio", audio_manifest_path, cfg["tts"])
        state.set("tts_done", True)
        state.set("tts_count", len(audio_rows))
    else:
        import json

        audio_rows = json.loads(audio_manifest_path.read_text(encoding="utf-8"))

    if not state.get("images_done"):
        image_rows = fetch_images_for_sentences(audio_rows, data / "images", image_manifest_path, cfg["images"], cfg["video"])
        state.set("images_done", True)
        state.set("images_count", len(image_rows))
    else:
        import json

        image_rows = json.loads(image_manifest_path.read_text(encoding="utf-8"))

    if not state.get("clips_done"):
        clip_rows = build_clips(image_rows, data / "clips", clip_manifest_path, cfg["video"])
        state.set("clips_done", True)
        state.set("clips_count", len(clip_rows))
    else:
        import json

        clip_rows = json.loads(clip_manifest_path.read_text(encoding="utf-8"))

    if not state.get("final_video_done"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = base / "output" / f"{cfg['run'].get('output_name', 'sample')}_{ts}.mp4"
        final_path = assemble_video(clip_rows, output, fps=cfg["video"].get("fps", 30))
        state.set("final_video_done", True)
        state.set("final_video", final_path)

    print("DONE", state.get("final_video"))


def login_zhihu(cfg: dict):
    """首次运行：打开浏览器让用户手动登录知乎，之后会保存登录态"""
    from src.crawler_zhihu import open_browser_for_login

    open_browser_for_login(cfg["run"]["topic_url"], cfg["browser"])
    print("登录成功后关闭浏览器即可。下次运行将自动使用已保存的登录态。")


def main():
    parser = argparse.ArgumentParser(description="知乎视频生成工具")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--login", action="store_true", help="仅打开浏览器进行知乎登录（首次必做）")
    args = parser.parse_args()

    cfg = load_cfg(args.config)

    if args.login:
        login_zhihu(cfg)
    else:
        run(cfg)


if __name__ == "__main__":
    main()
