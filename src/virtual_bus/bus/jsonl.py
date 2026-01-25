from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import threading


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Truncate on startup for "fresh run" behavior
        self.path.write_text("", encoding="utf-8")

    def append(self, obj: Dict[str, Any]) -> None:
        line = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
