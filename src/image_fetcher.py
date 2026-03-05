from __future__ import annotations

from io import BytesIO
from pathlib import Path

import requests
from duckduckgo_search import DDGS
from PIL import Image, ImageOps

from .utils import write_json


def _resize_to_canvas(img: Image.Image, out_path: Path, width: int, height: int) -> None:
    canvas = ImageOps.fit(img.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    canvas.save(out_path, quality=95)


def _fallback_image(out_path: Path, width: int, height: int, sentence_id: str) -> None:
    # 用 picsum 保底，避免黑屏
    try:
        r = requests.get(f"https://picsum.photos/seed/{sentence_id}/{width}/{height}", timeout=20)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        _resize_to_canvas(img, out_path, width, height)
        return
    except Exception:
        pass
    Image.new("RGB", (width, height), "#223344").save(out_path, quality=95)


def _extract_query(sentence: str) -> str:
    s = sentence.replace("。", " ").replace("，", " ").strip()
    # 你的主题主要是AI/机器人，补强英文关键词提升美国区命中
    if "机器人" in s or "人工智能" in s or "AI" in s:
        return f"{s} robot artificial intelligence technology"
    return s[:80] if s else "technology"


def _ddg_first_image_url(query: str) -> str | None:
    with DDGS() as ddgs:
        results = ddgs.images(
            keywords=query,
            region="us-en",
            safesearch="moderate",
            size="Large",
            color="color",
            max_results=10,
        )
        for item in results:
            url = item.get("image") or item.get("thumbnail")
            if url and url.startswith("http"):
                return url
    return None


def fetch_images_for_sentences(audio_rows: list[dict], out_dir: str | Path, manifest_out: str | Path, cfg: dict, video_cfg: dict) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width, height = video_cfg["width"], video_cfg["height"]
    rows = []

    for row in audio_rows:
        sentence_id = row["sentence_id"]
        query = _extract_query(row["text"])
        img_out = out_dir / f"{sentence_id}.jpg"

        source = None
        ok = False
        try:
            source = _ddg_first_image_url(query)
            if source:
                r = requests.get(source, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                img = Image.open(BytesIO(r.content))
                # 过滤太小的缩略图
                if img.width >= 300 and img.height >= 300:
                    _resize_to_canvas(img, img_out, width, height)
                    ok = True
        except Exception:
            ok = False

        if not ok:
            _fallback_image(img_out, width, height, sentence_id)

        rows.append({**row, "image_path": str(img_out), "query": query, "source": source})

    write_json(manifest_out, rows)
    return rows
