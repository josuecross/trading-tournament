from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import current_multi_asset_portfolio_accounting_blast_radius_v1 as blast


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "current_multi_asset_portfolio_accounting_blast_radius_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_blast_radius_evidence() -> dict[str, object]:
    return blast.run(ROOT)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_blast_radius_files_exist() -> None:
    required = {
        "decision.json",
        "decision.md",
        "consumer_inventory.csv",
        "accounting_pattern_matches.csv",
        "consumer_classifications.csv",
        "active_combo_accounting_review.csv",
        "dsr_accounting_review.csv",
        "vm_accounting_review.csv",
        "independent_reconstructions.csv",
        "confirmed_defects.csv",
        "patches_applied.csv",
        "before_after_metrics.csv",
        "superseded_artifacts.csv",
        "downstream_outcome_changes.csv",
        "remaining_unresolved_consumers.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_every_scoped_consumer_has_one_allowed_classification() -> None:
    rows = read_csv(EVIDENCE / "consumer_classifications.csv")
    ids = [row["consumer_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert len(rows) >= 8
    assert all(row["classification"] in blast.ALLOWED_CLASSIFICATIONS for row in rows)
    consistency = read_json(EVIDENCE / "consistency_check.json")
    assert consistency["every_scoped_consumer_classified"] is True
    assert consistency["no_unresolved_current_consumers"] is True


def test_confirmed_current_defects_are_patched() -> None:
    rows = {row["consumer_id"]: row for row in read_csv(EVIDENCE / "consumer_classifications.csv")}
    assert rows[blast.active.VM_ID]["classification"] == "accounting_defect_confirmed"
    assert rows[blast.active.DSR_ID]["classification"] == "accounting_defect_confirmed"
    assert rows["raw_sector_equal_weight_basket"]["classification"] == "accounting_defect_confirmed"
    assert rows[blast.combo.COMBO_ID]["classification"] == "accounting_defect_confirmed"
    assert all(rows[key]["post_patch_status"] == "correct_drifting_holdings" for key in [blast.active.VM_ID, blast.active.DSR_ID, "raw_sector_equal_weight_basket", blast.combo.COMBO_ID])
    assert all(rows[key]["patched"] == "True" for key in [blast.active.VM_ID, blast.active.DSR_ID, "raw_sector_equal_weight_basket", blast.combo.COMBO_ID])


def test_vm_and_dsr_are_not_misclassified_as_binary() -> None:
    vm = read_csv(EVIDENCE / "vm_accounting_review.csv")[0]
    dsr = read_csv(EVIDENCE / "dsr_accounting_review.csv")[0]
    assert int(vm["mixed_risky_target_months"]) > 0
    assert int(dsr["mixed_risky_target_months"]) > 0
    assert vm["post_patch_status"] == "correct_drifting_holdings"
    assert dsr["post_patch_status"] == "correct_drifting_holdings"


def test_monthly_component_and_multisector_holdings_drift_between_rebalances() -> None:
    rows = {row["scenario"]: row for row in read_csv(EVIDENCE / "independent_reconstructions.csv")}
    component = rows["synthetic_monthly_50_50_component_portfolio"]
    sector = rows["synthetic_multi_sector_equal_weight_holdings"]
    assert float(component["turnover_from_pre_trade_actual"]) > float(component["target_to_target_turnover"])
    assert float(sector["turnover_from_pre_trade_actual"]) > float(sector["target_to_target_turnover"])
    assert float(component["cost_charged_on_non_execution_date"]) == 0.0
    assert float(sector["cost_charged_on_non_execution_date"]) == 0.0


def test_binary_spy_bil_control_is_classified_as_single_asset_equivalent() -> None:
    rows = {row["consumer_id"]: row for row in read_csv(EVIDENCE / "consumer_classifications.csv")}
    assert rows["bt_adapter_spy_bil_controls"]["classification"] == "binary_single_asset_equivalent"
    recon = {row["scenario"]: row for row in read_csv(EVIDENCE / "independent_reconstructions.csv")}
    binary = recon["synthetic_binary_one_risky_or_cash"]
    assert float(binary["turnover_from_pre_trade_actual"]) == pytest.approx(float(binary["target_to_target_turnover"]))


def test_precomputed_series_lineage_is_traced_for_checkpoint_and_public_screening() -> None:
    rows = {row["consumer_id"]: row for row in read_csv(EVIDENCE / "consumer_classifications.csv")}
    assert rows["current_research_checkpoint"]["classification"] == "precomputed_series_dependency"
    assert "active_combo_series_reconciliation" in rows["current_research_checkpoint"]["source_series_trace"]
    assert rows["public_source_comparative_screening_batch_v1"]["classification"] == "precomputed_series_dependency"
    assert "combo_daily_series.csv" in rows["public_source_comparative_screening_batch_v1"]["source_series_trace"]


def test_active_combo_reconstruction_is_exact_and_reference_only() -> None:
    review = read_csv(EVIDENCE / "active_combo_accounting_review.csv")[0]
    assert review["reconstructability"] == "exactly_reconstructable"
    assert review["checkpoint_safe_to_restore"] == "True"
    assert review["role"] == "benchmark_reference_only"
    consistency = read_json(EVIDENCE / "consistency_check.json")
    assert consistency["active_combo_exact_reconstruction_available"] is True
    assert consistency["active_combo_benchmark_reference_only"] is True


def test_before_after_metrics_and_downstream_rows_are_recorded() -> None:
    before_after = read_csv(EVIDENCE / "before_after_metrics.csv")
    assert {row["consumer_id"] for row in before_after} >= {blast.active.VM_ID, blast.active.DSR_ID, "raw_sector_equal_weight_basket", blast.combo.COMBO_ID}
    assert any(row["delta_after_minus_before"] not in {"", "0", "0.0"} for row in before_after)
    downstream = {row["downstream_artifact"]: row for row in read_csv(EVIDENCE / "downstream_outcome_changes.csv")}
    assert downstream["current_research_checkpoint"]["regenerated"] == "True"
    assert downstream["risk_parity_trend_etf_wrapper_screen_v1"]["outcome_after"] == "control_weak"


def test_risk_parity_exact_candidate_remains_closed_control_weak() -> None:
    decision = read_json(EVIDENCE / "decision.json")
    assert decision["risk_parity_exact_candidate_status"] == "closed_for_immediate_retesting_control_weak"
    rows = {row["consumer_id"]: row for row in read_csv(EVIDENCE / "consumer_classifications.csv")}
    assert rows["rp_ivol_10m_trend_etf_wrapper_adaptation_v1"]["classification"] == "correct_drifting_holdings"
    consistency = read_json(EVIDENCE / "consistency_check.json")
    assert consistency["risk_parity_exact_candidate_remains_closed"] is True


def test_lifecycle_paper_demo_and_discovery_guardrails_remain_clean() -> None:
    consistency = read_json(EVIDENCE / "consistency_check.json")
    assert consistency["vm_lifecycle_state_unchanged"] is True
    assert consistency["dsr_lifecycle_state_unchanged"] is True
    assert consistency["dsr_historical_and_current_metrics_separated"] is True
    assert consistency["no_provider_calls"] is True
    assert consistency["no_parameter_wrapper_universe_or_window_search"] is True
    assert consistency["no_strategy_discovery_run"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_demo_state_change"] is True
    assert consistency["no_broker_live_real_money_path"] is True
    assert consistency["consistency_passed"] is True
