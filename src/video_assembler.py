from __future__ import annotations

from pathlib import Path

from moviepy.editor import VideoFileClip, concatenate_videoclips


def assemble_video(clip_rows: list[dict], out_file: str | Path, fps: int = 30) -> str:
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    clips = [VideoFileClip(r["clip_path"]) for r in sorted(clip_rows, key=lambda x: x["order"])]
    if not clips:
        raise RuntimeError("No clips were generated. Check crawling/login status and manifests.")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(str(out_file), fps=fps, codec="libx264", audio_codec="aac")

    final.close()
    for c in clips:
        c.close()

    return str(out_file)
