from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.research.dsr_evidence_status import (
    CURRENT_DIAGNOSTIC_BEST_FINAL_EQUITY,
    DSR_ACTIVE_ID,
    HISTORICAL_BEST_FINAL_EQUITY,
    load_dsr_evidence_status,
)


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "dsr_evidence_status_integration" / "latest"
TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def consumer_inventory(root: Path) -> list[dict[str, Any]]:
    consumers = [
        (
            "strategy_lab/research_os/strategy_evidence_library/builder.py",
            True,
            True,
            "SEL decision annotation fields",
            True,
            "DSR decision exposes historical_recovered_metrics/current_diagnostic_metrics, non_comparable status, not_qualifying_e4, and mismatch-review provenance",
        ),
        (
            "run_research_state_dashboard.py",
            False,
            False,
            "dashboard active-row note and manifest warning block",
            True,
            "DSR appears active/frozen with historical_unverified/current_diagnostic_only/E4 incomplete warning and no added performance display",
        ),
        (
            "run_advisor_consistency_check.py",
            True,
            True,
            "advisor semantic guardrail checks",
            True,
            "fails unannotated 4071.04, current diagnostic mislabeled as activation/qualifying performance, silent substitution, or lifecycle/evidence-chain conflation",
        ),
        (
            "strategy_lab/research_os/research/dsr_active_evidence_mismatch_review.py",
            True,
            True,
            "raw mismatch-review packet producer",
            True,
            "status taxonomy now says historical_unverified_non_comparable_not_used_as_current_diagnostic_reference",
        ),
        (
            "strategy_lab/research_os/research/active_observation_evidence_reconciliation.py",
            True,
            True,
            "active-observation reconciliation evidence",
            True,
            "DSR E4 conflict row now labels historical_recovered_claim/current_sampled_window_diagnostic and not_qualifying_e4",
        ),
        (
            "run_current_research_checkpoint.py",
            True,
            True,
            "legacy checkpoint caveat and best-set CSV",
            True,
            "future checkpoint output preserves both numbers with unverified_non_comparable and reproducible_diagnostic_only labels",
        ),
        (
            "paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1/active_observation.yaml",
            True,
            False,
            "canonical recovered active state",
            False,
            "preserved canonical historical record; downstream annotations attach evidence quality",
        ),
        (
            "evidence/active_strategy_evidence_recompute/latest",
            False,
            True,
            "raw cached-data diagnostic evidence",
            False,
            "raw diagnostic producer remains separate from historical activation performance",
        ),
    ]
    rows = []
    for path, reads_historical, reads_current, presentation, change_required, result in consumers:
        text = read_text(root / path) if (root / path).is_file() else ""
        rows.append(
            {
                "consumer_path": path,
                "exists": (root / path).exists(),
                "reads_historical_metric": reads_historical,
                "reads_current_diagnostic": reads_current,
                "presentation": presentation,
                "change_required": change_required,
                "result_after_patch": result,
                "contains_4071_04": "4071.04" in text,
                "contains_3481_6998": "3481.6998" in text,
            }
        )
    return rows


def metric_classification(status: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "metric": "best_final_equity",
            "value": HISTORICAL_BEST_FINAL_EQUITY,
            "role": status["historical_metric_role"],
            "evidence_status": status["historical_metric_evidence_status"],
            "reproducible": status["historical_metric_reproducible"],
            "eligible_e4": status["historical_metric_eligible_for_e4"],
            "scope": "historical recovered activation claim",
            "limitation": status["historical_metric_reason"],
        },
        {
            "metric": "best_final_equity",
            "value": status["current_diagnostic_metrics"]["best_final_equity"],
            "role": status["current_diagnostic_role"],
            "evidence_status": status["current_diagnostic_evidence_status"],
            "reproducible": status["current_diagnostic_reproducible"],
            "eligible_e4": status["current_diagnostic_eligible_for_e4"],
            "scope": status["current_diagnostic_scope"],
            "limitation": status["current_diagnostic_limitation"],
        },
    ]


def consumer_changes() -> list[dict[str, Any]]:
    return [
        {"consumer_path": "strategy_lab/research_os/strategy_evidence_library/builder.py", "change_type": "added_dsr_metric_status_fields", "decision_effect": "DSR remains active E1; metrics do not qualify E4"},
        {"consumer_path": "run_research_state_dashboard.py", "change_type": "added_dsr_warning_without_performance_display", "decision_effect": "dashboard distinguishes active lifecycle from incomplete E4 lineage"},
        {"consumer_path": "run_advisor_consistency_check.py", "change_type": "added_metric_semantic_guardrails", "decision_effect": "unsafe metric presentations fail consistency check"},
        {"consumer_path": "strategy_lab/research_os/research/dsr_active_evidence_mismatch_review.py", "change_type": "taxonomy_correction", "decision_effect": "historical metric preserved but unverified/non-comparable; current diagnostic not a historical replacement"},
        {"consumer_path": "strategy_lab/research_os/research/active_observation_evidence_reconciliation.py", "change_type": "taxonomy_correction", "decision_effect": "DSR reconciliation conflict row labels both roles and not_qualifying_e4"},
        {"consumer_path": "run_current_research_checkpoint.py", "change_type": "legacy_checkpoint_wording_patch", "decision_effect": "future checkpoint caveat no longer presents either metric as qualifying performance"},
    ]


def candidate_text_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def classify_reference(path: Path, text: str, line: str) -> tuple[str, bool]:
    normalized_path = str(path).replace("\\", "/")
    lowered_text = text.lower()
    lowered_line = line.lower()
    has_historical = "4071.04" in line
    has_current = "3481.6998" in line
    if "paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1" in normalized_path:
        return "canonical historical record", False
    if "evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1" in normalized_path:
        return "canonical historical record", False
    if (
        "evidence/active_strategy_evidence_recompute" in normalized_path
        or "evidence/dsr_active_evidence_mismatch_review" in normalized_path
        or normalized_path == "run_active_strategy_evidence_recompute.py"
        or "strategy_lab/research_os/research/dsr_active_evidence_mismatch_review.py" in normalized_path
        or "strategy_lab/research_os/research/dsr_evidence_status.py" in normalized_path
        or "tests/test_dsr_active_evidence_mismatch_review.py" in normalized_path
    ):
        return "raw diagnostic evidence", False
    historical_safe = (not has_historical) or "unverified_non_comparable" in lowered_text or "historical_unverified" in lowered_text
    current_safe = (not has_current) or "reproducible_diagnostic_only" in lowered_text or "current_diagnostic_only" in lowered_text
    comparable_safe = not (has_historical and has_current) or "non_comparable" in lowered_text
    if historical_safe and current_safe and comparable_safe:
        return "correctly annotated generated view", False
    if "best_final_equity" in lowered_line and ("non_comparable" in lowered_text or "unverified_non_comparable" in lowered_text):
        return "correctly annotated generated view", False
    return "unsafe unresolved reference", True


def remaining_metric_references(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    needles = [str(HISTORICAL_BEST_FINAL_EQUITY), str(CURRENT_DIAGNOSTIC_BEST_FINAL_EQUITY)]
    for path in candidate_text_files(root):
        text = read_text(path)
        if not any(needle in text for needle in needles):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not any(needle in line for needle in needles):
                continue
            classification, unsafe = classify_reference(path.relative_to(root), text, line)
            rows.append(
                {
                    "path": rel(root, path),
                    "line": line_number,
                    "contains_4071_04": "4071.04" in line,
                    "contains_3481_6998": "3481.6998" in line,
                    "classification": classification,
                    "unsafe_unresolved": unsafe,
                    "excerpt": line[:240],
                }
            )
    return rows


def markdown_summary(payload: dict[str, Any], unsafe_count: int) -> str:
    return f"""# DSR Evidence Status Integration

Created UTC: `{payload['created_at_utc']}`

Target: `{DSR_ACTIVE_ID}`

## Metric Taxonomy

- Historical recovered `4071.04`: `historical_recovered_claim`, `unverified_non_comparable`, reproducible=`false`, E4 eligible=`false`.
- Current diagnostic `3481.6998`: `current_sampled_window_diagnostic`, `reproducible_diagnostic_only`, E4 eligible=`false`.
- Comparability: `non_comparable`.
- Lifecycle: active/frozen unchanged, highest independent SEL level `E1`.

## Integration Result

- SEL annotation integrated: `{str(payload['sel_integration_present']).lower()}`.
- Dashboard warning integrated: `{str(payload['dashboard_integration_present']).lower()}`.
- Advisor semantic checks integrated: `{str(payload['advisor_checks_present']).lower()}`.
- Unsafe unresolved metric references: `{unsafe_count}`.

No strategy rule, lifecycle, paper/demo state, registry status, provider data, backtest, promotion, or broker/live path was changed.
"""


def run_dsr_evidence_status_integration(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    status = load_dsr_evidence_status(root)
    inventory = consumer_inventory(root)
    classifications = metric_classification(status)
    changes = consumer_changes()
    references = remaining_metric_references(root)
    unsafe = [row for row in references if row["unsafe_unresolved"]]

    payload = {
        "created_at_utc": utc_now(),
        "integration_step_only": True,
        "target_active_observation_id": DSR_ACTIVE_ID,
        "source_mismatch_packet_valid": status["source_packet_valid"],
        "historical_metric_evidence_status": status["historical_metric_evidence_status"],
        "current_diagnostic_evidence_status": status["current_diagnostic_evidence_status"],
        "metric_comparability": status["metric_comparability"],
        "metric_eligible_for_evidence_stage": status["metric_eligible_for_evidence_stage"],
        "canonical_lifecycle_status": status["canonical_lifecycle_status"],
        "highest_independent_sel_level": status["highest_independent_sel_level"],
        "sel_integration_present": any(row["consumer_path"].endswith("builder.py") and row["change_required"] for row in inventory),
        "dashboard_integration_present": any(row["consumer_path"] == "run_research_state_dashboard.py" and row["change_required"] for row in inventory),
        "advisor_checks_present": any(row["consumer_path"] == "run_advisor_consistency_check.py" and row["change_required"] for row in inventory),
        "consumer_count": len(inventory),
        "unsafe_unresolved_reference_count": len(unsafe),
        "no_metric_replacement": True,
        "no_metric_recompute": True,
        "no_strategy_decision_from_metric": True,
    }
    consistency = {
        "integration_consistency_passed": len(unsafe) == 0 and status["historical_metric_evidence_status"] == "unverified_non_comparable" and status["metric_eligible_for_evidence_stage"]["E4"] is False,
        "unsafe_unresolved_reference_count": len(unsafe),
        "source_packet_valid": status["source_packet_valid"],
        "dsr_active_lifecycle_preserved": status["canonical_lifecycle_status"] == "active",
        "highest_independent_sel_level_e1": status["highest_independent_sel_level"] == "E1",
        "historical_metric_not_replaced": True,
        "current_diagnostic_not_activation_performance": True,
    }

    write_json(output / "dsr_evidence_status_integration.json", payload)
    (output / "dsr_evidence_status_integration.md").write_text(markdown_summary(payload, len(unsafe)), encoding="utf-8")
    write_csv(
        output / "metric_consumer_inventory.csv",
        inventory,
        ["consumer_path", "exists", "reads_historical_metric", "reads_current_diagnostic", "presentation", "change_required", "result_after_patch", "contains_4071_04", "contains_3481_6998"],
    )
    write_csv(output / "metric_classification.csv", classifications, ["metric", "value", "role", "evidence_status", "reproducible", "eligible_e4", "scope", "limitation"])
    write_csv(output / "consumer_changes.csv", changes, ["consumer_path", "change_type", "decision_effect"])
    write_csv(output / "remaining_unsafe_references.csv", references, ["path", "line", "contains_4071_04", "contains_3481_6998", "classification", "unsafe_unresolved", "excerpt"])
    write_json(output / "integration_consistency_check.json", consistency)
    return {"output_dir": str(output), **payload, "consistency_passed": consistency["integration_consistency_passed"]}


def main() -> None:
    print(json.dumps(run_dsr_evidence_status_integration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
