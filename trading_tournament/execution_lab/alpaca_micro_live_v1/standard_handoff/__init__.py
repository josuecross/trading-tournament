"""Additive standardized handoff path; legacy runtime registration remains unchanged."""

from pathlib import Path

from contracts.forward_observation.forward_observation_handoff_standard_v1.importer import HandoffImporter
from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT


# Keep the immutable import root short enough for full content hashes on Windows.
DEFAULT_IMPORT_STORAGE = MODULE_ROOT / "i"
DEFAULT_STRATEGY_STATE_STORAGE = MODULE_ROOT / "evidence" / "standard_strategy_state"


def receiver_importer(storage_root: Path | None = None) -> HandoffImporter:
    return HandoffImporter(storage_root=storage_root or DEFAULT_IMPORT_STORAGE)


__all__ = ["DEFAULT_IMPORT_STORAGE", "DEFAULT_STRATEGY_STATE_STORAGE", "receiver_importer"]
