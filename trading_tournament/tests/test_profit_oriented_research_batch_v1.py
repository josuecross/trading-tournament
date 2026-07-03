import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    NEXT_ACTION_AUDIT,
    OBSERVATION_OUTPUT_DIR,
    RESEARCH_OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def batch_run() -> dict[str, object]:
    manifest_path = ROOT / RESEARCH_OUTPUT_DIR / "profit_research_batch_manifest.json"
    observation_path = ROOT / OBSERVATION_OUTPUT_DIR / "observation_delegation_manifest.json"
    if not manifest_path.exists() or not observation_path.exists():
        pytest.skip("profit-oriented batch v1 evidence is not present")
    return {"research_output_dir": str((ROOT / RESEARCH_OUTPUT_DIR).resolve())}


def research_manifest() -> dict[str, object]:
    return json.loads((ROOT / RESEARCH_OUTPUT_DIR / "profit_research_batch_manifest.json").read_text(encoding="utf-8"))


def observation_manifest() -> dict[str, object]:
    return json.loads((ROOT / OBSERVATION_OUTPUT_DIR / "observation_delegation_manifest.json").read_text(encoding="utf-8"))


def test_observation_loop_delegated_and_not_research_blocking(batch_run: dict[str, object]) -> None:
    obs = observation_manifest()
    manifest = research_manifest()

    assert obs["status"] == "observation_manual_snapshot_loop_delegated_to_alpaca_module"
    assert obs["manual_observation_loop_blocking_research"] is False
    assert obs["alpaca_execution_module_delegated"] is True
    assert obs["research_track_unblocked"] is True
    assert manifest["manual_observation_loop_blocking_research"] is False
    assert manifest["alpaca_execution_module_delegated"] is True

    for filename in (
        "observation_delegation_summary.md",
        "alpaca_execution_module_boundary.md",
        "manual_snapshot_loop_status.md",
        "operations_research_boundary.md",
        "observation_delegation_next_action.md",
    ):
        assert (ROOT / OBSERVATION_OUTPUT_DIR / filename).exists(), filename


def test_profit_research_manifest_strict_scope_flags(batch_run: dict[str, object]) -> None:
    manifest = research_manifest()

    assert manifest["profit_oriented_research_batch"] is True
    assert manifest["batch_id"] == "profit_oriented_research_batch_v1"
    assert manifest["historical_research_only"] is True
    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["old_dollar_target_is_hard_gate"] is False
    assert manifest["low_drawdown_is_hard_discovery_gate"] is False
    assert manifest["research_outputs_non_promotable"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_AUDIT


def test_batch_outputs_exist_and_are_consistent(batch_run: dict[str, object]) -> None:
    output = ROOT / RESEARCH_OUTPUT_DIR
    consistency = json.loads((output / "profit_research_batch_consistency_check.json").read_text(encoding="utf-8"))
    manifest = research_manifest()

    assert consistency["consistency_passed"] is True
    assert (output / "profit_research_variant_results.csv").exists()
    assert (output / "profit_research_family_summary.csv").exists()
    assert (output / "high_profit_high_risk_signals.md").exists()
    assert (output / "portfolio_diversifier_signals.md").exists()
    assert (output / "do_not_promote_from_profit_research_batch_v1.md").exists()
    assert (output / "gld_macro_lineage_status.md").exists()
    assert manifest["variants_planned_count"] <= 120
    assert manifest["variants_evaluated_count"] <= 120
    assert manifest["families_evaluated_count"] == 5


def test_variant_results_are_non_promotable(batch_run: dict[str, object]) -> None:
    rows = list(csv.DictReader((ROOT / RESEARCH_OUTPUT_DIR / "profit_research_variant_results.csv").open(encoding="utf-8")))
    assert rows

    forbidden = {
        "promotion_review_candidate",
        "candidate_exhaustive_candidate",
        "paper_forward_candidate",
        "live_ready",
        "demo_active_new",
        "real_money_candidate",
    }
    allowed = {
        "research_signal_promising",
        "research_signal_high_risk",
        "research_signal_diversifier",
        "research_signal_needs_robustness",
        "research_signal_weak",
        "research_signal_data_blocked",
        "research_signal_duplicate",
        "research_signal_rejected",
    }
    for row in rows:
        assert row["research_label"] in allowed
        assert row["research_label"] not in forbidden
        assert row["promotion_eligibility"] == "False"
        assert row["paper_forward_eligibility"] == "False"
        assert row["promotion_eligibility_score"] in {"0.0", "0"}


def test_research_signal_files_and_counts(batch_run: dict[str, object]) -> None:
    manifest = research_manifest()
    high_risk = (ROOT / RESEARCH_OUTPUT_DIR / "high_profit_high_risk_signals.md").read_text(encoding="utf-8")
    diversifier = (ROOT / RESEARCH_OUTPUT_DIR / "portfolio_diversifier_signals.md").read_text(encoding="utf-8")
    do_not_promote = (ROOT / RESEARCH_OUTPUT_DIR / "do_not_promote_from_profit_research_batch_v1.md").read_text(
        encoding="utf-8"
    )

    assert manifest["research_signal_high_risk_count"] >= 0
    assert manifest["research_signal_diversifier_count"] >= 0
    assert manifest["research_signal_data_blocked_count"] >= 0
    assert "High-Profit / High-Risk Signals" in high_risk
    assert "Portfolio Diversifier Signals" in diversifier
    assert "This batch is non-promotable by design." in do_not_promote


def test_gld_macro_lineage_is_research_only(batch_run: dict[str, object]) -> None:
    text = (ROOT / RESEARCH_OUTPUT_DIR / "gld_macro_lineage_status.md").read_text(encoding="utf-8")
    rows = list(csv.DictReader((ROOT / RESEARCH_OUTPUT_DIR / "profit_research_variant_results.csv").open(encoding="utf-8")))
    macro_rows = [row for row in rows if row["family_id"] == "macro_gld_duration_risk_off"]

    assert macro_rows
    assert "lineage_incomplete_research_only" in text
    assert all(row["lineage_status"] == "lineage_incomplete_research_only" for row in macro_rows)
    assert "cannot become promotable" in text
