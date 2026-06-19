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
LANE_ID = "dual_momentum_paa_etf_wrapper"
OUTPUT_DIR = Path("evidence") / "lane_reviews" / LANE_ID / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
LANE_VERDICT = "approve_future_research_sample_prompt"
NEXT_ACTION = "create_dual_momentum_paa_etf_wrapper_research_sample_prompt"
CURRENT_ACTION = "create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt"

PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}

FORBIDDEN_NEXT_ACTIONS = [
    "direct_futures_contracts",
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

VARIANTS = [
    {
        "strategy_id": "dm_global_dual_momentum_top1_v1",
        "family": LANE_ID,
        "universe": "SPY;EFA;EEM;BIL",
        "rule_summary": "Monthly rebalance; rank SPY, EFA, EEM by 126-day return; selected asset must have positive 126-day return and close > 200-day SMA; hold top 1 else BIL.",
        "expected_profit_driver": "Minimal global dual momentum selects the strongest global equity wrapper while using BIL for failed absolute momentum.",
        "expected_failure_mode": "May duplicate SPY_200d or become BIL-heavy and too slow.",
        "likely_duplicate_risk": "SPY_200d, GROR, and SPY equity beta.",
        "implementation_difficulty": "low",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;GROR;SPY_buy_hold;QQQ_buy_hold;BIL_cash_proxy",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "dm_multi_asset_top2_absolute_momentum_v1",
        "family": LANE_ID,
        "universe": "SPY;QQQ;EFA;EEM;IWM;GLD;IEF;BIL",
        "rule_summary": "Monthly rebalance; rank SPY, QQQ, EFA, EEM, IWM, GLD, IEF by 126-day return / 60-day realized volatility; hold top 2 eligible assets equally; unused allocation to BIL.",
        "expected_profit_driver": "Multi-asset relative plus absolute momentum may diversify beyond equity-only trend.",
        "expected_failure_mode": "Risk-adjusted ranking can over-favor defensive assets and become too slow.",
        "likely_duplicate_risk": "GROR, active combo, GLD/IEF/BIL defensive sleeve.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;GROR;SPY_buy_hold;QQQ_buy_hold;GLD_buy_hold;IEF_buy_hold;BIL_cash_proxy",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "dm_protective_canary_bil_v1",
        "family": LANE_ID,
        "universe": "SPY;QQQ;EFA;EEM;GLD;IEF;BIL",
        "rule_summary": "Monthly rebalance; if EFA and EEM both have negative 126-day return or are below 200-day SMA hold BIL; otherwise rank SPY, QQQ, GLD, IEF by 126-day return / 60-day realized volatility and hold top 2 eligible assets.",
        "expected_profit_driver": "Global canary may reduce crash exposure while still allowing offensive participation.",
        "expected_failure_mode": "Canary may over-defend and miss equity recoveries.",
        "likely_duplicate_risk": "BIL-heavy protective allocation and GROR-like risk-on/risk-off behavior.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;GROR;BIL_cash_proxy;SPY_buy_hold;QQQ_buy_hold",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "dm_balanced_offensive_defensive_v1",
        "family": LANE_ID,
        "universe": "SPY;QQQ;EFA;EEM;GLD;IEF;BIL",
        "rule_summary": "Monthly rebalance; if SPY > 200-day SMA allocate 60% best eligible offensive asset and 40% best eligible defensive asset; if SPY <= 200-day SMA allocate 40% defensive and 60% BIL.",
        "expected_profit_driver": "Balanced offensive/defensive sleeve may improve drawdown without fully abandoning target power.",
        "expected_failure_mode": "Could become GROR under a different name.",
        "likely_duplicate_risk": "High overlap with GROR, SPY_200d, and active combo.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;GROR;SPY_buy_hold;GLD_buy_hold;BIL_cash_proxy",
        "next_allowed_action": NEXT_ACTION,
        "forbidden_next_actions": ";".join(FORBIDDEN_NEXT_ACTIONS),
    },
    {
        "strategy_id": "dm_paa_breadth_protection_v1",
        "family": LANE_ID,
        "universe": "SPY;QQQ;EFA;EEM;IWM;GLD;IEF;BIL",
        "rule_summary": "Monthly rebalance; if fewer than 2 risky assets are positive, hold 50% best eligible defensive asset and 50% BIL; otherwise rank all eligible assets by 126-day return / 60-day volatility and hold top 2.",
        "expected_profit_driver": "Protective asset allocation breadth may avoid broad risk-off regimes while keeping multi-asset opportunity.",
        "expected_failure_mode": "Breadth gate may be too defensive or duplicate existing risk-on/risk-off rows.",
        "likely_duplicate_risk": "GROR, SPY_200d, BIL-heavy protective sleeve.",
        "implementation_difficulty": "moderate",
        "required_benchmarks": "active_combo;VM;DSR;SPY_200d;GROR;SPY_buy_hold;QQQ_buy_hold;GLD_buy_hold;IEF_buy_hold;BIL_cash_proxy",
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


def load_yaml(path: Path) -> dict[str, Any]:
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


def state_checks(registry: dict[str, Any], root: Path) -> tuple[dict[str, bool], list[str]]:
    rows = rows_by_id(registry)
    managed_manifest = root / "evidence" / "research_samples" / "managed_futures_etf_wrapper" / "latest" / "managed_futures_etf_wrapper_manifest.json"
    managed_payload = json.loads(managed_manifest.read_text(encoding="utf-8")) if managed_manifest.exists() else {}
    managed = rows.get("managed_futures_etf_wrapper", {})
    dual = rows.get(LANE_ID, {})
    gror = rows.get("gror_balanced_momentum_60_40_v1", {})
    quality = rows.get("quality_momentum_etf_proxy", {})
    vm = rows.get("paper_forward_vm_quality_lowvol_proxy_v1", {})
    dsr = rows.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", {})
    spy = rows.get("SPY_200d_trend_model", {})
    checks = {
        "managed_futures_watchlist_not_promotion_candidate": managed_payload.get("family_verdict") == "watchlist_family" and managed.get("status") == "watchlist_family",
        "next_action_is_dual_momentum_review": managed_payload.get("next_action") == CURRENT_ACTION and managed.get("allowed_next_action") == CURRENT_ACTION,
        "dual_momentum_priority_2": dual.get("priority_rank") == 2,
        "gror_watchlist_not_next": gror.get("paper_forward_active") is False and "watchlist" in str(gror.get("status")),
        "quality_momentum_watchlist_not_next": quality.get("paper_forward_active") is False and "watchlist" in str(quality.get("status")),
        "vm_quality_active_frozen": vm.get("paper_forward_active") is True and vm.get("rules_frozen") is True,
        "dsr_equal_weight_active_frozen": dsr.get("paper_forward_active") is True and dsr.get("rules_frozen") is True,
        "spy_200d_frozen_control": spy.get("paper_forward_active") is True and spy.get("rules_frozen") is True,
    }
    return checks, [key for key, value in checks.items() if not value]


def update_registry(registry: dict[str, Any], output_dir: str) -> dict[str, Any]:
    updated = deepcopy(registry)
    updated.setdefault("strategies", [])
    rows = rows_by_id(updated)
    row = rows.get(LANE_ID)
    if row is None:
        row = {
            "id": LANE_ID,
            "display_name": "Dual Momentum PAA ETF Wrapper",
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
            "evidence_source": "dual_momentum_paa_etf_wrapper_review",
            "promotion_requirements": "Future research_sample prompt required before any implementation.",
            "demotion_or_kill_criteria": "Reject if duplicate, too slow, too risky, or requires forbidden mechanics.",
            "notes": "ETF/fund-wrapper review row only.",
            "strategy_id": LANE_ID,
            "family": LANE_ID,
            "instrument_lane": "ETF",
            "evidence_tier": "tier1_research_queue",
            "risk_framework_status": "research_only_review_gate",
            "promotion_blockers": "planning_only;not_tested;no_real_money_path",
            "primary_failure_mode": "not_tested",
            "duplication_risk": "requires_future_review",
            "risk_budget_status": "not_tested",
            "evidence_needed": "future research_sample evidence",
            "duplicate_of": "",
            "blocked_reason": "",
        }
        updated["strategies"].append(row)
    if row.get("paper_forward_active") is True:
        return updated
    row.update(
        {
            "status": "research_sample_candidate",
            "current_status": "research_sample_candidate",
            "lane_review_verdict": LANE_VERDICT,
            "allowed_next_action": NEXT_ACTION,
            "next_allowed_action": NEXT_ACTION,
            "allowed_next_actions": [NEXT_ACTION],
            "paper_forward_active": False,
            "paper_forward_allowed_by_risk_framework": False,
            "real_money_recommendation": False,
            "candidate_exhaustive_run": False,
            "candidate_exhaustive_recommended": False,
            "promotion_review_required": False,
            "promotion_decision": "not_reviewed",
            "promotion_reason": "Design gate only.",
            "latest_evidence_path": output_dir,
            "latest_known_result_summary": "Dual momentum / PAA ETF-wrapper design gate approved fixed variants for a future explicitly prompted research_sample. No strategy/backtest/data download was run.",
            "evidence_source": "dual_momentum_paa_etf_wrapper_review",
            "notes": "ETF/fund-wrapper only. No direct futures, leverage, shorting, broker path, or real-money recommendation.",
            "forbidden_next_actions": sorted(set(row.get("forbidden_next_actions") or []) | set(FORBIDDEN_NEXT_ACTIONS)),
        }
    )
    updated.setdefault("registry", {})["last_updated_utc"] = now_utc()
    return updated


def render_review(mismatches: list[str]) -> str:
    mismatch_lines = ["- None."] if not mismatches else [f"- {item}" for item in mismatches]
    return "\n".join(
        [
            "# Dual Momentum PAA ETF Wrapper Review",
            "",
            f"Family id: `{LANE_ID}`",
            f"Lane verdict: `{LANE_VERDICT}`",
            f"Exact next action: `{NEXT_ACTION}`",
            "",
            "This is a review/design gate only. It does not implement a strategy, run a backtest, run research_sample, run candidate_exhaustive, download data, call provider APIs, activate paper-forward, or add broker/live-order/real-money paths.",
            "",
            "The lane is allowed only as fixed tactical ETF/fund-wrapper rules. No direct futures, leverage, shorting, options, forex, crypto, or intraday path is allowed.",
            "",
            "## State Mismatches",
            "",
            *mismatch_lines,
            "",
        ]
    )


def render_family_thesis() -> str:
    return """# Dual Momentum PAA ETF Wrapper Family Thesis

Family id: `dual_momentum_paa_etf_wrapper`

Thesis: use simple ETF-wrapper rules combining relative momentum and absolute momentum / protective allocation logic to test whether a tactical multi-asset family can improve the project's profit/risk frontier without becoming another SPY_200d, GROR, or active-combo duplicate.

Why this family may help:

- Relative momentum can select stronger assets.
- Absolute momentum / trend filters can reduce crash exposure.
- Protective allocation may avoid deep drawdowns.
- It can remain simple, fixed-rule, and ETF-wrapper only.
- It may be more adaptable than static GTAA and less equity-heavy than quality/momentum.
- It may provide a clean bridge between trend following and tactical allocation.

Why this family may fail:

- It may duplicate GROR, SPY_200d, or active combo.
- It may become too defensive and slow.
- It may overfit tactical allocation logic if too many filters are added.
- It may underperform SPY/QQQ in strong equity regimes.
- It may rely too much on BIL.
- It may look good only because of a specific crisis window.
- It may not add enough after VM quality and DSR equal-weight are already active.

This family should be minimal and fixed-rule. No parameter search. No many-variant tuning. No direct futures. No leverage.
"""


def render_data_policy() -> str:
    return """# Dual Momentum PAA ETF Wrapper Data Policy

Allowed default symbols:

- `SPY`
- `QQQ`
- `EFA`
- `EEM`
- `IWM`
- `GLD`
- `IEF`
- `BIL`

Conditional benchmark-only:

- `TLT`
- `AGG`

Optional only if already approved elsewhere:

- `DBC` or broad commodity ETF wrapper, benchmark-only unless explicitly approved later.

Do not use individual stocks, leveraged ETFs, inverse ETFs, direct futures, options, forex, crypto, intraday data, sector ETFs as core symbols, or managed-futures wrappers as core symbols in this lane.

This review does not download data. A future research_sample may use yfinance-compatible adjusted daily ETF/fund-wrapper data only if explicitly prompted and clearly labeled as exploratory/non-institutional.
"""


def render_fixed_rules() -> str:
    lines = ["# Dual Momentum PAA ETF Wrapper Fixed Rules", ""]
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
                "No leverage. No direct futures contracts. No parameter optimization or grid search.",
                "",
            ]
        )
    return "\n".join(lines)


def render_duplicate_plan() -> str:
    return """# Dual Momentum PAA ETF Wrapper Duplicate Risk Plan

Future research_sample must compare against active combo, `paper_forward_vm_quality_lowvol_proxy_v1`, `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`, `SPY_200d`, `gror_balanced_momentum_60_40_v1`, SPY buy-hold, QQQ buy-hold, GLD buy-hold, BIL, IEF/TLT/AGG if available, and an equal-weight global tactical basket if available.

Duplicate risks:

- Simply replicates SPY_200d.
- Becomes GROR under a different name.
- Becomes active-combo-like SPY/GLD blend.
- Becomes BIL-heavy and too slow.
- Becomes QQQ/SPY growth beta.
- Creates many tactical rules without real additive behavior.

Additive proof should include different target windows, different drawdown windows, useful +300/+400 rates, acceptable drawdown, lower overlap with SPY_200d/GROR/active combo, and a clear reason why it is not just another global risk-on/risk-off blend.
"""


def render_risk_policy() -> str:
    return """# Dual Momentum PAA ETF Wrapper Risk Policy

Future research_sample must evaluate profit metrics: median final equity, mean final equity, upper-percentile final equity, best-window final equity, and +300/+400 target-before-stop rates.

Future research_sample must evaluate risk metrics: worst drawdown, median drawdown, -$600 stop-hit rate, worst loss window, loss-window rate, profit-to-drawdown ratio, and whether protection makes it too slow.

Practical risk review must include tactical rule overfitting, too many filters, BIL-heavy behavior, duplication with GROR / SPY_200d, and history sensitivity.

Decision rules:

- If row improves drawdown but kills target power, too_slow.
- If row breaches drawdown budget, too_risky.
- If row is mostly SPY_200d or GROR duplicate, duplicate_or_near_duplicate.
- If row has useful target/risk and additive behavior, promotion_review_candidate.
- If all rows are slow/duplicate, move to GTAA benchmark lane.
"""


def render_rejection_criteria() -> str:
    return """# Dual Momentum PAA ETF Wrapper Rejection Criteria

Reject or watchlist if a row fails to improve profit opportunity, has weak +300/+400 target rates, is too defensive/slow, duplicates GROR, SPY_200d, active combo, SPY/QQQ, GLD, or BIL, breaches drawdown budget, relies on too many tactical filters, requires forbidden mechanics, depends on tuned thresholds, or cannot be tested with ETF/fund-wrapper adjusted daily data.

Promotion review is allowed only if the row is fixed-rule, ETF/fund-wrapper only, has useful profit/target metrics, acceptable drawdown, likely additive behavior, and no forbidden mechanics.
"""


def render_next_action() -> str:
    return f"""# Dual Momentum PAA ETF Wrapper Next Action

Decision: `{LANE_VERDICT}`

Exact next action: `{NEXT_ACTION}`

Reason: fixed variants are defined, no forbidden mechanics are needed, future data can be ETF/fund-wrapper adjusted daily, active observations stay separate, and the duplicate plan explicitly includes GROR, SPY_200d, active combo, VM, and DSR.

Do not implement the lane, download data, run research_sample, run candidate_exhaustive, or activate paper-forward from this review.
"""


def render_decision_tree() -> str:
    return """# Dual Momentum PAA ETF Wrapper Decision Tree

1. If fixed ETF-wrapper symbols are unavailable, defer or perform an explicitly prompted data/symbol check.
2. If data is available, run only a future explicitly prompted exploratory research_sample.
3. If rows are too slow, watchlist or reject.
4. If rows breach risk budget, mark too_risky.
5. If rows duplicate GROR/SPY_200d/active combo, mark duplicate_or_near_duplicate.
6. If a fixed row is profitable, risk-acceptable, and additive, allow promotion_review_candidate.
7. If all rows fail, move to GTAA Faber-style benchmark lane.
"""


def benchmark_rows() -> list[dict[str, Any]]:
    rows = [
        ("active_combo", True, "active reference blend", "delta equity; correlation; target/drawdown overlap", "required; if unavailable mark evidence_missing"),
        ("paper_forward_vm_quality_lowvol_proxy_v1", True, "active/frozen VM reference", "correlation; drawdown behavior; target windows", "required; do not mutate"),
        ("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", True, "active/frozen DSR reference", "correlation; drawdown behavior; target windows", "required; do not mutate"),
        ("SPY_200d", True, "frozen control", "delta equity; stop-hit rate; drawdown", "required"),
        ("gror_balanced_momentum_60_40_v1", True, "watchlist GROR comparator", "delta equity; duplicate/overlap", "required; use latest evidence if available"),
        ("SPY_buy_hold", True, "equity beta benchmark", "delta equity; drawdown; target rates", "required"),
        ("QQQ_buy_hold", True, "growth benchmark", "delta equity; drawdown; target rates", "required"),
        ("GLD_buy_hold", True, "alternative/defensive benchmark", "correlation; drawdown; delta equity", "required"),
        ("BIL_cash_proxy", True, "cash proxy", "cash fallback opportunity cost", "required"),
        ("IEF_buy_hold", True, "bond benchmark", "correlation; defensive overlap", "if available"),
        ("TLT_buy_hold", False, "duration benchmark", "correlation; defensive overlap", "conditional if available"),
        ("AGG_buy_hold", False, "aggregate bond benchmark", "correlation; defensive overlap", "conditional if available"),
        ("equal_weight_global_tactical_basket", False, "simple global tactical comparator", "delta equity; duplicate risk", "conditional if available"),
    ]
    return [
        {"benchmark_id": benchmark_id, "required": required, "reason": reason, "comparison_metric": metric, "missing_handling": missing}
        for benchmark_id, required, reason, metric, missing in rows
    ]


def symbol_review_rows() -> list[dict[str, Any]]:
    symbols = ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL", "TLT", "AGG", "DBC"]
    return [
        {
            "symbol": symbol,
            "role": "core" if symbol in {"SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"} else "conditional_benchmark",
            "allowed_for_future_review": symbol != "DBC",
            "data_checked_now": False,
            "provider_api_called": False,
            "notes": "Review only; no data download. DBC is benchmark-only unless explicitly approved later." if symbol == "DBC" else "ETF/fund-wrapper symbol allowed if future prompt authorizes data use.",
        }
        for symbol in symbols
    ]


def failure_mode_rows() -> list[dict[str, Any]]:
    modes = [
        "duplicates_spy_200d",
        "duplicates_gror",
        "active_combo_like_spy_gld_blend",
        "bil_heavy_too_slow",
        "qqq_spy_growth_beta",
        "too_many_tactical_filters",
        "weak_target_power",
        "drawdown_budget_breach",
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
    registry = load_yaml(registry_path)
    before_protected = protected_snapshot(registry)
    checks, mismatches = state_checks(registry, root)
    if mismatches:
        raise RuntimeError("; ".join(mismatches))

    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(output_dir / f"{LANE_ID}_candidate_variants.csv", VARIANTS, list(VARIANTS[0].keys()))
    write_csv(output_dir / f"{LANE_ID}_benchmark_plan.csv", benchmark_rows(), ["benchmark_id", "required", "reason", "comparison_metric", "missing_handling"])
    write_csv(output_dir / f"{LANE_ID}_symbol_review.csv", symbol_review_rows(), ["symbol", "role", "allowed_for_future_review", "data_checked_now", "provider_api_called", "notes"])
    write_csv(output_dir / f"{LANE_ID}_expected_failure_modes.csv", failure_mode_rows(), ["failure_mode", "review_handling"])

    (output_dir / f"{LANE_ID}_review.md").write_text(render_review(mismatches), encoding="utf-8")
    (output_dir / f"{LANE_ID}_family_thesis.md").write_text(render_family_thesis(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_data_policy.md").write_text(render_data_policy(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_fixed_rules.md").write_text(render_fixed_rules(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_risk_policy.md").write_text(render_risk_policy(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_duplicate_risk_plan.md").write_text(render_duplicate_plan(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_rejection_criteria.md").write_text(render_rejection_criteria(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_next_action.md").write_text(render_next_action(), encoding="utf-8")
    (output_dir / f"{LANE_ID}_decision_tree.md").write_text(render_decision_tree(), encoding="utf-8")

    updated_registry = update_registry(registry, str(output_dir))
    active_unchanged = before_protected == protected_snapshot(updated_registry)
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
        "active_observations_unchanged": active_unchanged,
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
        "state_checks": checks,
        "state_mismatches": mismatches,
        "planning_only": True,
        "strategy_implementation_run": False,
        "backtest_run": False,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "direct_futures_contracts": False,
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
    print(f"dual_momentum_review_latest_dir={result['output_dir']}")
    print(f"dual_momentum_review_packet={result['packet']}")
    print(f"lane_verdict={result['lane_verdict']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
