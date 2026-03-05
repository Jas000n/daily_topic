from __future__ import annotations

from pathlib import Path

from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont

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


def build_clips(image_rows: list[dict], clips_dir: str | Path, manifest_out: str | Path, video_cfg: dict) -> list[dict]:
    clips_dir = Path(clips_dir)
    clips_dir.mkdir(parents=True, exist_ok=True)

    result = []
    for i, row in enumerate(image_rows, start=1):
        duration = max(float(row["duration"]), float(video_cfg.get("min_sentence_duration_sec", 2.0)))

        bg = ImageClip(row["image_path"]).set_duration(duration)
        bg = bg.resize((video_cfg["width"], video_cfg["height"]))

        sub_png = clips_dir / f"sub_{i:04d}.png"
        _build_subtitle_png(row["text"], sub_png, video_cfg["width"], video_cfg["height"], video_cfg.get("font_size", 52))
        subtitle = ImageClip(str(sub_png)).set_duration(duration)

        audio = AudioFileClip(row["audio_path"])
        comp = CompositeVideoClip([bg, subtitle]).set_audio(audio)

        clip_path = clips_dir / f"clip_{i:04d}.mp4"
        comp.write_videofile(
            str(clip_path),
            fps=video_cfg.get("fps", 30),
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )
        comp.close()
        audio.close()

        result.append({**row, "clip_path": str(clip_path), "order": i})

    write_json(manifest_out, result)
    return result
