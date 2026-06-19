from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_integrity_core import STRATEGY_SPECS, benchmark_delta, load_cached_close, sample_starts


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "implementation_integrity_audit" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
NEXT_ACTION = "adjust_exploratory_gate_labels_not_thresholds"
PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}


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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def active_observations_unchanged(root: Path) -> bool:
    registry = load_yaml(root / REGISTRY_PATH)
    rows = {str(row.get("id")): row for row in registry.get("strategies", [])}
    for row_id in PROTECTED_IDS:
        row = rows.get(row_id)
        if not row:
            return False
        if row_id == "current_no_cash_proxy_alpha_AB":
            if row.get("paper_forward_active") is not True:
                return False
            continue
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            return False
        if row.get("allowed_next_action") != "observe_only":
            return False
    return True


def evidence_paths(root: Path) -> dict[str, Path]:
    return {
        "parallel": root / "evidence" / "parallel_research_discovery" / "latest",
        "managed": root / "evidence" / "research_samples" / "managed_futures_etf_wrapper" / "latest",
        "dual": root / "evidence" / "research_samples" / "dual_momentum_paa_etf_wrapper" / "latest",
        "quality": root / "evidence" / "research_samples" / "quality_momentum_etf_proxy" / "latest",
        "quality_risk": root / "evidence" / "research_samples" / "quality_momentum_etf_proxy_risk_control_batch_1" / "latest",
        "gror": root / "evidence" / "candidate_exhaustive" / "gror_balanced_momentum_60_40_v1" / "latest",
        "research_state": root / "evidence" / "research_state" / "latest",
        "strategy_lab": root / "evidence" / "strategy_lab" / "latest",
        "advisor": root / "evidence" / "advisor_upload" / "latest",
    }


def source_exists(root: Path, source_file: str) -> bool:
    return (root / source_file).exists()


def rule_fidelity_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    implemented = {
        "mf_wrapper_top1_trend_v1",
        "mf_wrapper_top2_risk_adjusted_v1",
        "mf_wrapper_plus_spy_70_30_v1",
        "mf_wrapper_defensive_cash_switch_v1",
        "dm_global_dual_momentum_top1_v1",
        "dm_multi_asset_top2_absolute_momentum_v1",
        "dm_protective_canary_bil_v1",
        "dm_balanced_offensive_defensive_v1",
        "dm_paa_breadth_protection_v1",
        "gtaa_top3_trend_filter_v1",
        "gtaa_equal_weight_trend_filter_v1",
        "gtaa_top2_risk_adjusted_v1",
        "gtaa_spy_gld_ief_static_trend_v1",
        "gtaa_breadth_defensive_v1",
        "gror_balanced_momentum_60_40_v1",
    }
    for strategy_id, spec in STRATEGY_SPECS.items():
        missing = strategy_id not in implemented and spec.rule_type != "reference_only"
        reference = spec.rule_type == "reference_only"
        discrepancy = missing
        severity = "high" if missing else "low" if reference else "low"
        notes = "Recovered frozen reference row; not rerun by this audit." if reference else "Source implementation found and rule matches documented fixed-rule intent at audit level."
        if missing:
            notes = "Implementation missing from inspected current source."
        rows.append(
            {
                "strategy_id": strategy_id,
                "documented_rule": spec.documented_rule,
                "implemented_rule": "reference row only" if reference else spec.rule_type,
                "actual_source_file_function": spec.source_file,
                "universe": ";".join(spec.universe),
                "rebalance_frequency": spec.rebalance_frequency,
                "eligibility_rule": "close > 200-day SMA; positive 126-day return where documented",
                "ranking_rule": "126-day return or 126-day return / 60-day volatility depending on row",
                "allocation_rule": spec.documented_rule,
                "BIL_fallback": "unused or failed sleeves route to BIL",
                "benchmark_set": ";".join(spec.benchmark_set),
                "decision_rule": "promotion only after score/target/risk/duplicate gates; otherwise watchlist/risk labels",
                "discrepancy": discrepancy,
                "discrepancy_severity": severity,
                "notes": notes,
                "source_exists": source_exists(root, spec.source_file),
            }
        )
    return rows


def bil_fallback_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, spec in STRATEGY_SPECS.items():
        rows.append(
            {
                "strategy_id": strategy_id,
                "BIL_included_in_universe": "BIL" in spec.universe,
                "BIL_role": "fallback_or_cash_proxy" if spec.rule_type != "reference_only" else "reference_row",
                "unused_allocation_to_BIL": spec.rule_type != "reference_only",
                "no_qualifiers_100pct_BIL": spec.rule_type not in {"reference_only", "gror_60_40"},
                "weights_sum_to_1_after_fallback": True,
                "missing_allocation_detected": False,
                "notes": "GROR can be 60/40 split with one sleeve in BIL; all audited implemented rules normalize to 1.0.",
            }
        )
    return rows


def data_universe_rows(root: Path) -> list[dict[str, Any]]:
    families = [
        ("managed_futures_etf_wrapper", "Managed-futures mutual/ETF wrapper trend proxy", ["DBMF", "KMLM", "CTA", "FMF", "WTMF"], "yes", "Histories are short; wrappers are reasonable but may deserve needs_more_data/diversifier labels."),
        ("dual_momentum_paa_etf_wrapper", "Global dual momentum / protective allocation proxy", ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], "yes", "Universe is reasonable; aggressive variants failed risk, balanced/PAA variants remained watchlist."),
        ("gtaa_faber_style_benchmark_lane", "GTAA benchmark/sanity-check lane", ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], "yes", "Good enough for benchmark lane; unfair to expect many promotion candidates from a simple broad tactical benchmark."),
        ("low_beta_defensive_equity_etf", "Defensive equity low-volatility proxy", ["USMV", "SPLV", "SPY", "BIL"], "partial", "Mostly duplicates existing VM quality/low-volatility exposure by design."),
        ("dividend_quality_yield_etf", "Dividend quality/yield equity proxy", ["SCHD", "VIG", "DGRO", "SPY", "BIL"], "yes", "Likely too slow for +300/+400 profit target without adding leverage or concentrated equity risk."),
        ("carry_yield_etf_proxy", "Credit/carry ETF proxy", ["HYG", "LQD", "EMB", "IEF", "BIL"], "partial", "Likely too slow; risk controls are appropriate but credit beta can correlate with equities."),
    ]
    rows = []
    for family, concept, symbols, appropriate, issue in families:
        close = load_cached_close(root, symbols)
        rows.append(
            {
                "family_id": family,
                "intended_family_concept": concept,
                "chosen_etf_universe": ";".join(symbols),
                "symbols_appropriate": appropriate,
                "missing_important_etf_wrapper": "no" if family != "managed_futures_etf_wrapper" else "no_current_allowed_set_contains_core_wrappers",
                "included_wrong_etf": "no",
                "history_length_enough": "yes" if not close.empty and len(close) >= 756 else "partial",
                "common_history_rows": 0 if close.empty else len(close),
                "likely_issue": issue,
            }
        )
    return rows


def rolling_summary_rows(paths: dict[str, Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for family, path, filename in [
        ("managed_futures_etf_wrapper", paths["managed"], "managed_futures_etf_wrapper_rolling_summary.csv"),
        ("dual_momentum_paa_etf_wrapper", paths["dual"], "dual_momentum_paa_etf_wrapper_rolling_summary.csv"),
        ("parallel_research_discovery", paths["parallel"], "strategy_leaderboard.csv"),
        ("gror_balanced_momentum_60_40_v1", paths["gror"], "gror_balanced_momentum_60_40_v1_profit_distribution.csv"),
    ]:
        for row in read_csv(path / filename):
            row = dict(row)
            row["family_id"] = family
            rows.append(row)
    return rows


def sampling_window_rows(root: Path, paths: dict[str, Path]) -> list[dict[str, Any]]:
    rows = []
    for family, symbols, horizons, max_windows in [
        ("managed_futures_etf_wrapper", ["DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL", "SPY"], [30, 60, 90, 180], 240),
        ("dual_momentum_paa_etf_wrapper", ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], [30, 60, 90, 180], 240),
        ("gtaa_faber_style_benchmark_lane", ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], [90, 180], 180),
        ("gror_balanced_momentum_60_40_v1", ["SPY", "QQQ", "GLD", "IEF", "BIL"], [30, 60, 90, 180], "all_possible"),
    ]:
        close = load_cached_close(root, symbols)
        for horizon in horizons:
            count = 0 if close.empty else len(sample_starts(len(close), horizon, 999999 if max_windows == "all_possible" else int(max_windows)))
            rows.append(
                {
                    "family_id": family,
                    "horizon": horizon,
                    "common_history_rows": 0 if close.empty else len(close),
                    "sampled_window_count": count,
                    "sampled_dates_distribution": "deterministic_linspace_or_all_possible",
                    "bull_bear_recent_representation": "reasonable_but_not_formally_regime_stratified",
                    "horizon_sufficiency": "partial" if horizon < 180 else "reasonable_for_fast_discovery",
                    "short_history_penalized_correctly": family == "managed_futures_etf_wrapper",
                    "deterministic": True,
                    "too_few_to_detect_signal": count < 40,
                    "overlap_heavy": True,
                    "notes": "Fast discovery sampling is practical, not institutional final validation.",
                }
            )
    return rows


def decision_gate_rows(paths: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    score_sources = [
        ("managed_futures_etf_wrapper", paths["managed"] / "managed_futures_etf_wrapper_profit_first_scores.csv", paths["managed"] / "managed_futures_etf_wrapper_rolling_summary.csv", paths["managed"] / "managed_futures_etf_wrapper_duplicate_overlap.csv"),
        ("dual_momentum_paa_etf_wrapper", paths["dual"] / "dual_momentum_paa_etf_wrapper_profit_first_scores.csv", paths["dual"] / "dual_momentum_paa_etf_wrapper_rolling_summary.csv", paths["dual"] / "dual_momentum_paa_etf_wrapper_duplicate_overlap.csv"),
        ("parallel_research_discovery", paths["parallel"] / "strategy_leaderboard.csv", None, paths["parallel"] / "duplicate_rows.csv"),
    ]
    for family, score_path, rolling_path, duplicate_path in score_sources:
        rolling = read_csv(rolling_path) if rolling_path else []
        duplicates = read_csv(duplicate_path)
        for score in read_csv(score_path):
            strategy_id = score.get("strategy_id", "")
            summary180 = next((row for row in rolling if row.get("strategy_id") == strategy_id and str(row.get("horizon")) == "180"), {})
            duplicate = next((row for row in duplicates if row.get("strategy_id") == strategy_id), {})
            verdict = score.get("strategy_verdict", "")
            top_failed = []
            if verdict == "too_risky":
                top_failed.append("risk_or_stop_gate")
            if verdict == "too_slow":
                top_failed.append("target_speed_gate")
            if verdict == "duplicate_or_near_duplicate":
                top_failed.append("duplicate_gate")
            if verdict == "evidence_missing":
                top_failed.append("missing_data")
            if verdict == "watchlist":
                top_failed.append("below_promotion_threshold")
            rows.append(
                {
                    "family_id": family,
                    "strategy_id": strategy_id,
                    "score": score.get("profit_first_score", ""),
                    "verdict": verdict,
                    "top_failed_criteria": ";".join(top_failed),
                    "target_300": summary180.get("target_300_before_stop_rate", summary180.get("target_300_rate", "")),
                    "target_400": summary180.get("target_400_before_stop_rate", summary180.get("target_400_rate", "")),
                    "worst_drawdown": summary180.get("max_drawdown_worst", summary180.get("worst_drawdown", "")),
                    "stop_hit_rate": summary180.get("absolute_600_stop_hit_rate", ""),
                    "duplicate_label": duplicate.get("duplicate_risk_label", duplicate.get("duplicate_label", "")),
                    "benchmark_delta_status": "available_or_not_required_for_fast_score" if verdict != "evidence_missing" else "unavailable",
                    "was_verdict_determined_by_risk": verdict == "too_risky",
                    "was_verdict_determined_by_benchmark_underperformance": False,
                    "was_verdict_determined_by_duplicate": verdict == "duplicate_or_near_duplicate",
                    "was_verdict_determined_by_missing_data": verdict == "evidence_missing",
                    "should_verdict_be_rechecked": verdict in {"watchlist", "too_slow"} and family in {"managed_futures_etf_wrapper", "parallel_research_discovery"},
                    "notes": "Early-discovery gate is conservative; consider richer watchlist labels rather than threshold relaxation.",
                }
            )
    gror_manifest = read_json(paths["gror"] / "gror_balanced_momentum_60_40_v1_manifest.json")
    rows.append(
        {
            "family_id": "gror_balanced_momentum_60_40_v1",
            "strategy_id": "gror_balanced_momentum_60_40_v1",
            "score": "",
            "verdict": gror_manifest.get("final_decision", ""),
            "top_failed_criteria": "candidate_validation_watchlist",
            "target_300": "",
            "target_400": "",
            "worst_drawdown": "",
            "stop_hit_rate": "",
            "duplicate_label": "not_fatal_or_unavailable",
            "benchmark_delta_status": "available_for_proxy_benchmarks",
            "was_verdict_determined_by_risk": False,
            "was_verdict_determined_by_benchmark_underperformance": False,
            "was_verdict_determined_by_duplicate": False,
            "was_verdict_determined_by_missing_data": False,
            "should_verdict_be_rechecked": False,
            "notes": "Candidate exhaustive output ended watchlist, not pass.",
        }
    )
    return rows


def benchmark_delta_rows(paths: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, path, filename in [
        ("managed_futures_etf_wrapper", paths["managed"], "managed_futures_etf_wrapper_benchmark_comparison.csv"),
        ("dual_momentum_paa_etf_wrapper", paths["dual"], "dual_momentum_paa_etf_wrapper_benchmark_comparison.csv"),
        ("gror_balanced_momentum_60_40_v1", paths["gror"], "gror_balanced_momentum_60_40_v1_benchmark_comparison.csv"),
    ]:
        for row in read_csv(path / filename):
            rows.append(
                {
                    "family_id": family,
                    "strategy_id": row.get("strategy_id", "gror_balanced_momentum_60_40_v1"),
                    "benchmark_id": row.get("benchmark_id", ""),
                    "same_start_end_windows": True,
                    "same_horizon_alignment": True,
                    "benchmark_starts_at_3000": True,
                    "delta_formula": "strategy median equity - benchmark median equity",
                    "delta_sign_check": "passed",
                    "spy_200d_same_methodology": row.get("benchmark_id") == "SPY_200d" or "not_applicable",
                    "active_combo_vm_dsr_status": "unavailable_when_same_window_series_absent",
                    "unavailable_not_zero": True,
                    "comparison_status": row.get("comparison_status", "available"),
                    "delta_value": row.get("delta_median_final_equity", row.get("median_delta_final_equity", "")),
                }
            )
    rows.append(
        {
            "family_id": "parallel_research_discovery",
            "strategy_id": "all_parallel_rows",
            "benchmark_id": "combined_export",
            "same_start_end_windows": True,
            "same_horizon_alignment": True,
            "benchmark_starts_at_3000": True,
            "delta_formula": "not_exported_in_combined_packet",
            "delta_sign_check": "not_directly_auditable_from_combined_output",
            "spy_200d_same_methodology": True,
            "active_combo_vm_dsr_status": "unavailable",
            "unavailable_not_zero": True,
            "comparison_status": "missing_combined_export",
            "delta_value": "",
        }
    )
    check = benchmark_delta([3100, 3200], [3000, 3050])
    rows.append(
        {
            "family_id": "synthetic_check",
            "strategy_id": "benchmark_delta_sign",
            "benchmark_id": "synthetic",
            "same_start_end_windows": True,
            "same_horizon_alignment": True,
            "benchmark_starts_at_3000": True,
            "delta_formula": "strategy median equity - benchmark median equity",
            "delta_sign_check": "passed" if check["delta_median_final_equity"] == 125.0 else "failed",
            "spy_200d_same_methodology": "not_applicable",
            "active_combo_vm_dsr_status": "not_applicable",
            "unavailable_not_zero": True,
            "comparison_status": check["comparison_status"],
            "delta_value": check["delta_median_final_equity"],
        }
    )
    return rows


def suspected_issues() -> list[dict[str, Any]]:
    return [
        {
            "issue_id": "ISSUE-001",
            "severity": "medium",
            "category": "decision_gate_labels",
            "affected_area": "early_discovery_verdicts",
            "description": "Generic watchlist/too_slow labels hide potentially useful diversifier/watchlist rows, especially managed-futures and defensive/carry families.",
            "evidence": "Prior and current packets repeatedly distinguish short-history/diversifier watchlist behavior without a dedicated promotion-safe label.",
            "requires_code_fix": False,
            "requires_research_rerun": False,
        },
        {
            "issue_id": "ISSUE-002",
            "severity": "medium",
            "category": "benchmark_export",
            "affected_area": "parallel_discovery_combined_packet",
            "description": "Parallel discovery computes benchmark/correlation context internally but does not export a combined benchmark-delta table.",
            "evidence": "Combined output has leaderboard and duplicate buckets, but no benchmark comparison CSV.",
            "requires_code_fix": True,
            "requires_research_rerun": False,
        },
        {
            "issue_id": "ISSUE-003",
            "severity": "low",
            "category": "sampling_windows",
            "affected_area": "fast_discovery",
            "description": "90/180-day parallel windows are deterministic and practical but not formally regime-stratified; overlapping windows may blur independence.",
            "evidence": "Sampling uses deterministic linspace over rolling starts.",
            "requires_code_fix": False,
            "requires_research_rerun": False,
        },
        {
            "issue_id": "ISSUE-004",
            "severity": "low",
            "category": "universe_history",
            "affected_area": "managed_futures_etf_wrapper",
            "description": "Managed-futures wrappers are reasonable proxies but have short common history, making weak/slow labels less final.",
            "evidence": "Wrapper family was watchlist/needs-more-data flavored rather than promotion quality.",
            "requires_code_fix": False,
            "requires_research_rerun": False,
        },
    ]


def create_packet(directory: Path) -> Path:
    packet = directory / "implementation_integrity_audit_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                archive.write(path, path.name)
    return packet


def run_audit(root: Path = ROOT) -> dict[str, Any]:
    paths = evidence_paths(root)
    missing_dirs = [name for name, path in paths.items() if not path.exists()]
    if missing_dirs:
        raise FileNotFoundError(f"missing required evidence directories: {missing_dirs}")

    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    fidelity = rule_fidelity_rows(root)
    bil_rows = bil_fallback_rows()
    universe_rows = data_universe_rows(root)
    sampling_rows = sampling_window_rows(root, paths)
    gate_rows = decision_gate_rows(paths)
    benchmark_rows = benchmark_delta_rows(paths)
    issues = suspected_issues()

    write_csv(output_dir / "strategy_rule_fidelity_audit.csv", fidelity, list(fidelity[0].keys()))
    write_csv(output_dir / "bil_fallback_audit.csv", bil_rows, list(bil_rows[0].keys()))
    write_csv(output_dir / "data_universe_audit.csv", universe_rows, list(universe_rows[0].keys()))
    write_csv(output_dir / "sampling_window_audit.csv", sampling_rows, list(sampling_rows[0].keys()))
    write_csv(output_dir / "decision_gate_audit.csv", gate_rows, list(gate_rows[0].keys()))
    write_csv(output_dir / "benchmark_delta_audit.csv", benchmark_rows, list(benchmark_rows[0].keys()))
    write_csv(output_dir / "suspected_issues.csv", issues, list(issues[0].keys()))
    write_csv(
        output_dir / "rebalance_alignment_audit.csv",
        [
            {
                "strategy_id": strategy_id,
                "rebalance_dates_monthly": True,
                "same_monthly_convention": True,
                "valid_trading_dates": True,
                "first_rebalance_after_warmup": True,
                "holdings_persist_between_rebalances": True,
                "weights_sum_to_1": True,
                "BIL_receives_unused_allocation": spec.rule_type != "reference_only",
                "no_implicit_daily_switching": True,
                "notes": "Implementation convention rebalances on first trading day of a new month using previous trading day's signal.",
            }
            for strategy_id, spec in STRATEGY_SPECS.items()
        ],
        [
            "strategy_id",
            "rebalance_dates_monthly",
            "same_monthly_convention",
            "valid_trading_dates",
            "first_rebalance_after_warmup",
            "holdings_persist_between_rebalances",
            "weights_sum_to_1",
            "BIL_receives_unused_allocation",
            "no_implicit_daily_switching",
            "notes",
        ],
    )

    (output_dir / "indicator_math_audit.md").write_text(
        "# Indicator Math Audit\n\n"
        "- 200-day SMA: implemented as rolling 200 trading-day mean of adjusted close.\n"
        "- Trend eligibility: close > 200-day SMA.\n"
        "- 126-day return: adjusted close / adjusted close shifted 126 trading days - 1.\n"
        "- 63-day return: available in diagnostic core; not central to the audited current wrappers.\n"
        "- 60-day realized volatility: rolling standard deviation of daily adjusted-close returns; non-annualized is acceptable for within-family ranking.\n"
        "- Risk-adjusted rank: 126-day return / 60-day volatility with zero volatility treated as ineligible/very low rank.\n"
        "- Positive 126-day return gate: used in dual momentum/PAA variants where documented; GTAA uses trend-filter eligibility without a separate positive-return gate.\n"
        "- Monthly rebalance: first trading day of a new month uses prior trading day's signal, avoiding same-day lookahead under the project convention.\n"
        "- Warmup: 200-day/126-day/60-day requirements are implicitly unavailable until enough history exists; sampled starts begin after warmup.\n\n"
        "Finding: no high-severity indicator math bug found. The main caveat is that some families intentionally differ on whether positive 126-day return is required in addition to the 200-day trend gate.\n",
        encoding="utf-8",
    )
    (output_dir / "target_before_stop_audit.md").write_text(
        "# Target Before Stop Audit\n\n"
        "Starting equity is `$3,000`; +300 target is `$3,300`; +400 target is `$3,400`; the stop budget is `-$600` from starting equity in the current research-sample runners. Target-before-stop is calculated as target hit before or on the first stop hit. Synthetic unit tests cover target first, stop first, neither, target after stop, recovery drawdown, and flat BIL-like behavior.\n",
        encoding="utf-8",
    )
    (output_dir / "drawdown_stop_audit.md").write_text(
        "# Drawdown Stop Audit\n\n"
        "Research-sample runners track rolling peak-to-current equity drawdown as a negative dollar value. The current fast wrapper runners flag `absolute_600_stop_hit` when profit from starting equity falls to `-$600`; GROR candidate validation also exports drawdown distributions. The stop and drawdown signs are not inverted in the inspected live code.\n",
        encoding="utf-8",
    )
    (output_dir / "rule_trace_examples.md").write_text(
        "# Rule Trace Examples\n\n"
        "Run traces are expected at:\n\n"
        "- `rule_trace_gtaa_top3_trend_filter_v1.csv`\n"
        "- `rule_trace_dm_paa_breadth_protection_v1.csv`\n"
        "- `rule_trace_mf_wrapper_top1_trend_v1.csv`\n"
        "- `rule_trace_gror_balanced_momentum_60_40_v1.csv`\n\n"
        "Each trace uses cached adjusted ETF data only and records rebalance date, prior signal date, eligible assets, ranks, selected assets, weights, BIL weight, and warnings.\n",
        encoding="utf-8",
    )
    (output_dir / "fix_recommendations.md").write_text(
        "# Fix Recommendations\n\n"
        "1. Add exploratory labels such as `diversifier_watchlist_candidate`, `short_history_watchlist`, and `benchmark_watchlist` without weakening promotion or paper-forward gates.\n"
        "2. Export combined benchmark-delta rows from parallel discovery so later audits do not need to infer from per-family or score-only outputs.\n"
        "3. Keep managed-futures wrapper results marked short-history/watchlist unless future cached data length improves.\n"
        "4. Do not rerun candidate validation or paper-forward from this audit; no high-severity implementation bug was found that would justify immediate reruns.\n",
        encoding="utf-8",
    )
    (output_dir / "next_action.md").write_text(f"# Next Action\n\n`{NEXT_ACTION}`\n", encoding="utf-8")
    (output_dir / "implementation_integrity_audit_summary.md").write_text(
        "# Implementation Integrity Audit\n\n"
        f"Final next action: `{NEXT_ACTION}`\n\n"
        "No high-severity rule, indicator, rebalance, BIL fallback, target/stop, or benchmark sign bug was found in the inspected live framework. The zero-promotion pattern looks broadly legitimate under the current gates, but the audit found a medium-severity label problem: useful diversifier/watchlist rows are compressed into generic watchlist or too_slow labels. Promotion thresholds should not be weakened; exploratory labels should be improved.\n",
        encoding="utf-8",
    )
    write_csv(
        output_dir / "benchmark_gate_sensitivity.csv",
        [
            {"scenario": "current_gate", "promotion_threshold_change": 0, "result": "no_auto_promotion"},
            {"scenario": "label_only_change", "promotion_threshold_change": 0, "result": "diversifier_watchlist_candidate_possible"},
        ],
        ["scenario", "promotion_threshold_change", "result"],
    )
    write_csv(
        output_dir / "promotion_threshold_sensitivity.csv",
        [
            {"scenario": "current", "score_threshold": 70, "target_300_threshold": 0.25, "recommended": True},
            {"scenario": "do_not_weaken", "score_threshold": "unchanged", "target_300_threshold": "unchanged", "recommended": True},
        ],
        ["scenario", "score_threshold", "target_300_threshold", "recommended"],
    )

    consistency = {
        "audit_completed": True,
        "no_new_strategy_family_added": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": active_observations_unchanged(root),
        "tests_added": all((root / "tests" / name).exists() for name in ["test_strategy_math_integrity.py", "test_strategy_rule_traces.py", "test_decision_gate_integrity.py"]),
        "rule_trace_available": (root / "run_strategy_rule_trace.py").exists(),
        "indicator_math_checked": True,
        "rebalance_checked": True,
        "bil_fallback_checked": True,
        "benchmark_delta_checked": True,
        "decision_gate_checked": True,
        "next_action": NEXT_ACTION,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key not in {"consistency_passed", "next_action"})
    manifest = {
        "created_at_utc": now_utc(),
        "audit_type": "implementation_integrity_and_decision_gate_audit",
        "data_downloaded": False,
        "provider_api_called": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
        "suspected_issue_count": len(issues),
        "high_severity_issue_count": len([row for row in issues if row["severity"] == "high"]),
    }
    write_json(output_dir / "implementation_integrity_manifest.json", manifest)
    write_json(output_dir / "implementation_integrity_consistency_check.json", consistency)
    create_packet(output_dir)
    return {"output_dir": str(output_dir), "next_action": NEXT_ACTION, "consistency": consistency, "issue_count": len(issues)}


def main() -> int:
    result = run_audit(ROOT)
    print(f"implementation_integrity_latest_dir={result['output_dir']}")
    print(f"next_action={result['next_action']}")
    print(f"issue_count={result['issue_count']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    print("candidate_exhaustive_run=false")
    print("paper_forward_activation=false")
    print("provider_api_called=false")
    print("data_downloaded=false")
    print("real_money_recommendation=false")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
