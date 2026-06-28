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


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "research_lane_decision" / "latest"
RECOMMENDED_NEXT_ACTION = "create_approved_symbol_expansion_review"
FORBIDDEN_FLAGS = {
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "paper_forward_checkpoint": False,
    "provider_api_called": False,
    "data_downloaded": False,
    "broker_integration": False,
    "live_orders": False,
    "order_placement": False,
    "real_money_recommendation": False,
    "strategy_run": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pd.read_csv(path).fillna("").to_dict("records")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def best_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return max(rows, key=lambda row: float(row.get("180d_median_final_equity") or 0.0))


def metric(row: dict[str, Any], field: str) -> str:
    value = row.get(field, "")
    return "" if value is None else str(value)


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    rows = rows_by_id(registry)
    required_dirs = [
        root / "evidence" / "promotion_reviews" / "qvm_quality_value_momentum_risk_adjusted_top2_v1" / "latest",
        root / "evidence" / "promotion_reviews" / "qvm_quality_value_momentum_top2_v1" / "latest",
        root / "evidence" / "promotion_reviews" / "lvq_lowvol_quality_spy_regime_v1" / "latest",
        root / "evidence" / "promotion_reviews" / "dsr_sector_top2_momentum_200d_bil_v1" / "latest",
        root / "evidence" / "promotion_reviews" / "dsr_sector_top3_momentum_defensive_cash_v1" / "latest",
        root / "evidence" / "active_strategy_evidence_recompute" / "latest",
        root / "evidence" / "research_state" / "latest",
        root / "evidence" / "strategy_lab" / "latest",
    ]
    for directory in required_dirs:
        if not directory.exists():
            mismatches.append(f"required evidence directory missing: {directory.relative_to(root)}")
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    if not readiness.exists() or load_json(readiness).get("missing_symbols") not in ([], None):
        mismatches.append("approved ETF cache is not ready")
    for strategy_id in [
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not frozen/active")
    required_dispositions = {
        "dsr_sector_top2_momentum_200d_bil_v1": "mark_duplicate_or_near_duplicate",
        "dsr_sector_top3_momentum_defensive_cash_v1": "mark_duplicate_or_near_duplicate",
        "qvm_quality_value_momentum_risk_adjusted_top2_v1": "mark_too_risky",
        "qvm_quality_value_momentum_top2_v1": "mark_duplicate_or_near_duplicate",
        "lvq_lowvol_quality_spy_regime_v1": "keep_watchlist",
    }
    for strategy_id, expected in required_dispositions.items():
        row = rows.get(strategy_id, {})
        if row.get("promotion_decision") != expected and row.get("status") != expected:
            mismatches.append(f"{strategy_id} is not currently disposed as {expected}")
    for batch, prefix in [
        ("new_batch_approved_cache", "parallel_discovery_approved_cache"),
        ("approved_cache_batch_2", "approved_cache_batch_2"),
        ("approved_cache_batch_3", "approved_cache_batch_3"),
    ]:
        output = root / "evidence" / "parallel_research_discovery" / batch / "latest"
        if not output.exists():
            mismatches.append(f"{batch} evidence missing")
            continue
        if batch != "new_batch_approved_cache":
            promotions = read_csv(output / f"{prefix}_promotion_candidates.csv")
            if promotions:
                mismatches.append(f"{batch} still has promotion candidates")
    return mismatches


def build_failure_audit(root: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    b1 = read_csv(root / "evidence" / "parallel_research_discovery" / "new_batch_approved_cache" / "latest" / "parallel_discovery_approved_cache_results.csv")
    b2 = read_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_results.csv")
    b3 = read_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_results.csv")
    rows = rows_by_id(registry)
    b2_best = best_result(b2)
    b3_best = best_result(b3)
    qvm_ra = next((row for row in b1 if row.get("strategy_id") == "qvm_quality_value_momentum_risk_adjusted_top2_v1"), {})
    qvm_top2 = next((row for row in b1 if row.get("strategy_id") == "qvm_quality_value_momentum_top2_v1"), {})
    lvq = next((row for row in b1 if row.get("strategy_id") == "lvq_lowvol_quality_spy_regime_v1"), {})
    return [
        failure_row("DSR Top2", rows.get("dsr_sector_top2_momentum_200d_bil_v1", {}), "duplicate_or_near_duplicate", "same DSR family as active DSR", False, False, True, False, "diagnostic_duplicate", False, "promotion review disposition archived it as duplicate/near-duplicate"),
        failure_row("DSR Top3", rows.get("dsr_sector_top3_momentum_defensive_cash_v1", {}), "duplicate_or_near_duplicate", "same DSR family as active DSR", False, False, True, False, "diagnostic_duplicate", False, "promotion review disposition archived it as duplicate/near-duplicate"),
        failure_row("QVM risk-adjusted top2", rows.get("qvm_quality_value_momentum_risk_adjusted_top2_v1", {}), "risk_buffer_too_thin", f"180d median {metric(qvm_ra, '180d_median_final_equity')}; buffer {metric(qvm_ra, 'risk_buffer_vs_minus_600')}", True, False, False, False, "rejected_reference", False, "target profile existed, but drawdown buffer was too close to stop"),
        failure_row("QVM top2", rows.get("qvm_quality_value_momentum_top2_v1", {}), "duplicate_or_near_duplicate", f"180d median {metric(qvm_top2, '180d_median_final_equity')}; buffer {metric(qvm_top2, 'risk_buffer_vs_minus_600')}", True, False, True, False, "diagnostic_duplicate", False, "same thin-risk-buffer family as QVM risk-adjusted sibling"),
        failure_row("LVQ SPY-regime", rows.get("lvq_lowvol_quality_spy_regime_v1", {}), "watchlist_valid", f"180d median {metric(lvq, '180d_median_final_equity')}; buffer {metric(lvq, 'risk_buffer_vs_minus_600')}", False, True, False, False, "watchlist", False, "safer but not strong enough versus active references"),
        failure_row("approved-cache batch 2 best row", b2_best, "benchmark_only", f"{metric(b2_best, 'strategy_id')} 180d median {metric(b2_best, '180d_median_final_equity')}", False, True, False, False, "benchmark_watchlist", False, "best row was a benchmark sanity row and produced no surviving candidate"),
        failure_row("approved-cache batch 3 best row", b3_best, "duplicate_or_near_duplicate", f"{metric(b3_best, 'strategy_id')} 180d median {metric(b3_best, '180d_median_final_equity')}", False, True, True, False, "diagnostic_duplicate", False, "best row lagged DSR/SPY references and correlated with SPY_200d"),
        failure_row("GROR balanced momentum", rows.get("gror_balanced_momentum_60_40_v1", {}), "watchlist_valid", "candidate validation ended as watchlist/incomplete evidence", False, False, False, True, "watchlist", False, "not a current candidate_exhaustive launch point"),
        failure_row("managed futures wrapper best row", rows.get("managed_futures_proxy_etf_trend_v1", rows.get("managed_futures_etf_wrapper", {})), "too_slow_for_profit_goal", "short history wrapper proxy; too slow", False, True, False, True, "diversifier_watchlist", False, "additive theme but not profit-strong enough in existing evidence"),
        failure_row("dual momentum/PAA best row", rows.get("dm_paa_breadth_protection_v1", rows.get("dual_momentum_paa_etf_wrapper", {})), "too_risky", "several rows too risky; best remaining row watchlist only", True, False, False, False, "watchlist", False, "did not survive promotion path"),
        failure_row("GTAA best row", rows.get("gtaa_faber_style_benchmark_lane", {}), "benchmark_only", "planning/control lane; likely overlaps SPY_200d/GROR", False, True, True, False, "benchmark", False, "useful as benchmark, not current promotion lane"),
        failure_row("carry/yield defensive filter", rows.get("yield_credit_trend_filter_v1", {}), "too_slow_for_profit_goal", "credit/yield filter did not clear profit gates", False, True, False, False, "watchlist_or_control", False, "current approved credit/yield set looks defensive but slow"),
    ]


def failure_row(name: str, source: dict[str, Any], primary: str, secondary: str, risk: bool, profit: bool, duplicate: bool, data: bool, useful_as: str, rerun: bool, reason: str) -> dict[str, Any]:
    status = source.get("promotion_decision") or source.get("status") or source.get("decision") or source.get("current_status") or "reviewed"
    best_metric = source.get("latest_known_result_summary") or source.get("180d_median_final_equity") or source.get("best_metric_available") or secondary
    return {
        "strategy_or_family": name,
        "current_status": status,
        "best_metric_available": best_metric,
        "primary_failure_reason": primary,
        "secondary_failure_reason": secondary,
        "risk_issue": risk,
        "profit_issue": profit,
        "duplicate_issue": duplicate,
        "data_issue": data,
        "still_useful_as": useful_as,
        "should_rerun": rerun,
        "reason": reason,
    }


def build_family_status(root: Path, registry: dict[str, Any]) -> list[dict[str, Any]]:
    b1 = read_csv(root / "evidence" / "parallel_research_discovery" / "new_batch_approved_cache" / "latest" / "parallel_discovery_approved_cache_results.csv")
    b2 = read_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_results.csv")
    b3 = read_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_results.csv")
    rows = rows_by_id(registry)
    best_by_family: dict[str, dict[str, Any]] = {}
    for row in b1 + b2 + b3:
        family = str(row.get("family_group") or row.get("family") or "")
        if family and float(row.get("180d_median_final_equity") or 0.0) > float(best_by_family.get(family, {}).get("180d_median_final_equity") or 0.0):
            best_by_family[family] = row
    return [
        family_row("volatility_managed_equity_etf", "active", rows.get("paper_forward_vm_quality_lowvol_proxy_v1", {}), "keep observing frozen active VM", False, True),
        family_row("defensive_sector_rotation_etf", "active", rows.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", {}), "keep observing frozen active DSR; top2/top3 exhausted as duplicates", False, True),
        family_row_from_best("quality_value_momentum_blend", "exhausted_for_now", best_by_family.get("quality_value_momentum_blend", {}), "do not rescue QVM again without new symbols", True),
        family_row_from_best("lowvol_quality_hybrid", "watchlist_valid", best_by_family.get("lowvol_quality_hybrid", {}), "watchlist only; safer but not validation-ready", True),
        family_row_from_best("growth_defensive_barbell", "exhausted_for_now", best_by_family.get("growth_defensive_barbell", {}), "current variants too slow or benchmark-weaker", True),
        family_row_from_best("multi_asset_trend_risk_control", "exhausted_for_now", best_by_family.get("multi_asset_trend_risk_control", {}), "risk controlled but not profit-strong", True),
        family_row_from_best("growth_cash_brake", "exhausted_for_now", best_by_family.get("growth_with_cash_brake", {}), "best batch 3 row duplicate/near-duplicate", True),
        family_row_from_best("dual_regime_growth_defensive", "exhausted_for_now", best_by_family.get("dual_regime_growth_defensive", {}), "batch 3 rows duplicate/too slow", True),
        family_row_from_best("drawdown_guard_growth", "exhausted_for_now", best_by_family.get("drawdown_guard_growth", {}), "predefined guards reduced risk but duplicated controls", True),
        family_row("global_risk_on_risk_off_etf", "watchlist_valid", rows.get("gror_balanced_momentum_60_40_v1", {}), "watchlist after validation/incomplete evidence", False, True),
        family_row("managed_futures_etf_wrapper", "watchlist_valid", rows.get("managed_futures_etf_wrapper", {}), "diversifier watchlist; short-history and too slow", False, True),
        family_row("dual_momentum_paa_etf_wrapper", "watchlist_valid", rows.get("dm_paa_breadth_protection_v1", rows.get("dual_momentum_paa_etf_wrapper", {})), "watchlist only after risk/duplicate gates", False, True),
        family_row("gtaa_faber_style_benchmark_lane", "benchmark_only", rows.get("gtaa_faber_style_benchmark_lane", {}), "benchmark/control only for now", False, True),
        family_row("static_all_weather_or_permanent_portfolio_benchmark", "benchmark_only", rows.get("static_all_weather_or_permanent_portfolio_benchmark", {}), "defensive benchmark/control only", False, True),
        family_row("low_beta_defensive_equity_etf", "needs_new_symbols", {}, "needs controlled expansion such as EFAV/EEMV/ACWV before useful discovery", False, False),
        family_row("dividend_quality_yield_etf", "not_tested_enough", rows.get("yield_credit_trend_filter_v1", {}), "approved SCHD/VIG/DGRO exist but lane is not deeply tested", False, True),
        family_row("carry_yield_etf_proxy", "exhausted_for_now", rows.get("yield_credit_trend_filter_v1", {}), "HYG/LQD/EMB defensive carry filters look too slow", True, True),
    ]


def family_row_from_best(family: str, status: str, row: dict[str, Any], action: str, exhausted: bool) -> dict[str, Any]:
    return {
        "family": family,
        "status": status,
        "best_row": row.get("strategy_id", ""),
        "best_known_180d_median": row.get("180d_median_final_equity", ""),
        "best_known_drawdown": row.get("180d_worst_drawdown", ""),
        "promotion_candidate_survived": False,
        "candidate_validation_recommended": False,
        "active_duplicate_risk": "flagged" if "duplicate" in str(row.get("decision", "")) else "not_flagged",
        "data_ready": True,
        "exhausted_for_now": exhausted,
        "recommended_action": action,
    }


def family_row(family: str, status: str, row: dict[str, Any], action: str, exhausted: bool, data_ready: bool) -> dict[str, Any]:
    return {
        "family": family,
        "status": status,
        "best_row": row.get("id") or row.get("strategy_id") or "",
        "best_known_180d_median": "",
        "best_known_drawdown": "",
        "promotion_candidate_survived": False,
        "candidate_validation_recommended": False,
        "active_duplicate_risk": row.get("duplication_risk", "not_assessed"),
        "data_ready": data_ready,
        "exhausted_for_now": exhausted,
        "recommended_action": action,
    }


def build_universe_review() -> list[dict[str, Any]]:
    return [
        universe_row("US broad/growth: SPY, QQQ, IWM, MTUM", "high", "active references plus batches tested", "duplicate or benchmark-weaker", False, False, "pause variants unless paired with new structure"),
        universe_row("quality/value/lowvol: QUAL, VLUE, VTV, SPLV, USMV", "high", "QVM/LVQ tested and disposed", "thin risk buffer or too slow/duplicate", False, True, "expand factor set before further rescue"),
        universe_row("international: EFA, EEM", "shallow", "mostly benchmark/control exposure", "too little regional granularity", True, True, "review IEFA/VEA/VWO/regional ETFs"),
        universe_row("bonds/cash: BIL, IEF, TLT, AGG", "high", "useful risk dampener", "helps drawdown but slows profit", False, False, "keep as controls/fallbacks"),
        universe_row("gold: GLD", "medium", "useful diversifier/control", "not enough alone for promotion", False, False, "keep as diversifier"),
        universe_row("sector: XLK, XLF, XLE, XLV, XLY, XLP, XLU, XLI, XLB, XLC", "high", "active DSR survives; top2/top3 duplicate", "same-family duplicate risk", False, False, "observe active DSR; no same-family rescue"),
        universe_row("credit/yield: HYG, LQD, EMB", "medium", "defensive/carry filters available", "too slow for profit goal", False, False, "watchlist/control only"),
        universe_row("managed futures: DBMF, KMLM, CTA, FMF, WTMF", "medium", "additive but short-history/slow", "short history and weak profit profile", False, False, "watchlist diversifier only"),
    ]


def universe_row(group: str, depth: str, useful: str, failure: str, more_variants: bool, needs_new: bool, action: str) -> dict[str, Any]:
    return {"universe_group": group, "tested_depth": depth, "useful_results": useful, "failure_pattern": failure, "more_variants_likely_useful": more_variants, "needs_new_symbols": needs_new, "proposed_next_action": action}


def build_next_options() -> list[dict[str, Any]]:
    return [
        option("continue_current_approved_universe_batch_4", "Continue current approved ETF universe with batch 4.", "low", "diminishing returns", "medium", "none", "low", False, "three approved-cache batches produced no surviving candidate"),
        option("small_approved_etf_expansion", "Add small approved ETF expansion.", "medium_high", "symbol governance and cache QA required", "medium", "requires review only", "medium", True, "current universe looks saturated; expansion can add structural breadth without forbidden products"),
        option("revisit_diversifier_watchlist", "Revisit diversifier watchlist candidates.", "medium", "may remain too slow", "low", "none", "low_medium", False, "watchlist items are useful but not current promotion candidates"),
        option("repair_active_combo_benchmark", "Recompute/validate active combo series availability.", "medium", "diagnostic only", "low_medium", "none", "low", False, "would improve deltas but not create a new candidate"),
        option("pause_and_improve_scoring", "Pause discovery and improve scoring/labeling.", "medium", "opportunity cost", "low", "none", "low", False, "useful cleanup but not highest next lane"),
        option("different_product_area", "Move to a different product/project area.", "low_medium", "abandons current ETF learning", "high", "large", "unknown", False, "premature before controlled ETF expansion review"),
        option("revisit_crypto_spot_policy", "Revisit crypto spot policy.", "low", "outside current risk direction", "high", "large", "unknown", False, "deferred by current boundaries"),
        option("revisit_individual_stock_policy", "Revisit individual stock momentum policy.", "low", "survivorship/provider/terms risk", "high", "large", "unknown", False, "not appropriate for current ETF-wrapper direction"),
        option("add_international_regional_etfs", "Add international/regional ETFs.", "medium_high", "new symbol QA", "medium", "requires approved-symbol review", "medium", True, "addresses shallow EFA/EEM-only international breadth"),
        option("add_factor_etfs", "Add factor ETFs beyond current QUAL/MTUM/VLUE/VTV.", "medium", "may duplicate existing beta", "medium", "requires approved-symbol review", "medium", True, "could create structurally different growth/value sleeves"),
    ]


def option(option_id: str, description: str, expected_value: str, risk: str, cost: str, policy: str, likely: str, recommended: bool, reason: str) -> dict[str, Any]:
    return {"option_id": option_id, "description": description, "expected_value": expected_value, "risk": risk, "implementation_cost": cost, "policy_impact": policy, "likely_to_find_promotion_candidate": likely, "recommended": recommended, "reason": reason}


def symbol_expansion_proposal() -> dict[str, Any]:
    return {
        "status": "proposed_only_not_approved",
        "recommended": True,
        "next_action": RECOMMENDED_NEXT_ACTION,
        "rules": {
            "download_now": False,
            "approve_automatically": False,
            "strategy_run_now": False,
            "requires_policy_review": True,
        },
        "symbols": [
            {"symbol": "IEFA", "group": "international_regional", "expected_lane": "international_factor_breadth", "reason": "broader developed ex-US proxy than current EFA-only lane"},
            {"symbol": "VEA", "group": "international_regional", "expected_lane": "international_factor_breadth", "reason": "low-cost developed-market alternative for robustness checks"},
            {"symbol": "VWO", "group": "international_regional", "expected_lane": "international_factor_breadth", "reason": "emerging-market alternative to EEM"},
            {"symbol": "EWJ", "group": "international_regional", "expected_lane": "regional_momentum", "reason": "adds Japan regional sleeve"},
            {"symbol": "EWU", "group": "international_regional", "expected_lane": "regional_momentum", "reason": "adds UK regional sleeve"},
            {"symbol": "EWG", "group": "international_regional", "expected_lane": "regional_momentum", "reason": "adds Germany regional sleeve"},
            {"symbol": "EWY", "group": "international_regional", "expected_lane": "regional_momentum", "reason": "adds Korea regional sleeve"},
            {"symbol": "INDA", "group": "international_regional", "expected_lane": "regional_momentum", "reason": "adds India regional sleeve"},
            {"symbol": "IWF", "group": "us_factor", "expected_lane": "factor_rotation", "reason": "large-cap growth factor alternative"},
            {"symbol": "IWD", "group": "us_factor", "expected_lane": "factor_rotation", "reason": "large-cap value factor alternative"},
            {"symbol": "SCHG", "group": "us_factor", "expected_lane": "factor_rotation", "reason": "growth ETF alternative to QQQ/MTUM"},
            {"symbol": "SCHV", "group": "us_factor", "expected_lane": "factor_rotation", "reason": "value ETF alternative to VTV/VLUE"},
            {"symbol": "EFAV", "group": "minimum_volatility", "expected_lane": "international_lowvol_defensive", "reason": "developed ex-US minimum-volatility sleeve"},
            {"symbol": "EEMV", "group": "minimum_volatility", "expected_lane": "international_lowvol_defensive", "reason": "emerging-market minimum-volatility sleeve"},
            {"symbol": "ACWV", "group": "minimum_volatility", "expected_lane": "global_lowvol_defensive", "reason": "global minimum-volatility control/diversifier"},
        ],
    }


def create_packet(directory: Path) -> Path:
    packet = directory / "research_lane_decision_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    write_csv(output / "research_lane_failure_pattern_audit.csv", payload["failure_rows"], ["strategy_or_family", "current_status", "best_metric_available", "primary_failure_reason", "secondary_failure_reason", "risk_issue", "profit_issue", "duplicate_issue", "data_issue", "still_useful_as", "should_rerun", "reason"])
    write_csv(output / "strategy_family_status_matrix.csv", payload["family_rows"], ["family", "status", "best_row", "best_known_180d_median", "best_known_drawdown", "promotion_candidate_survived", "candidate_validation_recommended", "active_duplicate_risk", "data_ready", "exhausted_for_now", "recommended_action"])
    write_csv(output / "approved_universe_exhaustion_review.csv", payload["universe_rows"], ["universe_group", "tested_depth", "useful_results", "failure_pattern", "more_variants_likely_useful", "needs_new_symbols", "proposed_next_action"])
    write_csv(output / "next_lane_options.csv", payload["option_rows"], ["option_id", "description", "expected_value", "risk", "implementation_cost", "policy_impact", "likely_to_find_promotion_candidate", "recommended", "reason"])

    (output / "proposed_symbol_expansion_if_any.yaml").write_text(yaml.safe_dump(payload["symbol_expansion"], sort_keys=False, width=120), encoding="utf-8")
    (output / "recommended_next_lane.md").write_text(f"# Recommended Next Lane\n\n`{RECOMMENDED_NEXT_ACTION}`\n\nRationale: the current approved universe has produced repeated duplicate, too-slow, benchmark-only, or too-thin-risk-buffer results. Review a small symbol expansion before launching another discovery batch.\n\nNo symbols are approved automatically. No downloads or strategy runs are authorized by this audit.\n", encoding="utf-8")

    summary = [
        "# Research Lane Decision",
        "",
        f"Created at UTC: {now_utc()}",
        f"Recommended next action: `{RECOMMENDED_NEXT_ACTION}`",
        "",
        "Main finding: the current approved ETF universe looks saturated for immediate profit-candidate discovery. Recent candidates either failed risk buffer gates, duplicated active references, or lagged active/SPY benchmarks.",
        "",
        "This audit did not run new strategies, download data, mutate active observations, start paper-forward workflows, add broker paths, or make real-money recommendations.",
    ]
    (output / "research_lane_decision_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    write_json(output / "research_lane_decision_manifest.json", payload["manifest"])
    write_json(output / "research_lane_decision_consistency_check.json", payload["consistency"])
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet)}


def build_payload(root: Path, strict_state: bool = True) -> dict[str, Any]:
    registry = load_yaml(root / "strategy_lab" / "strategy_registry.yaml")
    mismatches = state_mismatches(root, registry)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    failure_rows = build_failure_audit(root, registry)
    family_rows = build_family_status(root, registry)
    universe_rows = build_universe_review()
    option_rows = build_next_options()
    expansion = symbol_expansion_proposal()
    consistency = {
        "lane_decision_completed": True,
        "no_strategy_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": True,
        "failure_pattern_audit_created": bool(failure_rows),
        "family_status_matrix_created": bool(family_rows),
        "universe_exhaustion_review_created": bool(universe_rows),
        "next_lane_options_created": bool(option_rows),
        "recommended_next_lane_created": bool(RECOMMENDED_NEXT_ACTION),
        "symbol_expansion_proposal_created": bool(expansion),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    manifest = {
        "created_at_utc": now_utc(),
        "recommended_next_action": RECOMMENDED_NEXT_ACTION,
        "state_mismatches": mismatches,
        "approved_universe_saturated": True,
        "surviving_promotion_candidate": False,
        "active_vm_frozen_active": True,
        "active_dsr_frozen_active": True,
        **FORBIDDEN_FLAGS,
    }
    return {"failure_rows": failure_rows, "family_rows": family_rows, "universe_rows": universe_rows, "option_rows": option_rows, "symbol_expansion": expansion, "consistency": consistency, "manifest": manifest}


def run_lane_decision(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    payload = build_payload(root, strict_state=strict_state)
    outputs = write_outputs(root, payload)
    return {"output_dir": outputs["output_dir"], "packet": outputs["packet"], "recommended_next_action": RECOMMENDED_NEXT_ACTION, "consistency": payload["consistency"], "symbol_expansion_count": len(payload["symbol_expansion"]["symbols"])}


def main() -> None:
    print(json.dumps(run_lane_decision(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
