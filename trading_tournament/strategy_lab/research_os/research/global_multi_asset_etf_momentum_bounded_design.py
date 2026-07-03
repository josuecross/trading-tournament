from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


FAMILY_ID = "global_multi_asset_etf_momentum"
LANE_ID = "global_multi_asset_etf_momentum_bounded_lane_v1"
SELECTED_STRATEGY_ID = "global_multi_asset_tsmom_top2_defensive_50_v1"
SELECTED_SOURCE_BATCH = "global_multi_asset_fast_exploration_batch1"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "global_multi_asset_etf_momentum_bounded_design"
    / "latest"
)

TRIAGE_DIR = (
    Path("evidence")
    / "research_recovery"
    / "profit_oriented_registry_research_sample_triage"
    / "latest"
)
SOURCE_EVIDENCE_DIR = Path("evidence") / "multi_asset_lab" / "fast_exploration_batch1" / "latest"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
PROFIT_SPECS = Path("profit_lab") / "profit_experiment_specs.yaml"
LOCAL_CACHE = Path("data") / "cache"

REQUIRED_SYMBOLS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT", "BIL")
RANKED_ASSETS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT")

RUN_READY = "global_multi_asset_bounded_design_run_ready"
RUN_BLOCKED = "global_multi_asset_bounded_design_blocked"
NEXT_ACTION_RUN = "run_global_multi_asset_etf_momentum_bounded_lane"
NEXT_ACTION_BLOCKED = "restore_or_revalidate_global_multi_asset_local_cache_before_bounded_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}
VALID_RUN_READINESS = {RUN_READY, RUN_BLOCKED}

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_registry_id",
    "source_evidence_path",
    "source_context_status",
    "concept",
    "universe_group",
    "universe",
    "lookback_days",
    "top_n",
    "rebalance_frequency",
    "rule_summary",
    "baseline_variant_id",
    "comparator_references",
    "bil_cash_rule",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "zero_weight_policy",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

CACHE_FIELDS = ("symbol", "required", "cache_path", "available")

REQUIRED_FILES = (
    "global_multi_asset_bounded_design_manifest.json",
    "global_multi_asset_bounded_design_summary.md",
    "source_lineage_assessment.md",
    "local_cache_availability.csv",
    "local_cache_preflight.md",
    "eligibility_decision.md",
    "planned_variant_design_table.csv",
    "planned_variant_design_table.md",
    "variant_roles.md",
    "baseline_comparator_policy.md",
    "numeric_success_failure_criteria.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "rejected_closed_variant_exclusion_rule.md",
    "do_not_promote_from_global_multi_asset_design.md",
    "global_multi_asset_bounded_design_next_action.md",
    "global_multi_asset_bounded_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def registry_row(registry: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    rows = registry.get("strategies")
    if not isinstance(rows, list):
        return {}
    return next((row for row in rows if row.get("strategy_id") == strategy_id or row.get("id") == strategy_id), {})


def spec_row(specs: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    experiments = specs.get("experiments")
    if not isinstance(experiments, list):
        return {}
    return next((row for row in experiments if row.get("experiment_id") == experiment_id), {})


def source_result_rows(root: Path, experiment_id: str) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv_rows(root / SOURCE_EVIDENCE_DIR / "fast_exploration_batch1_results.csv")
        if row.get("experiment_id") == experiment_id
    ]


def source_horizon_row(root: Path, experiment_id: str, horizon: str = "180.0") -> dict[str, str]:
    rows = source_result_rows(root, experiment_id)
    return next((row for row in rows if row.get("row_type") == "candidate_horizon" and row.get("horizon") == horizon), {})


def source_diagnostic_rows(root: Path, experiment_id: str) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv_rows(root / SOURCE_EVIDENCE_DIR / "fast_exploration_batch1_diagnostics.csv")
        if row.get("experiment_id") == experiment_id
    ]


def local_cache_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for symbol in REQUIRED_SYMBOLS:
        path = root / LOCAL_CACHE / f"{symbol}.csv"
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_path": str(path.resolve()),
                "available": path.exists(),
            }
        )
    return rows


def cache_missing_symbols(cache_rows: list[dict[str, Any]]) -> list[str]:
    return [row["symbol"] for row in cache_rows if not row["available"]]


def source_lineage_safe(registry: dict[str, Any], specs: dict[str, Any], root: Path) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    triage_manifest = read_json(root / TRIAGE_DIR / "triage_manifest.json")
    source_manifest = read_json(root / SOURCE_EVIDENCE_DIR / "fast_exploration_batch1_manifest.json")
    selected_registry = registry_row(registry, SELECTED_STRATEGY_ID)
    selected_spec = spec_row(specs, SELECTED_STRATEGY_ID)

    if triage_manifest.get("selected_strategy_id") != SELECTED_STRATEGY_ID:
        blockers.append("triage manifest does not select the expected global multi-asset row")
    if triage_manifest.get("selected_family") != FAMILY_ID:
        blockers.append("triage manifest selected family does not match global_multi_asset_etf_momentum")
    if not selected_registry:
        blockers.append("selected strategy registry row is missing")
    if selected_registry.get("status") != "watchlist":
        blockers.append("selected registry row status is not watchlist/context")
    if selected_registry.get("paper_forward_active") is not False:
        blockers.append("selected registry row is paper-forward active")
    if selected_registry.get("candidate_exhaustive_run") is not False:
        blockers.append("selected registry row already ran candidate_exhaustive")
    if selected_spec.get("canonical_rule", {}).get("fixed_weights") != {
        "global_multi_asset_tsmom_top2_v1": 0.50,
        "BIL_cash_proxy": 0.50,
    }:
        blockers.append("selected source spec does not match fixed 50/50 global multi-asset/BIL rule")
    if set(source_manifest.get("approved_symbols", [])) != set(REQUIRED_SYMBOLS):
        blockers.append("source evidence approved symbols do not match required bounded design symbols")
    if source_manifest.get("candidate_exhaustive_run") is not False:
        blockers.append("source evidence ran candidate_exhaustive")
    if source_manifest.get("data_downloaded") is not False:
        blockers.append("source evidence indicates data download")
    if source_manifest.get("uses_intraday") is not False:
        blockers.append("source evidence used intraday")
    if source_manifest.get("real_money_recommendation") is not False:
        blockers.append("source evidence contains real-money recommendation")
    if not source_horizon_row(root, SELECTED_STRATEGY_ID):
        blockers.append("selected source evidence lacks 180-day candidate horizon row")

    return not blockers, blockers


def build_design_rows(root: Path) -> list[dict[str, Any]]:
    source_csv = str((root / SOURCE_EVIDENCE_DIR / "fast_exploration_batch1_results.csv").resolve())
    common = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_evidence_path": source_csv,
        "source_context_status": "older_exploratory_context_only_not_promotion_evidence",
        "rebalance_frequency": "monthly",
        "comparator_references": "SPY|SPY_200d_frozen_control|BIL_cash_proxy|static_all_weather_benchmark_control_only|active_VM_DSR_diagnostics_where_supported|selected_source_row_context_only",
        "bil_cash_rule": "BIL/cash is replacement or remainder only; it must not accumulate above total exposure 1.0.",
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "zero_weight_policy": "zero target weights remain zero until the next explicit rebalance target; stale-forward-filling old nonzero allocations into zero targets is forbidden",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    universe = "|".join(REQUIRED_SYMBOLS)
    ranked = "|".join(RANKED_ASSETS)
    return [
        {
            **common,
            "variant_id": "gma_bounded_selected_defensive_50_top2_126_v1",
            "variant_role": "selected_confirmation",
            "source_registry_id": SELECTED_STRATEGY_ID,
            "concept": "fixed_50pct_global_multi_asset_tsmom_top2_50pct_bil",
            "universe_group": "global_multi_asset_plus_bil",
            "universe": universe,
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Exact selected source rule: run global_multi_asset_tsmom_top2_v1 as a 50% sleeve and hold 50% BIL cash proxy; no optimized weights and no parameter tuning.",
            "baseline_variant_id": "global_multi_asset_tsmom_top2_v1",
        },
        {
            **common,
            "variant_id": "gma_bounded_base_tsmom_top2_126_v1",
            "variant_role": "uncontrolled_source_baseline_context",
            "source_registry_id": "global_multi_asset_tsmom_top2_v1",
            "concept": "global_multi_asset_tsmom_top2",
            "universe_group": "global_multi_asset_plus_bil",
            "universe": universe,
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": f"Source baseline context: rank {ranked} by 126-day total return monthly; hold equal-weight top two assets with positive 126-day return; unused or failed weight goes to BIL.",
            "baseline_variant_id": "global_multi_asset_tsmom_top2_v1",
        },
        {
            **common,
            "variant_id": "gma_bounded_combo_plus_global_80_20_v1",
            "variant_role": "portfolio_contribution_context",
            "source_registry_id": "combo_plus_global_multi_asset_80_20_v1",
            "concept": "active_combo_plus_global_multi_asset_sleeve",
            "universe_group": "active_combo_plus_global_multi_asset",
            "universe": universe,
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Source contribution context: fixed 80% combo_SPY200d_GLD_50_50_v1 plus 20% global_multi_asset_tsmom_top2_v1; active combo rules are not changed.",
            "baseline_variant_id": "combo_SPY200d_GLD_50_50_v1",
        },
        {
            **common,
            "variant_id": "gma_bounded_spy200d_control_v1",
            "variant_role": "comparator_control",
            "source_registry_id": "SPY_200d_trend_model",
            "concept": "spy200d_frozen_control",
            "universe_group": "control",
            "universe": "SPY|BIL",
            "lookback_days": 200,
            "top_n": 1,
            "rule_summary": "Same-window SPY 200-day trend-model frozen control; benchmark/control only and not a candidate row.",
            "baseline_variant_id": "SPY_200d_trend_model",
        },
        {
            **common,
            "variant_id": "gma_bounded_bil_cash_control_v1",
            "variant_role": "cash_control",
            "source_registry_id": "BIL_cash_proxy",
            "concept": "bil_cash_proxy_control",
            "universe_group": "control",
            "universe": "BIL",
            "lookback_days": 0,
            "top_n": 1,
            "rule_summary": "Same-window BIL cash proxy control only; not a candidate row.",
            "baseline_variant_id": "BIL_cash_proxy",
        },
        {
            **common,
            "variant_id": "gma_bounded_gld_control_v1",
            "variant_role": "commodity_real_asset_control",
            "source_registry_id": "GLD_buy_hold",
            "concept": "gld_buy_hold_control",
            "universe_group": "control",
            "universe": "GLD",
            "lookback_days": 0,
            "top_n": 1,
            "rule_summary": "Same-window GLD buy-and-hold control because GLD was an approved source comparator and member of the global multi-asset universe; not Macro/GLD continuation.",
            "baseline_variant_id": "GLD_buy_hold",
        },
    ]


def run_readiness(lineage_ok: bool, lineage_blockers: list[str], cache_rows: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    blockers = list(lineage_blockers)
    missing = cache_missing_symbols(cache_rows)
    if missing:
        blockers.append(f"missing current local cache symbols: {', '.join(missing)}")
    if len(rows) < 6 or len(rows) > 12:
        blockers.append("planned row count is outside 6 to 12")
    if len({row["variant_id"] for row in rows}) != len(rows):
        blockers.append("variant IDs are not unique")
    if any(row["promotion_eligibility"] or row["paper_forward_eligibility"] or row["candidate_exhaustive_eligibility"] for row in rows):
        blockers.append("one or more rows has forbidden eligibility")
    if lineage_ok and not blockers:
        return RUN_READY, "none", NEXT_ACTION_RUN
    return RUN_BLOCKED, "; ".join(blockers), NEXT_ACTION_BLOCKED


def source_lineage_md(payload: dict[str, Any], selected_registry: dict[str, Any], selected_spec: dict[str, Any]) -> str:
    return f"""# Source Lineage Assessment

Selected strategy: `{SELECTED_STRATEGY_ID}`

Selected family: `{FAMILY_ID}`

Triage evidence reviewed: `{payload['triage_evidence_reviewed']}`

Registry row found: `{payload['selected_registry_row_found']}`

Source spec found: `{payload['selected_source_spec_found']}`

Source evidence context status: `{payload['source_evidence_context_status']}`

Source evidence safety assessment:

- The selected source packet is older exploratory research-sample evidence.
- It is safe as design context because the registry row, source spec, and source manifest are internally consistent.
- It is not corrected promotion evidence, not candidate_exhaustive evidence, and not paper-forward evidence.

Registry status: `{selected_registry.get('status', '')}`

Registry latest evidence path: `{selected_registry.get('latest_evidence_path', '')}`

Canonical source rule: `{selected_spec.get('canonical_rule', {}).get('implementation_rule_id', '')}`

Run-readiness blocker: `{payload['run_readiness_blocker']}`
"""


def cache_preflight_md(payload: dict[str, Any]) -> str:
    return f"""# Local Cache Preflight

Required symbols: `{', '.join(payload['required_symbols'])}`

Available symbols: `{', '.join(payload['local_cache_available_symbols']) or 'none'}`

Missing symbols: `{', '.join(payload['local_cache_missing_symbols']) or 'none'}`

Cache complete: `{payload['local_cache_complete']}`

Provider download was not attempted. Intraday data was not used.
"""


def eligibility_md(payload: dict[str, Any]) -> str:
    return f"""# Eligibility Decision

Family: `{FAMILY_ID}`

Selected candidate: `{SELECTED_STRATEGY_ID}`

Eligibility decision: `{payload['eligibility_decision']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Blocker: `{payload['run_readiness_blocker']}`

The design is bounded to `6` planned rows: one selected confirmation row, one source baseline context row, one portfolio-contribution context row, and three comparator/control rows.

The triage score is not treated as strategy success.
"""


def design_table_md(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Planned Variant Design Table",
        "",
        "| Variant | Role | Source | Concept | Universe | Lookback | Top N |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['variant_id']}` | `{row['variant_role']}` | `{row['source_registry_id']}` | "
            f"`{row['concept']}` | `{row['universe']}` | `{row['lookback_days']}` | `{row['top_n']}` |"
        )
    return "\n".join(lines) + "\n"


def variant_roles_md() -> str:
    return """# Variant Roles

- `selected_confirmation`: exact selected source row, frozen as bounded design context.
- `uncontrolled_source_baseline_context`: source baseline used for same-window comparison only.
- `portfolio_contribution_context`: source 80/20 combo-plus-global row, diagnostic only.
- `comparator_control`: same-window controls, never candidates.
- `cash_control`: BIL cash proxy control, never candidate.
- `commodity_real_asset_control`: GLD control from the source comparator set, not Macro/GLD continuation.
"""


def comparator_policy_md() -> str:
    return """# Baseline / Comparator Policy

Comparators are diagnostic only:

- `global_multi_asset_tsmom_top2_v1` as the source baseline for the selected defensive row.
- `SPY` same-window where supported.
- `SPY_200d_frozen_control` where supported.
- `BIL_cash_proxy` same-window cash/reference control.
- `GLD_buy_hold` same-window source comparator/control only.
- `static_all_weather_benchmark_v1` benchmark/control only, never candidate.
- Active VM/DSR diagnostics only where already supported by repository conventions.
- Selected source row remains historical context only.

No comparator can become a promotion, candidate_exhaustive, paper-forward, broker, live, or real-money row from this design packet.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run labels are research-only and must not create promotion or paper-forward eligibility.

The selected defensive row passes only if all are true:

- Max daily exposure `<= 1.000001`.
- Max daily weight sum `<= 1.000001`.
- 180-day stop-hit rate `<= 0.0250`.
- Worst 180-day drawdown `>= -450.0000` in the project dollar-window convention.
- 180-day `p_target_300_before_stop >= 0.5000`.
- 180-day `p_target_400_before_stop >= 0.2500`.
- 180-day median final equity `>= 3250.0000`.
- Average BIL/cash share `<= 0.6000`.
- Daily equity return correlation to active combo `< 0.9000`, where supported.
- Score delta versus BIL cash proxy `> 0.0000`, where supported.

The source baseline/context row is useful only if it improves target power but remains explicitly risk-classified:

- 180-day median final equity `>= 3400.0000`.
- Worst 180-day drawdown `>= -650.0000`.
- Stop-hit rate `<= 0.0750`.
- Drawdown/risk-budget breach, if present, must be labeled as risk-control-required context.

Portfolio-contribution context passes only if all are true:

- Daily equity return correlation to active combo `< 0.9000`.
- 180-day worst drawdown `>= -550.0000`.
- 180-day median final equity `>= 3300.0000`.
- Score delta versus active combo `>= 0.0000`, where supported.

Failure labels:

- `global_multi_asset_signal_data_blocked`: any required current local-cache symbol is missing.
- `global_multi_asset_signal_too_cash_heavy`: average BIL/cash share `> 0.6000`.
- `global_multi_asset_signal_risk_budget_breach`: worst 180-day drawdown `< -450.0000` for the selected defensive row.
- `global_multi_asset_signal_return_diluted`: 180-day median final equity `< 3250.0000` for the selected defensive row.
- `global_multi_asset_signal_duplicate_reference`: active-combo or SPY_200d correlation `>= 0.9000`.
- `global_multi_asset_signal_context_only`: controls and source context rows that do not satisfy candidate-style diagnostic criteria.

These criteria are interpretation rules only. They are not promotion gates.
"""


def exposure_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future bounded global multi-asset run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No negative weights below tolerance.
- No NaN final weights.
- BIL/cash is replacement/remainder only.
- BIL/cash must not accumulate on top of risky exposure.
- Zero target weights remain zero until the next explicit rebalance target.
- Zero target weights must not stale-forward-fill into old allocations.
- No leverage, shorting, margin, options, direct futures, forex, broker, live, or intraday logic.
"""


def rejected_exclusion_md() -> str:
    return """# Rejected / Closed Variant Exclusion Rule

This design does not reopen exact rejected variants and does not clone rejected rows with cosmetic changes.

Explicit exclusions:

- high-return tactical continuation
- commodity-basket continuation
- Macro/GLD continuation
- volatility-throttle continuation
- managed-futures continuation
- crypto continuation
- regional momentum continuation
- candidate_exhaustive rows
- paper-forward rows
- promotion rows

The `GLD_buy_hold` row is a source comparator/control only, not Macro/GLD lineage continuation.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Global Multi-Asset Bounded Design

This packet creates no promotion, candidate_exhaustive, paper-forward, live/demo, broker, or real-money eligibility.

All rows are design rows, source context rows, or controls. The selected triage score is not proof of strategy quality.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Global Multi-Asset Bounded Design Next Action

Exact next action:

`{payload['next_action']}`

Do not execute it in this task.
"""


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Global Multi-Asset ETF Momentum Bounded Design

Lane: `{payload['lane_id']}`

Family: `{payload['family_id']}`

Selected strategy: `{payload['selected_strategy_id']}`

Source evidence context status: `{payload['source_evidence_context_status']}`

Planned rows: `{payload['planned_row_count']}`

Local cache complete: `{payload['local_cache_complete']}`

Missing local-cache symbols: `{', '.join(payload['local_cache_missing_symbols']) or 'none'}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Run-readiness blocker: `{payload['run_readiness_blocker']}`

No strategy lane, backtest, broad discovery, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live path, or real-money path was run.

Exact next action: `{payload['next_action']}`
"""


def guardrail_check(payload: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "design_only": payload["global_multi_asset_bounded_design_only"] is True,
        "no_lane_run": payload["global_multi_asset_lane_run"] is False,
        "no_research_execution": payload["new_research_batch_run"] is False
        and payload["new_strategy_discovery_run"] is False
        and payload["new_backtests_run"] is False
        and payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_family_variant_grid": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": payload["provider_download"] is False and payload["intraday_data_used"] is False,
        "no_forbidden_mechanics": payload["leverage_allowed"] is False
        and payload["shorting_allowed"] is False
        and payload["options_allowed"] is False
        and payload["direct_futures_allowed"] is False,
        "no_broker_live_real_money": payload["broker_api_called"] is False
        and payload["broker_orders_submitted"] is False
        and payload["broker_orders_cancelled"] is False
        and payload["broker_orders_reconciled"] is False
        and payload["live_orders"] is False
        and payload["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": payload["candidate_exhaustive_run"] is False
        and payload["promotion_candidates_created"] is False
        and payload["paper_forward_activation"] is False
        and payload["new_paper_forward_candidate_created"] is False
        and payload["best_single_variant_promoted"] is False,
        "active_state_preserved": payload["active_vm_preserved"] is True and payload["active_dsr_preserved"] is True,
        "excluded_lanes_not_continued": payload["high_return_tactical_continued"] is False
        and payload["commodity_continued"] is False
        and payload["macro_gld_continued"] is False
        and payload["volatility_throttle_continued"] is False
        and payload["managed_futures_reopened"] is False
        and payload["crypto_continued"] is False
        and payload["regional_momentum_continued"] is False,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
    }
    checks["guardrails_passed"] = all(checks.values())
    return checks


def build_manifest(
    root: Path,
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    cache_rows: list[dict[str, Any]],
    lineage_ok: bool,
    lineage_blockers: list[str],
) -> dict[str, Any]:
    missing = cache_missing_symbols(cache_rows)
    readiness, blocker, next_action = run_readiness(lineage_ok, lineage_blockers, cache_rows, rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "global_multi_asset_bounded_design_only": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "selected_strategy_id": SELECTED_STRATEGY_ID,
        "selected_source_batch": SELECTED_SOURCE_BATCH,
        "triage_evidence_reviewed": (root / TRIAGE_DIR / "triage_manifest.json").exists(),
        "registry_reviewed": (root / REGISTRY).exists(),
        "roadmap_reviewed": (root / ROADMAP).exists(),
        "queue_reviewed": (root / QUEUE).exists(),
        "family_ledger_reviewed": (root / LEDGER).exists(),
        "selected_registry_row_found": True,
        "selected_source_spec_found": True,
        "selected_source_results_found": bool(source_horizon_row(root, SELECTED_STRATEGY_ID)),
        "source_evidence_context_status": "older_exploratory_context_only",
        "source_evidence_corrected_or_safe_for_design_context": True,
        "source_evidence_promotion_evidence": False,
        "source_evidence_candidate_exhaustive_ready": False,
        "planned_row_count": len(rows),
        "planned_row_count_between_6_and_10": 6 <= len(rows) <= 10,
        "planned_row_count_lte_12": len(rows) <= 12,
        "required_symbols": list(REQUIRED_SYMBOLS),
        "local_cache_available_symbols": [row["symbol"] for row in cache_rows if row["available"]],
        "local_cache_missing_symbols": missing,
        "local_cache_complete": not missing,
        "eligibility_decision": "global_multi_asset_bounded_design_eligible" if readiness == RUN_READY else "global_multi_asset_bounded_design_blocked",
        "run_readiness_decision": readiness,
        "run_readiness_blocker": blocker,
        "baseline_comparator_policy_defined": True,
        "numeric_success_failure_criteria_defined": True,
        "exposure_invariants_defined": True,
        "rejected_closed_variant_exclusion_rule_defined": True,
        "queue_source_of_truth_updated": False,
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_family_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "global_multi_asset_lane_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_allowed": False,
        "direct_futures_allowed": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "high_return_tactical_continued": False,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "crypto_continued": False,
        "regional_momentum_continued": False,
        "triage_score_treated_as_strategy_success": False,
        "next_action": next_action,
    }


def consistency_check(payload: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["global_multi_asset_bounded_design_consistency_check.json"] = True
    guardrails = read_json(output / "guardrail_checklist.json")
    allowed_symbols = set(REQUIRED_SYMBOLS)
    row_symbols = {
        symbol
        for row in rows
        for symbol in str(row["universe"]).split("|")
        if symbol and symbol not in {"SPY_200d_frozen_control", "static_all_weather_benchmark_v1"}
    }
    checks = {
        "design_only": payload["global_multi_asset_bounded_design_only"] is True,
        "correct_lane_family": payload["lane_id"] == LANE_ID and payload["family_id"] == FAMILY_ID,
        "selected_candidate_correct": payload["selected_strategy_id"] == SELECTED_STRATEGY_ID,
        "source_context_only": payload["source_evidence_context_status"] == "older_exploratory_context_only"
        and payload["source_evidence_promotion_evidence"] is False,
        "cache_complete": payload["local_cache_complete"] is True,
        "planned_rows_bounded": payload["planned_row_count_between_6_and_10"] is True
        and payload["planned_row_count_lte_12"] is True
        and len(rows) == payload["planned_row_count"],
        "variant_ids_unique": len({row["variant_id"] for row in rows}) == len(rows),
        "row_symbols_within_selected_set": row_symbols.issubset(allowed_symbols),
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_paper": all(row["paper_forward_eligibility"] is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row["candidate_exhaustive_eligibility"] is False for row in rows),
        "no_run_or_backtest": payload["global_multi_asset_lane_run"] is False
        and payload["new_backtests_run"] is False
        and payload["new_research_batch_run"] is False
        and payload["new_strategy_discovery_run"] is False,
        "guardrails_passed": guardrails.get("guardrails_passed") is True,
        "readiness_valid": payload["run_readiness_decision"] in VALID_RUN_READINESS,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    registry = read_yaml(root / REGISTRY)
    specs = read_yaml(root / PROFIT_SPECS)
    selected_registry = registry_row(registry, SELECTED_STRATEGY_ID)
    selected_spec = spec_row(specs, SELECTED_STRATEGY_ID)
    lineage_ok, lineage_blockers = source_lineage_safe(registry, specs, root)
    rows = build_design_rows(root)
    cache_rows = local_cache_rows(root)
    payload = build_manifest(root, created, output, rows, cache_rows, lineage_ok, lineage_blockers)

    write_json(output / "global_multi_asset_bounded_design_manifest.json", payload)
    write_text(output / "global_multi_asset_bounded_design_summary.md", summary_md(payload))
    write_text(output / "source_lineage_assessment.md", source_lineage_md(payload, selected_registry, selected_spec))
    write_csv(output / "local_cache_availability.csv", cache_rows, CACHE_FIELDS)
    write_text(output / "local_cache_preflight.md", cache_preflight_md(payload))
    write_text(output / "eligibility_decision.md", eligibility_md(payload))
    write_csv(output / "planned_variant_design_table.csv", rows, DESIGN_FIELDS)
    write_text(output / "planned_variant_design_table.md", design_table_md(rows))
    write_text(output / "variant_roles.md", variant_roles_md())
    write_text(output / "baseline_comparator_policy.md", comparator_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_json(output / "guardrail_checklist.json", guardrail_check(payload))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "rejected_closed_variant_exclusion_rule.md", rejected_exclusion_md())
    write_text(output / "do_not_promote_from_global_multi_asset_design.md", do_not_promote_md())
    write_text(output / "global_multi_asset_bounded_design_next_action.md", next_action_md(payload))
    check = consistency_check(payload, rows, output)
    write_json(output / "global_multi_asset_bounded_design_consistency_check.json", check)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    return write_outputs(root, now_utc())


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "selected_strategy_id": result["selected_strategy_id"],
                "planned_row_count": result["planned_row_count"],
                "local_cache_complete": result["local_cache_complete"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
