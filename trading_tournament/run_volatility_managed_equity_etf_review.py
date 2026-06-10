from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent
LANE_ID = "volatility_managed_equity_etf"
OUTPUT_ROOT = Path("evidence/lane_reviews") / LANE_ID
DECISION = "approve_future_research_sample_prompt"
NEXT_ACTION = "create_volatility_managed_equity_etf_research_sample_prompt"

CONTROL_FILES = [
    Path("strategy_lab/PROMOTION_POLICY.md"),
    Path("strategy_lab/policies/EVIDENCE_TIER_POLICY.md"),
    Path("strategy_lab/policies/EXPERIMENT_LANE_POLICY.md"),
    Path("strategy_lab/policies/PAPER_FORWARD_FREEZE_POLICY.md"),
    Path("strategy_lab/promotion_thresholds.yaml"),
    Path("strategy_lab/strategy_registry.yaml"),
]

EVIDENCE_FILES = [
    Path("evidence/promotion_gap/latest/promotion_gap_summary.md"),
    Path("evidence/promotion_gap/latest/next_research_lane_recommendation.md"),
    Path("evidence/promotion_gap/latest/next_allowed_action.md"),
    Path("evidence/promotion_gap/latest/failure_mode_summary.csv"),
    Path("evidence/promotion_gap/latest/closest_to_promotion.csv"),
    Path("evidence/promotion_gap/latest/research_lane_ranking.csv"),
    Path("evidence/promotion_review/latest/promotion_decisions.csv"),
    Path("evidence/strategy_lab/latest/current_state_summary.md"),
    Path("evidence/strategy_lab/latest/candidate_status_matrix.csv"),
    Path("evidence/strategy_lab/latest/historical_leaders.csv"),
    Path("evidence/strategy_lab/latest/active_observations.csv"),
    Path("evidence/strategy_lab/latest/warnings_and_limitations.md"),
]

REQUIRED_OUTPUTS = [
    "volatility_managed_equity_etf_review.md",
    "volatility_managed_equity_etf_fixed_rules.md",
    "volatility_managed_equity_etf_data_policy.md",
    "volatility_managed_equity_etf_risk_policy.md",
    "volatility_managed_equity_etf_rejection_criteria.md",
    "volatility_managed_equity_etf_next_action.md",
    "volatility_managed_equity_etf_review_manifest.json",
    "volatility_managed_equity_etf_consistency_check.json",
    "volatility_managed_equity_etf_review_packet.zip",
]

OPTIONAL_OUTPUTS = [
    "volatility_managed_equity_etf_candidate_variants.csv",
    "volatility_managed_equity_etf_expected_failure_modes.csv",
    "volatility_managed_equity_etf_benchmark_plan.csv",
]

VARIANTS = [
    {
        "strategy_id": "vm_spy_realized_vol_target_v1",
        "family": LANE_ID,
        "instrument_lane": "ETF_fund_wrapper",
        "evidence_tier": "tier1_or_tier2_exploratory_research_sample_only",
        "universe": "SPY,BIL",
        "rule_summary": "Monthly fixed-rule SPY/BIL allocation using 20-day or 60-day realized volatility regime; normal volatility holds 100% SPY, high volatility reduces to 50% SPY / 50% BIL, and below-SPY-200d condition uses BIL or existing trend-rule convention.",
        "expected_benefit": "Reduce drawdown-budget breaches while preserving more equity target potential than constant cash dilution.",
        "expected_failure_mode": "May react too late, duplicate SPY_200d behavior, or reduce target rates too much.",
        "benchmark_comparison": "SPY_200d_trend_model, SPY_buy_hold, BIL_cash_proxy, active combo historical row",
        "implementation_difficulty": "low",
        "allowed_next_action": "future_research_sample_prompt_only",
        "forbidden_next_actions": "candidate_exhaustive,paper_forward_activation,active_combo_mutation,SPY_200d_replacement,broker_integration,live_orders,real_money_recommendation,parameter_optimization",
    },
    {
        "strategy_id": "vm_spy_drawdown_vol_filter_v1",
        "family": LANE_ID,
        "instrument_lane": "ETF_fund_wrapper",
        "evidence_tier": "tier1_or_tier2_exploratory_research_sample_only",
        "universe": "SPY,BIL",
        "rule_summary": "Hold SPY only when SPY is above 200-day SMA and realized volatility is below a fixed threshold; otherwise hold BIL.",
        "expected_benefit": "Simple absolute-trend plus volatility gate may reduce stop and drawdown events.",
        "expected_failure_mode": "May become too slow or simply reproduce SPY_200d with extra lag.",
        "benchmark_comparison": "SPY_200d_trend_model, SPY_buy_hold, BIL_cash_proxy",
        "implementation_difficulty": "low",
        "allowed_next_action": "future_research_sample_prompt_only",
        "forbidden_next_actions": "candidate_exhaustive,paper_forward_activation,active_combo_mutation,SPY_200d_replacement,broker_integration,live_orders,real_money_recommendation,parameter_optimization",
    },
    {
        "strategy_id": "vm_quality_lowvol_proxy_v1",
        "family": LANE_ID,
        "instrument_lane": "ETF_fund_wrapper",
        "evidence_tier": "tier1_or_tier2_exploratory_research_sample_only",
        "universe": "SPLV,USMV,QUAL,SPY,BIL",
        "rule_summary": "Monthly comparison of low-volatility and quality ETF proxies versus SPY/BIL with a simple trend or volatility risk filter.",
        "expected_benefit": "May add non-duplicate defensive equity behavior while retaining some upside.",
        "expected_failure_mode": "Short proxy histories, product construction changes, and too-slow target behavior.",
        "benchmark_comparison": "SPY_200d_trend_model, active combo historical row, SPY_buy_hold, BIL_cash_proxy",
        "implementation_difficulty": "medium",
        "allowed_next_action": "future_research_sample_prompt_only_after_symbol_QA",
        "forbidden_next_actions": "candidate_exhaustive,paper_forward_activation,active_combo_mutation,SPY_200d_replacement,broker_integration,live_orders,real_money_recommendation,parameter_optimization",
    },
    {
        "strategy_id": "vm_sector_vol_scaled_top2_v1",
        "family": LANE_ID,
        "instrument_lane": "sector_ETF_fund_wrapper",
        "evidence_tier": "tier1_or_tier2_exploratory_research_sample_only",
        "universe": "sector_ETFs_already_supported_by_project,BIL",
        "rule_summary": "Choose top 2 existing sector ETFs by momentum, but reduce exposure in fixed high-volatility regimes; compare to current sector momentum behavior.",
        "expected_benefit": "May preserve sector dispersion target power while reducing high-volatility drawdowns.",
        "expected_failure_mode": "May duplicate existing sector rows or rely on incomplete sector-stream diagnostics.",
        "benchmark_comparison": "sector_top2_momentum_simple_v1, A_ETF_sector_momentum, SPY_200d_trend_model",
        "implementation_difficulty": "medium",
        "allowed_next_action": "future_research_sample_prompt_only_after_existing_sector_universe_review",
        "forbidden_next_actions": "candidate_exhaustive,paper_forward_activation,active_combo_mutation,SPY_200d_replacement,broker_integration,live_orders,real_money_recommendation,parameter_optimization,add_unreviewed_sector_symbols",
    },
    {
        "strategy_id": "vm_combo_overlay_v1",
        "family": LANE_ID,
        "instrument_lane": "ETF_fund_wrapper_combo_copy",
        "evidence_tier": "tier1_or_tier2_exploratory_research_sample_only",
        "universe": "current_active_combo_components_plus_BIL",
        "rule_summary": "Apply a fixed volatility exposure reducer to a copy of an existing combo using a new strategy id; must not mutate active combo observation.",
        "expected_benefit": "May directly test whether volatility control improves the existing leader without changing paper/demo rules.",
        "expected_failure_mode": "Likely duplicate or mostly combo behavior with target dilution.",
        "benchmark_comparison": "active combo historical row, SPY_200d_trend_model, asset_class_tsmom_top2_v1",
        "implementation_difficulty": "medium",
        "allowed_next_action": "future_research_sample_prompt_only_with_new_strategy_id",
        "forbidden_next_actions": "candidate_exhaustive,paper_forward_activation,active_combo_mutation,SPY_200d_replacement,broker_integration,live_orders,real_money_recommendation,parameter_optimization",
    },
]

BENCHMARKS = [
    {
        "benchmark_id": "SPY_200d_trend_model",
        "reason": "Frozen control and primary trend benchmark.",
        "comparison_metric": "target-before-stop, drawdown, stop-hit, overlap, score delta",
        "required": "true",
    },
    {
        "benchmark_id": "profit_combo_SPY200d_GLD_50_50_v1",
        "reason": "Current active combo historical row if available; must remain separate from active paper/demo observation.",
        "comparison_metric": "target-before-stop, drawdown, stop-hit, duplicate/overlap diagnostics",
        "required": "true",
    },
    {
        "benchmark_id": "SPY_buy_hold",
        "reason": "Equity beta baseline.",
        "comparison_metric": "return target rates and drawdown budget behavior",
        "required": "true",
    },
    {
        "benchmark_id": "BIL_cash_proxy",
        "reason": "Fallback and cash-dilution baseline.",
        "comparison_metric": "target dilution and drawdown floor",
        "required": "true",
    },
    {
        "benchmark_id": "GLD_buy_hold",
        "reason": "Relevant for combo comparisons and non-equity diversification checks.",
        "comparison_metric": "target-window overlap and drawdown coincidence",
        "required": "false",
    },
    {
        "benchmark_id": "asset_class_tsmom_top2_v1",
        "reason": "Historical leader and multi-asset comparison row.",
        "comparison_metric": "stop-aware score and target-window independence",
        "required": "false",
    },
    {
        "benchmark_id": "sector_top2_momentum_simple_v1",
        "reason": "Required only if sector volatility-scaled variant is used.",
        "comparison_metric": "sector target rate, drawdown, and duplicate behavior",
        "required": "false",
    },
]

FAILURE_MODES = [
    {
        "failure_mode": "too_slow_target_dilution",
        "where_expected": "All variants, especially defensive filters and combo overlay",
        "required_response": "Mark too_slow if +300/+400 rates are diluted below useful thresholds.",
    },
    {
        "failure_mode": "duplicate_existing_leader",
        "where_expected": "SPY trend filter and combo overlay variants",
        "required_response": "Mark duplicate_or_near_duplicate unless target-window independence is demonstrated.",
    },
    {
        "failure_mode": "too_risky_drawdown_budget",
        "where_expected": "Vol-scaled sector or equity variants if exposure reducer fails",
        "required_response": "Mark too_risky if -$600 budget is breached or stop behavior is unacceptable.",
    },
    {
        "failure_mode": "evidence_missing",
        "where_expected": "Low-vol/quality proxies if symbols or history are missing",
        "required_response": "Keep as review-only until symbol QA and history checks pass.",
    },
]


def run_id_now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve(path: Path, project_root: Path = PROJECT_ROOT) -> Path:
    return path if path.is_absolute() else project_root / path


def existing_and_missing(paths: Iterable[Path]) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing: list[str] = []
    for path in paths:
        if resolve(path).exists():
            existing.append(str(path))
        else:
            missing.append(str(path))
    return existing, missing


def read_text_if_exists(path: Path) -> str:
    resolved = resolve(path)
    if not resolved.exists():
        return ""
    return resolved.read_text(encoding="utf-8", errors="ignore")


def read_failure_summary() -> list[dict[str, str]]:
    path = resolve(Path("evidence/promotion_gap/latest/failure_mode_summary.csv"))
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def write_review_files(run_dir: Path, run_id: str, existing_inputs: list[str], missing_inputs: list[str]) -> None:
    failure_summary = read_failure_summary()
    failure_lines = [
        f"- {row.get('failure_mode')}: {row.get('row_count')} rows"
        for row in failure_summary
    ]
    if not failure_lines:
        failure_lines = ["- Missing failure-mode summary; review records this as input gap."]

    review_md = f"""# Volatility-Managed Equity ETF Lane Review

Decision context: the latest promotion gap review recommended `volatility_managed_equity_etf` because current research rows are dominated by missing diagnostics, drawdown-budget failures, duplicate blends, and blocked provider/instrument lanes.

This is a review/design gate only. It does not implement a strategy, run a backtest, run Profit Exploration, download data, call provider APIs, run candidate_exhaustive, activate paper-forward, mutate active observations, replace frozen controls, add broker integration, place orders, or make a real-money recommendation.

## Strategy Idea

Use ETF/fund wrappers to test whether volatility-managed equity exposure can improve the current project gap: high-upside rows often breach the -$600 drawdown budget, while defensive rows become too slow or duplicate existing leaders.

The lane remains:

- ETF/fund wrapper only
- daily adjusted data only
- research_sample only
- exploratory and non-final
- no leverage
- no margin
- no shorting
- no options
- no futures
- no forex
- no intraday
- no broker integration
- no paper-forward activation

## Why This Lane May Help

- It directly targets drawdown-budget failures.
- It may preserve equity target potential better than pure cash dilution.
- It may produce a non-duplicate challenger if exposure changes are driven by volatility regimes rather than simply adding GLD or BIL.
- It stays compatible with fast ETF/fund exploratory data policy.

## Why This Lane May Fail

- It may reduce exposure too much and become too slow.
- It may duplicate `SPY_200d_trend_model`.
- It may reduce drawdown but also reduce +$300/+400 target probability.
- It may overfit volatility thresholds if future implementation tunes parameters.
- It may react after drawdowns instead of before them.
- It may look useful only because of a specific historical regime.

## Current Promotion Gap Inputs

{chr(10).join(failure_lines)}

## Input Files Read

{markdown_list(existing_inputs)}

## Missing Input Files

{markdown_list(missing_inputs)}
"""
    (run_dir / "volatility_managed_equity_etf_review.md").write_text(review_md, encoding="utf-8")

    fixed_rules = """# Fixed Rules And Future Variants

Future variants must be fixed before testing. Do not optimize thresholds, lookbacks, weights, or symbol lists during implementation.

Approved future research_sample variants:

1. `vm_spy_realized_vol_target_v1`
   - Universe: SPY, BIL.
   - Use 20-day or 60-day realized volatility.
   - Normal volatility: 100% SPY.
   - High volatility: 50% SPY / 50% BIL.
   - If SPY is below 200-day SMA: use BIL or the existing trend-rule convention.
   - No leverage.

2. `vm_spy_drawdown_vol_filter_v1`
   - Universe: SPY, BIL.
   - Hold SPY only when SPY is above 200-day SMA and volatility is below a fixed threshold.
   - Otherwise hold BIL.
   - No leverage.

3. `vm_quality_lowvol_proxy_v1`
   - Universe: SPLV, USMV, QUAL, SPY, BIL if available and QA passes.
   - Monthly rebalance.
   - Simple trend or volatility filter.
   - No leverage.

4. `vm_sector_vol_scaled_top2_v1`
   - Universe: sector ETFs already supported by the project plus BIL.
   - Choose top 2 sectors by momentum and reduce exposure in fixed high-volatility regimes.
   - Compare against existing sector momentum behavior.
   - No leverage.

5. `vm_combo_overlay_v1`
   - Universe: current active combo components plus BIL.
   - Apply volatility exposure reducer to a copy of an existing combo with a new strategy id.
   - Must not mutate active combo observation.
   - Research_sample only.

All five variants are approved only for a future implementation prompt. This review does not implement them.
"""
    (run_dir / "volatility_managed_equity_etf_fixed_rules.md").write_text(fixed_rules, encoding="utf-8")

    data_policy = """# Data Policy

Allowed data for future research_sample:

- ETF/fund wrapper adjusted daily data.
- Existing cache preferred.
- yfinance-compatible data is acceptable for fast exploratory screening if basic QA passes.
- Raw OHLCV must stay out of compact advisor packets.
- Fast exploratory data alone cannot approve candidate_exhaustive.
- Fast exploratory data cannot activate paper-forward.

Future allowed symbols, only if data is available and QA passes:

- SPY
- QQQ
- IWM
- sector ETFs already used in the project
- BIL
- SHY
- IEF
- TLT
- GLD
- SPLV
- USMV
- QUAL

This review does not download data.

Basic QA requirements:

- sufficient history
- no missing adjusted close for the required period
- no impossible OHLC values
- no duplicate dates
- enough warmup data for indicators
- no raw vendor data in compact evidence
- symbol availability documented
"""
    (run_dir / "volatility_managed_equity_etf_data_policy.md").write_text(data_policy, encoding="utf-8")

    risk_policy = """# Risk Policy

Future research_sample must evaluate:

- +$300 target-before-stop
- +$400 target-before-stop
- absolute -$600 budget
- trailing drawdown behavior
- max drawdown
- target dilution
- stress/slippage if applicable
- benchmark-relative drawdown
- correlation/overlap with existing leaders
- whether volatility management adds value or simply duplicates `SPY_200d_trend_model`

Risk rules:

- No leverage
- No margin
- No shorting
- No options
- No futures
- No forex
- No intraday
- No broker integration
- No live orders
- No real-money recommendation
- No active observation mutation

If a variant reduces drawdown but destroys target probability, mark `too_slow`.

If a variant keeps target probability but breaches the drawdown budget, mark `too_risky`.

If a variant mostly reproduces `SPY_200d_trend_model` or the active combo historical row, mark `duplicate_or_near_duplicate`.
"""
    (run_dir / "volatility_managed_equity_etf_risk_policy.md").write_text(risk_policy, encoding="utf-8")

    rejection = """# Rejection And Promotion Criteria

Reject or watchlist a future research_sample row if:

- +$300 target-before-stop rate is not meaningfully competitive.
- +$400 target-before-stop rate is negligible.
- Drawdown budget still breaches.
- Target potential is too diluted.
- It duplicates `SPY_200d_trend_model` or active combo behavior.
- It depends on tuned volatility thresholds.
- It needs leverage or shorting.
- Evidence is too short.
- Stress assumptions break the row.
- It is worse than `SPY_200d_trend_model`, active combo, SPY buy-hold, or BIL on relevant metrics.

A future row may request promotion_review only if:

- it improves drawdown without destroying target probability, or
- it improves +$300 target-before-stop versus current leaders without breaching risk budget, or
- it shows materially different target windows from existing leaders, and
- it has basic QA, target, drawdown, stop, benchmark, and duplication evidence.

A future row may request candidate_exhaustive queue only after promotion review confirms:

- meaningful target evidence
- acceptable drawdown evidence
- no obvious stress fragility
- no near-duplicate behavior
- no data or instrument blocker
- no mutation of active paper/demo rows
"""
    (run_dir / "volatility_managed_equity_etf_rejection_criteria.md").write_text(rejection, encoding="utf-8")

    next_action = f"""# Next Action Decision

Decision: `{DECISION}`

Exact next allowed action:

`{NEXT_ACTION}`

Reason: this lane is ETF/fund-wrapper compatible, requires no leverage/margin/shorting/options/futures/forex/intraday mechanics, uses fixed variants, keeps active observations untouched, and remains exploratory/non-final until later gates.

Forbidden next actions:

- candidate_exhaustive
- paper_forward_activation
- active combo mutation
- SPY_200d replacement
- live trading
- broker integration
- data download without explicit prompt
- provider API call without explicit prompt
- parameter optimization

This review approves only a future research_sample implementation prompt. It does not implement or run the strategy.
"""
    (run_dir / "volatility_managed_equity_etf_next_action.md").write_text(next_action, encoding="utf-8")

    write_csv(
        run_dir / "volatility_managed_equity_etf_candidate_variants.csv",
        VARIANTS,
        [
            "strategy_id",
            "family",
            "instrument_lane",
            "evidence_tier",
            "universe",
            "rule_summary",
            "expected_benefit",
            "expected_failure_mode",
            "benchmark_comparison",
            "implementation_difficulty",
            "allowed_next_action",
            "forbidden_next_actions",
        ],
    )
    write_csv(
        run_dir / "volatility_managed_equity_etf_benchmark_plan.csv",
        BENCHMARKS,
        ["benchmark_id", "reason", "comparison_metric", "required"],
    )
    write_csv(
        run_dir / "volatility_managed_equity_etf_expected_failure_modes.csv",
        FAILURE_MODES,
        ["failure_mode", "where_expected", "required_response"],
    )


def create_packet(run_dir: Path) -> None:
    zip_path = run_dir / "volatility_managed_equity_etf_review_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.iterdir()):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.name)


def consistency(run_dir: Path) -> dict[str, object]:
    missing = [name for name in REQUIRED_OUTPUTS if not (run_dir / name).exists()]
    variant_rows = []
    variants_path = run_dir / "volatility_managed_equity_etf_candidate_variants.csv"
    if variants_path.exists():
        with variants_path.open(newline="", encoding="utf-8") as handle:
            variant_rows = list(csv.DictReader(handle))
    forbidden_text = " ".join(row.get("forbidden_next_actions", "") for row in variant_rows).lower()
    all_fixed = len(variant_rows) == 5 and all("parameter_optimization" in row.get("forbidden_next_actions", "") for row in variant_rows)
    checks = {
        "no_backtest_run": True,
        "no_data_download": True,
        "no_provider_api_call": True,
        "no_profit_exploration_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_active_observation_mutation": True,
        "no_frozen_control_mutation": True,
        "no_broker_integration": True,
        "no_live_orders": True,
        "no_real_money_recommendation": True,
        "required_review_files_exist": not missing,
        "next_action_is_explicit": NEXT_ACTION in (run_dir / "volatility_managed_equity_etf_next_action.md").read_text(encoding="utf-8"),
        "lane_status": "research_review_only",
        "all_future_variants_fixed_rule_and_non_final": all_fixed and "paper_forward_activation" in forbidden_text,
    }
    errors = [key for key, value in checks.items() if value is not True and key != "lane_status"]
    if checks["lane_status"] != "research_review_only":
        errors.append("lane_status")
    return {
        "consistency_passed": not errors,
        "errors": errors,
        "missing_required_outputs": missing,
        **checks,
        "decision": DECISION,
        "exact_next_allowed_action": NEXT_ACTION,
    }


def run_review(run_id: str | None = None) -> dict[str, object]:
    run_id = run_id or run_id_now()
    output_root = resolve(OUTPUT_ROOT)
    run_dir = output_root / "runs" / run_id
    latest_dir = output_root / "latest"
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    existing_controls, missing_controls = existing_and_missing(CONTROL_FILES)
    existing_evidence, missing_evidence = existing_and_missing(EVIDENCE_FILES)
    existing_inputs = existing_controls + existing_evidence
    missing_inputs = missing_controls + missing_evidence

    write_review_files(run_dir, run_id, existing_inputs, missing_inputs)

    manifest = {
        "run_id": run_id,
        "lane_id": LANE_ID,
        "lane_status": "research_review_only",
        "decision": DECISION,
        "exact_next_allowed_action": NEXT_ACTION,
        "existing_input_files": existing_inputs,
        "missing_input_files": missing_inputs,
        "candidate_variant_count": len(VARIANTS),
        "backtest_run": False,
        "profit_exploration_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activated": False,
        "active_observation_mutated": False,
        "frozen_control_changed": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    (run_dir / "volatility_managed_equity_etf_review_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    preliminary = consistency(run_dir)
    (run_dir / "volatility_managed_equity_etf_consistency_check.json").write_text(
        json.dumps(preliminary, indent=2) + "\n",
        encoding="utf-8",
    )
    create_packet(run_dir)
    final_consistency = consistency(run_dir)
    (run_dir / "volatility_managed_equity_etf_consistency_check.json").write_text(
        json.dumps(final_consistency, indent=2) + "\n",
        encoding="utf-8",
    )
    create_packet(run_dir)
    if not final_consistency["consistency_passed"]:
        raise RuntimeError(f"Consistency check failed: {final_consistency}")

    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_dir": str(latest_dir),
        "packet_path": str(latest_dir / "volatility_managed_equity_etf_review_packet.zip"),
        "decision": DECISION,
        "exact_next_allowed_action": NEXT_ACTION,
        "consistency_passed": True,
        "backtest_run": False,
        "profit_exploration_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activated": False,
    }


def main() -> None:
    result = run_review()
    print(f"volatility_review_run_dir={result['run_dir']}")
    print(f"volatility_review_latest_dir={result['latest_dir']}")
    print(f"volatility_review_packet={result['packet_path']}")
    print(f"decision={result['decision']}")
    print(f"exact_next_allowed_action={result['exact_next_allowed_action']}")
    print(f"consistency_passed={str(result['consistency_passed']).lower()}")
    print("backtest_run=false")
    print("profit_exploration_run=false")
    print("data_downloaded=false")
    print("provider_api_called=false")
    print("candidate_exhaustive_run=false")
    print("paper_forward_activated=false")


if __name__ == "__main__":
    main()
