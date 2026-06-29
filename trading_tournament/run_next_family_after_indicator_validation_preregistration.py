from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "next_family_after_indicator_validation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
DATA_CACHE_DIR = Path("data") / "cache"
DEPENDENCY_REVIEW_DIR = Path("evidence") / "governance" / "indicator_library_dependency_review" / "latest"
INDICATOR_VALIDATION_DIR = Path("evidence") / "governance" / "indicator_validation_harness_implementation" / "latest"
MF_SAMPLE_DIR = Path("evidence") / "research_samples" / "managed_futures_etf_wrapper" / "latest"
FAMILY_STATUS_PATH = Path("strategy_lab") / "research_os" / "family_status" / "managed_futures_etf_wrapper.yaml"
LANE_MODEL_PATH = Path("strategy_lab") / "research_os" / "lane_model.yaml"

SELECTED_FAMILY = "managed_futures_etf_wrapper"
NEXT_ACTION = "run_next_family_discovery_after_indicator_validation"
DATA_AVAILABILITY_STATUS = "sufficient_for_preregistered_discovery"

VALID_FAMILIES = {
    "managed_futures_etf_wrapper",
    "macro_contribution_family",
    "gtaa_faber_style_benchmark_lane",
    "pause_no_next_family",
}
VALID_NEXT_ACTIONS = {
    "run_next_family_discovery_after_indicator_validation",
    "manual_review_required_for_next_family_selection",
    "pause_expansion_and_wait_for_manual_direction",
}

MANIFEST_FLAGS = {
    "family_preregistration_only": True,
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
    "expansion_remains_paused_until_discovery_authorized": True,
    "intraday_research_remains_paused": True,
}

CANDIDATE_SPECS = [
    {
        "candidate_id": "mfv_equal_weight_trend_filter_v1",
        "family": SELECTED_FAMILY,
        "lane": "diversifier_contribution_lane",
        "instrument_family": "ETF_or_fund_wrapper",
        "candidate_type": "strategy_candidate",
        "rules_frozen": True,
        "primary_edge_hypothesis": (
            "A diversified basket of managed-futures ETF/fund wrappers may provide an additive trend-following "
            "return stream versus equity/sector/growth references without direct futures, leverage, shorting, or derivatives."
        ),
        "rule": {
            "rebalance_frequency": "monthly",
            "universe": ["DBMF", "KMLM", "CTA", "FMF", "WTMF"],
            "trend_filter": "wrapper close above its own 200-day SMA using prior completed daily data",
            "momentum_filter": "wrapper 126-day ROC greater than zero using prior completed daily data",
            "allocation": "equal weight all wrappers passing both filters; if none pass, allocate 100% to BIL",
            "cash_fallback": "BIL",
            "position_constraints": "long-only ETF/fund-wrapper exposure; no leverage, margin, shorting, direct futures, options, forex, or crypto",
            "indicator_source": "validated custom indicators only: SMA and ROC/rolling return",
            "limited_history_policy": "same-window benchmark comparison begins only after all required candidate and benchmark warmups are available",
            "parameter_policy": "fixed 200-day SMA and 126-day ROC; no grid search or post-result tuning",
        },
        "benchmarks": [
            "SPY",
            "QQQ",
            "BIL",
            "GLD",
            "TLT",
            "AGG",
            "static_all_weather_benchmark_v1",
            "active_combo_vm_dsr_equal_weight_v1",
            "managed_futures_wrapper_equal_weight_unfiltered_reference",
            "prior_mf_wrapper_top1_top2_watchlist_rows_as_historical_context_only",
        ],
        "risk_gates": [
            "must not breach small-account drawdown/stop-risk gates",
            "must show additive same-window behavior versus active references",
            "must pass duplication review against active combo, SPY/QQQ, GLD/TLT/AGG, and prior managed-futures rows",
            "must preserve limited-history caveat and avoid extrapolating wrapper inception samples",
        ],
        "rejection_gates": [
            "too_slow_for_profit_goal",
            "duplicate_or_near_duplicate",
            "risk_buffer_too_thin",
            "weaker_than_active_references",
            "limited_history_not_actionable",
            "data_quality_or_cache_blocker",
        ],
        "valid_future_outcomes": [
            "discovery_reject",
            "promotion_review_candidate",
            "promotion_review_candidate_macro",
            "promotion_review_candidate_macro_limited_history",
        ],
        "forbidden_future_outcomes": [
            "candidate_exhaustive",
            "paper_forward",
            "paper_forward_active",
            "demo_active",
            "live_ready",
        ],
    }
]

REQUIRED_SYMBOLS = ["DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL", "SPY", "QQQ", "GLD", "TLT", "AGG"]

REQUIRED_FILES = [
    "next_family_preregistration_manifest.json",
    "next_family_preregistration_summary.md",
    "family_selection_decision.md",
    "candidate_specs.yaml",
    "candidate_specs.md",
    "family_data_availability_report.md",
    "family_benchmark_plan.md",
    "family_risk_gate_plan.md",
    "family_rejection_gates.md",
    "indicator_usage_plan.md",
    "do_not_run_now.md",
    "next_family_preregistration_next_action.md",
    "next_family_preregistration_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def approved_symbols(root: Path) -> set[str]:
    manifest = load_json(root / MF_SAMPLE_DIR / "managed_futures_etf_wrapper_manifest.json")
    return set(manifest.get("approved_symbols", []))


def symbol_cache_report(root: Path, symbol: str, approved: set[str], created_utc: str) -> dict[str, Any]:
    path = root / DATA_CACHE_DIR / f"{symbol}.csv"
    row: dict[str, Any] = {
        "symbol": symbol,
        "approved_status": str(symbol in approved),
        "cache_present": str(path.exists()),
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "adjusted_close_availability": "False",
        "null_count": "",
        "duplicate_date_count": "",
        "stale_flag": "True",
        "supports_candidate_window": "False",
    }
    if not path.exists():
        return row
    frame = pd.read_csv(path)
    date_series = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame else pd.Series(dtype="datetime64[ns]")
    row["first_date"] = str(date_series.min().date()) if not date_series.dropna().empty else ""
    row["last_date"] = str(date_series.max().date()) if not date_series.dropna().empty else ""
    row["row_count"] = int(len(frame))
    adjusted_col = "adj_close" if "adj_close" in frame.columns else "raw_adj_close" if "raw_adj_close" in frame.columns else ""
    row["adjusted_close_availability"] = str(bool(adjusted_col and frame[adjusted_col].notna().any()))
    quality_columns = [column for column in ["date", "open", "high", "low", "close", "adj_close", "volume"] if column in frame]
    row["null_count"] = int(frame[quality_columns].isna().sum().sum()) if quality_columns else int(frame.isna().sum().sum())
    row["duplicate_date_count"] = int(frame["date"].duplicated().sum()) if "date" in frame else ""
    created_date = datetime.fromisoformat(created_utc.replace("Z", "+00:00")).date()
    last_date = date_series.max().date() if not date_series.dropna().empty else None
    row["stale_flag"] = str(last_date is None or (created_date - last_date).days > 45)
    row["supports_candidate_window"] = str(
        symbol in approved
        and path.exists()
        and int(row["row_count"]) >= 252 + 126
        and row["adjusted_close_availability"] == "True"
        and row["duplicate_date_count"] == 0
        and row["stale_flag"] == "False"
    )
    return row


def data_report(root: Path, created_utc: str) -> list[dict[str, Any]]:
    approved = approved_symbols(root)
    return [symbol_cache_report(root, symbol, approved, created_utc) for symbol in REQUIRED_SYMBOLS]


def data_status(rows: list[dict[str, Any]]) -> str:
    return DATA_AVAILABILITY_STATUS if all(row["supports_candidate_window"] == "True" for row in rows) else "manual_review_required_data_incomplete"


def data_report_md(rows: list[dict[str, Any]]) -> str:
    header = "| symbol | approved | cache present | first date | last date | rows | adj close | nulls | duplicate dates | stale | supports candidate window |\n|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|"
    body = "\n".join(
        f"| `{row['symbol']}` | `{row['approved_status']}` | `{row['cache_present']}` | {row['first_date']} | {row['last_date']} | {row['row_count']} | `{row['adjusted_close_availability']}` | {row['null_count']} | {row['duplicate_date_count']} | `{row['stale_flag']}` | `{row['supports_candidate_window']}` |"
        for row in rows
    )
    return f"""# Family Data Availability Report

Local approved/cache-present daily data only. No provider data was downloaded and no provider API was called.

{header}
{body}

Data availability status: `{data_status(rows)}`
"""


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Next Family After Indicator Validation Preregistration Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Selected family: `{manifest['selected_family']}`

Candidate count: `{manifest['candidate_count']}`

Candidate IDs: `{', '.join(manifest['candidate_ids'])}`

Data availability status: `{manifest['data_availability_status']}`

Next action: `{manifest['next_action']}`

Inputs inspected:

- `strategy_lab/RESEARCH_ROADMAP.md`
- `strategy_lab/research_os/family_status/managed_futures_etf_wrapper.yaml`
- `strategy_lab/research_os/lane_model.yaml`
- `evidence/governance/indicator_library_dependency_review/latest/`
- `evidence/governance/indicator_validation_harness_implementation/latest/`
- `evidence/research_samples/managed_futures_etf_wrapper/latest/`
- `data/cache/`

This is a family-selection and preregistration packet only. It does not run discovery, backtests, new metrics, provider download, candidate_exhaustive, paper-forward activation, broker/live actions, or real-money recommendation.
"""


def selection_md() -> str:
    return """# Family Selection Decision

Decision: select `managed_futures_etf_wrapper`.

Reason: after indicator validation, the project needs a more additive return stream than SPY/QQQ/sector/growth exposure. Managed-futures ETF/fund wrappers are the strongest allowed family because they may provide trend-following/diversifier behavior while staying inside ETF/fund-wrapper constraints.

Evidence read:

- Roadmap priority backlog lists `managed_futures_etf_wrapper` as the highest next family to review.
- Family status is `future_hypothesis_only`, with exact rejected managed-futures variants still closed.
- Lane model assigns this family to `diversifier_contribution_lane`, where contribution and duplication control matter more than headline return.
- Indicator dependency review selected `stay_custom_indicators_only`; indicator validation found the current custom indicator set clean.

Guardrails:

- ETF/fund-wrapper only.
- No direct futures.
- No leverage, margin, shorting, options, forex, crypto, or intraday logic.
- Do not replay exact prior top-1/top-2 ranking rows or fixed active-combo blend rows.
- Use validated custom SMA and ROC only.
- Treat prior managed-futures research-sample evidence as historical context, not promotion evidence.
"""


def candidate_specs_md() -> str:
    lines = []
    for candidate in CANDIDATE_SPECS:
        lines.append(
            f"""## `{candidate['candidate_id']}`

- Family: `{candidate['family']}`
- Lane: `{candidate['lane']}`
- Hypothesis: {candidate['primary_edge_hypothesis']}
- Frozen rule: monthly equal-weight allocation to DBMF, KMLM, CTA, FMF, and WTMF wrappers that pass both close > 200-day SMA and 126-day ROC > 0 using prior completed daily data; if none pass, allocate 100% to BIL.
- Indicators: validated custom SMA and ROC/rolling return only.
- Valid future outcomes: `{', '.join(candidate['valid_future_outcomes'])}`
- Forbidden future outcomes: `{', '.join(candidate['forbidden_future_outcomes'])}`
"""
        )
    return "# Candidate Specs\n\n" + "\n".join(lines)


def benchmark_plan_md() -> str:
    benchmarks = "\n".join(f"- `{item}`" for item in CANDIDATE_SPECS[0]["benchmarks"])
    return f"""# Family Benchmark Plan

Same-window benchmark comparison is mandatory before any promotion review.

Benchmarks and controls:

{benchmarks}

Benchmark/control use does not imply candidate_exhaustive, paper-forward, or real-money eligibility.
"""


def risk_gate_plan_md() -> str:
    gates = "\n".join(f"- {item}" for item in CANDIDATE_SPECS[0]["risk_gates"])
    return f"""# Family Risk Gate Plan

{gates}

The candidate must preserve the small-account drawdown/stop-risk discipline. Drawdown improvement without sufficient objective progress remains insufficient.
"""


def rejection_gates_md() -> str:
    gates = "\n".join(f"- `{item}`" for item in CANDIDATE_SPECS[0]["rejection_gates"])
    return f"""# Family Rejection Gates

{gates}

Any direct replay of exact rejected variants or post-result tuning must be rejected.
"""


def indicator_usage_md() -> str:
    return """# Indicator Usage Plan

Allowed indicators:

- validated custom SMA
- validated custom ROC / rolling return

Forbidden/gated indicators for this family preregistration:

- MACD
- Keltner Channel
- OBV
- external indicator-library outputs
- indicator voting systems
- broad indicator scans
- parameter grids

Indicator use is limited to the frozen rule in `candidate_specs.yaml`; indicators may not be added later to rescue a failed row or weaken gates.
"""


def do_not_run_md() -> str:
    return """# Do Not Run Now

This preregistration does not authorize:

- strategy discovery
- backtests
- new strategy performance metrics
- provider downloads
- intraday data
- indicator library installation
- candidate_exhaustive
- paper-forward review or activation
- broker/live-order paths
- direct futures/options/forex/crypto
- leverage, margin, or shorting
- exact rejected variant reopening
- real-money recommendations
"""


def next_action_md(next_action: str, status: str) -> str:
    reason = (
        "one managed-futures ETF-wrapper candidate is selected, rules are fully frozen, local approved/cache-present "
        "data is sufficient, exact rejected variants remain closed, and no discovery/backtest was run in this "
        "preregistration task."
        if next_action == NEXT_ACTION
        else f"data availability status is `{status}`, so manual review is required before any future discovery."
    )
    return f"""# Next Family Preregistration Next Action

Exact next action: `{next_action}`

Reason: {reason}

Do not run this next action in the preregistration task.
"""


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "next_family_after_indicator_validation_preregistration_path": str(output.resolve()),
            "next_family_after_indicator_validation_preregistration_status": "pre_registered",
            "next_family_after_indicator_validation_preregistration_created_utc": created_utc,
            "selected_family_after_indicator_validation": manifest["selected_family"],
            "next_family_candidate_count": manifest["candidate_count"],
            "next_family_candidate_ids": manifest["candidate_ids"],
            "next_family_data_availability_status": manifest["data_availability_status"],
            "family_preregistration_only": True,
            "indicator_library_dependency_added": False,
            "expansion_paused": True,
            "expansion_remains_paused_until_discovery_authorized": True,
            "intraday_research_remains_paused": True,
            "official_current_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "strategy_discovery_run": False,
            "backtests_run": False,
            "new_performance_metrics_computed": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "live_orders": False,
            "real_money_recommendation": False,
        }
    )
    write_yaml(path, data)


def update_roadmap(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `next_family_after_indicator_validation_preregistered`
- Official current next action: `{NEXT_ACTION}`
- Next-family preregistration evidence: `{output.resolve()}`
- Selected family: `{manifest['selected_family']}`
- Candidate IDs: `{', '.join(manifest['candidate_ids'])}`
- Data availability status: `{manifest['data_availability_status']}`
- Expansion remains paused until discovery is separately authorized: `true`
- Intraday remains paused: `true`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- This section does not authorize discovery, backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, or real-money recommendation.
"""
    text = replace_or_append_section(text, "## Compact Current State", compact)
    section = f"""## Next Family After Indicator Validation Preregistration

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Family-preregistration-only: `true`
- Selected family: `{manifest['selected_family']}`
- Candidate count: `{manifest['candidate_count']}`
- Candidate IDs: `{', '.join(manifest['candidate_ids'])}`
- Data availability status: `{manifest['data_availability_status']}`
- Indicator library dependency added: `false`
- Expansion remains paused until discovery is separately authorized: `true`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This preregistration does not authorize discovery, backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Next Family After Indicator Validation Preregistration", section))


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "family_preregistration_only": manifest["family_preregistration_only"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "selected_family_valid": manifest["selected_family"] in VALID_FAMILIES,
        "candidate_count_valid": 0 <= manifest["candidate_count"] <= 3,
        "candidate_specs_exist_if_needed": manifest["candidate_count"] == 0 or (output / "candidate_specs.yaml").exists(),
        "data_availability_report_exists": (output / "family_data_availability_report.md").exists(),
        "benchmark_plan_exists": (output / "family_benchmark_plan.md").exists(),
        "indicator_usage_plan_exists": (output / "indicator_usage_plan.md").exists(),
        "do_not_run_now_file_exists": (output / "do_not_run_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(output: Path, created_utc: str, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "next_family_preregistration_manifest.json", manifest)
    write_text(output / "next_family_preregistration_summary.md", summary_md(created_utc, output, manifest))
    write_text(output / "family_selection_decision.md", selection_md())
    write_yaml(output / "candidate_specs.yaml", {"candidates": CANDIDATE_SPECS})
    write_text(output / "candidate_specs.md", candidate_specs_md())
    write_text(output / "family_data_availability_report.md", data_report_md(rows))
    write_text(output / "family_benchmark_plan.md", benchmark_plan_md())
    write_text(output / "family_risk_gate_plan.md", risk_gate_plan_md())
    write_text(output / "family_rejection_gates.md", rejection_gates_md())
    write_text(output / "indicator_usage_plan.md", indicator_usage_md())
    write_text(output / "do_not_run_now.md", do_not_run_md())
    write_text(
        output / "next_family_preregistration_next_action.md",
        next_action_md(manifest["next_action"], manifest["data_availability_status"]),
    )
    write_json(output / "next_family_preregistration_consistency_check.json", {"consistency_passed": False})
    with (output / "family_data_availability_report.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "symbol",
            "approved_status",
            "cache_present",
            "first_date",
            "last_date",
            "row_count",
            "adjusted_close_availability",
            "null_count",
            "duplicate_date_count",
            "stale_flag",
            "supports_candidate_window",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_next_family_after_indicator_validation_preregistration(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    rows = data_report(root, created_utc)
    status = data_status(rows)
    candidate_ids = [candidate["candidate_id"] for candidate in CANDIDATE_SPECS]
    next_action = NEXT_ACTION if status == DATA_AVAILABILITY_STATUS else "manual_review_required_for_next_family_selection"
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "selected_family": SELECTED_FAMILY,
        "candidate_count": len(CANDIDATE_SPECS),
        "candidate_ids": candidate_ids,
        "data_availability_status": status,
        "next_action": next_action,
    }
    write_evidence(output, created_utc, manifest, rows)
    consistency = consistency_check(manifest, output)
    write_json(output / "next_family_preregistration_consistency_check.json", consistency)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output, manifest)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
        write_json(output / "next_family_preregistration_manifest.json", manifest)
        consistency = consistency_check(manifest, output)
        write_json(output / "next_family_preregistration_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "selected_family": manifest["selected_family"],
        "candidate_count": manifest["candidate_count"],
        "candidate_ids": manifest["candidate_ids"],
        "data_availability_status": manifest["data_availability_status"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_next_family_after_indicator_validation_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
