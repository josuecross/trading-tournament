from __future__ import annotations

import csv
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
LANE_ID = "managed_futures_etf_wrapper"
OUTPUT_DIR = Path("evidence") / "lane_reviews" / LANE_ID / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_NEXT_ACTION = "create_managed_futures_etf_wrapper_fast_exploration_review_prompt"
LANE_VERDICT = "approve_future_research_sample_prompt"
NEXT_ACTION = "create_managed_futures_etf_wrapper_research_sample_prompt"

PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}

FORBIDDEN_NEXT_ACTIONS = [
    "direct_futures_trading",
    "futures_contracts",
    "options",
    "forex",
    "crypto",
    "intraday_logic",
    "leverage_created_by_system",
    "margin",
    "shorting",
    "individual_stock_strategy_logic",
    "broker_integration",
    "live_orders",
    "order_placement",
    "real_money_recommendation",
    "paper_forward_activation",
    "paper_forward_checkpoint",
    "candidate_exhaustive",
    "research_sample_without_future_prompt",
    "backtest_execution",
    "profit_exploration",
    "data_download_without_future_prompt",
    "provider_api_call_without_future_prompt",
    "parameter_optimization",
    "grid_search",
]

WRAPPER_SYMBOLS = ["DBMF", "KMLM", "CTA", "FMF", "WTMF"]
BASELINE_SYMBOLS = ["SPY", "QQQ", "BIL", "GLD", "IEF"]
CONDITIONAL_BENCHMARKS = ["TLT", "AGG"]

VARIANTS = [
    {
        "strategy_id": "mf_wrapper_top1_trend_v1",
        "family": LANE_ID,
        "universe": "DBMF;KMLM;CTA;FMF;WTMF;BIL",
        "rule_summary": "Monthly rebalance; wrappers eligible if close > 200-day SMA; rank eligible wrappers by 126-day return; hold top 1; otherwise 100% BIL.",
        "expected_profit_driver": "Pure managed-futures wrapper trend/momentum selection.",
        "expected_failure_mode": "Short wrapper histories, fee drag, one-regime dependence, or too few eligible wrappers.",
        "likely_duplicate_risk": "May duplicate bonds, GLD, BIL, or generic crisis-defense behavior.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "SPY_200d;SPY_buy_hold;QQQ_buy_hold;GLD_buy_hold;BIL_cash_proxy;IEF_buy_hold;wrapper_buy_holds",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "mf_wrapper_top2_risk_adjusted_v1",
        "family": LANE_ID,
        "universe": "DBMF;KMLM;CTA;FMF;WTMF;BIL",
        "rule_summary": "Monthly rebalance; eligible wrappers must be above 200-day SMA; rank by 126-day return / 60-day realized volatility; hold top 2 equally; unused allocation to BIL.",
        "expected_profit_driver": "Diversified managed-futures wrapper selection with a fixed risk-adjusted ranking.",
        "expected_failure_mode": "Volatility ranking may favor stale low-return wrappers or fail in short histories.",
        "likely_duplicate_risk": "May behave like a defensive bond/cash sleeve if wrapper trends are weak.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;BIL_cash_proxy;wrapper_buy_holds",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "mf_wrapper_plus_spy_70_30_v1",
        "family": LANE_ID,
        "universe": "SPY;DBMF;KMLM;CTA;FMF;WTMF;BIL",
        "rule_summary": "Monthly rebalance; 70% SPY if SPY > 200-day SMA else BIL; 30% best eligible wrapper by 126-day return else BIL.",
        "expected_profit_driver": "Managed-futures wrapper sleeve may improve an equity trend sleeve's drawdown/profit frontier.",
        "expected_failure_mode": "Wrapper sleeve may be too small, too slow, or add no benefit versus SPY_200d plus BIL.",
        "likely_duplicate_risk": "Could duplicate GROR or SPY_200d if wrapper allocation rarely contributes.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "SPY_200d;active_combo;SPY_buy_hold;BIL_cash_proxy;wrapper_buy_holds",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "mf_wrapper_plus_dsr_vm_combo_proxy_v1",
        "family": LANE_ID,
        "universe": "protected_reference_proxy;DBMF;KMLM;CTA;FMF;WTMF;BIL",
        "rule_summary": "Conditional only; separate research row; 70% existing protected reference proxy and 30% best eligible wrapper if safely inferable, otherwise evidence_missing.",
        "expected_profit_driver": "Tests additive sleeve value without mutating active VM, DSR, or combo observations.",
        "expected_failure_mode": "Protected reference series may not be safely inferable; additive benefit may simply duplicate active combo.",
        "likely_duplicate_risk": "High unless it proves lower correlation and different target/drawdown windows.",
        "implementation_difficulty": "high",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;wrapper_buy_holds",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "mf_wrapper_defensive_cash_switch_v1",
        "family": LANE_ID,
        "universe": "DBMF;KMLM;CTA;FMF;WTMF;BIL",
        "rule_summary": "Monthly rebalance; equal weight wrappers above 200-day SMA; if fewer than 2 qualify, 50% best wrapper and 50% BIL; if none, 100% BIL.",
        "expected_profit_driver": "Lower-risk wrapper basket with cash fallback.",
        "expected_failure_mode": "May be too defensive or too slow for project profit goals.",
        "likely_duplicate_risk": "May duplicate BIL, bonds, or a low-volatility defensive sleeve.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "BIL_cash_proxy;IEF_buy_hold;GLD_buy_hold;wrapper_buy_holds;active_combo",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def protected_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {
        row_id: deepcopy(row)
        for row_id, row in rows.items()
        if row_id in PROTECTED_IDS or row.get("paper_forward_active") is True
    }


def state_checks(registry: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    rows = rows_by_id(registry)
    checks = {
        "roadmap_next_action_is_managed_futures_review": False,
        "managed_futures_priority_1": False,
        "gror_watchlist_not_paper_forward": False,
        "quality_momentum_watchlist_not_next": False,
        "vm_quality_active_frozen": False,
        "dsr_equal_weight_active_frozen": False,
        "spy_200d_frozen_control": False,
    }
    roadmap = Path("strategy_lab/RESEARCH_ROADMAP.md")
    if roadmap.exists():
        text = roadmap.read_text(encoding="utf-8")
        checks["roadmap_next_action_is_managed_futures_review"] = ROADMAP_NEXT_ACTION in text
        checks["managed_futures_priority_1"] = "1. `managed_futures_etf_wrapper`" in text
    managed = rows.get(LANE_ID, {})
    checks["managed_futures_priority_1"] = checks["managed_futures_priority_1"] and managed.get("priority_rank") == 1
    gror = rows.get("gror_balanced_momentum_60_40_v1", {})
    checks["gror_watchlist_not_paper_forward"] = (
        gror.get("paper_forward_active") is False and "watchlist" in str(gror.get("current_status") or gror.get("status"))
    )
    quality = rows.get("quality_momentum_etf_proxy", {})
    checks["quality_momentum_watchlist_not_next"] = (
        quality.get("paper_forward_active") is False
        and quality.get("allowed_next_action") == "keep_quality_momentum_on_watchlist"
    )
    vm = rows.get("paper_forward_vm_quality_lowvol_proxy_v1", {})
    checks["vm_quality_active_frozen"] = vm.get("paper_forward_active") is True and vm.get("rules_frozen") is True
    dsr = rows.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", {})
    checks["dsr_equal_weight_active_frozen"] = dsr.get("paper_forward_active") is True and dsr.get("rules_frozen") is True
    spy = rows.get("SPY_200d_trend_model", {})
    checks["spy_200d_frozen_control"] = spy.get("paper_forward_active") is True and spy.get("rules_frozen") is True
    mismatches = [key for key, passed in checks.items() if not passed]
    return checks, mismatches


def update_registry(registry: dict[str, Any], output_path: str) -> dict[str, Any]:
    updated = deepcopy(registry)
    updated.setdefault("strategies", [])
    rows = rows_by_id(updated)
    row = rows.get(LANE_ID)
    if row is None:
        row = {
            "id": LANE_ID,
            "display_name": "Managed Futures ETF Wrapper",
            "lane": "profit_exploration",
            "instrument_family": "ETF",
            "strategy_family": LANE_ID,
            "version": "v1",
            "parent_id": "",
            "credibility_tier": "tier1_research_queue",
            "role": "research_lane_review",
            "rules_frozen": True,
            "implementation_status": "not_implemented",
            "data_source": "not_applicable_review_only",
            "evidence_source": "managed_futures_etf_wrapper_review",
            "promotion_requirements": "Future research_sample prompt required before any implementation.",
            "demotion_or_kill_criteria": "Reject if direct futures, insufficient wrapper history, duplicate behavior, or risk budget failure.",
            "notes": "ETF/fund-wrapper review row only.",
            "strategy_id": LANE_ID,
            "family": LANE_ID,
            "instrument_lane": "ETF",
            "evidence_tier": "tier1_research_queue",
            "candidate_exhaustive_recommended": False,
            "promotion_review_required": False,
            "promotion_decision": "not_reviewed",
            "promotion_reason": "Design gate only.",
            "primary_failure_mode": "not_tested",
            "duplication_risk": "requires_future_review",
            "risk_budget_status": "not_tested",
            "evidence_needed": "future research_sample evidence",
            "duplicate_of": "",
            "blocked_reason": "",
            "risk_framework_status": "research_only_review_gate",
            "promotion_blockers": "planning_only;not_tested;no_real_money_path",
        }
        updated["strategies"].append(row)

    if row.get("paper_forward_active") is True:
        return updated
    row["status"] = "research_sample_candidate"
    row["current_status"] = "research_sample_candidate"
    row["lane_review_verdict"] = LANE_VERDICT
    row["allowed_next_action"] = NEXT_ACTION
    row["next_allowed_action"] = NEXT_ACTION
    row["allowed_next_actions"] = [NEXT_ACTION]
    row["paper_forward_active"] = False
    row["paper_forward_allowed_by_risk_framework"] = False
    row["real_money_recommendation"] = False
    row["candidate_exhaustive_run"] = False
    row["candidate_exhaustive_recommended"] = False
    row["latest_evidence_path"] = output_path
    row["latest_known_result_summary"] = "Managed-futures ETF/fund-wrapper design gate approved fixed variants for a future explicitly prompted research_sample. No strategy/backtest/data download was run."
    row["evidence_source"] = "managed_futures_etf_wrapper_review"
    row["forbidden_next_actions"] = sorted(set(row.get("forbidden_next_actions") or []) | set(FORBIDDEN_NEXT_ACTIONS))
    row["notes"] = "ETF/fund-wrapper only. No direct futures trading, broker path, or real-money recommendation."
    updated.setdefault("registry", {})["last_updated_utc"] = now_utc()
    return updated


def render_review(state_mismatches: list[str]) -> str:
    mismatch_lines = ["- None."] if not state_mismatches else [f"- {item}" for item in state_mismatches]
    return "\n".join(
        [
            "# Managed Futures ETF Wrapper Review",
            "",
            f"Family id: `{LANE_ID}`",
            f"Lane verdict: `{LANE_VERDICT}`",
            f"Exact next action: `{NEXT_ACTION}`",
            "",
            "This is a review/design gate only. It does not implement a strategy, run a backtest, run research_sample, run candidate_exhaustive, download data, call provider APIs, activate paper-forward, or add broker/live-order/real-money paths.",
            "",
            "The lane is allowed only as publicly traded ETF/fund-wrapper exposure. The project does not directly trade futures contracts.",
            "",
            "## State Mismatches",
            "",
            *mismatch_lines,
            "",
        ]
    )


def render_family_thesis() -> str:
    return """# Managed Futures ETF Wrapper Family Thesis

Family id: `managed_futures_etf_wrapper`

Thesis: use ETF/fund wrappers that provide managed-futures-style or broad trend-following exposure to test whether the project can find a more additive return stream than equity/growth/sector-heavy families.

Why this family may help:

- It may be less correlated with SPY/QQQ/sector behavior.
- It may help during equity drawdowns.
- It may add crisis-alpha-like behavior through ETF wrappers.
- It may complement VM quality and DSR equal-weight without modifying them.
- It may improve the portfolio-level profit/risk frontier.

Why this family may fail:

- ETF wrapper histories may be short.
- Managed-futures ETFs can have high fees and tracking differences.
- Some wrappers may be too slow or low-return.
- Some wrappers may underperform in equity bull markets.
- Some wrappers may be internally futures-based, but the project only trades ETF shares.
- Performance may depend heavily on start date.
- A wrapper may look good only because of one recent regime.

This lane must not directly trade futures contracts. It must only use ETF/fund wrappers.
"""


def render_data_policy() -> str:
    return """# Managed Futures ETF Wrapper Data Policy

Allowed default wrapper symbols, only if cache/data is available or later explicitly bootstrapped:

- `DBMF`
- `KMLM`
- `CTA`
- `FMF`
- `WTMF`

Baseline/control symbols:

- `SPY`
- `QQQ`
- `BIL`
- `GLD`
- `IEF`

Conditional benchmark-only:

- `TLT`
- `AGG`

Do not use direct futures contracts, commodity futures contracts, forex contracts, crypto, options, leveraged ETFs, inverse ETFs, individual stocks, or intraday data.

This review does not download data. A future research_sample may use yfinance-compatible adjusted daily ETF/fund-wrapper data only if explicitly prompted and clearly labeled as exploratory/non-institutional. If wrapper histories are short, the future research_sample must label history limitations clearly.
"""


def render_fixed_rules() -> str:
    lines = ["# Managed Futures ETF Wrapper Fixed Rules", ""]
    for variant in VARIANTS:
        lines.extend(
            [
                f"## `{variant['strategy_id']}`",
                "",
                f"Universe: `{variant['universe']}`",
                "",
                variant["rule_summary"],
                "",
                f"Purpose/profit driver: {variant['expected_profit_driver']}",
                "",
                "No leverage by our system. No direct futures contracts. No parameter optimization or grid search.",
                "",
            ]
        )
    return "\n".join(lines)


def render_risk_policy() -> str:
    return """# Managed Futures ETF Wrapper Risk Policy

Future research_sample must evaluate profit metrics: median final equity, mean final equity, upper-percentile final equity, best-window final equity, and +300/+400 target-before-stop rates.

Future research_sample must evaluate risk metrics: worst drawdown, median drawdown, -$600 stop-hit rate, worst loss window, loss-window rate, profit-to-drawdown ratio, and whether short history makes the result unreliable.

Practical risk review must include fund inception date, history length, missing data, high fee / wrapper behavior warning, and possible regime dependency.

Decision rules:

- If row is additive but too slow, watchlist.
- If row improves drawdown but kills target power, too_slow.
- If row breaches drawdown budget, too_risky.
- If row only duplicates bonds/GLD/BIL, duplicate_or_near_duplicate.
- If row has promising target/risk and additive behavior, promotion_review_candidate.
"""


def render_duplicate_plan() -> str:
    return """# Managed Futures ETF Wrapper Duplicate Risk Plan

Future research_sample must compare against active combo, `paper_forward_vm_quality_lowvol_proxy_v1`, `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`, `SPY_200d`, SPY buy-hold, QQQ buy-hold, GLD buy-hold, BIL, IEF/TLT/AGG if available, and each wrapper buy-hold.

Duplicate risks:

- Wrapper behaves like bonds/GLD only.
- Wrapper behaves like equity beta.
- Wrapper adds too little profit to matter.
- Wrapper history is too short.
- Wrapper is only good in one regime.
- Sleeve variants simply duplicate active combo without improving drawdown/profit.

Additive proof should include lower correlation to SPY/QQQ/DSR/VM, different target windows, different drawdown behavior, useful +300/+400 target contribution, and drawdown improvement without becoming too slow.
"""


def render_rejection_criteria() -> str:
    return """# Managed Futures ETF Wrapper Rejection Criteria

Reject or watchlist if wrapper history is too short for useful screening, the row fails to improve profit opportunity, target rates are weak, the row is too defensive/slow, behavior duplicates GLD/bonds/BIL/equity beta, the row breaches drawdown budget, forbidden mechanics are required, tuned thresholds are required, or the row cannot be tested with ETF/fund-wrapper adjusted daily data.

Promotion review is allowed only if the rule is fixed, ETF/fund-wrapper only, has enough history for exploratory screening, has useful profit/target metrics, acceptable drawdown, likely additive behavior, and no forbidden mechanics.
"""


def render_next_action() -> str:
    return f"""# Managed Futures ETF Wrapper Next Action

Decision: `{LANE_VERDICT}`

Exact next action: `{NEXT_ACTION}`

Reason: enough candidate ETF/fund-wrapper symbols are known for a future explicitly prompted exploratory research_sample, fixed variants are defined, no forbidden mechanics are needed, and future data can remain yfinance-compatible adjusted daily ETF/fund-wrapper data labeled exploratory/non-final.

Do not implement the lane, download data, run research_sample, run candidate_exhaustive, or activate paper-forward from this review.
"""


def render_decision_tree() -> str:
    return """# Managed Futures ETF Wrapper Decision Tree

1. If wrapper symbols/history are unavailable, use symbol discovery or defer.
2. If ETF/fund-wrapper adjusted daily data is available, run only a future explicitly prompted research_sample.
3. If variants are too slow, watchlist or reject.
4. If variants breach risk budget, mark too_risky.
5. If variants duplicate GLD/bonds/BIL/equity beta, mark duplicate_or_near_duplicate.
6. If a fixed row is profitable, risk-acceptable, and additive, allow promotion_review_candidate.
"""


def benchmark_rows() -> list[dict[str, Any]]:
    rows = [
        ("active_combo", True, "portfolio-level active reference", "delta equity; correlation; target/drawdown window overlap", "required; if unavailable mark evidence_missing"),
        ("paper_forward_vm_quality_lowvol_proxy_v1", True, "active/frozen VM reference", "correlation; drawdown behavior; target windows", "required; do not mutate"),
        ("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", True, "active/frozen DSR reference", "correlation; drawdown behavior; target windows", "required; do not mutate"),
        ("SPY_200d", True, "frozen control", "delta equity; stop-hit rate; drawdown", "required"),
        ("SPY_buy_hold", True, "equity beta benchmark", "delta equity; drawdown; target rates", "required"),
        ("QQQ_buy_hold", True, "growth benchmark", "delta equity; drawdown; target rates", "required"),
        ("GLD_buy_hold", True, "gold/alternative benchmark", "correlation; drawdown; delta equity", "required"),
        ("BIL_cash_proxy", True, "cash proxy", "cash fallback opportunity cost", "required"),
        ("IEF_buy_hold", True, "bond benchmark", "correlation; defensive overlap", "if available"),
        ("TLT_buy_hold", False, "duration benchmark", "correlation; defensive overlap", "conditional benchmark-only if available"),
        ("AGG_buy_hold", False, "aggregate bond benchmark", "correlation; defensive overlap", "conditional benchmark-only if available"),
    ]
    rows.extend(
        (f"{symbol}_buy_hold", True, f"{symbol} wrapper buy-hold", "wrapper selection alpha vs buy-hold", "if wrapper data available")
        for symbol in WRAPPER_SYMBOLS
    )
    return [
        {
            "benchmark_id": benchmark_id,
            "required": required,
            "reason": reason,
            "comparison_metric": metric,
            "missing_handling": missing,
        }
        for benchmark_id, required, reason, metric, missing in rows
    ]


def symbol_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "symbol": symbol,
            "role": "managed_futures_or_trend_following_wrapper",
            "allowed_for_future_review": True,
            "data_checked_now": False,
            "provider_api_called": False,
            "notes": "Allowed only if cache/data is already available or later explicitly bootstrapped.",
        }
        for symbol in WRAPPER_SYMBOLS
    ] + [
        {
            "symbol": symbol,
            "role": "baseline_or_control",
            "allowed_for_future_review": True,
            "data_checked_now": False,
            "provider_api_called": False,
            "notes": "Baseline/control only.",
        }
        for symbol in BASELINE_SYMBOLS + CONDITIONAL_BENCHMARKS
    ]


def failure_mode_rows() -> list[dict[str, Any]]:
    modes = [
        "short_history",
        "high_fee_or_tracking_difference",
        "too_slow_or_low_return",
        "equity_bull_market_underperformance",
        "internally_futures_based_but_share_only_project",
        "start_date_dependency",
        "single_recent_regime_dependency",
        "duplicate_bonds_gld_bil_or_equity_beta",
    ]
    return [{"failure_mode": mode, "review_handling": "label and gate before promotion"} for mode in modes]


def create_packet(output_dir: Path) -> Path:
    packet = output_dir / f"{LANE_ID}_review_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def run_review(root: Path = ROOT, update_registry_file: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    original_registry = load_registry(registry_path)
    before_protected = protected_snapshot(original_registry)
    state, mismatches = state_checks(original_registry)

    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(output_dir / f"{LANE_ID}_candidate_variants.csv", VARIANTS, list(VARIANTS[0].keys()))
    write_csv(
        output_dir / f"{LANE_ID}_benchmark_plan.csv",
        benchmark_rows(),
        ["benchmark_id", "required", "reason", "comparison_metric", "missing_handling"],
    )
    write_csv(
        output_dir / f"{LANE_ID}_symbol_review.csv",
        symbol_review_rows(),
        ["symbol", "role", "allowed_for_future_review", "data_checked_now", "provider_api_called", "notes"],
    )
    write_csv(
        output_dir / f"{LANE_ID}_expected_failure_modes.csv",
        failure_mode_rows(),
        ["failure_mode", "review_handling"],
    )
    (output_dir / f"{LANE_ID}_review.md").write_text(render_review(mismatches), encoding="utf-8")
    (output_dir / f"{LANE_ID}_family_thesis.md").write_text(render_family_thesis(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_data_policy.md").write_text(render_data_policy(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_fixed_rules.md").write_text(render_fixed_rules(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_risk_policy.md").write_text(render_risk_policy(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_duplicate_risk_plan.md").write_text(render_duplicate_plan(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_rejection_criteria.md").write_text(render_rejection_criteria(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_next_action.md").write_text(render_next_action(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_decision_tree.md").write_text(render_decision_tree(), encoding="utf-8")

    updated_registry = update_registry(original_registry, str(output_dir))
    after_protected = protected_snapshot(updated_registry)
    active_observations_unchanged = before_protected == after_protected
    if update_registry_file:
        registry_path.write_text(yaml.safe_dump(updated_registry, sort_keys=False, width=140), encoding="utf-8")

    consistency = {
        "review_created": True,
        "planning_only": True,
        "no_strategy_implementation": True,
        "no_backtest_run": True,
        "no_research_sample_run": True,
        "no_candidate_exhaustive_run": True,
        "no_data_download": True,
        "no_provider_api_call": True,
        "no_direct_futures": True,
        "no_options": True,
        "no_forex": True,
        "no_crypto": True,
        "no_intraday": True,
        "no_leverage_added_by_system": True,
        "no_shorting": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": active_observations_unchanged,
        "next_action": NEXT_ACTION,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(
        value is True for key, value in consistency.items() if key not in {"next_action", "consistency_passed"}
    )
    manifest = {
        "created_at_utc": now_utc(),
        "family_id": LANE_ID,
        "lane_verdict": LANE_VERDICT,
        "next_action": NEXT_ACTION,
        "approved_variants": [variant["strategy_id"] for variant in VARIANTS],
        "state_checks": state,
        "state_mismatches": mismatches,
        "planning_only": True,
        "strategy_implementation_run": False,
        "backtest_run": False,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "direct_futures_trading": False,
        "futures_contracts": False,
        "options": False,
        "forex": False,
        "crypto": False,
        "intraday_logic": False,
        "leverage_added_by_system": False,
        "margin": False,
        "shorting": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
    }
    write_json(output_dir / f"{LANE_ID}_manifest.json", manifest)
    write_json(output_dir / f"{LANE_ID}_consistency_check.json", consistency)
    packet = create_packet(output_dir)
    return {
        "output_dir": str(output_dir),
        "packet": str(packet),
        "lane_verdict": LANE_VERDICT,
        "next_action": NEXT_ACTION,
        "approved_variants": manifest["approved_variants"],
        "consistency": consistency,
    }


def main() -> int:
    result = run_review(ROOT, update_registry_file=True)
    print(f"managed_futures_review_latest_dir={result['output_dir']}")
    print(f"managed_futures_review_packet={result['packet']}")
    print(f"lane_verdict={result['lane_verdict']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
