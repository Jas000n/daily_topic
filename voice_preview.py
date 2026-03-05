from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

VOICES = [
    "Tingting",
    "Eddy (Chinese (China mainland))",
    "Flo (Chinese (China mainland))",
    "Reed (Chinese (China mainland))",
    "Rocko (Chinese (China mainland))",
    "Sandy (Chinese (China mainland))",
    "Shelley (Chinese (China mainland))",
    "Grandma (Chinese (China mainland))",
    "Grandpa (Chinese (China mainland))",
    "Meijia",
    "Sinji",
]

TEXT = "大家好，这是一段离线中文配音测试，你可以听听这个音色是否自然。"
W, H = 1080, 1920


def _pick_font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    raise RuntimeError("No CJK font available for preview rendering")


def make_card(path: Path, voice: str):
    img = Image.new("RGB", (W, H), (20, 28, 44))
    d = ImageDraw.Draw(img)
    f1 = _pick_font(72)
    f2 = _pick_font(52)

    title = "离线 TTS 音色试听"
    body = f"音色：{voice}"
    tip = "同一文案，方便你直接对比"

    d.text((80, 260), title, font=f1, fill=(255, 255, 255))
    d.text((80, 420), body, font=f2, fill=(255, 210, 120))
    d.text((80, 520), tip, font=f2, fill=(210, 220, 235))
    d.rounded_rectangle((60, 1280, W - 60, 1700), radius=28, fill=(0, 0, 0, 120))
    d.text((90, 1350), TEXT, font=f2, fill=(255, 255, 255))
    img.save(path)


def synth(voice: str, out_aiff: Path):
    subprocess.run(["say", "-v", voice, "-r", "185", "-o", str(out_aiff), TEXT], check=True)


def main():
    base = Path(__file__).parent
    tmp = base / "data" / "cache" / "voice_preview"
    tmp.mkdir(parents=True, exist_ok=True)
    clips = []

    for i, voice in enumerate(VOICES, start=1):
        aiff = tmp / f"{i:02d}.aiff"
        png = tmp / f"{i:02d}.png"
        synth(voice, aiff)
        make_card(png, voice)

        audio = AudioFileClip(str(aiff))
        bg = ImageClip(str(png)).set_duration(audio.duration).set_audio(audio)
        clips.append(bg)

    final = concatenate_videoclips(clips, method="compose")
    out = base / "output" / f"voice_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    final.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac")

    final.close()
    for c in clips:
        c.close()

    print(out)


if __name__ == "__main__":
    main()
