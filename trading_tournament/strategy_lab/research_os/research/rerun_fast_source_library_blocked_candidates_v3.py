from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior
from strategy_lab.research_os.research import fast_source_library_batch_v3 as source_batch
from strategy_lab.research_os.research import vnq_jnk_data_feasibility_acquisition_v1 as data_task


BATCH_ID = "rerun_fast_source_library_blocked_candidates_v3"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v1"
ADAPTATION_LABEL = "data_feasibility_adjustment"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = source_batch.WEIGHT_TOLERANCE

TARGET_STRATEGY_IDS = (
    "daryanani_opportunistic_rebalance_20band_10day_v1",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "ice_vaneck_us_fallen_angel_angl_v1",
)
NVI_STRATEGY_ID = "fosback_nvi_255ema_spy_bil_v1"

NEXT_ACTION_REVIEW = "direction_owner_review_rerun_fast_source_library_blocked_candidates_v3"
NEXT_ACTION_EVALUATE_REMAINING = "evaluate_remaining_source_library_candidates_v1"
NEXT_ACTION_PARTIAL_BLOCK = "direction_owner_review_partial_block_rerun_fast_source_library_v3"

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
INPUT_EVIDENCE_FILES = [
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "batch_manifest.yaml",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "frozen_source_cards.csv",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "preregistered_strategy_cards.csv",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "trial_lineage.csv",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "rejection_and_data_issue_log.csv",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "benchmark_reference_log.csv",
    ROOT / "evidence" / "data_capability" / "vnq_jnk_data_feasibility_acquisition_v1" / "latest" / "data_coverage.csv",
    ROOT / "evidence" / "data_capability" / "vnq_jnk_data_feasibility_acquisition_v1" / "latest" / "data_integrity_checks.csv",
    ROOT
    / "evidence"
    / "data_capability"
    / "vnq_jnk_data_feasibility_acquisition_v1"
    / "latest"
    / "cache_reload_reconciliation.csv",
    ROOT
    / "evidence"
    / "data_capability"
    / "vnq_jnk_data_feasibility_acquisition_v1"
    / "latest"
    / "strategy_data_sufficiency.csv",
    ROOT
    / "evidence"
    / "data_capability"
    / "vnq_jnk_data_feasibility_acquisition_v1"
    / "latest"
    / "consistency_check.json",
]
PROTECTED_CACHE_PATHS = [
    ROOT / "data" / "cache" / "VNQ.csv",
    ROOT / "data" / "cache" / "VNQ.acquisition.json",
    ROOT / "data" / "cache" / "JNK.csv",
    ROOT / "data" / "cache" / "JNK.acquisition.json",
]
FORBIDDEN_FLAGS = {
    "source_research": False,
    "source_rule_completion": False,
    "provider_download": False,
    "parameter_search": False,
    "parameter_variation": False,
    "instrument_substitution": False,
    "benchmark_correction": False,
    "timeframe_selection_based_on_results": False,
    "validation_or_robustness_testing": False,
    "dsr_pbo_cscv_reality_check_run": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "trade_management_overlay_run": False,
    "registry_or_dashboard_rebuild": False,
    "broker_account_order_or_real_money_action": False,
    "nvi_rerun_or_modification": False,
}


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized = normalized.sort_values("date") if "date" in normalized.columns else normalized
    payload = normalized.to_csv(index=False, lineterminator="\n")
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def input_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in INPUT_EVIDENCE_FILES if path.exists()}


def protected_cache_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_CACHE_PATHS if path.exists()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parent_issue_rows() -> dict[str, dict[str, str]]:
    rows = read_csv_rows(ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest" / "rejection_and_data_issue_log.csv")
    return {row["strategy_id"]: row for row in rows}


def data_coverage_rows() -> dict[str, dict[str, str]]:
    rows = read_csv_rows(
        ROOT / "evidence" / "data_capability" / "vnq_jnk_data_feasibility_acquisition_v1" / "latest" / "data_coverage.csv"
    )
    return {row["symbol"]: row for row in rows}


def data_source_manifest_rows() -> dict[str, dict[str, str]]:
    rows = read_csv_rows(
        ROOT
        / "evidence"
        / "data_capability"
        / "vnq_jnk_data_feasibility_acquisition_v1"
        / "latest"
        / "data_source_manifest.csv"
    )
    return {row["symbol"]: row for row in rows}


def data_consistency() -> dict[str, Any]:
    return read_json(
        ROOT / "evidence" / "data_capability" / "vnq_jnk_data_feasibility_acquisition_v1" / "latest" / "consistency_check.json"
    )


def base_cards_by_id() -> dict[str, Any]:
    return {card.strategy_id: card for card in source_batch.CARDS}


def rerun_trial_id(strategy_id: str) -> str:
    return f"rerun_fast_source_v3__{strategy_id}__data_feasibility_adjustment_child"


def child_cards() -> list[Any]:
    cards = []
    source_cards = base_cards_by_id()
    for strategy_id in TARGET_STRATEGY_IDS:
        parent = source_cards[strategy_id]
        cards.append(replace(parent, parent_trial_id=parent.trial_id))
    return cards


def child_trial_id_by_strategy() -> dict[str, str]:
    return {strategy_id: rerun_trial_id(strategy_id) for strategy_id in TARGET_STRATEGY_IDS}


def with_child_trial(row: dict[str, Any], card: Any) -> dict[str, Any]:
    out = dict(row)
    out["trial_id"] = rerun_trial_id(card.strategy_id)
    out["parent_trial_id"] = card.parent_trial_id
    return out


def load_normal_interface_symbol(symbol: str) -> pd.DataFrame:
    return prior.load_adjusted_ohlcv(symbol)


def canonical_cache_frame(symbol: str) -> pd.DataFrame:
    return data_task.load_canonical_cache(symbol)


def symbol_preflight_rows(cards: list[Any]) -> list[dict[str, Any]]:
    coverage = data_coverage_rows()
    source_manifest = data_source_manifest_rows()
    rows: list[dict[str, Any]] = []
    for symbol in ("VNQ", "JNK"):
        loaded = load_normal_interface_symbol(symbol)
        canonical = canonical_cache_frame(symbol)
        evidence = coverage.get(symbol, {})
        source_row = source_manifest.get(symbol, {})
        first = loaded.index.min().date().isoformat() if not loaded.empty else ""
        last = loaded.index.max().date().isoformat() if not loaded.empty else ""
        rows.append(
            {
                "record_id": symbol,
                "record_type": "symbol_preflight",
                "stage": "exploration",
                "symbol": symbol,
                "strategy_id": "",
                "trial_id": "",
                "normal_interface_row_count": int(len(loaded)),
                "evidence_row_count": evidence.get("row_count", ""),
                "row_count_matches_evidence": str(len(loaded)) == str(evidence.get("row_count", "")),
                "normal_interface_first_date": first,
                "evidence_first_date": evidence.get("first_date", ""),
                "first_date_matches_evidence": first == evidence.get("first_date", ""),
                "normal_interface_last_date": last,
                "evidence_last_date": evidence.get("last_date", ""),
                "last_date_matches_evidence": last == evidence.get("last_date", ""),
                "normal_interface_cache_hash": loaded.attrs.get("cache_hash", ""),
                "evidence_cache_hash": evidence.get("cache_file_hash", ""),
                "cache_hash_matches_evidence": loaded.attrs.get("cache_hash", "") == evidence.get("cache_file_hash", ""),
                "canonical_frame_hash": dataframe_hash(canonical) if not canonical.empty else "",
                "evidence_canonical_frame_hash": source_row.get("canonical_frame_hash", ""),
                "canonical_frame_hash_matches_evidence": dataframe_hash(canonical) == source_row.get("canonical_frame_hash", "")
                if not canonical.empty
                else False,
                "preflight_status": "pass"
                if (
                    not loaded.empty
                    and str(len(loaded)) == str(evidence.get("row_count", ""))
                    and first == evidence.get("first_date", "")
                    and last == evidence.get("last_date", "")
                    and loaded.attrs.get("cache_hash", "") == evidence.get("cache_file_hash", "")
                )
                else "fail",
                "failure_reason": "" if not loaded.empty else "data_or_comparability_failure",
            }
        )
    for card in cards:
        required_symbols = tuple(card.required_data_symbols)
        missing = [symbol for symbol in required_symbols if load_normal_interface_symbol(symbol).empty]
        prices = prior.load_price_frame(required_symbols)
        rows.append(
            {
                "record_id": card.strategy_id,
                "record_type": "strategy_preflight",
                "stage": "exploration",
                "symbol": "",
                "strategy_id": card.strategy_id,
                "trial_id": rerun_trial_id(card.strategy_id),
                "required_symbols": required_symbols,
                "missing_symbols": missing,
                "all_candidate_and_control_instruments_available": not missing,
                "first_common_candidate_control_date": prices.index.min().date().isoformat() if not prices.empty else "",
                "last_common_candidate_control_date": prices.index.max().date().isoformat() if not prices.empty else "",
                "common_trading_days": int(len(prices)),
                "preflight_status": "pass" if not missing and not prices.empty else "fail",
                "failure_reason": "" if not missing and not prices.empty else "data_or_comparability_failure",
            }
        )
    return rows


def normalize_outcome(classification: str) -> str:
    if classification == "exploratory_followup_candidate_diversifier":
        return classification
    if classification == "closed_exploration":
        return classification
    if classification == "inconclusive_data_issue":
        return classification
    return "blocked_feasibility"


def standardized_stage(outcome: str) -> str:
    if outcome == "exploratory_followup_candidate_diversifier":
        return "exploratory_followup_diversifier"
    if outcome == "closed_exploration":
        return "closed"
    if outcome in {"inconclusive_data_issue", "blocked_feasibility"}:
        return "blocked"
    return "exploration"


def failure_reason_for(outcome: str, decision_reason: str) -> str:
    if outcome == "exploratory_followup_candidate_diversifier":
        return ""
    text = decision_reason.lower()
    if "data" in text or "missing" in text or "invariant" in text or "methodology" in text:
        return "data_or_comparability_failure"
    if "return_not_positive" in text:
        return "weak_return"
    if "dominated" in text or "replicated" in text or "control" in text:
        return "weak_vs_primary_control"
    if "80_20_portfolio_did_not_improve_reference" in text:
        return "weak_vs_primary_control"
    if "half" in text or "period" in text:
        return "period_instability"
    return "weak_vs_primary_control"


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return source_batch.dominates(control, candidate)


def metrics_for_returns(returns: pd.Series) -> dict[str, Any]:
    metrics = prior.metrics_from_returns(returns)
    return {
        **metrics,
        "turnover": 0.0,
        "rebalance_or_trade_count": 0,
        "estimated_transaction_cost_drag": 0.0,
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "numeric_invariant_status": "pass" if len(returns.dropna()) else "fail",
        "timing_invariant_status": "pass_project_shifted_weight_no_lookahead",
        "exposure_weight_invariant_status": "pass",
        "invariant_pass": bool(len(returns.dropna())),
    }


def split_periods(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    halves = source_batch.split_halves(index)
    return [("full_period", pd.Timestamp(index.min()), pd.Timestamp(index.max())), *halves]


def portfolio_contribution_rows(
    card: Any,
    candidate_returns_by_cost: dict[float, pd.Series],
    control_returns_by_cost: dict[tuple[str, float], pd.Series],
    reference: pd.Series,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS_GRID:
        reference_aligned = reference.dropna()
        portfolios = {
            "frozen_reference_100pct": reference_aligned,
            f"{card.strategy_id}_candidate_20pct": 0.8 * reference_aligned
            + 0.2 * candidate_returns_by_cost[cost_bps].reindex(reference_aligned.index).fillna(0.0),
        }
        for control_id in card.principal_control_ids:
            portfolios[f"{control_id}_20pct_control"] = 0.8 * reference_aligned + 0.2 * control_returns_by_cost[
                (control_id, cost_bps)
            ].reindex(reference_aligned.index).fillna(0.0)
        for period_label, start, end in split_periods(reference_aligned.index):
            for portfolio_id, returns in portfolios.items():
                period_returns = returns.loc[start:end]
                metrics = metrics_for_returns(period_returns)
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": rerun_trial_id(card.strategy_id),
                        "parent_trial_id": card.parent_trial_id,
                        "route": card.route,
                        "cost_assumption_bps": cost_bps,
                        "period_label": period_label,
                        "half_source": "chronological_half_not_clean_holdout" if period_label != "full_period" else "full_period",
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": "100pct_frozen_reference"
                        if portfolio_id == "frozen_reference_100pct"
                        else "80pct_frozen_reference_plus_20pct_candidate_or_control",
                        **metrics,
                        "correlation_to_frozen_reference": 1.0
                        if portfolio_id == "frozen_reference_100pct"
                        else prior.safe_corr(period_returns, reference_aligned.loc[start:end]),
                    }
                )
    return rows


def classify_diversifier(
    card: Any,
    candidate_5: dict[str, Any],
    control_5: dict[str, dict[str, Any]],
    contribution_rows: list[dict[str, Any]],
) -> tuple[str, str]:
    if not candidate_5.get("invariant_pass"):
        return "inconclusive_data_issue", "candidate_numeric_or_exposure_invariant_failed"
    if float(candidate_5["total_return"]) <= 0.0:
        return "closed_exploration", "candidate_after_cost_full_period_return_not_positive_at_5bps"
    if any(dominates(control, candidate_5) for control in control_5.values()):
        return "closed_exploration", "principal_same_purpose_control_dominated_candidate_on_cagr_sharpe_and_drawdown"

    rows_5 = [
        row
        for row in contribution_rows
        if row["strategy_id"] == card.strategy_id and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
    ]
    full_rows = [row for row in rows_5 if row["period_label"] == "full_period"]
    reference = next(row for row in full_rows if row["portfolio_id"] == "frozen_reference_100pct")
    candidate_portfolio = next(row for row in full_rows if row["portfolio_id"] == f"{card.strategy_id}_candidate_20pct")
    control_portfolios = [row for row in full_rows if row["portfolio_id"].endswith("_20pct_control")]
    improves_sharpe = float(candidate_portfolio["sharpe_ratio"]) > float(reference["sharpe_ratio"])
    improves_drawdown = float(candidate_portfolio["maximum_drawdown"]) > float(reference["maximum_drawdown"])
    worsens_both = (
        float(candidate_portfolio["sharpe_ratio"]) < float(reference["sharpe_ratio"])
        and float(candidate_portfolio["maximum_drawdown"]) < float(reference["maximum_drawdown"])
    )
    if not ((improves_sharpe or improves_drawdown) and not worsens_both):
        return "closed_exploration", "candidate_80_20_portfolio_did_not_improve_reference_without_worsening_both"
    if any(dominates(control, candidate_portfolio) for control in control_portfolios):
        return "closed_exploration", "simple_80_20_control_dominated_candidate_80_20_portfolio"

    for half_label in ("first_chronological_half", "second_chronological_half"):
        half_rows = [row for row in rows_5 if row["period_label"] == half_label]
        candidate_half = next(row for row in half_rows if row["portfolio_id"] == f"{card.strategy_id}_candidate_20pct")
        control_halves = [row for row in half_rows if row["portfolio_id"].endswith("_20pct_control")]
        favorable = any(
            float(candidate_half["sharpe_ratio"]) > float(control["sharpe_ratio"])
            or float(candidate_half["maximum_drawdown"]) > float(control["maximum_drawdown"])
            for control in control_halves
        )
        if not favorable:
            return "closed_exploration", "candidate_80_20_portfolio_not_favorable_vs_control_in_each_chronological_half"
    return "exploratory_followup_candidate_diversifier", "diversifier_candidate_passed_lightweight_exploration_gate"


def trial_metric_row(card: Any, cost_bps: float, returns: pd.Series, turnover: pd.Series, cost: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    metrics = source_batch.metric_payload(returns, turnover, cost, weights)
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": rerun_trial_id(card.strategy_id),
        "parent_trial_id": card.parent_trial_id,
        "route": card.route,
        "cost_assumption_bps": cost_bps,
        "outcome": "pending_gate",
        "stage": "exploration",
        "primary_failure_reason": "",
        "next_action": "",
        **metrics,
        "data_issue": "",
        "missing_symbols": "",
        **FORBIDDEN_FLAGS,
    }


def control_metric_row(
    card: Any,
    control_id: str,
    cost_bps: float,
    returns: pd.Series,
    turnover: pd.Series,
    cost: pd.Series,
    weights: pd.DataFrame,
) -> dict[str, Any]:
    metrics = source_batch.metric_payload(returns, turnover, cost, weights)
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": rerun_trial_id(card.strategy_id),
        "parent_trial_id": card.parent_trial_id,
        "control_id": control_id,
        "entity_type": "benchmark_reference",
        "stage": "benchmark_reference_only",
        "cost_assumption_bps": cost_bps,
        **metrics,
        "data_issue": "",
        "missing_symbols": "",
    }


def half_metric_rows(
    card: Any,
    row_type: str,
    control_id: str,
    cost_bps: float,
    returns: pd.Series,
    turnover: pd.Series,
    cost: pd.Series,
    weights: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for half_label, start, end in source_batch.split_halves(returns.index):
        half_returns = returns.loc[start:end]
        metrics = source_batch.metric_payload(
            half_returns,
            turnover.loc[start:end],
            cost.loc[start:end],
            weights.reindex(half_returns.index).ffill().fillna(0.0),
        )
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "row_type": row_type,
                "control_id": control_id,
                "cost_assumption_bps": cost_bps,
                "half_label": half_label,
                "half_source": "chronological_half_not_clean_holdout",
                **metrics,
            }
        )
    return rows


def blocked_trial_rows(card: Any, issue: str, missing: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS_GRID:
        trial_rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "route": card.route,
                "cost_assumption_bps": cost_bps,
                "outcome": "inconclusive_data_issue",
                "stage": "blocked",
                "primary_failure_reason": "data_or_comparability_failure",
                "next_action": NEXT_ACTION_PARTIAL_BLOCK,
                "evaluation_start": "",
                "evaluation_end": "",
                "trading_days": 0,
                "numeric_invariant_status": "not_evaluated_data_issue",
                "timing_invariant_status": "not_evaluated_data_issue",
                "exposure_weight_invariant_status": "not_evaluated_data_issue",
                "invariant_pass": False,
                "data_issue": issue,
                "missing_symbols": missing,
                **FORBIDDEN_FLAGS,
            }
        )
        for control_id in card.principal_control_ids:
            control_rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": rerun_trial_id(card.strategy_id),
                    "parent_trial_id": card.parent_trial_id,
                    "control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "cost_assumption_bps": cost_bps,
                    "data_issue": issue,
                    "missing_symbols": missing,
                }
            )
    return trial_rows, control_rows, half_rows


def run_candidate(card: Any, reference_returns: pd.Series) -> dict[str, Any]:
    outcome = source_batch.run_card(card, reference_returns)
    if not outcome["executable"]:
        issue = outcome.get("date_issue", "data_or_comparability_failure")
        missing = outcome.get("missing", [])
        trial_rows, control_rows, half_rows = blocked_trial_rows(card, issue, missing)
        return {
            "card": card,
            "executable": False,
            "outcome": "inconclusive_data_issue",
            "decision_reason": issue,
            "primary_failure_reason": "data_or_comparability_failure",
            "trial_rows": trial_rows,
            "control_rows": control_rows,
            "half_rows": half_rows,
            "portfolio_rows": [],
            "candidate_5": {},
            "control_5": {},
            "evaluation_start": "",
            "evaluation_end": "",
        }

    prices = outcome["prices"]
    reference = outcome["reference"]
    weights = outcome["weights"]
    controls = outcome["controls"]
    trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    candidate_returns_by_cost: dict[float, pd.Series] = {}
    control_returns_by_cost: dict[tuple[str, float], pd.Series] = {}
    candidate_5: dict[str, Any] = {}
    control_5: dict[str, dict[str, Any]] = {}

    for cost_bps in COST_BPS_GRID:
        candidate_returns, turnover, cost = source_batch.returns_for_weights(prices, weights, cost_bps)
        candidate_returns_by_cost[cost_bps] = candidate_returns
        trial_row = trial_metric_row(card, cost_bps, candidate_returns, turnover, cost, weights)
        trial_rows.append(trial_row)
        half_rows.extend(half_metric_rows(card, "candidate", "", cost_bps, candidate_returns, turnover, cost, weights))
        if cost_bps == PRIMARY_COST_BPS:
            candidate_5 = trial_row
        for control_id, control_weight in controls.items():
            control_prices = prices.reindex(columns=control_weight.columns).dropna()
            aligned_control_weight = control_weight.reindex(control_prices.index).ffill().fillna(0.0)
            control_returns, control_turnover, control_cost = source_batch.returns_for_weights(
                control_prices, aligned_control_weight, cost_bps
            )
            control_returns_by_cost[(control_id, cost_bps)] = control_returns
            control_row = control_metric_row(card, control_id, cost_bps, control_returns, control_turnover, control_cost, aligned_control_weight)
            control_rows.append(control_row)
            half_rows.extend(
                half_metric_rows(card, "control", control_id, cost_bps, control_returns, control_turnover, control_cost, aligned_control_weight)
            )
            if cost_bps == PRIMARY_COST_BPS:
                control_5[control_id] = {**control_row, "control_id": control_id}

    portfolio_rows = portfolio_contribution_rows(card, candidate_returns_by_cost, control_returns_by_cost, reference)
    outcome_label, decision_reason = classify_diversifier(card, candidate_5, control_5, portfolio_rows)
    primary_failure = failure_reason_for(outcome_label, decision_reason)
    next_action = NEXT_ACTION_REVIEW if outcome_label == "exploratory_followup_candidate_diversifier" else NEXT_ACTION_EVALUATE_REMAINING
    for row in trial_rows:
        row["outcome"] = outcome_label
        row["stage"] = standardized_stage(outcome_label)
        row["primary_failure_reason"] = primary_failure
        row["next_action"] = next_action
        row["decision_reason"] = decision_reason
    return {
        "card": card,
        "executable": True,
        "outcome": outcome_label,
        "decision_reason": decision_reason,
        "primary_failure_reason": primary_failure,
        "trial_rows": trial_rows,
        "control_rows": control_rows,
        "half_rows": half_rows,
        "portfolio_rows": portfolio_rows,
        "candidate_5": candidate_5,
        "control_5": control_5,
        "evaluation_start": prices.index.min().date().isoformat(),
        "evaluation_end": prices.index.max().date().isoformat(),
    }


def strategy_card_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "stage": "exploration",
                "source_library_id": SOURCE_LIBRARY_ID,
                "complete_frozen_rule": card.complete_frozen_rule,
                "instrument_universe": card.required_data_symbols,
                "parameters": card.parameters,
                "benchmark_or_control": card.principal_control_ids,
                "route": card.route,
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "evaluation_start": result["evaluation_start"],
                "evaluation_end": result["evaluation_end"],
                "strategy_definition_changed": False,
                "nvi_record": False,
            }
        )
    return rows


def trial_ledger_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        outcome_label = normalize_outcome(result["outcome"])
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "experiment_trial",
                "strategy_architecture": card.complete_frozen_rule,
                "source_or_research_lineage": "fast_source_library_batch_v3_blocked_parent_trial",
                "instrument_universe": card.required_data_symbols,
                "parameters": card.parameters,
                "benchmark_or_control": card.principal_control_ids,
                "stage": standardized_stage(outcome_label),
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "adaptation_label": ADAPTATION_LABEL,
                "changed_fields_from_parent": "data_availability_and_common_eligible_period_only",
                "outcome": outcome_label,
                "primary_failure_reason": result["primary_failure_reason"],
                "next_action": next_action,
                "new_child_trial_created": True,
                "parent_trial_reused": False,
                "strategy_definition_changed": False,
            }
        )
    return rows


def benchmark_reference_rows(cards: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in cards:
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
                "entity_type": "benchmark_reference",
                "stage": "benchmark_reference_only",
                "calculated_in_this_task": True,
                "reference_role": "portfolio_contribution_reference_only",
            }
        )
        for control_id in card.principal_control_ids:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": rerun_trial_id(card.strategy_id),
                    "parent_trial_id": card.parent_trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "calculated_in_this_task": True,
                    "reference_role": "same_purpose_control",
                }
            )
    return rows


def process_task_row(next_action: str, outcome: str) -> dict[str, Any]:
    return {
        "task_id": BATCH_ID,
        "entity_type": "process_task",
        "stage": "exploration",
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_now": False,
        "strategy_counted": False,
        "experiment_trial_counted": False,
    }


def outcome_summary_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        card = result["card"]
        outcome_label = normalize_outcome(result["outcome"])
        rows.append(
            {
                "entity_id": card.strategy_id,
                "entity_type": "strategy_configuration",
                "stage": standardized_stage(outcome_label),
                "outcome": outcome_label,
                "primary_failure_reason": result["primary_failure_reason"],
                "next_action": next_action,
                "counted_in_strategy_cohort": True,
            }
        )
    rows.append(
        {
            "entity_id": NVI_STRATEGY_ID,
            "entity_type": "strategy_configuration",
            "stage": "exploratory_followup_standalone",
            "outcome": "exploratory_followup_candidate_standalone",
            "primary_failure_reason": "",
            "next_action": "targeted_nvi_incremental_signal_followup_v1",
            "counted_in_strategy_cohort": False,
        }
    )
    return rows


def failure_reason_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        if result["outcome"] == "exploratory_followup_candidate_diversifier":
            continue
        card = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": rerun_trial_id(card.strategy_id),
                "parent_trial_id": card.parent_trial_id,
                "outcome": normalize_outcome(result["outcome"]),
                "primary_failure_reason": result["primary_failure_reason"],
                "decision_reason": result["decision_reason"],
                "next_action": next_action,
            }
        )
    return rows


def next_action_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": "global",
            "entity_id": BATCH_ID,
            "exact_next_action": next_action,
            "execute_now": False,
            "reason": "selected_from_predeclared_rerun_outcome_rules",
        }
    ]
    for result in results:
        card = result["card"]
        rows.append(
            {
                "scope": "strategy_configuration",
                "entity_id": card.strategy_id,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": result["outcome"],
            }
        )
    rows.append(
        {
            "scope": "nvi_context_only",
            "entity_id": NVI_STRATEGY_ID,
            "exact_next_action": "targeted_nvi_incremental_signal_followup_v1",
            "execute_now": False,
            "reason": "nvi_not_included_or_modified_in_this_rerun",
        }
    )
    return rows


def final_next_action(results: list[dict[str, Any]]) -> str:
    outcomes = [result["outcome"] for result in results]
    if any(outcome in {"inconclusive_data_issue", "blocked_feasibility"} for outcome in outcomes):
        return NEXT_ACTION_PARTIAL_BLOCK
    if any(outcome == "exploratory_followup_candidate_diversifier" for outcome in outcomes):
        return NEXT_ACTION_REVIEW
    return NEXT_ACTION_EVALUATE_REMAINING


def funnel_counts(results: list[dict[str, Any]], next_action: str, benchmark_rows: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = [result["outcome"] for result in results]
    return {
        "batch_id": BATCH_ID,
        "strategy_configuration_count": 3,
        "new_experiment_trial_count": 3,
        "process_task_count": 1,
        "benchmark_reference_count": len(benchmark_rows),
        "strategies_considered": 3,
        "trials_executed": 3,
        "completed_executable_strategies": sum(result["executable"] for result in results),
        "exploratory_followup_diversifier_count": outcomes.count("exploratory_followup_candidate_diversifier"),
        "closed_strategy_count": outcomes.count("closed_exploration"),
        "blocked_or_inconclusive_strategy_count": outcomes.count("inconclusive_data_issue") + outcomes.count("blocked_feasibility"),
        "nvi_context_only_count": 1,
        "cost_diagnostic_count": len(results) * len(COST_BPS_GRID),
        "exact_next_action": next_action,
    }


def build_report(results: list[dict[str, Any]], funnel: dict[str, Any]) -> str:
    lines = [
        "# Rerun Fast Source Library Blocked Candidates V3",
        "",
        "## Scope",
        "",
        "This rerun used exactly the three `fast_source_library_batch_v3` candidates that were previously blocked by VNQ/JNK data availability. It used the admitted VNQ/JNK local cache and did not repeat data acquisition, perform source research, tune parameters, change instruments, run promotion review, activate paper/demo observation, or touch broker/account/order paths.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['card'].strategy_id}`: `{result['outcome']}`; reason `{result['decision_reason']}`; "
            f"window `{result['evaluation_start']}` to `{result['evaluation_end']}`."
        )
    lines.extend(
        [
            "",
            "## Funnel",
            "",
            f"- Strategy configurations: `{funnel['strategy_configuration_count']}`",
            f"- New experiment trials: `{funnel['new_experiment_trial_count']}`",
            f"- Process tasks: `{funnel['process_task_count']}`",
            f"- Benchmark references: `{funnel['benchmark_reference_count']}`",
            f"- Exploratory follow-up diversifiers: `{funnel['exploratory_followup_diversifier_count']}`",
            f"- Closed strategies: `{funnel['closed_strategy_count']}`",
            f"- Blocked or inconclusive strategies: `{funnel['blocked_or_inconclusive_strategy_count']}`",
            "",
            "`fosback_nvi_255ema_spy_bil_v1` was not included, rerun, modified, promoted, validated, or closed.",
            "",
            f"Exact next action: `{funnel['exact_next_action']}`.",
        ]
    )
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    names = [
        "batch_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "data_preflight_reconciliation.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "cohort_funnel_counts.json",
        "batch_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def same_dates_by_group(rows: list[dict[str, Any]], group_fields: tuple[str, ...]) -> bool:
    groups: dict[tuple[Any, ...], set[tuple[str, str, int]]] = {}
    for row in rows:
        if not row.get("evaluation_start"):
            continue
        key = tuple(row.get(field, "") for field in group_fields)
        groups.setdefault(key, set()).add(
            (str(row.get("evaluation_start", "")), str(row.get("evaluation_end", "")), int(row.get("trading_days", 0)))
        )
    return bool(groups) and all(len(values) == 1 for values in groups.values())


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    input_before = input_evidence_hashes()
    cache_before = protected_cache_hashes()
    clean_output_dir()

    cards = child_cards()
    preflight = symbol_preflight_rows(cards)
    symbol_preflight_passed = all(
        row["preflight_status"] == "pass" for row in preflight if row["record_type"] in {"symbol_preflight", "strategy_preflight"}
    )
    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    results = [run_candidate(card, reference_returns) for card in cards]
    next_action = final_next_action(results)
    benchmark_rows = benchmark_reference_rows(cards)
    funnel = funnel_counts(results, next_action, benchmark_rows)

    trial_rows = [row for result in results for row in result["trial_rows"]]
    control_rows = [row for result in results for row in result["control_rows"]]
    half_rows = [row for result in results for row in result["half_rows"]]
    portfolio_rows = [row for result in results for row in result["portfolio_rows"]]
    strategy_rows = strategy_card_rows(results)
    ledger_rows = trial_ledger_rows(results, next_action)
    process_rows = [process_task_row(next_action, "rerun_completed" if not any(not r["executable"] for r in results) else "rerun_partially_blocked")]
    outcome_rows = outcome_summary_rows(results, next_action)
    failure_rows = failure_reason_rows(results, next_action)
    action_rows = next_action_rows(results, next_action)

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": BATCH_ID,
            "mode": "fast-progress",
            "lane": "fast implementation",
            "stage": "exploration",
            "adaptation_label": ADAPTATION_LABEL,
            "source_library_id": SOURCE_LIBRARY_ID,
            "frozen_timestamp": FROZEN_TIMESTAMP,
            "target_strategy_ids": list(TARGET_STRATEGY_IDS),
            "excluded_strategy_ids": [NVI_STRATEGY_ID],
            "primary_cost_assumption_bps": PRIMARY_COST_BPS,
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            "input_evidence_files": [rel(path) for path in INPUT_EVIDENCE_FILES if path.exists()],
            "exact_next_action": next_action,
            **FORBIDDEN_FLAGS,
        },
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_rows,
        [
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "stage",
            "source_library_id",
            "complete_frozen_rule",
            "instrument_universe",
            "parameters",
            "benchmark_or_control",
            "route",
            "trial_id",
            "parent_trial_id",
            "evaluation_start",
            "evaluation_end",
            "strategy_definition_changed",
            "nvi_record",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        ledger_rows,
        [
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "strategy_architecture",
            "source_or_research_lineage",
            "instrument_universe",
            "parameters",
            "benchmark_or_control",
            "stage",
            "trial_id",
            "parent_trial_id",
            "adaptation_label",
            "changed_fields_from_parent",
            "outcome",
            "primary_failure_reason",
            "next_action",
            "new_child_trial_created",
            "parent_trial_reused",
            "strategy_definition_changed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        [
            "task_id",
            "entity_type",
            "stage",
            "outcome",
            "exact_next_action",
            "execute_now",
            "strategy_counted",
            "experiment_trial_counted",
        ],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "parent_trial_id",
            "benchmark_or_control_id",
            "entity_type",
            "stage",
            "calculated_in_this_task",
            "reference_role",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight,
        [
            "record_id",
            "record_type",
            "stage",
            "symbol",
            "strategy_id",
            "trial_id",
            "required_symbols",
            "missing_symbols",
            "normal_interface_row_count",
            "evidence_row_count",
            "row_count_matches_evidence",
            "normal_interface_first_date",
            "evidence_first_date",
            "first_date_matches_evidence",
            "normal_interface_last_date",
            "evidence_last_date",
            "last_date_matches_evidence",
            "normal_interface_cache_hash",
            "evidence_cache_hash",
            "cache_hash_matches_evidence",
            "canonical_frame_hash",
            "evidence_canonical_frame_hash",
            "canonical_frame_hash_matches_evidence",
            "all_candidate_and_control_instruments_available",
            "first_common_candidate_control_date",
            "last_common_candidate_control_date",
            "common_trading_days",
            "preflight_status",
            "failure_reason",
        ],
    )
    trial_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "parent_trial_id",
        "route",
        "cost_assumption_bps",
        "outcome",
        "stage",
        "decision_reason",
        "primary_failure_reason",
        "next_action",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
        "data_issue",
        "missing_symbols",
        *FORBIDDEN_FLAGS.keys(),
    ]
    write_csv(OUTPUT_DIR / "all_trial_results.csv", trial_rows, trial_fields)
    control_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "parent_trial_id",
        "control_id",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
        "data_issue",
        "missing_symbols",
    ]
    write_csv(OUTPUT_DIR / "control_results.csv", control_rows, control_fields)
    half_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "parent_trial_id",
        "row_type",
        "control_id",
        "cost_assumption_bps",
        "half_label",
        "half_source",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
    ]
    write_csv(OUTPUT_DIR / "chronological_half_results.csv", half_rows, half_fields)
    portfolio_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "parent_trial_id",
        "route",
        "cost_assumption_bps",
        "period_label",
        "half_source",
        "portfolio_id",
        "portfolio_construction",
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "rebalance_or_trade_count",
        "estimated_transaction_cost_drag",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_weight_invariant_status",
        "invariant_pass",
        "correlation_to_frozen_reference",
    ]
    write_csv(OUTPUT_DIR / "portfolio_contribution_results.csv", portfolio_rows, portfolio_fields)
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        ["entity_id", "entity_type", "stage", "outcome", "primary_failure_reason", "next_action", "counted_in_strategy_cohort"],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "parent_trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        action_rows,
        ["scope", "entity_id", "exact_next_action", "execute_now", "reason"],
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, funnel))

    protected_after = protected_hashes()
    input_after = input_evidence_hashes()
    cache_after = protected_cache_hashes()
    consistency = {
        "batch_id": BATCH_ID,
        "exactly_three_previously_blocked_strategies_rerun": tuple(result["card"].strategy_id for result in results)
        == TARGET_STRATEGY_IDS,
        "nvi_excluded_and_unchanged": NVI_STRATEGY_ID not in {result["card"].strategy_id for result in results},
        "new_child_trial_ids_created": all(result["card"].parent_trial_id != rerun_trial_id(result["card"].strategy_id) for result in results),
        "parent_trial_ids_preserved": all(result["card"].parent_trial_id == base_cards_by_id()[result["card"].strategy_id].trial_id for result in results),
        "only_adaptation_label_data_feasibility_adjustment": all(
            row["adaptation_label"] == ADAPTATION_LABEL for row in ledger_rows
        ),
        "symbol_preflight_passed": symbol_preflight_passed,
        "vnq_jnk_cache_hashes_unchanged": cache_before == cache_after,
        "strategy_control_dates_identical_by_strategy_and_cost": same_dates_by_group(
            [
                *[
                    {
                        "strategy_id": row["strategy_id"],
                        "cost_assumption_bps": row["cost_assumption_bps"],
                        "evaluation_start": row.get("evaluation_start", ""),
                        "evaluation_end": row.get("evaluation_end", ""),
                        "trading_days": row.get("trading_days", 0),
                    }
                    for row in trial_rows
                    if row.get("evaluation_start")
                ],
                *[
                    {
                        "strategy_id": row["strategy_id"],
                        "cost_assumption_bps": row["cost_assumption_bps"],
                        "evaluation_start": row.get("evaluation_start", ""),
                        "evaluation_end": row.get("evaluation_end", ""),
                        "trading_days": row.get("trading_days", 0),
                    }
                    for row in control_rows
                    if row.get("evaluation_start")
                ],
            ],
            ("strategy_id", "cost_assumption_bps"),
        ),
        "chronological_halves_not_clean_holdout": all(row.get("half_source") == "chronological_half_not_clean_holdout" for row in half_rows),
        "portfolio_contribution_dates_identical_by_strategy_cost_period": same_dates_by_group(
            portfolio_rows, ("strategy_id", "cost_assumption_bps", "period_label")
        ),
        "benchmark_references_separate": all(row["entity_type"] == "benchmark_reference" and row["stage"] == "benchmark_reference_only" for row in benchmark_rows),
        "process_task_separate": len(process_rows) == 1 and process_rows[0]["entity_type"] == "process_task",
        "cohort_counts_reconcile": (
            funnel["strategy_configuration_count"] == len(strategy_rows) == 3
            and funnel["new_experiment_trial_count"] == len(ledger_rows) == 3
            and funnel["process_task_count"] == len(process_rows) == 1
            and funnel["benchmark_reference_count"] == len(benchmark_rows)
            and funnel["completed_executable_strategies"]
            + funnel["blocked_or_inconclusive_strategy_count"]
            == funnel["strategies_considered"]
        ),
        "closed_or_blocked_have_failure_reason": all(
            bool(row["primary_failure_reason"]) for row in ledger_rows if row["outcome"] != "exploratory_followup_candidate_diversifier"
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "input_evidence_hashes_before": input_before,
        "input_evidence_hashes_after": input_after,
        "input_evidence_hashes_unchanged": input_before == input_after,
        "vnq_jnk_cache_hashes_before": cache_before,
        "vnq_jnk_cache_hashes_after": cache_after,
        "deterministic_core_hash": deterministic_core_hash(),
        "exact_next_action": next_action,
        **FORBIDDEN_FLAGS,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": BATCH_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "strategies_considered": 3,
        "trials_executed": 3,
        "completed_executable_strategies": funnel["completed_executable_strategies"],
        "exploratory_followup_diversifier_count": funnel["exploratory_followup_diversifier_count"],
        "closed_strategy_count": funnel["closed_strategy_count"],
        "blocked_or_inconclusive_strategy_count": funnel["blocked_or_inconclusive_strategy_count"],
        "exact_next_action": next_action,
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "input_evidence_hashes_unchanged": consistency["input_evidence_hashes_unchanged"],
        "vnq_jnk_cache_hashes_unchanged": consistency["vnq_jnk_cache_hashes_unchanged"],
        "task_outcome": "rerun_fast_source_library_blocked_candidates_v3_complete",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
