from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior
from strategy_lab.research_os.research import fast_source_library_remaining_candidates_batch_v4 as parent


VALIDATION_ID = "hrp_incremental_diversifier_validation_v1"
OUTPUT_DIR = ROOT / "evidence" / "validation" / VALIDATION_ID / "latest"
PARENT_EVIDENCE_DIR = ROOT / "evidence" / "research_recovery" / "fast_source_library_remaining_candidates_batch_v4" / "latest"
STRATEGY_ID = "lopez_de_prado_hrp_five_asset_v1"
FAMILY_ID = "hierarchical_risk_parity_allocation"
DISPLAY_NAME = "Five-Asset Hierarchical Risk Parity"
PARENT_TRIAL_ID = "fast_source_v4__lopez_de_prado_hrp_five_asset_v1__canonical"
VALIDATION_TRIAL_ID = "validation_hrp__lopez_de_prado_hrp_five_asset_v1__validation_variant_child"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v1"
ADAPTATION_LABEL = "validation_variant"
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-6
SYMBOLS = ("SPY", "EEM", "IEF", "DBC", "VNQ")
ADDITIONAL_SYMBOLS = ("BIL",)

EXISTING_CONTROL_IDS = (
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
)
VALIDATION_CONTROL_IDS = (
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "static_initial_hrp_weight_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
)
STANDALONE_ENTITY_IDS = (
    "HRP",
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "static_initial_hrp_weight_control",
    "IEF_buy_hold",
    "BIL_cash_proxy",
)
PORTFOLIO_IDS = (
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "monthly_equal_weight_same_five_etfs_20pct_control",
    "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
    "static_initial_hrp_weight_control_20pct_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
)
NEXT_ACTION_BY_OUTCOME = {
    "validation_positive": "direction_owner_review_hrp_paper_demo_eligibility_v1",
    "validation_mixed": "direction_owner_review_hrp_validation_mixed_v1",
    "validation_failed": "direction_owner_review_close_hrp_after_validation_v1",
    "validation_data_or_methodology_blocked": "direction_owner_review_hrp_validation_block_v1",
}
ALLOWED_OUTCOMES = set(NEXT_ACTION_BY_OUTCOME)
ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "period_instability",
    "benchmark_like_behavior",
    "cost_drag",
    "turnover_drag",
    "excess_drawdown",
    "methodology_failure",
    "data_or_comparability_failure",
    "overfit_or_unstable",
}

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
INPUT_EVIDENCE_FILES = [
    PARENT_EVIDENCE_DIR / name
    for name in [
        "strategy_cards.csv",
        "trial_ledger.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "portfolio_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "consistency_check.json",
    ]
]
PROTECTED_CACHE_PATHS = [ROOT / "data" / "cache" / f"{symbol}.csv" for symbol in (*SYMBOLS, *ADDITIONAL_SYMBOLS)]
FORBIDDEN_FLAGS = {
    "source_research_or_completion": False,
    "provider_download": False,
    "parameter_change": False,
    "alternative_lookbacks": False,
    "alternative_linkage_methods": False,
    "alternative_covariance_estimators": False,
    "alternative_universes": False,
    "performance_selected_controls": False,
    "trade_management_overlay": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "registry_cleanup": False,
    "dashboard_rebuild": False,
    "broker_account_order_paper_live_or_real_money_action": False,
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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def input_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in INPUT_EVIDENCE_FILES if path.exists()}


def cache_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_CACHE_PATHS if path.exists()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "validation" / VALIDATION_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def hrp_card() -> parent.CandidateCard:
    return next(card for card in parent.CARDS if card.strategy_id == STRATEGY_ID)


def load_parent_trial_state() -> dict[str, str]:
    rows = read_csv_rows(PARENT_EVIDENCE_DIR / "outcome_summary.csv")
    return next(row for row in rows if row.get("strategy_id") == STRATEGY_ID)


def metric_payload(payload: dict[str, Any], period_index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return parent.metric_payload(payload, period_index)


def standalone_metric_payload(
    entity_id: str,
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    metrics = metric_payload(payload, period_index)
    return {
        "entity_id": entity_id,
        "entity_type": "candidate_standalone" if entity_id == "HRP" else "control_standalone",
        **metrics,
        "rebalance_count": metrics["trade_or_rebalance_count"],
        "weight_invariant_status": "pass" if metrics["invariant_pass"] else "fail",
    }


def portfolio_metric_payload(
    portfolio_id: str,
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    metrics = metric_payload(payload, period_index)
    return {
        "portfolio_id": portfolio_id,
        "entity_id": portfolio_id,
        "entity_type": "portfolio_construction",
        "portfolio_construction": "100pct_frozen_reference"
        if portfolio_id == "frozen_reference_100pct"
        else "monthly_rebalanced_80_20",
        **metrics,
        "rebalance_count": metrics["trade_or_rebalance_count"],
        "weight_invariant_status": "pass" if metrics["invariant_pass"] else "fail",
    }


def static_initial_hrp_weights(prices: pd.DataFrame) -> tuple[dict[str, float], pd.Timestamp, str]:
    log_returns = np.log(prices[list(SYMBOLS)] / prices[list(SYMBOLS)].shift(1))
    for signal_date in parent.month_last_dates(prices.index):
        trailing = log_returns.loc[:signal_date].tail(252)
        if len(trailing) == 252 and not trailing.isna().any().any():
            weights, order = hrp_weights_and_order_from_returns(trailing)
            return weights, pd.Timestamp(signal_date), "|".join(order)
    return parent.equal_weights(SYMBOLS), pd.Timestamp(prices.index[0]), "equal_weight_fallback_no_valid_window"


def static_initial_hrp_event_weights(prices: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    weights, first_valid_signal, order = static_initial_hrp_weights(prices)
    equal = parent.equal_weights(SYMBOLS)
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for signal_date in parent.month_last_dates(prices.index):
        targets[pd.Timestamp(signal_date)] = weights if pd.Timestamp(signal_date) >= first_valid_signal else equal
    events = parent.monthly_target_events(prices.index, SYMBOLS, targets, equal)
    return events, {
        "first_valid_signal_date": first_valid_signal.date().isoformat(),
        "frozen_weights": weights,
        "frozen_cluster_order": order,
        "warmup_behavior": "monthly_equal_weight_until_first_valid_252_day_hrp_signal",
    }


def single_asset_initial_event(prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    return parent.initial_event(prices.index, {symbol: 1.0}, (symbol,))


def hrp_weights_and_order_from_returns(returns: pd.DataFrame) -> tuple[dict[str, float], list[str]]:
    if len(returns) < 252 or returns.isna().any().any():
        return parent.equal_weights(SYMBOLS), list(SYMBOLS)
    ordered = tuple(sorted(SYMBOLS))
    frozen_returns = returns[list(ordered)]
    cov = frozen_returns.cov()
    corr = frozen_returns.corr().clip(-1.0, 1.0).fillna(0.0)
    distance = np.sqrt((1.0 - corr.to_numpy(dtype=float)) / 2.0)
    np.fill_diagonal(distance, 0.0)
    try:
        condensed = squareform(distance, checks=False)
        link = linkage(condensed, method="single", optimal_ordering=False)
        order = [ordered[int(i)] for i in leaves_list(link)]
    except Exception:
        return parent.equal_weights(SYMBOLS), list(SYMBOLS)

    weights = pd.Series(1.0, index=order, dtype=float)
    clusters = [order]
    while clusters:
        next_clusters: list[list[str]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            split = len(cluster) // 2
            left = cluster[:split]
            right = cluster[split:]
            left_var = parent.cluster_variance(cov, left)
            right_var = parent.cluster_variance(cov, right)
            if not math.isfinite(left_var) or not math.isfinite(right_var) or (left_var + right_var) <= 0.0:
                alpha = 0.5
            else:
                alpha = 1.0 - left_var / (left_var + right_var)
            weights.loc[left] *= alpha
            weights.loc[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters
    weights = weights.reindex(SYMBOLS).astype(float)
    if weights.isna().any() or (weights < -WEIGHT_TOLERANCE).any() or float(weights.sum()) <= 0.0:
        return parent.equal_weights(SYMBOLS), list(SYMBOLS)
    weights = weights.clip(lower=0.0)
    weights = weights / float(weights.sum())
    return {symbol: float(weights[symbol]) for symbol in SYMBOLS}, order


def hrp_monthly_rebalance_records(prices: pd.DataFrame, hrp_payload: dict[str, Any]) -> list[dict[str, Any]]:
    log_returns = np.log(prices[list(SYMBOLS)] / prices[list(SYMBOLS)].shift(1))
    event_by_date = {pd.Timestamp(row["event_date"]): row for row in hrp_payload["event_rows"]}
    rows: list[dict[str, Any]] = []
    for signal_date in parent.month_last_dates(prices.index):
        execution_date = parent.next_session_after(prices.index, signal_date)
        if execution_date is None:
            continue
        trailing = log_returns.loc[:signal_date].tail(252)
        weights, order = hrp_weights_and_order_from_returns(trailing)
        warmup = len(trailing) < 252 or trailing.isna().any().any()
        event = event_by_date.get(pd.Timestamp(execution_date), {})
        weight_values = np.array([weights[symbol] for symbol in SYMBOLS], dtype=float)
        rows.append(
            {
                "signal_date": pd.Timestamp(signal_date).date().isoformat(),
                "execution_date": pd.Timestamp(execution_date).date().isoformat(),
                "SPY_weight": weights["SPY"],
                "EEM_weight": weights["EEM"],
                "IEF_weight": weights["IEF"],
                "DBC_weight": weights["DBC"],
                "VNQ_weight": weights["VNQ"],
                "maximum_asset_weight": float(weight_values.max()),
                "minimum_asset_weight": float(weight_values.min()),
                "effective_number_of_holdings": float(1.0 / np.square(weight_values).sum()),
                "cluster_ordering": "equal_weight_warmup" if warmup else "|".join(order),
                "warmup_equal_weight": warmup,
                "one_way_turnover": float(event.get("one_way_turnover", 0.0) or 0.0),
                "transaction_cost": float(event.get("transaction_cost_drag", 0.0) or 0.0),
            }
        )
    return rows


def hrp_weight_summary_rows(monthly_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frame = pd.DataFrame(monthly_rows)
    if frame.empty:
        return rows
    for symbol in SYMBOLS:
        col = f"{symbol}_weight"
        weights = pd.to_numeric(frame[col], errors="coerce")
        rows.append(
            {
                "summary_scope": "instrument_weight",
                "instrument": symbol,
                "average_weight": float(weights.mean()),
                "minimum_weight": float(weights.min()),
                "maximum_weight": float(weights.max()),
                "percentage_months_largest_allocation": float((frame[[f"{s}_weight" for s in SYMBOLS]].idxmax(axis=1) == col).mean()),
            }
        )
    rows.append(
        {
            "summary_scope": "portfolio_concentration",
            "instrument": "all",
            "average_weight": "",
            "minimum_weight": "",
            "maximum_weight": "",
            "percentage_months_IEF_largest_allocation": float((frame[[f"{s}_weight" for s in SYMBOLS]].idxmax(axis=1) == "IEF_weight").mean()),
            "percentage_months_any_asset_exceeds_50pct": float((frame[[f"{s}_weight" for s in SYMBOLS]] > 0.5).any(axis=1).mean()),
            "median_effective_number_of_holdings": float(pd.to_numeric(frame["effective_number_of_holdings"], errors="coerce").median()),
            "unique_cluster_ordering_count": int(frame["cluster_ordering"].nunique()),
        }
    )
    return rows


def hrp_cluster_ordering_summary_rows(monthly_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(monthly_rows)
    if frame.empty:
        return []
    counts = frame["cluster_ordering"].value_counts().sort_index()
    total = float(counts.sum())
    return [
        {
            "cluster_ordering": ordering,
            "month_count": int(count),
            "month_percentage": float(count / total) if total else 0.0,
        }
        for ordering, count in counts.items()
    ]


def prepare_validation_payloads() -> dict[str, Any]:
    preflight = {symbol: parent.data_preflight_row(symbol) for symbol in (*SYMBOLS, *ADDITIONAL_SYMBOLS)}
    missing = [symbol for symbol in SYMBOLS if preflight[symbol]["preflight_status"] != "pass"]
    if missing:
        raise RuntimeError(f"Required HRP symbols failed local preflight: {missing}")

    card = hrp_card()
    result = parent.run_candidate(card, {symbol: preflight[symbol] for symbol in SYMBOLS})
    if not result["executable"]:
        raise RuntimeError(f"Parent HRP calculation was not executable: {result['decision_reason']}")
    prices = parent.load_price_frame(SYMBOLS)
    bil_prices = parent.load_price_frame(("BIL",))
    static_events, static_info = static_initial_hrp_event_weights(prices)
    payloads: dict[str, dict[float, dict[str, Any]]] = {"HRP": {}, **{control_id: {} for control_id in VALIDATION_CONTROL_IDS}}
    payloads["IEF_buy_hold"] = {}
    payloads["BIL_cash_proxy"] = {}

    for cost_bps in COST_BPS_GRID:
        payloads["HRP"][cost_bps] = result["candidate_payloads"][cost_bps]
        for control_id in EXISTING_CONTROL_IDS:
            payloads[control_id][cost_bps] = result["control_payloads"][(control_id, cost_bps)]
        payloads["static_initial_hrp_weight_control"][cost_bps] = parent.simulate_close_to_close(
            prices[list(SYMBOLS)],
            static_events,
            cost_bps,
            "month_end_signal_next_available_session_close_execution",
        )
        payloads["IEF_single_asset_20pct_control"][cost_bps] = parent.simulate_close_to_close(
            prices[["IEF"]],
            single_asset_initial_event(prices[["IEF"]], "IEF"),
            cost_bps,
            "daily_close_to_close_buy_hold",
        )
        payloads["BIL_cash_20pct_control"][cost_bps] = parent.simulate_close_to_close(
            bil_prices[["BIL"]],
            single_asset_initial_event(bil_prices[["BIL"]], "BIL"),
            cost_bps,
            "daily_close_to_close_buy_hold",
        )
        payloads["IEF_buy_hold"][cost_bps] = payloads["IEF_single_asset_20pct_control"][cost_bps]
        payloads["BIL_cash_proxy"][cost_bps] = payloads["BIL_cash_20pct_control"][cost_bps]

    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    portfolio_payloads = build_portfolio_payloads(payloads, reference_returns)
    monthly_rows = hrp_monthly_rebalance_records(prices, payloads["HRP"][PRIMARY_COST_BPS])
    return {
        "card": card,
        "parent_result": result,
        "preflight": preflight,
        "prices": prices,
        "payloads": payloads,
        "portfolio_payloads": portfolio_payloads,
        "reference_returns": reference_returns,
        "static_info": static_info,
        "hrp_monthly_rows": monthly_rows,
    }


def build_portfolio_payloads(
    payloads: dict[str, dict[float, dict[str, Any]]],
    reference_returns: pd.Series,
) -> dict[str, dict[float, dict[str, Any]]]:
    portfolios: dict[str, dict[float, dict[str, Any]]] = {portfolio_id: {} for portfolio_id in PORTFOLIO_IDS}
    for cost_bps in COST_BPS_GRID:
        reference = reference_returns.dropna()
        portfolios["frozen_reference_100pct"][cost_bps] = parent.reference_payload(reference, cost_bps)
        portfolio_map = {
            f"{STRATEGY_ID}_candidate_20pct": payloads["HRP"][cost_bps]["returns"],
            "monthly_equal_weight_same_five_etfs_20pct_control": payloads["monthly_equal_weight_same_five_etfs"][cost_bps]["returns"],
            "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control": payloads[
                "clare_inverse_volatility_five_asset_risk_parity_v1"
            ][cost_bps]["returns"],
            "static_initial_hrp_weight_control_20pct_control": payloads["static_initial_hrp_weight_control"][cost_bps]["returns"],
            "IEF_single_asset_20pct_control": payloads["IEF_single_asset_20pct_control"][cost_bps]["returns"],
            "BIL_cash_20pct_control": payloads["BIL_cash_20pct_control"][cost_bps]["returns"],
        }
        for portfolio_id, sleeve_returns in portfolio_map.items():
            common = reference.index.intersection(sleeve_returns.dropna().index).sort_values()
            aligned_reference = reference.reindex(common).dropna()
            aligned_sleeve = sleeve_returns.reindex(aligned_reference.index).dropna()
            aligned_reference = aligned_reference.reindex(aligned_sleeve.index).dropna()
            portfolios[portfolio_id][cost_bps] = parent.simulate_two_component_portfolio(
                aligned_reference,
                aligned_sleeve,
                portfolio_id,
                cost_bps,
            )
    return portfolios


def full_period_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in STANDALONE_ENTITY_IDS:
        for cost_bps, payload in state["payloads"][entity_id].items():
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "family_id": FAMILY_ID,
                    "trial_id": VALIDATION_TRIAL_ID,
                    "stage": "validation",
                    "cost_assumption_bps": cost_bps,
                    **standalone_metric_payload(entity_id, payload),
                }
            )
    for portfolio_id in PORTFOLIO_IDS:
        for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "family_id": FAMILY_ID,
                    "trial_id": VALIDATION_TRIAL_ID,
                    "stage": "validation",
                    "cost_assumption_bps": cost_bps,
                    **portfolio_metric_payload(portfolio_id, payload),
                    "correlation_to_frozen_reference": 1.0
                    if portfolio_id == "frozen_reference_100pct"
                    else prior.safe_corr(payload["returns"], state["portfolio_payloads"]["frozen_reference_100pct"][cost_bps]["returns"]),
                }
            )
    return rows


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    return parent.split_halves(index)


def chronological_half_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_index = state["payloads"]["HRP"][PRIMARY_COST_BPS]["returns"].index
    halves = split_halves(base_index)
    for half_label, start, end in halves:
        for entity_id in STANDALONE_ENTITY_IDS:
            for cost_bps, payload in state["payloads"][entity_id].items():
                period_index = payload["returns"].index[(payload["returns"].index >= start) & (payload["returns"].index <= end)]
                if len(period_index) == 0:
                    continue
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "stage": "validation",
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **standalone_metric_payload(entity_id, payload, period_index),
                    }
                )
        for portfolio_id in PORTFOLIO_IDS:
            for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
                period_index = payload["returns"].index[(payload["returns"].index >= start) & (payload["returns"].index <= end)]
                if len(period_index) == 0:
                    continue
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "stage": "validation",
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **portfolio_metric_payload(portfolio_id, payload, period_index),
                    }
                )
    return rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return parent.month_last_dates(index)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    c_values = (float(control["cagr"]), float(control["sharpe_ratio"]), float(control["maximum_drawdown"]))
    v_values = (float(candidate["cagr"]), float(candidate["sharpe_ratio"]), float(candidate["maximum_drawdown"]))
    return all(c >= v - 1e-12 for c, v in zip(c_values, v_values)) and any(c > v + 1e-12 for c, v in zip(c_values, v_values))


def replicates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return dominates(control, candidate) or (
        abs(float(control["sharpe_ratio"]) - float(candidate["sharpe_ratio"])) <= 0.01
        and float(control["cagr"]) >= float(candidate["cagr"]) - 1e-12
        and float(control["maximum_drawdown"]) >= float(candidate["maximum_drawdown"]) - 1e-12
    )


def rolling_rows(state: dict[str, Any], months: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate_id = f"{STRATEGY_ID}_candidate_20pct"
    control_ids = tuple(pid for pid in PORTFOLIO_IDS if pid not in {"frozen_reference_100pct", candidate_id})
    for cost_bps in COST_BPS_GRID:
        candidate = state["portfolio_payloads"][candidate_id][cost_bps]["returns"].dropna()
        for end_date in month_end_dates(candidate.index):
            cutoff = pd.Timestamp(end_date) - pd.DateOffset(months=months)
            if cutoff < candidate.index.min():
                continue
            window_index = candidate.index[(candidate.index >= cutoff) & (candidate.index <= end_date)]
            if len(window_index) == 0:
                continue
            candidate_returns = candidate.reindex(window_index).dropna()
            for control_id in control_ids:
                control_returns = state["portfolio_payloads"][control_id][cost_bps]["returns"].reindex(candidate_returns.index).dropna()
                aligned_candidate = candidate_returns.reindex(control_returns.index).dropna()
                if aligned_candidate.empty:
                    continue
                candidate_metrics = metric_payload(state["portfolio_payloads"][candidate_id][cost_bps], aligned_candidate.index)
                control_metrics = metric_payload(state["portfolio_payloads"][control_id][cost_bps], aligned_candidate.index)
                dominated = dominates(control_metrics, candidate_metrics)
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "window_months": months,
                        "window_start": aligned_candidate.index.min().date().isoformat(),
                        "window_end": aligned_candidate.index.max().date().isoformat(),
                        "trading_days": int(len(aligned_candidate)),
                        "cost_assumption_bps": cost_bps,
                        "candidate_portfolio_id": candidate_id,
                        "control_portfolio_id": control_id,
                        "candidate_total_return": candidate_metrics["total_return"],
                        "candidate_cagr": candidate_metrics["cagr"],
                        "candidate_annualized_volatility": candidate_metrics["annualized_volatility"],
                        "candidate_sharpe_ratio": candidate_metrics["sharpe_ratio"],
                        "candidate_maximum_drawdown": candidate_metrics["maximum_drawdown"],
                        "control_total_return": control_metrics["total_return"],
                        "control_cagr": control_metrics["cagr"],
                        "control_annualized_volatility": control_metrics["annualized_volatility"],
                        "control_sharpe_ratio": control_metrics["sharpe_ratio"],
                        "control_maximum_drawdown": control_metrics["maximum_drawdown"],
                        "cagr_difference": float(candidate_metrics["cagr"]) - float(control_metrics["cagr"]),
                        "sharpe_ratio_difference": float(candidate_metrics["sharpe_ratio"]) - float(control_metrics["sharpe_ratio"]),
                        "maximum_drawdown_difference": float(candidate_metrics["maximum_drawdown"]) - float(control_metrics["maximum_drawdown"]),
                        "annualized_volatility_difference": float(candidate_metrics["annualized_volatility"])
                        - float(control_metrics["annualized_volatility"]),
                        "control_dominates_hrp": dominated,
                        "turnover": candidate_metrics["turnover"],
                        "rebalance_count": candidate_metrics["trade_or_rebalance_count"],
                        "transaction_cost_drag": candidate_metrics["transaction_cost_drag"],
                        "max_daily_exposure": candidate_metrics["max_daily_exposure"],
                        "max_daily_weight_sum": candidate_metrics["max_daily_weight_sum"],
                        "timing_invariant_status": candidate_metrics["timing_invariant_status"],
                        "numeric_invariant_status": candidate_metrics["numeric_invariant_status"],
                        "exposure_invariant_status": candidate_metrics["exposure_invariant_status"],
                        "weight_invariant_status": "pass" if candidate_metrics["invariant_pass"] else "fail",
                        "invariant_pass": candidate_metrics["invariant_pass"],
                    }
                )
    return rows


def rolling_summary_rows(rows_36: list[dict[str, Any]], rows_60: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for months, source_rows in ((36, rows_36), (60, rows_60)):
        for cost_bps in COST_BPS_GRID:
            cost_rows = [row for row in source_rows if float(row["cost_assumption_bps"]) == cost_bps]
            by_window: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cost_rows:
                by_window.setdefault((row["window_start"], row["window_end"]), []).append(row)
            best_sharpe_diffs: list[float] = []
            best_drawdown_diffs: list[float] = []
            dominated_windows = 0
            for window_rows in by_window.values():
                best_sharpe = max(window_rows, key=lambda row: float(row["control_sharpe_ratio"]))
                best_drawdown = max(window_rows, key=lambda row: float(row["control_maximum_drawdown"]))
                best_sharpe_diffs.append(float(best_sharpe["sharpe_ratio_difference"]))
                best_drawdown_diffs.append(float(best_drawdown["maximum_drawdown_difference"]))
                if any(row["control_dominates_hrp"] for row in window_rows):
                    dominated_windows += 1
            count = len(by_window)
            rows.append(
                {
                    "window_months": months,
                    "cost_assumption_bps": cost_bps,
                    "window_count": count,
                    "median_sharpe_difference_vs_best_control": float(pd.Series(best_sharpe_diffs).median()) if best_sharpe_diffs else "",
                    "median_maximum_drawdown_difference_vs_best_control": float(pd.Series(best_drawdown_diffs).median())
                    if best_drawdown_diffs
                    else "",
                    "positive_sharpe_difference_count": int(sum(value > 0.0 for value in best_sharpe_diffs)),
                    "positive_sharpe_difference_pct": float(sum(value > 0.0 for value in best_sharpe_diffs) / count) if count else "",
                    "control_dominated_window_count": dominated_windows,
                    "control_dominated_window_pct": float(dominated_windows / count) if count else "",
                }
            )
    return rows


def calendar_year_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in STANDALONE_ENTITY_IDS:
        for cost_bps, payload in state["payloads"][entity_id].items():
            for year, year_returns in payload["returns"].groupby(payload["returns"].index.year):
                period_index = year_returns.index
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "calendar_year": int(year),
                        "cost_assumption_bps": cost_bps,
                        **standalone_metric_payload(entity_id, payload, period_index),
                    }
                )
    for portfolio_id in PORTFOLIO_IDS:
        for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
            for year, year_returns in payload["returns"].groupby(payload["returns"].index.year):
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "calendar_year": int(year),
                        "cost_assumption_bps": cost_bps,
                        **portfolio_metric_payload(portfolio_id, payload, year_returns.index),
                    }
                )
    return rows


def portfolio_contribution_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
            for period_label, period_index in [
                ("full_period", payload["returns"].index),
                *[
                    (
                        label,
                        payload["returns"].index[(payload["returns"].index >= start) & (payload["returns"].index <= end)],
                    )
                    for label, start, end in split_halves(payload["returns"].index)
                ],
            ]:
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": "100pct_frozen_reference"
                        if portfolio_id == "frozen_reference_100pct"
                        else "monthly_rebalanced_80_20",
                        "period_label": period_label,
                        "half_source": "" if period_label == "full_period" else "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **portfolio_metric_payload(portfolio_id, payload, period_index),
                        "correlation_to_frozen_reference": 1.0
                        if portfolio_id == "frozen_reference_100pct"
                        else prior.safe_corr(
                            payload["returns"].reindex(period_index),
                            state["portfolio_payloads"]["frozen_reference_100pct"][cost_bps]["returns"].reindex(period_index),
                        ),
                    }
                )
    return rows


def portfolio_rebalance_event_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
            for event in payload["event_rows"]:
                rows.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "family_id": FAMILY_ID,
                        "trial_id": VALIDATION_TRIAL_ID,
                        "portfolio_id": portfolio_id,
                        "cost_assumption_bps": cost_bps,
                        **event,
                    }
                )
    return rows


def turnover_cost_reconciliation_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in STANDALONE_ENTITY_IDS:
        for cost_bps, payload in state["payloads"][entity_id].items():
            metrics = metric_payload(payload)
            rows.append(
                {
                    "record_scope": "standalone",
                    "entity_id": entity_id,
                    "portfolio_id": "",
                    "cost_assumption_bps": cost_bps,
                    "total_one_way_turnover": metrics["turnover"],
                    "rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "rebalance_policy": "frozen_standalone_rule",
                }
            )
    for portfolio_id in PORTFOLIO_IDS:
        for cost_bps, payload in state["portfolio_payloads"][portfolio_id].items():
            metrics = metric_payload(payload)
            rows.append(
                {
                    "record_scope": "portfolio_contribution",
                    "entity_id": portfolio_id,
                    "portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost_bps,
                    "total_one_way_turnover": metrics["turnover"],
                    "rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "rebalance_policy": "reference_only_no_task_turnover"
                    if portfolio_id == "frozen_reference_100pct"
                    else "monthly_rebalanced_80_20_with_natural_drift",
                }
            )
    return rows


def parent_prior_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(PARENT_EVIDENCE_DIR / "all_trial_results.csv"):
        if row.get("strategy_id") == STRATEGY_ID and row.get("cost_assumption_bps") == "5":
            lookup["HRP"] = row
    for row in read_csv_rows(PARENT_EVIDENCE_DIR / "control_results.csv"):
        if row.get("strategy_id") == STRATEGY_ID and row.get("cost_assumption_bps") == "5":
            lookup[row["control_id"]] = row
    for row in read_csv_rows(PARENT_EVIDENCE_DIR / "portfolio_contribution_results.csv"):
        if row.get("strategy_id") == STRATEGY_ID and row.get("cost_assumption_bps") == "5" and row.get("period_label") == "full_period":
            lookup[row["portfolio_id"]] = row
    return lookup


def reproduction_rows(full_rows: list[dict[str, Any]], portfolio_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prior_lookup = parent_prior_lookup()
    current_lookup: dict[str, dict[str, Any]] = {}
    for row in full_rows:
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS and row["entity_id"] in {"HRP", *EXISTING_CONTROL_IDS}:
            current_lookup[row["entity_id"]] = row
    for row in portfolio_rows:
        if (
            row.get("period_label") == "full_period"
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
            and row["portfolio_id"]
            in {
            "frozen_reference_100pct",
            f"{STRATEGY_ID}_candidate_20pct",
            "monthly_equal_weight_same_five_etfs_20pct_control",
            "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
            }
        ):
            current_lookup[row["portfolio_id"]] = row
    metric_fields = [
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "transaction_cost_drag",
    ]
    rows: list[dict[str, Any]] = []
    for entity_id in (
        "HRP",
        "monthly_equal_weight_same_five_etfs",
        "clare_inverse_volatility_five_asset_risk_parity_v1",
        "frozen_reference_100pct",
        f"{STRATEGY_ID}_candidate_20pct",
        "monthly_equal_weight_same_five_etfs_20pct_control",
        "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
    ):
        prior_row = prior_lookup.get(entity_id, {})
        current_row = current_lookup.get(entity_id, {})
        for metric in metric_fields:
            if metric not in prior_row or prior_row.get(metric, "") == "":
                continue
            previous = float(prior_row.get(metric, "nan"))
            current = float(current_row.get(metric, "nan")) if current_row.get(metric, "") != "" else float("nan")
            diff = current - previous if math.isfinite(current) and math.isfinite(previous) else float("nan")
            rows.append(
                {
                    "entity_id": entity_id,
                    "metric": metric,
                    "prior_value": previous,
                    "recomputed_value": current,
                    "absolute_difference": abs(diff) if math.isfinite(diff) else "",
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "reproduction_status": "pass" if math.isfinite(diff) and abs(diff) <= REPRODUCTION_TOLERANCE else "fail",
                }
            )
    return rows


def primary_portfolio_metrics(portfolio_rows: list[dict[str, Any]], cost_bps: float = PRIMARY_COST_BPS) -> dict[str, dict[str, Any]]:
    return {
        row["portfolio_id"]: row
        for row in portfolio_rows
        if row.get("period_label", "full_period") == "full_period" and float(row["cost_assumption_bps"]) == cost_bps
    }


def half_metric_lookup(half_rows: list[dict[str, Any]], cost_bps: float = PRIMARY_COST_BPS) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["entity_id"], row["half_label"]): row
        for row in half_rows
        if row["entity_type"] == "portfolio_construction" and float(row["cost_assumption_bps"]) == cost_bps
    }


def rolling_summary_lookup(rows: list[dict[str, Any]], cost_bps: float) -> dict[int, dict[str, Any]]:
    return {int(row["window_months"]): row for row in rows if float(row["cost_assumption_bps"]) == cost_bps}


def validation_decision(
    reproduction: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    reproduction_pass = all(row["reproduction_status"] == "pass" for row in reproduction)
    invariants_pass = all(row.get("invariant_pass") is True for row in full_rows if row.get("invariant_pass") != "")
    if not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "data_or_comparability_failure",
            "reproduction_gate_failed",
            {"reproduction_pass": False, "invariants_pass": invariants_pass},
        )
    if not invariants_pass:
        return (
            "validation_data_or_methodology_blocked",
            "methodology_failure",
            "numeric_timing_weight_or_exposure_invariant_failed",
            {"reproduction_pass": True, "invariants_pass": False},
        )

    portfolio_5 = primary_portfolio_metrics([row for row in full_rows if row["entity_type"] == "portfolio_construction"], 5.0)
    candidate_id = f"{STRATEGY_ID}_candidate_20pct"
    candidate = portfolio_5[candidate_id]
    control_ids = tuple(pid for pid in PORTFOLIO_IDS if pid not in {"frozen_reference_100pct", candidate_id})
    controls = {pid: portfolio_5[pid] for pid in control_ids}
    simple_controls = {pid: controls[pid] for pid in ("IEF_single_asset_20pct_control", "BIL_cash_20pct_control")}
    static_control = controls["static_initial_hrp_weight_control_20pct_control"]
    algorithmic_controls = {
        pid: controls[pid]
        for pid in (
            "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
            "static_initial_hrp_weight_control_20pct_control",
        )
    }

    control_dominates = {pid: dominates(metrics, candidate) for pid, metrics in controls.items()}
    simple_replicates = {pid: replicates(metrics, candidate) for pid, metrics in simple_controls.items()}
    static_replicates = replicates(static_control, candidate)
    best_sharpe_control = max(controls.items(), key=lambda item: float(item[1]["sharpe_ratio"]))
    best_drawdown_control = max(controls.items(), key=lambda item: float(item[1]["maximum_drawdown"]))
    full_best_sharpe_diff = float(candidate["sharpe_ratio"]) - float(best_sharpe_control[1]["sharpe_ratio"])
    full_best_drawdown_diff = float(candidate["maximum_drawdown"]) - float(best_drawdown_control[1]["maximum_drawdown"])
    full_favorable = (
        not any(control_dominates.values())
        and (float(candidate["sharpe_ratio"]) > float(portfolio_5["frozen_reference_100pct"]["sharpe_ratio"])
             or float(candidate["maximum_drawdown"]) > float(portfolio_5["frozen_reference_100pct"]["maximum_drawdown"]))
    )
    algorithmic_advantage = {
        pid: (
            float(candidate["sharpe_ratio"]) - float(metrics["sharpe_ratio"]) >= 0.02
            or float(candidate["maximum_drawdown"]) - float(metrics["maximum_drawdown"]) >= 0.01
        )
        for pid, metrics in algorithmic_controls.items()
    }

    halves = half_metric_lookup(half_rows, 5.0)
    half_worse_both = {}
    for half_label in ("first_chronological_half", "second_chronological_half"):
        cand_half = halves[(candidate_id, half_label)]
        best_half_control = max((halves[(pid, half_label)] for pid in control_ids), key=lambda row: float(row["sharpe_ratio"]))
        half_worse_both[half_label] = (
            float(cand_half["sharpe_ratio"]) < float(best_half_control["sharpe_ratio"])
            and float(cand_half["maximum_drawdown"]) < float(best_half_control["maximum_drawdown"])
        )

    summary_5 = rolling_summary_lookup(rolling_summary, 5.0)
    summary_10 = rolling_summary_lookup(rolling_summary, 10.0)
    rolling_36_pass = (
        float(summary_5[36]["median_sharpe_difference_vs_best_control"]) > 0.0
        or float(summary_5[36]["median_maximum_drawdown_difference_vs_best_control"]) >= 0.005
    )
    rolling_60_pass = (
        float(summary_5[60]["median_sharpe_difference_vs_best_control"]) > 0.0
        or float(summary_5[60]["median_maximum_drawdown_difference_vs_best_control"]) >= 0.005
    )
    rolling_36_dominated_pct = float(summary_5[36]["control_dominated_window_pct"])
    rolling_60_dominated_pct = float(summary_5[60]["control_dominated_window_pct"])
    dominated_both_rolling_majority = rolling_36_dominated_pct >= 0.5 and rolling_60_dominated_pct >= 0.5
    both_rolling_no_advantage = not rolling_36_pass and not rolling_60_pass
    ten_bps_survives = (
        float(summary_10[36]["median_sharpe_difference_vs_best_control"]) > 0.0
        or float(summary_10[36]["median_maximum_drawdown_difference_vs_best_control"]) >= 0.0
        or float(summary_10[60]["median_sharpe_difference_vs_best_control"]) > 0.0
        or float(summary_10[60]["median_maximum_drawdown_difference_vs_best_control"]) >= 0.0
    )

    diagnostics = {
        "reproduction_pass": reproduction_pass,
        "invariants_pass": invariants_pass,
        "full_favorable": full_favorable,
        "control_dominates_full_period": control_dominates,
        "simple_controls_replicate": simple_replicates,
        "static_initial_hrp_replicates": static_replicates,
        "algorithmic_control_advantage": algorithmic_advantage,
        "half_worse_than_best_control_on_both_sharpe_and_drawdown": half_worse_both,
        "median_rolling_36_sharpe_difference_vs_best_control": summary_5[36]["median_sharpe_difference_vs_best_control"],
        "median_rolling_60_sharpe_difference_vs_best_control": summary_5[60]["median_sharpe_difference_vs_best_control"],
        "median_rolling_36_max_drawdown_difference_vs_best_control": summary_5[36][
            "median_maximum_drawdown_difference_vs_best_control"
        ],
        "median_rolling_60_max_drawdown_difference_vs_best_control": summary_5[60][
            "median_maximum_drawdown_difference_vs_best_control"
        ],
        "rolling_36_dominated_pct": rolling_36_dominated_pct,
        "rolling_60_dominated_pct": rolling_60_dominated_pct,
        "full_best_sharpe_diff": full_best_sharpe_diff,
        "full_best_drawdown_diff": full_best_drawdown_diff,
        "ten_bps_survives_without_both_signs_turning_unfavorable": ten_bps_survives,
    }

    if any(simple_replicates.values()):
        return "validation_failed", "benchmark_like_behavior", "IEF_or_BIL_economically_replicates_HRP_contribution", diagnostics
    if static_replicates:
        return "validation_failed", "benchmark_like_behavior", "static_initial_hrp_control_replicates_or_exceeds_dynamic_HRP", diagnostics
    if any(control_dominates.values()):
        return "validation_failed", "weak_vs_primary_control", "control_dominates_HRP_on_full_period_80_20", diagnostics
    if dominated_both_rolling_majority:
        return "validation_failed", "period_instability", "HRP_dominated_in_at_least_50pct_of_both_rolling_window_sets", diagnostics
    if both_rolling_no_advantage:
        return "validation_failed", "period_instability", "rolling_windows_show_no_median_sharpe_or_drawdown_advantage", diagnostics
    if not ten_bps_survives:
        return "validation_failed", "cost_drag", "effect_disappears_under_10bps_diagnostic", diagnostics

    positive = (
        full_favorable
        and all(algorithmic_advantage.values())
        and not any(half_worse_both.values())
        and rolling_36_pass
        and rolling_60_pass
        and rolling_36_dominated_pct <= 0.5
        and rolling_60_dominated_pct <= 0.5
        and ten_bps_survives
    )
    if positive:
        return "validation_positive", "", "validation_positive_requirements_satisfied", diagnostics
    if full_favorable:
        return "validation_mixed", "period_instability", "full_period_favorable_but_validation_diagnostics_conflicting", diagnostics
    return "validation_failed", "weak_vs_primary_control", "full_period_HRP_result_not_favorable_after_validation_controls", diagnostics


def strategy_card_row(outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": "hierarchical_risk_based_multi_asset_allocation",
        "source_or_research_lineage": "strategy_source_library_refresh_v1__lopez_de_prado_hrp",
        "instrument_universe": SYMBOLS,
        "parameters": {
            "lookback_trading_days": 252,
            "return_type": "daily_log_return",
            "covariance_estimator": "sample_covariance",
            "distance_formula": "sqrt((1-rho)/2)",
            "linkage_method": "single",
            "tie_break": "lexical_ticker_order",
            "rebalance_frequency": "monthly",
            "warmup_rule": "equal_weights_before_252_observations",
        },
        "benchmark_or_control": ("frozen_current_active_vm_dsr_usci_combo", *VALIDATION_CONTROL_IDS),
        "stage": "validation",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "next_action": next_action,
    }


def trial_ledger_row(outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "experiment_trial",
        "stage": "validation",
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "source_library_id": SOURCE_LIBRARY_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "changed_fields_from_parent": "validation_diagnostics_and_predeclared_simple_controls_only",
        "strategy_definition_changed": False,
        "hrp_strategy_definition_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "universe_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "new_validation_controls_added": True,
        "timeframe_selected_from_results": False,
        "transaction_cost_assumptions": "5 bps primary; 0 and 10 bps fixed diagnostics",
        "execution_timing": "month_end_signal_next_available_session_close_execution",
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_reference_rows() -> list[dict[str, Any]]:
    rows = [
        ("frozen_current_active_vm_dsr_usci_combo", "portfolio_contribution_reference_only"),
        ("monthly_equal_weight_same_five_etfs", "same_purpose_control"),
        ("clare_inverse_volatility_five_asset_risk_parity_v1", "same_purpose_control_benchmark_only"),
        ("static_initial_hrp_weight_control", "validation_diagnostic_control"),
        ("IEF_single_asset_20pct_control", "validation_simple_exposure_control"),
        ("BIL_cash_20pct_control", "validation_simple_derisking_control"),
    ]
    return [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": VALIDATION_TRIAL_ID,
            "benchmark_or_control_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "reference_role": role,
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "counted_as_observation": False,
        }
        for control_id, role in rows
    ]


def process_task_row(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": VALIDATION_ID,
        "entity_type": "process_task",
        "stage": "validation",
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
    }


def outcome_summary_row(outcome: str, failure_reason: str, decision_reason: str, next_action: str, diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": VALIDATION_TRIAL_ID,
        "stage": "validation",
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "next_action": next_action,
        "reproduction_passed": diagnostics.get("reproduction_pass", False),
        "invariants_passed": diagnostics.get("invariants_pass", False),
        "full_favorable": diagnostics.get("full_favorable", False),
        "static_initial_hrp_replicates": diagnostics.get("static_initial_hrp_replicates", False),
        "simple_controls_replicate": diagnostics.get("simple_controls_replicate", diagnostics.get("simple_controls_replicate", "")),
    }


def failure_reason_rows(outcome: str, failure_reason: str, decision_reason: str) -> list[dict[str, Any]]:
    if not failure_reason:
        return []
    return [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": VALIDATION_TRIAL_ID,
            "stage": "validation",
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "decision_reason": decision_reason,
        }
    ]


def next_action_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "scope": "strategy",
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_now": False,
        },
        {
            "scope": "validation_task",
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_now": False,
        },
    ]


def deterministic_core_hash(
    outcome: str,
    full_rows: list[dict[str, Any]],
    portfolio_rows: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    monthly_rows: list[dict[str, Any]],
) -> str:
    payload = {
        "outcome": outcome,
        "full_rows": full_rows,
        "portfolio_rows": portfolio_rows,
        "rolling_summary": rolling_summary,
        "monthly_rows": monthly_rows,
    }
    text = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_report(
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    next_action: str,
    diagnostics: dict[str, Any],
    static_info: dict[str, Any],
) -> str:
    lines = [
        "# HRP Incremental Diversifier Validation V1",
        "",
        f"Strategy: `{STRATEGY_ID}`",
        f"Parent exploratory trial: `{PARENT_TRIAL_ID}`",
        f"Validation child trial: `{VALIDATION_TRIAL_ID}`",
        f"Outcome: `{outcome}`",
        f"Primary failure reason: `{failure_reason}`" if failure_reason else "Primary failure reason: none",
        f"Decision reason: `{decision_reason}`",
        "",
        "The HRP strategy definition, universe, 252-day log-return lookback, sample covariance, single-linkage method, lexical tie rule, monthly rebalance cadence, and next-session-close execution convention were kept frozen.",
        "",
        "The reproduction gate compares the recomputed 5 bps parent HRP, equal-weight, inverse-volatility, frozen reference, and original 80/20 portfolio rows against the v4 exploratory evidence.",
        "",
        "Additional validation controls are benchmark references only: static initial-HRP weights, an IEF sleeve, and a BIL sleeve. They do not create new strategy trials.",
        "",
        f"Static initial-HRP first valid signal date: `{static_info['first_valid_signal_date']}`",
        f"Static initial-HRP frozen cluster order: `{static_info['frozen_cluster_order']}`",
        "",
        "Decision diagnostics:",
        f"- Reproduction passed: `{diagnostics.get('reproduction_pass')}`",
        f"- Invariants passed: `{diagnostics.get('invariants_pass')}`",
        f"- Full-period favorable: `{diagnostics.get('full_favorable')}`",
        f"- Static initial-HRP replicates: `{diagnostics.get('static_initial_hrp_replicates')}`",
        f"- Simple controls replicate: `{diagnostics.get('simple_controls_replicate')}`",
        f"- Rolling 36 dominated pct: `{diagnostics.get('rolling_36_dominated_pct')}`",
        f"- Rolling 60 dominated pct: `{diagnostics.get('rolling_60_dominated_pct')}`",
        "",
        "No chronological half is treated as a clean or sealed holdout. No promotion, paper/demo activation, broker action, parameter change, source research, provider download, or trade-management overlay occurred.",
        "",
        f"Exact next action: `{next_action}`. It was not executed.",
    ]
    return "\n".join(lines)


def write_artifacts(
    state: dict[str, Any],
    full_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rows_36: list[dict[str, Any]],
    rows_60: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    calendar_rows: list[dict[str, Any]],
    monthly_rows: list[dict[str, Any]],
    weight_summary: list[dict[str, Any]],
    cluster_summary: list[dict[str, Any]],
    portfolio_rows: list[dict[str, Any]],
    portfolio_events: list[dict[str, Any]],
    turnover_rows: list[dict[str, Any]],
    reproduction: list[dict[str, Any]],
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    next_action: str,
    diagnostics: dict[str, Any],
    protected_before: dict[str, str],
    input_before: dict[str, str],
    cache_before: dict[str, str],
) -> dict[str, Any]:
    protected_after = protected_hashes()
    input_after = input_evidence_hashes()
    cache_after = cache_hashes()
    benchmark_rows = benchmark_reference_rows()
    process_rows = [process_task_row(outcome, next_action)]
    strategy_rows = [strategy_card_row(outcome, failure_reason, next_action)]
    trial_rows = [trial_ledger_row(outcome, failure_reason, next_action)]
    outcome_rows = [outcome_summary_row(outcome, failure_reason, decision_reason, next_action, diagnostics)]
    failure_rows = failure_reason_rows(outcome, failure_reason, decision_reason)
    next_rows = next_action_rows(outcome, next_action)
    core_hash = deterministic_core_hash(outcome, full_rows, portfolio_rows, rolling_summary, monthly_rows)
    consistency = {
        "validation_id": VALIDATION_ID,
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "exactly_one_strategy_validated": len(strategy_rows) == 1 and strategy_rows[0]["strategy_id"] == STRATEGY_ID,
        "exactly_one_validation_child_trial": len(trial_rows) == 1 and trial_rows[0]["parent_trial_id"] == PARENT_TRIAL_ID,
        "reproduction_passed": all(row["reproduction_status"] == "pass" for row in reproduction),
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "input_evidence_hashes_unchanged": input_before == input_after,
        "protected_cache_hashes_unchanged": cache_before == cache_after,
        "benchmark_references_separate": all(row["entity_type"] == "benchmark_reference" for row in benchmark_rows),
        "inverse_volatility_benchmark_reference_only": any(
            row["benchmark_or_control_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1" for row in benchmark_rows
        )
        and not any(row["strategy_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1" for row in strategy_rows),
        "all_required_validation_controls_present": {row["benchmark_or_control_id"] for row in benchmark_rows}
        == {
            "frozen_current_active_vm_dsr_usci_combo",
            "monthly_equal_weight_same_five_etfs",
            "clare_inverse_volatility_five_asset_risk_parity_v1",
            "static_initial_hrp_weight_control",
            "IEF_single_asset_20pct_control",
            "BIL_cash_20pct_control",
        },
        "monthly_rebalanced_80_20_used": all(
            row["portfolio_construction"] in {"100pct_frozen_reference", "monthly_rebalanced_80_20"} for row in portfolio_rows
        ),
        "portfolio_exposure_lte_one": all(float(row.get("max_daily_exposure") or 0.0) <= 1.0 + WEIGHT_TOLERANCE for row in portfolio_rows),
        "portfolio_weight_sum_lte_one": all(float(row.get("max_daily_weight_sum") or 0.0) <= 1.0 + WEIGHT_TOLERANCE for row in portfolio_rows),
        "rolling_36_window_count_primary": int(
            next(row for row in rolling_summary if int(row["window_months"]) == 36 and float(row["cost_assumption_bps"]) == 5.0)[
                "window_count"
            ]
        ),
        "rolling_60_window_count_primary": int(
            next(row for row in rolling_summary if int(row["window_months"]) == 60 and float(row["cost_assumption_bps"]) == 5.0)[
                "window_count"
            ]
        ),
        "hrp_monthly_weight_rows": len(monthly_rows),
        "static_initial_hrp_first_valid_signal_date": state["static_info"]["first_valid_signal_date"],
        "static_initial_hrp_frozen_cluster_order": state["static_info"]["frozen_cluster_order"],
        "static_initial_hrp_frozen_weights": state["static_info"]["frozen_weights"],
        "static_initial_hrp_warmup_behavior": state["static_info"]["warmup_behavior"],
        "all_outcomes_allowed": outcome in ALLOWED_OUTCOMES,
        "all_failure_reasons_allowed": failure_reason in ALLOWED_FAILURE_REASONS,
        "prior_exploratory_state": {
            "stage": load_parent_trial_state().get("stage", ""),
            "outcome": load_parent_trial_state().get("outcome", ""),
        },
        "deterministic_core_hash": core_hash,
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["exactly_one_strategy_validated"]
        and consistency["exactly_one_validation_child_trial"]
        and consistency["reproduction_passed"]
        and consistency["protected_state_hashes_unchanged"]
        and consistency["input_evidence_hashes_unchanged"]
        and consistency["protected_cache_hashes_unchanged"]
        and consistency["benchmark_references_separate"]
        and consistency["inverse_volatility_benchmark_reference_only"]
        and consistency["all_required_validation_controls_present"]
        and consistency["monthly_rebalanced_80_20_used"]
        and consistency["portfolio_exposure_lte_one"]
        and consistency["portfolio_weight_sum_lte_one"]
        and consistency["all_outcomes_allowed"]
        and consistency["all_failure_reasons_allowed"]
        and not any(consistency[key] for key in FORBIDDEN_FLAGS)
    )
    manifest = {
        "validation_id": VALIDATION_ID,
        "mode": "validation",
        "lane": "validation",
        "stage": "validation",
        "scope": "research_and_paper_demo_only",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "primary_cost_assumption_bps": PRIMARY_COST_BPS,
        "cost_diagnostics_bps": list(COST_BPS_GRID),
        "frozen_universe": list(SYMBOLS),
        "hrp_rule_frozen": True,
        "lookback_trading_days": 252,
        "covariance_estimator": "sample_covariance",
        "linkage_method": "single",
        "tie_breaking_rule": "lexical_ticker_order",
        "execution_convention": "month_end_signal_next_available_session_close_execution",
        "additional_controls": [
            "static_initial_hrp_weight_control",
            "IEF_single_asset_20pct_control",
            "BIL_cash_20pct_control",
        ],
        "static_initial_hrp_control": state["static_info"],
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "exact_next_action": next_action,
        "provider_download": False,
        "paper_demo_eligibility_or_activation": False,
        "broker_account_order_paper_live_or_real_money_action": False,
    }

    write_yaml(OUTPUT_DIR / "validation_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows, STRATEGY_CARD_FIELDS)
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows, TRIAL_LEDGER_FIELDS)
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, PROCESS_TASK_FIELDS)
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_rows, BENCHMARK_FIELDS)
    write_csv(OUTPUT_DIR / "reproduction_check.csv", reproduction, REPRODUCTION_FIELDS)
    write_csv(OUTPUT_DIR / "full_period_results.csv", full_rows, RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "chronological_half_results.csv", half_rows, HALF_RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "rolling_36_month_results.csv", rows_36, ROLLING_FIELDS)
    write_csv(OUTPUT_DIR / "rolling_60_month_results.csv", rows_60, ROLLING_FIELDS)
    write_csv(OUTPUT_DIR / "rolling_window_summary.csv", rolling_summary, ROLLING_SUMMARY_FIELDS)
    write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar_rows, CALENDAR_FIELDS)
    write_csv(OUTPUT_DIR / "hrp_monthly_weights.csv", monthly_rows, HRP_MONTHLY_FIELDS)
    write_csv(OUTPUT_DIR / "hrp_weight_concentration_summary.csv", weight_summary, HRP_WEIGHT_SUMMARY_FIELDS)
    write_csv(OUTPUT_DIR / "hrp_cluster_ordering_summary.csv", cluster_summary, HRP_CLUSTER_FIELDS)
    write_csv(OUTPUT_DIR / "portfolio_contribution_results.csv", portfolio_rows, PORTFOLIO_FIELDS)
    write_csv(OUTPUT_DIR / "portfolio_rebalance_events.csv", portfolio_events, PORTFOLIO_EVENT_FIELDS)
    write_csv(OUTPUT_DIR / "turnover_cost_reconciliation.csv", turnover_rows, TURNOVER_FIELDS)
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows, OUTCOME_FIELDS)
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, FAILURE_FIELDS)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, NEXT_ACTION_FIELDS)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "validation_report.md", build_report(outcome, failure_reason, decision_reason, next_action, diagnostics, state["static_info"]))
    return consistency


STRATEGY_CARD_FIELDS = [
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
    "outcome",
    "primary_failure_reason",
    "next_action",
]
TRIAL_LEDGER_FIELDS = [
    "strategy_id",
    "family_id",
    "display_name",
    "entity_type",
    "stage",
    "trial_id",
    "parent_trial_id",
    "source_library_id",
    "adaptation_label",
    "changed_fields_from_parent",
    "strategy_definition_changed",
    "hrp_strategy_definition_changed",
    "parameters_changed",
    "instruments_changed",
    "universe_changed",
    "execution_changed",
    "cost_model_changed",
    "new_validation_controls_added",
    "timeframe_selected_from_results",
    "transaction_cost_assumptions",
    "execution_timing",
    "outcome",
    "primary_failure_reason",
    "next_action",
]
PROCESS_TASK_FIELDS = ["task_id", "entity_type", "stage", "outcome", "exact_next_action", "strategy_counted", "trial_counted"]
BENCHMARK_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "benchmark_or_control_id",
    "entity_type",
    "stage",
    "reference_role",
    "counted_as_strategy",
    "counted_as_trial",
    "counted_as_observation",
]
REPRODUCTION_FIELDS = ["entity_id", "metric", "prior_value", "recomputed_value", "absolute_difference", "tolerance", "reproduction_status"]
METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "rebalance_count",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "average_gross_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]
RESULT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "stage",
    "entity_id",
    "entity_type",
    "portfolio_id",
    "portfolio_construction",
    "cost_assumption_bps",
    *METRIC_FIELDS,
    "correlation_to_frozen_reference",
]
HALF_RESULT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "stage",
    "half_label",
    "half_source",
    "entity_id",
    "entity_type",
    "portfolio_id",
    "portfolio_construction",
    "cost_assumption_bps",
    *METRIC_FIELDS,
]
ROLLING_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "window_months",
    "window_start",
    "window_end",
    "trading_days",
    "cost_assumption_bps",
    "candidate_portfolio_id",
    "control_portfolio_id",
    "candidate_total_return",
    "candidate_cagr",
    "candidate_annualized_volatility",
    "candidate_sharpe_ratio",
    "candidate_maximum_drawdown",
    "control_total_return",
    "control_cagr",
    "control_annualized_volatility",
    "control_sharpe_ratio",
    "control_maximum_drawdown",
    "cagr_difference",
    "sharpe_ratio_difference",
    "maximum_drawdown_difference",
    "annualized_volatility_difference",
    "control_dominates_hrp",
    "turnover",
    "rebalance_count",
    "transaction_cost_drag",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]
ROLLING_SUMMARY_FIELDS = [
    "window_months",
    "cost_assumption_bps",
    "window_count",
    "median_sharpe_difference_vs_best_control",
    "median_maximum_drawdown_difference_vs_best_control",
    "positive_sharpe_difference_count",
    "positive_sharpe_difference_pct",
    "control_dominated_window_count",
    "control_dominated_window_pct",
]
CALENDAR_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "calendar_year",
    "cost_assumption_bps",
    "entity_id",
    "entity_type",
    "portfolio_id",
    "portfolio_construction",
    *METRIC_FIELDS,
]
HRP_MONTHLY_FIELDS = [
    "signal_date",
    "execution_date",
    "SPY_weight",
    "EEM_weight",
    "IEF_weight",
    "DBC_weight",
    "VNQ_weight",
    "maximum_asset_weight",
    "minimum_asset_weight",
    "effective_number_of_holdings",
    "cluster_ordering",
    "warmup_equal_weight",
    "one_way_turnover",
    "transaction_cost",
]
HRP_WEIGHT_SUMMARY_FIELDS = [
    "summary_scope",
    "instrument",
    "average_weight",
    "minimum_weight",
    "maximum_weight",
    "percentage_months_largest_allocation",
    "percentage_months_IEF_largest_allocation",
    "percentage_months_any_asset_exceeds_50pct",
    "median_effective_number_of_holdings",
    "unique_cluster_ordering_count",
]
HRP_CLUSTER_FIELDS = ["cluster_ordering", "month_count", "month_percentage"]
PORTFOLIO_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "portfolio_id",
    "portfolio_construction",
    "period_label",
    "half_source",
    "cost_assumption_bps",
    "entity_id",
    "entity_type",
    *METRIC_FIELDS,
    "correlation_to_frozen_reference",
]
PORTFOLIO_EVENT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "portfolio_id",
    "cost_assumption_bps",
    "date",
    "event_date",
    "event_type",
    "signal_date",
    "gross_return_before_cost",
    "net_return",
    "equity",
    "pretrade_reference_weight",
    "pretrade_sleeve_weight",
    "post_trade_reference_weight",
    "post_trade_sleeve_weight",
    "one_way_turnover",
    "transaction_cost_drag",
    "max_daily_exposure",
    "max_daily_weight_sum",
]
TURNOVER_FIELDS = [
    "record_scope",
    "entity_id",
    "portfolio_id",
    "cost_assumption_bps",
    "total_one_way_turnover",
    "rebalance_count",
    "transaction_cost_drag",
    "rebalance_policy",
]
OUTCOME_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "stage",
    "outcome",
    "primary_failure_reason",
    "decision_reason",
    "next_action",
    "reproduction_passed",
    "invariants_passed",
    "full_favorable",
    "static_initial_hrp_replicates",
    "simple_controls_replicate",
]
FAILURE_FIELDS = ["strategy_id", "family_id", "trial_id", "stage", "outcome", "primary_failure_reason", "decision_reason"]
NEXT_ACTION_FIELDS = ["scope", "strategy_id", "outcome", "exact_next_action", "execute_now"]


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    input_before = input_evidence_hashes()
    cache_before = cache_hashes()
    clean_output_dir()
    state = prepare_validation_payloads()
    full_rows = full_period_rows(state)
    half_rows = chronological_half_rows(state)
    rows_36 = rolling_rows(state, 36)
    rows_60 = rolling_rows(state, 60)
    rolling_summary = rolling_summary_rows(rows_36, rows_60)
    calendar_rows = calendar_year_rows(state)
    monthly_rows = state["hrp_monthly_rows"]
    weight_summary = hrp_weight_summary_rows(monthly_rows)
    cluster_summary = hrp_cluster_ordering_summary_rows(monthly_rows)
    portfolio_rows = portfolio_contribution_rows(state)
    portfolio_events = portfolio_rebalance_event_rows(state)
    turnover_rows = turnover_cost_reconciliation_rows(state)
    reproduction = reproduction_rows(full_rows, portfolio_rows)
    outcome, failure_reason, decision_reason, diagnostics = validation_decision(reproduction, full_rows, half_rows, rolling_summary)
    next_action = NEXT_ACTION_BY_OUTCOME[outcome]
    consistency = write_artifacts(
        state,
        full_rows,
        half_rows,
        rows_36,
        rows_60,
        rolling_summary,
        calendar_rows,
        monthly_rows,
        weight_summary,
        cluster_summary,
        portfolio_rows,
        portfolio_events,
        turnover_rows,
        reproduction,
        outcome,
        failure_reason,
        decision_reason,
        next_action,
        diagnostics,
        protected_before,
        input_before,
        cache_before,
    )
    return {
        "validation_id": VALIDATION_ID,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "validation_trial_id": VALIDATION_TRIAL_ID,
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "reproduction_passed": consistency["reproduction_passed"],
        "consistency_passed": consistency["consistency_passed"],
        "exact_next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
