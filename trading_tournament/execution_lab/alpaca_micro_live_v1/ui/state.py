from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeUiState:
    emergency_stop: bool = False
    last_session_dir: str | None = None

