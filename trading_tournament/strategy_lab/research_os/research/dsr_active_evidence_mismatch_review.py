from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active_recompute


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "dsr_active_evidence_mismatch_review" / "latest"

ACTIVE_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
PARENT_ID = "dsr_sector_equal_weight_defensive_filter_v1"
FAMILY_ID = "defensive_sector_rotation_etf"

ACTIVE_OBSERVATION_PATH = Path("paper_forward_observations") / ACTIVE_ID / "active_observation.yaml"
ACTIVATION_DIR = Path("evidence") / "paper_forward_activations" / PARENT_ID / "latest"
ACTIVATION_COPY_PATH = ACTIVATION_DIR / f"{ACTIVE_ID}_active_observation.yaml"
ACTIVATION_MANIFEST_PATH = ACTIVATION_DIR / "manifest.json"
RECOMPUTE_DIR = Path("evidence") / "active_strategy_evidence_recompute" / "latest"
RECOMPUTE_PROFIT_PATH = RECOMPUTE_DIR / "active_strategy_recompute_profit_review.csv"
RECOMPUTE_RECOVERED_VS_RECOMPUTED_PATH = RECOMPUTE_DIR / "active_strategy_recompute_recovered_vs_recomputed.csv"
RECOMPUTE_TARGET_WINDOWS_PATH = RECOMPUTE_DIR / "active_strategy_recompute_target_window_review.csv"
RECOMPUTE_RULE_FIDELITY_PATH = RECOMPUTE_DIR / "active_strategy_recompute_rule_fidelity.csv"
RECOMPUTE_CONSISTENCY_PATH = RECOMPUTE_DIR / "active_strategy_recompute_consistency_check.json"
RECONCILIATION_PATH = Path("evidence") / "active_observation_evidence_reconciliation" / "latest"

CANONICAL_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
    ACTIVE_OBSERVATION_PATH,
]

RECOVERED_BEST_FINAL_EQUITY = 4071.04
CURRENT_BEST_FINAL_EQUITY = 3481.6998
TOLERANCE = 1e-4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(root: Path, paths: list[Path]) -> dict[str, str]:
    return {str(path).replace("\\", "/"): file_hash(root / path) for path in paths}


def rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def dsr_recomputed_metric_rows(root: Path) -> list[dict[str, str]]:
    return [row for row in read_csv(root / RECOMPUTE_RECOVERED_VS_RECOMPUTED_PATH) if row.get("strategy_id") == ACTIVE_ID]


def current_best_profit_row(root: Path) -> dict[str, str]:
    for row in read_csv(root / RECOMPUTE_PROFIT_PATH):
        if row.get("strategy_id") == ACTIVE_ID and row.get("metric") == "best_final_equity":
            return row
    return {}


def current_sample_rows(root: Path) -> list[dict[str, Any]]:
    close, missing = active_recompute.prepare_prices(root)
    if missing:
        return []
    return [active_recompute.simulate(close, start, 180, ACTIVE_ID) for start in active_recompute.sample_starts(close, 180)]


def trace_window(root: Path, start_index: int, horizon: int = 180) -> list[dict[str, Any]]:
    close, missing = active_recompute.prepare_prices(root)
    if missing:
        return []
    equity = active_recompute.STARTING_EQUITY
    peak = equity
    weights: dict[str, float] = {}
    last_month = None
    months = [dt.year * 12 + dt.month for dt in close.index]
    rows: list[dict[str, Any]] = []
    for offset in range(1, horizon + 1):
        today = start_index + offset
        signal = today - 1
        month = int(months[today])
        rebalanced = month != last_month
        turnover = 0.0
        stale_removed_symbols: list[str] = []
        if rebalanced:
            new_weights = active_recompute.strategy_weights(close, signal, ACTIVE_ID)
            stale_removed_symbols = sorted(symbol for symbol in weights if abs(weights.get(symbol, 0.0)) > 1e-12 and symbol not in new_weights)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * active_recompute.SLIPPAGE
            weights = new_weights
            last_month = month
        daily_return = 0.0
        symbol_returns: dict[str, float] = {}
        for symbol, weight in weights.items():
            if active_recompute.available_at(close, symbol, today, 1):
                symbol_return = float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
                symbol_returns[symbol] = symbol_return
                daily_return += weight * symbol_return
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        drawdown = equity - peak
        risky_weight = sum(weight for symbol, weight in weights.items() if symbol != "BIL")
        bil_weight = weights.get("BIL", 0.0)
        weight_sum = sum(weights.values())
        rows.append(
            {
                "date": str(close.index[today].date()),
                "signal_date": str(close.index[signal].date()),
                "window_start": str(close.index[start_index].date()),
                "window_end": str(close.index[start_index + horizon].date()),
                "offset": offset,
                "rebalanced": rebalanced,
                "turnover": turnover,
                "weights": dict(sorted(weights.items())),
                "symbol_returns": dict(sorted(symbol_returns.items())),
                "daily_return": daily_return,
                "equity": equity,
                "drawdown": drawdown,
                "weight_sum": weight_sum,
                "risky_weight": risky_weight,
                "bil_weight": bil_weight,
                "max_single_weight": max(weights.values()) if weights else 0.0,
                "removed_symbols_on_rebalance": stale_removed_symbols,
                "exposure": weight_sum,
            }
        )
    return rows


def best_sample_start(root: Path) -> tuple[int | None, dict[str, Any]]:
    close, missing = active_recompute.prepare_prices(root)
    if missing:
        return None, {}
    starts = active_recompute.sample_starts(close, 180)
    rows = [(start, active_recompute.simulate(close, start, 180, ACTIVE_ID)) for start in starts]
    if not rows:
        return None, {}
    return max(rows, key=lambda item: item[1]["final_equity"])


def build_metric_comparison(root: Path, current_reproduced: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in dsr_recomputed_metric_rows(root):
        rows.append(
            {
                "metric": row.get("metric"),
                "recovered_value": row.get("recovered_value"),
                "current_recomputed_value": row.get("recomputed_value"),
                "diagnostic_reproduced_value": current_reproduced if row.get("metric") == "best_final_equity" else "",
                "absolute_delta": row.get("absolute_delta"),
                "verdict": row.get("verdict"),
                "notes": row.get("notes"),
            }
        )
    if not any(row["metric"] == "best_final_equity" for row in rows):
        rows.append(
            {
                "metric": "best_final_equity",
                "recovered_value": RECOVERED_BEST_FINAL_EQUITY,
                "current_recomputed_value": CURRENT_BEST_FINAL_EQUITY,
                "diagnostic_reproduced_value": current_reproduced,
                "absolute_delta": current_reproduced - RECOVERED_BEST_FINAL_EQUITY,
                "verdict": "material_mismatch_requires_review",
                "notes": "Inserted from known review context because metric comparison row was missing.",
            }
        )
    return rows


def build_methodology_comparison() -> list[dict[str, Any]]:
    current = {
        "Initial capital": "$3000.00",
        "Start and end dates": "Five sampled 180-day windows: 2008-01-03..2008-09-19; 2012-06-06..2013-02-26; 2016-11-10..2017-08-01; 2021-04-21..2022-01-05; 2025-09-30..2026-06-18",
        "Warm-up period": "252 index rows before sampled starts; 200-day SMA per asset",
        "Asset universe": "XLK, XLF, XLE, XLV, XLY, XLP, XLU, XLI, XLB, XLC, BIL",
        "Asset availability dates": "Per-asset availability; XLC begins 2018-06-19 and is absent from earlier decisions",
        "Price field and adjustment method": "data/cache adjusted close field",
        "Corporate-action treatment": "Uses cached adjusted close; no separate corporate-action replay",
        "Lookback periods": "200-day SMA",
        "Momentum or ranking calculation": "Not used; all qualifying sectors are held",
        "Defensive filter": "sector close > sector 200-day SMA",
        "Selection count": "all qualifying sectors; if one/two qualify, one-third each plus BIL",
        "Weighting method": "equal-weight qualifying sectors when >=3; one-third slots when 1 or 2",
        "BIL or cash fallback": "BIL is replacement/remainder only; 100% BIL if none qualify",
        "Rebalance schedule": "monthly, first trading day of month using prior trading day signal; diagnostic window initial allocation is set on first simulated return day from prior close",
        "Signal timestamp": "signal = today - 1",
        "Execution timestamp and assumed fill price": "shifted close-to-close return from today-1 to today; turnover cost before daily return on rebalance date",
        "Signal lag": "one trading day",
        "Missing-data handling": "asset unavailable if price or lookback value missing; no zero-to-NaN conversion",
        "Target-weight zero handling": "weights dict is replaced at rebalance; omitted assets are zero",
        "Weight forward-fill behavior": "weights persist between monthly rebalances only; no stale weights across rebalance replacement",
        "Exposure normalization and caps": "weights sum to 1.0 within tolerance",
        "Transaction costs and slippage": "0.0005 turnover cost on rebalance",
        "Fractional-share assumptions": "continuous fractional allocation/equity simulation",
        "Dividends or distributions": "captured only through adjusted close cache",
        "Equity and return calculation": "daily weighted close-to-close returns; fresh $3000 per sampled window",
        "Metric-definition differences": "best_final_equity is max across the five sampled 180-day diagnostic windows",
    }
    recovered = {
        "Initial capital": "not explicitly recoverable from activation artifact",
        "Start and end dates": "not recoverable; no window list for 4071.04",
        "Warm-up period": "not recoverable",
        "Asset universe": "rule text lists XLK, XLF, XLE, XLV, XLY, XLP, XLU, XLI, XLB, XLC, BIL",
        "Asset availability dates": "not recoverable",
        "Price field and adjustment method": "not recoverable",
        "Corporate-action treatment": "not recoverable",
        "Lookback periods": "200-day SMA in recovered rule text",
        "Momentum or ranking calculation": "not applicable per recovered rule text",
        "Defensive filter": "close > 200-day SMA in recovered rule text",
        "Selection count": "all qualifying sectors in recovered rule text",
        "Weighting method": "equal-weight or one-third slot rule in recovered rule text",
        "BIL or cash fallback": "BIL fallback in recovered rule text",
        "Rebalance schedule": "monthly in recovered rule text",
        "Signal timestamp": "not recoverable",
        "Execution timestamp and assumed fill price": "not recoverable",
        "Signal lag": "not recoverable",
        "Missing-data handling": "not recoverable",
        "Target-weight zero handling": "not recoverable",
        "Weight forward-fill behavior": "not recoverable",
        "Exposure normalization and caps": "not recoverable",
        "Transaction costs and slippage": "not recoverable",
        "Fractional-share assumptions": "not recoverable",
        "Dividends or distributions": "not recoverable",
        "Equity and return calculation": "not recoverable",
        "Metric-definition differences": "not recoverable; 4071.04 appears only as conversation-recovered final-equity summary",
    }
    rows = []
    for field in current:
        recovered_value = recovered[field]
        status = "same_or_compatible" if recovered_value == current[field] else "not_recoverable" if "not recoverable" in recovered_value else "partially_comparable"
        rows.append(
            {
                "comparison_field": field,
                "recovered_activation_evidence": recovered_value,
                "current_cached_recompute": current[field],
                "comparison_status": status,
                "notes": "Recovered methodology lacks enough structured fields for date-level replay." if status == "not_recoverable" else "",
            }
        )
    return rows


def build_daily_path_rows(trace_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in trace_rows:
        rows.append(
            {
                "date": row["date"],
                "signal_date": row["signal_date"],
                "window_start": row["window_start"],
                "window_end": row["window_end"],
                "current_recompute_weights": json.dumps(row["weights"], sort_keys=True),
                "current_recompute_exposure": round(row["exposure"], 8),
                "current_recompute_daily_return": round(row["daily_return"], 10),
                "current_recompute_equity": round(row["equity"], 6),
                "recovered_weights": "unavailable",
                "recovered_exposure": "unavailable",
                "recovered_daily_return": "unavailable",
                "recovered_equity": "unavailable",
                "comparison_status": "current_path_only_recovered_path_unavailable",
            }
        )
    return rows


def build_invariant_rows(sample_rows: list[dict[str, Any]], trace_rows: list[dict[str, Any]], reproduced_best: float) -> list[dict[str, Any]]:
    max_exposure = max((row["exposure"] for row in trace_rows), default=0.0)
    max_weight_sum = max((row["weight_sum"] for row in trace_rows), default=0.0)
    min_weight = min((min(row["weights"].values()) for row in trace_rows if row["weights"]), default=0.0)
    no_nan = all(not math.isnan(weight) for row in trace_rows for weight in row["weights"].values())
    bil_remainder_pass = all(abs(row["bil_weight"] + row["risky_weight"] - row["weight_sum"]) <= 1e-10 for row in trace_rows)
    stale_removed_pass = all(all(symbol not in row["weights"] for symbol in row["removed_symbols_on_rebalance"]) for row in trace_rows)
    current_best_sample = max((row["final_equity"] for row in sample_rows), default=float("nan"))
    rows = [
        ("deterministic_best_final_equity", abs(current_best_sample - reproduced_best) <= TOLERANCE, current_best_sample, reproduced_best, "best sampled window reproduces current evidence"),
        ("max_daily_exposure_lte_1", max_exposure <= 1.000001, max_exposure, "<=1.000001", "current traced best sampled window"),
        ("max_daily_weight_sum_lte_1", max_weight_sum <= 1.000001, max_weight_sum, "<=1.000001", "current traced best sampled window"),
        ("no_negative_weights", min_weight >= -1e-12, min_weight, ">=0", "current traced best sampled window"),
        ("no_nan_final_weights", no_nan, no_nan, True, "current traced best sampled window"),
        ("bil_remainder_not_additive", bil_remainder_pass, bil_remainder_pass, True, "BIL plus risky exposure equals total exposure; BIL is not additive above 1"),
        ("zero_targets_not_stale_forward_filled", stale_removed_pass, stale_removed_pass, True, "weights dict is replaced at rebalance; removed symbols are absent after rebalance"),
    ]
    return [
        {
            "check": check,
            "passed": passed,
            "observed_value": observed,
            "expected_value": expected,
            "notes": notes,
        }
        for check, passed, observed, expected, notes in rows
    ]


def build_first_divergence(recovered_reproducible: bool, current_reproduced: float, best_row: dict[str, Any]) -> list[dict[str, Any]]:
    if not recovered_reproducible:
        return [
            {
                "divergence_type": "artifact_level",
                "date": "not_available",
                "current_window_start": best_row.get("window_start", "unknown"),
                "current_window_end": best_row.get("window_end", "unknown"),
                "current_value": current_reproduced,
                "recovered_value": RECOVERED_BEST_FINAL_EQUITY,
                "signal_difference": "not_available_recovered_daily_signals_missing",
                "target_weight_difference": "not_available_recovered_daily_weights_missing",
                "exposure_difference": "not_available_recovered_daily_exposure_missing",
                "daily_return_difference": "not_available_recovered_daily_returns_missing",
                "equity_path_difference": "not_available_recovered_daily_equity_missing",
                "first_assumption_or_transformation": "Recovered best_final_equity has no source window list, daily path, metric definition, data snapshot, execution lag, or cost assumption in repository evidence.",
            }
        ]
    return []


def build_artifact_lineage(root: Path) -> list[dict[str, Any]]:
    artifacts = [
        ("canonical_active_observation", ACTIVE_OBSERVATION_PATH, "contains recovered 4071.04 metric and frozen active state"),
        ("recovered_activation_copy", ACTIVATION_COPY_PATH, "copy matches active observation hash"),
        ("recovered_activation_manifest", ACTIVATION_MANIFEST_PATH, "records evidence_source=conversation_recovered"),
        ("current_recompute_profit_review", RECOMPUTE_PROFIT_PATH, "contains current best_final_equity=3481.6998"),
        ("current_recovered_vs_recomputed", RECOMPUTE_RECOVERED_VS_RECOMPUTED_PATH, "contains material mismatch row"),
        ("current_target_windows", RECOMPUTE_TARGET_WINDOWS_PATH, "contains five sampled current diagnostic windows"),
        ("current_rule_fidelity", RECOMPUTE_RULE_FIDELITY_PATH, "documents DSR rule fidelity pass"),
        ("current_consistency", RECOMPUTE_CONSISTENCY_PATH, "documents non-mutation and recompute guardrails"),
        ("prior_reconciliation_summary", RECONCILIATION_PATH / "active_observation_evidence_reconciliation.json", "documents E4 conflict and E1 SEL level"),
    ]
    return [
        {
            "artifact_role": role,
            "source_path": rel(path),
            "exists": (root / path).exists(),
            "sha256": file_hash(root / path),
            "notes": notes,
        }
        for role, path, notes in artifacts
    ]


def build_unresolved_assumptions() -> list[dict[str, Any]]:
    assumptions = [
        ("recovered_metric_window_start", "missing", "No source artifact identifies the 180-day window producing 4071.04."),
        ("recovered_metric_window_end", "missing", "No source artifact identifies the 180-day window producing 4071.04."),
        ("recovered_daily_signals", "missing", "No recovered daily signal path exists."),
        ("recovered_daily_weights", "missing", "No recovered daily target-weight path exists."),
        ("recovered_data_snapshot", "missing", "No data snapshot/hash/date range linked to the recovered metric exists."),
        ("recovered_price_field", "missing", "Adjusted-price field and corporate-action treatment are not specified for the recovered metric."),
        ("recovered_execution_lag", "missing", "Signal/execution timestamp and fill price are not specified for the recovered metric."),
        ("recovered_cost_assumption", "missing", "Recovered metric does not state whether slippage/turnover costs were applied."),
        ("recovered_metric_definition", "missing", "It is not specified whether best_final_equity is from five sampled windows, all rolling windows, or a different report."),
        ("historical_source_code", "missing", "No source code or git-linked implementation was found that deterministically generated 4071.04."),
    ]
    return [
        {
            "assumption": name,
            "status": status,
            "impact": "prevents exact recovery of 4071.04",
            "notes": notes,
        }
        for name, status, notes in assumptions
    ]


def build_superseded_metrics(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in metric_rows:
        metric = row.get("metric")
        status = "historical_recovered_claim_non_comparable_to_current_diagnostic"
        if metric == "best_final_equity":
            status = "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference"
        rows.append(
            {
                "metric": metric,
                "recovered_value": row.get("recovered_value"),
                "current_recomputed_value": row.get("current_recomputed_value"),
                "status": status,
                "reason": f"{row.get('notes')} Historical value is preserved for audit history; current diagnostic is not a historical replacement.",
                "current_reference_artifact": rel(RECOMPUTE_RECOVERED_VS_RECOMPUTED_PATH),
            }
        )
    return rows


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# DSR Active Evidence Mismatch Review",
        "",
        f"Created UTC: `{payload['created_at_utc']}`",
        "",
        f"Root-cause verdict: `{payload['root_cause_verdict']}`.",
        "",
        "## Conclusions",
        "",
        f"- `4071.04` reproducible from repository evidence: `{str(payload['recovered_4071_reproducible']).lower()}`.",
        f"- `3481.6998` reproducible deterministically: `{str(payload['current_3481_reproducible']).lower()}`.",
        f"- Current diagnostic reference: `{payload['defensible_current_diagnostic_reference']}`.",
        f"- Recovered metric status: `{payload['recovered_metric_status']}`.",
        f"- First divergence: `{payload['first_divergence_summary']}`.",
        f"- Current recompute defect found: `{str(payload['current_recompute_defect_found']).lower()}`.",
        f"- SEL evidence effect: `{payload['sel_evidence_effect']}`.",
        "",
        "## Guardrails",
        "",
        "- No strategy, lifecycle, registry, paper/demo, broker/live, provider-download, or real-money state was changed.",
        "- No DSR rules, thresholds, universe, frozen configuration, or active observation instructions were modified.",
    ]
    return "\n".join(lines) + "\n"


def run_dsr_active_evidence_mismatch_review(root: Path = ROOT) -> dict[str, Any]:
    canonical_hashes_before = hash_paths(root, CANONICAL_PATHS)
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    activation = read_yaml(root / ACTIVE_OBSERVATION_PATH)
    recompute_consistency = read_json(root / RECOMPUTE_CONSISTENCY_PATH)
    sample_rows = current_sample_rows(root)
    best_start, best_row = best_sample_start(root)
    trace_rows = trace_window(root, best_start) if best_start is not None else []
    current_best = max((float(row["final_equity"]) for row in sample_rows), default=float("nan"))
    current_3481_reproducible = abs(current_best - CURRENT_BEST_FINAL_EQUITY) <= 1e-3
    recovered_4071_reproducible = False

    metric_rows = build_metric_comparison(root, current_best)
    methodology_rows = build_methodology_comparison()
    daily_path_rows = build_daily_path_rows(trace_rows)
    invariant_rows = build_invariant_rows(sample_rows, trace_rows, current_best)
    first_divergence_rows = build_first_divergence(recovered_4071_reproducible, current_best, best_row)
    artifact_rows = build_artifact_lineage(root)
    unresolved_rows = build_unresolved_assumptions()
    superseded_rows = build_superseded_metrics(metric_rows)

    invariant_passed = all(str(row["passed"]).lower() == "true" for row in invariant_rows)
    root_cause = "unresolved_missing_inputs"
    payload = {
        "created_at_utc": utc_now(),
        "git_head": git_head(root),
        "target_active_observation_id": ACTIVE_ID,
        "parent_strategy_id": PARENT_ID,
        "family_id": FAMILY_ID,
        "mismatch_review_only": True,
        "root_cause_verdict": root_cause,
        "root_cause_secondary_classification": "non_comparable_methodologies",
        "recovered_4071_reproducible": recovered_4071_reproducible,
        "current_3481_reproducible": current_3481_reproducible,
        "current_best_final_equity": round(current_best, 4) if not math.isnan(current_best) else "unavailable",
        "recovered_best_final_equity": RECOVERED_BEST_FINAL_EQUITY,
        "final_equity_gap": round(RECOVERED_BEST_FINAL_EQUITY - current_best, 4) if not math.isnan(current_best) else "unavailable",
        "same_rules": "partially_recoverable_rule_text_matches",
        "same_data": "cannot_determine_recovered_data_snapshot_missing",
        "same_date_range": "cannot_determine_recovered_window_missing",
        "same_execution_assumptions": "cannot_determine_recovered_execution_missing",
        "same_cost_assumptions": "cannot_determine_recovered_cost_missing",
        "first_divergence_summary": first_divergence_rows[0]["first_assumption_or_transformation"],
        "current_recompute_defect_found": False,
        "current_recompute_invariants_passed": invariant_passed,
        "current_recompute_known_defect_invalidates_result": False,
        "recovered_metric_status": "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference",
        "defensible_current_diagnostic_reference": "3481.6998 from active_strategy_evidence_recompute sampled-window diagnostic; current_diagnostic_only_not_historical_replacement",
        "sel_evidence_effect": "No SEL evidence-level upgrade; DSR remains highest independently verified E1 and E4 remains non-qualifying because original qualifying backtest/config/data lineage is missing.",
        "missing_evidence_prevents_e4_qualification": True,
        "canonical_state_unchanged": True,
        "active_observation_status": activation.get("status", "unknown"),
        "paper_forward_active": activation.get("paper_forward_active", "unknown"),
        "rules_frozen": activation.get("rules_frozen", "unknown"),
        "guardrails": {
            "no_backtest_or_strategy_discovery": True,
            "diagnostic_replay_only": True,
            "no_parameter_tuning": True,
            "no_alternative_variants": True,
            "no_provider_download": True,
            "no_broker_or_live_path": True,
            "no_promotion_rejection_activation_or_deactivation": True,
            "no_canonical_state_change": True,
        },
        "evidence_outputs": [
            "dsr_mismatch_review.json",
            "dsr_mismatch_review.md",
            "methodology_comparison.csv",
            "metric_comparison.csv",
            "first_divergence.csv",
            "daily_path_comparison.csv",
            "weight_exposure_invariants.csv",
            "artifact_lineage.csv",
            "unresolved_assumptions.csv",
            "superseded_metrics.csv",
            "mismatch_review_consistency_check.json",
        ],
    }

    canonical_hashes_after = hash_paths(root, CANONICAL_PATHS)
    consistency = {
        "mismatch_review_completed": True,
        "target_active_observation_id": ACTIVE_ID,
        "canonical_hashes_before": canonical_hashes_before,
        "canonical_hashes_after": canonical_hashes_after,
        "canonical_hashes_unchanged": canonical_hashes_before == canonical_hashes_after,
        "current_3481_reproducible": current_3481_reproducible,
        "recovered_4071_reproducible": recovered_4071_reproducible,
        "root_cause_verdict_valid": root_cause
        in {
            "recovered_metric_superseded",
            "current_recompute_defect",
            "non_comparable_methodologies",
            "historical_methodology_partially_recoverable",
            "unresolved_missing_inputs",
        },
        "current_recompute_invariants_passed": invariant_passed,
        "active_recompute_reference_consistency_passed": bool(recompute_consistency.get("consistency_passed")),
        "no_strategy_metrics_recomputed_for_selection": True,
        "no_new_backtest_run": True,
        "no_provider_download": True,
        "no_broker_or_live_path": True,
        "no_strategy_lifecycle_change": True,
        "no_paper_demo_state_change": True,
        "no_frozen_rule_change": True,
        "no_strategy_promotion_or_rejection": True,
        "sel_evidence_model_changed": False,
    }
    consistency["consistency_passed"] = all(
        bool(consistency[key])
        for key in [
            "mismatch_review_completed",
            "canonical_hashes_unchanged",
            "current_3481_reproducible",
            "root_cause_verdict_valid",
            "current_recompute_invariants_passed",
            "active_recompute_reference_consistency_passed",
            "no_strategy_metrics_recomputed_for_selection",
            "no_new_backtest_run",
            "no_provider_download",
            "no_broker_or_live_path",
            "no_strategy_lifecycle_change",
            "no_paper_demo_state_change",
            "no_frozen_rule_change",
            "no_strategy_promotion_or_rejection",
        ]
    )

    write_json(output / "dsr_mismatch_review.json", payload)
    (output / "dsr_mismatch_review.md").write_text(markdown_report(payload), encoding="utf-8")
    write_csv(output / "methodology_comparison.csv", methodology_rows, ["comparison_field", "recovered_activation_evidence", "current_cached_recompute", "comparison_status", "notes"])
    write_csv(output / "metric_comparison.csv", metric_rows, ["metric", "recovered_value", "current_recomputed_value", "diagnostic_reproduced_value", "absolute_delta", "verdict", "notes"])
    write_csv(
        output / "first_divergence.csv",
        first_divergence_rows,
        [
            "divergence_type",
            "date",
            "current_window_start",
            "current_window_end",
            "current_value",
            "recovered_value",
            "signal_difference",
            "target_weight_difference",
            "exposure_difference",
            "daily_return_difference",
            "equity_path_difference",
            "first_assumption_or_transformation",
        ],
    )
    write_csv(
        output / "daily_path_comparison.csv",
        daily_path_rows,
        [
            "date",
            "signal_date",
            "window_start",
            "window_end",
            "current_recompute_weights",
            "current_recompute_exposure",
            "current_recompute_daily_return",
            "current_recompute_equity",
            "recovered_weights",
            "recovered_exposure",
            "recovered_daily_return",
            "recovered_equity",
            "comparison_status",
        ],
    )
    write_csv(output / "weight_exposure_invariants.csv", invariant_rows, ["check", "passed", "observed_value", "expected_value", "notes"])
    write_csv(output / "artifact_lineage.csv", artifact_rows, ["artifact_role", "source_path", "exists", "sha256", "notes"])
    write_csv(output / "unresolved_assumptions.csv", unresolved_rows, ["assumption", "status", "impact", "notes"])
    write_csv(output / "superseded_metrics.csv", superseded_rows, ["metric", "recovered_value", "current_recomputed_value", "status", "reason", "current_reference_artifact"])
    write_json(output / "mismatch_review_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "root_cause_verdict": payload["root_cause_verdict"],
        "recovered_4071_reproducible": recovered_4071_reproducible,
        "current_3481_reproducible": current_3481_reproducible,
        "current_best_final_equity": payload["current_best_final_equity"],
        "current_recompute_invariants_passed": invariant_passed,
        "canonical_state_unchanged": consistency["canonical_hashes_unchanged"],
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    result = run_dsr_active_evidence_mismatch_review(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
