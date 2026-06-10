from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml


PACKAGE_DISTRIBUTIONS = {
    "pandas": "pandas",
    "numpy": "numpy",
    "yfinance": "yfinance",
    "matplotlib": "matplotlib",
    "pyyaml": "PyYAML",
    "pytest": "pytest",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True, default=str)


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def utc_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_hash(config: dict[str, Any]) -> str:
    text = yaml.safe_dump(config, sort_keys=True)
    return sha256_text(text)


def get_package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for label, distribution in PACKAGE_DISTRIBUTIONS.items():
        try:
            versions[label] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[label] = "NOT_INSTALLED"
    return versions


def validate_required_imports() -> dict[str, str]:
    import importlib

    import_names = {
        "pandas": "pandas",
        "numpy": "numpy",
        "yfinance": "yfinance",
        "matplotlib": "matplotlib",
        "pyyaml": "yaml",
        "pytest": "pytest",
    }
    failures: list[str] = []
    for label, import_name in import_names.items():
        try:
            importlib.import_module(import_name)
        except Exception as exc:  # pragma: no cover - exercised by environment
            failures.append(f"{label}: {exc}")
    if failures:
        joined = "\n".join(failures)
        raise RuntimeError(
            "Required package import check failed. Run "
            "`python3 -m pip install -r requirements.txt` and retry.\n"
            f"{joined}"
        )
    return get_package_versions()


def pip_freeze() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return result.stderr.strip()
        return result.stdout
    except Exception as exc:  # pragma: no cover - defensive environment capture
        return f"pip freeze unavailable: {exc}"


def git_commit_hash(cwd: str | Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def create_run_dir(results_root: str | Path) -> Path:
    run_dir = Path(results_root) / "runs" / utc_run_id()
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def refresh_latest(run_dir: str | Path, latest_dir: str | Path) -> None:
    run_dir = Path(run_dir)
    latest_dir = Path(latest_dir)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)


def platform_metadata() -> dict[str, str]:
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
    }


def parse_date(value: Any) -> Any:
    if value is None:
        return None
    return str(value)
