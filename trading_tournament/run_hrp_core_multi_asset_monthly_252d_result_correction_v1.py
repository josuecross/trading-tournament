from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
EXPLORATORY_ID = "hrp_core_multi_asset_monthly_252d_exploratory_v1"
CORRECTION_ID = "hrp_core_multi_asset_monthly_252d_result_correction_v1"
EXACT_STATUS = "HRP_CORE_MULTI_ASSET_MONTHLY_252D_NO_ADVANCEMENT"
PREVIOUS_CLASSIFICATION = "WORTH_DEEPER_RESEARCH"
CORRECTED_CLASSIFICATION = "CONTROL_WEAK"
EXACT_COMBINATION_STATUS = "NO_ADVANCEMENT"
EXPLORATORY_DIR = ROOT / "reports" / "strategy_research" / EXPLORATORY_ID
CORRECTION_DIR = ROOT / "reports" / "strategy_research" / CORRECTION_ID

RAW_ARTIFACTS = (
    "metrics.csv",
    "monthly_weights.csv",
    "monthly_clusters.jsonl",
    "risk_contributions.csv",
    "trial_registry.csv",
    "identity_equivalence.csv",
    "failure_registry.csv",
    "rebalance_failures.csv",
)


def main() -> None:
    CORRECTION_DIR.mkdir(parents=True, exist_ok=True)
    raw_hashes_before = raw_artifact_hashes()
    metrics = read_csv(EXPLORATORY_DIR / "metrics.csv")
    trial_rows = [row for row in metrics if row.get("row_type") == "trial"]
    comparison_rows = control_comparison_rows(trial_rows)
    stability = cluster_stability_interpretation()

    classification = {
        "artifact_id": CORRECTION_ID,
        "corrected_at_utc": datetime.now(UTC).isoformat(),
        "lineage": {
            "exploratory_artifact_id": EXPLORATORY_ID,
            "exploratory_artifact_path": relative(EXPLORATORY_DIR),
        },
        "previous_classification": PREVIOUS_CLASSIFICATION,
        "corrected_classification": CORRECTED_CLASSIFICATION,
        "exact_combination_status": EXACT_COMBINATION_STATUS,
        "exact_strategy_disposition": EXACT_STATUS,
        "adaptation_label": "methodology_correction",
        "reason": (
            "HRP improved downside versus equal weight but failed to improve meaningfully versus "
            "inverse variance and incurred higher turnover"
        ),
        "raw_artifact_hashes_before_correction": raw_hashes_before,
        "raw_evidence_preserved": True,
        "performance_rerun": False,
        "parameter_or_universe_variation": False,
        "promotion_or_paper_demo_status": False,
    }

    write_json(CORRECTION_DIR / "classification_correction.json", classification)
    write_csv(CORRECTION_DIR / "control_comparison.csv", comparison_rows, control_comparison_fields())
    write_text(CORRECTION_DIR / "cluster_stability_interpretation.md", stability["markdown"])
    write_text(CORRECTION_DIR / "files_updated.md", files_updated_text(raw_hashes_before))
    write_json(CORRECTION_DIR / "manifest.json", manifest(classification, stability, comparison_rows))
    test_results_path = CORRECTION_DIR / "test_results.txt"
    if not test_results_path.exists():
        write_text(test_results_path, "Test command output is recorded after correction verification.\n")
    write_text(CORRECTION_DIR / "source_of_truth_update.md", correction_source_of_truth_update())
    write_text(EXPLORATORY_DIR / "comparison.md", corrected_comparison_text(trial_rows, comparison_rows))
    write_text(EXPLORATORY_DIR / "source_of_truth_update.md", corrected_exploratory_source_update())
    write_text(EXPLORATORY_DIR / "test_results.txt", corrected_exploratory_test_results())


def control_comparison_rows(trial_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    lookup = {(row["method_id"], int(row["cost_bps_per_side"])): row for row in trial_rows}
    rows: list[dict[str, Any]] = []
    for cost in (0, 5, 10):
        hrp = lookup[("HRP", cost)]
        for control in ("EQUAL_WEIGHT_1N", "INVERSE_VARIANCE_252D"):
            ctrl = lookup[(control, cost)]
            conclusion = (
                "HRP_LOWER_RISK_THAN_EQUAL_WEIGHT_BUT_LOWER_RETURN_AND_HIGHER_TURNOVER"
                if control == "EQUAL_WEIGHT_1N"
                else "HRP_NO_MEANINGFUL_ADVANTAGE_VERSUS_INVERSE_VARIANCE_HIGHER_TURNOVER"
            )
            rows.append(
                {
                    "cost_bps_per_side": cost,
                    "control_method": control,
                    "hrp_annualized_return": fnum(hrp["annualized_return"]),
                    "control_annualized_return": fnum(ctrl["annualized_return"]),
                    "annualized_return_diff": fnum(diff(hrp, ctrl, "annualized_return")),
                    "hrp_annualized_volatility": fnum(hrp["annualized_volatility"]),
                    "control_annualized_volatility": fnum(ctrl["annualized_volatility"]),
                    "annualized_volatility_diff": fnum(diff(hrp, ctrl, "annualized_volatility")),
                    "hrp_maximum_drawdown": fnum(hrp["maximum_drawdown"]),
                    "control_maximum_drawdown": fnum(ctrl["maximum_drawdown"]),
                    "maximum_drawdown_diff": fnum(diff(hrp, ctrl, "maximum_drawdown")),
                    "hrp_sharpe": fnum(hrp["sharpe"]),
                    "control_sharpe": fnum(ctrl["sharpe"]),
                    "sharpe_diff": fnum(diff(hrp, ctrl, "sharpe")),
                    "hrp_sortino": fnum(hrp["sortino"]),
                    "control_sortino": fnum(ctrl["sortino"]),
                    "sortino_diff": fnum(diff(hrp, ctrl, "sortino")),
                    "hrp_return_to_drawdown": fnum(hrp["return_to_drawdown"]),
                    "control_return_to_drawdown": fnum(ctrl["return_to_drawdown"]),
                    "return_to_drawdown_diff": fnum(diff(hrp, ctrl, "return_to_drawdown")),
                    "hrp_gross_traded_notional": fnum(hrp["gross_traded_notional"]),
                    "control_gross_traded_notional": fnum(ctrl["gross_traded_notional"]),
                    "gross_traded_notional_diff": fnum(diff(hrp, ctrl, "gross_traded_notional")),
                    "hrp_modeled_transaction_costs": fnum(hrp["modeled_transaction_costs"]),
                    "control_modeled_transaction_costs": fnum(ctrl["modeled_transaction_costs"]),
                    "modeled_transaction_cost_diff": fnum(diff(hrp, ctrl, "modeled_transaction_costs")),
                    "conclusion": conclusion,
                }
            )
    return rows


def cluster_stability_interpretation() -> dict[str, Any]:
    rows = [json.loads(line) for line in (EXPLORATORY_DIR / "monthly_clusters.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    full_signatures: list[str] = []
    leaf_orders: list[tuple[str, ...]] = []
    topologies: list[str] = []
    distance_signatures: list[str] = []
    for row in rows:
        linkage = row["linkage_result"]
        full_signatures.append(stable_hash({"linkage": linkage, "order": row["quasi_diagonal_asset_order"]}))
        leaf_orders.append(tuple(row["quasi_diagonal_asset_order"]))
        topologies.append(stable_hash([(int(item["left"]), int(item["right"]), int(item["sample_count"])) for item in linkage]))
        distance_signatures.append(stable_hash([round(float(item["distance"]), 12) for item in linkage]))
    comparisons = max(0, len(rows) - 1)
    full_changes = count_changes(full_signatures)
    leaf_order_changes = count_changes(leaf_orders)
    merge_topology_changes = count_changes(topologies)
    distance_changes = count_changes(distance_signatures)
    numerical_only_distance_changes = sum(
        1
        for idx in range(1, len(rows))
        if full_signatures[idx] != full_signatures[idx - 1]
        and leaf_orders[idx] == leaf_orders[idx - 1]
        and topologies[idx] == topologies[idx - 1]
        and distance_signatures[idx] != distance_signatures[idx - 1]
    )
    markdown = f"""# Cluster Stability Interpretation

Status: `NON_INTERPRETABLE_CLUSTER_SIGNATURE_METRIC` for the prior headline claim that the cluster signature changed in 218 of 219 months.

The existing `cluster_signature_hash` was constructed from:

```text
stable_hash({{"linkage": linkage_result, "order": quasi_diagonal_asset_order}})
```

`linkage_result` contains the merge child IDs, sample counts, and linkage distances. It does not contain covariance matrices, correlation matrices, or cluster variances directly, but it does contain continuously varying linkage distances. Therefore a full signature change cannot be read as proof that economic cluster membership changed every month.

Existing-artifact decomposition:

| measure | comparisons changed | total comparisons |
| --- | ---: | ---: |
| full signature including distances and leaf order | {full_changes} | {comparisons} |
| numerical linkage-distance signature | {distance_changes} | {comparisons} |
| leaf order | {leaf_order_changes} | {comparisons} |
| merge topology ignoring distances | {merge_topology_changes} | {comparisons} |
| numerical-only distance changes with same topology and order | {numerical_only_distance_changes} | {comparisons} |
| static economic sleeve membership | 0 | {comparisons} |

Correct interpretation: the old 218/219 figure mostly confirms that at least one linkage distance changed month to month. It does not prove that the HRP hierarchy, quasi-diagonal order, or static economic sleeve membership changed every month. The exact economic sleeve mapping used for reporting was static throughout the run.
"""
    return {
        "full_signature_changes": full_changes,
        "total_month_to_month_comparisons": comparisons,
        "distance_signature_changes": distance_changes,
        "leaf_order_changes": leaf_order_changes,
        "merge_topology_changes": merge_topology_changes,
        "numerical_only_distance_changes": numerical_only_distance_changes,
        "economic_sleeve_membership_changes": 0,
        "metric_status": "NON_INTERPRETABLE_CLUSTER_SIGNATURE_METRIC",
        "markdown": markdown,
    }


def corrected_comparison_text(trial_rows: list[dict[str, str]], comparison_rows: list[dict[str, Any]]) -> str:
    lookup = {(row["method_id"], int(row["cost_bps_per_side"])): row for row in trial_rows}
    lines = [
        f"# {EXPLORATORY_ID} Corrected Comparison",
        "",
        "Frozen evaluation range: `2008-05-01` to `2026-07-16`.",
        f"Previous exploratory classification: `{PREVIOUS_CLASSIFICATION}`.",
        f"Corrected exploratory classification: `{CORRECTED_CLASSIFICATION}`.",
        f"Exact strategy disposition: `{EXACT_STATUS}`.",
        "",
        "## Corrected Conclusion",
        "",
        "- HRP showed a meaningful risk reduction versus equal weight.",
        "- HRP did not show a meaningful advantage over inverse variance.",
        "- HRP had higher turnover and modeled costs than inverse variance.",
        "- The exact 252-day, monthly, ten-ETF HRP configuration does not advance.",
        "- This does not reject all HRP methods or other portfolio-construction strategies.",
        "- No parameter or universe variation is authorized from this result.",
        "",
        "## Trial Metrics",
        "",
        "| method | bps | total return | ann return | ann vol | max DD | Sharpe | Sortino | return/DD | gross traded notional | modeled costs |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cost in (0, 5, 10):
        for method in ("HRP", "EQUAL_WEIGHT_1N", "INVERSE_VARIANCE_252D"):
            row = lookup[(method, cost)]
            lines.append(
                f"| {method} | {cost} | {float(row['total_return']):.4f} | {float(row['annualized_return']):.4f} | "
                f"{float(row['annualized_volatility']):.4f} | {float(row['maximum_drawdown']):.4f} | "
                f"{float(row['sharpe']):.4f} | {float(row['sortino']):.4f} | {float(row['return_to_drawdown']):.4f} | "
                f"{float(row['gross_traded_notional']):.4f} | {float(row['modeled_transaction_costs']):.2f} |"
            )
    lines.extend(
        [
            "",
            "## Control Comparison",
            "",
            "The predeclared `CONTROL_WEAK` condition applies: HRP improves downside and diversification versus equal weight, but it does not improve meaningfully versus inverse variance. At both 5 and 10 bps, inverse variance has higher annual return, Sharpe, Sortino, and return-to-drawdown, while HRP has higher turnover and modeled costs. HRP's volatility advantage is small and maximum drawdown is slightly worse versus inverse variance.",
            "",
            "## Scope",
            "",
            "- Raw metrics, monthly weights, clusters, risk contributions, trial registry, Identity records, and failure registry are preserved.",
            "- No performance rerun, tuning, optional overlay, universe replacement, validation, promotion, or execution-connected action occurred for this correction.",
            f"- Correction artifact: `reports/strategy_research/{CORRECTION_ID}/`.",
        ]
    )
    return "\n".join(lines) + "\n"


def corrected_exploratory_source_update() -> str:
    return f"""# Source Of Truth Update

`{EXPLORATORY_ID}` completed its first bounded full-period exploratory run and was subsequently corrected by `{CORRECTION_ID}`.

- Frozen universe: `SPY, EFA, EEM, IYR, IEF, TLT, LQD, HYG, GLD, DBC`.
- Evaluation range: `2008-05-01` to `2026-07-16`.
- Registered runs: `12`.
- Previous exploratory classification: `{PREVIOUS_CLASSIFICATION}`.
- Corrected exploratory classification: `{CORRECTED_CLASSIFICATION}`.
- Exact strategy disposition: `{EXACT_STATUS}`.
- Research stage: `research_only_exploration`.
- Result: HRP reduced risk versus equal weight but did not establish meaningful superiority over inverse variance and had higher turnover/costs.
- No tuning, optional management overlay, universe replacement, validation, promotion, paper/demo/live action, or broker invocation occurred.

Project direction returns to external-source strategy discovery.
"""


def correction_source_of_truth_update() -> str:
    return f"""# Source Of Truth Update

Correction artifact `{CORRECTION_ID}` supersedes the exploratory packet's advancing interpretation for `{EXPLORATORY_ID}`.

- Previous classification: `{PREVIOUS_CLASSIFICATION}`.
- Corrected classification: `{CORRECTED_CLASSIFICATION}`.
- Exact combination status: `{EXACT_COMBINATION_STATUS}`.
- Exact strategy disposition: `{EXACT_STATUS}`.
- Reason: HRP improved downside versus equal weight but failed to improve meaningfully versus inverse variance and incurred higher turnover.
- Cluster-stability headline is qualified as `NON_INTERPRETABLE_CLUSTER_SIGNATURE_METRIC`.
- Raw exploratory evidence and lineage are preserved.
- No performance rerun, tuning, optional overlay, universe replacement, validation, promotion, paper/demo/live action, or broker invocation occurred.

Project direction returns to external-source strategy discovery.
"""


def corrected_exploratory_test_results() -> str:
    return f"""Command:
python run_hrp_core_multi_asset_monthly_252d_exploratory_v1.py

Original runner result:
original_runner_classification_superseded={PREVIOUS_CLASSIFICATION}
artifact_dir={EXPLORATORY_DIR}

Correction:
The original runner classification is superseded by `{CORRECTION_ID}`.
corrected_classification={CORRECTED_CLASSIFICATION}
exact_strategy_disposition={EXACT_STATUS}

Command:
python -m pytest tests\\test_hrp_engine_feasibility_v1.py tests\\test_hrp_core_multi_asset_monthly_252d_exploratory_v1.py tests\\test_position_sizing.py tests\\test_metrics.py tests\\test_risk_framework.py tests\\test_current_multi_asset_portfolio_accounting_blast_radius_v1.py -q

Prior result:
50 passed in 122.23s (0:02:02)

Scope guard:
No tuning, optional overlay, universe replacement, validation, promotion, paper/demo/live action, or broker invocation occurred.
"""


def files_updated_text(raw_hashes: dict[str, str]) -> str:
    lines = [
        "# Files Updated",
        "",
        "Updated reporting/source-of-truth artifacts:",
        "",
        f"- `{relative(EXPLORATORY_DIR / 'comparison.md')}`",
        f"- `{relative(EXPLORATORY_DIR / 'source_of_truth_update.md')}`",
        f"- `{relative(EXPLORATORY_DIR / 'test_results.txt')}`",
        "",
        "Created correction packet:",
        "",
        f"- `{relative(CORRECTION_DIR / 'classification_correction.json')}`",
        f"- `{relative(CORRECTION_DIR / 'control_comparison.csv')}`",
        f"- `{relative(CORRECTION_DIR / 'cluster_stability_interpretation.md')}`",
        f"- `{relative(CORRECTION_DIR / 'files_updated.md')}`",
        f"- `{relative(CORRECTION_DIR / 'manifest.json')}`",
        f"- `{relative(CORRECTION_DIR / 'test_results.txt')}`",
        f"- `{relative(CORRECTION_DIR / 'source_of_truth_update.md')}`",
        "",
        "Added correction tooling:",
        "",
        f"- `{relative(ROOT / 'run_hrp_core_multi_asset_monthly_252d_result_correction_v1.py')}`",
        f"- `{relative(ROOT / 'tests' / 'test_hrp_core_multi_asset_monthly_252d_result_correction_v1.py')}`",
        "",
        "Raw evidence preserved with hashes:",
        "",
    ]
    lines.extend([f"- `{name}`: `{digest}`" for name, digest in raw_hashes.items()])
    return "\n".join(lines) + "\n"


def manifest(classification: dict[str, Any], stability: dict[str, Any], comparison_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_id": CORRECTION_ID,
        "created_utc": datetime.now(UTC).isoformat(),
        "lineage": classification["lineage"],
        "previous_classification": PREVIOUS_CLASSIFICATION,
        "corrected_classification": CORRECTED_CLASSIFICATION,
        "exact_combination_status": EXACT_COMBINATION_STATUS,
        "exact_strategy_disposition": EXACT_STATUS,
        "control_comparison_row_count": len(comparison_rows),
        "cluster_stability": {key: value for key, value in stability.items() if key != "markdown"},
        "raw_artifact_hashes_after_correction": raw_artifact_hashes(),
        "performance_rerun": False,
        "strategy_logic_changed": False,
        "execution_connected_path_invoked": False,
    }


def raw_artifact_hashes() -> dict[str, str]:
    return {name: sha256_file(EXPLORATORY_DIR / name) for name in RAW_ARTIFACTS}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def control_comparison_fields() -> list[str]:
    return [
        "cost_bps_per_side",
        "control_method",
        "hrp_annualized_return",
        "control_annualized_return",
        "annualized_return_diff",
        "hrp_annualized_volatility",
        "control_annualized_volatility",
        "annualized_volatility_diff",
        "hrp_maximum_drawdown",
        "control_maximum_drawdown",
        "maximum_drawdown_diff",
        "hrp_sharpe",
        "control_sharpe",
        "sharpe_diff",
        "hrp_sortino",
        "control_sortino",
        "sortino_diff",
        "hrp_return_to_drawdown",
        "control_return_to_drawdown",
        "return_to_drawdown_diff",
        "hrp_gross_traded_notional",
        "control_gross_traded_notional",
        "gross_traded_notional_diff",
        "hrp_modeled_transaction_costs",
        "control_modeled_transaction_costs",
        "modeled_transaction_cost_diff",
        "conclusion",
    ]


def count_changes(values: list[Any]) -> int:
    return sum(1 for left, right in zip(values, values[1:]) if left != right)


def diff(left: dict[str, str], right: dict[str, str], field: str) -> float:
    return float(left[field]) - float(right[field])


def fnum(value: float | str) -> str:
    parsed = float(value)
    return f"{parsed:.12g}"


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def stable_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
