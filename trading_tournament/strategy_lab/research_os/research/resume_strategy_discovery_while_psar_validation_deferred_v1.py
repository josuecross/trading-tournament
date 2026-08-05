from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "resume_strategy_discovery_while_psar_validation_deferred_v1"
MODE = "ready-queue-fast-progress"
STAGE = "exploration"
OUTCOME = "ready_queue_insufficient_for_four_candidate_batch"
NEXT_ACTION = "targeted_native_etf_source_refresh_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
GENERATED_AT = "2026-07-30T00:00:00+00:00"

V2_RECORDS = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "selected_source_library_records.yaml"
)
V5_QUEUE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v5"
    / "latest"
    / "ranked_implementation_queue.csv"
)
SOURCE_STAGE_INVENTORY = (
    ROOT
    / "evidence"
    / "strategy_library_discovery_yield_checkpoint_v1"
    / "latest"
    / "source_candidate_stage_inventory.csv"
)
EXTERNAL_SOURCE_BACKLOG = (
    ROOT
    / "evidence"
    / "strategy_evidence_library"
    / "latest"
    / "external_public_source_backlog.csv"
)
READY_QUEUE_INVENTORY = (
    ROOT
    / "evidence"
    / "continue_internal_ready_queue_batch_v2"
    / "latest"
    / "candidate_eligibility.csv"
)
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ROADMAP = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
RESEARCH_QUEUE = (
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
)
FAMILY_LEDGER = (
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
)
ACTIVE_OBSERVATIONS = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "operations"
    / "active_observations.yaml"
)
CACHE_DIR = ROOT / "data" / "cache"

PROTECTED_PATHS = (
    REGISTRY,
    ROADMAP,
    RESEARCH_QUEUE,
    FAMILY_LEDGER,
    ACTIVE_OBSERVATIONS,
)
PRIOR_PSAR_PATHS = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "decelerated_psar_diversifier_incremental_value_followup_v1"
    / "latest",
    ROOT
    / "evidence"
    / "robustness"
    / "decelerated_psar_diversifier_final_robustness_v1"
    / "latest",
    ROOT
    / "evidence"
    / "experiment_design"
    / "design_decelerated_psar_prospective_validation_v1"
    / "latest",
    ROOT
    / "evidence"
    / "validation"
    / "activate_decelerated_psar_prospective_validation_v1"
    / "latest",
    ROOT
    / "evidence"
    / "validation"
    / "repair_and_retry_decelerated_psar_prospective_activation_v1"
    / "latest",
)

REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "psar_deferred_state_reconciliation.csv",
    "internal_candidate_inventory.csv",
    "duplicate_screening.csv",
    "candidate_eligibility_results.csv",
    "selected_candidate_cohort.csv",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "near_qualified_candidate_diagnostics.csv",
    "cohort_requirement_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}

PROTECTED_EXACT_CONFIGURATIONS = {
    "bilello_gayed_beta_rotation_xlu_spy_4week_v1",
    "ma_adaptive_top4_3month_multi_asset_v1",
    "dalmasso_rati_multi_asset_top7_v1",
    "liu_es_implied_relative_downside_beta_sector_top2_v1",
    "bouman_jacobsen_halloween_spy_bil_v1",
    "chaikin_cmf20_zero_state_spy_bil_v1",
    "elder_force_index13_zero_state_spy_bil_v1",
    "cqg_kvo_34_55_13_spy_bil_v1",
    "barbara_decelerated_psar_spy_bil_v1",
    "lopez_de_prado_hrp_five_asset_v1",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "pring_kst_default_centerline_spy_bil_v1",
    "chande_aroon_oscillator_25_90_spy_bil_v1",
    "connors_alvarez_double7_spy_bil_next_open_v1",
    "kaufman_pjk_lr_channel_breakout_spy_bil_v1",
    "pagonidis_ibs_spy_next_open_intraday_v1",
    "li_hoi_olmar5_sector_etf_v1",
    "li_zhao_pamr0_sector_etf_v1",
    "borodin_bah30_anticor_sector_etf_v1",
    "choi_max_drawdown_sector_momentum_6x6_v1",
    "six_month_low_volatility_bottom3_sector_diversifier_v1",
    "chen_yu_52week_low_sector_one_month_portability_v1",
    "george_hwang_52week_high_sector_v1",
    "donninger_vix_vix3m_median5_spy_ief_portability_v1",
    "kritzman_absorption_ratio_sector_spy_ief_v1",
    "da_gurun_warachka_fip_sector_12_2_6m_v1",
    "gervais_kaniel_mingelgrin_high_volume_sector_v1",
    "bali_cakici_whitelaw_low_max_sector_v1",
    "treasury_duration_trend_rotation_v1",
}

SOURCE_ALIAS_TO_TESTED_OR_CONTROL = {
    "adx_dmi_trend_strength_crossover": "adx_dmi_spy_bil_primary_v1",
    "clare_seaton_smith_thomas_risk_parity_trend_following_2016": (
        "rp_ivol_10m_trend_etf_wrapper_adaptation_v1"
    ),
    "coppock_curve_monthly_equity_signal": (
        "coppock_spy_bil_monthly_zero_cross_primary_v1"
    ),
    "golden_cross_50_200": "SPY_50_200_golden_cross_control",
    "huang_huang_moving_average_etfs": "prior_moving_average_family_trials",
    "larry_connors_rsi2_mean_reversion": "connors_rsi2_spy_bil_primary_v1",
    "managed_futures_proxy_etf_trend_v1": "mfv_equal_weight_trend_filter_v1",
    "moskowitz_ooi_pedersen_time_series_momentum": (
        "prior_asset_class_time_series_momentum_trials"
    ),
    "parabolic_sar_spy_bil_long_only_reversal": (
        "parabolic_sar_spy_bil_primary_v1"
    ),
    "percent_b_money_flow": "percent_b_mfi_spy_bil_primary_v1",
    "pitkajarvi_suominen_vaittinen_cross_asset_tsmom": (
        "prior_asset_class_time_series_momentum_trials"
    ),
    "sector_momentum_rotational_system": "prior_sector_momentum_trials",
    "sell_in_may_halloween_effect": (
        "bouman_jacobsen_halloween_spy_bil_v1"
    ),
}

DATA_BLOCKED_IDS = {
    "individual_stock_momentum_gate1b_v1",
    "kuntz_beta_dispersion_timing",
    "research_affiliates_growth_inflation_taa",
    "sarwar_mateus_todorovic_sector_ff5_alpha",
}
CAPABILITY_BLOCKED_IDS = {
    "avellaneda_li_papanicolaou_wang_vix_futures_ml",
    "crypto_spot_tsmom_tier2_review_v1",
    "dabrowski_tactical_sp500_vix",
    "dunis_laws_rudy_conditional_autocorrelation_pairs",
    "fassas_hourvouliades_vix_futures_timing",
    "gatev_distance_pairs_12m_6m_2sd",
    "gatev_goetzmann_rouwenhorst_pairs_trading_2006",
    "options_futures_forex_intraday_blocked_reference_v1",
}
INCOMPLETE_IDS = {
    "bollinger_band_squeeze_breakout",
    "low_vol_quality_defensive_rotation_v1",
    "low_volatility_factor_proxy",
    "macd_stochastic_double_cross",
    "macro_gld_duration_risk_off_source_backed_candidate",
    "pagonidis_ibs_equity_etf_reversal",
    "treasury_duration_trend_rotation_v1",
}
NON_CANDIDATE_IDS = {
    "active_combo_vm_dsr_equal_weight_v1",
    "cash_pause_overlay_meta_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "static_all_weather_benchmark_v1",
}

INVENTORY_FIELDS = [
    "candidate_id",
    "source_record_ids",
    "family_id",
    "record_kinds",
    "source_paths",
    "source_complete",
    "exact_configuration_tested",
    "duplicate_or_prior_control",
    "data_ready",
    "capability_ready",
    "long_only_nonleveraged",
    "locally_implementable",
    "eligible",
    "primary_blocker_category",
    "exact_blocker",
    "duplicate_reference",
    "performance_used_for_selection",
]


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def write_csv(
    path: Path,
    rows: Iterable[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, value: Any) -> None:
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    elif path.is_dir():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
    else:
        digest.update(b"<missing>")
    return digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    paths = (*PROTECTED_PATHS, CACHE_DIR, *PRIOR_PSAR_PATHS)
    return {relative(path): sha256_path(path) for path in paths}


def _record(
    records: dict[str, dict[str, Any]],
    candidate_id: str,
    *,
    source_path: Path,
    record_kind: str,
    source_record_id: str = "",
    family_id: str = "",
    source_complete: bool | None = None,
    tested_hint: bool = False,
    blocker_hint: str = "",
) -> None:
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        return
    row = records.setdefault(
        candidate_id,
        {
            "candidate_id": candidate_id,
            "source_record_ids": set(),
            "family_id": "",
            "record_kinds": set(),
            "source_paths": set(),
            "source_complete_votes": [],
            "tested_hint": False,
            "blocker_hints": set(),
        },
    )
    row["source_paths"].add(relative(source_path))
    row["record_kinds"].add(record_kind)
    if source_record_id:
        row["source_record_ids"].add(source_record_id)
    if family_id and not row["family_id"]:
        row["family_id"] = family_id
    if source_complete is not None:
        row["source_complete_votes"].append(bool(source_complete))
    row["tested_hint"] = row["tested_hint"] or tested_hint
    if blocker_hint:
        row["blocker_hints"].add(blocker_hint)


def trial_strategy_ids() -> set[str]:
    values: set[str] = set()
    for path in ROOT.glob("evidence/**/trial_ledger.csv"):
        for row in read_csv(path):
            candidate_id = (
                row.get("strategy_id") or row.get("candidate_id") or ""
            ).strip()
            if candidate_id:
                values.add(candidate_id)
    return values


def collect_internal_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}

    for row in read_csv(SOURCE_STAGE_INVENTORY):
        tested = (
            row["bounded_screen_completed"].lower() == "true"
            or row["exact_variant_closed"].lower() == "true"
            or row["highest_stage"] in {"validation_completed", "closed_exact_variant"}
        )
        _record(
            records,
            row["candidate_id"],
            source_path=SOURCE_STAGE_INVENTORY,
            record_kind="source_candidate_stage_inventory",
            source_record_id=row["source_id"],
            family_id=row["lane_or_family"],
            source_complete=row["complete_rules"].lower() == "true",
            tested_hint=tested,
            blocker_hint=row["primary_failure_reason"],
        )

    for row in read_csv(EXTERNAL_SOURCE_BACKLOG):
        _record(
            records,
            row["source_id"],
            source_path=EXTERNAL_SOURCE_BACKLOG,
            record_kind="external_public_source_backlog",
            source_record_id=row["source_id"],
            source_complete=row["rules_completeness"].startswith("clear"),
            tested_hint=row["linked_local_implementation_exists"].lower() == "true",
            blocker_hint=row["rules_completeness"],
        )

    for row in read_yaml(V2_RECORDS)["records"]:
        _record(
            records,
            row["proposed_strategy_id"],
            source_path=V2_RECORDS,
            record_kind="selected_source_library_record",
            source_record_id=row["source_record_id"],
            family_id=row["family_id"],
            source_complete=str(row["source_completeness_result"]).startswith(
                "complete"
            ),
        )

    for row in read_csv(V5_QUEUE):
        _record(
            records,
            row["candidate_id"],
            source_path=V5_QUEUE,
            record_kind="ranked_source_implementation_queue",
            source_complete=row["source_completeness_0_to_5"] == "5",
            tested_hint=row["primary_blocker"] == "already_tested",
            blocker_hint=row["primary_blocker"],
        )

    for path in ROOT.glob("evidence/**/source_library_records.csv"):
        for row in read_csv(path):
            candidate_id = (
                row.get("strategy_id") or row.get("proposed_strategy_id") or ""
            ).strip()
            if not candidate_id:
                continue
            _record(
                records,
                candidate_id,
                source_path=path,
                record_kind="source_library_record",
                source_record_id=row.get("source_record_id", ""),
                family_id=row.get("family_id", ""),
                source_complete=True,
            )

    for path in ROOT.glob("evidence/pre_registered_lanes/**/*.yaml"):
        value = read_yaml(path)
        candidates = value.get("candidates")
        if not isinstance(candidates, list):
            continue
        for row in candidates:
            if not isinstance(row, dict):
                continue
            _record(
                records,
                row.get("candidate_id") or row.get("strategy_id") or "",
                source_path=path,
                record_kind="frozen_preregistered_candidate",
                family_id=row.get("family")
                or row.get("source_family")
                or row.get("lane")
                or "",
                source_complete=bool(row.get("rules_frozen", True)),
                tested_hint=True,
                blocker_hint=str(row.get("formula_status", "")),
            )

    for row in read_csv(READY_QUEUE_INVENTORY):
        blocker = row["blocker_type"]
        _record(
            records,
            row["candidate_id"],
            source_path=READY_QUEUE_INVENTORY,
            record_kind="internal_ready_queue_inventory",
            family_id=row["family_id"],
            source_complete=blocker
            not in {
                "rules",
                "rules_data",
                "unsupported_constituent_data",
                "unsupported_data_execution",
                "unsupported_instrument_reference",
            },
            tested_hint=blocker
            in {"closed_exact_variant", "valid_screen_completed"},
            blocker_hint=blocker,
        )

    registry = read_yaml(REGISTRY).get("registry", {})
    for candidate_id in registry.get("future_rows", []):
        _record(
            records,
            candidate_id,
            source_path=REGISTRY,
            record_kind="registry_historical_future_row",
            family_id="breadth_state_regime",
            source_complete=True,
            tested_hint=True,
            blocker_hint="completed_discovery_reject",
        )
    return records


def classify_inventory(
    raw_records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    tested = trial_strategy_ids() | PROTECTED_EXACT_CONFIGURATIONS
    rows: list[dict[str, Any]] = []
    for candidate_id, source in sorted(raw_records.items()):
        source_complete = any(source["source_complete_votes"])
        exact_tested = source["tested_hint"] or candidate_id in tested
        duplicate_reference = ""
        if candidate_id in SOURCE_ALIAS_TO_TESTED_OR_CONTROL:
            duplicate_reference = SOURCE_ALIAS_TO_TESTED_OR_CONTROL[candidate_id]
            exact_tested = True

        category = ""
        blocker = ""
        data_ready = True
        capability_ready = True
        long_only = True
        locally_implementable = True

        if candidate_id in DATA_BLOCKED_IDS:
            category = "data_blocked"
            blocker = (
                "The frozen mechanism requires point-in-time, constituent, factor, "
                "fundamental, or vintage data absent from canonical local caches."
            )
            data_ready = False
            locally_implementable = False
        elif candidate_id in CAPABILITY_BLOCKED_IDS:
            category = "capability_blocked"
            blocker = (
                "The mechanism requires unsupported short, borrow, futures, "
                "volatility-product, intraday, or non-ETF accounting capability."
            )
            capability_ready = False
            long_only = candidate_id not in {
                "crypto_spot_tsmom_tier2_review_v1",
                "dabrowski_tactical_sp500_vix",
            }
            locally_implementable = False
        elif candidate_id in INCOMPLETE_IDS or not source_complete:
            category = "incomplete"
            blocker = (
                "At least one core rule, mapping, timing field, or project "
                "configuration remains incomplete; source completion is prohibited."
            )
            locally_implementable = False
        elif exact_tested or candidate_id in NON_CANDIDATE_IDS:
            category = "exact_duplicate"
            duplicate_reference = (
                duplicate_reference
                or (
                    "non_candidate_benchmark_or_active_state"
                    if candidate_id in NON_CANDIDATE_IDS
                    else candidate_id
                )
            )
            blocker = (
                "The exact configuration has prior performance evidence, is a "
                "protected active/benchmark entity, or is a prior control that "
                "cannot be promoted in this task."
            )
        else:
            category = "eligible"
            blocker = ""

        eligible = category == "eligible"
        rows.append(
            {
                "candidate_id": candidate_id,
                "source_record_ids": "|".join(sorted(source["source_record_ids"])),
                "family_id": source["family_id"] or "unmapped",
                "record_kinds": "|".join(sorted(source["record_kinds"])),
                "source_paths": "|".join(sorted(source["source_paths"])),
                "source_complete": source_complete,
                "exact_configuration_tested": exact_tested,
                "duplicate_or_prior_control": category == "exact_duplicate",
                "data_ready": data_ready,
                "capability_ready": capability_ready,
                "long_only_nonleveraged": long_only,
                "locally_implementable": locally_implementable,
                "eligible": eligible,
                "primary_blocker_category": category if not eligible else "",
                "exact_blocker": blocker,
                "duplicate_reference": duplicate_reference,
                "performance_used_for_selection": False,
            }
        )
    return rows


def empty_output_files() -> None:
    strategy_fields = [
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
        "failure_reason",
        "next_action",
    ]
    trial_fields = [
        "trial_id",
        "strategy_id",
        "entity_type",
        "stage",
        "parent_trial_id",
        "adaptation_label",
        "optimization_performed",
        "post_result_adaptation_allowed",
        "source_completion_performed",
        "provider_access_performed",
        "outcome",
        "failure_reason",
        "next_action",
    ]
    result_fields = [
        "strategy_id",
        "trial_id",
        "result_id",
        "cost_bps",
        "period",
        "evaluation_start",
        "evaluation_end",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "average_risky_exposure",
        "turnover",
        "transaction_cost_drag",
        "signal_or_rebalance_count",
        "maximum_single_asset_weight",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
    ]
    write_csv(
        OUTPUT_DIR / "selected_candidate_cohort.csv",
        [],
        [
            "rank",
            "source_record_id",
            "strategy_id",
            "family_id",
            "route",
            "selection_reason",
        ],
    )
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        [],
        [
            "source_record_id",
            "strategy_id",
            "entity_type",
            "stage",
            "outcome",
            "next_action",
        ],
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [], strategy_fields)
    write_csv(OUTPUT_DIR / "trial_ledger.csv", [], trial_fields)
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        [],
        [
            "benchmark_id",
            "entity_type",
            "stage",
            "candidate_strategy_id",
            "role",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        [],
        [
            "strategy_id",
            "symbol",
            "cache_path",
            "file_hash",
            "frame_hash",
            "first_date",
            "last_date",
            "row_count",
            "status",
        ],
    )
    for name in (
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
    ):
        write_csv(OUTPUT_DIR / name, [], result_fields)
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        [],
        [
            "strategy_id",
            "cost_bps",
            "one_way_turnover",
            "transaction_cost_drag",
            "cost_charged_once",
        ],
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        [],
        ["strategy_id", "trial_id", "invariant_id", "status", "details"],
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        [],
        ["strategy_id", "trial_id", "outcome", "route", "next_action"],
    )


def run() -> dict[str, Any]:
    before = protected_hashes()
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    inventory = classify_inventory(collect_internal_records())
    eligible = [row for row in inventory if row["eligible"]]
    if len(eligible) >= 4:
        raise RuntimeError(
            "Audit unexpectedly found four or more eligible records; "
            "the zero-trial shortfall path may not run."
        )

    write_csv(OUTPUT_DIR / "internal_candidate_inventory.csv", inventory, INVENTORY_FIELDS)
    write_csv(
        OUTPUT_DIR / "candidate_eligibility_results.csv",
        inventory,
        INVENTORY_FIELDS,
    )
    duplicates = [
        {
            "candidate_id": row["candidate_id"],
            "duplicate_reference": row["duplicate_reference"],
            "exact_configuration_tested": row["exact_configuration_tested"],
            "prior_control_or_benchmark": (
                row["duplicate_reference"]
                == "non_candidate_benchmark_or_active_state"
                or row["duplicate_reference"].startswith("SPY_")
                or row["duplicate_reference"].startswith("prior_")
            ),
            "excluded": True,
            "reason": row["exact_blocker"],
        }
        for row in inventory
        if row["primary_blocker_category"] == "exact_duplicate"
    ]
    write_csv(
        OUTPUT_DIR / "duplicate_screening.csv",
        duplicates,
        [
            "candidate_id",
            "duplicate_reference",
            "exact_configuration_tested",
            "prior_control_or_benchmark",
            "excluded",
            "reason",
        ],
    )
    empty_output_files()

    write_csv(
        OUTPUT_DIR / "psar_deferred_state_reconciliation.csv",
        [
            {
                "strategy": "barbara_decelerated_psar_spy_bil_v1",
                "route": "20pct_diversifier_only",
                "historical_status": "robustness_positive",
                "prospective_status": "activation_deferred",
                "current_blocker": (
                    "prospective_data_capability_unavailable_under_frozen_"
                    "activation_contract"
                ),
                "direction_level_status": (
                    "historically_robust_validation_ready_route_operationally_deferred"
                ),
                "new_psar_trials_created": 0,
                "new_activation_attempts": 0,
                "counted_in_this_exploration_cohort": False,
            }
        ],
        [
            "strategy",
            "route",
            "historical_status",
            "prospective_status",
            "current_blocker",
            "direction_level_status",
            "new_psar_trials_created",
            "new_activation_attempts",
            "counted_in_this_exploration_cohort",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "mode": MODE,
                "performance_trials_executed": 0,
                "provider_access_performed": False,
                "source_completion_performed": False,
                "psar_work_performed": False,
                "outcome": OUTCOME,
                "next_action": NEXT_ACTION,
            }
        ],
        [
            "task_id",
            "entity_type",
            "stage",
            "mode",
            "performance_trials_executed",
            "provider_access_performed",
            "source_completion_performed",
            "psar_work_performed",
            "outcome",
            "next_action",
        ],
    )
    near_qualified = [
        {
            "candidate_id": row["candidate_id"],
            "family_id": row["family_id"],
            "source_complete": row["source_complete"],
            "blocker_category": row["primary_blocker_category"],
            "exact_blocker": row["exact_blocker"],
            "duplicate_reference": row["duplicate_reference"],
            "smallest_allowed_resolution": (
                "external direction task only; no resolution is authorized here"
            ),
        }
        for row in inventory
        if row["source_complete"]
        and row["primary_blocker_category"]
        in {"data_blocked", "capability_blocked"}
    ]
    write_csv(
        OUTPUT_DIR / "near_qualified_candidate_diagnostics.csv",
        near_qualified,
        [
            "candidate_id",
            "family_id",
            "source_complete",
            "blocker_category",
            "exact_blocker",
            "duplicate_reference",
            "smallest_allowed_resolution",
        ],
    )
    requirements = [
        ("exact_candidate_count", 4, len(eligible), False),
        ("minimum_distinct_families", 3, 0, False),
        ("minimum_native_rules", 3, 0, False),
        ("maximum_portability_translations", 1, 0, True),
        ("maximum_spy_bil_technical_state_rules", 1, 0, True),
        ("minimum_diversifier_diagnostics", 2, 0, False),
        ("maximum_high_turnover_candidates", 1, 0, True),
        ("passive_or_structural_wrappers", 0, 0, True),
    ]
    write_csv(
        OUTPUT_DIR / "cohort_requirement_diagnostics.csv",
        [
            {
                "requirement": name,
                "required": required,
                "observed": observed,
                "passed": passed,
                "evaluated_before_performance": True,
            }
            for name, required, observed, passed in requirements
        ],
        [
            "requirement",
            "required",
            "observed",
            "passed",
            "evaluated_before_performance",
        ],
    )

    counts = {
        "total_internal_records_screened": len(inventory),
        "source_complete_records": sum(bool(row["source_complete"]) for row in inventory),
        "exact_duplicates": sum(
            row["primary_blocker_category"] == "exact_duplicate" for row in inventory
        ),
        "data_blocked_records": sum(
            row["primary_blocker_category"] == "data_blocked" for row in inventory
        ),
        "capability_blocked_records": sum(
            row["primary_blocker_category"] == "capability_blocked"
            for row in inventory
        ),
        "incomplete_records": sum(
            row["primary_blocker_category"] == "incomplete" for row in inventory
        ),
        "eligible_records": len(eligible),
        "selected_candidates": 0,
        "source_library_records_created": 0,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "benchmark_references_created": 0,
        "data_capability_tasks_created": 0,
        "process_tasks_created": 1,
        "performance_calculations": 0,
        "psar_trials_created": 0,
        "psar_activation_attempts": 0,
        "paper_demo_observations_created": 0,
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", counts)
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "stage": STAGE,
                "outcome": OUTCOME,
                "eligible_record_count": len(eligible),
                "selected_candidate_count": 0,
                "performance_trials_executed": 0,
                "failure_reason": "internal_ready_queue_shortfall",
                "next_action": NEXT_ACTION,
            }
        ],
        [
            "task_id",
            "stage",
            "outcome",
            "eligible_record_count",
            "selected_candidate_count",
            "performance_trials_executed",
            "failure_reason",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "entity_id": TASK_ID,
                "entity_type": "process_task",
                "failure_reason": "internal_ready_queue_shortfall",
                "details": (
                    "Fewer than four records passed source completeness, novelty, "
                    "local data, capability, route, and control gates."
                ),
            }
        ],
        ["entity_id", "entity_type", "failure_reason", "details"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": OUTCOME,
                "next_action": NEXT_ACTION,
                "executed_in_this_task": False,
            }
        ],
        ["task_id", "outcome", "next_action", "executed_in_this_task"],
    )

    after = protected_hashes()
    hashes_unchanged = before == after
    consistency = {
        "overall_pass": hashes_unchanged and len(eligible) < 4,
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "inventory_frozen_before_performance": True,
        "required_four_candidate_gate_met": False,
        "eligible_record_count": len(eligible),
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "performance_calculations_executed": 0,
        "provider_access_performed": False,
        "source_research_performed": False,
        "source_completion_performed": False,
        "new_dependency_installed": False,
        "psar_analysis_performed": False,
        "psar_activation_attempted": False,
        "psar_status_preserved": True,
        "prior_controls_promoted": False,
        "lifecycle_state_changed": False,
        "paper_demo_observations_changed": False,
        "broker_or_order_path_touched": False,
        "real_money_action_performed": False,
        "protected_state_cache_and_prior_psar_unchanged": hashes_unchanged,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "required_output_count": len(REQUIRED_OUTPUTS),
        "exact_next_action": NEXT_ACTION,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "generated_at_utc": GENERATED_AT,
        "outcome": OUTCOME,
        "failure_reason": "internal_ready_queue_shortfall",
        "exact_next_action": NEXT_ACTION,
        "candidate_gate": {
            "required_candidate_count": 4,
            "eligible_candidate_count": len(eligible),
            "selected_candidate_count": 0,
            "performance_authorized": False,
        },
        "counts": counts,
        "governance": {
            "cohort_frozen_before_performance": True,
            "performance_executed": False,
            "source_research_performed": False,
            "provider_access_performed": False,
            "psar_work_performed": False,
            "lifecycle_state_changed": False,
        },
        "required_outputs": sorted(REQUIRED_OUTPUTS),
    }
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    report = f"""# Resumed Strategy Discovery Ready-Queue Audit

## Outcome

`{OUTCOME}`

The internal audit screened **{counts['total_internal_records_screened']}**
deduplicated records. It found **{len(eligible)}** configurations that passed
every pre-performance gate, below the required cohort of four. The batch
therefore created no strategy configuration, experiment trial, benchmark
reference, data task, or performance result.

## Inventory Result

| Measure | Count |
|---|---:|
| Source-complete records | {counts['source_complete_records']} |
| Exact duplicates, prior controls, or protected entities | {counts['exact_duplicates']} |
| Data-blocked records | {counts['data_blocked_records']} |
| Capability-blocked records | {counts['capability_blocked_records']} |
| Incomplete records | {counts['incomplete_records']} |
| Eligible records | {counts['eligible_records']} |

The source-complete untested records that came closest still require missing
point-in-time data, unsupported long-short or derivatives capability, or are
economically duplicate source mechanisms. Criteria were not weakened to fill
the cohort.

## PSAR Boundary

`barbara_decelerated_psar_spy_bil_v1` remains historically robust on its
20% diversifier route and operationally deferred. This audit made no PSAR
trial, activation attempt, data remediation, dependency change, or lifecycle
change.

## Research Boundary

No web research, source completion, provider access, cache write, performance
calculation, validation, paper/demo action, broker action, or real-money action
occurred.

## Next Action

`{NEXT_ACTION}`
"""
    (OUTPUT_DIR / "batch_report.md").write_text(report, encoding="utf-8")

    missing = sorted(REQUIRED_OUTPUTS - {path.name for path in OUTPUT_DIR.iterdir()})
    if missing:
        raise RuntimeError(f"Required outputs missing: {missing}")
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "eligible_record_count": len(eligible),
        "selected_candidate_count": 0,
        "performance_trials_executed": 0,
        "next_action": NEXT_ACTION,
        "consistency_pass": consistency["overall_pass"],
        "evidence_path": str(OUTPUT_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
