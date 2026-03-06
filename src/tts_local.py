from __future__ import annotations

import re
import threading
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from piper.voice import PiperVoice
from tqdm import tqdm

from .utils import safe_filename, write_json


def _normalize_cn_text(text: str) -> str:
    text = text.replace("AI", "人工智能")
    text = re.sub(r"\s+", "", text)
    text = text.replace("...", "，")
    return text.strip("，。 ") + "。"


def _audio_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        return frames / float(rate)


def _synthesize_piper(text: str, out_file: Path, voice: PiperVoice, tts_cfg: dict | None = None) -> Path:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tts_cfg = tts_cfg or {}

    # 当前 piper-tts 版本的 synthesize_wav 不支持 length_scale；
    # 若强传会抛 TypeError，甚至导致 wave 文件头未写完整。
    try:
        with wave.open(str(out_file), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
    except Exception:
        try:
            out_file.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return out_file


_VOICE_CACHE: dict[tuple[int, str, str], PiperVoice] = {}
_VOICE_LOCK = threading.Lock()


def _get_thread_voice(model: Path, config: Path) -> PiperVoice:
    key = (threading.get_ident(), str(model), str(config))
    with _VOICE_LOCK:
        voice = _VOICE_CACHE.get(key)
        if voice is None:
            voice = PiperVoice.load(str(model), config_path=str(config))
            _VOICE_CACHE[key] = voice
        return voice


def _tts_one(task: tuple[dict, int, str], model: Path, config: Path, audio_dir: Path, tts_cfg: dict) -> dict:
    ans, idx, sentence = task
    sentence = _normalize_cn_text(sentence)
    sid = f"{ans['answer_id']}_s{idx:03d}_{safe_filename(sentence, 20)}"

    out_file = audio_dir / f"{sid}.wav"
    voice = _get_thread_voice(model, config)
    real_audio_file = _synthesize_piper(sentence, out_file, voice, tts_cfg=tts_cfg)
    duration = _audio_duration(real_audio_file)

    return {
        "sentence_id": sid,
        "answer_id": ans["answer_id"],
        "text": sentence,
        "audio_path": str(real_audio_file),
        "duration": float(duration),
        "source_url": ans.get("source_url", ""),
    }


def tts_batch(
    sent_manifest: list[dict],
    audio_dir: str | Path,
    manifest_out: str | Path,
    tts_cfg: dict,
) -> list[dict]:
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    model = Path(tts_cfg.get("piper_model", "./models/piper/zh_CN-xiao_ya-medium.onnx"))
    config = Path(tts_cfg.get("piper_config", str(model) + ".json"))
    workers = int(tts_cfg.get("workers", 1))

    tasks: list[tuple[dict, int, str]] = []
    for ans in sent_manifest:
        for idx, sentence in enumerate(ans["sentences"], start=1):
            tasks.append((ans, idx, sentence))

    rows: list[dict] = []
    if workers <= 1:
        for task in tqdm(tasks, desc="[TTS] 生成语音", unit="句"):
            rows.append(_tts_one(task, model, config, audio_dir, tts_cfg))
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_tts_one, task, model, config, audio_dir, tts_cfg) for task in tasks]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"[TTS] 生成语音({workers}线程)", unit="句"):
                rows.append(fut.result())

    rows.sort(key=lambda x: x["sentence_id"])
    write_json(manifest_out, rows)
    return rows
