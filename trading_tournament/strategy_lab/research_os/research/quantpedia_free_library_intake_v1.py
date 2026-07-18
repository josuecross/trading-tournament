from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
LIBRARY_ID = "quantpedia_free_v1"
EXPECTED_FREE_STRATEGY_COUNT = 82
INPUT_DIR = Path("inputs") / "quantpedia_free_strategies"
LIBRARY_DIR = Path("strategy_lab") / "external_libraries" / LIBRARY_ID
EVIDENCE_DIR = Path("evidence") / "quantpedia_free_library_intake_v1" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
SUPPORTED_EXTENSIONS = (".csv", ".json", ".html", ".htm", ".txt")
OUTCOME_INPUT_REQUIRED = "authorized_quantpedia_capture_required"
OUTCOME_PASSED = "quantpedia_free_library_intake_passed"
OUTCOME_INCOMPLETE = "quantpedia_capture_incomplete_but_intake_usable"
OUTCOME_INVALID = "invalid_library_intake_methodology"
NEXT_ACTION_INPUT_REQUIRED = "authorized_quantpedia_capture_required"


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_hash_or_missing(root: Path, path: Path) -> str:
    full = abs_path(root, path)
    return sha256_file(full) if full.exists() else "missing"


def list_input_files(root: Path) -> list[Path]:
    input_root = abs_path(root, INPUT_DIR)
    if not input_root.exists():
        return []
    return sorted(path for path in input_root.rglob("*") if path.is_file())


def input_file_inventory(root: Path) -> list[dict[str, Any]]:
    input_root = abs_path(root, INPUT_DIR)
    rows: list[dict[str, Any]] = []
    for path in list_input_files(root):
        rows.append(
            {
                "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                "input_relative_path": str(path.relative_to(input_root)).replace("\\", "/"),
                "extension": path.suffix.lower(),
                "supported_extension": path.suffix.lower() in SUPPORTED_EXTENSIONS,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def usable_input_files(root: Path) -> list[dict[str, Any]]:
    return [
        row
        for row in input_file_inventory(root)
        if row["supported_extension"] and int(row["size_bytes"]) > 0
    ]


def clean_evidence_dir(root: Path) -> Path:
    output = abs_path(root, EVIDENCE_DIR)
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()
    return output


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def input_blocker_payload(root: Path) -> dict[str, Any]:
    input_root = abs_path(root, INPUT_DIR)
    inventory = input_file_inventory(root)
    usable = [row for row in inventory if row["supported_extension"] and int(row["size_bytes"]) > 0]
    registry_before = file_hash_or_missing(root, REGISTRY_PATH)
    active_before = file_hash_or_missing(root, ACTIVE_OBSERVATIONS_PATH)
    return {
        "library_id": LIBRARY_ID,
        "outcome": OUTCOME_INPUT_REQUIRED,
        "next_action": NEXT_ACTION_INPUT_REQUIRED,
        "reason": "No usable user-supplied Quantpedia free-strategy capture was found.",
        "input_directory": str(input_root),
        "input_directory_exists": input_root.exists(),
        "supported_input_formats": [
            "CSV",
            "JSON",
            "Browser-saved HTML",
            "Plain-text title-and-URL list",
        ],
        "supported_extensions": list(SUPPORTED_EXTENSIONS),
        "expected_free_strategy_count": EXPECTED_FREE_STRATEGY_COUNT,
        "raw_input_file_count": len(inventory),
        "usable_input_file_count": len(usable),
        "raw_input_records": 0,
        "normalized_strategy_count": 0,
        "difference_from_expected_count": EXPECTED_FREE_STRATEGY_COUNT,
        "missing_strategies_fabricated": False,
        "empty_library_created": False,
        "library_output_dir_created": abs_path(root, LIBRARY_DIR).exists(),
        "strategy_registry_hash_before": registry_before,
        "strategy_registry_hash_after": registry_before,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_before,
        "input_file_inventory": inventory,
        "usable_input_files": usable,
        "access_guardrails": {
            "network_used": False,
            "quantpedia_scraped": False,
            "login_requested": False,
            "credentials_requested": False,
            "cookies_accessed": False,
            "session_tokens_accessed": False,
            "private_endpoints_used": False,
            "provider_data_downloaded": False,
            "original_papers_verified": False,
            "strategy_backtest_run": False,
            "performance_ranking_created": False,
            "paper_demo_activation": False,
            "broker_or_live_path": False,
            "real_money_recommendation": False,
        },
        "content_boundary": {
            "full_quantpedia_articles_stored": False,
            "charts_or_performance_tables_stored": False,
            "quantpedia_or_quantconnect_code_copied": False,
        },
    }


def run(root: Path = ROOT) -> dict[str, Any]:
    output = clean_evidence_dir(root)
    usable = usable_input_files(root)
    if not usable:
        payload = input_blocker_payload(root)
        write_json(output / "input_blocker.json", payload)
        return {
            "library_id": LIBRARY_ID,
            "outcome": payload["outcome"],
            "next_action": payload["next_action"],
            "evidence_dir": str(output),
            "usable_input_file_count": payload["usable_input_file_count"],
            "normalized_strategy_count": 0,
        }

    payload = {
        "library_id": LIBRARY_ID,
        "outcome": OUTCOME_INVALID,
        "next_action": "implement_quantpedia_free_library_normalization_from_supplied_capture",
        "reason": "Usable capture files are present, but this runner currently only completed the authorized no-input blocker path.",
        "usable_input_files": usable,
        "network_used": False,
        "strategy_backtest_run": False,
    }
    write_json(output / "input_blocker.json", payload)
    return {
        "library_id": LIBRARY_ID,
        "outcome": payload["outcome"],
        "next_action": payload["next_action"],
        "evidence_dir": str(output),
        "usable_input_file_count": len(usable),
        "normalized_strategy_count": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
