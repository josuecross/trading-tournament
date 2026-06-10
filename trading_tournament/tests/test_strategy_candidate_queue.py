from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


QUEUE_DIR = Path("strategy_candidate_queue")
QUEUE_LATEST = Path("evidence/strategy_candidate_queue/latest")
EXPECTED_CANDIDATES = {
    "qqq_spy_gld_ief_dual_momentum_v1",
    "value_momentum_factor_etf_rotation_v1",
    "low_vol_quality_defensive_rotation_v1",
    "sector_top2_momentum_simple_v1",
    "managed_futures_proxy_etf_trend_v1",
    "treasury_duration_trend_rotation_v1",
    "commodity_basket_etf_momentum_v1",
    "crypto_spot_tsmom_tier2_review_v1",
    "individual_stock_momentum_gate1b_v1",
    "options_futures_forex_intraday_blocked_reference_v1",
}
REQUIRED_FIELDS = {
    "candidate_id",
    "display_name",
    "version",
    "strategy_family",
    "instrument_family",
    "return_driver",
    "source_prior",
    "evidence_quality",
    "evidence_tier",
    "current_status",
    "recommended_next_action",
    "implementation_allowed_now",
    "paper_forward_allowed_now",
    "paper_forward_active",
    "real_money_recommendation",
    "broker_integration_required",
    "live_orders_required",
    "uses_leverage",
    "uses_shorting",
    "uses_margin",
    "requires_new_data",
    "required_symbols_or_data",
    "current_engine_can_test",
    "expected_correlation_with_current_finalists",
    "diversification_value",
    "target_potential",
    "stop_risk",
    "data_gate_status",
    "execution_gate_status",
    "risk_model_gate_status",
    "benchmark_gate_status",
    "complexity_gate_status",
    "anti_overfitting_risk",
    "primary_benchmark",
    "failure_mode",
    "reason_to_test",
    "reason_to_reject_or_defer",
    "promotion_requirements",
    "notes",
}


def load_queue_yaml() -> dict:
    return yaml.safe_load((QUEUE_DIR / "strategy_candidate_queue.yaml").read_text(encoding="utf-8"))


def test_strategy_candidate_queue_files_exist_and_latest_is_compact() -> None:
    assert (QUEUE_DIR / "strategy_candidate_queue.yaml").exists()
    assert (QUEUE_DIR / "candidate_queue_matrix.csv").exists()
    assert (QUEUE_DIR / "candidate_gate_policy.md").exists()
    assert (QUEUE_DIR / "rejected_or_deferred_candidates.md").exists()
    assert QUEUE_LATEST.exists()
    latest_files = [path.name for path in QUEUE_LATEST.iterdir() if path.is_file()]
    assert len(latest_files) <= 10
    assert set(latest_files) == {
        "README_FOR_ADVISOR.md",
        "candidate_queue_summary.md",
        "candidate_queue_matrix.csv",
        "strategy_candidate_queue.yaml",
        "candidate_gate_policy.md",
        "candidate_research_notes.md",
        "rejected_or_deferred_candidates.md",
        "next_candidate_decision.md",
        "warnings_and_limitations.md",
        "candidate_queue_manifest.json",
    }
    assert Path("evidence/strategy_candidate_queue/latest_strategy_candidate_queue_packet.zip").exists()


def test_candidate_queue_contains_exact_candidates_and_required_fields() -> None:
    data = load_queue_yaml()
    candidates = data["candidates"]
    assert {row["candidate_id"] for row in candidates} == EXPECTED_CANDIDATES
    for row in candidates:
        assert REQUIRED_FIELDS.issubset(row.keys())
        assert row["implementation_allowed_now"] is False
        assert row["paper_forward_allowed_now"] is False
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
    matrix = pd.read_csv(QUEUE_DIR / "candidate_queue_matrix.csv")
    assert set(matrix["candidate_id"]) == EXPECTED_CANDIDATES
    assert not matrix["implementation_allowed_now"].astype(str).str.lower().isin(["true", "1"]).any()
    assert not matrix["paper_forward_active"].astype(str).str.lower().isin(["true", "1"]).any()
    assert not matrix["real_money_recommendation"].astype(str).str.lower().isin(["true", "1"]).any()


def test_rejected_deferred_and_gate_policy_cover_blocked_items() -> None:
    rejected = (QUEUE_DIR / "rejected_or_deferred_candidates.md").read_text(encoding="utf-8")
    for phrase in [
        "Options premium",
        "Futures trend following",
        "Forex carry/momentum",
        "Intraday/day trading",
        "Volatility products",
        "Crypto leverage/perps",
        "AI trading gate",
    ]:
        assert phrase in rejected
    policy = (QUEUE_DIR / "candidate_gate_policy.md").read_text(encoding="utf-8")
    for gate in [
        "Evidence Gate",
        "Data Gate",
        "Execution Realism Gate",
        "Risk-Model Gate",
        "Benchmark Gate",
        "Diversification Gate",
        "Complexity Gate",
        "Target-Potential Gate",
        "Anti-Overfitting Gate",
    ]:
        assert gate in policy


def test_strategy_lab_registry_validates_queue_only_rows() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    rows = [row for row in data["strategies"] if row["id"] in EXPECTED_CANDIDATES]
    assert {row["id"] for row in rows} == EXPECTED_CANDIDATES
    implemented_research_sample_ids = {
        "qqq_spy_gld_ief_dual_momentum_v1",
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
        "managed_futures_proxy_etf_trend_v1",
    }
    for row in rows:
        if row["id"] in implemented_research_sample_ids:
            assert row["lane"] == "profit_exploration"
            assert row["implementation_status"] == "implemented_research_sample"
        else:
            assert row["lane"] == "strategy_candidate_queue"
            assert row["implementation_status"] == "not_implemented"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True
        if row["id"] not in {"qqq_spy_gld_ief_dual_momentum_v1", "managed_futures_proxy_etf_trend_v1"}:
            assert any("run_backtest" in action for action in row["forbidden_next_actions"])
        if row["id"] != "qqq_spy_gld_ief_dual_momentum_v1":
            assert "observe_as_paper_forward" in row["forbidden_next_actions"]
            assert "promote_to_real_money" in row["forbidden_next_actions"]


def test_advisor_upload_includes_strategy_candidate_queue_packet(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "08_STRATEGY_CANDIDATE_QUEUE.zip" in top_files
    with zipfile.ZipFile(latest / "08_STRATEGY_CANDIDATE_QUEUE.zip") as zf:
        names = zf.namelist()
        assert "PACKET_MANIFEST.json" in names
        assert "source/evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv" in names
        manifest = json.loads(zf.read("PACKET_MANIFEST.json"))
    assert manifest["real_money_recommendation"] is False
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        names = zf.namelist()
        assert "CANDIDATE_QUEUE_DECISION_MATRIX.csv" in names
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "Strategy candidate queue exists: True" in executive


def test_queue_files_have_no_real_money_recommendation_or_raw_data() -> None:
    for path in list(QUEUE_DIR.iterdir()) + list(QUEUE_LATEST.iterdir()):
        if path.suffix.lower() not in {".md", ".csv", ".json", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        assert "data/cache" not in text
        assert "data/raw" not in text
        assert "ohlcv" not in path.name.lower()
        assert (
            "real-money recommendation" not in text
            or "no real-money recommendation" in text
            or "not a real-money recommendation" in text
            or "not real-money" in text
        )
