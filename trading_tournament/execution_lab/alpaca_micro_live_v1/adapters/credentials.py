from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from execution_lab.alpaca_micro_live_v1 import PACKAGE_ROOT, WORKSPACE_ROOT


PAPER_KEY = "ALPACA_PAPER_API_KEY"
PAPER_SECRET = "ALPACA_PAPER_SECRET_KEY"
LIVE_KEY = "ALPACA_LIVE_API_KEY"
LIVE_SECRET = "ALPACA_LIVE_SECRET_KEY"


@dataclass(frozen=True)
class AlpacaCredentials:
    environment: str
    api_key: str | None
    secret_key: str | None
    source: str
    live_credentials_detected: bool = False

    @property
    def present(self) -> bool:
        return bool(self.api_key and self.secret_key)

    @property
    def masked_api_key(self) -> str:
        return mask_secret(self.api_key)

    @property
    def masked_secret_key(self) -> str:
        return mask_secret(self.secret_key)


def mask_secret(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key] = value
    return values


def default_env_paths() -> list[Path]:
    cwd = Path.cwd()
    candidates = [
        cwd / ".env.local",
        cwd / "trading_tournament" / ".env.local",
        PACKAGE_ROOT / ".env.local",
        WORKSPACE_ROOT / ".env.local",
    ]
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def load_env_local(paths: list[Path] | None = None) -> tuple[dict[str, str], str]:
    merged: dict[str, str] = {}
    source_names: list[str] = []
    for path in paths or default_env_paths():
        values = _parse_env_file(path)
        if values:
            merged.update(values)
            source_names.append(str(path))
    return merged, ";".join(source_names) if source_names else "none"


def load_alpaca_credentials(environment: str = "paper", env_paths: list[Path] | None = None) -> AlpacaCredentials:
    if environment != "paper":
        raise ValueError("Only paper credentials are supported by this runtime.")
    file_values, file_source = load_env_local(env_paths)

    api_key = os.environ.get(PAPER_KEY) or file_values.get(PAPER_KEY)
    secret_key = os.environ.get(PAPER_SECRET) or file_values.get(PAPER_SECRET)
    live_detected = bool(
        os.environ.get(LIVE_KEY)
        or os.environ.get(LIVE_SECRET)
        or file_values.get(LIVE_KEY)
        or file_values.get(LIVE_SECRET)
    )
    source = "environment" if os.environ.get(PAPER_KEY) or os.environ.get(PAPER_SECRET) else file_source
    return AlpacaCredentials(
        environment="paper",
        api_key=api_key,
        secret_key=secret_key,
        source=source,
        live_credentials_detected=live_detected,
    )

