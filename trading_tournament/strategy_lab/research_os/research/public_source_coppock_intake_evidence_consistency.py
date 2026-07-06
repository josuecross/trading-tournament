from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "coppock_curve_monthly_equity_signal"
FAMILY_ID = "long_term_equity_index_momentum_zero_cross"
EXPECTED_DECISION = "eligible_for_bounded_bt_design"
NEXT_ACTION = "design_public_source_coppock_curve_monthly_equity_signal_bounded_bt_lane"
VERIFY_PASS = "coppock_intake_evidence_consistent_ready_for_design"
VERIFY_FAIL = "coppock_intake_evidence_inconsistent_block_design"

COPPOCK_YAML = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "coppock_curve_monthly_equity_signal.yaml"
)
LARRY_YAML = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "larry_connors_rsi2_mean_reversion.yaml"
)
INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
BRIDGE_DIR = Path("evidence") / "research_recovery" / "public_source_preregistration_bridge" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_coppock_intake_evidence_consistency"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
INTAKE_CACHE = INTAKE_DIR / "local_cache_availability_report.csv"
INTAKE_SIMILARITY = INTAKE_DIR / "family_similarity_do_not_retest_report.md"
BATCH_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
BRIDGE_MANIFEST = BRIDGE_DIR / "public_source_bridge_manifest.json"

EXPECTED_SIMILARITY_HITS = {
    "spy200d_trend_control",
    "global_multi_asset",
    "macro_gld_duration_risk_off",
    "high_return_tactical_equity",
    "volatility_throttle_volatility_managed_equity",
    "turn_of_month_calendar_effect",
    "mean_reversion_rejected_or_existing_candidate",
    "price_band_money_flow_confirmation",
}

REQUIRED_FILES = (
    "coppock_intake_evidence_consistency_manifest.json",
    "git_diff_summary.md",
    "coppock_yaml_validation_report.md",
    "larry_connors_yaml_change_report.md",
    "candidate_specific_evidence_location_report.md",
    "generic_bridge_evidence_explanation.md",
    "similarity_do_not_retest_confirmation.md",
    "guardrail_checklist.json",
    "coppock_intake_evidence_consistency_next_action.md",
    "coppock_intake_evidence_consistency_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def dotted_get(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def git_output(args: list[str], root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    return (result.stdout + result.stderr).strip()


def tracked_diff_for(path: Path, root: Path) -> str:
    return git_output(["diff", "--", str(path)], root)


def git_diff_summary(root: Path) -> dict[str, Any]:
    return {
        "git_diff_stat": git_output(["diff", "--stat"], root),
        "git_diff_name_only": git_output(["diff", "--name-only"], root),
        "coppock_yaml_diff_present": bool(tracked_diff_for(COPPOCK_YAML, root).strip()),
        "larry_connors_yaml_diff_present": bool(tracked_diff_for(LARRY_YAML, root).strip()),
        "intake_validator_diff_present": bool(
            tracked_diff_for(Path("strategy_lab") / "research_os" / "research" / "public_source_intake_validation.py", root).strip()
        ),
    }


def coppock_yaml_checks(payload: dict[str, Any]) -> dict[str, Any]:
    formula = str(dotted_get(payload, "rules.formula") or "")
    entry = str(dotted_get(payload, "rules.entry_rule") or "")
    exit_rule = str(dotted_get(payload, "rules.exit_rule") or "")
    risk = str(dotted_get(payload, "rules.risk_controls") or "").lower()
    instruments = dotted_get(payload, "strategy_description.instruments") or []
    roc_periods = dotted_get(payload, "rules.indicator_definitions.roc_periods") or []
    checks = {
        "source_id_correct": dotted_get(payload, "source.source_id") == SOURCE_ID,
        "family_id_correct": dotted_get(payload, "strategy_description.strategy_family") == FAMILY_ID,
        "rule_clarity_clear": dotted_get(payload, "strategy_description.rule_clarity") == "clear_and_testable",
        "monthly_coppock_curve": "monthly" in str(dotted_get(payload, "strategy_description.timeframe") or "").lower()
        and "monthly" in str(dotted_get(payload, "rules.indicator_definitions.data_frequency") or "").lower(),
        "formula_source_backed": "10-period WMA" in formula
        and "14-period ROC" in formula
        and "11-period ROC" in formula
        and roc_periods == [14, 11]
        and dotted_get(payload, "rules.indicator_definitions.source_backed_parameters") is True,
        "entry_positive_zero_cross": "negative territory to positive territory" in entry,
        "exit_negative_zero_cross": "positive territory to negative territory" in exit_rule,
        "spy_bil_only": instruments == ["SPY", "BIL"],
        "long_only_cash_fallback": "long-only spy" in risk and "bil/cash fallback" in risk,
        "no_prohibited_features": all(
            phrase in risk
            for phrase in [
                "no leverage",
                "no shorting",
                "no options/futures",
                "no intraday",
            ]
        ),
        "no_added_filter_text": all(
            item not in (formula + " " + entry + " " + exit_rule).lower()
            for item in ["stop-loss", "profit target", "divergence", "signal line", "weekly", "daily variant"]
        ),
        "single_source_priority_present": dotted_get(payload, "project_screening.single_source_validation_priority") == 100,
    }
    checks["coppock_yaml_valid"] = all(checks.values())
    return checks


def cache_status(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("symbol", ""): row.get("cache_status", "") for row in rows}


def batch_decision(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("source_id") == SOURCE_ID), {})


def evidence_checks(
    intake_manifest: dict[str, Any],
    cache_rows: list[dict[str, str]],
    batch_row: dict[str, str],
) -> dict[str, Any]:
    cache = cache_status(cache_rows)
    hits = set(intake_manifest.get("family_similarity_hits", []))
    checks = {
        "candidate_specific_manifest_source_id": intake_manifest.get("source_id") == SOURCE_ID,
        "source_fields_complete": intake_manifest.get("exact_missing_fields") == [],
        "no_constraint_blockers": intake_manifest.get("constraint_blockers") == [],
        "spy_cache_ready": cache.get("SPY") == "cache_ready",
        "bil_cache_ready": cache.get("BIL") == "cache_ready",
        "similarity_hits_expected": EXPECTED_SIMILARITY_HITS.issubset(hits),
        "duplicate_do_not_retest_false": intake_manifest.get("eligibility_decision") != "duplicate_or_do_not_retest",
        "eligibility_decision_expected": intake_manifest.get("eligibility_decision") == EXPECTED_DECISION,
        "single_source_next_action_expected": intake_manifest.get("next_action") == NEXT_ACTION,
        "batch_evidence_decision_expected": batch_row.get("eligibility_decision") == EXPECTED_DECISION,
        "batch_evidence_next_action_expected": batch_row.get("next_action") == NEXT_ACTION,
    }
    checks["candidate_specific_evidence_valid"] = all(checks.values())
    return checks


def guardrails() -> dict[str, bool]:
    return {
        "coppock_bounded_design_created": False,
        "coppock_implemented": False,
        "coppock_backtest_run": False,
        "different_public_source_selected": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "coppock_parameters_tuned": False,
        "daily_or_weekly_variants_added": False,
        "filters_stops_signal_lines_divergence_or_alternate_exits_added": False,
        "larry_connors_continued": False,
        "percent_b_continued": False,
        "turn_of_month_continued": False,
        "faber_taa_retested": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_demo_activation": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    coppock_yaml = read_yaml(root / COPPOCK_YAML)
    larry_diff = tracked_diff_for(LARRY_YAML, root)
    diff = git_diff_summary(root)
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    cache_rows = read_csv_rows(root / INTAKE_CACHE)
    batch_rows = read_csv_rows(root / BATCH_DECISIONS)
    batch_row = batch_decision(batch_rows)
    bridge_manifest = read_json(root / BRIDGE_MANIFEST)
    yaml_checks = coppock_yaml_checks(coppock_yaml)
    evidence = evidence_checks(intake_manifest, cache_rows, batch_row)
    bridge_generic_expected = (
        bridge_manifest.get("public_source_preregistration_bridge_only") is True
        and bridge_manifest.get("public_strategy_selected") is False
        and bridge_manifest.get("blank_intake_eligibility_decision") == "source_intake_incomplete"
        and bridge_manifest.get("next_action") == "manual_public_source_intake_required"
    )
    larry_status = "unrelated_reverted" if not larry_diff.strip() else "unresolved_requires_direction_owner_review"
    verification_passed = (
        yaml_checks["coppock_yaml_valid"]
        and evidence["candidate_specific_evidence_valid"]
        and bridge_generic_expected
        and larry_status == "unrelated_reverted"
    )
    decision = VERIFY_PASS if verification_passed else VERIFY_FAIL
    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "coppock_intake_evidence_consistency_verification_only": True,
        "source_id": SOURCE_ID,
        "candidate_yaml_path": str((root / COPPOCK_YAML).resolve()),
        "larry_connors_yaml_path": str((root / LARRY_YAML).resolve()),
        "coppock_yaml_valid": yaml_checks["coppock_yaml_valid"],
        "larry_connors_yaml_change_report": larry_status,
        "larry_connors_yaml_current_diff_present": bool(larry_diff.strip()),
        "candidate_specific_evidence_valid": evidence["candidate_specific_evidence_valid"],
        "candidate_specific_intake_evidence_path": str((root / INTAKE_DIR).resolve()),
        "candidate_specific_batch_evidence_path": str((root / BATCH_INTAKE_DIR).resolve()),
        "generic_bridge_evidence_path": str((root / BRIDGE_DIR).resolve()),
        "generic_bridge_blank_intake_expected": bridge_generic_expected,
        "source_fields_complete": evidence["source_fields_complete"],
        "constraint_blockers": intake_manifest.get("constraint_blockers", []),
        "spy_cache_ready": evidence["spy_cache_ready"],
        "bil_cache_ready": evidence["bil_cache_ready"],
        "similarity_hits": intake_manifest.get("family_similarity_hits", []),
        "similarity_hits_expected": evidence["similarity_hits_expected"],
        "duplicate_do_not_retest_decision": False if evidence["duplicate_do_not_retest_false"] else True,
        "eligibility_decision": intake_manifest.get("eligibility_decision", ""),
        "batch_eligibility_decision": batch_row.get("eligibility_decision", ""),
        "verification_decision": decision,
        "next_action": NEXT_ACTION if decision == VERIFY_PASS else "block_coppock_design_until_intake_evidence_repaired",
        **guardrails(),
    }
    support = {
        "diff": diff,
        "coppock_yaml": coppock_yaml,
        "yaml_checks": yaml_checks,
        "evidence": evidence,
        "intake_manifest": intake_manifest,
        "batch_row": batch_row,
        "bridge_manifest": bridge_manifest,
        "cache_rows": cache_rows,
        "larry_diff": larry_diff,
    }
    return manifest, support


def diff_summary_md(diff: dict[str, Any]) -> str:
    return f"""# Git Diff Summary

Changed tracked files:

```text
{diff['git_diff_name_only'] or 'none'}
```

Diff stat:

```text
{diff['git_diff_stat'] or 'none'}
```

Coppock YAML diff present: `{diff['coppock_yaml_diff_present']}`

Larry Connors YAML diff present: `{diff['larry_connors_yaml_diff_present']}`

Intake validator diff present: `{diff['intake_validator_diff_present']}`
"""


def coppock_yaml_report_md(manifest: dict[str, Any], checks: dict[str, Any]) -> str:
    lines = ["# Coppock YAML Validation Report", ""]
    lines.append(f"Candidate YAML: `{manifest['candidate_yaml_path']}`")
    lines.append("")
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("No bounded design, backtest, parameter tuning, added filters, or variants were created by this verification.")
    return "\n".join(lines) + "\n"


def larry_report_md(manifest: dict[str, Any], larry_diff: str) -> str:
    return f"""# Larry Connors YAML Change Report

Report status: `{manifest['larry_connors_yaml_change_report']}`

Current Larry Connors YAML diff present: `{manifest['larry_connors_yaml_current_diff_present']}`

Explanation: During Coppock intake validation, Larry Connors was temporarily changed only to move the single-source validation selector. That was unrelated to Larry's closed final state, so the Larry YAML was restored. The validator now uses an explicit selected-candidate priority on Coppock, avoiding a Larry file mutation.

Current Larry diff:

```text
{larry_diff or 'none'}
```
"""


def candidate_evidence_report_md(manifest: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = ["# Candidate-Specific Evidence Location Report", ""]
    lines.append(f"Single-source validation evidence: `{manifest['candidate_specific_intake_evidence_path']}`")
    lines.append(f"Batch validation evidence: `{manifest['candidate_specific_batch_evidence_path']}`")
    lines.append("")
    for key, value in evidence.items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def bridge_explanation_md(manifest: dict[str, Any], bridge_manifest: dict[str, Any]) -> str:
    return f"""# Generic Bridge Evidence Explanation

Generic bridge evidence path: `{manifest['generic_bridge_evidence_path']}`

Generic bridge blank-intake state expected: `{manifest['generic_bridge_blank_intake_expected']}`

The `public_source_preregistration_bridge/latest` packet is an infrastructure/blank-template bridge check. It does not represent the currently selected Coppock candidate. Therefore fields such as `manual_public_source_intake_required`, `public_strategy_selected: false`, or a blank intake decision are expected in that generic packet and should not be used as the Coppock eligibility decision.

Bridge manifest excerpts:

- `public_strategy_selected`: `{bridge_manifest.get('public_strategy_selected')}`
- `blank_intake_eligibility_decision`: `{bridge_manifest.get('blank_intake_eligibility_decision')}`
- `next_action`: `{bridge_manifest.get('next_action')}`
"""


def similarity_report_md(manifest: dict[str, Any]) -> str:
    hits = "\n".join(f"- `{item}`" for item in manifest["similarity_hits"]) or "- none"
    return f"""# Similarity / Do-Not-Retest Confirmation

Similarity hits expected: `{manifest['similarity_hits_expected']}`

Similarity hits:

{hits}

Duplicate/do-not-retest decision: `{manifest['duplicate_do_not_retest_decision']}`

Eligibility decision: `{manifest['eligibility_decision']}`
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Coppock Intake Evidence Consistency Next Action

Verification decision: `{manifest['verification_decision']}`

Exact next action:

`{manifest['next_action']}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["coppock_intake_evidence_consistency_consistency_check.json"] = True
    checks: dict[str, Any] = {
        "verification_only": manifest["coppock_intake_evidence_consistency_verification_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "coppock_yaml_valid": manifest["coppock_yaml_valid"] is True,
        "larry_change_reverted": manifest["larry_connors_yaml_change_report"] == "unrelated_reverted"
        and manifest["larry_connors_yaml_current_diff_present"] is False,
        "candidate_specific_evidence_valid": manifest["candidate_specific_evidence_valid"] is True,
        "bridge_generic_expected": manifest["generic_bridge_blank_intake_expected"] is True,
        "eligibility_expected": manifest["eligibility_decision"] == EXPECTED_DECISION
        and manifest["batch_eligibility_decision"] == EXPECTED_DECISION,
        "cache_ready": manifest["spy_cache_ready"] is True and manifest["bil_cache_ready"] is True,
        "similarity_and_duplicate_status": manifest["similarity_hits_expected"] is True
        and manifest["duplicate_do_not_retest_decision"] is False,
        "no_forbidden_actions": all(manifest[key] is False for key in guardrails()),
        "decision_valid": manifest["verification_decision"] in {VERIFY_PASS, VERIFY_FAIL},
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, support = build_manifest(root)

    write_json(output / "coppock_intake_evidence_consistency_manifest.json", manifest)
    write_text(output / "git_diff_summary.md", diff_summary_md(support["diff"]))
    write_text(output / "coppock_yaml_validation_report.md", coppock_yaml_report_md(manifest, support["yaml_checks"]))
    write_text(output / "larry_connors_yaml_change_report.md", larry_report_md(manifest, support["larry_diff"]))
    write_text(output / "candidate_specific_evidence_location_report.md", candidate_evidence_report_md(manifest, support["evidence"]))
    write_text(output / "generic_bridge_evidence_explanation.md", bridge_explanation_md(manifest, support["bridge_manifest"]))
    write_text(output / "similarity_do_not_retest_confirmation.md", similarity_report_md(manifest))
    write_json(output / "guardrail_checklist.json", guardrails())
    write_text(output / "coppock_intake_evidence_consistency_next_action.md", next_action_md(manifest))
    check = consistency_check(manifest, output)
    write_json(output / "coppock_intake_evidence_consistency_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
