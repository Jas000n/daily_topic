from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import read_json, write_json


class StateManager:
    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)
        self.state: dict[str, Any] = read_json(self.state_path, default={})

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value
        self.flush()

    def flush(self) -> None:
        write_json(self.state_path, self.state)
