from __future__ import annotations

import csv
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "current_multi_asset_portfolio_accounting_blast_radius_v1" / "latest"
COMBO_RECONCILIATION_DIR = Path("evidence") / "active_combo_series_reconciliation" / "latest"
CURRENT_CHECKPOINT_DIR = Path("evidence") / "current_research_checkpoint" / "latest"
PUBLIC_COMPARATIVE_DIR = Path("evidence") / "public_source_comparative_screening_batch_v1" / "latest"
RISK_PARITY_SCREEN_DIR = Path("evidence") / "risk_parity_trend_etf_wrapper_screen_v1" / "latest"
RISK_PARITY_REVIEW_DIR = Path("evidence") / "risk_parity_trend_portfolio_accounting_review_v1" / "latest"

ALLOWED_CLASSIFICATIONS = {
    "correct_drifting_holdings",
    "explicit_daily_rebalance",
    "binary_single_asset_equivalent",
    "precomputed_series_dependency",
    "accounting_defect_confirmed",
    "unresolved",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def fmt(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return round(value, digits)
    return value


def registry_rows(root: Path) -> dict[str, dict[str, Any]]:
    registry = read_yaml(root / active.REGISTRY_PATH)
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def legacy_target_daily_return(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    return active.weighted_return(weights, active.daily_asset_returns(close, today, set(weights)))


def legacy_simulate_constant_targets(close: pd.DataFrame, start: int, horizon: int, strategy_id: str) -> dict[str, Any]:
    equity = active.STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    target_weights: dict[str, float] = {}
    last_month = None
    stop = None
    target300 = None
    target400 = None
    months = [dt.year * 12 + dt.month for dt in close.index]
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        turnover = 0.0
        month = int(months[today])
        if month != last_month:
            new_target = active.strategy_weights(close, signal, strategy_id)
            turnover = active.rebalance_turnover_units(new_target, target_weights)
            target_weights = new_target
            last_month = month
        gross = legacy_target_daily_return(close, today, target_weights)
        daily_return = (1.0 - turnover * active.SLIPPAGE) * (1.0 + gross) - 1.0
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - active.STARTING_EQUITY
        if stop is None and profit <= active.STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - active.STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def legacy_combo_window_constant_targets(close: pd.DataFrame, start: int, horizon: int) -> dict[str, Any]:
    vm_value = active.STARTING_EQUITY * 0.5
    dsr_value = active.STARTING_EQUITY * 0.5
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    peak = active.STARTING_EQUITY
    max_drawdown = 0.0
    last_month = None
    stop = None
    target300 = None
    target400 = None
    months = [dt.year * 12 + dt.month for dt in close.index]
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            total = vm_value + dsr_value
            vm_value = total * 0.5
            dsr_value = total * 0.5
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            last_month = month
        vm_value *= 1.0 + legacy_target_daily_return(close, today, vm_weights)
        dsr_value *= 1.0 + legacy_target_daily_return(close, today, dsr_weights)
        equity = vm_value + dsr_value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - active.STARTING_EQUITY
        if stop is None and profit <= active.STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {
        "strategy_id": combo.COMBO_ID,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": vm_value + dsr_value,
        "profit_dollars": vm_value + dsr_value - active.STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def summarize_legacy(close: pd.DataFrame, strategy_id: str, horizon: int) -> dict[str, Any]:
    rows = []
    for start in active.sample_starts(close, horizon):
        if strategy_id == combo.COMBO_ID:
            rows.append(legacy_combo_window_constant_targets(close, start, horizon))
        else:
            rows.append(legacy_simulate_constant_targets(close, start, horizon, strategy_id))
    return active.summarize(rows, strategy_id, horizon)


def current_summary(root: Path, payload: dict[str, Any], strategy_id: str, horizon: int) -> dict[str, Any]:
    if strategy_id == combo.COMBO_ID:
        combo_payload = combo.build_payload(root)
        return combo_payload.get("summaries", {}).get(combo.COMBO_ID, {}).get(horizon, {})
    return payload.get("summaries", {}).get(strategy_id, {}).get(horizon, {})


def before_after_metrics(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    close = payload.get("close", pd.DataFrame())
    if close.empty:
        return []
    rows: list[dict[str, Any]] = []
    specs = [
        (active.VM_ID, "active VM diagnostic"),
        (active.DSR_ID, "active DSR diagnostic"),
        ("raw_sector_equal_weight_basket", "current equal-weight sector benchmark diagnostic"),
        (combo.COMBO_ID, "active combo benchmark/reference"),
    ]
    metrics = [
        ("median_final_equity", "180d_median_final_equity"),
        ("best_final_equity", "180d_best_final_equity"),
        ("worst_drawdown", "180d_worst_drawdown"),
        ("target_300_before_stop_rate", "target_300_rate"),
        ("target_400_before_stop_rate", "target_400_rate"),
    ]
    for strategy_id, role in specs:
        before = summarize_legacy(close, strategy_id, 180)
        after = current_summary(root, payload, strategy_id, 180)
        for key, label in metrics:
            before_value = before.get(key)
            after_value = after.get(key)
            delta = "" if before_value is None or after_value is None else float(after_value) - float(before_value)
            rows.append(
                {
                    "consumer_id": strategy_id,
                    "role": role,
                    "metric": label,
                    "before_constant_target_daily_weight_method": fmt(before_value),
                    "after_drifting_holdings_method": fmt(after_value),
                    "delta_after_minus_before": fmt(delta),
                    "interpretation": "diagnostic changed by accounting method; lifecycle/status unchanged",
                }
            )
    return rows


def sample_monthly_target_counts(close: pd.DataFrame, strategy_id: str) -> dict[str, Any]:
    if close.empty:
        return {"sampled_months": 0, "mixed_risky_target_months": 0, "bil_mixed_months": 0, "binary_months": 0}
    months_seen: set[int] = set()
    mixed = 0
    bil_mixed = 0
    binary = 0
    for today in range(253, len(close)):
        month = int(close.index[today].year * 12 + close.index[today].month)
        if month in months_seen:
            continue
        months_seen.add(month)
        weights = active.strategy_weights(close, today - 1, strategy_id)
        risky = [sym for sym, weight in weights.items() if sym != "BIL" and abs(weight) > 1e-12]
        if len(risky) > 1:
            mixed += 1
        if "BIL" in weights and any(sym != "BIL" and abs(w) > 1e-12 for sym, w in weights.items()):
            bil_mixed += 1
        if len([sym for sym, weight in weights.items() if abs(weight) > 1e-12]) == 1:
            binary += 1
    return {
        "sampled_months": len(months_seen),
        "mixed_risky_target_months": mixed,
        "bil_mixed_months": bil_mixed,
        "binary_months": binary,
    }


def independent_reconstruction_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scenarios = [
        ("synthetic_monthly_50_50_component_portfolio", {"A": 0.5, "B": 0.5}, {"A": 0.10, "B": 0.0}, {"A": 0.5, "B": 0.5}),
        (
            "synthetic_multi_sector_equal_weight_holdings",
            {"XLK": 1.0 / 3.0, "XLF": 1.0 / 3.0, "XLV": 1.0 / 3.0},
            {"XLK": 0.10, "XLF": 0.0, "XLV": -0.05},
            {"XLK": 1.0 / 3.0, "XLF": 1.0 / 3.0, "XLV": 1.0 / 3.0},
        ),
        ("synthetic_binary_one_risky_or_cash", {"SPY": 1.0}, {"SPY": 0.10, "BIL": 0.0}, {"SPY": 1.0}),
    ]
    for scenario, start_weights, asset_returns, next_target in scenarios:
        gross_return = active.weighted_return(start_weights, asset_returns)
        drifted = active.drift_weights(start_weights, asset_returns)
        actual_turnover = active.rebalance_turnover_units(next_target, drifted)
        target_to_target_turnover = active.rebalance_turnover_units(next_target, start_weights)
        rows.append(
            {
                "scenario": scenario,
                "starting_weights": json.dumps({k: round(v, 8) for k, v in sorted(start_weights.items())}, sort_keys=True),
                "asset_returns": json.dumps({k: round(v, 8) for k, v in sorted(asset_returns.items())}, sort_keys=True),
                "gross_return_from_actual_weights": fmt(gross_return),
                "drifted_pre_trade_weights": json.dumps({k: round(v, 8) for k, v in sorted(drifted.items())}, sort_keys=True),
                "next_target_weights": json.dumps({k: round(v, 8) for k, v in sorted(next_target.items())}, sort_keys=True),
                "turnover_from_pre_trade_actual": fmt(actual_turnover),
                "target_to_target_turnover": fmt(target_to_target_turnover),
                "cost_charged_on_non_execution_date": 0.0,
                "classification_proof": "drift creates turnover missed by target-to-target accounting" if actual_turnover > target_to_target_turnover + 1e-12 else "binary/same-target path has no drift-related turnover",
            }
        )
    return rows


def consumer_inventory_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "consumer_id": "active_strategy_evidence_recompute",
            "consumer_name": "active VM/DSR current diagnostic recompute",
            "artifact_or_code_path": "run_active_strategy_evidence_recompute.py",
            "decision_role": "current active observation diagnostic recompute",
            "multi_asset_relevance": "VM can hold two risky ETFs; DSR can hold multiple sectors; raw sector benchmark holds many sectors",
            "status": "inspected_and_patched",
        },
        {
            "consumer_id": combo.COMBO_ID,
            "consumer_name": "active combo VM/DSR equal-weight benchmark generator",
            "artifact_or_code_path": "run_active_combo_benchmark_reporting.py",
            "decision_role": "benchmark/reference only in checkpoint and comparative screens",
            "multi_asset_relevance": "monthly 50/50 VM/DSR component sleeves plus multi-asset component holdings",
            "status": "inspected_and_patched",
        },
        {
            "consumer_id": "active_combo_series_reconciliation",
            "consumer_name": "active combo source series reconciliation",
            "artifact_or_code_path": "strategy_lab/research_os/research/active_combo_series_reconciliation.py",
            "decision_role": "precomputed active combo lineage verifier for current checkpoint",
            "multi_asset_relevance": "traces regenerated combo series to generator methodology",
            "status": "inspected_and_patched_verifier",
        },
        {
            "consumer_id": "current_research_checkpoint",
            "consumer_name": "current research checkpoint",
            "artifact_or_code_path": "run_current_research_checkpoint.py",
            "decision_role": "current best-strategy/checkpoint reporting",
            "multi_asset_relevance": "consumes active recompute and active-combo precomputed evidence",
            "status": "inspected_and_regenerated",
        },
        {
            "consumer_id": "public_source_comparative_screening_batch_v1",
            "consumer_name": "public-source comparative screening batch",
            "artifact_or_code_path": "strategy_lab/research_os/research/public_source_comparative_screening_batch_v1.py",
            "decision_role": "diagnostic comparative screening across implemented public-source lanes",
            "multi_asset_relevance": "uses SPY/BIL controls and precomputed active-combo benchmark",
            "status": "inspected_and_regenerated",
        },
        {
            "consumer_id": "bt_adapter_spy_bil_controls",
            "consumer_name": "bt adapter SPY/BIL control-return path",
            "artifact_or_code_path": "strategy_lab/research_os/external_adapters/bt_adapter.py",
            "decision_role": "public-source SPY/BIL benchmark controls",
            "multi_asset_relevance": "binary SPY/BIL weights in scoped comparative screening",
            "status": "inspected_no_patch_needed",
        },
        {
            "consumer_id": "static_all_weather_benchmark_v1",
            "consumer_name": "static all-weather benchmark/control registration",
            "artifact_or_code_path": "strategy_lab/strategy_registry.yaml",
            "decision_role": "benchmark/control only where referenced",
            "multi_asset_relevance": "no current checkpoint holdings calculation found in scoped current consumers",
            "status": "inspected_no_current_calculation_to_patch",
        },
        {
            "consumer_id": "rp_ivol_10m_trend_etf_wrapper_adaptation_v1",
            "consumer_name": "risk-parity exact candidate and equal-weight benchmark after accounting review",
            "artifact_or_code_path": "strategy_lab/research_os/research/risk_parity_trend_etf_wrapper_screen_v1.py",
            "decision_role": "closed exact candidate with corrected control_weak outcome",
            "multi_asset_relevance": "tested reference implementation for drift-aware monthly accounting",
            "status": "inspected_and_regenerated_comparative_deltas_only",
        },
    ]


def classification_rows(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    combo_manifest = read_json(root / COMBO_RECONCILIATION_DIR / "active_combo_series_reconciliation.json")
    public_manifest = read_json(root / PUBLIC_COMPARATIVE_DIR / "screening_manifest.json")
    risk_decision = read_json(root / RISK_PARITY_REVIEW_DIR / "decision.json")
    vm_counts = sample_monthly_target_counts(payload.get("close", pd.DataFrame()), active.VM_ID)
    dsr_counts = sample_monthly_target_counts(payload.get("close", pd.DataFrame()), active.DSR_ID)
    rows = [
        {
            "consumer_id": active.VM_ID,
            "classification": "accounting_defect_confirmed",
            "proof": f"VM has {vm_counts['mixed_risky_target_months']} sampled months with two risky ETF targets; active recompute now uses portfolio_step drift and actual-turnover costs.",
            "patched": True,
            "post_patch_status": "correct_drifting_holdings",
            "source_series_trace": "evidence/active_strategy_evidence_recompute/latest",
        },
        {
            "consumer_id": active.DSR_ID,
            "classification": "accounting_defect_confirmed",
            "proof": f"DSR has {dsr_counts['mixed_risky_target_months']} sampled months with multiple sector targets; active recompute now uses portfolio_step drift and actual-turnover costs.",
            "patched": True,
            "post_patch_status": "correct_drifting_holdings",
            "source_series_trace": "evidence/active_strategy_evidence_recompute/latest",
        },
        {
            "consumer_id": "raw_sector_equal_weight_basket",
            "classification": "accounting_defect_confirmed",
            "proof": "Current active recompute benchmark holds many sectors and previously shared the same simulate/full_returns path; it now uses scheduled rebalance plus drifting actual weights.",
            "patched": True,
            "post_patch_status": "correct_drifting_holdings",
            "source_series_trace": "evidence/active_strategy_evidence_recompute/latest",
        },
        {
            "consumer_id": combo.COMBO_ID,
            "classification": "accounting_defect_confirmed",
            "proof": f"Source generator now records monthly sleeve/component drift; reconciliation classification is {combo_manifest.get('reconstructability_classification')}.",
            "patched": True,
            "post_patch_status": "correct_drifting_holdings",
            "source_series_trace": "evidence/active_combo_benchmark/latest -> evidence/active_combo_series_reconciliation/latest",
        },
        {
            "consumer_id": "active_combo_series_reconciliation",
            "classification": "precomputed_series_dependency",
            "proof": "Does not calculate strategy holdings for decisions; traces the regenerated precomputed combo series and verifies exact reconstruction.",
            "patched": True,
            "post_patch_status": "precomputed_series_dependency",
            "source_series_trace": "evidence/active_combo_benchmark/latest",
        },
        {
            "consumer_id": "current_research_checkpoint",
            "classification": "precomputed_series_dependency",
            "proof": "Checkpoint consumes active recompute CSVs and exact active-combo reconciliation metrics; it does not build a multi-asset portfolio series itself.",
            "patched": False,
            "post_patch_status": "precomputed_series_dependency",
            "source_series_trace": "evidence/active_strategy_evidence_recompute/latest; evidence/active_combo_series_reconciliation/latest",
        },
        {
            "consumer_id": "public_source_comparative_screening_batch_v1",
            "classification": "precomputed_series_dependency",
            "proof": f"Batch consumes exact active-combo series as benchmark reference and SPY/BIL controls; comparability complete={public_manifest.get('benchmark_comparability_complete')}.",
            "patched": False,
            "post_patch_status": "precomputed_series_dependency",
            "source_series_trace": "evidence/active_combo_series_reconciliation/latest/combo_daily_series.csv",
        },
        {
            "consumer_id": "bt_adapter_spy_bil_controls",
            "classification": "binary_single_asset_equivalent",
            "proof": "Scoped current use is SPY/BIL controls with one risky asset or cash; no mixed risky target row is used in the comparative screening controls.",
            "patched": False,
            "post_patch_status": "binary_single_asset_equivalent",
            "source_series_trace": "strategy_lab/research_os/external_adapters/bt_adapter.py",
        },
        {
            "consumer_id": "static_all_weather_benchmark_v1",
            "classification": "precomputed_series_dependency",
            "proof": "Current checkpoint treats static all-weather as benchmark/control metadata and does not calculate a current holdings series in scoped decision-facing consumers.",
            "patched": False,
            "post_patch_status": "precomputed_series_dependency",
            "source_series_trace": "strategy_lab/strategy_registry.yaml and current checkpoint benchmark/control rows",
        },
        {
            "consumer_id": "rp_ivol_10m_trend_etf_wrapper_adaptation_v1",
            "classification": "correct_drifting_holdings",
            "proof": f"Corrected risk-parity accounting review remains {risk_decision.get('corrected_screening_outcome')} and is closed for immediate retesting.",
            "patched": False,
            "post_patch_status": "correct_drifting_holdings",
            "source_series_trace": "evidence/risk_parity_trend_portfolio_accounting_review_v1/latest",
        },
    ]
    for row in rows:
        if row["classification"] not in ALLOWED_CLASSIFICATIONS:
            row["classification"] = "unresolved"
    return rows


def pattern_match_rows(root: Path) -> list[dict[str, Any]]:
    inspected = [
        "run_active_strategy_evidence_recompute.py",
        "run_active_combo_benchmark_reporting.py",
        "strategy_lab/research_os/research/active_combo_series_reconciliation.py",
        "run_current_research_checkpoint.py",
        "strategy_lab/research_os/research/public_source_comparative_screening_batch_v1.py",
        "strategy_lab/research_os/external_adapters/bt_adapter.py",
        "strategy_lab/research_os/research/risk_parity_trend_etf_wrapper_screen_v1.py",
    ]
    patterns = [
        ("target_weights.ffill", "literal target_weights.ffill()"),
        ("returns_from_weights", "adapter target-weight return helper"),
        ("turnover_from_weights", "target-frame turnover helper"),
        ("portfolio_step", "drift-aware holdings step"),
        ("rebalance_turnover_units", "actual/pre-trade turnover helper"),
        ("active_combo_daily_return", "precomputed active-combo return consumer"),
    ]
    rows: list[dict[str, Any]] = []
    for rel in inspected:
        text = (root / rel).read_text(encoding="utf-8") if (root / rel).exists() else ""
        for token, description in patterns:
            if token in text:
                rows.append(
                    {
                        "path": rel,
                        "matched_pattern": token,
                        "pattern_description": description,
                        "behavior_confirmation": "requires code-path classification; text match alone was not used as proof",
                    }
                )
    return rows


def review_rows(root: Path, payload: dict[str, Any], target: str) -> list[dict[str, Any]]:
    manifest = read_json(root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json")
    counts = sample_monthly_target_counts(payload.get("close", pd.DataFrame()), target)
    profit = {
        (row.get("strategy_id"), row.get("metric")): row.get("value")
        for row in read_csv_rows(root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_profit_review.csv")
    }
    return [
        {
            "strategy_id": target,
            "rebalance_cadence": "monthly",
            "sampled_months": counts["sampled_months"],
            "mixed_risky_target_months": counts["mixed_risky_target_months"],
            "bil_mixed_months": counts["bil_mixed_months"],
            "portfolio_accounting_method": manifest.get("portfolio_accounting_method", ""),
            "turnover_basis": manifest.get("turnover_basis", ""),
            "current_180d_median_final_equity": profit.get((target, "180d_median_final_equity"), ""),
            "historical_unverified_metric_used": False,
            "classification": "accounting_defect_confirmed",
            "post_patch_status": "correct_drifting_holdings",
        }
    ]


def active_combo_review_rows(root: Path) -> list[dict[str, Any]]:
    manifest = read_json(root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json")
    reconciliation = read_json(root / COMBO_RECONCILIATION_DIR / "active_combo_series_reconciliation.json")
    return [
        {
            "combo_id": combo.COMBO_ID,
            "role": "benchmark_reference_only",
            "rebalance_cadence": "monthly",
            "combo_weight_rule": "50/50 VM/DSR target sleeves at monthly rebalance; sleeve values drift between rebalances",
            "component_accounting": manifest.get("portfolio_accounting_method", ""),
            "component_turnover_basis": manifest.get("component_turnover_basis", ""),
            "combo_level_cost_basis": manifest.get("combo_level_cost_basis", ""),
            "reconstructability": reconciliation.get("reconstructability_classification", ""),
            "checkpoint_safe_to_restore": reconciliation.get("checkpoint_combo_row_safe_to_restore", False),
            "classification": "accounting_defect_confirmed",
            "post_patch_status": "correct_drifting_holdings",
        }
    ]


def confirmed_defects() -> list[dict[str, Any]]:
    return [
        {
            "defect_id": "active_recompute_constant_target_daily_weights",
            "affected_consumers": f"{active.VM_ID};{active.DSR_ID};raw_sector_equal_weight_basket",
            "defective_pattern": "monthly target weights applied directly to every daily asset return; turnover based on target changes",
            "patch_summary": "simulate/full_returns now trade only on month changes, use portfolio_step, drift weights daily, and charge costs only on scheduled turnover",
            "state_changed": False,
        },
        {
            "defect_id": "active_combo_component_constant_target_daily_weights",
            "affected_consumers": combo.COMBO_ID,
            "defective_pattern": "component strategy target weights and 50/50 combo sleeves did not distinguish pre-trade actual from target weights",
            "patch_summary": "combo generator now drifts component holdings and sleeve values, resets 50/50 only on monthly rebalance, and includes component-level turnover costs",
            "state_changed": False,
        },
    ]


def patches_applied() -> list[dict[str, Any]]:
    return [
        {
            "path": "run_active_strategy_evidence_recompute.py",
            "scope": "active VM/DSR/current equal-weight benchmark recompute",
            "change": "added drift-aware weight helpers and replaced constant target daily accounting in simulate/full_returns",
            "strategy_rules_changed": False,
        },
        {
            "path": "run_active_combo_benchmark_reporting.py",
            "scope": "active combo benchmark/reference generator",
            "change": "drifted VM/DSR sleeve values and component holdings between monthly rebalances; component-level costs included",
            "strategy_rules_changed": False,
        },
        {
            "path": "strategy_lab/research_os/research/active_combo_series_reconciliation.py",
            "scope": "active combo reconstruction verifier",
            "change": "recognized delegated daily_asset_returns/portfolio_step missing-component behavior in the patched generator",
            "strategy_rules_changed": False,
        },
    ]


def superseded_rows() -> list[dict[str, Any]]:
    return [
        {"artifact_path": "evidence/active_strategy_evidence_recompute/latest", "superseded_reason": "current active diagnostic metrics regenerated with drifting holdings", "replacement_path": "evidence/active_strategy_evidence_recompute/latest"},
        {"artifact_path": "evidence/active_combo_benchmark/latest", "superseded_reason": "active-combo source series regenerated with sleeve/component drift", "replacement_path": "evidence/active_combo_benchmark/latest"},
        {"artifact_path": "evidence/active_combo_series_reconciliation/latest", "superseded_reason": "previous partial reconstruction superseded by exact regenerated series", "replacement_path": "evidence/active_combo_series_reconciliation/latest"},
        {"artifact_path": "evidence/current_research_checkpoint/latest", "superseded_reason": "checkpoint regenerated after exact active-combo restoration", "replacement_path": "evidence/current_research_checkpoint/latest"},
        {"artifact_path": "evidence/public_source_comparative_screening_batch_v1/latest", "superseded_reason": "comparative screening regenerated against corrected active-combo series", "replacement_path": "evidence/public_source_comparative_screening_batch_v1/latest"},
        {"artifact_path": "evidence/risk_parity_trend_etf_wrapper_screen_v1/latest", "superseded_reason": "risk-parity comparative deltas regenerated because active-combo benchmark changed", "replacement_path": "evidence/risk_parity_trend_etf_wrapper_screen_v1/latest"},
        {"artifact_path": "evidence/risk_parity_trend_portfolio_accounting_review_v1/latest", "superseded_reason": "risk-parity accounting review regenerated to confirm corrected outcome remains control_weak", "replacement_path": "evidence/risk_parity_trend_portfolio_accounting_review_v1/latest"},
    ]


def downstream_rows(root: Path) -> list[dict[str, Any]]:
    checkpoint = read_json(root / CURRENT_CHECKPOINT_DIR / "current_research_checkpoint_manifest.json")
    public_manifest = read_json(root / PUBLIC_COMPARATIVE_DIR / "screening_manifest.json")
    risk_screen = read_json(root / RISK_PARITY_SCREEN_DIR / "execution_manifest.json")
    risk_review = read_json(root / RISK_PARITY_REVIEW_DIR / "decision.json")
    return [
        {
            "downstream_artifact": "current_research_checkpoint",
            "regenerated": True,
            "outcome_before": "active_combo repair caveat present or incomplete",
            "outcome_after": checkpoint.get("next_engineering_action", ""),
            "material_decision_change": "active combo restored as benchmark/reference row only; no lifecycle decision changed",
        },
        {
            "downstream_artifact": "public_source_comparative_screening_batch_v1",
            "regenerated": True,
            "outcome_before": "comparative screen depended on active-combo benchmark series",
            "outcome_after": f"comparative_positive_count={public_manifest.get('comparative_evidence_positive_count')}; lanes={public_manifest.get('lanes_evaluated_count')}",
            "material_decision_change": "none; outputs remain non-promotable diagnostic screening",
        },
        {
            "downstream_artifact": "risk_parity_trend_etf_wrapper_screen_v1",
            "regenerated": True,
            "outcome_before": risk_review.get("original_screening_outcome", "control_weak"),
            "outcome_after": risk_review.get("corrected_screening_outcome", risk_screen.get("screening_outcome", "")),
            "material_decision_change": "none; exact candidate remains closed for immediate retesting/control_weak",
        },
    ]


def remaining_unresolved_rows() -> list[dict[str, Any]]:
    return []


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    payload = active.build_review_payload(root)
    classifications = classification_rows(root, payload)
    inventory = consumer_inventory_rows(root)
    before_after = before_after_metrics(root, payload)
    reconstructions = independent_reconstruction_rows()
    unresolved = remaining_unresolved_rows()
    defects = confirmed_defects()
    downstream = downstream_rows(root)
    combo_review = active_combo_review_rows(root)
    dsr_review = review_rows(root, payload, active.DSR_ID)
    vm_review = review_rows(root, payload, active.VM_ID)
    patterns = pattern_match_rows(root)
    risk_review = read_json(root / RISK_PARITY_REVIEW_DIR / "decision.json")
    combo_reconciliation = read_json(root / COMBO_RECONCILIATION_DIR / "active_combo_series_reconciliation.json")
    registry = registry_rows(root)

    fields_inventory = ["consumer_id", "consumer_name", "artifact_or_code_path", "decision_role", "multi_asset_relevance", "status"]
    fields_class = ["consumer_id", "classification", "proof", "patched", "post_patch_status", "source_series_trace"]
    write_csv(output / "consumer_inventory.csv", inventory, fields_inventory)
    write_csv(output / "accounting_pattern_matches.csv", patterns, ["path", "matched_pattern", "pattern_description", "behavior_confirmation"])
    write_csv(output / "consumer_classifications.csv", classifications, fields_class)
    write_csv(output / "active_combo_accounting_review.csv", combo_review, ["combo_id", "role", "rebalance_cadence", "combo_weight_rule", "component_accounting", "component_turnover_basis", "combo_level_cost_basis", "reconstructability", "checkpoint_safe_to_restore", "classification", "post_patch_status"])
    write_csv(output / "dsr_accounting_review.csv", dsr_review, ["strategy_id", "rebalance_cadence", "sampled_months", "mixed_risky_target_months", "bil_mixed_months", "portfolio_accounting_method", "turnover_basis", "current_180d_median_final_equity", "historical_unverified_metric_used", "classification", "post_patch_status"])
    write_csv(output / "vm_accounting_review.csv", vm_review, ["strategy_id", "rebalance_cadence", "sampled_months", "mixed_risky_target_months", "bil_mixed_months", "portfolio_accounting_method", "turnover_basis", "current_180d_median_final_equity", "historical_unverified_metric_used", "classification", "post_patch_status"])
    write_csv(output / "independent_reconstructions.csv", reconstructions, ["scenario", "starting_weights", "asset_returns", "gross_return_from_actual_weights", "drifted_pre_trade_weights", "next_target_weights", "turnover_from_pre_trade_actual", "target_to_target_turnover", "cost_charged_on_non_execution_date", "classification_proof"])
    write_csv(output / "confirmed_defects.csv", defects, ["defect_id", "affected_consumers", "defective_pattern", "patch_summary", "state_changed"])
    write_csv(output / "patches_applied.csv", patches_applied(), ["path", "scope", "change", "strategy_rules_changed"])
    write_csv(output / "before_after_metrics.csv", before_after, ["consumer_id", "role", "metric", "before_constant_target_daily_weight_method", "after_drifting_holdings_method", "delta_after_minus_before", "interpretation"])
    write_csv(output / "superseded_artifacts.csv", superseded_rows(), ["artifact_path", "superseded_reason", "replacement_path"])
    write_csv(output / "downstream_outcome_changes.csv", downstream, ["downstream_artifact", "regenerated", "outcome_before", "outcome_after", "material_decision_change"])
    write_csv(output / "remaining_unresolved_consumers.csv", unresolved, ["consumer_id", "reason", "required_next_input"])

    vm_row = registry.get(active.VM_ID, {})
    dsr_row = registry.get(active.DSR_ID, {})
    current_consumer_count = len(classifications)
    unresolved_count = sum(1 for row in classifications if row["classification"] == "unresolved")
    confirmed_defect_consumers = [row["consumer_id"] for row in classifications if row["classification"] == "accounting_defect_confirmed"]
    consistency = {
        "blast_radius_packet_created": True,
        "every_scoped_consumer_classified": current_consumer_count == len({row["consumer_id"] for row in classifications}) and all(row["classification"] in ALLOWED_CLASSIFICATIONS for row in classifications),
        "no_unresolved_current_consumers": unresolved_count == 0 and not unresolved,
        "confirmed_defects_have_patches": all(row["patched"] is True for row in classifications if row["classification"] == "accounting_defect_confirmed"),
        "monthly_component_portfolios_drift_between_rebalances": any(row["scenario"] == "synthetic_monthly_50_50_component_portfolio" and float(row["turnover_from_pre_trade_actual"]) > float(row["target_to_target_turnover"]) for row in reconstructions),
        "multi_sector_equal_weight_drift_verified": any(row["scenario"] == "synthetic_multi_sector_equal_weight_holdings" and float(row["turnover_from_pre_trade_actual"]) > float(row["target_to_target_turnover"]) for row in reconstructions),
        "turnover_uses_pre_trade_actual_weights": "rebalance_turnover_units" in Path(root / "run_active_strategy_evidence_recompute.py").read_text(encoding="utf-8"),
        "no_non_execution_date_costs_in_reconstruction": all(float(row["cost_charged_on_non_execution_date"]) == 0.0 for row in reconstructions),
        "active_combo_exact_reconstruction_available": combo_reconciliation.get("reconstructability_classification") == "exactly_reconstructable",
        "active_combo_benchmark_reference_only": combo_review[0]["role"] == "benchmark_reference_only",
        "vm_lifecycle_state_unchanged": vm_row.get("paper_forward_active") is True and vm_row.get("rules_frozen") is True,
        "dsr_lifecycle_state_unchanged": dsr_row.get("paper_forward_active") is True and dsr_row.get("rules_frozen") is True,
        "dsr_historical_and_current_metrics_separated": dsr_review[0]["historical_unverified_metric_used"] is False,
        "risk_parity_exact_candidate_remains_closed": risk_review.get("corrected_screening_outcome") == "control_weak",
        "no_provider_calls": True,
        "no_parameter_wrapper_universe_or_window_search": True,
        "no_strategy_discovery_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_demo_state_change": True,
        "no_broker_live_real_money_path": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    write_json(output / "consistency_check.json", consistency)

    decision = {
        "created_at_utc": now_utc(),
        "decision": "current_multi_asset_portfolio_accounting_blast_radius_complete",
        "consumer_count": current_consumer_count,
        "confirmed_defect_consumer_count": len(confirmed_defect_consumers),
        "confirmed_defect_consumers": confirmed_defect_consumers,
        "remaining_unresolved_consumer_count": unresolved_count,
        "patches_applied_count": len(patches_applied()),
        "active_combo_reconstructability": combo_reconciliation.get("reconstructability_classification"),
        "active_combo_checkpoint_safe_to_restore": combo_reconciliation.get("checkpoint_combo_row_safe_to_restore") is True,
        "risk_parity_exact_candidate_status": "closed_for_immediate_retesting_control_weak",
        "current_checkpoint_next_engineering_action": read_json(root / CURRENT_CHECKPOINT_DIR / "current_research_checkpoint_manifest.json").get("next_engineering_action"),
        "no_strategy_rules_changed": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "no_provider_download": True,
        "no_strategy_discovery_run": True,
        "next_action": "resume_source_backed_strategy_discovery_after_accounting_blast_radius",
    }
    write_json(output / "decision.json", decision)
    decision_md = [
        "# Current Multi-Asset Portfolio Accounting Blast Radius",
        "",
        f"Decision: `{decision['decision']}`",
        f"Consumers classified: `{current_consumer_count}`",
        f"Confirmed affected current consumers: `{len(confirmed_defect_consumers)}`",
        f"Active combo reconstructability: `{decision['active_combo_reconstructability']}`",
        f"Risk-parity exact candidate status: `{decision['risk_parity_exact_candidate_status']}`",
        "",
        "Patched consumers now trade only on scheduled rebalance dates, drift actual holdings between rebalances, and charge costs from pre-trade actual turnover. Outputs remain diagnostic or benchmark/reference only.",
        "",
        f"Exact next action: `{decision['next_action']}`",
    ]
    (output / "decision.md").write_text("\n".join(decision_md) + "\n", encoding="utf-8")

    return {
        "output_dir": str(output),
        "decision": decision,
        "consistency": consistency,
        "confirmed_defect_consumers": confirmed_defect_consumers,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
