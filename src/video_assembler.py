from __future__ import annotations

from pathlib import Path

from moviepy.editor import VideoFileClip, concatenate_videoclips


def assemble_video(
    clip_rows: list[dict],
    out_file: str | Path,
    fps: int = 30,
    audio_bitrate: str = "96k",
    audio_fps: int = 22050,
    audio_channels: int = 1,
) -> str:
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    clips = [VideoFileClip(r["clip_path"]) for r in sorted(clip_rows, key=lambda x: x["order"])]
    if not clips:
        raise RuntimeError("No clips were generated. Check crawling/login status and manifests.")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        str(out_file),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate=audio_bitrate,
        audio_fps=audio_fps,
        ffmpeg_params=["-ac", str(audio_channels)],
    )

    final.close()
    for c in clips:
        c.close()

    return str(out_file)
