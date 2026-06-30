from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "governance" / "exploratory_strategy_search_sandbox_implementation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
APPROVED_SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
DATA_CACHE_DIR = Path("data") / "cache"

NEXT_ACTION_RUN_BATCH = "run_exploratory_strategy_search_sandbox_batch"
NEXT_ACTION_MANUAL_REVIEW = "manual_review_required_for_exploratory_sandbox_implementation"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_RUN_BATCH,
    NEXT_ACTION_MANUAL_REVIEW,
    NEXT_ACTION_PAUSE,
}

MAX_TOTAL_FUTURE_VARIANTS = 200
MAX_FAMILIES_PER_RUN = 7
MAX_VARIANTS_PER_FAMILY = 30
MAX_PARAMETER_CHOICES_PER_INDICATOR = 5
MAX_UNIVERSE_GROUPS_PER_RUN = 8
MAX_PORTFOLIO_COMBINATION_VARIANTS = 40

INITIAL_SANDBOX_STATUS = "non_promotable_exploration"
SANDBOX_PRINCIPLE = "explore broadly, promote narrowly"

ACTIVE_OBSERVATION_IDS = (
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
)
BENCHMARK_CONTROL_IDS = ("static_all_weather_benchmark_v1",)
EXACT_REJECTED_VARIANT_IDS = (
    "mfv_equal_weight_trend_filter_v1",
    "old_managed_futures_top1_v1",
    "old_managed_futures_top2_v1",
)

MANIFEST_FLAGS = {
    "sandbox_implementation_only": True,
    "sandbox_search_run": False,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "sandbox_results_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
}

REQUIRED_OUTPUT_FILES = (
    "exploratory_sandbox_implementation_manifest.json",
    "exploratory_sandbox_implementation_summary.md",
    "sandbox_module_report.md",
    "sandbox_variant_schema.md",
    "sandbox_variant_plan_dry_run.csv",
    "sandbox_universe_availability_report.md",
    "sandbox_family_registry_report.md",
    "sandbox_indicator_registry_report.md",
    "sandbox_status_taxonomy_report.md",
    "sandbox_scoring_framework_report.md",
    "sandbox_anti_overfitting_report.md",
    "sandbox_research_only_leverage_report.md",
    "sandbox_data_preflight_report.md",
    "sandbox_do_not_run_results.md",
    "sandbox_implementation_next_action.md",
    "exploratory_sandbox_implementation_consistency_check.json",
)
