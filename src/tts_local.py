from __future__ import annotations

import re
from pathlib import Path
import wave

from moviepy.editor import AudioFileClip
from piper.voice import PiperVoice

from .utils import safe_filename, write_json


def _normalize_cn_text(text: str) -> str:
    text = text.replace("AI", "人工智能")
    text = re.sub(r"\s+", "", text)
    text = text.replace("...", "，")
    return text.strip("，。 ") + "。"


def _audio_duration(path: Path) -> float:
    clip = AudioFileClip(str(path))
    d = float(clip.duration)
    clip.close()
    return d


def _synthesize_piper(text: str, out_file: Path, voice: PiperVoice) -> None:
    tmp_wav = out_file.with_suffix(".wav")
    with wave.open(str(tmp_wav), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    clip = AudioFileClip(str(tmp_wav))
    clip.write_audiofile(str(out_file), verbose=False, logger=None)
    clip.close()
    tmp_wav.unlink(missing_ok=True)


def tts_batch(sent_manifest: list[dict], audio_dir: str | Path, manifest_out: str | Path, tts_cfg: dict) -> list[dict]:
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    model = Path(tts_cfg.get("piper_model", "./models/piper/zh_CN-xiao_ya-medium.onnx"))
    config = Path(tts_cfg.get("piper_config", str(model) + ".json"))
    voice = PiperVoice.load(str(model), config_path=str(config))

    rows: list[dict] = []
    for ans in sent_manifest:
        for idx, sentence in enumerate(ans["sentences"], start=1):
            sentence = _normalize_cn_text(sentence)
            sid = f"{ans['answer_id']}_s{idx:03d}_{safe_filename(sentence, 20)}"
            out_file = audio_dir / f"{sid}.mp3"

            _synthesize_piper(sentence, out_file, voice)
            duration = _audio_duration(out_file)

            rows.append(
                {
                    "sentence_id": sid,
                    "answer_id": ans["answer_id"],
                    "text": sentence,
                    "audio_path": str(out_file),
                    "duration": float(duration),
                    "source_url": ans.get("source_url", ""),
                }
            )

    write_json(manifest_out, rows)
    return rows
