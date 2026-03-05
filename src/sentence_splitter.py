from __future__ import annotations

import re
from pathlib import Path

from .utils import write_json


def clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(展开阅读全文|赞同 \d+|发布于.*)$", "", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    parts = re.split(r"(?<=[。！？；!?;])", text)
    out = []
    for p in parts:
        s = p.strip()
        if len(s) >= 8:
            out.append(s)
    return out


def build_sentence_manifest(raw_answers_path: str | Path, out_path: str | Path) -> list[dict]:
    import json

    raw = json.loads(Path(raw_answers_path).read_text(encoding="utf-8"))
    answers = raw.get("answers", [])
    results: list[dict] = []

    topic_hint = "机器人与人工智能"
    intro = {
        "answer_id": "narration_intro",
        "author": "narrator",
        "upvotes": 0,
        "source_url": raw.get("topic_url", ""),
        "sentences": [
            f"今日话题是{topic_hint}。",
            "我们整理了几位知乎小伙伴的观点，一起看看他们怎么说。",
        ],
    }
    results.append(intro)

    for i, ans in enumerate(answers, start=1):
        sentences = split_sentences(ans.get("text", ""))
        if not sentences:
            continue

        lead = f"第{i}位小伙伴{ans.get('author', '匿名用户')}这样说。"
        enriched = [lead] + sentences
        results.append(
            {
                "answer_id": ans["answer_id"],
                "author": ans.get("author", ""),
                "upvotes": ans.get("upvotes", 0),
                "source_url": ans.get("source_url", ""),
                "sentences": enriched,
            }
        )

    results.append(
        {
            "answer_id": "narration_outro",
            "author": "narrator",
            "upvotes": 0,
            "source_url": raw.get("topic_url", ""),
            "sentences": ["你更认同哪种观点？欢迎留言说说你的看法。"],
        }
    )

    write_json(out_path, results)
    return results
