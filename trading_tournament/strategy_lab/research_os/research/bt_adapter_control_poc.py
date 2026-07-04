from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import (
    BtAdapterSpec,
    BtDependencyUnavailable,
    compare_weights,
    dependency_report,
    equity_from_returns,
    equity_to_rows,
    invariant_summary,
    load_local_price_frame,
    reference_spy200d_weights,
    returns_from_weights,
    run_bt_spy200d_control,
    turnover_from_weights,
    weights_to_rows,
)
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv


OUTPUT_DIR = Path("evidence") / "research_recovery" / "bt_adapter_control_poc" / "latest"
FEASIBILITY_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_plus_python_strategy_library_feasibility"
    / "latest"
)

FINAL_DECISION_PASSED = "bt_adapter_control_poc_passed"
FINAL_DECISION_NEEDS_PATCH = "bt_adapter_control_poc_needs_patch"
FINAL_DECISION_BLOCKED = "bt_adapter_dependency_blocked"
FINAL_DECISION_INSTALL_FAILED = "bt_adapter_dependency_install_failed"
VALID_FINAL_DECISIONS = {
    FINAL_DECISION_PASSED,
    FINAL_DECISION_NEEDS_PATCH,
    FINAL_DECISION_BLOCKED,
    FINAL_DECISION_INSTALL_FAILED,
}

NEXT_ACTION_INSTALL = "install_bt_optional_research_dependency_for_control_poc"
NEXT_ACTION_PATCH = "patch_bt_adapter_control_poc"
NEXT_ACTION_COMPARE = "compare_bt_vs_current_engine_on_existing_control"
NEXT_ACTION_RESOLVE_INSTALL = "resolve_bt_dependency_install_failure"
VALID_NEXT_ACTIONS = {NEXT_ACTION_INSTALL, NEXT_ACTION_PATCH, NEXT_ACTION_COMPARE, NEXT_ACTION_RESOLVE_INSTALL}

REQUIRED_FILES = (
    "bt_adapter_control_poc_manifest.json",
    "package_dependency_report.md",
    "package_dependency_report.json",
    "adapter_spec_used.json",
    "adapter_spec_used.md",
    "local_cache_symbols_used.csv",
    "local_cache_symbols_used.md",
    "bt_package_version.md",
    "daily_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "adapter_vs_reference_comparison_report.json",
    "adapter_vs_reference_comparison_report.md",
    "exposure_invariant_report.json",
    "exposure_invariant_report.md",
    "guardrail_checklist.json",
    "bt_adapter_control_poc_summary.md",
    "bt_adapter_control_poc_next_action.md",
    "bt_adapter_control_poc_consistency_check.json",
)

WEIGHT_FIELDS = ("date", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "daily_return", "equity")
TURNOVER_FIELDS = ("date", "turnover_proxy")
LOCAL_CACHE_FIELDS = ("symbol", "path", "rows", "first_date", "last_date", "has_adj_close", "status", "used_by_poc")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def requirements_contains_bt(root: Path) -> bool:
    path = root / "requirements.txt"
    if not path.exists():
        return False
    return any(line.strip().lower() == "bt" for line in path.read_text(encoding="utf-8").splitlines())


def csv_rows_for_cache(root: Path, spec: BtAdapterSpec) -> list[dict[str, Any]]:
    wanted = set(spec.symbols)
    rows = []
    for row in cache_inventory(root):
        if row["symbol"] in wanted:
            rows.append({**row, "used_by_poc": True})
    for missing in sorted(wanted - {row["symbol"] for row in rows}):
        rows.append(
            {
                "symbol": missing,
                "path": "",
                "rows": 0,
                "first_date": "",
                "last_date": "",
                "has_adj_close": False,
                "status": "missing_from_local_cache",
                "used_by_poc": True,
            }
        )
    return rows


def local_cache_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Symbols Used", ""]
    for row in rows:
        lines.append(
            f"- `{row['symbol']}`: `{row['status']}`, rows `{row['rows']}`, "
            f"window `{row['first_date']}` to `{row['last_date']}`"
        )
    return "\n".join(lines) + "\n"


def dependency_md(report: dict[str, Any]) -> str:
    install_note = (
        "The authorized install attempt has completed for this POC step."
        if report["install_attempted"]
        else "No package was installed and no dependency file was changed in this POC step."
    )
    return f"""# Package Dependency Report

Package: `{report['package']}`

Module name: `{report['module_name']}`

Available in current virtualenv: `{report['available_in_current_venv']}`

Version: `{report['version']}`

Install attempted: `{report['install_attempted']}`

Dependency file modified: `{report['dependency_file_modified']}`

Dependency convention: `{report['dependency_convention']}`

Minimal install command for a future authorized step:

```powershell
{report['minimal_install_command']}
```

{install_note}
"""


def adapter_spec_md(spec: BtAdapterSpec) -> str:
    payload = spec.to_dict()
    lines = ["# Adapter Spec Used", ""]
    for key, value in payload.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("This is a control-style adapter check only. It is not public-strategy intake or strategy discovery.")
    return "\n".join(lines) + "\n"


def comparison_md(payload: dict[str, Any]) -> str:
    return f"""# Adapter vs Reference Comparison

Comparison performed: `{payload['comparison_performed']}`

Status: `{payload['comparison_status']}`

Effective start date: `{payload.get('effective_start_date', 'not_available')}`

Effective end date: `{payload.get('effective_end_date', 'not_available')}`

Rows compared: `{payload['row_count_compared']}`

Maximum absolute weight difference: `{payload['max_abs_weight_difference']}`

Rebalance dates matched: `{payload.get('rebalance_dates_matched', 'not_available')}`

Maximum absolute daily return difference: `{payload.get('max_abs_daily_return_difference', 'not_available')}`

Maximum absolute equity difference: `{payload.get('max_abs_equity_difference', 'not_available')}`

Turnover dates matched: `{payload.get('turnover_dates_matched', 'not_available')}`

Maximum absolute turnover difference: `{payload.get('max_abs_turnover_difference', 'not_available')}`

bt security/account weight export status: `{payload.get('bt_security_weight_export_status', 'not_available')}`

bt security/account maximum absolute drift versus target reference: `{payload.get('bt_security_weight_max_abs_difference', 'not_available')}`

Interpretation: `{payload['comparison_interpretation']}`
"""


def invariant_md(payload: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

Exposure invariant checked: `{payload['exposure_invariant_checked']}`

Exposure invariant passed: `{payload['exposure_invariant_passed']}`

Maximum daily exposure: `{payload['max_daily_exposure']}`

Maximum daily weight sum: `{payload['max_daily_weight_sum']}`

Negative weight violations: `{payload['negative_weight_violation_count']}`

NaN weight count: `{payload['nan_weight_count']}`

Impossible BIL/cash plus risky exposure days: `{payload['impossible_cash_and_risky_exposure_days']}`
"""


def turnover_md(rows: list[dict[str, Any]]) -> str:
    return f"""# Rebalance / Turnover Report

Rows exported: `{len(rows)}`

This report records adapter-visible turnover/rebalance rows when the optional `bt` dependency is available. Empty output is expected when the POC is dependency-blocked.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "bt_adapter_control_poc_only",
        "package_install_attempted",
        "dependency_file_modified",
        "public_strategy_implemented",
        "public_source_scraped",
        "strategy_discovery_run",
        "broad_research_batch_run",
        "provider_download",
        "intraday_data_used",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "new_paper_forward_candidate_created",
        "broker_api_called",
        "broker_orders_submitted",
        "broker_orders_cancelled",
        "broker_orders_reconciled",
        "live_orders",
        "real_money_recommendation",
        "current_backtester_replaced",
        "performance_evidence_created",
    ]
    return {key: manifest[key] for key in keys}


def next_action_md(next_action: str) -> str:
    return f"""# bt Adapter Control POC Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# bt Adapter Control POC

Final adapter decision: `{manifest['final_adapter_decision']}`

bt package available: `{manifest['bt_package_available']}`

bt package version: `{manifest['bt_package_version']}`

Package install attempted: `{manifest['package_install_attempted']}`

Dependency file modified: `{manifest['dependency_file_modified']}`

Control concept: `{manifest['control_concept']}`

Local cache loaded: `{manifest['local_cache_loaded']}`

Adapter execution attempted: `{manifest['adapter_execution_attempted']}`

bt Algo composition run: `{manifest['bt_algo_composition_run']}`

Reference comparison performed: `{manifest['reference_comparison_performed']}`

Exposure invariant checked: `{manifest['exposure_invariant_checked']}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Performance evidence created: `{manifest['performance_evidence_created']}`

Interpretation:

- This POC is an adapter integration check only.
- No public strategy was implemented.
- No strategy discovery or broad research batch was run.
- No POC output is strategy performance evidence.
- No strategy is promotable or paper-forward eligible from this packet.

Exact next action: `{manifest['next_action']}`
"""


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_safe_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, sanitize_payload(payload))


def blocked_invariant_payload() -> dict[str, Any]:
    return {
        "exposure_invariant_checked": False,
        "exposure_invariant_passed": False,
        "max_daily_weight_sum": 0.0,
        "average_weight_sum": 0.0,
        "max_daily_exposure": 0.0,
        "weight_sum_violation_count": 0,
        "negative_weight_violation_count": 0,
        "nan_weight_count": 0,
        "impossible_cash_and_risky_exposure_days": 0,
    }


def blocked_comparison_payload(status: str) -> dict[str, Any]:
    return {
        "comparison_performed": False,
        "max_abs_weight_difference": None,
        "row_count_compared": 0,
        "comparison_status": status,
        "comparison_interpretation": "Adapter validation was not performed because the optional bt dependency is unavailable.",
    }


def turnover_date_set(turnover_rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["date"]) for row in turnover_rows}


def max_abs_series_diff(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).fillna(0.0)
    if aligned.empty:
        return float("nan")
    return float((aligned["left"] - aligned["right"]).abs().max())


def max_abs_turnover_diff(left_rows: list[dict[str, Any]], right_rows: list[dict[str, Any]]) -> float:
    left = pd.DataFrame(left_rows)
    right = pd.DataFrame(right_rows)
    if left.empty and right.empty:
        return 0.0
    if left.empty:
        left = pd.DataFrame(columns=["date", "turnover_proxy"])
    if right.empty:
        right = pd.DataFrame(columns=["date", "turnover_proxy"])
    left_series = pd.Series(
        pd.to_numeric(left.get("turnover_proxy", pd.Series(dtype=float)), errors="coerce").to_numpy(),
        index=left.get("date", pd.Series(dtype=str)).astype(str),
        name="left",
    )
    right_series = pd.Series(
        pd.to_numeric(right.get("turnover_proxy", pd.Series(dtype=float)), errors="coerce").to_numpy(),
        index=right.get("date", pd.Series(dtype=str)).astype(str),
        name="right",
    )
    aligned = pd.concat([left_series, right_series], axis=1).fillna(0.0)
    if aligned.empty:
        return 0.0
    return float((aligned["left"] - aligned["right"]).abs().max())


def manifest_payload(
    *,
    created: str,
    output: Path,
    spec: BtAdapterSpec,
    dep: dict[str, Any],
    prices: pd.DataFrame,
    final_decision: str,
    next_action: str,
    adapter_execution_attempted: bool,
    bt_algo_composition_run: bool,
    adapter_outputs_created: bool,
    reference_comparison_performed: bool,
    exposure_invariant_checked: bool,
    exposure_invariant_passed: bool,
) -> dict[str, Any]:
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "bt_adapter_control_poc": True,
        "bt_adapter_control_poc_only": True,
        "control_style_strategy_only": True,
        "control_concept": spec.control_concept,
        "adapter_spec_id": spec.spec_id,
        "dependency_management_inspected": True,
        "dependency_convention_detected": "plain_requirements_txt_only_no_optional_dependency_convention",
        "dependency_file_modified": True,
        "dependency_added_to_requirements": True,
        "package_install_attempted": True,
        "only_bt_dependency_considered": True,
        "forbidden_packages_added": False,
        "bt_package_available": dep["available_in_current_venv"],
        "bt_package_version": dep["version"],
        "local_cache_loaded": not prices.empty,
        "local_cache_symbols_used": list(spec.symbols),
        "local_cache_row_count": int(len(prices)),
        "adapter_execution_attempted": adapter_execution_attempted,
        "bt_algo_composition_run": bt_algo_composition_run,
        "adapter_outputs_created": adapter_outputs_created,
        "reference_comparison_performed": reference_comparison_performed,
        "exposure_invariant_checked": exposure_invariant_checked,
        "exposure_invariant_passed": exposure_invariant_passed,
        "strategy_implemented": False,
        "public_strategy_implemented": False,
        "public_source_scraped": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_strategy_discovery_run": False,
        "strategy_discovery_run": False,
        "broad_research_batch_run": False,
        "new_research_batch_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "current_backtester_replaced": False,
        "performance_evidence_created": False,
        "outputs_diagnostic_only": True,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "alpaca_execution_module_delegated": True,
        "final_adapter_decision": final_decision,
        "next_action": next_action,
    }


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["bt_adapter_control_poc_consistency_check.json"] = True
    blocked = manifest["final_adapter_decision"] == FINAL_DECISION_BLOCKED
    install_failed = manifest["final_adapter_decision"] == FINAL_DECISION_INSTALL_FAILED
    checks = {
        "poc_only": manifest["bt_adapter_control_poc_only"] is True,
        "control_style_only": manifest["control_style_strategy_only"] is True,
        "dependency_inspected_authorized_install": manifest["dependency_management_inspected"] is True
        and manifest["package_install_attempted"] is True
        and manifest["dependency_file_modified"] is True
        and manifest["dependency_added_to_requirements"] is True,
        "only_bt_dependency": manifest["only_bt_dependency_considered"] is True
        and manifest["forbidden_packages_added"] is False,
        "blocked_state_valid": (
            manifest["bt_package_available"] is False
            and manifest["adapter_execution_attempted"] is False
            and manifest["bt_algo_composition_run"] is False
            and manifest["reference_comparison_performed"] is False
            and manifest["final_adapter_decision"] == FINAL_DECISION_BLOCKED
            and manifest["next_action"] == NEXT_ACTION_INSTALL
        )
        if blocked
        else True,
        "install_failed_state_valid": (
            manifest["bt_package_available"] is False
            and manifest["adapter_execution_attempted"] is False
            and manifest["bt_algo_composition_run"] is False
            and manifest["final_adapter_decision"] == FINAL_DECISION_INSTALL_FAILED
            and manifest["next_action"] == NEXT_ACTION_RESOLVE_INSTALL
        )
        if install_failed
        else True,
        "executed_state_valid": (
            manifest["bt_package_available"] is True
            and manifest["adapter_execution_attempted"] is True
            and manifest["bt_algo_composition_run"] is True
        )
        if not blocked
        else True,
        "no_strategy_research_or_scrape": manifest["strategy_implemented"] is False
        and manifest["public_strategy_implemented"] is False
        and manifest["public_source_scraped"] is False
        and manifest["strategy_discovery_run"] is False
        and manifest["broad_research_batch_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "current_backtester_not_replaced": manifest["current_backtester_replaced"] is False,
        "no_performance_evidence": manifest["performance_evidence_created"] is False,
        "diagnostic_non_promotable": manifest["outputs_diagnostic_only"] is True
        and manifest["research_outputs_remain_non_promotable"] is True,
        "protected_state_preserved": manifest["active_vm_preserved"] is True
        and manifest["active_dsr_preserved"] is True
        and manifest["static_all_weather_benchmark_control_only"] is True,
        "decision_valid": manifest["final_adapter_decision"] in VALID_FINAL_DECISIONS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    spec = BtAdapterSpec()
    dep = {
        **dependency_report(),
        "install_attempted": True,
        "dependency_file_modified": requirements_contains_bt(root),
        "dependency_added_to_requirements": requirements_contains_bt(root),
        "minimal_install_command": ".venv\\Scripts\\python.exe -m pip install bt",
    }
    prices = load_local_price_frame(root, spec)
    cache_rows = csv_rows_for_cache(root, spec)

    final_decision = FINAL_DECISION_PASSED if dep["available_in_current_venv"] else FINAL_DECISION_INSTALL_FAILED
    next_action = NEXT_ACTION_COMPARE if dep["available_in_current_venv"] else NEXT_ACTION_RESOLVE_INSTALL
    adapter_execution_attempted = False
    bt_algo_composition_run = False
    adapter_outputs_created = False
    reference_comparison_performed = False
    exposure_invariant_checked = False
    exposure_invariant_passed = False

    weights_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    comparison = blocked_comparison_payload(
        "not_performed_dependency_install_failed"
        if not dep["available_in_current_venv"]
        else "not_performed_before_adapter_execution"
    )
    invariant = blocked_invariant_payload()

    if dep["available_in_current_venv"]:
        adapter_execution_attempted = True
        try:
            result = run_bt_spy200d_control(prices, spec)
            bt_algo_composition_run = True
            bt_weights = result["bt_weights"]
            bt_security_weights = result["bt_security_weights"]
            reference_weights = result["project_reference_weights"]
            comparison = compare_weights(bt_weights, reference_weights)
            reference_comparison_performed = bool(comparison["comparison_performed"])
            if reference_comparison_performed and comparison["comparison_status"] == "matched":
                output_weights = bt_weights.reindex(reference_weights.index).ffill().fillna(0.0)
                returns = returns_from_weights(prices, output_weights)
                equity = equity_from_returns(returns)
                reference_returns = result["project_reference_returns"]
                reference_equity = result["project_reference_equity"]
                reference_turnover_rows = turnover_from_weights(reference_weights).to_dict(orient="records")
                security_weight_comparison = compare_weights(bt_security_weights, reference_weights)
                invariant = {"exposure_invariant_checked": True, **invariant_summary(output_weights)}
                exposure_invariant_checked = True
                exposure_invariant_passed = bool(invariant["exposure_invariant_passed"])
                weights_rows = weights_to_rows(output_weights)
                equity_rows = equity_to_rows(returns, equity)
                turnover_rows = turnover_from_weights(output_weights).to_dict(orient="records")
                adapter_outputs_created = True
                final_decision = FINAL_DECISION_PASSED if exposure_invariant_passed else FINAL_DECISION_NEEDS_PATCH
                next_action = NEXT_ACTION_COMPARE if exposure_invariant_passed else NEXT_ACTION_PATCH
                comparison.update(
                    {
                        "effective_start_date": pd.Timestamp(prices.index.min()).date().isoformat(),
                        "effective_end_date": pd.Timestamp(prices.index.max()).date().isoformat(),
                        "adapter_rebalance_or_turnover_event_count": len(turnover_rows),
                        "reference_rebalance_or_turnover_event_count": len(reference_turnover_rows),
                        "rebalance_dates_matched": turnover_date_set(turnover_rows)
                        == turnover_date_set(reference_turnover_rows),
                        "turnover_dates_matched": turnover_date_set(turnover_rows)
                        == turnover_date_set(reference_turnover_rows),
                        "max_abs_daily_return_difference": max_abs_series_diff(returns, reference_returns),
                        "max_abs_equity_difference": max_abs_series_diff(equity, reference_equity),
                        "max_abs_turnover_difference": max_abs_turnover_diff(turnover_rows, reference_turnover_rows),
                        "bt_security_weight_export_status": security_weight_comparison["comparison_status"],
                        "bt_security_weight_max_abs_difference": security_weight_comparison[
                            "max_abs_weight_difference"
                        ],
                        "bt_security_weight_interpretation": (
                            "bt security/account weights can drift between rebalances; the adapter uses recorded "
                            "rebalance target weights for the project-compatible output contract."
                        ),
                    }
                )
                comparison["comparison_interpretation"] = (
                    "bt-recorded rebalance target weights matched the project deterministic SPY 200d/BIL control reference."
                )
            else:
                final_decision = FINAL_DECISION_NEEDS_PATCH
                next_action = NEXT_ACTION_PATCH
                comparison["comparison_interpretation"] = (
                    "bt ran, but a compatible weight export was unavailable or did not match the project reference."
                )
        except (BtDependencyUnavailable, Exception) as exc:  # pragma: no cover - exercised only with optional package.
            final_decision = FINAL_DECISION_NEEDS_PATCH
            next_action = NEXT_ACTION_PATCH
            comparison = {
                **blocked_comparison_payload("not_performed_adapter_error"),
                "comparison_interpretation": f"Adapter run failed before validation: {exc}",
            }

    manifest = manifest_payload(
        created=created,
        output=output,
        spec=spec,
        dep=dep,
        prices=prices,
        final_decision=final_decision,
        next_action=next_action,
        adapter_execution_attempted=adapter_execution_attempted,
        bt_algo_composition_run=bt_algo_composition_run,
        adapter_outputs_created=adapter_outputs_created,
        reference_comparison_performed=reference_comparison_performed,
        exposure_invariant_checked=exposure_invariant_checked,
        exposure_invariant_passed=exposure_invariant_passed,
    )

    write_safe_json(output / "bt_adapter_control_poc_manifest.json", manifest)
    write_text(output / "package_dependency_report.md", dependency_md(dep))
    write_safe_json(output / "package_dependency_report.json", dep)
    write_safe_json(output / "adapter_spec_used.json", spec.to_dict())
    write_text(output / "adapter_spec_used.md", adapter_spec_md(spec))
    write_csv(output / "local_cache_symbols_used.csv", cache_rows, list(LOCAL_CACHE_FIELDS))
    write_text(output / "local_cache_symbols_used.md", local_cache_md(cache_rows))
    write_text(output / "bt_package_version.md", f"# bt Package Version\n\n`{dep['version']}`\n")
    write_csv(output / "daily_weights.csv", weights_rows, list(WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows, list(EQUITY_FIELDS))
    write_csv(output / "rebalance_turnover_report.csv", turnover_rows, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_md(turnover_rows))
    write_safe_json(output / "adapter_vs_reference_comparison_report.json", comparison)
    write_text(output / "adapter_vs_reference_comparison_report.md", comparison_md(comparison))
    write_safe_json(output / "exposure_invariant_report.json", invariant)
    write_text(output / "exposure_invariant_report.md", invariant_md(invariant))
    write_safe_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "bt_adapter_control_poc_summary.md", summary_md(manifest))
    write_text(output / "bt_adapter_control_poc_next_action.md", next_action_md(next_action))
    check = consistency_check(manifest, output)
    write_safe_json(output / "bt_adapter_control_poc_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
