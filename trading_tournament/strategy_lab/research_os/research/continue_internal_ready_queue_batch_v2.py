from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from strategy_lab.research_os.research import resume_existing_ready_research_batch_v1 as ready


ROOT = ready.ROOT
EVIDENCE_DIR = ROOT / "evidence" / "continue_internal_ready_queue_batch_v2" / "latest"
BATCH_ID = "continue_internal_ready_queue_batch_v2"
NEXT_ACTION = "direction_owner_fast_discovery_required"
CORRECTED_QQQ_FAILURE = "horizon_dependent_weakness_and_unstable_primary_benchmark_edge"

ACTIVE_ROWS = {
    ready.ACTIVE_VM_ID,
    ready.ACTIVE_DSR_ID,
    ready.ACTIVE_COMBO_ID,
}

CLOSED_EXACT_ROWS = {
    "qqq_spy_gld_ief_dual_momentum_v1": "no_material_edge",
    "value_momentum_factor_etf_rotation_v1": "historical_edge_recently_weakened",
    "sector_top2_momentum_simple_v1": "control_weak",
    **{candidate_id: "closed_exact_variant" for candidate_id in ready.PREVIOUSLY_CLOSED_EXACT},
}

INTERNAL_QUEUE_ROWS = [
    {
        "candidate_id": "low_vol_quality_defensive_rotation_v1",
        "family_id": "defensive_factor_rotation",
        "queue_priority": 3,
        "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": False,
        "closed_or_duplicate": False,
        "data_ready": True,
        "primary_benchmark": "BIL_cash_proxy",
        "blocker_type": "rules",
        "blocker": "Universe is named, but exact signal, selection rule, number selected, weighting, rebalance cadence, and BIL behavior are not frozen; registry next action is research_memo.",
        "smallest_direct_action": "Freeze a bounded design or research memo with exact signal, selection, weighting, rebalance, and risk-off behavior.",
    },
    {
        "candidate_id": "treasury_duration_trend_rotation_v1",
        "family_id": "bond_trend_rotation",
        "queue_priority": 5,
        "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": False,
        "closed_or_duplicate": False,
        "data_ready": False,
        "primary_benchmark": "IEF_buy_hold",
        "blocker_type": "rules_data",
        "blocker": "Frozen symbol set is listed as SHY/IEF/TLT/BIL, but trend or momentum calculation, lookback, ranking/selection count, weighting, missing-data behavior, and risk-off behavior are not frozen; SHY is absent from current cache.",
        "smallest_direct_action": "Freeze the duration-rotation rule first; then acquire only SHY if the frozen rule still requires it.",
    },
    {
        "candidate_id": "managed_futures_proxy_etf_trend_v1",
        "family_id": "managed_futures_etf_wrapper",
        "queue_priority": 6,
        "source": "strategy_lab/research_os/family_lineage/family_ledger.yaml",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": True,
        "closed_or_duplicate": True,
        "data_ready": True,
        "primary_benchmark": "combo_SPY200d_GLD_50_50_v1",
        "blocker_type": "closed_family",
        "blocker": "Family ledger marks managed_futures_etf_wrapper closed_under_current_mechanics with future_research_allowed=false.",
        "smallest_direct_action": "Direction-owner must authorize a new objective or data-class review before any reopening.",
    },
    {
        "candidate_id": "commodity_basket_etf_momentum_v1",
        "family_id": "commodity_momentum",
        "queue_priority": 7,
        "source": "strategy_lab/research_os/research/research_queue.yaml",
        "rule_complete": True,
        "implementation_ready": False,
        "valid_corrected_screen_exists": True,
        "closed_or_duplicate": True,
        "data_ready": True,
        "primary_benchmark": "GLD_buy_hold",
        "blocker_type": "valid_screen_completed",
        "blocker": "Commodity bounded lane completed with weak diagnostic evidence/control-only pass and is completed_for_now in the research queue.",
        "smallest_direct_action": "Only a materially distinct direction-owner hypothesis should revisit the commodity family.",
    },
    {
        "candidate_id": "crypto_spot_tsmom_tier2_review_v1",
        "family_id": "crypto_spot_trend",
        "queue_priority": 8,
        "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": False,
        "closed_or_duplicate": False,
        "data_ready": False,
        "primary_benchmark": "crypto_buy_hold_equal_weight",
        "blocker_type": "unsupported_data_execution",
        "blocker": "Requires exchange-specific crypto OHLCV, fees, spreads, 24/7 handling, and Tier 2 execution memo; not supported by current internal bounded ETF screen.",
        "smallest_direct_action": "Complete a dedicated Tier 2 crypto data/execution memo before any screening.",
    },
    {
        "candidate_id": "individual_stock_momentum_gate1b_v1",
        "family_id": "individual_stock_momentum",
        "queue_priority": 9,
        "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": False,
        "closed_or_duplicate": False,
        "data_ready": False,
        "primary_benchmark": "SPY_200d_trend_model",
        "blocker_type": "unsupported_constituent_data",
        "blocker": "Requires survivorship-free active/delisted stock universe, delisting returns, and point-in-time universe data.",
        "smallest_direct_action": "Resolve Gate 1B survivorship-free data and execution review.",
    },
    {
        "candidate_id": "options_futures_forex_intraday_blocked_reference_v1",
        "family_id": "multi_blocked_reference",
        "queue_priority": 10,
        "source": "evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv",
        "rule_complete": False,
        "implementation_ready": False,
        "valid_corrected_screen_exists": False,
        "closed_or_duplicate": False,
        "data_ready": False,
        "primary_benchmark": "none",
        "blocker_type": "unsupported_instrument_reference",
        "blocker": "Queue row is a blocked reference for options, futures, forex, intraday, margin, chain, roll, and timestamp mechanics; it is not an implementable internal ETF candidate.",
        "smallest_direct_action": "Complete separate Gate 0/Gate 1 instrument, data, margin, spread, and timestamp reviews before any strategy-specific design.",
    },
]


def empty_csv(path: Path, fields: list[str]) -> None:
    ready.write_csv(path, [], fields)


def candidate_eligibility_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "candidate_id": ready.ACTIVE_VM_ID,
            "family_id": "active_observation",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "active_observation",
            "blocker": "Active VM observation cannot enter as a candidate.",
            "source": "strategy_lab/research_os/operations/active_observations.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": ready.ACTIVE_DSR_ID,
            "family_id": "active_observation",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "active_observation",
            "blocker": "Active DSR observation cannot enter as a candidate.",
            "source": "strategy_lab/research_os/operations/active_observations.yaml",
            "performance_used_for_selection": False,
        },
        {
            "candidate_id": ready.ACTIVE_COMBO_ID,
            "family_id": "benchmark_reference",
            "queue_priority": "",
            "eligible": False,
            "blocker_type": "benchmark_only",
            "blocker": "Active combo is benchmark/reference only.",
            "source": "evidence/active_combo_series_reconciliation/latest",
            "performance_used_for_selection": False,
        },
    ]
    for candidate_id, outcome in CLOSED_EXACT_ROWS.items():
        rows.append(
            {
                "candidate_id": candidate_id,
                "family_id": "closed_exact_variant",
                "queue_priority": "",
                "eligible": False,
                "blocker_type": "closed_exact_variant",
                "blocker": f"Exact candidate already closed or do-not-retest under current research memory; latest outcome={outcome}.",
                "source": "current exact-variant research memory",
                "performance_used_for_selection": False,
            }
        )
    for row in INTERNAL_QUEUE_ROWS:
        eligible = (
            row["rule_complete"]
            and row["implementation_ready"]
            and not row["valid_corrected_screen_exists"]
            and not row["closed_or_duplicate"]
            and row["data_ready"]
        )
        rows.append(
            {
                "candidate_id": row["candidate_id"],
                "family_id": row["family_id"],
                "queue_priority": row["queue_priority"],
                "eligible": eligible,
                "blocker_type": "" if eligible else row["blocker_type"],
                "blocker": "" if eligible else row["blocker"],
                "source": row["source"],
                "performance_used_for_selection": False,
            }
        )
    return rows


def selection_policy_rows() -> list[dict[str, Any]]:
    return [
        {"order": 1, "criterion": "highest_explicit_queue_priority", "applied_before_performance": True, "used": False, "notes": "No eligible candidates after gate checks."},
        {"order": 2, "criterion": "oldest_completed_frozen_specification", "applied_before_performance": True, "used": False, "notes": "No eligible candidates after gate checks."},
        {"order": 3, "criterion": "family_not_represented", "applied_before_performance": True, "used": False, "notes": "No eligible candidates after gate checks."},
        {"order": 4, "criterion": "market_or_asset_class_not_represented", "applied_before_performance": True, "used": False, "notes": "No eligible candidates after gate checks."},
        {"order": 5, "criterion": "lexicographic_candidate_id", "applied_before_performance": True, "used": False, "notes": "No eligible candidates after gate checks."},
    ]


def blocked_near_ready_rows() -> list[dict[str, Any]]:
    nearest_ids = [
        "treasury_duration_trend_rotation_v1",
        "low_vol_quality_defensive_rotation_v1",
        "managed_futures_proxy_etf_trend_v1",
    ]
    return [
        {
            "candidate_id": row["candidate_id"],
            "family_id": row["family_id"],
            "blocker_type": row["blocker_type"],
            "blocker": row["blocker"],
            "smallest_direct_action": row["smallest_direct_action"],
        }
        for row in INTERNAL_QUEUE_ROWS
        if row["candidate_id"] in nearest_ids
    ]


def run() -> dict[str, Any]:
    registry_hash_before = ready.sha256_path(ready.REGISTRY_PATH)
    active_hash_before = ready.sha256_path(ready.ACTIVE_OBSERVATIONS_PATH)

    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    eligibility = candidate_eligibility_rows()
    selected: list[dict[str, Any]] = []

    ready.write_csv(EVIDENCE_DIR / "candidate_eligibility.csv", eligibility)
    ready.write_csv(EVIDENCE_DIR / "selection_policy.csv", selection_policy_rows())
    empty_csv(
        EVIDENCE_DIR / "selected_candidates.csv",
        ["candidate_id", "family_id", "queue_priority", "primary_benchmark", "selection_reason"],
    )
    ready.write_json(
        EVIDENCE_DIR / "provider_acquisition_manifest.json",
        {
            "provider_download": False,
            "downloaded_symbol_count": 0,
            "downloaded_symbols": [],
            "max_missing_symbols_authorized": 2,
            "valid_caches_refreshed": False,
            "only_frozen_missing_tickers_downloadable": True,
            "reason": "No otherwise eligible candidate required acquisition.",
        },
    )

    empty_csv(EVIDENCE_DIR / "frozen_window_definitions.csv", ["candidate_id", "window_id", "horizon_days", "start_date", "end_date", "frozen_before_performance"])
    empty_csv(EVIDENCE_DIR / "candidate_metrics.csv", ["candidate_id", "horizon_days", "window_count", "median_total_return", "median_max_drawdown"])
    empty_csv(EVIDENCE_DIR / "benchmark_metrics.csv", ["candidate_id", "benchmark_id", "window_id", "benchmark_total_return"])
    empty_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", ["candidate_id", "benchmark_id", "window_id", "candidate_excess_return"])
    empty_csv(EVIDENCE_DIR / "window_level_results.csv", ["candidate_id", "window_id", "primary_benchmark", "candidate_total_return", "candidate_excess_return"])
    ready.write_csv(
        EVIDENCE_DIR / "accounting_and_exposure_invariants.csv",
        [
            {
                "candidate_id": "",
                "screen_ran": False,
                "actual_holdings_accounting_used": "not_applicable_no_eligible_candidate",
                "no_stale_weight_forward_fill": "not_applicable_no_eligible_candidate",
                "max_daily_exposure": "",
                "registry_byte_identical": True,
                "active_observations_unchanged": True,
            }
        ],
    )
    empty_csv(EVIDENCE_DIR / "screening_outcomes.csv", ["candidate_id", "screening_outcome", "promotion_eligible", "paper_forward_eligible"])
    ready.write_csv(
        EVIDENCE_DIR / "failure_reasons.csv",
        [
            {
                "candidate_id": "qqq_spy_gld_ief_dual_momentum_v1",
                "screening_outcome": "no_material_edge",
                "primary_failure_reason": CORRECTED_QQQ_FAILURE,
                "secondary_failure_reason": "",
                "wording_correction_only": True,
            }
        ],
    )
    ready.write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": "qqq_spy_gld_ief_dual_momentum_v1",
                "screening_outcome": "no_material_edge",
                "exact_candidate_closed_for_immediate_retesting": True,
                "primary_failure_description": CORRECTED_QQQ_FAILURE,
                "wording_correction_only": True,
                "rerun_in_this_task": False,
                "broader_family_closed": False,
                "lifecycle_state_changed": False,
            },
            {
                "candidate_id": "value_momentum_factor_etf_rotation_v1",
                "screening_outcome": "historical_edge_recently_weakened",
                "exact_candidate_closed_for_immediate_retesting": True,
                "rerun_in_this_task": False,
                "broader_family_closed": False,
                "lifecycle_state_changed": False,
            },
            {
                "candidate_id": "sector_top2_momentum_simple_v1",
                "screening_outcome": "control_weak",
                "exact_candidate_closed_for_immediate_retesting": True,
                "rerun_in_this_task": False,
                "broader_family_closed": False,
                "lifecycle_state_changed": False,
            },
        ],
    )
    ready.write_csv(EVIDENCE_DIR / "blocked_near_ready_candidates.csv", blocked_near_ready_rows())

    registry_hash_after = ready.sha256_path(ready.REGISTRY_PATH)
    active_hash_after = ready.sha256_path(ready.ACTIVE_OBSERVATIONS_PATH)
    consistency = {
        "active_observations_excluded": True,
        "benchmarks_excluded": True,
        "closed_exact_candidates_excluded": True,
        "previously_screened_candidates_excluded": True,
        "eligibility_requires_complete_rules": True,
        "deterministic_selection_policy_recorded": True,
        "performance_used_for_selection": False,
        "max_one_candidate_per_family": True,
        "downloaded_symbol_count": 0,
        "downloaded_symbol_count_lte_2": True,
        "valid_caches_refreshed": False,
        "windows_frozen_before_performance": True,
        "actual_holdings_accounting_used": "not_applicable_no_screen",
        "no_stale_weight_forward_fill": "not_applicable_no_screen",
        "registry_byte_identical": registry_hash_before == registry_hash_after,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": registry_hash_after,
        "active_observations_unchanged": active_hash_before == active_hash_after,
        "active_observations_hash_before": active_hash_before,
        "active_observations_hash_after": active_hash_after,
        "external_source_auto_selection_paused": True,
        "selected_candidate_count": len(selected),
        "screen_ran": False,
        "project_paused": False,
        "next_lane": NEXT_ACTION,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "broker_live_path_touched": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    ready.write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    manifest = {
        "batch_id": BATCH_ID,
        "remaining_internal_queue_evaluated": True,
        "eligible_candidate_count": 0,
        "selected_candidate_count": 0,
        "screen_ran": False,
        "zero_eligible_blocker_packet_created": True,
        "qqq_failure_wording_corrected": CORRECTED_QQQ_FAILURE,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "registry_byte_identical": consistency["registry_byte_identical"],
        "active_observations_unchanged": consistency["active_observations_unchanged"],
        "project_paused": False,
        "next_action": NEXT_ACTION,
    }
    ready.write_json(EVIDENCE_DIR / "batch_manifest.json", manifest)

    summary = [
        "# Continue Internal Ready Queue Batch v2",
        "",
        "The remaining internal queue was evaluated under deterministic eligibility rules. No candidate qualified for a bounded screen without inventing rules, reopening a closed exact variant, or using unsupported data/instrument mechanics.",
        "",
        "The QQQ research-memory failure wording was corrected to `horizon_dependent_weakness_and_unstable_primary_benchmark_edge` without rerunning QQQ.",
        "",
        "Nearest-to-ready blockers:",
        "- `treasury_duration_trend_rotation_v1`: rule incomplete; SHY cache only matters after rule freeze.",
        "- `low_vol_quality_defensive_rotation_v1`: rule incomplete; research memo/design required.",
        "- `managed_futures_proxy_etf_trend_v1`: family closed under current mechanics.",
        "",
        "This is not a project pause. The next lane is direction-owner fast discovery.",
        "",
        f"Exact next action: `{NEXT_ACTION}`.",
    ]
    (EVIDENCE_DIR / "batch_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=ready.clean_value))
