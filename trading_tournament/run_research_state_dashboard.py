from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = REPO_ROOT / "evidence" / "research_state"
LATEST_DIR = OUTPUT_ROOT / "latest"
LATEST_ZIP = OUTPUT_ROOT / "latest_research_state_packet.zip"
PHASE = "historical_research_expansion_parallel_to_paper_demo_observation"
REQUIRED_FILES = [
    "README_FOR_ADVISOR.md",
    "current_state_summary.md",
    "active_observations.csv",
    "historical_leaders.csv",
    "candidate_status_matrix.csv",
    "blocked_and_gated_items.csv",
    "next_allowed_actions.csv",
    "warnings_and_limitations.md",
    "research_state_manifest.json",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def find_row(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str]:
    for row in rows:
        if str(row.get(key, "")) == value:
            return row
    return {}


def registry_strategy(registry: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    for row in registry.get("strategies", []):
        if str(row.get("id", "")) == strategy_id:
            return row
    return {}


def format_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "unavailable"


def build_dashboard() -> Path:
    status_rows = read_csv_rows(REPO_ROOT / "evidence" / "paper_forward_runs" / "latest" / "paper_forward_status.csv")
    triage_rows = read_csv_rows(REPO_ROOT / "evidence" / "candidate_triage" / "latest" / "RECENT_CANDIDATE_SCORECARD.csv")
    historical_queue = read_csv_rows(REPO_ROOT / "historical_research_expansion" / "HISTORICAL_CANDIDATE_FAMILY_QUEUE.csv")
    combo_queue = read_csv_rows(REPO_ROOT / "historical_research_expansion" / "COMBINATION_CANDIDATE_QUEUE.csv")
    combination_batch_manifest = read_json(REPO_ROOT / "evidence" / "combination_lab" / "latest" / "combination_batch1_manifest.json")
    combination_batch_status = read_csv_rows(REPO_ROOT / "evidence" / "combination_lab" / "latest" / "combination_batch1_status.csv")
    combination_verdict_audit_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "combination_lab"
        / "batch1_verdict_audit"
        / "latest"
        / "batch1_verdict_audit_manifest.json"
    )
    combination_diagnostics_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "combination_lab"
        / "batch1_diagnostics_completion"
        / "latest"
        / "batch1_diagnostics_completion_manifest.json"
    )
    research_diagnostics_manifest = read_json(REPO_ROOT / "evidence" / "research_diagnostics" / "latest" / "research_diagnostics_manifest.json")
    stock_gate1b_manifest = read_json(REPO_ROOT / "evidence" / "research_memos" / "gate1b" / "individual_stock_momentum" / "latest" / "gate1b_manifest.json")
    stock_gate1c_manifest = read_json(REPO_ROOT / "evidence" / "research_memos" / "gate1c" / "individual_stock_momentum" / "latest" / "gate1c_manifest.json")
    stock_gate1d_manifest = read_json(REPO_ROOT / "evidence" / "research_memos" / "gate1d" / "individual_stock_momentum" / "latest" / "gate1d_manifest.json")
    stock_gate1e_manifest = read_json(REPO_ROOT / "evidence" / "research_memos" / "gate1e" / "individual_stock_momentum" / "latest" / "gate1e_manifest.json")
    stock_gate1f_manifest = read_json(REPO_ROOT / "evidence" / "research_memos" / "gate1f" / "individual_stock_momentum" / "latest" / "gate1f_manifest.json")
    queue_reprioritization_manifest = read_json(
        REPO_ROOT / "evidence" / "research_memos" / "queue_reprioritization" / "latest" / "queue_reprioritization_manifest.json"
    )
    commodity_review_manifest = read_json(
        REPO_ROOT / "evidence" / "research_memos" / "commodity_basket_etf_momentum" / "latest" / "commodity_review_manifest.json"
    )
    commodity_data_acquisition_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "data_acquisition_reviews"
        / "commodity_basket_etf_momentum_v1"
        / "latest"
        / "commodity_data_acquisition_manifest.json"
    )
    commodity_fast_acquisition_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "data_acquisition_runs"
        / "commodity_basket_fast_exploratory"
        / "latest"
        / "acquisition_manifest.json"
    )
    commodity_exploratory_manifest = read_json(REPO_ROOT / "evidence" / "commodity_exploratory" / "latest" / "commodity_exploratory_manifest.json")
    commodity_risk_control_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "commodity_lab"
        / "risk_control_batch1"
        / "latest"
        / "risk_control_batch1_manifest.json"
    )
    commodity_risk_control_verdict_audit_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "commodity_lab"
        / "risk_control_batch1_verdict_audit"
        / "latest"
        / "risk_control_batch1_verdict_audit_manifest.json"
    )
    commodity_risk_control_diagnostics_completion_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "commodity_lab"
        / "risk_control_batch1_diagnostics_completion"
        / "latest"
        / "risk_control_batch1_diagnostics_completion_manifest.json"
    )
    fast_policy_exists = (REPO_ROOT / "data_policy" / "FAST_EXPLORATORY_DATA_POLICY.md").exists()
    crypto_fast_policy_exists = (REPO_ROOT / "data_policy" / "FAST_EXPLORATORY_CRYPTO_SPOT_POLICY.md").exists()
    crypto_fast_acquisition_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "data_acquisition_runs"
        / "crypto_spot_fast_exploratory"
        / "latest"
        / "acquisition_manifest.json"
    )
    crypto_tier2_risk_control_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "crypto_lab"
        / "tier2_risk_control_batch1"
        / "latest"
        / "tier2_risk_control_batch1_manifest.json"
    )
    global_multi_asset_fast_acquisition_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "data_acquisition_runs"
        / "global_multi_asset_fast_exploratory"
        / "latest"
        / "acquisition_manifest.json"
    )
    global_multi_asset_batch1_manifest = read_json(
        REPO_ROOT
        / "evidence"
        / "multi_asset_lab"
        / "fast_exploration_batch1"
        / "latest"
        / "fast_exploration_batch1_manifest.json"
    )
    registry = read_yaml(REPO_ROOT / "strategy_lab" / "strategy_registry.yaml")
    activation_manifest = read_json(
        REPO_ROOT
        / "paper_forward_observations"
        / "combo_SPY200d_GLD_50_50_v1"
        / "observation_activation_manifest.json"
    )
    triage_manifest = read_json(REPO_ROOT / "candidate_triage" / "candidate_triage_manifest.json")

    combo = find_row(status_rows, "strategy", "combo_SPY200d_GLD_50_50_v1")
    spy = find_row(status_rows, "strategy", "SPY_200d_trend_model")
    combo_registry = registry_strategy(registry, "profit_combo_SPY200d_GLD_50_50_v1")
    spy_registry = registry_strategy(registry, "SPY_200d_trend_model")
    stock_gate1b_registry = registry_strategy(registry, "individual_stock_momentum_gate1b_v1")
    commodity_registry = registry_strategy(registry, "commodity_basket_etf_momentum_v1")
    commodity_exploratory_registry = registry_strategy(registry, "commodity_basket_tsmom_top2_v1")
    commodity_risk_control_best_registry = registry_strategy(registry, commodity_risk_control_manifest.get("best_risk_control_candidate", ""))
    crypto_tier2_best_registry = registry_strategy(registry, crypto_tier2_risk_control_manifest.get("best_risk_control_candidate", ""))
    global_multi_asset_best_registry = registry_strategy(registry, global_multi_asset_batch1_manifest.get("best_multi_asset_candidate", ""))

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_ROOT / "runs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if LATEST_DIR.exists():
        shutil.rmtree(LATEST_DIR)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    active_rows: list[dict[str, Any]] = []
    for row in status_rows:
        if str(row.get("status", "")).startswith("active") or str(row.get("strategy", "")) in {
            "combo_SPY200d_GLD_50_50_v1",
            "SPY_200d_trend_model",
        }:
            active_rows.append(
                {
                    "strategy": row.get("strategy", ""),
                    "role": row.get("role", ""),
                    "status": row.get("status", ""),
                    "current_equity": row.get("current_equity", ""),
                    "decision_status": row.get("decision_status", ""),
                    "signal_state": row.get("signal_state", ""),
                    "paper_forward_active": str(row.get("strategy", "")) in {"combo_SPY200d_GLD_50_50_v1", "SPY_200d_trend_model"},
                    "notes": "paper/demo observation only; not a trading signal",
                }
            )
    for row in registry.get("strategies", []):
        row_id = str(row.get("id", ""))
        if row_id.startswith("paper_forward_") and row.get("paper_forward_active") is True:
            if row_id not in {active_row.get("strategy") for active_row in active_rows}:
                active_rows.append(
                    {
                        "strategy": row_id,
                        "role": row.get("role", "active_recovered_paper_demo_observation"),
                        "status": row.get("status", "active_paper_demo_observation"),
                        "current_equity": "",
                        "decision_status": "recovered_frozen_too_early",
                        "signal_state": "recovered_active_observation",
                        "paper_forward_active": True,
                        "notes": "conversation-recovered frozen paper/demo observation only; not a trading signal",
                    }
                )

    historical_leaders = [
        {
            "strategy": "combo_SPY200d_GLD_50_50_v1",
            "status": "practical_historical_leader_and_active_paper_demo_observation",
            "reason": "Practical leader from triage/promotion path; active forward observation is too early to judge.",
            "next_action": "run checkpoint only after 30 trading days; continue historical research in parallel",
        },
        {
            "strategy": "asset_class_tsmom_top2_v1",
            "status": "serious_challenger",
            "reason": "Serious historical challenger with more drawdown-budget usage than combo.",
            "next_action": "retain as primary benchmark for future combination reviews",
        },
        {
            "strategy": "SPY_200d_trend_model",
            "status": "frozen_paper_forward_control",
            "reason": "Frozen control; not replaced by combo.",
            "next_action": "observe beside combo without rule change",
        },
    ]

    candidate_rows = []
    for row in triage_rows:
        candidate_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "latest_verdict": row.get("latest_verdict", ""),
                "deserves_candidate_exhaustive": row.get("deserves_candidate_exhaustive", ""),
                "recommended_next_action": row.get("recommended_next_action", ""),
                "risk_label": row.get("risk_label", ""),
                "duplicate_label": row.get("duplicate_label", ""),
                "paper_forward_active": row.get("paper_forward_active", ""),
            }
        )
    recovered_candidate_ids = {
        "dsr_sector_top3_momentum_defensive_cash_v1",
        "dsr_sector_top2_momentum_200d_bil_v1",
        "gror_balanced_momentum_60_40_v1",
        "quality_momentum_etf_proxy",
        "quality_momentum_etf_proxy_risk_control_batch_1",
    }
    existing_candidates = {row.get("candidate_id") for row in candidate_rows}
    for row in registry.get("strategies", []):
        row_id = str(row.get("id", ""))
        if row_id in recovered_candidate_ids and row_id not in existing_candidates:
            candidate_rows.append(
                {
                    "candidate_id": row_id,
                    "latest_verdict": row.get("status", ""),
                    "deserves_candidate_exhaustive": str(bool(row.get("candidate_exhaustive_recommended", False))).lower(),
                    "recommended_next_action": row.get("allowed_next_action", ""),
                    "risk_label": row.get("risk_budget_status", ""),
                    "duplicate_label": row.get("duplication_risk", ""),
                    "paper_forward_active": row.get("paper_forward_active", False),
                }
            )

    blocked_rows = []
    for row in historical_queue:
        blocked_rows.append(
            {
                "item_id": row.get("candidate_id", ""),
                "lane": "historical_candidate_family_queue",
                "gate_status": row.get("current_gate_status", ""),
                "first_required_action": row.get("first_required_action", ""),
                "implementation_allowed_now": row.get("implementation_allowed_now", ""),
                "backtest_allowed_now": row.get("backtest_allowed_now", ""),
                "notes": row.get("notes", ""),
            }
        )
    for row in combo_queue:
        blocked_rows.append(
            {
                "item_id": row.get("combination_id", ""),
                "lane": "combination_candidate_queue",
                "gate_status": row.get("implementation_gate_status", ""),
                "first_required_action": "combination implementation review",
                "implementation_allowed_now": row.get("research_sample_allowed_now", ""),
                "backtest_allowed_now": row.get("candidate_exhaustive_allowed_now", ""),
                "notes": row.get("notes", ""),
            }
        )

    next_actions = [
        {
            "action": "create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1",
            "allowed_now": "true",
            "lane": "global_risk_on_risk_off_etf",
            "notes": "Next allowed recovered action is to create the prompt only; do not run GROR candidate_exhaustive during recovery.",
        },
        {
            "action": "global_multi_asset_batch1_research_sample_review",
            "allowed_now": "true",
            "lane": "global_multi_asset_fast_exploration_batch1",
            "notes": "Review Global Multi-Asset ETF Fast Exploration Batch 1; no candidate_exhaustive, paper-forward, broker, live-order, leverage, margin, shorting, futures, options, forex, intraday, or real-money action.",
        },
        {
            "action": "crypto_tier2_risk_control_research_sample_review",
            "allowed_now": "true",
            "lane": "crypto_spot_tier2_risk_control_batch1",
            "notes": "Review BTC/ETH spot-only Tier 2 risk-control results; no candidate_exhaustive, paper-forward, exchange, broker, leverage, margin, futures, perpetuals, options, live-order, or real-money action.",
        },
        {
            "action": "commodity_risk_control_research_sample_review",
            "allowed_now": "true",
            "lane": "commodity_risk_control_batch1",
            "notes": "Review Batch 1 risk-control results; no candidate_exhaustive, paper-forward, broker, or real-money action.",
        },
        {
            "action": "commodity_risk_control_verdict_diagnostics_review",
            "allowed_now": "true",
            "lane": "commodity_risk_control_batch1_verdict_audit",
            "notes": "Verdict audit completed and was superseded by diagnostics completion; no commodity candidate_exhaustive run.",
        },
        {
            "action": "commodity_risk_control_watchlist_review",
            "allowed_now": "true",
            "lane": "commodity_risk_control_batch1_diagnostics_completion",
            "notes": "Diagnostics completion supports watchlist-only for combo_plus_commodity_basket_80_20_v1; no candidate_exhaustive was run or recommended.",
        },
        {
            "action": "research_sample_review",
            "allowed_now": "true",
            "lane": "commodity_basket_fast_exploratory",
            "notes": "Review the fast exploratory commodity wrapper screen; no candidate_exhaustive, paper-forward, broker, or real-money action.",
        },
        {
            "action": "product_identity_terms_review",
            "allowed_now": "true",
            "lane": "commodity_basket_etf_momentum",
            "notes": "Still required later if the fast exploratory commodity screen is promising; no paper-forward approval.",
        },
        {
            "action": "commodity_data_acquisition_review",
            "allowed_now": "true",
            "lane": "commodity_basket_etf_momentum",
            "notes": "Completed as review; superseded by product_identity_terms_review because no symbols are approved for download yet.",
        },
        {
            "action": "create_commodity_basket_etf_momentum_review",
            "allowed_now": "true",
            "lane": "historical_research_queue_reprioritization",
            "notes": "Completed as commodity product/data review; superseded by commodity_data_acquisition_review as the next gate.",
        },
        {
            "action": "create_combination_design_implementation_review",
            "allowed_now": "true",
            "lane": "historical_research",
            "notes": "Preferred next historical strategy path; review only before coding.",
        },
        {
            "action": "improve_correlation_and_co_movement_diagnostics",
            "allowed_now": "true",
            "lane": "diagnostics",
            "notes": "Plan/design or reporting-only work; no strategy rules changed.",
        },
        {
            "action": "use_attribution_diagnostics_before_future_combination_candidate_exhaustive_review",
            "allowed_now": "true",
            "lane": "diagnostics",
            "notes": "Attribution diagnostics should be reviewed before any future combination candidate_exhaustive prompt.",
        },
        {
            "action": "select_sharadar_package_and_terms_review",
            "allowed_now": "true",
            "lane": "individual_stock_momentum_gate1f",
            "notes": "Select Sharadar/Nasdaq package and terms/security path only; no provider call, API key, stock loader, or data download.",
        },
        {
            "action": "judge_combo_forward_observation",
            "allowed_now": "false",
            "lane": "paper_forward",
            "notes": "Not before 30 trading days; current status is inconclusive_too_early.",
        },
        {
            "action": "tune_active_combo",
            "allowed_now": "false",
            "lane": "paper_forward",
            "notes": "Active combo rules are frozen.",
        },
        {
            "action": "replace_spy200d",
            "allowed_now": "false",
            "lane": "paper_forward_governance",
            "notes": "SPY_200d remains frozen control.",
        },
    ]

    combination_verdict = combination_batch_manifest.get("overall_verdict", "not_run")
    combination_audit_decision = combination_verdict_audit_manifest.get("verdict_audit_decision", "not_run")
    combination_audit_candidate_exhaustive_decision = combination_verdict_audit_manifest.get(
        "candidate_exhaustive_decision",
        "not_reviewed",
    )
    audited_verdicts = combination_verdict_audit_manifest.get("audited_verdicts", {})
    audited_verdict_summary = (
        ", ".join(f"{key}:{value}" for key, value in sorted(audited_verdicts.items()))
        if isinstance(audited_verdicts, dict) and audited_verdicts
        else "unavailable"
    )
    combination_diagnostics_decision = combination_diagnostics_manifest.get(
        "diagnostics_completion_decision",
        "not_run",
    )
    combination_diagnostics_status = (
        f"target-window co-movement={combination_diagnostics_manifest.get('target_window_comovement_status', 'unavailable')}; "
        f"component contribution={combination_diagnostics_manifest.get('component_contribution_status', 'unavailable')}; "
        f"drawdown coincidence={combination_diagnostics_manifest.get('drawdown_coincidence_detail_status', 'unavailable')}"
    )
    attribution_diagnostics_available = bool(research_diagnostics_manifest.get("attribution_diagnostics_available", False))
    target_window_attribution_available = bool(research_diagnostics_manifest.get("target_window_attribution_available", False))
    component_drawdown_attribution_available = bool(research_diagnostics_manifest.get("component_drawdown_attribution_available", False))
    recovery_attribution_available = bool(research_diagnostics_manifest.get("recovery_attribution_available", False))
    worst_n_drawdown_export_available = bool(research_diagnostics_manifest.get("worst_n_drawdown_export_available", False))
    combination_status_summary = ", ".join(
        f"{row.get('combination_id', '')}:{row.get('verdict', '')}"
        for row in combination_batch_status
        if row.get("combination_id")
    ) or "unavailable"

    summary = f"""# Current Research State

current_phase: `{PHASE}`

## Paper/Demo Observation

- combo active as paper/demo observation: `{combo.get('status', activation_manifest.get('activation_status', 'unavailable'))}`
- combo paper_forward_active: `{str(combo_registry.get('paper_forward_active', activation_manifest.get('paper_forward_active', False))).lower()}`
- combo current equity: `{format_money(combo.get('current_equity'))}`
- combo checkpoint_status: `{combo.get('decision_status', 'unavailable')}`
- SPY_200d frozen control: `{str(spy_registry.get('rules_frozen', False)).lower()}`
- SPY_200d status: `{spy.get('status', spy_registry.get('status', 'unavailable'))}`
- SPY_200d replaced: `false`

Forward checkpoint is not ready for judgment. No conclusion is allowed from first-day forward observation evidence.

## Historical Research Continues

The 30-trading-day paper-forward checkpoint rule does not block historical research. Historical research, data reviews, implementation reviews, diagnostics design, and predeclared combination-design preparation may continue in parallel under evidence gates.

## Candidate Triage

- no recent research_sample candidate deserves candidate_exhaustive now: `true`
- QQQ/value candidates: archived references
- sector top2 and managed-futures proxy: watchlist
- combo remains practical historical leader
- asset_class_tsmom_top2_v1 remains serious challenger

	## Next Allowed Action

	Latest historical combination batch status: `{combination_verdict}`. Batch row statuses: {combination_status_summary}.

	Latest combination verdict audit: `{combination_audit_decision}`. Audited verdicts: {audited_verdict_summary}. Candidate_exhaustive review decision: `{combination_audit_candidate_exhaustive_decision}`.

	Latest combination diagnostics completion: `{combination_diagnostics_decision}`. Diagnostics status: {combination_diagnostics_status}. Candidate_exhaustive run: `false`.

	Attribution diagnostics available: `{str(attribution_diagnostics_available).lower()}`. Target-window attribution: `{str(target_window_attribution_available).lower()}`. Component drawdown attribution: `{str(component_drawdown_attribution_available).lower()}`. Recovery attribution: `{str(recovery_attribution_available).lower()}`. Worst-N drawdown export: `{str(worst_n_drawdown_export_available).lower()}`.

	Individual stock momentum Gate 1B historical decision: `{stock_gate1b_manifest.get('decision', 'unavailable')}`.
	Individual stock momentum Gate 1C historical decision: `{stock_gate1c_manifest.get('decision', 'unavailable')}`.
	Individual stock momentum Gate 1D historical decision: `{stock_gate1d_manifest.get('decision', 'unavailable')}`.
	Individual stock momentum Gate 1E Norgate blocker: `{stock_gate1e_manifest.get('decision', 'unavailable')}`. Local access: `{stock_gate1e_manifest.get('local_access_status', 'unavailable')}`. Terms: `{stock_gate1e_manifest.get('terms_acceptance_status', 'unavailable')}`.
	Individual stock momentum Gate 1F status: `{stock_gate1b_registry.get('status', stock_gate1f_manifest.get('decision', 'unavailable'))}`. Decision: `{stock_gate1f_manifest.get('decision', 'unavailable')}`. Provider focus: `{stock_gate1f_manifest.get('provider_focus', 'unavailable')}`. Package selected: `{str(stock_gate1f_manifest.get('package_selected', False)).lower()}`. Implementation: `not_implemented`; data downloaded: `false`; provider API called: `false`; next action: `user_select_sharadar_package`.

	Historical research queue reprioritization: `{queue_reprioritization_manifest.get('decision', 'unavailable')}`. Stock momentum remains provider-blocked/conditional, with Norgate blocked and Sharadar pending package/terms selection. Next family: `{queue_reprioritization_manifest.get('next_family', 'unavailable')}`. Next action: `{queue_reprioritization_manifest.get('next_allowed_action', 'unavailable')}`.

	Commodity basket ETF product/data review: `{commodity_review_manifest.get('decision', 'unavailable')}`. Products reviewed: `{', '.join(commodity_review_manifest.get('products_reviewed', [])) if isinstance(commodity_review_manifest.get('products_reviewed', []), list) else 'unavailable'}`. Data acquisition review approved: `{str(commodity_review_manifest.get('data_acquisition_review_approved', False)).lower()}`. Implementation approved: `{str(commodity_review_manifest.get('implementation_approved', False)).lower()}`. Commodity data downloaded: `{str(commodity_review_manifest.get('data_downloaded', False)).lower()}`. Next action: `{commodity_review_manifest.get('next_allowed_action', 'unavailable')}`.

	Commodity basket ETF data acquisition review: `{commodity_data_acquisition_manifest.get('decision', 'unavailable')}`. Future download symbols approved under the old strict lane: `{', '.join(commodity_data_acquisition_manifest.get('future_download_symbols_approved', [])) if isinstance(commodity_data_acquisition_manifest.get('future_download_symbols_approved', []), list) else 'unavailable'}`. Data downloaded in that review: `{str(commodity_data_acquisition_manifest.get('data_downloaded', False)).lower()}`. Provider API called in that review: `{str(commodity_data_acquisition_manifest.get('provider_api_called', False)).lower()}`.

	Fast exploratory ETF/fund data policy available: `{str(fast_policy_exists).lower()}`. Commodity fast exploratory acquisition downloaded symbols: `{', '.join(commodity_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(commodity_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}`. Failed symbols: `{', '.join(commodity_fast_acquisition_manifest.get('failed_symbols', [])) if isinstance(commodity_fast_acquisition_manifest.get('failed_symbols', []), list) else 'unavailable'}`. Raw OHLCV in compact evidence: `{str(commodity_fast_acquisition_manifest.get('raw_ohlcv_included', False)).lower()}`.

	Commodity exploratory screen status: `{commodity_exploratory_registry.get('status', commodity_exploratory_manifest.get('verdict', 'unavailable'))}`. Verdict: `{commodity_exploratory_manifest.get('verdict', 'unavailable')}`. Candidate_exhaustive run: `{str(commodity_exploratory_manifest.get('candidate_exhaustive_run', False)).lower()}`. Paper-forward active: `{str(commodity_exploratory_manifest.get('paper_forward_active', False)).lower()}`. Real-money recommendation: `{str(commodity_exploratory_manifest.get('real_money_recommendation', False)).lower()}`.

	Commodity Risk-Control Batch 1 status: completed. Base commodity verdict correction: `{commodity_risk_control_manifest.get('base_commodity_verdict_correction', 'unavailable')}`. Best risk-control candidate: `{commodity_risk_control_manifest.get('best_risk_control_candidate', 'unavailable')}`. Candidate_exhaustive recommended: `{str(commodity_risk_control_manifest.get('candidate_exhaustive_recommended', False)).lower()}`. Candidate_exhaustive run: `{str(commodity_risk_control_manifest.get('candidate_exhaustive_run', False)).lower()}`. Best row registry status: `{commodity_risk_control_best_registry.get('status', 'unavailable')}`.

	Commodity Risk-Control Batch 1 verdict audit: `{commodity_risk_control_verdict_audit_manifest.get('verdict_audit_decision', 'unavailable')}`. Candidate_exhaustive decision: `{commodity_risk_control_verdict_audit_manifest.get('candidate_exhaustive_decision', 'unavailable')}`. Target-window co-movement: `{commodity_risk_control_verdict_audit_manifest.get('target_window_comovement_status', 'unavailable')}`. Component contribution: `{commodity_risk_control_verdict_audit_manifest.get('component_contribution_status', 'unavailable')}`. Candidate_exhaustive run: `{str(commodity_risk_control_verdict_audit_manifest.get('candidate_exhaustive_run', False)).lower()}`.

	Commodity Risk-Control Batch 1 diagnostics completion: `{commodity_risk_control_diagnostics_completion_manifest.get('decision', 'unavailable')}`. Target-window co-movement: `{commodity_risk_control_diagnostics_completion_manifest.get('target_window_comovement_status', 'unavailable')}`. Component contribution: `{commodity_risk_control_diagnostics_completion_manifest.get('component_contribution_status', 'unavailable')}`. Drawdown overlap: `{commodity_risk_control_diagnostics_completion_manifest.get('drawdown_overlap_status', 'unavailable')}`. Candidate_exhaustive recommended: `{str(commodity_risk_control_diagnostics_completion_manifest.get('candidate_exhaustive_review_recommended', False)).lower()}`. Candidate_exhaustive run: `{str(commodity_risk_control_diagnostics_completion_manifest.get('candidate_exhaustive_run', False)).lower()}`.

	Crypto spot fast exploratory policy available: `{str(crypto_fast_policy_exists).lower()}`. BTC/ETH cache confirmed: `{', '.join(crypto_fast_acquisition_manifest.get('cache_confirmed_symbols', [])) if isinstance(crypto_fast_acquisition_manifest.get('cache_confirmed_symbols', []), list) else 'unavailable'}`. Downloaded symbols: `{', '.join(crypto_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(crypto_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}`. Failed symbols: `{', '.join(crypto_fast_acquisition_manifest.get('failed_symbols', [])) if isinstance(crypto_fast_acquisition_manifest.get('failed_symbols', []), list) else 'unavailable'}`. Raw OHLCV in compact evidence: `{str(crypto_fast_acquisition_manifest.get('raw_ohlcv_in_evidence', False)).lower()}`.

		Crypto Spot Tier 2 Risk-Control Batch 1 status: `{str(crypto_tier2_risk_control_manifest.get('research_sample_run', False)).lower()}`. Best risk-control candidate: `{crypto_tier2_risk_control_manifest.get('best_risk_control_candidate', 'unavailable')}`. Candidate_exhaustive recommended: `{str(crypto_tier2_risk_control_manifest.get('candidate_exhaustive_recommended', False)).lower()}`. Candidate_exhaustive run: `{str(crypto_tier2_risk_control_manifest.get('candidate_exhaustive_run', False)).lower()}`. Data downloaded in Profit Exploration: `{str(crypto_tier2_risk_control_manifest.get('data_downloaded', False)).lower()}`. Best row registry status: `{crypto_tier2_best_registry.get('status', 'unavailable')}`. Paper-forward active: `{str(crypto_tier2_risk_control_manifest.get('paper_forward_active', False)).lower()}`. Real-money recommendation: `{str(crypto_tier2_risk_control_manifest.get('real_money_recommendation', False)).lower()}`.

		Global multi-asset fast acquisition downloaded symbols: `{', '.join(global_multi_asset_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(global_multi_asset_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}`. Cache-confirmed symbols: `{', '.join(global_multi_asset_fast_acquisition_manifest.get('cache_confirmed_symbols', [])) if isinstance(global_multi_asset_fast_acquisition_manifest.get('cache_confirmed_symbols', []), list) else 'unavailable'}`. Failed symbols: `{', '.join(global_multi_asset_fast_acquisition_manifest.get('failed_symbols', [])) if isinstance(global_multi_asset_fast_acquisition_manifest.get('failed_symbols', []), list) else 'unavailable'}`. Raw OHLCV in compact evidence: `{str(global_multi_asset_fast_acquisition_manifest.get('raw_ohlcv_included', False)).lower()}`.

		Global Multi-Asset ETF Fast Exploration Batch 1 status: `{str(global_multi_asset_batch1_manifest.get('research_sample_run', False)).lower()}`. Best multi-asset candidate: `{global_multi_asset_batch1_manifest.get('best_multi_asset_candidate', 'unavailable')}`. Candidate_exhaustive recommended: `{str(global_multi_asset_batch1_manifest.get('candidate_exhaustive_recommended', False)).lower()}`. Candidate_exhaustive run: `{str(global_multi_asset_batch1_manifest.get('candidate_exhaustive_run', False)).lower()}`. Data downloaded in Profit Exploration: `{str(global_multi_asset_batch1_manifest.get('data_downloaded', False)).lower()}`. Best row registry status: `{global_multi_asset_best_registry.get('status', 'unavailable')}`. Paper-forward active: `{str(global_multi_asset_batch1_manifest.get('paper_forward_active', False)).lower()}`. Real-money recommendation: `{str(global_multi_asset_batch1_manifest.get('real_money_recommendation', False)).lower()}`.

		Preferred next action: review Global Multi-Asset ETF Fast Exploration Batch 1 as research_sample evidence only; no candidate_exhaustive is currently recommended. keep combo_plus_commodity_basket_80_20_v1 on watchlist only unless new evidence justifies reopening; product identity and wrapper/tax/roll-risk review remains required if reopened; use attribution diagnostics before any future combination candidate_exhaustive review. Do not tune the active combo, replace SPY_200d, or add random one-off ETF momentum variants.

## Research-Only Boundary

No paper-forward strategy was implemented, no backtest was run, no candidate_exhaustive was run, no broker integration or live orders were added, and no real-money recommendation is made. Controlled fast exploratory ETF/fund wrapper data acquisitions may be recorded separately when approved by prompt.
"""

    readme = """# README For Advisor

This is a compact current-state dashboard generated from existing latest evidence only.

It does not run backtests, run Profit Exploration, run candidate_exhaustive, download data, implement strategies, change paper-forward rules, connect to brokers, place live orders, or recommend real-money trading.

Read `current_state_summary.md` first, then the CSV matrices for active observations, historical leaders, candidate status, gated items, and next allowed actions.
"""

    warnings = """# Warnings And Limitations

- Research-only paper/demo evidence.
- No real-money recommendation.
- No broker integration.
- No live orders.
- No order placement.
- Dashboard reads existing latest evidence only.
- It does not compute strategy returns from raw data.
- It does not validate the active combo observation.
- Forward observation remains too early to judge before 30 trading days.
- Historical research may continue in parallel but must follow gates.
- Active combo and SPY_200d rules must not be changed.
"""

    manifest = {
        "attribution_diagnostics_available": attribution_diagnostics_available,
        "backtest_run": False,
        "broker_integration": False,
        "candidate_exhaustive_run": False,
        "combo_checkpoint_status": combo.get("decision_status", "unavailable"),
        "combo_current_equity": combo.get("current_equity", ""),
        "combo_paper_forward_active": bool(combo_registry.get("paper_forward_active", activation_manifest.get("paper_forward_active", False))),
        "combination_batch1_overall_verdict": combination_verdict,
        "combination_batch1_verdict_audit_decision": combination_audit_decision,
        "combination_batch1_candidate_exhaustive_review_decision": combination_audit_candidate_exhaustive_decision,
        "combination_batch1_diagnostics_completion_decision": combination_diagnostics_decision,
        "combination_batch1_target_window_comovement_status": combination_diagnostics_manifest.get("target_window_comovement_status", "unavailable"),
        "combination_batch1_component_contribution_status": combination_diagnostics_manifest.get("component_contribution_status", "unavailable"),
        "combination_batch1_drawdown_coincidence_detail_status": combination_diagnostics_manifest.get("drawdown_coincidence_detail_status", "unavailable"),
        "component_drawdown_attribution_available": component_drawdown_attribution_available,
        "current_phase": PHASE,
        "data_downloaded": False,
        "historical_research_parallel_allowed": True,
        "individual_stock_momentum_gate1b_decision": stock_gate1b_manifest.get("decision", "unavailable"),
        "individual_stock_momentum_gate1b_status": stock_gate1b_registry.get("status", "unavailable"),
        "individual_stock_momentum_gate1b_implementation_status": stock_gate1b_registry.get("implementation_status", "unavailable"),
        "individual_stock_momentum_gate1c_decision": stock_gate1c_manifest.get("decision", "unavailable"),
        "individual_stock_momentum_gate1c_status": stock_gate1b_registry.get("status", "unavailable"),
        "individual_stock_momentum_gate1c_implementation_status": stock_gate1b_registry.get("implementation_status", "unavailable"),
        "individual_stock_momentum_gate1c_data_downloaded": bool(stock_gate1c_manifest.get("data_downloaded", False)),
        "individual_stock_momentum_gate1c_provider_api_called": bool(stock_gate1c_manifest.get("provider_api_called", False)),
        "individual_stock_momentum_gate1d_decision": stock_gate1d_manifest.get("decision", "unavailable"),
        "individual_stock_momentum_gate1d_status": stock_gate1b_registry.get("status", "unavailable"),
        "individual_stock_momentum_gate1d_implementation_status": stock_gate1b_registry.get("implementation_status", "unavailable"),
        "individual_stock_momentum_gate1d_data_downloaded": bool(stock_gate1d_manifest.get("data_downloaded", False)),
        "individual_stock_momentum_gate1d_provider_api_called": bool(stock_gate1d_manifest.get("provider_api_called", False)),
        "individual_stock_momentum_gate1d_preferred_provider": stock_gate1d_manifest.get("preferred_provider", "unavailable"),
        "individual_stock_momentum_gate1e_decision": stock_gate1e_manifest.get("decision", "unavailable"),
        "individual_stock_momentum_gate1e_status": stock_gate1b_registry.get("status", "unavailable"),
        "individual_stock_momentum_gate1e_implementation_status": stock_gate1b_registry.get("implementation_status", "unavailable"),
        "individual_stock_momentum_gate1e_data_downloaded": bool(stock_gate1e_manifest.get("data_downloaded", False)),
        "individual_stock_momentum_gate1e_full_stock_universe_downloaded": bool(stock_gate1e_manifest.get("full_stock_universe_downloaded", False)),
        "individual_stock_momentum_gate1e_provider_api_called": bool(stock_gate1e_manifest.get("provider_api_called", False)),
        "individual_stock_momentum_gate1e_local_access_status": stock_gate1e_manifest.get("local_access_status", "unavailable"),
        "individual_stock_momentum_gate1e_terms_acceptance_status": stock_gate1e_manifest.get("terms_acceptance_status", "unavailable"),
        "individual_stock_momentum_gate1f_decision": stock_gate1f_manifest.get("decision", "unavailable"),
        "individual_stock_momentum_gate1f_status": stock_gate1b_registry.get("status", "unavailable"),
        "individual_stock_momentum_gate1f_implementation_status": stock_gate1b_registry.get("implementation_status", "unavailable"),
        "individual_stock_momentum_gate1f_data_downloaded": bool(stock_gate1f_manifest.get("data_downloaded", False)),
        "individual_stock_momentum_gate1f_provider_api_called": bool(stock_gate1f_manifest.get("provider_api_called", False)),
        "individual_stock_momentum_gate1f_package_selected": bool(stock_gate1f_manifest.get("package_selected", False)),
        "individual_stock_momentum_gate1f_provider_focus": stock_gate1f_manifest.get("provider_focus", "unavailable"),
        "latest_folder_file_count": len(REQUIRED_FILES),
        "live_orders": False,
        "no_recent_research_sample_candidate_exhaustive": str(triage_manifest.get("decision", "")).lower().find("no_new_candidate_exhaustive") >= 0,
        "order_placement": False,
        "paper_forward_rule_changed": False,
        "profit_exploration_run": False,
        "real_money_recommendation": False,
        "research_queue_reprioritization_decision": queue_reprioritization_manifest.get("decision", "unavailable"),
        "research_queue_reprioritization_next_allowed_action": queue_reprioritization_manifest.get("next_allowed_action", "unavailable"),
        "research_queue_reprioritization_next_family": queue_reprioritization_manifest.get("next_family", "unavailable"),
        "commodity_basket_etf_momentum_status": commodity_registry.get("status", "unavailable"),
        "commodity_basket_etf_momentum_implementation_status": commodity_registry.get("implementation_status", "unavailable"),
        "commodity_basket_etf_momentum_allowed_next_action": commodity_registry.get("allowed_next_action", "unavailable"),
        "commodity_basket_etf_review_decision": commodity_review_manifest.get("decision", "unavailable"),
        "commodity_basket_etf_review_data_acquisition_review_approved": bool(commodity_review_manifest.get("data_acquisition_review_approved", False)),
        "commodity_basket_etf_review_implementation_approved": bool(commodity_review_manifest.get("implementation_approved", False)),
        "commodity_basket_etf_review_data_downloaded": bool(commodity_review_manifest.get("data_downloaded", False)),
        "commodity_basket_etf_review_provider_api_called": bool(commodity_review_manifest.get("provider_api_called", False)),
        "commodity_basket_etf_review_products_reviewed": commodity_review_manifest.get("products_reviewed", []),
        "commodity_data_acquisition_review_decision": commodity_data_acquisition_manifest.get("decision", "unavailable"),
        "commodity_data_acquisition_future_download_prompt_approved": bool(commodity_data_acquisition_manifest.get("future_download_prompt_approved", False)),
        "commodity_data_acquisition_future_download_symbols_approved": commodity_data_acquisition_manifest.get("future_download_symbols_approved", []),
        "commodity_data_acquisition_stage1_preferred_symbols_after_terms_review": commodity_data_acquisition_manifest.get("stage1_preferred_symbols_after_terms_review", []),
        "commodity_data_acquisition_data_downloaded": bool(commodity_data_acquisition_manifest.get("data_downloaded", False)),
        "commodity_data_acquisition_provider_api_called": bool(commodity_data_acquisition_manifest.get("provider_api_called", False)),
        "commodity_data_acquisition_strategy_implemented": bool(commodity_data_acquisition_manifest.get("strategy_implemented", False)),
        "fast_exploratory_data_policy_available": fast_policy_exists,
        "commodity_fast_exploratory_acquisition_data_downloaded": bool(commodity_fast_acquisition_manifest.get("data_downloaded", False)),
        "commodity_fast_exploratory_downloaded_symbols": commodity_fast_acquisition_manifest.get("downloaded_symbols", []),
        "commodity_fast_exploratory_failed_symbols": commodity_fast_acquisition_manifest.get("failed_symbols", []),
        "commodity_fast_exploratory_raw_ohlcv_included": bool(commodity_fast_acquisition_manifest.get("raw_ohlcv_included", False)),
        "commodity_exploratory_status": commodity_exploratory_registry.get("status", "unavailable"),
        "commodity_exploratory_implementation_status": commodity_exploratory_registry.get("implementation_status", "unavailable"),
        "commodity_exploratory_verdict": commodity_exploratory_manifest.get("verdict", "unavailable"),
        "commodity_exploratory_candidate_exhaustive_run": bool(commodity_exploratory_manifest.get("candidate_exhaustive_run", False)),
        "commodity_exploratory_paper_forward_active": bool(commodity_exploratory_manifest.get("paper_forward_active", False)),
        "commodity_exploratory_real_money_recommendation": bool(commodity_exploratory_manifest.get("real_money_recommendation", False)),
        "commodity_risk_control_batch1_completed": bool(commodity_risk_control_manifest.get("research_sample_run", False)),
        "commodity_risk_control_batch1_best_candidate": commodity_risk_control_manifest.get("best_risk_control_candidate", "unavailable"),
        "commodity_risk_control_batch1_candidate_exhaustive_recommended": bool(commodity_risk_control_manifest.get("candidate_exhaustive_recommended", False)),
        "commodity_risk_control_batch1_candidate_exhaustive_run": bool(commodity_risk_control_manifest.get("candidate_exhaustive_run", False)),
        "commodity_risk_control_batch1_data_downloaded": bool(commodity_risk_control_manifest.get("data_downloaded", False)),
        "commodity_risk_control_batch1_new_symbols_added": bool(commodity_risk_control_manifest.get("new_symbols_added", False)),
        "commodity_risk_control_batch1_base_verdict_correction": commodity_risk_control_manifest.get("base_commodity_verdict_correction", "unavailable"),
        "commodity_risk_control_verdict_audit_decision": commodity_risk_control_verdict_audit_manifest.get("verdict_audit_decision", "unavailable"),
        "commodity_risk_control_verdict_audit_candidate_exhaustive_decision": commodity_risk_control_verdict_audit_manifest.get("candidate_exhaustive_decision", "unavailable"),
        "commodity_risk_control_verdict_audit_candidate_exhaustive_run": bool(commodity_risk_control_verdict_audit_manifest.get("candidate_exhaustive_run", False)),
        "commodity_risk_control_verdict_audit_target_window_comovement_status": commodity_risk_control_verdict_audit_manifest.get("target_window_comovement_status", "unavailable"),
        "commodity_risk_control_verdict_audit_component_contribution_status": commodity_risk_control_verdict_audit_manifest.get("component_contribution_status", "unavailable"),
        "commodity_risk_control_diagnostics_completion_decision": commodity_risk_control_diagnostics_completion_manifest.get("decision", "unavailable"),
        "commodity_risk_control_diagnostics_completion_candidate_exhaustive_recommended": bool(commodity_risk_control_diagnostics_completion_manifest.get("candidate_exhaustive_review_recommended", False)),
        "commodity_risk_control_diagnostics_completion_candidate_exhaustive_run": bool(commodity_risk_control_diagnostics_completion_manifest.get("candidate_exhaustive_run", False)),
        "commodity_risk_control_diagnostics_completion_target_window_comovement_status": commodity_risk_control_diagnostics_completion_manifest.get("target_window_comovement_status", "unavailable"),
        "commodity_risk_control_diagnostics_completion_component_contribution_status": commodity_risk_control_diagnostics_completion_manifest.get("component_contribution_status", "unavailable"),
        "commodity_risk_control_diagnostics_completion_drawdown_overlap_status": commodity_risk_control_diagnostics_completion_manifest.get("drawdown_overlap_status", "unavailable"),
        "crypto_fast_exploratory_policy_available": crypto_fast_policy_exists,
        "crypto_spot_fast_acquisition_data_downloaded": bool(crypto_fast_acquisition_manifest.get("data_downloaded", False)),
        "crypto_spot_fast_cache_confirmed_symbols": crypto_fast_acquisition_manifest.get("cache_confirmed_symbols", []),
        "crypto_spot_fast_downloaded_symbols": crypto_fast_acquisition_manifest.get("downloaded_symbols", []),
        "crypto_spot_fast_failed_symbols": crypto_fast_acquisition_manifest.get("failed_symbols", []),
        "crypto_spot_fast_raw_ohlcv_included": bool(crypto_fast_acquisition_manifest.get("raw_ohlcv_in_evidence", False)),
        "crypto_tier2_risk_control_batch1_completed": bool(crypto_tier2_risk_control_manifest.get("research_sample_run", False)),
        "crypto_tier2_risk_control_batch1_best_candidate": crypto_tier2_risk_control_manifest.get("best_risk_control_candidate", "unavailable"),
        "crypto_tier2_risk_control_batch1_candidate_exhaustive_recommended": bool(crypto_tier2_risk_control_manifest.get("candidate_exhaustive_recommended", False)),
        "crypto_tier2_risk_control_batch1_candidate_exhaustive_run": bool(crypto_tier2_risk_control_manifest.get("candidate_exhaustive_run", False)),
        "crypto_tier2_risk_control_batch1_data_downloaded": bool(crypto_tier2_risk_control_manifest.get("data_downloaded", False)),
        "crypto_tier2_risk_control_batch1_paper_forward_active": bool(crypto_tier2_risk_control_manifest.get("paper_forward_active", False)),
        "crypto_tier2_risk_control_batch1_real_money_recommendation": bool(crypto_tier2_risk_control_manifest.get("real_money_recommendation", False)),
        "crypto_tier2_risk_control_batch1_uses_leverage": bool(crypto_tier2_risk_control_manifest.get("uses_leverage", False)),
        "crypto_tier2_risk_control_batch1_uses_margin": bool(crypto_tier2_risk_control_manifest.get("uses_margin", False)),
        "crypto_tier2_risk_control_batch1_uses_shorting": bool(crypto_tier2_risk_control_manifest.get("uses_shorting", False)),
        "crypto_tier2_risk_control_batch1_uses_futures_contracts": bool(crypto_tier2_risk_control_manifest.get("uses_futures_contracts", False)),
        "crypto_tier2_risk_control_batch1_uses_perpetuals": bool(crypto_tier2_risk_control_manifest.get("uses_perpetuals", False)),
        "crypto_tier2_risk_control_batch1_uses_options": bool(crypto_tier2_risk_control_manifest.get("uses_options", False)),
        "global_multi_asset_fast_acquisition_data_downloaded": bool(global_multi_asset_fast_acquisition_manifest.get("data_downloaded", False)),
        "global_multi_asset_fast_acquisition_provider_api_called": bool(global_multi_asset_fast_acquisition_manifest.get("provider_api_called", False)),
        "global_multi_asset_fast_acquisition_downloaded_symbols": global_multi_asset_fast_acquisition_manifest.get("downloaded_symbols", []),
        "global_multi_asset_fast_acquisition_cache_confirmed_symbols": global_multi_asset_fast_acquisition_manifest.get("cache_confirmed_symbols", []),
        "global_multi_asset_fast_acquisition_failed_symbols": global_multi_asset_fast_acquisition_manifest.get("failed_symbols", []),
        "global_multi_asset_fast_acquisition_raw_ohlcv_included": bool(global_multi_asset_fast_acquisition_manifest.get("raw_ohlcv_included", False)),
        "global_multi_asset_batch1_completed": bool(global_multi_asset_batch1_manifest.get("research_sample_run", False)),
        "global_multi_asset_batch1_best_candidate": global_multi_asset_batch1_manifest.get("best_multi_asset_candidate", "unavailable"),
        "global_multi_asset_batch1_best_candidate_registry_status": global_multi_asset_best_registry.get("status", "unavailable"),
        "global_multi_asset_batch1_candidate_exhaustive_recommended": bool(global_multi_asset_batch1_manifest.get("candidate_exhaustive_recommended", False)),
        "global_multi_asset_batch1_candidate_exhaustive_run": bool(global_multi_asset_batch1_manifest.get("candidate_exhaustive_run", False)),
        "global_multi_asset_batch1_data_downloaded_in_profit_exploration": bool(global_multi_asset_batch1_manifest.get("data_downloaded", False)),
        "global_multi_asset_batch1_paper_forward_active": bool(global_multi_asset_batch1_manifest.get("paper_forward_active", False)),
        "global_multi_asset_batch1_real_money_recommendation": bool(global_multi_asset_batch1_manifest.get("real_money_recommendation", False)),
        "global_multi_asset_batch1_uses_leverage": bool(global_multi_asset_batch1_manifest.get("uses_leverage", False)),
        "global_multi_asset_batch1_uses_margin": bool(global_multi_asset_batch1_manifest.get("uses_margin", False)),
        "global_multi_asset_batch1_uses_shorting": bool(global_multi_asset_batch1_manifest.get("uses_shorting", False)),
        "global_multi_asset_batch1_uses_futures_contracts": bool(global_multi_asset_batch1_manifest.get("uses_futures_contracts", False)),
        "global_multi_asset_batch1_uses_options": bool(global_multi_asset_batch1_manifest.get("uses_options", False)),
        "global_multi_asset_batch1_uses_forex": bool(global_multi_asset_batch1_manifest.get("uses_forex", False)),
        "global_multi_asset_batch1_uses_intraday": bool(global_multi_asset_batch1_manifest.get("uses_intraday", False)),
        "recovery_attribution_available": recovery_attribution_available,
        "run_id": run_id,
        "spy200d_replaced": False,
        "strategy_implemented": False,
        "target_window_attribution_available": target_window_attribution_available,
        "worst_n_drawdown_export_available": worst_n_drawdown_export_available,
    }

    outputs = {
        "README_FOR_ADVISOR.md": readme,
        "current_state_summary.md": summary,
        "warnings_and_limitations.md": warnings,
        "research_state_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    }
    for directory in [run_dir, LATEST_DIR]:
        for name, content in outputs.items():
            (directory / name).write_text(content, encoding="utf-8")
        write_csv(
            directory / "active_observations.csv",
            active_rows,
            ["strategy", "role", "status", "current_equity", "decision_status", "signal_state", "paper_forward_active", "notes"],
        )
        write_csv(directory / "historical_leaders.csv", historical_leaders, ["strategy", "status", "reason", "next_action"])
        write_csv(
            directory / "candidate_status_matrix.csv",
            candidate_rows,
            ["candidate_id", "latest_verdict", "deserves_candidate_exhaustive", "recommended_next_action", "risk_label", "duplicate_label", "paper_forward_active"],
        )
        write_csv(
            directory / "blocked_and_gated_items.csv",
            blocked_rows,
            ["item_id", "lane", "gate_status", "first_required_action", "implementation_allowed_now", "backtest_allowed_now", "notes"],
        )
        write_csv(directory / "next_allowed_actions.csv", next_actions, ["action", "allowed_now", "lane", "notes"])

    if LATEST_ZIP.exists():
        LATEST_ZIP.unlink()
    with zipfile.ZipFile(LATEST_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in REQUIRED_FILES:
            zf.write(LATEST_DIR / name, name)
    return LATEST_DIR


def main() -> int:
    latest = build_dashboard()
    print(f"research_state_latest_dir={latest}")
    print(f"research_state_file_count={len([p for p in latest.iterdir() if p.is_file()])}")
    print("backtest_run=false")
    print("profit_exploration_run=false")
    print("data_downloaded=false")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
