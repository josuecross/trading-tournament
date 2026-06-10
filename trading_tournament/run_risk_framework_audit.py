from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parent
FRAMEWORK_PATH = REPO_ROOT / "risk_framework" / "risk_framework.yaml"
OUTPUT_ROOT = REPO_ROOT / "evidence" / "risk_framework"
REQUIRED_FILES = [
    "README_FOR_AUDITOR.md",
    "risk_framework_summary.md",
    "risk_framework.yaml",
    "risk_rules_table.csv",
    "instrument_risk_budgets.csv",
    "metric_hierarchy.csv",
    "promotion_demotion_rules.csv",
    "validation_checklist.csv",
    "warnings_and_limitations.md",
    "risk_framework_validation.json",
]


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_framework(path: Path = FRAMEWORK_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def validate_framework(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        "framework",
        "account",
        "targets",
        "risk_bands",
        "success_metrics",
        "exposure_policy",
        "instrument_risk_budgets",
        "promotion_rules",
    ]
    for section in required:
        if section not in data:
            errors.append(f"missing section {section}")

    framework = data.get("framework", {})
    if framework.get("name") != "balanced_speculative_research_v1":
        errors.append("framework.name must be balanced_speculative_research_v1")
    if framework.get("research_only") is not True:
        errors.append("framework.research_only must be true")
    for field in ["real_money_recommendation", "broker_integration", "live_orders"]:
        if framework.get(field) is not False:
            errors.append(f"framework.{field} must be false")

    account = data.get("account", {})
    expected_account = {
        "starting_equity": 3000,
        "target_300_equity": 3300,
        "target_400_equity": 3400,
        "absolute_stop_equity": 2400,
        "trailing_drawdown_dollars": 600,
        "project_stop_mode": "both",
    }
    for field, expected in expected_account.items():
        if account.get(field) != expected:
            errors.append(f"account.{field} must be {expected}")
    if float(account.get("hard_stop_drawdown_pct", 0)) != 0.20:
        errors.append("account.hard_stop_drawdown_pct must be 0.20")

    targets = data.get("targets", {})
    if targets.get("target_300", {}).get("label") != "primary_challenge_target":
        errors.append("target_300 must be primary_challenge_target")
    if targets.get("target_400", {}).get("label") != "aggressive_challenge_target":
        errors.append("target_400 must be aggressive_challenge_target")

    bands = data.get("risk_bands", {})
    if bands.get("warning", {}).get("drawdown_dollars_gte") != 300:
        errors.append("warning band must be -$300 / -10%")
    if bands.get("review", {}).get("drawdown_dollars_gte") != 450:
        errors.append("review band must be -$450 / -15%")
    if bands.get("hard_stop", {}).get("drawdown_dollars_gte") != 600:
        errors.append("hard stop band must be -$600 / -20%")

    exposure = data.get("exposure_policy", {})
    if exposure.get("1.00", {}).get("status") != "paper_forward_eligible_if_candidate_validated":
        errors.append("1.00 exposure must be paper-forward eligible if candidate validated")
    for key in ["1.05", "1.10", "1.15", "1.20", "1.25", "1.50"]:
        status = exposure.get(key, {}).get("status")
        if status not in {"diagnostic_only", "too_risky_by_default", "stress_diagnostic_only"}:
            errors.append(f"{key} exposure must be diagnostic or too risky")

    instruments = data.get("instrument_risk_budgets", {})
    for key in ["broad_etf", "cash_treasury_proxy", "crypto_spot", "simulated_leverage", "individual_stocks", "options", "futures", "forex", "intraday"]:
        if key not in instruments:
            errors.append(f"instrument risk budget missing {key}")
    if instruments.get("simulated_leverage", {}).get("paper_forward_allowed") is not False:
        errors.append("simulated_leverage must not be paper-forward allowed")

    promotion = data.get("promotion_rules", {})
    disallowed = set(promotion.get("practical_candidate", {}).get("disallowed_if", []))
    for blocker in ["tier1_exploratory", "exposure_multiplier_gt_1", "stop_enforced_metric_quality_approximate", "final_validation_completed_false"]:
        if blocker not in disallowed:
            errors.append(f"practical_candidate promotion must block {blocker}")
    paper_disallowed = set(promotion.get("paper_forward", {}).get("disallowed_if", []))
    for blocker in ["leverage_or_exposure_diagnostic", "crypto_tier1", "blocked_by_gate", "real_money_claim"]:
        if blocker not in paper_disallowed:
            errors.append(f"paper_forward promotion must block {blocker}")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "framework_name": framework.get("name"),
        "research_only": framework.get("research_only") is True,
        "real_money_recommendation": framework.get("real_money_recommendation") is True,
        "exposure_policy_count": len(exposure),
        "instrument_budget_count": len(instruments),
    }


def risk_rules_table(data: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, spec in data.get("risk_bands", {}).items():
        rows.append(
            {
                "rule_type": "risk_band",
                "name": name,
                "threshold_pct": spec.get("drawdown_pct_gte", spec.get("drawdown_pct_lt", "")),
                "threshold_dollars": spec.get("drawdown_dollars_gte", ""),
                "status": name,
                "interpretation": spec.get("interpretation", ""),
            }
        )
    for name, spec in data.get("targets", {}).items():
        rows.append(
            {
                "rule_type": "target",
                "name": name,
                "threshold_pct": spec.get("return_pct", ""),
                "threshold_dollars": spec.get("profit_dollars", ""),
                "status": spec.get("label", ""),
                "interpretation": spec.get("interpretation", ""),
            }
        )
    for exposure, spec in data.get("exposure_policy", {}).items():
        rows.append(
            {
                "rule_type": "exposure_policy",
                "name": exposure,
                "threshold_pct": "",
                "threshold_dollars": "",
                "status": spec.get("status", ""),
                "interpretation": spec.get("interpretation", ""),
            }
        )
    return pd.DataFrame(rows)


def instrument_table(data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name, spec in data.get("instrument_risk_budgets", {}).items():
        row = {"instrument_family": name}
        row.update(spec)
        rows.append(row)
    return pd.DataFrame(rows)


def metric_table(data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for priority, metrics in data.get("success_metrics", {}).items():
        for order, metric in enumerate(metrics, start=1):
            rows.append({"priority": priority, "rank_within_priority": order, "metric": metric})
    return pd.DataFrame(rows)


def promotion_table(data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for target_status, spec in data.get("promotion_rules", {}).items():
        for item in spec.get("required", []):
            rows.append({"target_status": target_status, "rule_type": "required", "rule": item})
        for item in spec.get("disallowed_if", []):
            rows.append({"target_status": target_status, "rule_type": "disallowed_if", "rule": item})
    return pd.DataFrame(rows)


def checklist(validation: dict[str, Any]) -> pd.DataFrame:
    checks = {
        "framework_loads": True,
        "research_only_boundary": validation["research_only"],
        "no_real_money_recommendation": validation["real_money_recommendation"] is False,
        "targets_defined": True,
        "risk_bands_defined": True,
        "exposure_policy_defined": validation["exposure_policy_count"] >= 7,
        "instrument_budgets_defined": validation["instrument_budget_count"] >= 9,
        "promotion_blocks_defined": validation["passed"] or not any("promotion" in error for error in validation["errors"]),
        "validation_passed": validation["passed"],
    }
    return pd.DataFrame([{"check": key, "passed": value, "notes": "" if value else "See risk_framework_validation.json"} for key, value in checks.items()])


def build_summary(data: dict[str, Any], validation: dict[str, Any], run_id: str) -> str:
    account = data["account"]
    return f"""# Risk Framework Summary

## Research-Only Statement

This is the canonical paper/demo risk-governance framework. It does not validate any strategy, recommend real-money trading, connect to brokers, or place orders.

## Run Identity

- run_id: {run_id}
- framework: {data['framework']['name']}
- validation_passed: {validation['passed']}

## Account And Targets

- starting_equity: ${account['starting_equity']:,.0f}
- primary challenge target: ${account['target_300_equity']:,.0f} (+$300 / +10%)
- aggressive challenge target: ${account['target_400_equity']:,.0f} (+$400 / +13.3%)
- hard stop: ${account['absolute_stop_equity']:,.0f} or high-water mark minus ${account['trailing_drawdown_dollars']:,.0f}

## Risk Bands

- normal: under -10% drawdown
- warning: -10% / -$300
- review: -15% / -$450
- hard stop: -20% / -$600

## Exposure Policy

Only 1.00x can be paper-forward eligible after candidate validation. 1.05x and 1.10x are diagnostic only. 1.15x and above are too risky by default or stress diagnostics.

## Decision Use

The framework prioritizes rolling 90-day +$300 before stop, stress survival, benchmark-relative result, stop-hit rate, and worst rolling drawdown. Target hits alone are not success.
"""


def warnings_text() -> str:
    return """# Warnings And Limitations

- This framework is not strategy validation.
- This framework does not recommend real-money trading.
- No broker integration, live orders, or order placement are allowed.
- +$300 is a challenge metric, not income proof.
- +$400 is aggressive and expected to be lower reliability.
- Exposure above 1.00x is diagnostic only in the current framework.
- Tier 1, leverage, exposure, crypto, and gate-blocked rows cannot become practical candidates from this framework alone.
"""


def export_evidence(data: dict[str, Any], validation: dict[str, Any]) -> tuple[Path, Path]:
    run_id = utc_run_id()
    run_dir = OUTPUT_ROOT / "runs" / run_id
    latest_dir = OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "README_FOR_AUDITOR.md").write_text(
        "# README For Auditor\n\nRead `risk_framework_summary.md`, then the CSV rule tables and `risk_framework_validation.json`. This packet is research-only and not a real-money recommendation.\n",
        encoding="utf-8",
    )
    (run_dir / "risk_framework_summary.md").write_text(build_summary(data, validation, run_id), encoding="utf-8")
    (run_dir / "risk_framework.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    risk_rules_table(data).to_csv(run_dir / "risk_rules_table.csv", index=False)
    instrument_table(data).to_csv(run_dir / "instrument_risk_budgets.csv", index=False)
    metric_table(data).to_csv(run_dir / "metric_hierarchy.csv", index=False)
    promotion_table(data).to_csv(run_dir / "promotion_demotion_rules.csv", index=False)
    checklist(validation).to_csv(run_dir / "validation_checklist.csv", index=False)
    (run_dir / "warnings_and_limitations.md").write_text(warnings_text(), encoding="utf-8")
    (run_dir / "risk_framework_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")

    files = [p.name for p in run_dir.iterdir() if p.is_file()]
    extra = sorted(set(files) - set(REQUIRED_FILES))
    missing = sorted(set(REQUIRED_FILES) - set(files))
    if extra or missing or len(files) > 10:
        raise RuntimeError(f"Risk framework evidence contract failed. extra={extra} missing={missing} file_count={len(files)}")

    shutil.copytree(run_dir, latest_dir)
    zip_path = OUTPUT_ROOT / "latest_risk_framework_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    return run_dir, latest_dir


def main() -> int:
    data = load_framework()
    validation = validate_framework(data)
    run_dir, latest_dir = export_evidence(data, validation)
    print(json.dumps(validation, indent=2, sort_keys=True))
    print(f"risk_framework_run_dir={run_dir}")
    print(f"risk_framework_latest_dir={latest_dir}")
    print(f"risk_framework_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
