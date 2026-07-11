from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


FINGERPRINT_COMPONENTS = (
    "family",
    "signal_direction",
    "universe_type",
    "formation_horizon",
    "holding_horizon",
    "rebalance_frequency",
    "weighting_method",
    "risk_overlay",
    "execution_cadence",
)


def normalize_component(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (list, tuple, set)):
        return "|".join(sorted(normalize_component(v) for v in value)) or "unknown"
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def fingerprint_payload(values: Mapping[str, Any]) -> dict[str, str]:
    return {key: normalize_component(values.get(key, "unknown")) for key in FINGERPRINT_COMPONENTS}


def strategy_fingerprint(values: Mapping[str, Any]) -> str:
    payload = fingerprint_payload(values)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "fp_" + hashlib.sha256(encoded).hexdigest()[:20]
