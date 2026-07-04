from __future__ import annotations

import importlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import (
    BT_MODULE_NAME,
    bt_available,
    bt_version,
    compare_weights,
    equity_from_returns,
    equity_to_rows,
    invariant_summary,
    returns_from_weights,
    turnover_from_weights,
    weights_to_rows,
)
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.bt_adapter_control_poc import (
    max_abs_series_diff,
    max_abs_turnover_diff,
    requirements_contains_bt,
    sanitize_payload,
    turnover_date_set,
)
from strategy_lab.research_os.research.global_multi_asset_etf_momentum_bounded_design import (
    FAMILY_ID,
    LANE_ID as SOURCE_LANE_ID,
    RANKED_ASSETS,
    REQUIRED_SYMBOLS,
)
from strategy_lab.research_os.research.global_multi_asset_etf_momentum_bounded_run import (
    global_tsmom_weights,
    normalize_target,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    cache_inventory,
    complete_rebalance_weight_frame,
    load_prices,
    month_rebalance_mask,
    write_csv,
)


OUTPUT_DIR = Path("evidence") / "research_recovery" / "bt_adapter_multasset_control_poc" / "latest"
SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "global_multi_asset_etf_momentum_bounded_run" / "latest"
SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "global_multi_asset_etf_momentum_bounded_design" / "latest"
)

POC_ID = "bt_adapter_multasset_global_tsmom_top2_control_poc_v1"
REFERENCE_TEMPLATE_ID = "global_tsmom_weights"
REFERENCE_VARIANT_ID = "gma_bounded_base_tsmom_top2_126_v1"
CONTROL_CONCEPT = "global_multi_asset_tsmom_top2_126_bil_fallback"
LOOKBACK_DAYS = 126
TOP_N = 2
WEIGHT_TOLERANCE = 1e-9

FINAL_DECISION_PASSED = "bt_adapter_multasset_control_poc_passed"
FINAL_DECISION_NEEDS_PATCH = "bt_adapter_multasset_control_poc_needs_patch"
FINAL_DECISION_BLOCKED = "bt_adapter_multasset_poc_blocked_no_reference_template"
VALID_FINAL_DECISIONS = {FINAL_DECISION_PASSED, FINAL_DECISION_NEEDS_PATCH, FINAL_DECISION_BLOCKED}

NEXT_ACTION_COMPARE = "compare_bt_multasset_adapter_vs_current_engine_on_existing_template"
NEXT_ACTION_PATCH = "patch_bt_adapter_multasset_control_poc"
NEXT_ACTION_BLOCKED = "select_existing_multasset_reference_template_for_bt_adapter_poc"
VALID_NEXT_ACTIONS = {NEXT_ACTION_COMPARE, NEXT_ACTION_PATCH, NEXT_ACTION_BLOCKED}

WEIGHT_FIELDS = ("date", *REQUIRED_SYMBOLS, "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "daily_return", "equity")
TURNOVER_FIELDS = ("date", "turnover_proxy")
CACHE_FIELDS = ("symbol", "path", "rows", "first_date", "last_date", "has_adj_close", "status", "used_by_poc")
SELECTION_FIELDS = (
    "date",
    "adapter_selected_assets",
    "reference_selected_assets",
    "selected_assets_match",
    "adapter_rank_order",
    "reference_rank_order",
    "adapter_target_weights",
    "reference_target_weights",
)

REQUIRED_FILES = (
    "bt_adapter_multasset_control_poc_manifest.json",
    "selected_reference_template_report.md",
    "adapter_spec_used.json",
    "adapter_spec_used.md",
    "package_dependency_report.json",
    "package_dependency_report.md",
    "local_cache_symbols_used.csv",
    "local_cache_symbols_used.md",
    "daily_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "selected_assets_ranking_comparison_report.csv",
    "selected_assets_ranking_comparison_report.md",
    "adapter_vs_reference_comparison_report.json",
    "adapter_vs_reference_comparison_report.md",
    "exposure_invariant_report.json",
    "exposure_invariant_report.md",
    "guardrail_checklist.json",
    "bt_adapter_multasset_control_poc_summary.md",
    "bt_adapter_multasset_control_poc_next_action.md",
    "bt_adapter_multasset_control_poc_consistency_check.json",
)


@dataclass(frozen=True)
class MultassetAdapterSpec:
    poc_id: str = POC_ID
    reference_template_id: str = REFERENCE_TEMPLATE_ID
    reference_variant_id: str = REFERENCE_VARIANT_ID
    family_id: str = FAMILY_ID
    source_lane_id: str = SOURCE_LANE_ID
    control_concept: str = CONTROL_CONCEPT
    symbols: tuple[str, ...] = REQUIRED_SYMBOLS
    ranked_assets: tuple[str, ...] = RANKED_ASSETS
    lookback_days: int = LOOKBACK_DAYS
    top_n: int = TOP_N
    rebalance_frequency: str = "monthly"
    bil_cash_rule: str = "BIL receives negative-score slots, missing slots, and any remainder"
    max_daily_exposure: float = 1.0
    max_daily_weight_sum: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "poc_id": self.poc_id,
            "reference_template_id": self.reference_template_id,
            "reference_variant_id": self.reference_variant_id,
            "family_id": self.family_id,
            "source_lane_id": self.source_lane_id,
            "control_concept": self.control_concept,
            "symbols": "|".join(self.symbols),
            "ranked_assets": "|".join(self.ranked_assets),
            "lookback_days": self.lookback_days,
            "top_n": self.top_n,
            "rebalance_frequency": self.rebalance_frequency,
            "bil_cash_rule": self.bil_cash_rule,
            "max_daily_exposure": self.max_daily_exposure,
            "max_daily_weight_sum": self.max_daily_weight_sum,
            "adapter_verification_only": True,
            "strategy_performance_evidence": False,
        }


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_safe_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, sanitize_payload(payload))


def load_aligned_prices(root: Path, spec: MultassetAdapterSpec) -> pd.DataFrame:
    prices = load_prices(root, spec.symbols).sort_index()
    if prices.empty:
        return pd.DataFrame()
    return prices.loc[prices[list(spec.symbols)].notna().all(axis=1), list(spec.symbols)].copy()


def cache_rows(root: Path, spec: MultassetAdapterSpec) -> list[dict[str, Any]]:
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
    return sorted(rows, key=lambda row: spec.symbols.index(row["symbol"]) if row["symbol"] in spec.symbols else 999)


def dependency_payload(root: Path) -> dict[str, Any]:
    return {
        "package": "bt",
        "module_name": BT_MODULE_NAME,
        "available_in_current_venv": bt_available(),
        "version": bt_version(),
        "install_attempted_in_this_step": False,
        "dependency_file_modified_in_this_step": False,
        "requirements_contains_bt": requirements_contains_bt(root),
        "forbidden_strategy_libraries_installed_by_this_step": False,
        "dependency_note": "bt was already added and installed by the prior authorized control POC step.",
    }


def target_payload(weights: dict[str, float]) -> str:
    return json.dumps({key: round(float(value), 10) for key, value in weights.items() if abs(float(value)) > 1e-12}, sort_keys=True)


def selected_assets_from_weights(weights: dict[str, float]) -> list[str]:
    return [symbol for symbol, value in weights.items() if symbol != "BIL" and float(value) > 1e-12]


def score_and_target(
    scores: pd.DataFrame,
    date: pd.Timestamp,
    columns: list[str],
    *,
    top_n: int,
) -> tuple[dict[str, float], list[str], list[str]]:
    target = {symbol: 0.0 for symbol in columns}
    if date not in scores.index:
        target["BIL"] = 1.0
        return target, [], []
    score_row = scores.loc[date].dropna().sort_values(ascending=False)
    rank_order = [str(symbol) for symbol in score_row.index]
    selected = list(score_row.head(top_n).index)
    slot = 1.0 / max(top_n, 1)
    for symbol in selected:
        if float(score_row.get(symbol, float("nan"))) > 0.0:
            target[str(symbol)] += slot
        else:
            target["BIL"] += slot
    target["BIL"] += slot * max(0, top_n - len(selected))
    clean = normalize_target(target, columns)
    return clean, [str(symbol) for symbol in selected], rank_order


def reference_selection_rows(prices: pd.DataFrame, spec: MultassetAdapterSpec) -> dict[str, dict[str, Any]]:
    columns = list(spec.symbols)
    scores = prices[list(spec.ranked_assets)].pct_change(spec.lookback_days, fill_method=None).shift(1)
    rows: dict[str, dict[str, Any]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        target, selected, rank_order = score_and_target(scores, pd.Timestamp(date), columns, top_n=spec.top_n)
        rows[pd.Timestamp(date).date().isoformat()] = {
            "date": pd.Timestamp(date).date().isoformat(),
            "reference_selected_assets": "|".join(selected_assets_from_weights(target)),
            "reference_rank_order": "|".join(rank_order),
            "reference_target_weights": target_payload(target),
        }
    return rows


def run_bt_multasset_template(prices: pd.DataFrame, spec: MultassetAdapterSpec) -> dict[str, Any]:
    if not bt_available():
        return {"bt_ran": False, "error": "bt package is unavailable"}
    bt = importlib.import_module(BT_MODULE_NAME)
    columns = list(spec.symbols)
    scores = prices[list(spec.ranked_assets)].pct_change(spec.lookback_days, fill_method=None).shift(1)
    recorded_targets: dict[pd.Timestamp, dict[str, float]] = {}
    recorded_rows: dict[str, dict[str, Any]] = {}

    class ProjectGlobalTopNBilFallback(bt.Algo):
        def __call__(self, target: Any) -> bool:
            date = pd.Timestamp(target.now)
            target_weights, selected, rank_order = score_and_target(scores, date, columns, top_n=spec.top_n)
            recorded_targets[date] = target_weights
            recorded_rows[date.date().isoformat()] = {
                "date": date.date().isoformat(),
                "adapter_selected_assets": "|".join(selected_assets_from_weights(target_weights)),
                "adapter_rank_order": "|".join(rank_order),
                "adapter_target_weights": target_payload(target_weights),
            }
            target.temp["selected"] = [symbol for symbol, value in target_weights.items() if float(value) > 0.0]
            target.temp["weights"] = {symbol: value for symbol, value in target_weights.items() if float(value) > 0.0}
            return True

    strategy = bt.Strategy(
        spec.poc_id,
        [
            bt.algos.RunMonthly(),
            ProjectGlobalTopNBilFallback(),
            bt.algos.Rebalance(),
        ],
    )
    result = bt.run(bt.Backtest(strategy, prices))
    target_weights = complete_rebalance_weight_frame(prices.index, columns, recorded_targets)
    security_weights = pd.DataFrame()
    for accessor in ("get_security_weights", "get_weights"):
        candidate = getattr(result, accessor, None)
        if callable(candidate):
            maybe = candidate()
            if isinstance(maybe, pd.DataFrame) and not maybe.empty:
                security_weights = maybe.reindex(prices.index).ffill().fillna(0.0)
                break
    return {
        "bt_ran": True,
        "bt_result_type": type(result).__name__,
        "bt_weights": target_weights,
        "bt_security_weights": security_weights,
        "selection_rows": recorded_rows,
    }


def reference_weights(prices: pd.DataFrame, spec: MultassetAdapterSpec) -> pd.DataFrame:
    return global_tsmom_weights(prices, lookback=spec.lookback_days, top_n=spec.top_n)


def selection_comparison_rows(
    adapter_rows: dict[str, dict[str, Any]],
    reference_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date in sorted(set(adapter_rows) | set(reference_rows)):
        adapter = adapter_rows.get(date, {"date": date})
        reference = reference_rows.get(date, {"date": date})
        rows.append(
            {
                "date": date,
                "adapter_selected_assets": adapter.get("adapter_selected_assets", ""),
                "reference_selected_assets": reference.get("reference_selected_assets", ""),
                "selected_assets_match": adapter.get("adapter_selected_assets", "")
                == reference.get("reference_selected_assets", ""),
                "adapter_rank_order": adapter.get("adapter_rank_order", ""),
                "reference_rank_order": reference.get("reference_rank_order", ""),
                "adapter_target_weights": adapter.get("adapter_target_weights", ""),
                "reference_target_weights": reference.get("reference_target_weights", ""),
            }
        )
    return rows


def cache_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Symbols Used", ""]
    for row in rows:
        lines.append(f"- `{row['symbol']}`: `{row['status']}`, `{row['first_date']}` to `{row['last_date']}`")
    return "\n".join(lines) + "\n"


def selected_reference_md(root: Path, prices: pd.DataFrame, source_available: bool) -> str:
    return f"""# Selected Reference Template Report

Selected template: `{REFERENCE_TEMPLATE_ID}`

Reference variant ID: `{REFERENCE_VARIANT_ID}`

Source family: `{FAMILY_ID}`

Source lane: `{SOURCE_LANE_ID}`

Reason selected:

- Existing current-engine implementation under `global_multi_asset_etf_momentum_bounded_run.py`.
- Multi-asset universe: `{len(REQUIRED_SYMBOLS)}` symbols.
- Ranking/top-N selection: `top {TOP_N}` by `{LOOKBACK_DAYS}` trading-day momentum.
- Periodic rebalance: monthly.
- BIL/cash fallback: negative-score and missing selection slots route to `BIL`.
- Existing source run evidence available: `{source_available}`.

Effective adapter/reference date range:

- Start: `{pd.Timestamp(prices.index.min()).date().isoformat() if not prices.empty else 'not_available'}`
- End: `{pd.Timestamp(prices.index.max()).date().isoformat() if not prices.empty else 'not_available'}`
- Rows: `{len(prices)}`

This template is used only as deterministic adapter-reference mechanics. It is not being rescued, promoted, or reinterpreted as strategy performance evidence.
"""


def dependency_md(payload: dict[str, Any]) -> str:
    return f"""# Package Dependency Report

Package: `{payload['package']}`

Available in current virtualenv: `{payload['available_in_current_venv']}`

Version: `{payload['version']}`

Installed in this step: `{payload['install_attempted_in_this_step']}`

Dependency file modified in this step: `{payload['dependency_file_modified_in_this_step']}`

Requirements contains bt: `{payload['requirements_contains_bt']}`

Forbidden strategy libraries installed by this step: `{payload['forbidden_strategy_libraries_installed_by_this_step']}`

Note: `{payload['dependency_note']}`
"""


def adapter_spec_md(spec: MultassetAdapterSpec) -> str:
    lines = ["# Adapter Spec Used", ""]
    for key, value in spec.to_dict().items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def selection_md(rows: list[dict[str, Any]]) -> str:
    mismatches = [row for row in rows if str(row.get("selected_assets_match")).lower() != "true"]
    return f"""# Selected Assets / Ranking Comparison

Rows compared: `{len(rows)}`

Selection mismatches: `{len(mismatches)}`

The adapter records selected assets and rank order at monthly rebalance dates. This is a mechanics check only.
"""


def comparison_md(payload: dict[str, Any]) -> str:
    return f"""# Adapter vs Reference Comparison

Comparison performed: `{payload['comparison_performed']}`

Status: `{payload['comparison_status']}`

Effective start date: `{payload.get('effective_start_date', 'not_available')}`

Effective end date: `{payload.get('effective_end_date', 'not_available')}`

Rows compared: `{payload['row_count_compared']}`

Maximum absolute target-weight difference: `{payload['max_abs_weight_difference']}`

Selected/ranking rows compared: `{payload.get('selection_rows_compared', 'not_available')}`

Selected/ranking mismatches: `{payload.get('selection_mismatch_count', 'not_available')}`

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

Average weight sum: `{payload['average_weight_sum']}`

Weight sum violations: `{payload['weight_sum_violation_count']}`

Negative weight violations: `{payload['negative_weight_violation_count']}`

NaN weight count: `{payload['nan_weight_count']}`

Impossible BIL/cash plus risky exposure days: `{payload['impossible_cash_and_risky_exposure_days']}`
"""


def turnover_md(rows: list[dict[str, Any]]) -> str:
    return f"""# Rebalance / Turnover Report

Rows exported: `{len(rows)}`

Turnover is reconstructed from project-compatible daily target weights.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# bt Adapter Multasset Control POC

Final adapter decision: `{manifest['final_adapter_decision']}`

Reference template: `{manifest['reference_template_id']}`

Control concept: `{manifest['control_concept']}`

bt package available: `{manifest['bt_package_available']}`

bt package version: `{manifest['bt_package_version']}`

Adapter execution attempted: `{manifest['adapter_execution_attempted']}`

bt Algo composition run: `{manifest['bt_algo_composition_run']}`

Reference comparison performed: `{manifest['reference_comparison_performed']}`

Exposure invariant checked: `{manifest['exposure_invariant_checked']}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Selected/ranking comparison performed: `{manifest['selected_assets_ranking_comparison_performed']}`

Adapter outputs created: `{manifest['adapter_outputs_created']}`

Performance evidence created: `{manifest['performance_evidence_created']}`

Interpretation:

- This POC verifies `bt` adapter mechanics on an existing project multi-asset/top-N/BIL template.
- No public strategy was implemented.
- No strategy discovery or broad research batch was run.
- Current-engine output remains the validation authority.
- No POC output is strategy performance evidence, promotable, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "bt_adapter_multasset_control_poc_only",
        "new_public_strategy_implemented",
        "public_source_scraped",
        "provider_download",
        "intraday_data_used",
        "strategy_discovery_run",
        "broad_research_batch_run",
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
        "forbidden_strategy_libraries_installed",
    ]
    return {key: manifest[key] for key in keys}


def next_action_md(next_action: str) -> str:
    return f"""# bt Adapter Multasset Control POC Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    spec: MultassetAdapterSpec,
    dep: dict[str, Any],
    prices: pd.DataFrame,
    source_template_available: bool,
    final_decision: str,
    next_action: str,
    adapter_execution_attempted: bool,
    bt_algo_composition_run: bool,
    adapter_outputs_created: bool,
    reference_comparison_performed: bool,
    exposure_invariant_checked: bool,
    exposure_invariant_passed: bool,
    selection_comparison_performed: bool,
) -> dict[str, Any]:
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "bt_adapter_multasset_control_poc": True,
        "bt_adapter_multasset_control_poc_only": True,
        "poc_id": spec.poc_id,
        "selected_existing_template": True,
        "source_template_available": source_template_available,
        "reference_template_id": spec.reference_template_id,
        "reference_variant_id": spec.reference_variant_id,
        "source_family_id": spec.family_id,
        "source_lane_id": spec.source_lane_id,
        "control_concept": spec.control_concept,
        "lookback_days": spec.lookback_days,
        "top_n": spec.top_n,
        "rebalance_frequency": spec.rebalance_frequency,
        "bt_package_available": dep["available_in_current_venv"],
        "bt_package_version": dep["version"],
        "package_install_attempted_in_this_step": False,
        "dependency_file_modified_in_this_step": False,
        "requirements_contains_bt": dep["requirements_contains_bt"],
        "forbidden_strategy_libraries_installed": False,
        "local_cache_loaded": not prices.empty,
        "local_cache_row_count": int(len(prices)),
        "local_cache_symbols_used": list(spec.symbols),
        "adapter_execution_attempted": adapter_execution_attempted,
        "bt_algo_composition_run": bt_algo_composition_run,
        "adapter_outputs_created": adapter_outputs_created,
        "reference_comparison_performed": reference_comparison_performed,
        "selected_assets_ranking_comparison_performed": selection_comparison_performed,
        "exposure_invariant_checked": exposure_invariant_checked,
        "exposure_invariant_passed": exposure_invariant_passed,
        "new_public_strategy_implemented": False,
        "public_source_scraped": False,
        "provider_download": False,
        "intraday_data_used": False,
        "strategy_discovery_run": False,
        "new_strategy_discovery_run": False,
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
        "final_adapter_decision": final_decision,
        "next_action": next_action,
    }


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["bt_adapter_multasset_control_poc_consistency_check.json"] = True
    blocked = manifest["final_adapter_decision"] == FINAL_DECISION_BLOCKED
    checks = {
        "poc_only": manifest["bt_adapter_multasset_control_poc_only"] is True,
        "existing_template_selected": manifest["selected_existing_template"] is True,
        "source_template_available": manifest["source_template_available"] is True,
        "bt_dependency_available": manifest["bt_package_available"] is True
        and manifest["requirements_contains_bt"] is True,
        "no_install_or_dependency_edit_this_step": manifest["package_install_attempted_in_this_step"] is False
        and manifest["dependency_file_modified_in_this_step"] is False,
        "blocked_state_valid": (
            manifest["source_template_available"] is False
            and manifest["adapter_execution_attempted"] is False
            and manifest["final_adapter_decision"] == FINAL_DECISION_BLOCKED
        )
        if blocked
        else True,
        "adapter_ran": manifest["adapter_execution_attempted"] is True
        and manifest["bt_algo_composition_run"] is True,
        "comparison_performed": manifest["reference_comparison_performed"] is True
        and manifest["selected_assets_ranking_comparison_performed"] is True,
        "invariants_checked": manifest["exposure_invariant_checked"] is True,
        "no_strategy_research_or_scrape": manifest["new_public_strategy_implemented"] is False
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
    spec = MultassetAdapterSpec()
    dep = dependency_payload(root)
    prices = load_aligned_prices(root, spec)
    source_template_available = (root / SOURCE_RUN_DIR / "global_multi_asset_bounded_row_results.csv").exists()

    final_decision = FINAL_DECISION_NEEDS_PATCH
    next_action = NEXT_ACTION_PATCH
    adapter_execution_attempted = False
    bt_algo_composition_run = False
    adapter_outputs_created = False
    reference_comparison_performed = False
    exposure_invariant_checked = False
    exposure_invariant_passed = False
    selection_comparison_performed = False

    weights_rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    comparison: dict[str, Any] = {
        "comparison_performed": False,
        "comparison_status": "not_performed",
        "row_count_compared": 0,
        "max_abs_weight_difference": None,
        "comparison_interpretation": "Comparison not performed.",
    }
    invariant: dict[str, Any] = {
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

    if not source_template_available or prices.empty or not dep["available_in_current_venv"]:
        final_decision = FINAL_DECISION_BLOCKED
        next_action = NEXT_ACTION_BLOCKED
    else:
        adapter_execution_attempted = True
        try:
            bt_result = run_bt_multasset_template(prices, spec)
            bt_algo_composition_run = bool(bt_result.get("bt_ran"))
            adapter_weights = bt_result["bt_weights"]
            adapter_security_weights = bt_result["bt_security_weights"]
            current_engine_weights = reference_weights(prices, spec)
            comparison = compare_weights(adapter_weights, current_engine_weights)
            reference_comparison_performed = bool(comparison["comparison_performed"])
            reference_returns = returns_from_weights(prices, current_engine_weights)
            reference_equity = equity_from_returns(reference_returns)
            adapter_returns = returns_from_weights(prices, adapter_weights)
            adapter_equity = equity_from_returns(adapter_returns)
            reference_turnover_rows = turnover_from_weights(current_engine_weights).to_dict(orient="records")
            turnover_rows = turnover_from_weights(adapter_weights).to_dict(orient="records")
            reference_selection = reference_selection_rows(prices, spec)
            selection_rows = selection_comparison_rows(bt_result["selection_rows"], reference_selection)
            selection_comparison_performed = bool(selection_rows)
            selection_mismatch_count = sum(
                1 for row in selection_rows if str(row.get("selected_assets_match")).lower() != "true"
            )
            security_weight_comparison = compare_weights(adapter_security_weights, current_engine_weights)
            invariant = {"exposure_invariant_checked": True, **invariant_summary(adapter_weights)}
            exposure_invariant_checked = True
            exposure_invariant_passed = bool(invariant["exposure_invariant_passed"])
            weights_rows = weights_to_rows(adapter_weights)
            equity_rows = equity_to_rows(adapter_returns, adapter_equity)
            adapter_outputs_created = bool(weights_rows and equity_rows)
            comparison.update(
                {
                    "effective_start_date": pd.Timestamp(prices.index.min()).date().isoformat(),
                    "effective_end_date": pd.Timestamp(prices.index.max()).date().isoformat(),
                    "selection_rows_compared": len(selection_rows),
                    "selection_mismatch_count": selection_mismatch_count,
                    "adapter_rebalance_or_turnover_event_count": len(turnover_rows),
                    "reference_rebalance_or_turnover_event_count": len(reference_turnover_rows),
                    "rebalance_dates_matched": turnover_date_set(turnover_rows)
                    == turnover_date_set(reference_turnover_rows),
                    "turnover_dates_matched": turnover_date_set(turnover_rows)
                    == turnover_date_set(reference_turnover_rows),
                    "max_abs_daily_return_difference": max_abs_series_diff(adapter_returns, reference_returns),
                    "max_abs_equity_difference": max_abs_series_diff(adapter_equity, reference_equity),
                    "max_abs_turnover_difference": max_abs_turnover_diff(turnover_rows, reference_turnover_rows),
                    "bt_security_weight_export_status": security_weight_comparison["comparison_status"],
                    "bt_security_weight_max_abs_difference": security_weight_comparison[
                        "max_abs_weight_difference"
                    ],
                    "bt_security_weight_interpretation": (
                        "bt security/account weights can drift between rebalances; this POC validates recorded "
                        "target weights against current-engine target weights."
                    ),
                }
            )
            exact_match = (
                comparison["comparison_status"] == "matched"
                and comparison["max_abs_daily_return_difference"] <= WEIGHT_TOLERANCE
                and comparison["max_abs_equity_difference"] <= WEIGHT_TOLERANCE
                and comparison["max_abs_turnover_difference"] <= WEIGHT_TOLERANCE
                and selection_mismatch_count == 0
                and exposure_invariant_passed
            )
            comparison["comparison_interpretation"] = (
                "bt-recorded multasset target weights, selected assets, returns/equity, and turnover matched "
                "the current-engine global_tsmom_weights reference."
                if exact_match
                else "bt ran, but one or more adapter-vs-reference equivalence checks failed."
            )
            final_decision = FINAL_DECISION_PASSED if exact_match else FINAL_DECISION_NEEDS_PATCH
            next_action = NEXT_ACTION_COMPARE if exact_match else NEXT_ACTION_PATCH
        except Exception as exc:  # pragma: no cover - defensive adapter evidence path.
            final_decision = FINAL_DECISION_NEEDS_PATCH
            next_action = NEXT_ACTION_PATCH
            comparison = {
                "comparison_performed": False,
                "comparison_status": "not_performed_adapter_error",
                "row_count_compared": 0,
                "max_abs_weight_difference": None,
                "comparison_interpretation": f"Adapter run failed before validation: {exc}",
            }

    manifest = manifest_payload(
        created=created,
        output=output,
        spec=spec,
        dep=dep,
        prices=prices,
        source_template_available=source_template_available,
        final_decision=final_decision,
        next_action=next_action,
        adapter_execution_attempted=adapter_execution_attempted,
        bt_algo_composition_run=bt_algo_composition_run,
        adapter_outputs_created=adapter_outputs_created,
        reference_comparison_performed=reference_comparison_performed,
        exposure_invariant_checked=exposure_invariant_checked,
        exposure_invariant_passed=exposure_invariant_passed,
        selection_comparison_performed=selection_comparison_performed,
    )

    write_safe_json(output / "bt_adapter_multasset_control_poc_manifest.json", manifest)
    write_text(output / "selected_reference_template_report.md", selected_reference_md(root, prices, source_template_available))
    write_safe_json(output / "adapter_spec_used.json", spec.to_dict())
    write_text(output / "adapter_spec_used.md", adapter_spec_md(spec))
    write_safe_json(output / "package_dependency_report.json", dep)
    write_text(output / "package_dependency_report.md", dependency_md(dep))
    rows = cache_rows(root, spec)
    write_csv(output / "local_cache_symbols_used.csv", rows, list(CACHE_FIELDS))
    write_text(output / "local_cache_symbols_used.md", cache_md(rows))
    write_csv(output / "daily_weights.csv", weights_rows, list(WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows, list(EQUITY_FIELDS))
    write_csv(output / "rebalance_turnover_report.csv", turnover_rows, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_md(turnover_rows))
    write_csv(output / "selected_assets_ranking_comparison_report.csv", selection_rows, list(SELECTION_FIELDS))
    write_text(output / "selected_assets_ranking_comparison_report.md", selection_md(selection_rows))
    write_safe_json(output / "adapter_vs_reference_comparison_report.json", comparison)
    write_text(output / "adapter_vs_reference_comparison_report.md", comparison_md(comparison))
    write_safe_json(output / "exposure_invariant_report.json", invariant)
    write_text(output / "exposure_invariant_report.md", invariant_md(invariant))
    write_safe_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "bt_adapter_multasset_control_poc_summary.md", summary_md(manifest))
    write_text(output / "bt_adapter_multasset_control_poc_next_action.md", next_action_md(next_action))
    check = consistency_check(manifest, output)
    write_safe_json(output / "bt_adapter_multasset_control_poc_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}

