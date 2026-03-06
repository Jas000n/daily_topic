from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import moviepy.video.fx.all as vfx
from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]

from .utils import write_json


def _build_subtitle_png(text: str, out_path: Path, width: int, height: int, font_size: int = 52) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = None
    for fp in CJK_FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(fp, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    box_w = width - 120
    # naive wrap
    def _measure(s: str) -> float:
        try:
            return float(draw.textlength(s, font=font))
        except Exception:
            return len(s) * font_size * 0.6

    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if _measure(test) > box_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)

    line_h = int(font_size * 1.4)
    box_h = line_h * len(lines) + 40
    y0 = height - box_h - 140

    draw.rounded_rectangle((40, y0, width - 40, y0 + box_h), radius=24, fill=(0, 0, 0, 135))

    y = y0 + 20
    for line in lines:
        w = _measure(line)
        x = (width - w) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    img.save(out_path)


def _build_one_clip(i: int, row: dict, clips_dir: Path, video_cfg: dict) -> dict:
    audio = AudioFileClip(row["audio_path"])
    duration = max(float(audio.duration), float(video_cfg.get("min_sentence_duration_sec", 2.0)))

    bg = ImageClip(row["image_path"]).set_duration(duration)
    bg = bg.resize((video_cfg["width"], video_cfg["height"]))

    sub_png = clips_dir / f"sub_{i:04d}.png"
    _build_subtitle_png(row["text"], sub_png, video_cfg["width"], video_cfg["height"], video_cfg.get("font_size", 52))
    subtitle = ImageClip(str(sub_png)).set_duration(duration)

    comp = CompositeVideoClip([bg, subtitle]).set_audio(audio)

    speech_speed = float(video_cfg.get("speech_speed", 1.0))
    if speech_speed > 0 and abs(speech_speed - 1.0) > 1e-3:
        comp = comp.fx(vfx.speedx, speech_speed)

    clip_path = clips_dir / f"clip_{i:04d}.mp4"
    audio_bitrate = str(video_cfg.get("audio_bitrate", "96k"))
    audio_fps = int(video_cfg.get("audio_fps", 22050))
    audio_channels = int(video_cfg.get("audio_channels", 1))

    comp.write_videofile(
        str(clip_path),
        fps=video_cfg.get("fps", 30),
        codec="libx264",
        audio_codec="aac",
        audio_bitrate=audio_bitrate,
        audio_fps=audio_fps,
        ffmpeg_params=["-ac", str(audio_channels)],
        verbose=False,
        logger="bar",
    )
    comp.close()
    audio.close()

    return {**row, "clip_path": str(clip_path), "order": i}


def build_clips(image_rows: list[dict], clips_dir: str | Path, manifest_out: str | Path, video_cfg: dict) -> list[dict]:
    clips_dir = Path(clips_dir)
    clips_dir.mkdir(parents=True, exist_ok=True)

    workers = int(video_cfg.get("workers", 1))
    indexed = list(enumerate(image_rows, start=1))

    result = []
    if workers <= 1:
        for i, row in tqdm(indexed, desc="[CLIP] 生成分镜", unit="段"):
            result.append(_build_one_clip(i, row, clips_dir, video_cfg))
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_build_one_clip, i, row, clips_dir, video_cfg) for i, row in indexed]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"[CLIP] 生成分镜({workers}线程)", unit="段"):
                result.append(fut.result())

    result.sort(key=lambda x: x["order"])
    write_json(manifest_out, result)
    return result
