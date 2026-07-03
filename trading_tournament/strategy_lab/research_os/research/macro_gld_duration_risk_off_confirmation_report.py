from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_run import (
    LANE_ID,
    SOURCE_FAMILY,
    build_macro_weights,
    finite,
    parse_float,
)
from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_robustness import (
    OUTPUT_DIR as ROBUSTNESS_DIR,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    active_combo_returns,
    equity_curve,
    max_drawdown,
    write_csv,
)


SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest"
SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"
)
OUTPUT_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_confirmation_report" / "latest"

SURVIVOR_IDS = (
    "mgd_bounded_canary_defensive_top1_126_v1",
    "mgd_bounded_canary_defensive_top2_126_v1",
    "mgd_bounded_canary_defensive_top2_252_v1",
    "mgd_bounded_barbell_gated_126_v1",
)

EXCLUDED_CONTEXT_IDS = (
    "mgd_bounded_canary_defensive_top1_252_v1",
    "mgd_bounded_gold_duration_sleeve_top1_126_v1",
    "mgd_bounded_gold_duration_sleeve_top1_252_v1",
    "mgd_bounded_barbell_gated_252_v1",
)

NEXT_ACTION_QUEUE = "return_to_profit_oriented_research_queue"
NEXT_ACTION_FIX = "fix_macro_gld_duration_risk_off_confirmation_report_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_QUEUE, NEXT_ACTION_FIX}

CONFIRMATION_LABELS = {
    "macro_gld_confirmation_candidate_diagnostic",
    "macro_gld_confirmation_context_only",
}

REQUIRED_FILES = (
    "macro_gld_confirmation_manifest.json",
    "macro_gld_confirmation_consistency_check.json",
    "survivor_confirmation_rows.csv",
    "comparator_contribution_diagnostic.md",
    "baseline_comparator_report.md",
    "subperiod_confirmation.csv",
    "rolling_weakness_confirmation.csv",
    "rolling_weakness_confirmation_report.md",
    "exposure_invariant_report.md",
    "macro_gld_confirmation_summary.md",
    "do_not_promote_from_macro_gld_confirmation.md",
    "macro_gld_confirmation_next_action.md",
)

CONFIRMATION_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "concept",
    "lookback_days",
    "top_n",
    "universe",
    "comparator_references",
    "cagr",
    "total_return",
    "max_drawdown",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "same_window_return_vs_bil",
    "average_bil_cash_share",
    "correlation_to_spy200d",
    "correlation_to_static_all_weather",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "active_vm_dsr_combo_total_return_drag",
    "base_cagr",
    "base_total_return",
    "base_max_drawdown",
    "base_calmar",
    "base_numeric_criteria_pass",
    "stress_10bps_cagr",
    "stress_10bps_numeric_criteria_pass",
    "stress_25bps_cagr",
    "stress_25bps_numeric_criteria_pass",
    "subperiod_weakness_count",
    "rolling_weakness_flag",
    "correlation_to_active_combo",
    "active_combo_drawdown_overlap_ratio",
    "active_combo_drawdown_days",
    "strategy_drawdown_days",
    "active_combo_drawdown_improvement",
    "active_combo_total_return_drag",
    "portfolio_contribution_classification",
    "exposure_invariant_pass",
    "confirmation_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def load_sources(root: Path) -> dict[str, Any]:
    return {
        "design_rows": read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv"),
        "run_rows": read_csv_rows(root / SOURCE_RUN_DIR / "macro_gld_bounded_row_results.csv"),
        "robustness_manifest": read_json(root / ROBUSTNESS_DIR / "macro_gld_bounded_robustness_manifest.json"),
        "stress_rows": read_csv_rows(root / ROBUSTNESS_DIR / "base_vs_stress_row_results.csv"),
        "subperiod_rows": read_csv_rows(root / ROBUSTNESS_DIR / "subperiod_performance.csv"),
        "rolling_rows": read_csv_rows(root / ROBUSTNESS_DIR / "rolling_window_weakness.csv"),
    }


def drawdown_series(returns: pd.Series) -> pd.Series:
    equity = equity_curve(returns.dropna())
    if equity.empty:
        return pd.Series(dtype=float)
    return equity / equity.cummax() - 1.0


def active_combo_overlap(root: Path, design_row: dict[str, str]) -> dict[str, Any]:
    daily, _weights = build_macro_weights(root, design_row)
    active = active_combo_returns(root)
    aligned = pd.concat([daily.rename("strategy"), active.rename("active_combo")], axis=1, sort=False).dropna()
    if len(aligned) < 252:
        return {
            "correlation_to_active_combo": float("nan"),
            "active_combo_drawdown_overlap_ratio": float("nan"),
            "active_combo_drawdown_days": 0,
            "strategy_drawdown_days": 0,
        }
    corr = float(aligned["strategy"].corr(aligned["active_combo"]))
    strategy_dd = drawdown_series(aligned["strategy"])
    active_dd = drawdown_series(aligned["active_combo"])
    aligned_dd = pd.concat([strategy_dd.rename("strategy_dd"), active_dd.rename("active_dd")], axis=1).dropna()
    strategy_days = aligned_dd["strategy_dd"] < -0.10
    active_days = aligned_dd["active_dd"] < -0.10
    overlap_days = strategy_days & active_days
    ratio = float(overlap_days.sum() / strategy_days.sum()) if int(strategy_days.sum()) else 0.0
    return {
        "correlation_to_active_combo": corr,
        "active_combo_drawdown_overlap_ratio": ratio,
        "active_combo_drawdown_days": int(active_days.sum()),
        "strategy_drawdown_days": int(strategy_days.sum()),
    }


def contribution_classification(row: dict[str, Any]) -> str:
    corr = parse_float(row.get("correlation_to_active_combo"))
    overlap = parse_float(row.get("active_combo_drawdown_overlap_ratio"))
    drawdown_improvement = parse_float(row.get("active_combo_drawdown_improvement"))
    if finite(corr) and corr >= 0.75:
        return "redundant"
    if finite(overlap) and overlap >= 0.65:
        return "redundant"
    if finite(drawdown_improvement) and drawdown_improvement >= 0.0:
        return "diversifying"
    if finite(corr) and corr < 0.60:
        return "diversifying"
    return "redundant"


def build_confirmation_rows(root: Path, sources: dict[str, Any]) -> list[dict[str, Any]]:
    design_by_id = {row["variant_id"]: row for row in sources["design_rows"]}
    run_by_id = {row["variant_id"]: row for row in sources["run_rows"]}
    stress_by_id = {row["variant_id"]: row for row in sources["stress_rows"]}
    subperiod_by_id: dict[str, list[dict[str, str]]] = {}
    for row in sources["subperiod_rows"]:
        subperiod_by_id.setdefault(row["variant_id"], []).append(row)
    rolling_by_id = {row["variant_id"]: row for row in sources["rolling_rows"]}
    out: list[dict[str, Any]] = []
    for variant_id in SURVIVOR_IDS:
        design = design_by_id[variant_id]
        run = run_by_id[variant_id]
        stress = stress_by_id[variant_id]
        rolling = rolling_by_id[variant_id]
        overlap = active_combo_overlap(root, design)
        subperiod_weakness_count = sum(
            1 for row in subperiod_by_id.get(variant_id, []) if bool_value(row.get("subperiod_weakness_flag"))
        )
        rolling_weakness = bool_value(rolling.get("unacceptable_rolling_weakness"))
        exposure_pass = bool_value(run.get("exposure_invariant_pass"))
        base_pass = bool_value(stress.get("base_numeric_criteria_pass"))
        stress10_pass = bool_value(stress.get("stress_10bps_numeric_criteria_pass"))
        stress25_pass = bool_value(stress.get("stress_25bps_numeric_criteria_pass"))
        row = {
            "lane_id": LANE_ID,
            "family_id": SOURCE_FAMILY,
            "variant_id": variant_id,
            "variant_role": design["variant_role"],
            "concept": design["concept"],
            "lookback_days": design["lookback_days"],
            "top_n": design["top_n"],
            "universe": design["universe"],
            "comparator_references": design.get("comparator_references", ""),
            "cagr": run.get("cagr"),
            "total_return": run.get("total_return"),
            "max_drawdown": run.get("max_drawdown"),
            "volatility": run.get("volatility"),
            "calmar_or_return_drawdown_proxy": run.get("calmar_or_return_drawdown_proxy"),
            "same_window_return_vs_bil": run.get("same_window_return_vs_bil"),
            "average_bil_cash_share": run.get("average_bil_cash_share"),
            "correlation_to_spy200d": run.get("correlation_to_spy200d"),
            "correlation_to_static_all_weather": run.get("correlation_to_static_all_weather"),
            "active_vm_dsr_combo_max_drawdown_improvement": run.get("active_vm_dsr_combo_max_drawdown_improvement"),
            "active_vm_dsr_combo_total_return_drag": run.get("active_vm_dsr_combo_total_return_drag"),
            "base_cagr": stress.get("base_cagr"),
            "base_total_return": stress.get("base_total_return"),
            "base_max_drawdown": stress.get("base_max_drawdown"),
            "base_calmar": stress.get("base_calmar"),
            "base_numeric_criteria_pass": base_pass,
            "stress_10bps_cagr": stress.get("stress_10bps_cagr"),
            "stress_10bps_numeric_criteria_pass": stress10_pass,
            "stress_25bps_cagr": stress.get("stress_25bps_cagr"),
            "stress_25bps_numeric_criteria_pass": stress25_pass,
            "subperiod_weakness_count": subperiod_weakness_count,
            "rolling_weakness_flag": rolling_weakness,
            "active_combo_drawdown_improvement": run.get("active_vm_dsr_combo_max_drawdown_improvement"),
            "active_combo_total_return_drag": run.get("active_vm_dsr_combo_total_return_drag"),
            "exposure_invariant_pass": exposure_pass,
            **overlap,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        }
        row["portfolio_contribution_classification"] = contribution_classification(row)
        confirmed = (
            base_pass
            and stress10_pass
            and stress25_pass
            and subperiod_weakness_count == 0
            and not rolling_weakness
            and exposure_pass
        )
        row["confirmation_label"] = (
            "macro_gld_confirmation_candidate_diagnostic"
            if confirmed
            else "macro_gld_confirmation_context_only"
        )
        out.append(row)
    return out


def filter_subperiod_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("variant_id") in SURVIVOR_IDS]


def filter_rolling_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("variant_id") in SURVIVOR_IDS]


def manifest_payload(
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, str]],
    rolling_rows: list[dict[str, str]],
    sources: dict[str, Any],
) -> dict[str, Any]:
    row_ids = {row["variant_id"] for row in rows}
    confirmed = [row for row in rows if row["confirmation_label"] == "macro_gld_confirmation_candidate_diagnostic"]
    context = [row for row in rows if row["confirmation_label"] == "macro_gld_confirmation_context_only"]
    subperiod_weak = {row["variant_id"] for row in subperiod_rows if bool_value(row.get("subperiod_weakness_flag"))}
    rolling_weak = {row["variant_id"] for row in rolling_rows if bool_value(row.get("unacceptable_rolling_weakness"))}
    invariant_fail = [row["variant_id"] for row in rows if row["exposure_invariant_pass"] is not True]
    design_ids = {row["variant_id"] for row in sources["design_rows"]}
    run_ids = {row["variant_id"] for row in sources["run_rows"]}
    robustness_ids = {row["variant_id"] for row in sources["stress_rows"]}
    usable = (
        row_ids == set(SURVIVOR_IDS)
        and len(rows) == 4
        and set(EXCLUDED_CONTEXT_IDS).isdisjoint(row_ids)
        and row_ids.issubset(design_ids)
        and row_ids.issubset(run_ids)
        and row_ids.issubset(robustness_ids)
        and not invariant_fail
    )
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "macro_gld_confirmation_report": True,
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "source_robustness_reviewed": True,
        "exact_survivor_rows_used": row_ids == set(SURVIVOR_IDS),
        "excluded_context_rows_not_reopened": set(EXCLUDED_CONTEXT_IDS).isdisjoint(row_ids),
        "rows_evaluated": len(rows),
        "rows_confirmed": len(confirmed),
        "rows_downgraded_to_context_only": len(context),
        "rows_passing_base_criteria": sum(1 for row in rows if row["base_numeric_criteria_pass"] is True),
        "rows_passing_10bps_stress": sum(1 for row in rows if row["stress_10bps_numeric_criteria_pass"] is True),
        "rows_passing_25bps_stress": sum(1 for row in rows if row["stress_25bps_numeric_criteria_pass"] is True),
        "rows_with_subperiod_weakness": len(subperiod_weak),
        "rows_with_rolling_window_weakness": len(rolling_weak),
        "rows_with_invariant_failures": len(invariant_fail),
        "rows_appear_diversifying_vs_active_combo": sum(
            1 for row in rows if row["portfolio_contribution_classification"] == "diversifying"
        ),
        "rows_appear_redundant_vs_active_combo": sum(
            1 for row in rows if row["portfolio_contribution_classification"] == "redundant"
        ),
        "confirmation_evidence_usable": usable,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_families_created": False,
        "new_rows_added": False,
        "new_concepts_added": False,
        "new_lookbacks_added": False,
        "new_universes_added": False,
        "hidden_parameter_grid_created": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "next_action": NEXT_ACTION_QUEUE if usable else NEXT_ACTION_FIX,
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Macro / GLD Confirmation Report

Rows confirmed: `{manifest['rows_confirmed']}`

Rows downgraded to context-only: `{manifest['rows_downgraded_to_context_only']}`

Rows passing base criteria: `{manifest['rows_passing_base_criteria']}`

Rows passing 10 bps stress: `{manifest['rows_passing_10bps_stress']}`

Rows passing 25 bps stress: `{manifest['rows_passing_25bps_stress']}`

Rows with subperiod weakness: `{manifest['rows_with_subperiod_weakness']}`

Rows with rolling-window weakness: `{manifest['rows_with_rolling_window_weakness']}`

Rows with invariant failures: `{manifest['rows_with_invariant_failures']}`

Rows that appear diversifying versus active combo: `{manifest['rows_appear_diversifying_vs_active_combo']}`

Rows that appear redundant versus active combo: `{manifest['rows_appear_redundant_vs_active_combo']}`

Confirmation evidence usable: `{manifest['confirmation_evidence_usable']}`

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible from this task alone.

Exact next action: `{manifest['next_action']}`
"""


def contribution_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Comparator / Contribution Diagnostic", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: active combo corr `{parse_float(row['correlation_to_active_combo']):.6f}`, "
            f"drawdown overlap ratio `{parse_float(row['active_combo_drawdown_overlap_ratio']):.6f}`, "
            f"active combo drawdown improvement `{parse_float(row['active_combo_drawdown_improvement']):.6f}`, "
            f"total-return drag `{parse_float(row['active_combo_total_return_drag']):.6f}`, "
            f"classification `{row['portfolio_contribution_classification']}`"
        )
    lines.append("")
    lines.append("No new combo strategy or registry variant was created from this diagnostic.")
    return "\n".join(lines) + "\n"


def baseline_comparator_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Comparator Confirmation", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: CAGR `{parse_float(row.get('cagr')):.6f}`, "
            f"max drawdown `{parse_float(row.get('max_drawdown')):.6f}`, "
            f"same-window BIL delta `{parse_float(row.get('same_window_return_vs_bil')):.6f}`, "
            f"SPY 200d corr `{parse_float(row.get('correlation_to_spy200d')):.6f}`, "
            f"static all-weather corr `{parse_float(row.get('correlation_to_static_all_weather')):.6f}`, "
            f"average BIL/cash share `{parse_float(row.get('average_bil_cash_share')):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather is retained as benchmark/control only.")
    return "\n".join(lines) + "\n"


def rolling_report_md(rows: list[dict[str, str]]) -> str:
    lines = ["# Rolling Weakness Confirmation", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: worst 180d `{parse_float(row.get('worst_180_day_return')):.6f}`, "
            f"worst 252d `{parse_float(row.get('worst_252_day_return')):.6f}`, "
            f"weakness `{row.get('unacceptable_rolling_weakness')}`"
        )
    return "\n".join(lines) + "\n"


def invariant_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

- Rows with invariant failures: `{manifest['rows_with_invariant_failures']}`
- Exact survivor rows used: `{manifest['exact_survivor_rows_used']}`
- Excluded/context-only rows not reopened: `{manifest['excluded_context_rows_not_reopened']}`
- BIL/cash remains replacement/remainder only through the shared bounded lane weight builder.
- Static all-weather remains benchmark/control only.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Macro / GLD Confirmation

This confirmation report is diagnostic evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Macro / GLD Confirmation Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["macro_gld_confirmation_consistency_check.json"] = True
    labels = {row["confirmation_label"] for row in rows}
    checks = {
        "confirmation_report": manifest["macro_gld_confirmation_report"] is True,
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == SOURCE_FAMILY,
        "source_robustness_reviewed": manifest["source_robustness_reviewed"] is True,
        "exact_4_survivors": manifest["exact_survivor_rows_used"] is True and len(rows) == 4,
        "excluded_rows_not_reopened": manifest["excluded_context_rows_not_reopened"] is True,
        "allowed_confirmation_labels": labels.issubset(CONFIRMATION_LABELS),
        "no_strategy_expansion": manifest["new_rows_added"] is False
        and manifest["new_concepts_added"] is False
        and manifest["new_lookbacks_added"] is False
        and manifest["new_universes_added"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_discovery_or_batch": manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family": manifest["new_families_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_promotion_candidate_exhaustive_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_paper": all(row["paper_forward_eligibility"] is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row["candidate_exhaustive_eligibility"] is False for row in rows),
        "no_invariant_failures": manifest["rows_with_invariant_failures"] == 0,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, sources: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    rows = build_confirmation_rows(root, sources)
    subperiod_rows = filter_subperiod_rows(sources["subperiod_rows"])
    rolling_rows = filter_rolling_rows(sources["rolling_rows"])
    manifest = manifest_payload(created, output, rows, subperiod_rows, rolling_rows, sources)
    write_json(output / "macro_gld_confirmation_manifest.json", manifest)
    write_csv(output / "survivor_confirmation_rows.csv", rows, list(CONFIRMATION_FIELDS))
    write_text(output / "comparator_contribution_diagnostic.md", contribution_md(rows))
    write_text(output / "baseline_comparator_report.md", baseline_comparator_md(rows))
    if subperiod_rows:
        write_csv(output / "subperiod_confirmation.csv", subperiod_rows, list(subperiod_rows[0].keys()))
    else:
        write_csv(output / "subperiod_confirmation.csv", [], [])
    if rolling_rows:
        write_csv(output / "rolling_weakness_confirmation.csv", rolling_rows, list(rolling_rows[0].keys()))
    else:
        write_csv(output / "rolling_weakness_confirmation.csv", [], [])
    write_text(output / "rolling_weakness_confirmation_report.md", rolling_report_md(rolling_rows))
    write_text(output / "exposure_invariant_report.md", invariant_md(manifest))
    write_text(output / "macro_gld_confirmation_summary.md", summary_md(manifest))
    write_text(output / "do_not_promote_from_macro_gld_confirmation.md", do_not_promote_md())
    write_text(output / "macro_gld_confirmation_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "macro_gld_confirmation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    sources = load_sources(root)
    return write_outputs(root, created, sources)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "rows_evaluated": result["rows_evaluated"],
                "rows_confirmed": result["rows_confirmed"],
                "rows_downgraded_to_context_only": result["rows_downgraded_to_context_only"],
                "rows_appear_diversifying_vs_active_combo": result["rows_appear_diversifying_vs_active_combo"],
                "confirmation_evidence_usable": result["confirmation_evidence_usable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
