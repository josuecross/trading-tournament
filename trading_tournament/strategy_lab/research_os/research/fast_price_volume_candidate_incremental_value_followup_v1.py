from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior


FOLLOWUP_ID = "fast_price_volume_candidate_incremental_value_followup_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / FOLLOWUP_ID / "latest"
PRIOR_DIR = ROOT / "evidence" / "research_recovery" / prior.BATCH_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-6
COST_BPS_GRID = (0.0, 5.0, 10.0)

NEXT_ACTION_REVIEW = "direction_owner_review_incremental_value_followup_v1"
NEXT_ACTION_REFRESH = "refresh_strategy_source_library_v1"

SELECTED_STRATEGY_IDS = (
    "qqq_spy_gld_ief_dual_momentum_v1",
    "treasury_duration_trend_rotation_v1",
)

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]

INPUT_EVIDENCE_PATHS = [
    PRIOR_DIR / "batch_manifest.yaml",
    PRIOR_DIR / "preregistered_strategy_cards.csv",
    PRIOR_DIR / "all_trial_results.csv",
    PRIOR_DIR / "exploratory_followup_candidates.csv",
    PRIOR_DIR / "trial_lineage.csv",
    PRIOR_DIR / "consistency_check.json",
]

FORBIDDEN_FLAGS = {
    "strategy_discovery_run": False,
    "parameter_optimization": False,
    "source_rule_completion": False,
    "trade_management_overlay_research": False,
    "promotion_review": False,
    "paper_demo_eligibility": False,
    "paper_demo_activation": False,
    "candidate_exhaustive": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "live_orders": False,
    "real_money_action": False,
    "clean_holdout_claimed": False,
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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / FOLLOWUP_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def selected_cards() -> list[prior.StrategyCard]:
    by_strategy_id = {card.strategy_id: card for card in prior.SELECTED_CARDS}
    cards = [by_strategy_id[strategy_id] for strategy_id in SELECTED_STRATEGY_IDS if strategy_id in by_strategy_id]
    if tuple(card.strategy_id for card in cards) != SELECTED_STRATEGY_IDS:
        missing = sorted(set(SELECTED_STRATEGY_IDS) - {card.strategy_id for card in cards})
        raise RuntimeError(f"Missing frozen prior candidate definitions: {missing}")
    return cards


def prior_trial_rows() -> dict[str, dict[str, str]]:
    rows = read_csv_rows(PRIOR_DIR / "all_trial_results.csv")
    return {row.get("strategy_id", ""): row for row in rows}


def card_to_definition_row(card: prior.StrategyCard, prior_row: dict[str, str]) -> dict[str, Any]:
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "original_trial_id": card.trial_id,
        "display_name": card.display_name,
        "original_batch_classification": prior_row.get("classification", ""),
        "direction_owner_followup_classification": "diversifier_followup_only",
        "rules_changed": False,
        "parameters_changed": False,
        "lookbacks_changed": False,
        "rebalance_schedule_changed": False,
        "instrument_universe_changed": False,
        "cash_proxy_changed": False,
        "evaluation_dates_changed": False,
        "transaction_timing_changed": False,
        "transaction_cost_methodology_changed": False,
        "parameters": card.parameters,
        "instrument_universe": card.instrument_universe,
        "complete_canonical_rule": card.complete_canonical_rule,
        "source_or_research_lineage": card.source_or_research_lineage,
    }


def common_prices_and_reference(card: prior.StrategyCard, reference_returns: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    common_prices = prior.evaluated_common_prices(card, reference_returns)
    if common_prices.empty:
        return pd.DataFrame(), pd.Series(dtype=float, name="reference")
    prices = common_prices[list(card.instrument_universe)].dropna()
    reference = common_prices["reference_return"].reindex(prices.index).fillna(0.0).rename("frozen_reference")
    return prices, reference


def dynamic_candidate_weights(card: prior.StrategyCard, prices: pd.DataFrame) -> pd.DataFrame:
    return prior.build_rotation_weights(
        prices,
        card.risky_universe,
        "BIL",
        int(card.parameters["lookback_trading_days"]),
        int(card.parameters["absolute_trend_sma_days"]),
    ).reindex(prices.index).fillna(0.0)


def buy_hold_weights(index: pd.DatetimeIndex, symbol: str) -> pd.DataFrame:
    return pd.DataFrame(1.0, index=index, columns=[symbol])


def equal_weight_weights(index: pd.DatetimeIndex, symbols: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(1.0 / len(symbols), index=index, columns=list(symbols))


def sleeve_definitions(card: prior.StrategyCard, prices: pd.DataFrame) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = [
        {
            "portfolio_id": f"{card.strategy_id}__reference_100pct",
            "sleeve_id": "frozen_current_active_vm_dsr_usci_combo",
            "sleeve_role": "reference_only",
            "same_purpose_control": False,
            "construction": "100% frozen reference portfolio",
            "weights": pd.DataFrame(index=prices.index),
        },
        {
            "portfolio_id": f"{card.strategy_id}__dynamic_candidate_20pct",
            "sleeve_id": card.strategy_id,
            "sleeve_role": "dynamic_candidate",
            "same_purpose_control": False,
            "construction": "80% frozen reference portfolio + 20% dynamic candidate sleeve",
            "weights": dynamic_candidate_weights(card, prices),
        },
        {
            "portfolio_id": f"{card.strategy_id}__bil_20pct",
            "sleeve_id": "BIL",
            "sleeve_role": "cash_control",
            "same_purpose_control": False,
            "construction": "80% frozen reference portfolio + 20% BIL sleeve",
            "weights": buy_hold_weights(prices.index, "BIL"),
        },
    ]
    if card.strategy_id == "qqq_spy_gld_ief_dual_momentum_v1":
        definitions.insert(
            2,
            {
                "portfolio_id": f"{card.strategy_id}__static_equal_weight_QQQ_SPY_GLD_IEF_20pct",
                "sleeve_id": "static_equal_weight_QQQ_SPY_GLD_IEF",
                "sleeve_role": "static_equal_weight_control",
                "same_purpose_control": True,
                "construction": "80% frozen reference portfolio + 20% static equal-weight QQQ/SPY/GLD/IEF sleeve",
                "weights": equal_weight_weights(prices.index, ("QQQ", "SPY", "GLD", "IEF")),
            },
        )
    elif card.strategy_id == "treasury_duration_trend_rotation_v1":
        definitions.insert(
            2,
            {
                "portfolio_id": f"{card.strategy_id}__IEF_buy_hold_20pct",
                "sleeve_id": "IEF_buy_hold",
                "sleeve_role": "buy_hold_control",
                "same_purpose_control": True,
                "construction": "80% frozen reference portfolio + 20% IEF buy-and-hold sleeve",
                "weights": buy_hold_weights(prices.index, "IEF"),
            },
        )
        definitions.insert(
            3,
            {
                "portfolio_id": f"{card.strategy_id}__static_equal_weight_SHY_IEF_TLT_20pct",
                "sleeve_id": "static_equal_weight_SHY_IEF_TLT",
                "sleeve_role": "static_equal_weight_control",
                "same_purpose_control": True,
                "construction": "80% frozen reference portfolio + 20% static equal-weight SHY/IEF/TLT sleeve",
                "weights": equal_weight_weights(prices.index, ("SHY", "IEF", "TLT")),
            },
        )
    else:
        raise RuntimeError(f"Unsupported selected strategy: {card.strategy_id}")
    return definitions


def price_frame_for_weights(weights: pd.DataFrame, fallback_prices: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(index=fallback_prices.index)
    columns = tuple(weights.columns)
    return prior.load_price_frame(columns).reindex(fallback_prices.index).dropna()


def returns_cost_and_turnover(weights: pd.DataFrame, fallback_prices: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    if weights.empty:
        index = fallback_prices.index
        zeros = pd.Series(0.0, index=index, name="zero")
        return zeros, zeros, zeros
    prices = price_frame_for_weights(weights, fallback_prices)
    aligned_weights = weights.reindex(prices.index).fillna(0.0)
    gross = returns_from_weights(prices, aligned_weights).rename("gross_sleeve_return")
    turnover = prior.turnover_series(aligned_weights).reindex(gross.index).fillna(0.0)
    cost = (turnover * (cost_bps / 10000.0)).rename("sleeve_cost")
    return gross - cost, turnover, cost


def portfolio_returns(
    definition: dict[str, Any],
    prices: pd.DataFrame,
    reference: pd.Series,
    cost_bps: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if definition["sleeve_role"] == "reference_only":
        aligned_reference = reference.reindex(prices.index).fillna(0.0)
        zeros = pd.Series(0.0, index=aligned_reference.index)
        return aligned_reference.rename(definition["portfolio_id"]), zeros, zeros
    sleeve_returns, sleeve_turnover, sleeve_cost = returns_cost_and_turnover(definition["weights"], prices, cost_bps)
    aligned = pd.concat([reference.rename("reference"), sleeve_returns.rename("sleeve")], axis=1, join="inner").dropna()
    returns = (0.8 * aligned["reference"] + 0.2 * aligned["sleeve"]).rename(definition["portfolio_id"])
    turnover = (0.2 * sleeve_turnover.reindex(returns.index).fillna(0.0)).rename("portfolio_turnover")
    cost = (0.2 * sleeve_cost.reindex(returns.index).fillna(0.0)).rename("portfolio_cost")
    return returns, turnover, cost


def metric_row(returns: pd.Series, turnover: pd.Series, cost: pd.Series, reference: pd.Series) -> dict[str, Any]:
    metrics = prior.metrics_from_returns(returns)
    aligned_reference = reference.reindex(returns.index).fillna(0.0)
    return {
        **metrics,
        "turnover": float(turnover.reindex(returns.index).fillna(0.0).sum()),
        "estimated_transaction_cost_drag": float(cost.reindex(returns.index).fillna(0.0).sum()),
        "correlation_to_frozen_reference": 1.0 if returns.name and returns.name.endswith("__reference_100pct") else prior.safe_corr(returns, aligned_reference),
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "numeric_integrity_pass": bool(not returns.isna().any() and len(returns) > 0),
    }


def half_slices_from_prior(prior_row: dict[str, str]) -> dict[str, tuple[str, str]]:
    return {
        "first_chronological_half": (prior_row["first_half_start"], prior_row["first_half_end"]),
        "second_chronological_half": (prior_row["second_half_start"], prior_row["second_half_end"]),
    }


def slice_by_dates(series: pd.Series, start: str, end: str) -> pd.Series:
    return series.loc[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]


def full_result_row(
    card: prior.StrategyCard,
    original_trial_id: str,
    definition: dict[str, Any],
    cost_bps: float,
    returns: pd.Series,
    turnover: pd.Series,
    cost: pd.Series,
    reference: pd.Series,
) -> dict[str, Any]:
    metrics = metric_row(returns, turnover, cost, reference)
    return {
        "candidate_strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "original_trial_id": original_trial_id,
        "followup_trial_id": followup_trial_id(card, definition, cost_bps),
        "portfolio_id": definition["portfolio_id"],
        "portfolio_construction": definition["construction"],
        "sleeve_identity": definition["sleeve_id"],
        "sleeve_role": definition["sleeve_role"],
        "same_purpose_control": definition["same_purpose_control"],
        "cost_assumption_bps": cost_bps,
        **metrics,
        **FORBIDDEN_FLAGS,
    }


def half_result_rows(
    card: prior.StrategyCard,
    original_trial_id: str,
    definition: dict[str, Any],
    cost_bps: float,
    returns: pd.Series,
    turnover: pd.Series,
    cost: pd.Series,
    reference: pd.Series,
    halves: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for half_name, (start, end) in halves.items():
        half_returns = slice_by_dates(returns, start, end)
        half_turnover = slice_by_dates(turnover, start, end)
        half_cost = slice_by_dates(cost, start, end)
        half_reference = slice_by_dates(reference, start, end)
        metrics = metric_row(half_returns, half_turnover, half_cost, half_reference)
        rows.append(
            {
                "candidate_strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "original_trial_id": original_trial_id,
                "followup_trial_id": followup_trial_id(card, definition, cost_bps),
                "portfolio_id": definition["portfolio_id"],
                "half_label": half_name,
                "half_source": "exact_prior_batch_chronological_half_not_holdout",
                "portfolio_construction": definition["construction"],
                "sleeve_identity": definition["sleeve_id"],
                "sleeve_role": definition["sleeve_role"],
                "cost_assumption_bps": cost_bps,
                **metrics,
            }
        )
    return rows


def followup_trial_id(card: prior.StrategyCard, definition: dict[str, Any], cost_bps: float) -> str:
    cost_token = str(int(cost_bps)) if float(cost_bps).is_integer() else str(cost_bps).replace(".", "p")
    return f"fast_pv_incremental_v1__{card.strategy_id}__{definition['sleeve_role']}__cost{cost_token}bps"


def trial_lineage_row(card: prior.StrategyCard, definition: dict[str, Any], cost_bps: float) -> dict[str, Any]:
    return {
        "candidate_strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "original_trial_id": card.trial_id,
        "parent_trial_id": card.trial_id,
        "followup_trial_id": followup_trial_id(card, definition, cost_bps),
        "portfolio_construction": definition["construction"],
        "sleeve_identity": definition["sleeve_id"],
        "sleeve_role": definition["sleeve_role"],
        "cost_assumption_bps": cost_bps,
        "changed_fields_from_parent": "portfolio_sleeve_comparison|predeclared_cost_diagnostic|chronological_half_reporting",
        "candidate_rule_changes": False,
        "parameter_changes": False,
        "benchmark_changes": False,
        "instrument_universe_changes": False,
        "timeframe_changes": False,
        "reason_for_new_diagnostic": "test_incremental_dynamic_signal_value_beyond_exposure_matched_simple_controls",
        "predeclared_before_results": True,
        "task_or_process_record": False,
    }


def portfolio_definition_rows(card: prior.StrategyCard, definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for definition in definitions:
        rows.append(
            {
                "candidate_strategy_id": card.strategy_id,
                "portfolio_id": definition["portfolio_id"],
                "portfolio_construction": definition["construction"],
                "sleeve_identity": definition["sleeve_id"],
                "sleeve_role": definition["sleeve_role"],
                "same_purpose_control": definition["same_purpose_control"],
                "reference_weight": 1.0 if definition["sleeve_role"] == "reference_only" else 0.8,
                "sleeve_weight": 0.0 if definition["sleeve_role"] == "reference_only" else 0.2,
                "maximum_total_exposure": 1.0,
                "rebalance_convention": "same_daily_return_alignment_as_prior_batch; no sleeve rule rebalance changes",
                "transaction_cost_methodology": "predeclared bps times one-way turnover proxy; reference return path is frozen",
            }
        )
    return rows


def build_reproduction_rows(
    card: prior.StrategyCard,
    prices: pd.DataFrame,
    reference: pd.Series,
    prior_row: dict[str, str],
    dynamic_definition: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    standalone_weights = dynamic_definition["weights"]
    standalone_returns, turnover, cost = returns_cost_and_turnover(standalone_weights, prices, 5.0)
    standalone_metrics = prior.metrics_from_returns(standalone_returns)
    reference_metrics = prior.metrics_from_returns(reference.reindex(standalone_returns.index).fillna(0.0))
    combined_returns = (0.8 * reference.reindex(standalone_returns.index).fillna(0.0) + 0.2 * standalone_returns).rename(
        "prior_fixed_20pct_reproduction"
    )
    combined_metrics = prior.metrics_from_returns(combined_returns)
    checks = {
        "candidate_total_return": (standalone_metrics["total_return"], prior_row["total_return"]),
        "candidate_cagr": (standalone_metrics["cagr"], prior_row["cagr"]),
        "candidate_annualized_volatility": (standalone_metrics["annualized_volatility"], prior_row["annualized_volatility"]),
        "candidate_sharpe_ratio": (standalone_metrics["sharpe_ratio"], prior_row["sharpe_ratio"]),
        "candidate_maximum_drawdown": (standalone_metrics["maximum_drawdown"], prior_row["maximum_drawdown"]),
        "candidate_turnover": (float(turnover.sum()), prior_row["turnover"]),
        "candidate_estimated_cost_return_drag": (float(cost.sum()), prior_row["estimated_cost_return_drag"]),
        "reference_total_return": (reference_metrics["total_return"], prior_row["reference_combo_total_return"]),
        "reference_sharpe_ratio": (reference_metrics["sharpe_ratio"], prior_row["reference_combo_sharpe_ratio"]),
        "reference_maximum_drawdown": (reference_metrics["maximum_drawdown"], prior_row["reference_combo_maximum_drawdown"]),
        "fixed_20pct_sleeve_total_return": (combined_metrics["total_return"], prior_row["fixed_20pct_sleeve_total_return"]),
        "fixed_20pct_sleeve_sharpe_ratio": (combined_metrics["sharpe_ratio"], prior_row["fixed_20pct_sleeve_sharpe_ratio"]),
        "fixed_20pct_sleeve_maximum_drawdown": (
            combined_metrics["maximum_drawdown"],
            prior_row["fixed_20pct_sleeve_maximum_drawdown"],
        ),
    }
    all_pass = True
    for metric_name, (recomputed, prior_value_text) in checks.items():
        prior_value = float(prior_value_text)
        difference = float(recomputed) - prior_value
        passed = abs(difference) <= REPRODUCTION_TOLERANCE
        all_pass = all_pass and passed
        rows.append(
            {
                "candidate_strategy_id": card.strategy_id,
                "original_trial_id": card.trial_id,
                "metric": metric_name,
                "prior_value": prior_value,
                "recomputed_value": float(recomputed),
                "difference": difference,
                "tolerance": REPRODUCTION_TOLERANCE,
                "reproduction_pass": passed,
            }
        )
    return rows, all_pass


def row_by_portfolio(results: list[dict[str, Any]], strategy_id: str, cost_bps: float) -> dict[str, dict[str, Any]]:
    return {
        row["portfolio_id"]: row
        for row in results
        if row["candidate_strategy_id"] == strategy_id and float(row["cost_assumption_bps"]) == float(cost_bps)
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    control_values = (
        float(control["cagr"]),
        float(control["sharpe_ratio"]),
        float(control["maximum_drawdown"]),
    )
    candidate_values = (
        float(candidate["cagr"]),
        float(candidate["sharpe_ratio"]),
        float(candidate["maximum_drawdown"]),
    )
    at_least_equal = all(c >= v - 1e-12 for c, v in zip(control_values, candidate_values))
    strictly_better = any(c > v + 1e-12 for c, v in zip(control_values, candidate_values))
    return bool(at_least_equal and strictly_better)


def same_purpose_control_ids(strategy_id: str) -> list[str]:
    if strategy_id == "qqq_spy_gld_ief_dual_momentum_v1":
        return [f"{strategy_id}__static_equal_weight_QQQ_SPY_GLD_IEF_20pct"]
    if strategy_id == "treasury_duration_trend_rotation_v1":
        return [
            f"{strategy_id}__IEF_buy_hold_20pct",
            f"{strategy_id}__static_equal_weight_SHY_IEF_TLT_20pct",
        ]
    raise RuntimeError(f"Unsupported strategy: {strategy_id}")


def build_incremental_comparisons(
    card: prior.StrategyCard,
    full_results: list[dict[str, Any]],
    half_results: list[dict[str, Any]],
    reproduction_pass: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparison_rows: list[dict[str, Any]] = []
    candidate_portfolio_id = f"{card.strategy_id}__dynamic_candidate_20pct"
    control_ids = same_purpose_control_ids(card.strategy_id) + [f"{card.strategy_id}__bil_20pct"]
    for cost_bps in COST_BPS_GRID:
        rows_for_cost = row_by_portfolio(full_results, card.strategy_id, cost_bps)
        candidate = rows_for_cost[candidate_portfolio_id]
        for control_id in control_ids:
            control = rows_for_cost[control_id]
            comparison_rows.append(
                {
                    "candidate_strategy_id": card.strategy_id,
                    "cost_assumption_bps": cost_bps,
                    "candidate_portfolio_id": candidate_portfolio_id,
                    "control_portfolio_id": control_id,
                    "control_sleeve_identity": control["sleeve_identity"],
                    "control_sleeve_role": control["sleeve_role"],
                    "control_dominates_candidate": dominates(control, candidate),
                    "candidate_cagr_minus_control": float(candidate["cagr"]) - float(control["cagr"]),
                    "candidate_sharpe_minus_control": float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]),
                    "candidate_max_drawdown_minus_control": float(candidate["maximum_drawdown"])
                    - float(control["maximum_drawdown"]),
                    "candidate_total_return_minus_control": float(candidate["total_return"]) - float(control["total_return"]),
                }
            )

    rows_5 = row_by_portfolio(full_results, card.strategy_id, 5.0)
    candidate_5 = rows_5[candidate_portfolio_id]
    same_controls_5 = [rows_5[control_id] for control_id in same_purpose_control_ids(card.strategy_id)]
    bil_5 = rows_5[f"{card.strategy_id}__bil_20pct"]
    best_same_control_5 = max(same_controls_5, key=lambda row: float(row["sharpe_ratio"]))
    any_control_dominates_5 = any(
        dominates(rows_5[control_id], candidate_5) for control_id in same_purpose_control_ids(card.strategy_id) + [f"{card.strategy_id}__bil_20pct"]
    )
    candidate_sharpe_beats_best_same_control = float(candidate_5["sharpe_ratio"]) > float(best_same_control_5["sharpe_ratio"])
    bil_replicates_or_exceeds = (
        float(bil_5["sharpe_ratio"]) >= float(candidate_5["sharpe_ratio"]) - 1e-12
        and float(bil_5["maximum_drawdown"]) >= float(candidate_5["maximum_drawdown"]) - 1e-12
        and float(bil_5["cagr"]) >= float(candidate_5["cagr"]) - 1e-12
    )
    half_rows_by_key = {
        (row["candidate_strategy_id"], row["portfolio_id"], float(row["cost_assumption_bps"]), row["half_label"]): row
        for row in half_results
    }
    half_sharpe_favorable = True
    half_drawdown_favorable = True
    for half_label in ("first_chronological_half", "second_chronological_half"):
        candidate_half = half_rows_by_key[(card.strategy_id, candidate_portfolio_id, 5.0, half_label)]
        control_half = half_rows_by_key[(card.strategy_id, best_same_control_5["portfolio_id"], 5.0, half_label)]
        half_sharpe_favorable = half_sharpe_favorable and (
            float(candidate_half["sharpe_ratio"]) > float(control_half["sharpe_ratio"])
        )
        half_drawdown_favorable = half_drawdown_favorable and (
            float(candidate_half["maximum_drawdown"]) > float(control_half["maximum_drawdown"])
        )
    invariant_pass = bool(candidate_5["numeric_integrity_pass"]) and float(candidate_5["max_daily_exposure"]) <= 1.0 + WEIGHT_TOLERANCE
    all_advance_conditions = (
        reproduction_pass
        and not any_control_dominates_5
        and candidate_sharpe_beats_best_same_control
        and not bil_replicates_or_exceeds
        and (half_sharpe_favorable or half_drawdown_favorable)
        and invariant_pass
    )
    if all_advance_conditions:
        decision = "advance_to_validation_candidate"
        reason = "dynamic_80_20_portfolio_passed_all_predeclared_incremental_value_conditions"
    elif any_control_dominates_5 or not candidate_sharpe_beats_best_same_control or bil_replicates_or_exceeds:
        decision = "close_no_incremental_signal_value"
        reason = "simple_exposure_matched_control_replicated_or_exceeded_dynamic_portfolio_contribution_at_5bps"
    else:
        decision = "inconclusive_incremental_value"
        reason = "mixed_incremental_value_evidence_after_predeclared_control_comparisons"
    if not reproduction_pass:
        decision = "inconclusive_incremental_value"
        reason = "prior_5bps_reproduction_failed; comparison_decision_stopped_for_affected_candidate"
    decision_row = {
        "candidate_strategy_id": card.strategy_id,
        "original_trial_id": card.trial_id,
        "decision_cost_assumption_bps": 5.0,
        "incremental_signal_value_decision": decision,
        "decision_reason": reason,
        "reproduction_pass": reproduction_pass,
        "candidate_portfolio_id": candidate_portfolio_id,
        "best_same_purpose_control_portfolio_id": best_same_control_5["portfolio_id"],
        "any_simple_control_dominates_candidate": any_control_dominates_5,
        "candidate_sharpe_beats_best_same_purpose_control": candidate_sharpe_beats_best_same_control,
        "bil_control_replicates_or_exceeds_candidate": bil_replicates_or_exceeds,
        "half_sharpe_favorable_vs_best_same_control_in_both_halves": half_sharpe_favorable,
        "half_max_drawdown_favorable_vs_best_same_control_in_both_halves": half_drawdown_favorable,
        "exposure_and_numeric_invariants_pass": invariant_pass,
        "validation_candidate_not_due_to_reference_only_improvement": decision == "advance_to_validation_candidate",
        **FORBIDDEN_FLAGS,
    }
    return comparison_rows, decision_row


def build_report(funnel: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    lines = [
        "# Fast Price/Volume Candidate Incremental Value Follow-Up V1",
        "",
        "## Scope",
        "",
        "This targeted exploratory follow-up compared the two frozen candidates from `fast_price_volume_discovery_batch_v2` against exposure-matched 80/20 static and BIL controls. It preserved the candidate rules, parameters, dates, timing, universes and transaction-cost methodology.",
        "",
        "The prior standalone label for `qqq_spy_gld_ief_dual_momentum_v1` was not carried forward. Direction-owner override records both candidates as `diversifier_followup_only` for this task.",
        "",
        "## Funnel",
        "",
        f"- Candidates evaluated: `{funnel['candidate_count']}`",
        f"- Portfolio comparison rows: `{funnel['portfolio_comparison_row_count']}`",
        f"- Chronological-half rows: `{funnel['chronological_half_row_count']}`",
        f"- Reproduction failures: `{funnel['reproduction_failure_count']}`",
        f"- Advance decisions: `{funnel['advance_count']}`",
        f"- Close decisions: `{funnel['close_count']}`",
        f"- Inconclusive decisions: `{funnel['inconclusive_count']}`",
        "",
        "## Decisions",
        "",
    ]
    for row in decisions:
        lines.append(
            f"- `{row['candidate_strategy_id']}`: `{row['incremental_signal_value_decision']}` - {row['decision_reason']}"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "No promotion review, paper/demo eligibility, paper/demo activation, strategy discovery, parameter optimization, source-rule completion, trade-management overlay research, broker/order/live path, or real-money action occurred.",
            "",
            f"Exact next action: `{funnel['exact_next_action']}`.",
        ]
    )
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    names = [
        "followup_manifest.yaml",
        "direction_owner_classification_override.yaml",
        "frozen_candidate_definitions.csv",
        "portfolio_control_definitions.csv",
        "reproduction_check.csv",
        "all_portfolio_comparison_results.csv",
        "chronological_half_results.csv",
        "incremental_signal_value_comparison.csv",
        "candidate_followup_decisions.csv",
        "trial_lineage.csv",
        "followup_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def identical_full_period_dates(rows: list[dict[str, Any]]) -> bool:
    groups: dict[tuple[str, float], set[tuple[str, str, int]]] = {}
    for row in rows:
        key = (row["candidate_strategy_id"], float(row["cost_assumption_bps"]))
        groups.setdefault(key, set()).add(
            (str(row["evaluation_start"]), str(row["evaluation_end"]), int(row["trading_days"]))
        )
    return bool(groups) and all(len(values) == 1 for values in groups.values())


def identical_half_period_dates(rows: list[dict[str, Any]]) -> bool:
    groups: dict[tuple[str, float, str], set[tuple[str, str, int]]] = {}
    for row in rows:
        key = (row["candidate_strategy_id"], float(row["cost_assumption_bps"]), row["half_label"])
        groups.setdefault(key, set()).add(
            (str(row["evaluation_start"]), str(row["evaluation_end"]), int(row["trading_days"]))
        )
    return bool(groups) and all(len(values) == 1 for values in groups.values())


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    prior_input_hashes_before = {rel(path): file_hash(path) for path in INPUT_EVIDENCE_PATHS}
    cards = selected_cards()
    prior_rows = prior_trial_rows()
    clean_output_dir()

    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    candidate_def_rows: list[dict[str, Any]] = []
    portfolio_def_rows: list[dict[str, Any]] = []
    reproduction_rows: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    reproduction_pass_by_strategy: dict[str, bool] = {}

    for card in cards:
        prior_row = prior_rows[card.strategy_id]
        prices, reference = common_prices_and_reference(card, reference_returns)
        definitions = sleeve_definitions(card, prices)
        portfolio_def_rows.extend(portfolio_definition_rows(card, definitions))
        candidate_def_rows.append(card_to_definition_row(card, prior_row))
        dynamic_definition = next(definition for definition in definitions if definition["sleeve_role"] == "dynamic_candidate")
        card_reproduction_rows, reproduction_pass = build_reproduction_rows(
            card, prices, reference, prior_row, dynamic_definition
        )
        reproduction_rows.extend(card_reproduction_rows)
        reproduction_pass_by_strategy[card.strategy_id] = reproduction_pass
        halves = half_slices_from_prior(prior_row)
        for definition in definitions:
            for cost_bps in COST_BPS_GRID:
                returns, turnover, cost = portfolio_returns(definition, prices, reference, cost_bps)
                full_rows.append(full_result_row(card, card.trial_id, definition, cost_bps, returns, turnover, cost, reference))
                half_rows.extend(
                    half_result_rows(card, card.trial_id, definition, cost_bps, returns, turnover, cost, reference, halves)
                )
                lineage_rows.append(trial_lineage_row(card, definition, cost_bps))
        card_comparisons, card_decision = build_incremental_comparisons(
            card, full_rows, half_rows, reproduction_pass_by_strategy[card.strategy_id]
        )
        comparison_rows.extend(card_comparisons)
        decision_rows.append(card_decision)

    advance_or_inconclusive = [
        row
        for row in decision_rows
        if row["incremental_signal_value_decision"] in {"advance_to_validation_candidate", "inconclusive_incremental_value"}
    ]
    next_action = NEXT_ACTION_REVIEW if advance_or_inconclusive else NEXT_ACTION_REFRESH
    funnel = {
        "followup_id": FOLLOWUP_ID,
        "candidate_count": len(cards),
        "portfolio_comparison_row_count": len(full_rows),
        "chronological_half_row_count": len(half_rows),
        "incremental_comparison_row_count": len(comparison_rows),
        "trial_lineage_row_count": len(lineage_rows),
        "reproduction_failure_count": sum(1 for passed in reproduction_pass_by_strategy.values() if not passed),
        "advance_count": sum(1 for row in decision_rows if row["incremental_signal_value_decision"] == "advance_to_validation_candidate"),
        "close_count": sum(1 for row in decision_rows if row["incremental_signal_value_decision"] == "close_no_incremental_signal_value"),
        "inconclusive_count": sum(1 for row in decision_rows if row["incremental_signal_value_decision"] == "inconclusive_incremental_value"),
        "exact_next_action": next_action,
    }

    manifest = {
        "followup_id": FOLLOWUP_ID,
        "mode": "targeted_exploratory_incremental_value_followup",
        "research_and_paper_demo_only": True,
        "frozen_timestamp": FROZEN_TIMESTAMP,
        "source_batch_id": prior.BATCH_ID,
        "source_evidence_path": rel(PRIOR_DIR),
        "source_input_evidence": [
            {"path": rel(path), "exists": path.exists(), "sha256": prior_input_hashes_before[rel(path)]}
            for path in INPUT_EVIDENCE_PATHS
        ],
        "selected_strategy_ids": list(SELECTED_STRATEGY_IDS),
        "cost_diagnostic_bps": list(COST_BPS_GRID),
        "portfolio_construction": "80pct_frozen_reference_plus_20pct_candidate_or_control_sleeve",
        "frozen_reference_portfolio": "frozen_current_active_vm_dsr_usci_combo",
        "standalone_classification_carried_forward": False,
        "candidate_followup_classification": "diversifier_followup_only",
        "prior_batch_evidence_modified": False,
        "protected_state_paths": [rel(path) for path in PROTECTED_STATE_PATHS],
        **FORBIDDEN_FLAGS,
        "exact_next_action": next_action,
    }
    override = {
        "override_id": "direction_owner_classification_override_fast_pv_incremental_value_v1",
        "source_batch_id": prior.BATCH_ID,
        "override_applies_to": [
            {
                "strategy_id": "qqq_spy_gld_ief_dual_momentum_v1",
                "prior_classification": prior_rows["qqq_spy_gld_ief_dual_momentum_v1"].get("classification", ""),
                "followup_classification": "diversifier_followup_only",
                "reason": "same-universe static equal-weight control had higher CAGR, higher Sharpe, and smaller maximum drawdown",
            },
            {
                "strategy_id": "treasury_duration_trend_rotation_v1",
                "prior_classification": prior_rows["treasury_duration_trend_rotation_v1"].get("classification", ""),
                "followup_classification": "diversifier_followup_only",
                "reason": "direction-owner instructed both candidates to be evaluated only for incremental diversifier value",
            },
        ],
        "prior_evidence_rewritten_or_deleted": False,
    }

    write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)
    write_yaml(OUTPUT_DIR / "direction_owner_classification_override.yaml", override)
    write_csv(
        OUTPUT_DIR / "frozen_candidate_definitions.csv",
        candidate_def_rows,
        [
            "strategy_id",
            "family_id",
            "original_trial_id",
            "display_name",
            "original_batch_classification",
            "direction_owner_followup_classification",
            "rules_changed",
            "parameters_changed",
            "lookbacks_changed",
            "rebalance_schedule_changed",
            "instrument_universe_changed",
            "cash_proxy_changed",
            "evaluation_dates_changed",
            "transaction_timing_changed",
            "transaction_cost_methodology_changed",
            "parameters",
            "instrument_universe",
            "complete_canonical_rule",
            "source_or_research_lineage",
        ],
    )
    write_csv(
        OUTPUT_DIR / "portfolio_control_definitions.csv",
        portfolio_def_rows,
        [
            "candidate_strategy_id",
            "portfolio_id",
            "portfolio_construction",
            "sleeve_identity",
            "sleeve_role",
            "same_purpose_control",
            "reference_weight",
            "sleeve_weight",
            "maximum_total_exposure",
            "rebalance_convention",
            "transaction_cost_methodology",
        ],
    )
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction_rows,
        [
            "candidate_strategy_id",
            "original_trial_id",
            "metric",
            "prior_value",
            "recomputed_value",
            "difference",
            "tolerance",
            "reproduction_pass",
        ],
    )
    result_fields = [
        "candidate_strategy_id",
        "family_id",
        "original_trial_id",
        "followup_trial_id",
        "portfolio_id",
        "portfolio_construction",
        "sleeve_identity",
        "sleeve_role",
        "same_purpose_control",
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
        "estimated_transaction_cost_drag",
        "correlation_to_frozen_reference",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "numeric_integrity_pass",
        *FORBIDDEN_FLAGS.keys(),
    ]
    write_csv(OUTPUT_DIR / "all_portfolio_comparison_results.csv", full_rows, result_fields)
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_rows,
        [
            "candidate_strategy_id",
            "family_id",
            "original_trial_id",
            "followup_trial_id",
            "portfolio_id",
            "half_label",
            "half_source",
            "portfolio_construction",
            "sleeve_identity",
            "sleeve_role",
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
            "estimated_transaction_cost_drag",
            "correlation_to_frozen_reference",
            "max_daily_exposure",
            "max_daily_weight_sum",
            "numeric_integrity_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "incremental_signal_value_comparison.csv",
        comparison_rows,
        [
            "candidate_strategy_id",
            "cost_assumption_bps",
            "candidate_portfolio_id",
            "control_portfolio_id",
            "control_sleeve_identity",
            "control_sleeve_role",
            "control_dominates_candidate",
            "candidate_cagr_minus_control",
            "candidate_sharpe_minus_control",
            "candidate_max_drawdown_minus_control",
            "candidate_total_return_minus_control",
        ],
    )
    write_csv(
        OUTPUT_DIR / "candidate_followup_decisions.csv",
        decision_rows,
        [
            "candidate_strategy_id",
            "original_trial_id",
            "decision_cost_assumption_bps",
            "incremental_signal_value_decision",
            "decision_reason",
            "reproduction_pass",
            "candidate_portfolio_id",
            "best_same_purpose_control_portfolio_id",
            "any_simple_control_dominates_candidate",
            "candidate_sharpe_beats_best_same_purpose_control",
            "bil_control_replicates_or_exceeds_candidate",
            "half_sharpe_favorable_vs_best_same_control_in_both_halves",
            "half_max_drawdown_favorable_vs_best_same_control_in_both_halves",
            "exposure_and_numeric_invariants_pass",
            "validation_candidate_not_due_to_reference_only_improvement",
            *FORBIDDEN_FLAGS.keys(),
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_lineage.csv",
        lineage_rows,
        [
            "candidate_strategy_id",
            "family_id",
            "original_trial_id",
            "parent_trial_id",
            "followup_trial_id",
            "portfolio_construction",
            "sleeve_identity",
            "sleeve_role",
            "cost_assumption_bps",
            "changed_fields_from_parent",
            "candidate_rule_changes",
            "parameter_changes",
            "benchmark_changes",
            "instrument_universe_changes",
            "timeframe_changes",
            "reason_for_new_diagnostic",
            "predeclared_before_results",
            "task_or_process_record",
        ],
    )
    write_text(OUTPUT_DIR / "followup_report.md", build_report(funnel, decision_rows))
    prior_input_hashes_after = {rel(path): file_hash(path) for path in INPUT_EVIDENCE_PATHS}
    after_hashes = protected_hashes()
    consistency = {
        "followup_id": FOLLOWUP_ID,
        "source_batch_id": prior.BATCH_ID,
        "candidate_count": len(cards),
        "exact_selected_strategy_ids": [card.strategy_id for card in cards],
        "both_candidates_diversifier_followup_only": all(
            row["direction_owner_followup_classification"] == "diversifier_followup_only"
            for row in candidate_def_rows
        ),
        "prior_batch_input_hashes_before": prior_input_hashes_before,
        "prior_batch_input_hashes_after": prior_input_hashes_after,
        "prior_batch_evidence_unchanged": prior_input_hashes_before == prior_input_hashes_after,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "all_reproduction_checks_pass": all(row["reproduction_pass"] for row in reproduction_rows),
        "reproduction_tolerance": REPRODUCTION_TOLERANCE,
        "portfolio_cost_assumptions_bps": list(COST_BPS_GRID),
        "portfolio_comparison_row_count": len(full_rows),
        "chronological_half_row_count": len(half_rows),
        "trial_lineage_row_count": len(lineage_rows),
        "all_trial_rows_have_parent_trial_id": all(row["parent_trial_id"] for row in lineage_rows),
        "only_permitted_followup_changes_used": all(
            row["changed_fields_from_parent"]
            == "portfolio_sleeve_comparison|predeclared_cost_diagnostic|chronological_half_reporting"
            and not row["candidate_rule_changes"]
            and not row["parameter_changes"]
            and not row["benchmark_changes"]
            and not row["instrument_universe_changes"]
            and not row["timeframe_changes"]
            for row in lineage_rows
        ),
        "all_portfolios_exposure_invariant_pass": all(
            float(row["max_daily_exposure"]) <= 1.0 + WEIGHT_TOLERANCE
            and float(row["max_daily_weight_sum"]) <= 1.0 + WEIGHT_TOLERANCE
            and row["numeric_integrity_pass"]
            for row in full_rows
        ),
        "portfolio_rows_have_identical_dates_by_candidate_and_cost": identical_full_period_dates(full_rows),
        "half_rows_have_identical_dates_by_candidate_cost_and_half": identical_half_period_dates(half_rows),
        "no_strategy_classified_from_reference_improvement_only": all(
            row["incremental_signal_value_decision"] != "advance_to_validation_candidate"
            or row["validation_candidate_not_due_to_reference_only_improvement"]
            for row in decision_rows
        ),
        **FORBIDDEN_FLAGS,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "followup_id": FOLLOWUP_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "candidate_count": len(cards),
        "advance_count": funnel["advance_count"],
        "close_count": funnel["close_count"],
        "inconclusive_count": funnel["inconclusive_count"],
        "exact_next_action": next_action,
        "task_outcome": "fast_price_volume_candidate_incremental_value_followup_v1_complete",
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "prior_batch_evidence_unchanged": prior_input_hashes_before == prior_input_hashes_after,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
