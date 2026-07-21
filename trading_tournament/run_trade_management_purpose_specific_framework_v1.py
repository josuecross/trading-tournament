from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.trade_management_governance import (
    STRUCTURAL_COMPATIBILITY_FIELDS,
    generate_compatibility_matrix,
    implemented_strategy_records,
    legacy_status_rows,
    management_need_schema,
    overlay_migration_rows,
    taxonomy_rows,
)
from src.utils import git_commit_hash, load_config, sha256_file


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "purpose_specific_framework_v1"

SOURCE_FILES = [
    "src/overlays.py",
    "src/trade_management_governance.py",
    "docs/trade_management_research_policy.md",
    "tests/test_trade_management_purpose_specific_framework_v1.py",
    "run_trade_management_purpose_specific_framework_v1.py",
]

TEST_COMMANDS = [
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_trade_management_purpose_specific_framework_v1.py",
        "tests/test_trade_management_overlays.py",
        "tests/test_cppi_engine_capability.py",
        "tests/test_trade_management_cppi_n4_methodology_correction_v1.py",
        "tests/test_trade_management_cppi_n4_chronological_robustness_v1.py",
        "tests/test_metrics.py",
        "tests/test_position_sizing.py",
        "tests/test_audit_validation.py",
        "tests/test_risk_framework.py",
        "-q",
    ],
    [
        sys.executable,
        "-m",
        "py_compile",
        "src/overlays.py",
        "src/trade_management_governance.py",
        "src/backtester.py",
        "src/portfolio.py",
        "run_trade_management_purpose_specific_framework_v1.py",
        "tests/test_trade_management_purpose_specific_framework_v1.py",
    ],
]


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def run_test_commands() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    chunks: list[str] = []
    for cmd in TEST_COMMANDS:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
        command_text = " ".join(cmd)
        chunks.append("$ " + command_text)
        if proc.stdout:
            chunks.append(proc.stdout.rstrip())
        if proc.stderr:
            chunks.append(proc.stderr.rstrip())
        chunks.append(f"exit_code={proc.returncode}")
        chunks.append("")
        results.append(
            {
                "command": command_text,
                "exit_code": proc.returncode,
                "passed": proc.returncode == 0,
            }
        )
    write_text(OUT_DIR / "guardrail_test_results.txt", "\n".join(chunks))
    return results


def architecture_review() -> str:
    return """# Purpose-Specific Trade-Management Framework v1

## Architecture Findings

- `Backtester.run()` accepts one optional overlay object and has no native all-overlays matrix.
- Signal and lifecycle hooks are centralized in `src/overlays.py`; overlays clone intents and record deterministic event rows.
- Broad enumeration risk lives in historical research runners that build overlay factory lists across frozen bases.
- Compatibility was previously inferred from target-unit behavior and trial outcomes instead of declared in stable metadata.
- Source-defined management was documented in research packets, but not separated from optional overlays in a reusable schema.

## Combined Behaviors Identified

- `OVL-ORD-001` combined target-weight band suppression with minimum-notional filtering.
- `OVL-RSK-001` combined gross, per-asset, and group exposure caps.

## Holistic System

- `OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1` remains a complete source-defined portfolio-insurance system.
- CPPI controls remain attribution controls; floor-only, cushion-only, multiplier-only, cash-lock-only, and synthetic-safe variants are not future candidate overlays.
- The exact N4-CPPI combination remains `MIXED_ACROSS_EPISODES_CONCENTRATED_NO_ADVANCEMENT`.

## Migration Plan

- Keep legacy wrappers for historical reproduction and hash lineage.
- Use `OVL-ORD-WEIGHT-BAND-V1` or `OVL-ORD-MIN-NOTIONAL-V1` individually for future diagnosed execution-efficiency work.
- Use `OVL-RISK-GROSS-CAP-V1`, `OVL-RISK-ASSET-CAP-V1`, or `OVL-RISK-GROUP-CAP-V1` individually for future diagnosed portfolio-risk work.
- Require `ManagementExperimentPlan` validation before optional management research.
- Default optional-management count is `0`; one compatible primitive is the maximum for the default workflow.
- Generate compatibility reports from structure only. Compatibility is not authorization.
"""


def source_of_truth_update() -> str:
    return """# Source Of Truth Update

The repository trade-management rule is:

```text
source-exact base
-> Identity control
-> weakness diagnosis
-> one compatible purpose-specific overlay
-> attribution control
-> exact-combination decision
```

New strategies are not automatically tested against every management overlay. Optional overlays require a diagnosed weakness and a valid `ManagementExperimentPlan`.

Legacy composites remain visible only for reproduction:

- `OVL-ORD-001` = `OVL-ORD-WEIGHT-BAND-V1` plus `OVL-ORD-MIN-NOTIONAL-V1` behavior, not auto-combined in future experiments.
- `OVL-RSK-001` = combined gross, asset, and group cap wrapper, not a future default candidate.

CPPI remains holistic and source-defined as `OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1`; it was not rerun by this packet.

No performance backtest, parameter search, overlay search, promotion, paper/demo/live path, broker path, or strategy modification occurred.
"""


def files_changed_md() -> str:
    lines = ["# Files Changed", ""]
    for rel in SOURCE_FILES:
        path = ROOT / rel
        if path.exists():
            lines.append(f"- `{rel}`")
    lines.extend(
        [
            "",
            "Historical report packages under `reports/trade_management/` were not modified except for this new purpose-specific framework artifact directory.",
        ]
    )
    return "\n".join(lines)


def file_hashes() -> dict[str, str]:
    return {rel: sha256_file(ROOT / rel) for rel in SOURCE_FILES if (ROOT / rel).exists()}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config(ROOT / "config.yaml")
    strategy_rows = implemented_strategy_records(config)
    compatibility_rows = generate_compatibility_matrix(strategy_rows)

    write_text(OUT_DIR / "architecture_review.md", architecture_review())
    write_csv(OUT_DIR / "overlay_taxonomy.csv", taxonomy_rows())
    write_csv(OUT_DIR / "overlay_migration_map.csv", overlay_migration_rows())
    write_json(OUT_DIR / "management_need_schema.json", management_need_schema())
    write_csv(OUT_DIR / "compatibility_matrix.csv", compatibility_rows, list(STRUCTURAL_COMPATIBILITY_FIELDS))
    write_csv(OUT_DIR / "legacy_status_registry.csv", legacy_status_rows())
    write_text(OUT_DIR / "files_changed.md", files_changed_md())
    write_text(OUT_DIR / "source_of_truth_update.md", source_of_truth_update())

    test_results = run_test_commands()
    git_status = run_git(["status", "--short"]).stdout
    manifest = {
        "run_id": "purpose_specific_framework_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "task_labels": ["methodology_correction", "engine_capability_adjustment", "implementation"],
        "repository_commit": git_commit_hash(ROOT),
        "source_file_hashes": file_hashes(),
        "git_status_short": git_status,
        "default_optional_management_count": 0,
        "universal_overlay_matrix_created": False,
        "performance_backtest_run": False,
        "historical_performance_matrix_run": False,
        "parameter_search_run": False,
        "overlay_search_run": False,
        "overlay_combination_research_run": False,
        "strategy_modified": False,
        "promotion_or_paper_demo_live_broker_action": False,
        "paper_demo_live_broker_modules_invoked": False,
        "cppi_rerun": False,
        "cppi_exact_combination_status": "MIXED_ACROSS_EPISODES_CONCENTRATED_NO_ADVANCEMENT",
        "compatibility_report_performance_fields_included": False,
        "guardrail_tests_passed": all(row["passed"] for row in test_results),
        "guardrail_test_results": test_results,
        "outputs": {
            "architecture_review": str(OUT_DIR / "architecture_review.md"),
            "overlay_taxonomy": str(OUT_DIR / "overlay_taxonomy.csv"),
            "overlay_migration_map": str(OUT_DIR / "overlay_migration_map.csv"),
            "management_need_schema": str(OUT_DIR / "management_need_schema.json"),
            "compatibility_matrix": str(OUT_DIR / "compatibility_matrix.csv"),
            "legacy_status_registry": str(OUT_DIR / "legacy_status_registry.csv"),
            "guardrail_test_results": str(OUT_DIR / "guardrail_test_results.txt"),
            "files_changed": str(OUT_DIR / "files_changed.md"),
            "source_of_truth_update": str(OUT_DIR / "source_of_truth_update.md"),
            "manifest": str(OUT_DIR / "manifest.json"),
        },
    }
    write_json(OUT_DIR / "manifest.json", manifest)

    print(f"Purpose-specific trade-management framework packet written to {OUT_DIR}")
    return 0 if manifest["guardrail_tests_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
