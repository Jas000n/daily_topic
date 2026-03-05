from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_filename(text: str, max_len: int = 80) -> str:
    x = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text).strip("_")
    return x[:max_len] if len(x) > max_len else x


def random_wait(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))
