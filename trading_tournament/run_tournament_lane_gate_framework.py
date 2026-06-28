from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "tournament_lane_gate_framework" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
ROOT_CAUSE_DIR = Path("evidence") / "tournament_root_cause_audit" / "latest"

NEXT_ACTION = "pre_register_second_expansion_discovery_batch_with_lane_framework"
VALID_NEXT_ACTIONS = {
    "run_sector_rs_limited_history_discovery_batch",
    "pre_register_gld_gror_macro_research_lane",
    "pre_register_second_expansion_discovery_batch_with_lane_framework",
}

LANE_IDS = [
    "conservative_etf_allocation_lane",
    "moderate_tactical_etf_lane",
    "macro_gld_duration_risk_off_lane",
    "diversifier_contribution_lane",
    "intraday_research_only_lane",
]

GATES = [
    "benchmark edge",
    "risk buffer",
    "drawdown",
    "stop-hit count/rate",
    "slippage/spread stress",
    "max trades per week",
    "max trades per day",
    "max open positions",
    "BIL allocation",
    "correlation/duplication",
    "minimum trade count",
    "limited-history handling",
    "same-window benchmark handling",
    "target hit rate",
    "turnover",
    "concentration",
    "execution realism",
    "paper/demo eligibility",
]

MANIFEST_FLAGS = {
    "governance_only": True,
    "lane_gate_framework_created": True,
    "new_backtests_run": False,
    "new_discovery_run": False,
    "performance_metrics_computed_from_new_tests": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "provider_download": False,
    "real_money_recommendation": False,
    "strategy_results_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "old_gld_gror_state_resumed": False,
}


LANES: dict[str, dict[str, Any]] = {
    "conservative_etf_allocation_lane": {
        "purpose": "Low-complexity, drawdown-controlled ETF allocation.",
        "eligible_strategy_families": [
            "SPY_200d",
            "VM/DSR controls",
            "BIL/IEF/GLD defensive blends",
            "low-turnover tactical allocation",
        ],
        "benchmark_group": ["SPY_200d", "active VM", "active DSR", "active combo", "BIL"],
        "performance_gates": [
            "Must improve benchmark risk profile or provide clear same-window risk reduction.",
            "Must not dilute return target without drawdown benefit.",
            "Must show useful target-hit behavior for a conservative allocation lane.",
        ],
        "risk_gates": [
            "Strict drawdown gate.",
            "Strict risk buffer gate.",
            "Stop-hit count/rate must remain acceptable.",
            "No weak duplicates of active VM, active DSR, or active combo.",
        ],
        "slippage_execution_assumptions": [
            "Weekly/monthly allocation execution assumptions only.",
            "Spread/slippage stress must reflect low-turnover ETF allocation.",
        ],
        "trade_frequency_rules": [
            "Low turnover expected.",
            "Max one scheduled rebalance per week unless the candidate preregistration is stricter.",
        ],
        "drawdown_risk_buffer_rules": [
            "Drawdown and risk buffer remain strict and cannot be waived for simplicity.",
            "BIL/defensive sleeves must reduce risk rather than simply slow the strategy.",
        ],
        "correlation_duplication_rules": [
            "Reject near-duplicates of active VM, active DSR, active combo, or SPY_200d.",
        ],
        "diversification_contribution_rules": [
            "Defensive allocation must add risk reduction or stability after costs.",
        ],
        "demo_eligibility_rules": [
            "Promotion review required before any demo or paper-forward validation.",
        ],
        "promotion_review_rules": [
            "Promotion review only after same-window benchmark packet and risk packet.",
        ],
        "rejection_rules": [
            "Reject if weaker than active references without risk benefit.",
            "Reject if only a diluted equity wrapper.",
            "Reject if low return is not compensated by drawdown reduction.",
        ],
        "gate_decisions": {
            "benchmark edge": "lane-specific",
            "risk buffer": "shared across all lanes",
            "drawdown": "shared across all lanes",
            "stop-hit count/rate": "shared across all lanes",
            "slippage/spread stress": "lane-specific",
            "max trades per week": "lane-specific",
            "max trades per day": "not applicable",
            "max open positions": "lane-specific",
            "BIL allocation": "lane-specific",
            "correlation/duplication": "shared across all lanes",
            "minimum trade count": "lane-specific",
            "limited-history handling": "shared across all lanes",
            "same-window benchmark handling": "lane-specific",
            "target hit rate": "lane-specific",
            "turnover": "lane-specific",
            "concentration": "lane-specific",
            "execution realism": "shared across all lanes",
            "paper/demo eligibility": "lane-specific",
        },
    },
    "moderate_tactical_etf_lane": {
        "purpose": "More active daily/weekly ETF strategies with controlled risk and higher return potential.",
        "eligible_strategy_families": [
            "daily mean reversion",
            "daily/weekly momentum",
            "volatility compression breakout",
            "Donchian/ATR breakout",
            "tactical SPY/QQQ/sector rotation",
        ],
        "benchmark_group": ["active VM", "active DSR", "active combo", "SPY_200d", "SPY", "QQQ", "BIL"],
        "performance_gates": [
            "Must beat or materially improve risk versus active VM, active DSR, active combo, and SPY_200d.",
            "Must have enough trades for its timeframe.",
            "Must not be only a SPY/QQQ clone.",
        ],
        "risk_gates": [
            "Strict drawdown/risk-buffer gate.",
            "Strict slippage/spread stress.",
            "Trade diagnostics required.",
        ],
        "slippage_execution_assumptions": [
            "Daily and weekly rows need explicit next-open or next-close assumptions.",
            "Higher-turnover rows require stricter spread/slippage stress.",
        ],
        "trade_frequency_rules": [
            "Higher trade count allowed than conservative allocation.",
            "Max trades per week/day must be declared by candidate.",
        ],
        "drawdown_risk_buffer_rules": [
            "Higher activity does not relax stop or drawdown gates.",
        ],
        "correlation_duplication_rules": [
            "Reject if behavior is a SPY, QQQ, active combo, VM, or DSR clone.",
        ],
        "diversification_contribution_rules": [
            "Diversification is useful, but standalone risk-adjusted edge is still required.",
        ],
        "demo_eligibility_rules": [
            "No direct demo eligibility from discovery.",
            "Promotion review required first.",
        ],
        "promotion_review_rules": [
            "Requires trade diagnostics, rolling-window evidence, and stress results.",
        ],
        "rejection_rules": [
            "Reject if slippage erases edge.",
            "Reject if drawdown/risk buffer fails.",
            "Reject if trade count is too thin for confidence or too high for ETF execution.",
        ],
        "gate_decisions": {
            "benchmark edge": "lane-specific",
            "risk buffer": "shared across all lanes",
            "drawdown": "shared across all lanes",
            "stop-hit count/rate": "shared across all lanes",
            "slippage/spread stress": "lane-specific",
            "max trades per week": "lane-specific",
            "max trades per day": "lane-specific",
            "max open positions": "lane-specific",
            "BIL allocation": "lane-specific",
            "correlation/duplication": "shared across all lanes",
            "minimum trade count": "lane-specific",
            "limited-history handling": "shared across all lanes",
            "same-window benchmark handling": "lane-specific",
            "target hit rate": "lane-specific",
            "turnover": "lane-specific",
            "concentration": "lane-specific",
            "execution realism": "shared across all lanes",
            "paper/demo eligibility": "lane-specific",
        },
    },
    "macro_gld_duration_risk_off_lane": {
        "purpose": "Evaluate macro diversifiers and risk-off assets, not only standalone equity-like return.",
        "eligible_strategy_families": [
            "GLD trend",
            "GLD/equity rotation",
            "GLD/IEF/BIL defensive rotation",
            "GROR / global risk-on-risk-off",
            "TLT/IEF duration strategies if data approved",
        ],
        "benchmark_group": [
            "same-window SPY_200d",
            "active combo",
            "active VM",
            "active DSR",
            "GLD",
            "IEF/TLT where applicable",
            "BIL",
        ],
        "performance_gates": [
            "Must use same-window benchmarks.",
            "May earn diversification credit for crisis/risk-off usefulness.",
            "Must not be only GLD buy-and-hold with extra complexity.",
        ],
        "risk_gates": [
            "Drawdown/risk buffer must remain acceptable.",
            "BIL fallback is acceptable only when it improves risk-adjusted behavior.",
            "Recovered GROR history is context only and cannot prove current readiness.",
        ],
        "slippage_execution_assumptions": [
            "Weekly/monthly ETF rotation assumptions unless a candidate preregistration says otherwise.",
            "Spread/slippage stress must reflect GLD, IEF, TLT, BIL, SPY, and QQQ liquidity.",
        ],
        "trade_frequency_rules": [
            "Weekly or monthly cadence preferred.",
            "No intraday logic in this lane.",
        ],
        "drawdown_risk_buffer_rules": [
            "Do not require equity-like behavior, but do require risk survival.",
        ],
        "correlation_duplication_rules": [
            "Reject if just an equity wrapper with GLD decoration.",
            "Check overlap with active combo and SPY_200d.",
        ],
        "diversification_contribution_rules": [
            "Crisis/risk-off diagnostics required.",
            "Contribution to portfolio risk reduction may matter.",
        ],
        "demo_eligibility_rules": [
            "Clean pre-registration and promotion review required.",
        ],
        "promotion_review_rules": [
            "Only promotion_review_candidate_macro is allowed after future discovery.",
        ],
        "rejection_rules": [
            "Reject if benchmarks are not recomputed same-window.",
            "Reject if GLD buy-and-hold explains the result.",
            "Reject if data comparability is incomplete.",
        ],
        "gate_decisions": {
            "benchmark edge": "lane-specific",
            "risk buffer": "shared across all lanes",
            "drawdown": "shared across all lanes",
            "stop-hit count/rate": "shared across all lanes",
            "slippage/spread stress": "lane-specific",
            "max trades per week": "lane-specific",
            "max trades per day": "not applicable",
            "max open positions": "lane-specific",
            "BIL allocation": "lane-specific",
            "correlation/duplication": "shared across all lanes",
            "minimum trade count": "lane-specific",
            "limited-history handling": "shared across all lanes",
            "same-window benchmark handling": "lane-specific",
            "target hit rate": "lane-specific",
            "turnover": "lane-specific",
            "concentration": "lane-specific",
            "execution realism": "shared across all lanes",
            "paper/demo eligibility": "lane-specific",
        },
    },
    "diversifier_contribution_lane": {
        "purpose": "Evaluate strategies that may not be strong standalone winners but may improve active combo or portfolio risk.",
        "eligible_strategy_families": [
            "small fixed sleeves",
            "overlays",
            "defensive ballast",
            "risk filters",
            "cash/BIL overlays",
        ],
        "benchmark_group": ["base strategy", "active combo", "portfolio-without-diversifier", "portfolio-with-diversifier"],
        "performance_gates": [
            "Marginal contribution matters more than standalone profit.",
            "Must improve risk-adjusted return or reduce drawdown without target collapse.",
        ],
        "risk_gates": [
            "Must reduce or not materially worsen portfolio drawdown.",
            "Must not hide risk by excessive cash dilution.",
        ],
        "slippage_execution_assumptions": [
            "Execution assumptions follow the base strategy cadence.",
            "Overlay turnover must be explicit.",
        ],
        "trade_frequency_rules": [
            "Trade frequency is candidate-specific and must not create hidden implementation burden.",
        ],
        "drawdown_risk_buffer_rules": [
            "Judge marginal drawdown and risk-buffer contribution relative to the base portfolio.",
        ],
        "correlation_duplication_rules": [
            "High correlation is allowed only if marginal drawdown/return contribution is proven.",
        ],
        "diversification_contribution_rules": [
            "Must compare portfolio with and without diversifier.",
            "Must document contribution to crisis/risk-off or smoother compounding.",
        ],
        "demo_eligibility_rules": [
            "Watchlist by default unless strong incremental evidence exists.",
        ],
        "promotion_review_rules": [
            "Requires component contribution and overlap exports.",
        ],
        "rejection_rules": [
            "Reject if it simply dilutes exposure.",
            "Reject if standalone profit looks fine but portfolio contribution is weak.",
        ],
        "gate_decisions": {
            "benchmark edge": "lane-specific",
            "risk buffer": "shared across all lanes",
            "drawdown": "shared across all lanes",
            "stop-hit count/rate": "shared across all lanes",
            "slippage/spread stress": "lane-specific",
            "max trades per week": "lane-specific",
            "max trades per day": "lane-specific",
            "max open positions": "lane-specific",
            "BIL allocation": "lane-specific",
            "correlation/duplication": "lane-specific",
            "minimum trade count": "lane-specific",
            "limited-history handling": "shared across all lanes",
            "same-window benchmark handling": "lane-specific",
            "target hit rate": "lane-specific",
            "turnover": "lane-specific",
            "concentration": "lane-specific",
            "execution realism": "shared across all lanes",
            "paper/demo eligibility": "lane-specific",
        },
    },
    "intraday_research_only_lane": {
        "purpose": "Explore intraday ideas without demo eligibility until execution/data readiness is proven.",
        "eligible_strategy_families": [
            "ORB",
            "VWAP deviation",
            "gap fade",
            "gap continuation",
            "intraday ETF reversion/momentum",
        ],
        "benchmark_group": ["intraday SPY/QQQ baselines only after data QA"],
        "performance_gates": [
            "Performance gates are secondary to data quality and execution realism at this stage.",
            "No demo eligibility initially.",
        ],
        "risk_gates": [
            "Max daily loss required.",
            "Max trade count per day required.",
            "Kill switch readiness required.",
        ],
        "slippage_execution_assumptions": [
            "Point-in-time intraday data required before any research run.",
            "Fill, spread, latency, and reconciliation assumptions must be audited first.",
        ],
        "trade_frequency_rules": [
            "Max trades per day is mandatory.",
            "No paper/demo path until execution quality is proven.",
        ],
        "drawdown_risk_buffer_rules": [
            "Daily loss controls and kill switch design precede strategy performance review.",
        ],
        "correlation_duplication_rules": [
            "Must prove it is not just daily ETF exposure in intraday clothing.",
        ],
        "diversification_contribution_rules": [
            "Diversification is secondary until data/execution readiness exists.",
        ],
        "demo_eligibility_rules": [
            "Research-only; not demo eligible.",
        ],
        "promotion_review_rules": [
            "No promotion review until data QA and execution readiness gates pass.",
        ],
        "rejection_rules": [
            "Reject or defer if data quality, fill realism, broker reconciliation, or kill switch readiness is absent.",
        ],
        "gate_decisions": {
            "benchmark edge": "not applicable",
            "risk buffer": "shared across all lanes",
            "drawdown": "shared across all lanes",
            "stop-hit count/rate": "shared across all lanes",
            "slippage/spread stress": "lane-specific",
            "max trades per week": "lane-specific",
            "max trades per day": "lane-specific",
            "max open positions": "lane-specific",
            "BIL allocation": "not applicable",
            "correlation/duplication": "shared across all lanes",
            "minimum trade count": "lane-specific",
            "limited-history handling": "shared across all lanes",
            "same-window benchmark handling": "lane-specific",
            "target hit rate": "lane-specific",
            "turnover": "lane-specific",
            "concentration": "lane-specific",
            "execution realism": "shared across all lanes",
            "paper/demo eligibility": "lane-specific",
        },
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_state_snapshot(root: Path) -> list[dict[str, Any]]:
    registry = load_yaml(root / REGISTRY_PATH)
    return deepcopy(registry.get("strategies", []))


def update_registry_metadata(root: Path, output: Path, created_utc: str) -> bool:
    path = root / REGISTRY_PATH
    if not path.exists():
        return False
    registry = load_yaml(path)
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "tournament_lane_gate_framework_path": str(output),
            "tournament_lane_gate_framework_status": "created",
            "tournament_lane_gate_framework_created_utc": created_utc,
            "lane_gate_framework_next_action": NEXT_ACTION,
            "current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "governance_only": True,
            "new_backtests_run": False,
            "new_discovery_run": False,
            "candidate_exhaustive_run": False,
            "paper_forward_active": False,
            "real_money_recommendation": False,
        }
    )
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    return True


def update_roadmap(root: Path, output: Path, created_utc: str) -> bool:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[index] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        lines.insert(1 if lines else 0, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    marker = "## Tournament Lane Gate Framework"
    section = f"""## Tournament Lane Gate Framework

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Lanes: `{', '.join(LANE_IDS)}`
- Status: `created_governance_only`
- Next action: `{NEXT_ACTION}`
- No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, strategy result change, accepted/rejected state change, GLD/GROR state resumption, or real-money recommendation is authorized by this framework update.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True


def framework_yaml() -> dict[str, Any]:
    return {
        "framework_id": "tournament_lane_gate_framework_v1",
        "governance_only": True,
        "lane_count": len(LANES),
        "lanes": LANES,
        "gate_classification_values": ["shared across all lanes", "lane-specific", "not applicable"],
        "global_rules": [
            "Do not lower standards globally.",
            "Do not remove risk controls.",
            "Do not approve weak strategies.",
            "Do not create a shortcut to paper-forward.",
            "Do not resume old GLD/GROR candidate_exhaustive state.",
        ],
        "valid_next_actions": sorted(VALID_NEXT_ACTIONS),
        "next_action": NEXT_ACTION,
    }


def lane_strategy_family_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for family in lane["eligible_strategy_families"]:
            rows.append(
                {
                    "lane_id": lane_id,
                    "purpose": lane["purpose"],
                    "eligible_strategy_family": family,
                    "demo_eligibility": "; ".join(lane["demo_eligibility_rules"]),
                }
            )
    return rows


def lane_benchmark_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for benchmark in lane["benchmark_group"]:
            rows.append(
                {
                    "lane_id": lane_id,
                    "benchmark": benchmark,
                    "same_window_required": "true" if lane_id == "macro_gld_duration_risk_off_lane" or "same-window" in " ".join(lane["performance_gates"]).lower() else "when_window_differs",
                    "benchmark_role": "required_or_lane_primary",
                }
            )
    return rows


def lane_risk_gate_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for gate in lane["risk_gates"] + lane["drawdown_risk_buffer_rules"] + lane["correlation_duplication_rules"]:
            rows.append(
                {
                    "lane_id": lane_id,
                    "risk_gate": gate,
                    "gate_decision_context": "lane-specific detail with shared no-shortcut risk discipline",
                }
            )
    return rows


def lane_performance_gate_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for gate in lane["performance_gates"] + lane["diversification_contribution_rules"]:
            rows.append(
                {
                    "lane_id": lane_id,
                    "performance_gate": gate,
                    "gate_decision_context": "lane-specific performance and contribution standard",
                }
            )
    return rows


def lane_execution_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for assumption in lane["slippage_execution_assumptions"] + lane["trade_frequency_rules"]:
            rows.append(
                {
                    "lane_id": lane_id,
                    "execution_or_trade_frequency_rule": assumption,
                    "paper_demo_eligibility": "; ".join(lane["demo_eligibility_rules"]),
                }
            )
    return rows


def gate_decision_rows() -> list[dict[str, Any]]:
    rows = []
    for lane_id, lane in LANES.items():
        for gate in GATES:
            rows.append(
                {
                    "lane_id": lane_id,
                    "gate": gate,
                    "decision": lane["gate_decisions"][gate],
                }
            )
    return rows


def failure_reason_rows(root: Path) -> list[dict[str, Any]]:
    failure_rows = read_csv_rows(root / ROOT_CAUSE_DIR / "failure_reason_dashboard.csv")
    counts = Counter(row.get("primary_failure_reason", "unknown") for row in failure_rows)
    if not counts:
        counts = Counter({"unavailable_root_cause_dashboard": 0})
    recommendations = {
        "duplication_or_high_correlation": ("All lanes", "Keep correlation/duplication gate; require lane-specific benchmark and overlap evidence."),
        "risk_buffer_or_drawdown": ("All lanes", "Keep strict risk buffer and drawdown gates; do not rescue high-upside rows by lowering risk controls."),
        "data_or_incomplete_evidence": ("Macro, intraday, limited-history lanes", "Require data QA and same-window comparability before discovery."),
        "weaker_than_active_or_benchmark": ("Conservative and tactical lanes", "Use active VM, active DSR, active combo, and SPY_200d as relevant lane references."),
        "too_slow_for_profit_goal": ("Conservative and diversifier lanes", "Allow risk reduction only if target collapse is avoided."),
        "limited_history_or_inception": ("All lanes", "Keep limited-history labels and same-window benchmark recomputation."),
        "watchlist_not_promoted": ("All lanes", "Keep watchlist status unless promotion-review evidence is explicit."),
        "not_promoted_or_incomplete": ("All lanes", "Require complete evidence packet before any promotion-review candidate label."),
        "unavailable_root_cause_dashboard": ("Manual review", "Root-cause dashboard was not available in the fixture or workspace."),
    }
    rows = []
    for reason, count in sorted(counts.items()):
        lane, rec = recommendations.get(reason, ("All lanes", "Manual lane assignment required."))
        rows.append(
            {
                "primary_failure_reason": reason,
                "count": count,
                "lane_recommendation": lane,
                "gate_framework_response": rec,
            }
        )
    return rows


def promotion_rules_md() -> str:
    lines = ["# Lane Promotion Rules", ""]
    for lane_id, lane in LANES.items():
        lines.extend([f"## {lane_id}", ""])
        lines.extend(f"- {item}" for item in lane["promotion_review_rules"])
        lines.extend(f"- Demo eligibility: {item}" for item in lane["demo_eligibility_rules"])
        lines.append("")
    lines.extend(
        [
            "No lane creates direct permission for candidate_exhaustive, paper-forward activation, demo-active status, live readiness, broker integration, or real-money use.",
            "",
        ]
    )
    return "\n".join(lines)


def rejection_rules_md() -> str:
    lines = ["# Lane Rejection Rules", ""]
    for lane_id, lane in LANES.items():
        lines.extend([f"## {lane_id}", ""])
        lines.extend(f"- {item}" for item in lane["rejection_rules"])
        lines.append("")
    lines.extend(
        [
            "A rejected exact variant remains rejected. A family may remain open only with a new written hypothesis, a new candidate ID, exactly one major changed dimension, and a new pre-registration before testing.",
            "",
        ]
    )
    return "\n".join(lines)


def next_batch_policy_md() -> str:
    return f"""# Next Batch Selection Policy

Use the lane framework before adding any new discovery batch.

1. Assign every proposed row to exactly one lane.
2. Require the lane-specific benchmark group before discovery.
3. Require risk, execution, turnover, concentration, and duplication gates before discovery.
4. Do not reopen rejected rows or old GLD/GROR candidate_exhaustive state.
5. Do not allow candidate_exhaustive or paper-forward directly from discovery.
6. Prefer a pre-registered second expansion batch using this framework over ad hoc strategy expansion.

Exact next action: `{NEXT_ACTION}`
"""


def summary_md(manifest: dict[str, Any], failure_rows: list[dict[str, Any]]) -> str:
    return f"""# Tournament Lane Gate Framework

Created UTC: `{manifest['created_utc']}`

Governance-only: `{manifest['governance_only']}`

Lanes created: `{manifest['lane_count']}`

Failure reasons mapped: `{len(failure_rows)}`

## Main Design Decision

The framework keeps global risk discipline but makes benchmark, turnover, BIL allocation, trade-frequency, same-window, and contribution gates lane-specific. This addresses the root-cause audit finding that repeated research failures were driven by normal quant attrition plus lane/gate mismatch rather than a single strategy family or a clear backtester bug.

## Next Action

`{manifest['next_action']}`
"""


def consistency_check(
    manifest: dict[str, Any],
    output: Path,
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_files = [
        "tournament_lane_gate_manifest.json",
        "lane_gate_framework.yaml",
        "lane_gate_framework_summary.md",
        "lane_strategy_family_map.csv",
        "lane_benchmark_matrix.csv",
        "lane_risk_gate_matrix.csv",
        "lane_performance_gate_matrix.csv",
        "lane_execution_assumption_matrix.csv",
        "lane_promotion_rules.md",
        "lane_rejection_rules.md",
        "failure_reason_to_lane_recommendations.csv",
        "next_batch_selection_policy.md",
        "tournament_lane_gate_next_action.md",
    ]
    check = {
        "governance_only": manifest["governance_only"],
        "lane_gate_framework_created": manifest["lane_gate_framework_created"],
        "no_new_backtests": not manifest["new_backtests_run"],
        "no_new_discovery": not manifest["new_discovery_run"],
        "no_provider_download": not manifest["provider_download"],
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "five_lanes_defined": set(manifest["lane_ids"]) == set(LANE_IDS),
        "each_lane_has_benchmark_group": all(bool(LANES[lane_id]["benchmark_group"]) for lane_id in LANE_IDS),
        "each_lane_has_risk_gates": all(bool(LANES[lane_id]["risk_gates"]) for lane_id in LANE_IDS),
        "each_lane_has_performance_gates": all(bool(LANES[lane_id]["performance_gates"]) for lane_id in LANE_IDS),
        "each_lane_has_promotion_rejection_rules": all(bool(LANES[lane_id]["promotion_review_rules"]) and bool(LANES[lane_id]["rejection_rules"]) for lane_id in LANE_IDS),
        "intraday_lane_research_only": "Research-only" in " ".join(LANES["intraday_research_only_lane"]["demo_eligibility_rules"]),
        "macro_gld_lane_same_window_required": "same-window" in " ".join(LANES["macro_gld_duration_risk_off_lane"]["performance_gates"] + LANES["macro_gld_duration_risk_off_lane"]["benchmark_group"]),
        "diversifier_lane_marginal_contribution": "Marginal contribution" in " ".join(LANES["diversifier_contribution_lane"]["performance_gates"]),
        "moderate_tactical_lane_specific_trade_frequency": LANES["moderate_tactical_etf_lane"]["gate_decisions"]["max trades per week"] == "lane-specific",
        "conservative_lane_strict_drawdown_risk_buffer": "Strict drawdown gate." in LANES["conservative_etf_allocation_lane"]["risk_gates"] and "Strict risk buffer gate." in LANES["conservative_etf_allocation_lane"]["risk_gates"],
        "accepted_rejected_strategy_state_unchanged": strategies_before == strategies_after,
        "old_gld_gror_state_not_resumed": not manifest["old_gld_gror_state_resumed"],
        "required_files_created": all((output / name).exists() for name in required_files),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_tournament_lane_gate_framework(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    strategies_before = strategy_state_snapshot(root)

    framework = framework_yaml()
    family_rows = lane_strategy_family_rows()
    benchmark_rows = lane_benchmark_rows()
    risk_rows = lane_risk_gate_rows()
    performance_rows = lane_performance_gate_rows()
    execution_rows = lane_execution_rows()
    gate_rows = gate_decision_rows()
    failure_rows = failure_reason_rows(root)

    roadmap_updated = update_roadmap(root, output, created_utc)
    registry_updated = update_registry_metadata(root, output, created_utc)
    strategies_after = strategy_state_snapshot(root)

    manifest = {
        "artifact": "tournament_lane_gate_framework",
        "created_utc": created_utc,
        "output_dir": str(output),
        "lane_count": len(LANES),
        "lane_ids": LANE_IDS,
        "gate_count": len(GATES),
        "next_action": NEXT_ACTION,
        "roadmap_updated": roadmap_updated,
        "registry_metadata_updated": registry_updated,
        **MANIFEST_FLAGS,
    }

    (output / "lane_gate_framework.yaml").write_text(yaml.safe_dump(framework, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    write_json(output / "tournament_lane_gate_manifest.json", manifest)
    write_csv(output / "lane_strategy_family_map.csv", family_rows, ["lane_id", "purpose", "eligible_strategy_family", "demo_eligibility"])
    write_csv(output / "lane_benchmark_matrix.csv", benchmark_rows, ["lane_id", "benchmark", "same_window_required", "benchmark_role"])
    write_csv(output / "lane_risk_gate_matrix.csv", risk_rows, ["lane_id", "risk_gate", "gate_decision_context"])
    write_csv(output / "lane_performance_gate_matrix.csv", performance_rows, ["lane_id", "performance_gate", "gate_decision_context"])
    write_csv(output / "lane_execution_assumption_matrix.csv", execution_rows, ["lane_id", "execution_or_trade_frequency_rule", "paper_demo_eligibility"])
    write_csv(output / "lane_gate_decision_matrix.csv", gate_rows, ["lane_id", "gate", "decision"])
    write_csv(output / "failure_reason_to_lane_recommendations.csv", failure_rows, ["primary_failure_reason", "count", "lane_recommendation", "gate_framework_response"])
    (output / "lane_promotion_rules.md").write_text(promotion_rules_md(), encoding="utf-8")
    (output / "lane_rejection_rules.md").write_text(rejection_rules_md(), encoding="utf-8")
    (output / "next_batch_selection_policy.md").write_text(next_batch_policy_md(), encoding="utf-8")
    (output / "tournament_lane_gate_next_action.md").write_text(f"# Tournament Lane Gate Next Action\n\n`{NEXT_ACTION}`\n\nDo not run this next action from the governance framework task.\n", encoding="utf-8")
    (output / "lane_gate_framework_summary.md").write_text(summary_md(manifest, failure_rows), encoding="utf-8")

    consistency = consistency_check(manifest, output, strategies_before, strategies_after)
    write_json(output / "tournament_lane_gate_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "lane_ids": LANE_IDS,
        "next_action": NEXT_ACTION,
        "manifest": manifest,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_tournament_lane_gate_framework(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
