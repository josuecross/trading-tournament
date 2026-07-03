from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "profit_oriented_registry_research_sample_triage"
    / "latest"
)

NEXT_ACTION_SHORTLIST = "direction_owner_select_from_registry_triage_shortlist"
CLEAR_WINNER_MIN_SCORE = 60.0
CLEAR_WINNER_SCORE_MARGIN = 8.0

COMPLETED_OR_EXCLUDED_FAMILY_TOKENS = (
    "high_return_tactical",
    "volatility_throttle",
    "commodity",
    "managed_futures",
    "macro_gld",
    "gld_macro",
    "risk_on_risk_off",
)

COMPLETED_OR_EXCLUDED_FAMILIES = {
    "active_sleeve_ensemble",
    "benchmark_sanity_rows",
    "commodity_basket_etf_momentum_v1",
    "commodity_wrapper_time_series_momentum",
    "fixed_strategy_combination",
    "managed_futures_etf_wrapper",
    "managed_futures_style_trend",
    "regional_gold_bond_defensive_rotation",
}

TERMINAL_OR_NON_RESEARCHABLE_STATUSES = {
    "active_observation_running",
    "benchmark_watchlist",
    "duplicate_or_near_duplicate",
    "filter_ineffective_or_bug_review",
    "promotion_candidate_found",
    "too_slow",
    "too_slow_defensive_watchlist",
    "too_slow_for_profit_goal",
    "weaker_than_active_references_watchlist",
}

METRIC_FILENAME_TOKENS = ("results", "rankings", "diagnostics")
ID_COLUMNS = ("strategy_id", "experiment_id", "id", "run_id")

REGISTRY_CANDIDATE_FIELDS = (
    "strategy_id",
    "family",
    "status",
    "latest_evidence_path",
    "disposition",
    "exclusion_reasons",
    "triage_score",
    "metric_source_csv",
    "median_180d_final_equity",
    "worst_drawdown",
    "risk_buffer_vs_minus_600",
    "max_reference_correlation",
    "delta_vs_active_vm",
    "delta_vs_active_dsr",
    "delta_vs_spy_200d",
    "required_local_data_symbols",
    "expected_bounded_design_size_recommendation",
)

RANKING_FIELDS = (
    "rank",
    "strategy_id",
    "family",
    "status",
    "triage_score",
    "evidence_quality_score",
    "lineage_score",
    "profit_score",
    "risk_score",
    "distinctness_score",
    "data_availability_score",
    "bounded_design_feasibility_score",
    "status_adjustment_score",
    "metric_source_csv",
    "median_180d_final_equity",
    "worst_drawdown",
    "risk_buffer_vs_minus_600",
    "max_reference_correlation",
    "delta_vs_active_vm",
    "delta_vs_active_dsr",
    "delta_vs_spy_200d",
    "required_local_data_symbols",
    "score_rationale",
)

REQUIRED_FILES_ALWAYS = (
    "triage_manifest.json",
    "registry_candidate_table.csv",
    "excluded_candidate_table.csv",
    "ranking_scoring_table.csv",
    "guardrail_checklist.json",
    "triage_summary.md",
    "registry_triage_next_action.md",
    "triage_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def registry_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("strategies")
    return rows if isinstance(rows, list) else []


def is_research_sample_review(row: dict[str, Any]) -> bool:
    actions = row.get("allowed_next_actions", row.get("allowed_next_action", ""))
    return "research_sample_review" in str(actions)


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def metric_value(metrics: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = as_float(metrics.get(name))
        if value is not None:
            return value
    return None


def clean_string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def lower_row_text(row: dict[str, Any]) -> str:
    keys = (
        "strategy_id",
        "id",
        "family",
        "strategy_family",
        "lane",
        "role",
        "instrument_family",
        "instrument_lane",
        "status",
        "current_status",
    )
    return " ".join(clean_string(row.get(key)).lower() for key in keys)


def strategy_id(row: dict[str, Any]) -> str:
    return clean_string(row.get("strategy_id") or row.get("id"))


def family_id(row: dict[str, Any]) -> str:
    return clean_string(row.get("family") or row.get("strategy_family") or row.get("family_id"))


def resolve_path(root: Path, value: Any) -> Path:
    text = clean_string(value)
    if not text:
        return root / "__missing__"
    path = Path(text)
    return path if path.is_absolute() else root / path


def csv_priority(path: Path, row: dict[str, Any]) -> tuple[int, float, int, int]:
    row_type = clean_string(row.get("row_type")).lower()
    if row_type == "candidate_horizon":
        candidate_score = 3
    elif row_type in {"", "nan"}:
        candidate_score = 2
    elif "benchmark" in row_type:
        candidate_score = 0
    else:
        candidate_score = 1
    horizon = as_float(row.get("horizon")) or 0.0
    name = path.name.lower()
    file_score = 3 if "results" in name else 2 if "rankings" in name else 1
    populated = sum(1 for value in row.values() if clean_string(value))
    return (candidate_score, horizon, file_score, populated)


def load_metric_lookup(root: Path, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    evidence_dirs: set[Path] = set()
    for row in rows:
        path = resolve_path(root, row.get("latest_evidence_path"))
        if path.exists() and path.is_dir():
            evidence_dirs.add(path)

    lookup: dict[str, dict[str, Any]] = {}
    priorities: dict[str, tuple[int, float, int, int]] = {}
    for directory in sorted(evidence_dirs):
        for path in sorted(directory.glob("*.csv")):
            if not any(token in path.name.lower() for token in METRIC_FILENAME_TOKENS):
                continue
            try:
                with path.open("r", newline="", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    if not reader.fieldnames:
                        continue
                    id_column = next((column for column in ID_COLUMNS if column in reader.fieldnames), None)
                    if id_column is None:
                        continue
                    for source_row in reader:
                        item_id = clean_string(source_row.get(id_column))
                        if not item_id:
                            continue
                        candidate = dict(source_row)
                        candidate["_source_csv"] = str(path)
                        priority = csv_priority(path, source_row)
                        if item_id not in lookup or priority > priorities[item_id]:
                            lookup[item_id] = candidate
                            priorities[item_id] = priority
            except UnicodeDecodeError:
                continue
    return lookup


def explicit_duplicate_risk(row: dict[str, Any]) -> bool:
    status = clean_string(row.get("status") or row.get("current_status")).lower()
    failure_mode = clean_string(row.get("primary_failure_mode")).lower()
    duplicate_risk = clean_string(row.get("duplication_risk")).lower()
    duplicate_of = clean_string(row.get("duplicate_of"))
    allowed_not_flagged = {"", "none", "not_flagged", "not_flagged_by_registry"}
    return (
        "duplicate" in status
        or "duplicate" in failure_mode
        or duplicate_of != ""
        or (duplicate_risk not in allowed_not_flagged)
    )


def exclusion_reasons(row: dict[str, Any], ledger_by_family: dict[str, dict[str, Any]]) -> list[str]:
    item_id = strategy_id(row)
    family = family_id(row)
    status = clean_string(row.get("status") or row.get("current_status")).lower()
    text = lower_row_text(row)
    reasons: list[str] = []

    if family in COMPLETED_OR_EXCLUDED_FAMILIES:
        reasons.append(f"family `{family}` is completed, control-only, combination-only, or closed for now")
    if any(token in text for token in COMPLETED_OR_EXCLUDED_FAMILY_TOKENS):
        reasons.append("belongs to a completed/excluded immediate-continuation family or lane")
    if any(token in text for token in ("benchmark", "static_all_weather")):
        reasons.append("benchmark/control-only row")
    if any(token in text for token in ("gld", "gold")):
        reasons.append("Macro/GLD/gold lineage is excluded from immediate continuation")
    if status in TERMINAL_OR_NON_RESEARCHABLE_STATUSES:
        reasons.append(f"status `{status}` is terminal, weak, active, benchmark, or non-researchable for this triage")
    if explicit_duplicate_risk(row):
        reasons.append("duplicate or near-duplicate risk is explicitly flagged")
    if row.get("implementation_allowed_now") is False:
        reasons.append("registry marks implementation_allowed_now=false")

    ledger_entry = ledger_by_family.get(family)
    if ledger_entry and ledger_entry.get("future_research_allowed") is False:
        reasons.append(f"family ledger marks `{family}` future_research_allowed=false")

    instrument = clean_string(row.get("instrument_family") or row.get("instrument_lane")).lower()
    if "futures" in instrument or "options" in instrument:
        reasons.append("instrument lane would require futures/options mechanics")
    if row.get("paper_forward_active") is True:
        reasons.append("row is already paper-forward/active observation state")
    if row.get("candidate_exhaustive_run") is True:
        reasons.append("candidate_exhaustive already ran")

    if item_id.startswith("static_all_weather"):
        reasons.append("static all-weather remains benchmark/control only")
    return reasons


def extract_symbols(row: dict[str, Any], metrics: dict[str, Any], root: Path) -> str:
    symbols = clean_string(metrics.get("symbols"))
    if symbols:
        return symbols
    evidence_path = resolve_path(root, row.get("latest_evidence_path"))
    if evidence_path.exists() and evidence_path.is_dir():
        for manifest_path in sorted(evidence_path.glob("*manifest.json")):
            manifest = read_json(manifest_path)
            approved = manifest.get("approved_symbols")
            if isinstance(approved, list) and approved:
                return ";".join(clean_string(symbol) for symbol in approved)
    text = " ".join(
        clean_string(row.get(key))
        for key in ("notes", "latest_known_result_summary", "promotion_requirements", "demotion_or_kill_criteria")
    )
    tokens = sorted(set(re.findall(r"\b[A-Z]{2,5}\b", text)))
    return ";".join(tokens)


def max_reference_correlation(metrics: dict[str, Any]) -> float | None:
    values = [
        metric_value(metrics, "corr_vs_active_vm"),
        metric_value(metrics, "corr_vs_active_dsr"),
        metric_value(metrics, "corr_vs_spy_200d"),
        metric_value(metrics, "correlation_to_combo_if_available"),
        metric_value(metrics, "correlation_to_spy200d_if_available"),
    ]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def evidence_quality_score(row: dict[str, Any], metrics: dict[str, Any], root: Path) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    evidence_path = resolve_path(root, row.get("latest_evidence_path"))
    evidence_text = clean_string(row.get("latest_evidence_path")).lower()
    if evidence_path.exists():
        score += 8.0
        reasons.append("latest evidence path exists +8")
    if any(token in evidence_text for token in ("bounded", "methodology_fix", "labeling_fix", "robustness", "confirmation")):
        score += 15.0
        reasons.append("corrected/focused diagnostic evidence +15")
    elif any(token in evidence_text for token in ("approved_cache", "expanded_universe", "fast_exploration")):
        score += 8.0
        reasons.append("approved-cache or expanded-universe evidence +8")
    elif "profit_exploration" in evidence_text:
        score += 4.0
        reasons.append("older profit-exploration evidence +4")
    if metrics:
        score += 4.0
        reasons.append("row-level saved metrics found +4")
    return score, reasons


def lineage_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if strategy_id(row):
        score += 2.0
        reasons.append("strategy_id present +2")
    if family_id(row):
        score += 6.0
        reasons.append("family present +6")
    if clean_string(row.get("parent_id")):
        score += 3.0
        reasons.append("parent_id present +3")
    if row.get("rules_frozen") is True:
        score += 4.0
        reasons.append("rules_frozen=true +4")
    return score, reasons


def profit_score(metrics: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    median = metric_value(metrics, "180d_median_final_equity", "median_stop_enforced_final_equity")
    if median is not None:
        points = max(0.0, min(25.0, (median - 3000.0) / 500.0 * 25.0))
        score += points
        reasons.append(f"saved median final equity {median:.4f} -> +{points:.2f}")
    target_300 = metric_value(metrics, "target_300_before_stop_rate", "p_target_300_before_stop")
    if target_300 is not None:
        points = max(0.0, min(4.0, target_300 * 4.0))
        score += points
        reasons.append(f"target_300 rate {target_300:.4f} -> +{points:.2f}")
    target_400 = metric_value(metrics, "target_400_before_stop_rate", "p_target_400_before_stop")
    if target_400 is not None:
        points = max(0.0, min(3.0, target_400 * 3.0))
        score += points
        reasons.append(f"target_400 rate {target_400:.4f} -> +{points:.2f}")
    delta_bil = metric_value(metrics, "delta_vs_bil")
    if delta_bil is not None:
        points = max(0.0, min(4.0, delta_bil / 100.0))
        score += points
        reasons.append(f"delta_vs_bil {delta_bil:.4f} -> +{points:.2f}")
    return score, reasons


def risk_score(row: dict[str, Any], metrics: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    risk_buffer = metric_value(metrics, "risk_buffer_vs_minus_600")
    drawdown = metric_value(metrics, "180d_worst_drawdown", "worst_max_drawdown", "max_drawdown_dollars")
    if risk_buffer is not None:
        points = 20.0 if risk_buffer >= 300 else 12.0 if risk_buffer >= 150 else 6.0 if risk_buffer >= 50 else -20.0
        score += points
        reasons.append(f"risk buffer {risk_buffer:.4f} -> {points:+.0f}")
    elif drawdown is not None:
        points = 12.0 if drawdown >= -300 else 6.0 if drawdown >= -500 else -10.0 if drawdown >= -650 else -20.0
        score += points
        reasons.append(f"worst drawdown {drawdown:.4f} -> {points:+.0f}")
    status = clean_string(row.get("status") or row.get("current_status")).lower()
    if "too_risky" in status or "risk_budget_breach" in status:
        score -= 12.0
        reasons.append(f"risk status `{status}` -> -12")
    return score, reasons


def distinctness_score(row: dict[str, Any], metrics: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    correlation = max_reference_correlation(metrics)
    if correlation is not None:
        if correlation < 0.75:
            points = 10.0
        elif correlation < 0.85:
            points = 5.0
        elif correlation >= 0.90:
            points = -8.0
        else:
            points = 0.0
        score += points
        reasons.append(f"max reference correlation {correlation:.4f} -> {points:+.0f}")
    if clean_string(row.get("duplication_risk")).lower() == "not_flagged":
        score += 4.0
        reasons.append("duplication_risk not_flagged +4")
    return score, reasons


def data_availability_score(row: dict[str, Any], metrics: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    data_source = clean_string(row.get("data_source")).lower()
    data_history_mode = clean_string(metrics.get("data_history_mode")).lower()
    instrument = clean_string(row.get("instrument_family") or row.get("instrument_lane")).lower()
    if any(token in data_source for token in ("existing", "cache", "cached")):
        score += 8.0
        reasons.append("registry data source is existing/cache +8")
    if "public" in data_source or "yfinance" in data_source:
        score -= 4.0
        reasons.append("public/provider-compatible source needs caution -4")
    if "per_asset_availability" in data_history_mode:
        score += 3.0
        reasons.append("saved metrics report per-asset availability +3")
    if "etf" in instrument or "wrapper" in instrument:
        score += 8.0
        reasons.append("ETF/wrapper instrument lane +8")
    if "crypto" in instrument:
        score -= 8.0
        reasons.append("crypto/session mechanics review would be needed -8")
    return score, reasons


def bounded_design_feasibility_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if row.get("rules_frozen") is True:
        score += 4.0
        reasons.append("rules already frozen +4")
    if clean_string(row.get("implementation_status")).startswith("implemented"):
        score += 3.0
        reasons.append("research sample implementation exists +3")
    forbidden = clean_string(row.get("forbidden_next_actions")).lower()
    if "tune_parameters" in forbidden:
        score += 2.0
        reasons.append("registry forbids tuning, supports bounded design +2")
    return score, reasons


def status_adjustment_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    status = clean_string(row.get("status") or row.get("current_status")).lower()
    if status == "research_sample_candidate":
        return 4.0, ["research_sample_candidate +4"]
    if status == "watchlist":
        return 1.0, ["watchlist +1"]
    if status == "needs_benchmark_delta_review":
        return -4.0, ["needs_benchmark_delta_review -4"]
    if "too_risky" in status:
        return -8.0, [f"{status} -8"]
    if "risk_budget_breach" in status:
        return -8.0, [f"{status} -8"]
    return 0.0, []


def score_candidate(row: dict[str, Any], metrics: dict[str, Any], root: Path) -> dict[str, Any]:
    component_functions = (
        ("evidence_quality_score", evidence_quality_score(row, metrics, root)),
        ("lineage_score", lineage_score(row)),
        ("profit_score", profit_score(metrics)),
        ("risk_score", risk_score(row, metrics)),
        ("distinctness_score", distinctness_score(row, metrics)),
        ("data_availability_score", data_availability_score(row, metrics)),
        ("bounded_design_feasibility_score", bounded_design_feasibility_score(row)),
        ("status_adjustment_score", status_adjustment_score(row)),
    )
    output: dict[str, Any] = {}
    reasons: list[str] = []
    total = 0.0
    for name, (score, local_reasons) in component_functions:
        output[name] = round(score, 4)
        total += score
        reasons.extend(local_reasons)
    metrics_source = clean_string(metrics.get("_source_csv"))
    output.update(
        {
            "strategy_id": strategy_id(row),
            "family": family_id(row),
            "status": clean_string(row.get("status") or row.get("current_status")),
            "triage_score": round(total, 4),
            "metric_source_csv": metrics_source,
            "median_180d_final_equity": metric_value(metrics, "180d_median_final_equity", "median_stop_enforced_final_equity"),
            "worst_drawdown": metric_value(metrics, "180d_worst_drawdown", "worst_max_drawdown", "max_drawdown_dollars"),
            "risk_buffer_vs_minus_600": metric_value(metrics, "risk_buffer_vs_minus_600"),
            "max_reference_correlation": max_reference_correlation(metrics),
            "delta_vs_active_vm": metric_value(metrics, "delta_vs_active_vm"),
            "delta_vs_active_dsr": metric_value(metrics, "delta_vs_active_dsr"),
            "delta_vs_spy_200d": metric_value(metrics, "delta_vs_spy_200d"),
            "required_local_data_symbols": extract_symbols(row, metrics, root),
            "expected_bounded_design_size_recommendation": "6_to_12_rows_max",
            "score_rationale": "; ".join(reasons),
        }
    )
    return output


def candidate_table_row(row: dict[str, Any], disposition: str, reasons: list[str], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id(row),
        "family": family_id(row),
        "status": clean_string(row.get("status") or row.get("current_status")),
        "latest_evidence_path": clean_string(row.get("latest_evidence_path")),
        "disposition": disposition,
        "exclusion_reasons": "; ".join(reasons),
        "triage_score": score.get("triage_score", ""),
        "metric_source_csv": score.get("metric_source_csv", ""),
        "median_180d_final_equity": score.get("median_180d_final_equity", ""),
        "worst_drawdown": score.get("worst_drawdown", ""),
        "risk_buffer_vs_minus_600": score.get("risk_buffer_vs_minus_600", ""),
        "max_reference_correlation": score.get("max_reference_correlation", ""),
        "delta_vs_active_vm": score.get("delta_vs_active_vm", ""),
        "delta_vs_active_dsr": score.get("delta_vs_active_dsr", ""),
        "delta_vs_spy_200d": score.get("delta_vs_spy_200d", ""),
        "required_local_data_symbols": score.get("required_local_data_symbols", ""),
        "expected_bounded_design_size_recommendation": score.get("expected_bounded_design_size_recommendation", ""),
    }


def build_triage(root: Path) -> dict[str, Any]:
    registry = read_yaml(root / "strategy_lab" / "strategy_registry.yaml")
    queue = read_yaml(root / "strategy_lab" / "research_os" / "research" / "research_queue.yaml")
    ledger = read_yaml(root / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml")
    research_state = read_json(root / "evidence" / "research_state" / "latest" / "research_state_manifest.json")
    queue_resolution = read_json(
        root
        / "evidence"
        / "research_recovery"
        / "profit_oriented_queue_resolution_after_high_return_robustness"
        / "latest"
        / "queue_resolution_manifest.json"
    )

    rows = [row for row in registry_rows(registry) if is_research_sample_review(row)]
    ledger_entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    ledger_by_family = {clean_string(entry.get("family_id")): entry for entry in ledger_entries if isinstance(entry, dict)}
    metrics = load_metric_lookup(root, rows)

    candidate_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    ranked_rows: list[dict[str, Any]] = []

    for row in rows:
        reasons = exclusion_reasons(row, ledger_by_family)
        item_metrics = metrics.get(strategy_id(row), {})
        score = score_candidate(row, item_metrics, root) if not reasons else {}
        if reasons:
            excluded = candidate_table_row(row, "excluded", reasons, score)
            excluded_rows.append(excluded)
            candidate_rows.append(excluded)
            continue
        ranked_rows.append(score)
        candidate_rows.append(candidate_table_row(row, "eligible_ranked", [], score))

    ranked_rows.sort(key=lambda item: (-float(item["triage_score"]), item["family"], item["strategy_id"]))
    for index, row in enumerate(ranked_rows, start=1):
        row["rank"] = index

    top_score = float(ranked_rows[0]["triage_score"]) if ranked_rows else 0.0
    second_score = float(ranked_rows[1]["triage_score"]) if len(ranked_rows) > 1 else None
    score_margin_to_second = top_score - second_score if second_score is not None else top_score
    ambiguous_top = [
        row
        for row in ranked_rows
        if top_score - float(row["triage_score"]) < CLEAR_WINNER_SCORE_MARGIN
    ]
    clear_winner = bool(
        ranked_rows
        and top_score >= CLEAR_WINNER_MIN_SCORE
        and len(ambiguous_top) == 1
        and (second_score is None or score_margin_to_second >= CLEAR_WINNER_SCORE_MARGIN)
    )
    selected = ranked_rows[0] if clear_winner else None
    selected_family = selected["family"] if selected else "none"
    selected_strategy = selected["strategy_id"] if selected else "none"
    next_action = f"design_{selected_family}_bounded_lane" if selected else NEXT_ACTION_SHORTLIST

    return {
        "candidate_rows": candidate_rows,
        "excluded_rows": excluded_rows,
        "ranked_rows": ranked_rows,
        "selected": selected,
        "manifest_context": {
            "registry_inspected": True,
            "roadmap_inspected": (root / "strategy_lab" / "RESEARCH_ROADMAP.md").exists(),
            "queue_inspected": bool(queue),
            "ledger_inspected": bool(ledger),
            "research_state_inspected": bool(research_state),
            "queue_exhaustion_packet_inspected": bool(queue_resolution),
            "research_state_next_family": research_state.get("next_family", research_state.get("research_state_next_family", "")),
            "research_state_next_action": research_state.get("next_action", research_state.get("research_state_next_action", "")),
            "active_queue_next_action": (
                queue.get("active_bounded_research_task", {}).get("next_action", "")
                if isinstance(queue.get("active_bounded_research_task"), dict)
                else ""
            ),
            "queue_resolution_next_action": queue_resolution.get("next_action", ""),
            "total_research_sample_review_rows_inspected": len(rows),
            "rows_excluded": len(excluded_rows),
            "rows_eligible_after_filters": len(ranked_rows),
            "top_ranked_candidates": [row["strategy_id"] for row in ranked_rows[:10]],
            "ambiguous_top_candidate_ids": [row["strategy_id"] for row in ambiguous_top],
            "top_ranked_score": round(top_score, 4),
            "score_margin_to_second": round(score_margin_to_second, 4) if second_score is not None else "",
            "clear_winner_found": clear_winner,
            "selected_strategy_id": selected_strategy,
            "selected_family": selected_family,
            "selected_evidence_paths": selected["metric_source_csv"] if selected else "",
            "expected_bounded_design_size_recommendation": "6_to_12_rows_max" if selected else "not_selected",
            "next_action": next_action,
        },
    }


def manifest_payload(created: str, output: Path, triage: dict[str, Any]) -> dict[str, Any]:
    context = triage["manifest_context"]
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "registry_research_sample_triage_only": True,
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "existing_saved_evidence_metrics_read": True,
        "new_families_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_used": False,
        "shorting_used": False,
        "options_used": False,
        "direct_futures_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "completed_high_return_tactical_excluded": True,
        "completed_commodity_excluded": True,
        "completed_macro_gld_excluded": True,
        "completed_volatility_throttle_excluded": True,
        "managed_futures_excluded": True,
        "diagnostic_evidence_treated_as_deployment_approval": False,
        **context,
    }


def guardrail_check(manifest: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "triage_only": manifest["registry_research_sample_triage_only"] is True,
        "no_research_execution": manifest["new_research_batch_run"] is False
        and manifest["new_strategy_discovery_run"] is False
        and manifest["new_backtests_run"] is False
        and manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_family_variant_grid": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_disallowed_mechanics": manifest["leverage_used"] is False
        and manifest["shorting_used"] is False
        and manifest["options_used"] is False
        and manifest["direct_futures_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "excluded_completed_lanes": manifest["completed_high_return_tactical_excluded"] is True
        and manifest["completed_commodity_excluded"] is True
        and manifest["completed_macro_gld_excluded"] is True
        and manifest["completed_volatility_throttle_excluded"] is True
        and manifest["managed_futures_excluded"] is True,
        "next_action_valid": manifest["next_action"] == NEXT_ACTION_SHORTLIST
        or (
            manifest["next_action"].startswith("design_")
            and manifest["next_action"].endswith("_bounded_lane")
            and manifest["clear_winner_found"] is True
        ),
    }
    checks["guardrails_passed"] = all(checks.values())
    return checks


def triage_summary_md(manifest: dict[str, Any], ranked_rows: list[dict[str, Any]]) -> str:
    top_lines = []
    for row in ranked_rows[:10]:
        top_lines.append(
            f"- Rank {row['rank']}: `{row['strategy_id']}` / `{row['family']}` score `{row['triage_score']}` "
            f"status `{row['status']}`"
        )
    top_text = "\n".join(top_lines) if top_lines else "- No eligible rows after hard exclusions."
    selected_text = (
        f"Selected candidate: `{manifest['selected_strategy_id']}` / `{manifest['selected_family']}`"
        if manifest["clear_winner_found"]
        else "Selected candidate: `none`; top rows are too close for a deterministic single-candidate choice."
    )
    return f"""# Profit-Oriented Registry Research-Sample Triage

Total `research_sample_review` rows inspected: `{manifest['total_research_sample_review_rows_inspected']}`

Rows excluded: `{manifest['rows_excluded']}`

Rows eligible after filters: `{manifest['rows_eligible_after_filters']}`

{selected_text}

Top score: `{manifest['top_ranked_score']}`

Score margin to second: `{manifest['score_margin_to_second']}`

Clear winner found: `{manifest['clear_winner_found']}`

Top-ranked candidates:

{top_text}

This packet reads registry/source-of-truth state and saved evidence metrics only. No backtest, strategy discovery, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live path, or real-money path was run.

Exact next action: `{manifest['next_action']}`
"""


def selected_candidate_report_md(manifest: dict[str, Any], selected: dict[str, Any] | None) -> str:
    if selected is None:
        return """# Selected Candidate Report

No single bounded-design candidate was selected.

The deterministic ranking did not produce exactly one clearly highest-ranked row under the required margin rule. See `ambiguity_no_safe_candidate_report.md`.
"""
    return f"""# Selected Candidate Report

Selected strategy ID: `{selected['strategy_id']}`

Selected family: `{selected['family']}`

Evidence path supporting selection: `{selected['metric_source_csv']}`

Triage score: `{selected['triage_score']}`

Expected bounded design size recommendation: `{selected['expected_bounded_design_size_recommendation']}`

Reason suitable for bounded design:

- Highest score above `{CLEAR_WINNER_MIN_SCORE}`.
- Score margin to second is at least `{CLEAR_WINNER_SCORE_MARGIN}`.
- Existing saved evidence and registry fields support a bounded, non-promotable design step.

No design was created in this triage task.
"""


def ambiguity_report_md(manifest: dict[str, Any], ranked_rows: list[dict[str, Any]]) -> str:
    top_ids = manifest["ambiguous_top_candidate_ids"]
    lines = [
        "# Ambiguity / No-Safe-Candidate Report",
        "",
        "No single registry row was selected because the top-ranked rows did not clear the deterministic separation rule.",
        "",
        f"Clear-winner rule: score >= `{CLEAR_WINNER_MIN_SCORE}` and margin to second/top ambiguity group >= `{CLEAR_WINNER_SCORE_MARGIN}`.",
        "",
        f"Top score: `{manifest['top_ranked_score']}`",
        "",
        f"Score margin to second: `{manifest['score_margin_to_second']}`",
        "",
        "Ambiguous top candidate IDs:",
    ]
    for item_id in top_ids:
        row = next((candidate for candidate in ranked_rows if candidate["strategy_id"] == item_id), None)
        if row:
            lines.append(
                f"- `{row['strategy_id']}` / `{row['family']}` score `{row['triage_score']}` status `{row['status']}`"
            )
    lines.extend(
        [
            "",
            "Required direction input: choose one family/row from this shortlist for a bounded design, or authorize a different deterministic tie-breaker.",
            "",
            "No strategy run, design, promotion, paper-forward activation, or candidate_exhaustive step was executed.",
        ]
    )
    return "\n".join(lines) + "\n"


def next_action_md(next_action: str) -> str:
    return f"""# Registry Triage Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path, triage: dict[str, Any]) -> dict[str, Any]:
    required_names = list(REQUIRED_FILES_ALWAYS) + ["selected_candidate_report.md"]
    if not manifest["clear_winner_found"]:
        required_names.append("ambiguity_no_safe_candidate_report.md")
    required = {name: (output / name).exists() for name in required_names}
    required["triage_consistency_check.json"] = True
    guardrails = read_json(output / "guardrail_checklist.json")
    excluded_count = len(triage["excluded_rows"])
    ranked_count = len(triage["ranked_rows"])
    total = manifest["total_research_sample_review_rows_inspected"]
    checks = {
        "triage_only": manifest["registry_research_sample_triage_only"] is True,
        "sources_inspected": manifest["registry_inspected"] is True
        and manifest["roadmap_inspected"] is True
        and manifest["queue_inspected"] is True
        and manifest["ledger_inspected"] is True
        and manifest["research_state_inspected"] is True
        and manifest["queue_exhaustion_packet_inspected"] is True,
        "row_counts_reconcile": excluded_count + ranked_count == total,
        "research_sample_rows_inspected": total >= 1,
        "guardrails_passed": guardrails.get("guardrails_passed") is True,
        "required_files_present": all(required.values()),
        "required_files": required,
        "next_action_valid": manifest["next_action"] == NEXT_ACTION_SHORTLIST
        or (
            manifest["next_action"].startswith("design_")
            and manifest["next_action"].endswith("_bounded_lane")
            and manifest["clear_winner_found"] is True
        ),
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, triage: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, triage)
    ranked_rows = triage["ranked_rows"]
    selected = triage["selected"]

    write_json(output / "triage_manifest.json", manifest)
    write_csv(output / "registry_candidate_table.csv", triage["candidate_rows"], list(REGISTRY_CANDIDATE_FIELDS))
    write_csv(output / "excluded_candidate_table.csv", triage["excluded_rows"], list(REGISTRY_CANDIDATE_FIELDS))
    write_csv(output / "ranking_scoring_table.csv", ranked_rows, list(RANKING_FIELDS))
    write_text(output / "selected_candidate_report.md", selected_candidate_report_md(manifest, selected))
    if not selected:
        write_text(output / "ambiguity_no_safe_candidate_report.md", ambiguity_report_md(manifest, ranked_rows))
    write_json(output / "guardrail_checklist.json", guardrail_check(manifest))
    write_text(output / "triage_summary.md", triage_summary_md(manifest, ranked_rows))
    write_text(output / "registry_triage_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output, triage)
    write_json(output / "triage_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    triage = build_triage(root)
    return write_outputs(root, created, triage)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "total_research_sample_review_rows_inspected": result["total_research_sample_review_rows_inspected"],
                "rows_excluded": result["rows_excluded"],
                "rows_eligible_after_filters": result["rows_eligible_after_filters"],
                "clear_winner_found": result["clear_winner_found"],
                "selected_strategy_id": result["selected_strategy_id"],
                "selected_family": result["selected_family"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
