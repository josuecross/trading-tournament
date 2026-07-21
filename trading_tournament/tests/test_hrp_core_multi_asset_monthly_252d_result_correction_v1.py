from __future__ import annotations

import ast
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPLORATORY = ROOT / "reports" / "strategy_research" / "hrp_core_multi_asset_monthly_252d_exploratory_v1"
CORRECTION = ROOT / "reports" / "strategy_research" / "hrp_core_multi_asset_monthly_252d_result_correction_v1"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_raw_metrics_and_historical_records_remain_unchanged() -> None:
    correction = read_json(CORRECTION / "classification_correction.json")
    hashes = correction["raw_artifact_hashes_before_correction"]

    for name, expected in hashes.items():
        assert sha256_file(EXPLORATORY / name) == expected


def test_corrected_classification_and_exact_no_advancement_status() -> None:
    correction = read_json(CORRECTION / "classification_correction.json")

    assert correction["previous_classification"] == "WORTH_DEEPER_RESEARCH"
    assert correction["corrected_classification"] == "CONTROL_WEAK"
    assert correction["exact_combination_status"] == "NO_ADVANCEMENT"
    assert correction["exact_strategy_disposition"] == "HRP_CORE_MULTI_ASSET_MONTHLY_252D_NO_ADVANCEMENT"
    assert correction["performance_rerun"] is False


def test_no_downstream_summary_marks_exact_configuration_as_advancing() -> None:
    comparison = (EXPLORATORY / "comparison.md").read_text(encoding="utf-8")
    source_update = (EXPLORATORY / "source_of_truth_update.md").read_text(encoding="utf-8")
    correction_update = (CORRECTION / "source_of_truth_update.md").read_text(encoding="utf-8")

    assert "Corrected exploratory classification: `CONTROL_WEAK`" in comparison
    assert "Exact strategy disposition: `HRP_CORE_MULTI_ASSET_MONTHLY_252D_NO_ADVANCEMENT`" in comparison
    assert "Final exploratory classification: `WORTH_DEEPER_RESEARCH`" not in comparison
    assert "Final exploratory classification: `WORTH_DEEPER_RESEARCH`" not in source_update
    assert "Corrected classification: `CONTROL_WEAK`" in correction_update


def test_control_comparison_supports_control_weak_correction() -> None:
    rows = read_csv(CORRECTION / "control_comparison.csv")
    inv_5 = next(row for row in rows if row["control_method"] == "INVERSE_VARIANCE_252D" and row["cost_bps_per_side"] == "5")
    inv_10 = next(row for row in rows if row["control_method"] == "INVERSE_VARIANCE_252D" and row["cost_bps_per_side"] == "10")
    eq_5 = next(row for row in rows if row["control_method"] == "EQUAL_WEIGHT_1N" and row["cost_bps_per_side"] == "5")

    assert float(inv_5["annualized_return_diff"]) < 0.0
    assert float(inv_5["sharpe_diff"]) < 0.0
    assert float(inv_5["sortino_diff"]) < 0.0
    assert float(inv_5["return_to_drawdown_diff"]) < 0.0
    assert float(inv_5["gross_traded_notional_diff"]) > 0.0
    assert float(inv_10["annualized_return_diff"]) < 0.0
    assert float(inv_10["gross_traded_notional_diff"]) > 0.0
    assert float(eq_5["annualized_volatility_diff"]) < 0.0
    assert float(eq_5["maximum_drawdown_diff"]) > 0.0


def test_identity_and_trial_records_are_preserved() -> None:
    identity_rows = read_csv(EXPLORATORY / "identity_equivalence.csv")
    trial_rows = read_csv(EXPLORATORY / "trial_registry.csv")

    assert len(identity_rows) == 3
    assert all(row["equivalence_status"] == "PASS" for row in identity_rows)
    assert len(trial_rows) == 12
    assert all(row["status"] == "COMPLETED" for row in trial_rows)


def test_cluster_stability_metric_is_qualified() -> None:
    text = (CORRECTION / "cluster_stability_interpretation.md").read_text(encoding="utf-8")
    manifest = read_json(CORRECTION / "manifest.json")

    assert "NON_INTERPRETABLE_CLUSTER_SIGNATURE_METRIC" in text
    assert manifest["cluster_stability"]["full_signature_changes"] == 218
    assert manifest["cluster_stability"]["distance_signature_changes"] == 218
    assert manifest["cluster_stability"]["leaf_order_changes"] == 70
    assert manifest["cluster_stability"]["merge_topology_changes"] == 123
    assert manifest["cluster_stability"]["economic_sleeve_membership_changes"] == 0


def test_correction_script_does_not_import_performance_or_execution_paths() -> None:
    script = ROOT / "run_hrp_core_multi_asset_monthly_252d_result_correction_v1.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_roots = {
        "src",
        "strategy_lab",
        "run_hrp_core_multi_asset_monthly_252d_exploratory_v1",
        "alpaca",
        "broker",
        "brokers",
        "live",
        "paper",
        "demo",
    }
    assert not any(module.split(".")[0] in forbidden_roots for module in imported)
