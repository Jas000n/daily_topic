from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
import os
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from PIL import Image, ImageOps
from tqdm import tqdm

from .utils import write_json


def _resize_to_canvas(img: Image.Image, out_path: Path, width: int, height: int) -> None:
    canvas = ImageOps.fit(img.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    canvas.save(out_path, quality=95)


def _fallback_image(out_path: Path, width: int, height: int, sentence_id: str) -> None:
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
    s = re.sub(r"\s+", " ", s)
    s = s[:120]
    if "机器人" in s or "人工智能" in s or "AI" in s:
        return f"{s} robot artificial intelligence technology"
    return s if s else "technology"


def _try_download_image(source: str, out_path: Path, width: int, height: int) -> bool:
    r = requests.get(source, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    img = Image.open(BytesIO(r.content))
    if img.width < 300 or img.height < 300:
        return False
    _resize_to_canvas(img, out_path, width, height)
    return True


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


def _google_cse_first_image_url(query: str, cfg: dict) -> str | None:
    api_key = cfg.get("google_api_key") or os.getenv("GOOGLE_API_KEY")
    cx = cfg.get("google_cse_cx") or os.getenv("GOOGLE_CSE_CX")
    if not api_key or not cx:
        return None

    r = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": api_key,
            "cx": cx,
            "q": query,
            "searchType": "image",
            "num": 5,
            "safe": "active",
            "gl": "us",
            "hl": "en",
        },
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    for item in data.get("items", []):
        url = item.get("link")
        if url and url.startswith("http"):
            return url
    return None


def _google_html_first_image_url(query: str, cfg: dict) -> str | None:
    base_url = cfg.get("google_html_base_url", "https://www.google.com/search")
    headers = cfg.get("google_html_headers") or {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(f"{base_url}?q={quote_plus(query)}&tbm=isch", headers=headers, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("http"):
            continue
        if "gstatic.com" in src:
            continue
        return src
    return None


def _provider_chain(preferred: str) -> list[str]:
    preferred = preferred.lower().strip()
    if preferred == "google":
        return ["google_cse", "ddg", "google_html"]
    if preferred == "ddg":
        return ["ddg", "google_cse", "google_html"]
    if preferred in {"google_html", "google-scrape"}:
        return ["google_html", "google_cse", "ddg"]
    return ["google_cse", "ddg", "google_html"]


def _resolve_source(query: str, cfg: dict) -> tuple[str | None, str | None]:
    for provider in _provider_chain(str(cfg.get("provider", "google"))):
        try:
            if provider == "google_cse":
                url = _google_cse_first_image_url(query, cfg)
            elif provider == "ddg":
                url = _ddg_first_image_url(query)
            else:
                url = _google_html_first_image_url(query, cfg)
            if url:
                return url, provider
        except Exception:
            continue
    return None, None


def _fetch_one_image(row: dict, out_dir: Path, width: int, height: int, cfg: dict) -> dict:
    sentence_id = row["sentence_id"]
    query = _extract_query(row["text"])
    img_out = out_dir / f"{sentence_id}.jpg"

    source = None
    source_provider = None
    ok = False

    source, source_provider = _resolve_source(query, cfg)
    if source:
        try:
            ok = _try_download_image(source, img_out, width, height)
        except Exception:
            ok = False

    if not ok:
        _fallback_image(img_out, width, height, sentence_id)

    return {
        **row,
        "image_path": str(img_out),
        "query": query,
        "source": source,
        "source_provider": source_provider or "fallback",
    }


def fetch_images_for_sentences(audio_rows: list[dict], out_dir: str | Path, manifest_out: str | Path, cfg: dict, video_cfg: dict) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width, height = video_cfg["width"], video_cfg["height"]
    workers = int(cfg.get("workers", 1))

    rows = []
    if workers <= 1:
        for row in tqdm(audio_rows, desc="[IMG] 抓取配图", unit="张"):
            rows.append(_fetch_one_image(row, out_dir, width, height, cfg))
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_fetch_one_image, row, out_dir, width, height, cfg) for row in audio_rows]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"[IMG] 抓取配图({workers}线程)", unit="张"):
                rows.append(fut.result())

    rows.sort(key=lambda x: x["sentence_id"])
    write_json(manifest_out, rows)
    return rows
