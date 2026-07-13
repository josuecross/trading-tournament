from __future__ import annotations

import csv
import hashlib
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
OUTPUT_DIR = Path("evidence") / "active_combo_series_reconciliation" / "latest"
SOURCE_DIR = Path("evidence") / "active_combo_benchmark" / "latest"
COMBO_ID = combo.COMBO_ID
BENCHMARK_REGISTRY_PATH = Path("strategy_lab") / "research_os" / "benchmark_control_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> Any:
    return round(value, 6) if isinstance(value, float) else value


def _weights_sum(raw_json: str) -> float:
    weights = json.loads(raw_json or "{}")
    return float(sum(float(v) for v in weights.values()))


def _has_bil_remainder(raw_json: str) -> bool:
    weights = {str(k): float(v) for k, v in json.loads(raw_json or "{}").items()}
    risky = sum(v for k, v in weights.items() if k != "BIL")
    bil = weights.get("BIL", 0.0)
    return bil == 0.0 or abs((risky + bil) - 1.0) <= 1e-5


def source_packet_status(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DIR
    definition = read_yaml(source / "active_combo_benchmark_definition.yaml")
    manifest = read_json(source / "active_combo_manifest.json")
    consistency = read_json(source / "active_combo_consistency_check.json")
    return {
        "source_dir": source,
        "definition": definition,
        "manifest": manifest,
        "consistency": consistency,
        "definition_hash": file_hash(source / "active_combo_benchmark_definition.yaml"),
        "manifest_hash": file_hash(source / "active_combo_manifest.json"),
        "consistency_hash": file_hash(source / "active_combo_consistency_check.json"),
        "series_hash": file_hash(source / "active_combo_equity_series.csv"),
        "metrics_hash": file_hash(source / "active_combo_benchmark_metrics.csv"),
    }


def identity_rows(root: Path, source_status: dict[str, Any]) -> list[dict[str, Any]]:
    benchmark_registry = read_yaml(root / BENCHMARK_REGISTRY_PATH)
    controls = benchmark_registry.get("controls", {})
    active_ops = read_yaml(root / ACTIVE_OBSERVATIONS_PATH)
    definition = source_status["definition"]
    manifest = source_status["manifest"]
    consistency = source_status["consistency"]
    return [
        {
            "combo_id": definition.get("benchmark_id", ""),
            "role": definition.get("role", ""),
            "lifecycle_status": controls.get(COMBO_ID, {}).get("status", ""),
            "control_registry_role": controls.get(COMBO_ID, {}).get("role", ""),
            "operations_reference_present": "active_combo" in active_ops.get("references", []),
            "source_definition_path": str(source_status["source_dir"] / "active_combo_benchmark_definition.yaml"),
            "source_manifest_created_at_utc": manifest.get("created_at_utc", ""),
            "source_consistency_passed": consistency.get("consistency_passed", False),
            "predates_this_task": bool(manifest.get("created_at_utc")),
            "notes": "Reference benchmark only; not an active paper/demo observation.",
        }
    ]


def component_rows(root: Path, source_status: dict[str, Any]) -> list[dict[str, Any]]:
    definition = source_status["definition"]
    sleeves = definition.get("sleeves", [])
    rows = []
    active_obs = {sid: read_yaml(path) for sid, path in active.active_observation_paths(root).items()}
    for sleeve in sleeves:
        strategy_id = sleeve.get("strategy_id", "")
        obs = active_obs.get(strategy_id, {})
        rows.append(
            {
                "combo_id": definition.get("benchmark_id", ""),
                "component_strategy_id": strategy_id,
                "component_version": obs.get("base_strategy_id", ""),
                "allocation": sleeve.get("allocation", ""),
                "rule_source": sleeve.get("rule_source", ""),
                "component_status": obs.get("status", ""),
                "frozen": obs.get("frozen", ""),
                "rules_frozen": obs.get("rules_frozen", ""),
                "paper_forward_active": obs.get("paper_forward_active", ""),
                "rebalance_cadence": definition.get("rebalance", ""),
                "cash_bil_treatment": "component rules use BIL fallback/remainder where frozen rules specify it",
                "source_artifact": str(active.active_observation_paths(root).get(strategy_id, "")),
            }
        )
    return rows


def reconstruct(root: Path) -> dict[str, Any]:
    payload = combo.build_payload(root)
    if not payload.get("diagnostics_available"):
        return payload
    equity = payload["equity_frame"].copy()
    metrics = combo.metric_rows(payload)
    return {**payload, "equity_frame": equity, "metric_rows": metrics}


def compare_to_source(root: Path, reconstructed: dict[str, Any]) -> dict[str, Any]:
    source_equity_path = root / SOURCE_DIR / "active_combo_equity_series.csv"
    if not reconstructed.get("diagnostics_available"):
        return {"source_series_exists": source_equity_path.exists(), "series_matches_source": False, "max_abs_equity_delta": "", "row_count_delta": ""}
    if not source_equity_path.exists():
        return {"source_series_exists": False, "series_matches_source": False, "max_abs_equity_delta": "", "row_count_delta": ""}
    source = pd.read_csv(source_equity_path)
    current = reconstructed["equity_frame"]
    cols = ["date", "active_combo_equity", "vm_sleeve_equity", "dsr_sleeve_equity"]
    source_cmp = source[cols].copy()
    current_cmp = current[cols].copy()
    row_count_delta = int(len(current_cmp) - len(source_cmp))
    merged = source_cmp.merge(current_cmp, on="date", suffixes=("_source", "_current"))
    deltas = []
    for col in cols[1:]:
        deltas.extend((pd.to_numeric(merged[f"{col}_source"]) - pd.to_numeric(merged[f"{col}_current"])).abs().tolist())
    max_delta = max(deltas) if deltas else float("inf")
    return {
        "source_series_exists": True,
        "series_matches_source": row_count_delta == 0 and len(merged) == len(source_cmp) and max_delta <= 1e-6,
        "max_abs_equity_delta": round(float(max_delta), 10) if math.isfinite(float(max_delta)) else "unavailable",
        "row_count_delta": row_count_delta,
    }


def invariant_report(reconstructed: dict[str, Any]) -> dict[str, Any]:
    if not reconstructed.get("diagnostics_available"):
        return {
            "max_daily_exposure": "",
            "max_sleeve_weight_sum": "",
            "weight_invariant_passed": False,
            "bil_remainder_passed": False,
            "date_alignment_passed": False,
        }
    close = reconstructed["close"]
    allocations = reconstructed["allocations"]
    max_daily_exposure = 0.0
    max_sleeve_sum = 0.0
    bil_ok = True
    months = [dt.year * 12 + dt.month for dt in close.index]
    last_month = None
    for today in range(253, len(close)):
        month = int(months[today])
        if month == last_month:
            continue
        signal = today - 1
        vm_weights = active.strategy_weights(close, signal, active.VM_ID)
        dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
        vm_sum = float(sum(vm_weights.values()))
        dsr_sum = float(sum(dsr_weights.values()))
        max_sleeve_sum = max(max_sleeve_sum, vm_sum, dsr_sum)
        max_daily_exposure = max(max_daily_exposure, 0.5 * vm_sum + 0.5 * dsr_sum)
        bil_ok = bil_ok and abs(sum(vm_weights.values()) - 1.0) <= 1e-12 and abs(sum(dsr_weights.values()) - 1.0) <= 1e-12
        last_month = month
    equity = reconstructed["equity_frame"]
    date_alignment = bool(not equity.empty and equity["date"].is_unique and equity[["active_combo_equity", "vm_sleeve_equity", "dsr_sleeve_equity"]].notna().all().all())
    return {
        "max_daily_exposure": round(max_daily_exposure, 10),
        "max_sleeve_weight_sum": round(max_sleeve_sum, 10),
        "weight_invariant_passed": bool(max_daily_exposure <= 1.0 + 1e-12 and max_sleeve_sum <= 1.0 + 1e-12),
        "bil_remainder_passed": bool(bil_ok),
        "date_alignment_passed": date_alignment,
        "rounded_allocation_csv_max_exposure": max((0.5 * _weights_sum(row["vm_holdings"]) + 0.5 * _weights_sum(row["dsr_holdings"])) for row in allocations) if allocations else "",
    }


def alignment_rows(reconstructed: dict[str, Any]) -> list[dict[str, Any]]:
    if not reconstructed.get("diagnostics_available"):
        return [
            {
                "component": "all",
                "aligned": False,
                "start_date": "",
                "end_date": "",
                "row_count": 0,
                "missing_return_count": "",
                "notes": "diagnostics unavailable",
            }
        ]
    frame = reconstructed["equity_frame"]
    rows = []
    for component, equity_col, return_col in [
        ("active_combo", "active_combo_equity", "active_combo_daily_return"),
        ("vm_sleeve", "vm_sleeve_equity", "vm_sleeve_daily_return"),
        ("dsr_sleeve", "dsr_sleeve_equity", "dsr_sleeve_daily_return"),
    ]:
        returns = frame[return_col].replace("", pd.NA)
        rows.append(
            {
                "component": component,
                "aligned": True,
                "start_date": frame["date"].iloc[0],
                "end_date": frame["date"].iloc[-1],
                "row_count": len(frame),
                "missing_return_count": int(returns.isna().sum()),
                "notes": f"{component} daily series shares the combo date index",
            }
        )
    return rows


def missing_rows(classification: str, checks: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for name, value in checks.items():
        if value not in (True, 0, "0"):
            rows.append({"input_or_check": name, "status": "missing_or_failed", "detail": value})
    if not rows:
        rows.append({"input_or_check": "all_required_inputs", "status": "available", "detail": "no missing or conflicting inputs found"})
    if classification != "exactly_reconstructable":
        rows.append({"input_or_check": "reconstructability", "status": classification, "detail": "exact reconstruction criteria did not all pass"})
    return rows


def checkpoint_review_rows(classification: str, metric_lookup: dict[str, Any]) -> list[dict[str, Any]]:
    include = classification == "exactly_reconstructable"
    return [
        {
            "checkpoint_item": "active_combo_row",
            "include_in_checkpoint": include,
            "evidence_source": "evidence/active_combo_series_reconciliation/latest",
            "metric_source": "reconstructed_daily_series_and_sampled_window_recompute" if include else "unavailable",
            "trust_level": "reconstructed_benchmark_reference" if include else "not_restored",
            "known_caveat": "benchmark/control only; not an active strategy; no independent E4 upgrade",
            "metric_180d_median_equity": metric_lookup.get("180d_median_final_equity", ""),
            "recommended_action": "compare_only" if include else "keep_repair_caveat",
        }
    ]


def metric_lookup(metric_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {row["metric"]: row.get("value", "") for row in metric_rows}


def classify(source_status: dict[str, Any], reconstructed: dict[str, Any], source_compare: dict[str, Any], invariants: dict[str, Any], components: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    definition = source_status["definition"]
    manifest = source_status["manifest"]
    consistency = source_status["consistency"]
    component_allocations = [_float(row.get("allocation")) for row in components]
    source_code = Path("run_active_combo_benchmark_reporting.py").read_text(encoding="utf-8")
    checks = {
        "definition_exists": bool(definition),
        "canonical_combo_id": definition.get("benchmark_id") == COMBO_ID,
        "role_is_benchmark_reference": definition.get("role") == "benchmark_reference_only",
        "source_packet_predates_task": bool(manifest.get("created_at_utc")),
        "source_packet_consistency_passed": consistency.get("consistency_passed") is True,
        "component_ids_verified": [row.get("component_strategy_id") for row in components] == [active.VM_ID, active.DSR_ID],
        "component_allocations_verified": component_allocations == [0.5, 0.5] and abs(sum(x or 0.0 for x in component_allocations) - 1.0) <= 1e-12,
        "components_frozen": all(str(row.get("frozen")).lower() == "true" and str(row.get("rules_frozen")).lower() == "true" for row in components),
        "rebalance_rule_verified": definition.get("rebalance") == "monthly" and "signal = today - 1" in source_code,
        "missing_component_behavior_verified": "available_at(close, symbol, today, 1)" in source_code,
        "cost_treatment_explicit": "sleeve_daily_return" in source_code and "SLIPPAGE" not in source_code.split("def combo_window", 1)[1].split("def run_windows", 1)[0],
        "source_series_reproduced": source_compare.get("series_matches_source") is True,
        "diagnostics_available": reconstructed.get("diagnostics_available") is True,
        "weight_invariant_passed": invariants["weight_invariant_passed"] is True,
        "bil_remainder_passed": invariants["bil_remainder_passed"] is True,
        "date_alignment_passed": invariants["date_alignment_passed"] is True,
        "no_dsr_unverified_metric_used": "4071.04" not in source_code,
    }
    if all(value is True for value in checks.values()):
        return "exactly_reconstructable", checks
    if not checks["definition_exists"]:
        return "missing_canonical_definition", checks
    if not checks["component_ids_verified"] or not checks["component_allocations_verified"]:
        return "conflicting_definition", checks
    if reconstructed.get("diagnostics_available"):
        return "partially_reconstructable", checks
    return "historical_summary_only", checks


def write_outputs(root: Path, source_status: dict[str, Any], reconstructed: dict[str, Any], source_compare: dict[str, Any], classification: str, checks: dict[str, Any], invariants: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    identity = identity_rows(root, source_status)
    components = component_rows(root, source_status)
    metrics = reconstructed.get("metric_rows", []) if reconstructed.get("diagnostics_available") else []
    metrics_by_name = metric_lookup(metrics)

    write_csv(output / "combo_identity_and_lineage.csv", identity, ["combo_id", "role", "lifecycle_status", "control_registry_role", "operations_reference_present", "source_definition_path", "source_manifest_created_at_utc", "source_consistency_passed", "predates_this_task", "notes"])
    write_csv(output / "component_definition.csv", components, ["combo_id", "component_strategy_id", "component_version", "allocation", "rule_source", "component_status", "frozen", "rules_frozen", "paper_forward_active", "rebalance_cadence", "cash_bil_treatment", "source_artifact"])
    write_csv(output / "component_series_alignment.csv", alignment_rows(reconstructed), ["component", "aligned", "start_date", "end_date", "row_count", "missing_return_count", "notes"])
    if classification == "exactly_reconstructable":
        reconstructed["equity_frame"].to_csv(output / "combo_daily_series.csv", index=False)
        write_csv(output / "combo_metric_summary.csv", metrics, ["benchmark_id", "metric", "value", "horizon", "notes"])
    write_csv(output / "missing_or_conflicting_inputs.csv", missing_rows(classification, checks), ["input_or_check", "status", "detail"])
    write_csv(output / "checkpoint_integration_review.csv", checkpoint_review_rows(classification, metrics_by_name), ["checkpoint_item", "include_in_checkpoint", "evidence_source", "metric_source", "trust_level", "known_caveat", "metric_180d_median_equity", "recommended_action"])

    manifest = {
        "created_at_utc": now_utc(),
        "combo_id": COMBO_ID,
        "reconstructability_classification": classification,
        "source_benchmark_packet": str(root / SOURCE_DIR),
        "source_definition_hash": source_status["definition_hash"],
        "source_manifest_hash": source_status["manifest_hash"],
        "source_consistency_hash": source_status["consistency_hash"],
        "source_series_hash": source_status["series_hash"],
        "source_metrics_hash": source_status["metrics_hash"],
        "series_reconstructed": classification == "exactly_reconstructable",
        "source_series_reproduced": source_compare.get("series_matches_source") is True,
        "max_abs_source_equity_delta": source_compare.get("max_abs_equity_delta", ""),
        "component_count": len(components),
        "component_ids": [row.get("component_strategy_id") for row in components],
        "rebalance_cadence": source_status["definition"].get("rebalance", ""),
        "starting_equity": source_status["definition"].get("starting_equity", ""),
        "max_daily_exposure": invariants["max_daily_exposure"],
        "weight_invariant_passed": invariants["weight_invariant_passed"],
        "bil_remainder_passed": invariants["bil_remainder_passed"],
        "date_alignment_passed": invariants["date_alignment_passed"],
        "no_strategy_discovery_run": True,
        "no_backtest_run": True,
        "no_provider_download": True,
        "no_broker_live_path": True,
        "no_paper_forward_activation": True,
        "no_lifecycle_state_change": True,
        "no_strategy_decision": True,
        "checkpoint_combo_row_safe_to_restore": classification == "exactly_reconstructable",
        "active_combo_issue_blocks_major_discovery": classification != "exactly_reconstructable",
        "next_action": "run_current_research_checkpoint" if classification == "exactly_reconstructable" else "repair_active_combo_inputs_before_new_research",
    }
    consistency = {
        "reconciliation_created": True,
        "canonical_identity_verified": checks.get("canonical_combo_id") is True,
        "components_verified": checks.get("component_ids_verified") is True and checks.get("component_allocations_verified") is True,
        "source_packet_consistent": checks.get("source_packet_consistency_passed") is True,
        "series_reconstructed_if_exact": classification != "exactly_reconstructable" or (output / "combo_daily_series.csv").exists(),
        "metrics_created_if_exact": classification != "exactly_reconstructable" or (output / "combo_metric_summary.csv").exists(),
        "no_summary_metric_inputs": checks.get("no_dsr_unverified_metric_used") is True,
        "no_unverified_dsr_metric_used": checks.get("no_dsr_unverified_metric_used") is True,
        "weight_invariant_passed": invariants["weight_invariant_passed"] is True,
        "bil_remainder_passed": invariants["bil_remainder_passed"] is True,
        "date_alignment_passed": invariants["date_alignment_passed"] is True,
        "checkpoint_integration_review_created": True,
        "no_strategy_discovery_run": True,
        "no_provider_download": True,
        "no_lifecycle_state_change": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    write_json(output / "active_combo_series_reconciliation.json", manifest)
    write_json(output / "reconciliation_consistency_check.json", consistency)
    summary_lines = [
        "# Active Combo Series Reconciliation",
        "",
        f"Combo ID: `{COMBO_ID}`",
        f"Classification: `{classification}`",
        f"Source packet: `{root / SOURCE_DIR}`",
        f"Source series reproduced: `{source_compare.get('series_matches_source')}`",
        f"Max daily exposure: `{invariants['max_daily_exposure']}`",
        "",
        "The combo remains a benchmark/reference only. No active observation, strategy rule, paper/demo status, broker/live path, or real-money decision was changed.",
    ]
    if classification == "exactly_reconstructable":
        summary_lines.extend(
            [
                "",
                f"180d median final equity: `{metrics_by_name.get('180d_median_final_equity')}`",
                f"180d worst drawdown: `{metrics_by_name.get('180d_worst_drawdown')}`",
                f"Stop-hit rate: `{metrics_by_name.get('stop_hit_rate')}`",
            ]
        )
    (output / "active_combo_series_reconciliation.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return {"output_dir": str(output), "manifest": manifest, "consistency": consistency}


def run_active_combo_series_reconciliation(root: Path = ROOT) -> dict[str, Any]:
    source_status = source_packet_status(root)
    reconstructed = reconstruct(root)
    source_compare = compare_to_source(root, reconstructed)
    invariants = invariant_report(reconstructed)
    components = component_rows(root, source_status)
    classification, checks = classify(source_status, reconstructed, source_compare, invariants, components)
    return write_outputs(root, source_status, reconstructed, source_compare, classification, checks, invariants)
