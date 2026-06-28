from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import run_active_strategy_evidence_recompute as active
import run_first_expansion_discovery_preregistration as first_prereg


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "sector_rs_limited_history" / "latest"
EXPANSION_REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
EXPANSION_ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"
FIRST_EXPANSION_DISCOVERY_DIR = Path("evidence") / "parallel_research_discovery" / "first_expansion_batch_without_sector_rs" / "latest"
MANUAL_PERIOD_REVIEW_DIR = Path("evidence") / "data_availability" / "first_expansion_batch" / "manual_period_review" / "latest"

CANDIDATE_ID = "sector_rs_weekly_cash_filter_v1"
LANE_ID = "sector_rs_limited_history"
LIMITED_HISTORY_LABEL = "limited_history_due_to_xlre_inception"
METHODOLOGY = "common_start_2016_after_xlre_sma_warmup"
NEXT_ACTION = "run_sector_rs_limited_history_discovery_batch"
VALID_FUTURE_OUTCOMES = ["discovery_reject", "promotion_review_candidate_limited_history"]
FORBIDDEN_FUTURE_OUTCOMES = ["candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"]
SECTOR_UNIVERSE = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"]
REQUIRED_DATA_SYMBOLS = [*SECTOR_UNIVERSE, "SPY"]
FIRST_EXPANSION_REJECT_IDS = [
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
]
INTRADAY_CANDIDATE_IDS = [
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
]
EVENT_DATA_CANDIDATE_IDS = ["post_earnings_drift_large_cap_later_v1"]

BENCHMARK_PLAN = [
    "active DSR over the same limited-history window",
    "active combo over the same limited-history window",
    "active VM over the same limited-history window",
    "SPY_200d over the same limited-history window",
    "SPY buy-and-hold over the same limited-history window",
    "QQQ buy-and-hold over the same limited-history window",
    "BIL cash proxy over the same limited-history window",
    "equal-weight sector baseline over the same limited-history window if available",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(path) for strategy_id, path in active.active_observation_paths(root).items()}


def clean_output_dir(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    root_resolved = root.resolve()
    if root_resolved not in output.parents:
        raise RuntimeError(f"refusing to clean output outside workspace: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.is_file():
            child.unlink()
    return output


def first_prereg_candidate(root: Path) -> dict[str, Any]:
    batch_path = root / first_prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
    batch = load_yaml(batch_path)
    for candidate in batch.get("candidates", []):
        if candidate.get("candidate_id") == CANDIDATE_ID:
            return deepcopy(candidate)
    registry = load_yaml(root / EXPANSION_REGISTRY_PATH)
    for candidate in registry.get("candidates", []):
        if candidate.get("candidate_id") == CANDIDATE_ID:
            return {
                "candidate_id": CANDIDATE_ID,
                "family": candidate.get("family", "sector_relative_strength_rotation"),
                "timeframe": candidate.get("timeframe", "weekly"),
                "universe": candidate.get("instruments", SECTOR_UNIVERSE),
                "data_required": candidate.get("data_required", []),
                "entry_rule": candidate.get("entry_rule", ""),
                "exit_rule": candidate.get("exit_rule", ""),
                "sizing_rule": candidate.get("sizing_rule", ""),
                "risk_controls": candidate.get("risk_controls", []),
                "max_position_size": candidate.get("max_position_size", "50% account notional per sector ETF"),
                "max_open_positions": candidate.get("max_open_positions", 2),
                "max_trades_per_day": candidate.get("max_trades_per_day", 2),
                "max_trades_per_week": candidate.get("max_trades_per_week", 4),
                "max_holding_period": candidate.get("max_holding_period", "Open-ended while weekly rules remain valid"),
                "execution_assumptions": candidate.get("execution_assumptions", []),
                "benchmark_controls": candidate.get("benchmark_controls", []),
                "acceptance_criteria": candidate.get("minimum_acceptance_criteria", []),
                "rejection_criteria": candidate.get("rejection_criteria", []),
                "duplication_checks": candidate.get("duplication_checks", []),
            }
    raise RuntimeError(f"{CANDIDATE_ID} not found in first expansion preregistration or expansion registry")


def xlre_context(root: Path) -> dict[str, Any]:
    compatibility_rows = read_csv_rows(root / MANUAL_PERIOD_REVIEW_DIR / "first_expansion_candidate_period_compatibility.csv")
    row = next((item for item in compatibility_rows if item.get("candidate_id") == CANDIDATE_ID), {})
    xlre_cache = root / "data" / "cache" / "XLRE.csv"
    first_cache_date = ""
    last_cache_date = ""
    if xlre_cache.exists():
        rows = read_csv_rows(xlre_cache)
        if rows:
            first_cache_date = rows[0].get("date", "")
            last_cache_date = rows[-1].get("date", "")
    return {
        "xlre_first_date": row.get("effective_all_symbols_start_date") or first_cache_date or "2015-10-08",
        "xlre_cache_first_date": first_cache_date or row.get("effective_all_symbols_start_date") or "2015-10-08",
        "xlre_cache_last_date": last_cache_date or row.get("common_last_date", ""),
        "common_history_years": row.get("common_history_years", ""),
        "full_2007_style_period_supported": row.get("full_2007_style_period_supported", "False"),
        "issue_classification": row.get("issue_classification", "period_inception_limitation"),
        "recommended_handling": row.get("recommended_handling", "defer_to_limited_history_preregistration"),
    }


def first_expansion_reject_status(root: Path) -> dict[str, str]:
    rows = read_csv_rows(root / FIRST_EXPANSION_DISCOVERY_DIR / "first_expansion_candidate_results.csv")
    return {row.get("candidate_id", ""): row.get("discovery_outcome", "") for row in rows}


def build_candidate_spec(source: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(source)
    candidate.update(
        {
            "candidate_id": CANDIDATE_ID,
            "family": "sector_relative_strength_rotation",
            "timeframe": "weekly",
            "universe": SECTOR_UNIVERSE,
            "limited_history_label": LIMITED_HISTORY_LABEL,
            "methodology": METHODOLOGY,
            "xlre_first_available_date": context["xlre_first_date"],
            "not_2007_style_full_history_test": True,
            "valid_future_outcomes": VALID_FUTURE_OUTCOMES,
            "forbidden_future_outcomes": FORBIDDEN_FUTURE_OUTCOMES,
            "future_discovery_outcome_limit": "discovery_reject_or_promotion_review_candidate_limited_history_only",
            "candidate_exhaustive_allowed_from_preregistration": False,
            "paper_forward_allowed_from_preregistration": False,
            "benchmark_plan": BENCHMARK_PLAN,
            "same_window_benchmark_recompute_required": True,
            "limited_history_visibility_required_in_all_evidence": True,
        }
    )
    candidate["entry_rule"] = (
        "At weekly rebalance, rank sectors by fixed 13-week momentum using prior completed data only, "
        "hold the top 2 sectors only if each is above its 200-day SMA and SPY is above its 200-day SMA, "
        "and allocate failed sleeves to BIL. No future data, optimized ranking window, alternate sector count, "
        "alternate SMA filter, or universe change is allowed."
    )
    candidate["exit_rule"] = (
        "At weekly rebalance or risk event, exit a sector if it falls below its 200-day SMA, leaves the top 2 ranking, "
        "SPY fails its 200-day SMA risk filter, or missing/stale data triggers exit or pause."
    )
    candidate["sizing_rule"] = "Allocate 50% to each accepted sector, send failed sleeves to BIL, cap each sector at 50%, and use no leverage, shorting, options, or futures."
    candidate["risk_controls"] = [
        "Max 2 sectors.",
        "Weekly rebalance only.",
        "BIL fallback.",
        "Turnover cap of one scheduled weekly rebalance.",
        "Drawdown pause after 6% strategy drawdown.",
        "Weekly loss pause after 3% weekly strategy loss.",
        "Liquidity filter required.",
        "Spread/slippage stress required in future discovery.",
        "Missing/stale data blocks new trades and can force exit or pause.",
        "Duplication check against active DSR and active combo.",
    ]
    candidate["benchmark_controls"] = BENCHMARK_PLAN
    candidate["acceptance_criteria"] = [
        "May become promotion_review_candidate_limited_history only if evidence is strong despite the shorter sample.",
        "Must beat active DSR and active combo over the same limited-history window or show unmistakable risk reduction with useful return.",
        "Must beat or materially risk-improve versus SPY_200d over the same limited-history window.",
        "Must pass risk buffer, slippage/spread stress, turnover, concentration, BIL allocation, and duplication gates.",
        "Cannot proceed directly to candidate_exhaustive or paper-forward.",
    ]
    candidate["rejection_criteria"] = [
        "Reject if it underperforms active DSR, active combo, or SPY_200d over the same limited-history window without meaningful risk reduction.",
        "Reject if drawdown, risk buffer, slippage/spread stress, or turnover is unacceptable.",
        "Reject if it is just an active DSR clone.",
        "Reject if results depend mainly on one sector, one short period, or excessive BIL allocation without enough benefit.",
        "Reject if limited-history evidence is weak, ambiguous, or not strong enough to justify promotion review.",
    ]
    candidate["data_required"] = [
        "Weekly rebalance derived from daily adjusted OHLCV.",
        "XLK, XLF, XLV, XLE, XLI, XLY, XLP, XLU, XLB, XLRE, and BIL.",
        "SPY for same-window risk filter.",
        "Benchmark/control data over the same limited-history window.",
        "No intraday data.",
        "No earnings or event data.",
        "No provider download in this pre-registration step.",
    ]
    return candidate


def batch_yaml(created_utc: str, candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {
            "lane_id": LANE_ID,
            "created_utc": created_utc,
            "pre_registration_only": True,
            "limited_history_due_to_xlre_inception": True,
            "candidate_id": CANDIDATE_ID,
            "included_candidate_ids": [CANDIDATE_ID],
            "methodology": METHODOLOGY,
            "limited_history_label": LIMITED_HISTORY_LABEL,
            "xlre_first_available_date": context["xlre_first_date"],
            "valid_future_outcomes": VALID_FUTURE_OUTCOMES,
            "next_action": NEXT_ACTION,
            "not_2007_style_full_history_test": True,
        },
        "candidates": [candidate],
    }


def markdown_candidate_spec(candidate: dict[str, Any], context: dict[str, Any]) -> str:
    return f"""# Sector RS Limited-History Candidate Spec

Candidate: `{CANDIDATE_ID}`

Label: `{LIMITED_HISTORY_LABEL}`

Methodology: `{METHODOLOGY}`

Universe: `{';'.join(SECTOR_UNIVERSE)}`

XLRE first available date: `{context['xlre_first_date']}`

This is not a 2007-style full-history test. `XLRE` remains in the universe and is not substituted.

## Frozen Rules

Entry: {candidate['entry_rule']}

Exit: {candidate['exit_rule']}

Sizing: {candidate['sizing_rule']}

Risk controls:

{chr(10).join(f'- {item}' for item in candidate['risk_controls'])}
"""


def methodology_md(context: dict[str, Any]) -> str:
    return f"""# Sector RS Limited-History Methodology

Selected methodology: `{METHODOLOGY}`

Rationale:

- `XLRE` starts on `{context['xlre_first_date']}` in the local cache context.
- The sector RS row requires momentum and 200-day SMA warmup.
- A clean common-start after XLRE warmup is more honest than pretending a full 2007-style comparison exists.
- Future discovery must label every result as limited-history.

The future discovery must recompute active VM, active DSR, active combo, SPY_200d, SPY, QQQ, BIL, and any equal-weight sector baseline over the same limited-history window. Full-history benchmark values may not be used against limited-history sector RS results.
"""


def benchmark_plan_md() -> str:
    return "# Sector RS Limited-History Benchmark Plan\n\n" + "\n".join(f"- {item}" for item in BENCHMARK_PLAN) + "\n"


def gates_md(title: str, items: list[str]) -> str:
    return f"# {title}\n\n" + "\n".join(f"- {item}" for item in items) + "\n"


def data_requirements_md(candidate: dict[str, Any]) -> str:
    return "# Sector RS Limited-History Data Requirements\n\n" + "\n".join(f"- {item}" for item in candidate["data_required"]) + "\n"


def do_not_run_md() -> str:
    return f"""# Do Not Run Now

This packet is pre-registration only.

Do not run `sector_rs_weekly_cash_filter_v1` discovery in this task. Do not run backtests, performance metrics, candidate_exhaustive, paper-forward review or activation, provider downloads, broker/live-order code, or real-money recommendations.

Valid future outcomes are only `{VALID_FUTURE_OUTCOMES[0]}` and `{VALID_FUTURE_OUTCOMES[1]}`.
"""


def next_action_md() -> str:
    return f"# Sector RS Limited-History Next Action\n\n`{NEXT_ACTION}`\n\nDo not run this next action from the pre-registration task.\n"


def update_metadata(root: Path, manifest: dict[str, Any]) -> None:
    registry_path = root / EXPANSION_REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("metadata", {})
    metadata.update(
        {
            "sector_rs_limited_history_preregistration_path": str((root / OUTPUT_DIR).resolve()),
            "sector_rs_limited_history_preregistration_status": "pre_registered",
            "sector_rs_limited_history_methodology": METHODOLOGY,
            "sector_rs_limited_history_label": LIMITED_HISTORY_LABEL,
            "sector_rs_limited_history_next_action": NEXT_ACTION,
            "sector_rs_limited_history_valid_future_outcomes": VALID_FUTURE_OUTCOMES,
            "pre_registration_only": True,
            "limited_history_due_to_xlre_inception": True,
            "backtests_run": False,
            "discovery_run": False,
            "performance_metrics_computed": False,
            "provider_download": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_path_touched": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "etf_wrapper_track_reopened": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / EXPANSION_ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Strategy Expansion Roadmap\n"
    marker = "## Sector RS Limited-History Pre-Registration"
    section = f"""## Sector RS Limited-History Pre-Registration

Created UTC: `{manifest['created_utc']}`

Candidate: `{CANDIDATE_ID}`

Limited-history label: `{LIMITED_HISTORY_LABEL}`

Methodology: `{METHODOLOGY}`

Reason: `XLRE` starts in 2015, so this row must not be treated as 2007-style/full-history comparable.

Valid future outcomes: `{', '.join(VALID_FUTURE_OUTCOMES)}`

Next action: `{NEXT_ACTION}`

No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, ETF-wrapper reopening, or real-money recommendation is authorized by this pre-registration.
"""
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def consistency_check(
    manifest: dict[str, Any],
    batch: dict[str, Any],
    first_rejects: dict[str, str],
    active_before: dict[str, str],
    active_after: dict[str, str],
    registry_before: dict[str, Any],
    registry_after: dict[str, Any],
) -> dict[str, Any]:
    included = batch["metadata"]["included_candidate_ids"]
    candidate = batch["candidates"][0]
    first_reject_status = {candidate_id: first_rejects.get(candidate_id, "") for candidate_id in FIRST_EXPANSION_REJECT_IDS}
    registry_before_status = registry_before.get("metadata", {}).get("etf_wrapper_track_status", "")
    registry_after_status = registry_after.get("metadata", {}).get("etf_wrapper_track_status", "")
    check = {
        "only_sector_rs_included": included == [CANDIDATE_ID],
        "first_expansion_rejects_remain_rejected": all(status == "discovery_reject" for status in first_reject_status.values()),
        "first_expansion_reject_status": first_reject_status,
        "no_first_expansion_rejected_row_reopened": not any(candidate_id in included for candidate_id in FIRST_EXPANSION_REJECT_IDS),
        "no_intraday_candidate_included": not any(candidate_id in included for candidate_id in INTRADAY_CANDIDATE_IDS),
        "no_event_data_candidate_included": not any(candidate_id in included for candidate_id in EVENT_DATA_CANDIDATE_IDS),
        "xlre_remains_in_universe": "XLRE" in candidate.get("universe", []),
        "limited_history_label_present": candidate.get("limited_history_label") == LIMITED_HISTORY_LABEL and manifest["limited_history_due_to_xlre_inception"],
        "same_window_benchmark_recompute_required": candidate.get("same_window_benchmark_recompute_required") is True,
        "no_strategy_results_computed": not manifest["backtests_run"] and not manifest["discovery_run"] and not manifest["performance_metrics_computed"],
        "no_paper_forward_state_changed": active_before == active_after and not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_broker_live_order_files_changed": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "etf_wrapper_track_remains_archived_stopped": registry_before_status == registry_after_status and "archived" in str(registry_after_status),
        "valid_future_outcomes_limited": manifest["valid_future_outcomes"] == VALID_FUTURE_OUTCOMES,
        "next_action_explicit": manifest["next_action"] == NEXT_ACTION,
    }
    check["consistency_passed"] = all(bool(value) for key, value in check.items() if key != "first_expansion_reject_status")
    return check


def run_sector_rs_limited_history_preregistration(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output_dir(root)
    created_utc = now_utc()
    registry_before = load_yaml(root / EXPANSION_REGISTRY_PATH)
    active_before = active_observation_hashes(root)
    source = first_prereg_candidate(root)
    source_before = deepcopy(source)
    context = xlre_context(root)
    first_rejects = first_expansion_reject_status(root)
    candidate = build_candidate_spec(source, context)
    batch = batch_yaml(created_utc, candidate, context)
    manifest = {
        "artifact": "sector_rs_limited_history_preregistration",
        "created_utc": created_utc,
        "output_dir": str(output),
        "pre_registration_only": True,
        "limited_history_due_to_xlre_inception": True,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "methodology": METHODOLOGY,
        "candidate_id": CANDIDATE_ID,
        "included_candidate_ids": [CANDIDATE_ID],
        "xlre_first_available_date": context["xlre_first_date"],
        "backtests_run": False,
        "discovery_run": False,
        "performance_metrics_computed": False,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "frozen_rules_changed": False,
        "candidate_universe_changed": False,
        "benchmarks_changed": False,
        "active_strategy_state_changed": False,
        "etf_wrapper_track_reopened": False,
        "valid_future_outcomes": VALID_FUTURE_OUTCOMES,
        "forbidden_future_outcomes": FORBIDDEN_FUTURE_OUTCOMES,
        "next_action": NEXT_ACTION,
        "first_expansion_rejected_candidate_ids": FIRST_EXPANSION_REJECT_IDS,
        "not_2007_style_full_history_test": True,
        "same_window_benchmark_recompute_required": True,
    }

    update_metadata(root, manifest)
    registry_after = load_yaml(root / EXPANSION_REGISTRY_PATH)
    active_after = active_observation_hashes(root)
    source_after = first_prereg_candidate(root)
    manifest["frozen_rules_changed"] = source_before != source_after
    manifest["candidate_universe_changed"] = source_before.get("universe") != source_after.get("universe")
    manifest["benchmarks_changed"] = source_before.get("benchmark_controls") != source_after.get("benchmark_controls")
    manifest["active_strategy_state_changed"] = active_before != active_after

    write_json(output / "sector_rs_limited_history_manifest.json", manifest)
    (output / "sector_rs_limited_history_batch.yaml").write_text(yaml.safe_dump(batch, sort_keys=False, width=120), encoding="utf-8")
    (output / "sector_rs_limited_history_candidate_spec.md").write_text(markdown_candidate_spec(candidate, context), encoding="utf-8")
    (output / "sector_rs_limited_history_methodology.md").write_text(methodology_md(context), encoding="utf-8")
    (output / "sector_rs_limited_history_benchmark_plan.md").write_text(benchmark_plan_md(), encoding="utf-8")
    (output / "sector_rs_limited_history_acceptance_gates.md").write_text(gates_md("Sector RS Limited-History Acceptance Gates", candidate["acceptance_criteria"]), encoding="utf-8")
    (output / "sector_rs_limited_history_rejection_gates.md").write_text(gates_md("Sector RS Limited-History Rejection Gates", candidate["rejection_criteria"]), encoding="utf-8")
    (output / "sector_rs_limited_history_data_requirements.md").write_text(data_requirements_md(candidate), encoding="utf-8")
    (output / "sector_rs_limited_history_do_not_run_now.md").write_text(do_not_run_md(), encoding="utf-8")
    (output / "sector_rs_limited_history_next_action.md").write_text(next_action_md(), encoding="utf-8")
    consistency = consistency_check(manifest, batch, first_rejects, active_before, active_after, registry_before, registry_after)
    write_json(output / "sector_rs_limited_history_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "methodology": METHODOLOGY,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "next_action": NEXT_ACTION,
        "manifest": manifest,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_sector_rs_limited_history_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
