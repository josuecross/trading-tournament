from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
TRIAGE_DIR = ROOT / "candidate_triage"
LATEST_DIR = ROOT / "evidence" / "candidate_triage" / "latest"
TRIAGE_ZIP = ROOT / "evidence" / "candidate_triage" / "latest_candidate_triage_packet.zip"
RECENT_CANDIDATES = {
    "qqq_spy_gld_ief_dual_momentum_v1",
    "value_momentum_factor_etf_rotation_v1",
    "sector_top2_momentum_simple_v1",
    "managed_futures_proxy_etf_trend_v1",
}
REQUIRED_SCORECARD_ROWS = RECENT_CANDIDATES | {
    "combo_SPY200d_GLD_50_50_v1",
    "asset_class_tsmom_top2_v1",
    "SPY_200d_trend_model",
    "GLD_buy_hold",
    "SPY_buy_hold",
    "BIL_cash_proxy",
}


def test_candidate_triage_packet_exists_and_is_compact() -> None:
    assert TRIAGE_DIR.exists()
    assert LATEST_DIR.exists()
    files = [path for path in LATEST_DIR.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert TRIAGE_ZIP.exists()
    with zipfile.ZipFile(TRIAGE_ZIP) as zf:
        names = set(zf.namelist())
    assert "RECENT_CANDIDATE_SCORECARD.csv" in names
    assert "CANDIDATE_DECISIONS.md" in names
    assert "DIVERSIFICATION_AUDIT.md" in names


def test_scorecard_includes_required_candidates_and_decisions() -> None:
    scorecard = pd.read_csv(LATEST_DIR / "RECENT_CANDIDATE_SCORECARD.csv")
    assert REQUIRED_SCORECARD_ROWS.issubset(set(scorecard["candidate_id"]))
    recent = scorecard[scorecard["candidate_id"].isin(RECENT_CANDIDATES)]
    assert recent["deserves_candidate_exhaustive"].astype(str).str.lower().eq("false").all()
    assert recent["paper_forward_active"].astype(str).str.lower().eq("false").all()
    decisions = (LATEST_DIR / "CANDIDATE_DECISIONS.md").read_text(encoding="utf-8")
    assert "archive_or_hold_as_high_upside_high_risk_reference" in decisions
    assert "archive_or_hold_as_duplicate_reference" in decisions
    assert "watchlist_only" in decisions
    assert "too_slow_watchlist_diversifier_only" in decisions


def test_required_triage_review_files_exist() -> None:
    for name in [
        "CANDIDATE_DECISIONS.md",
        "DIVERSIFICATION_AUDIT.md",
        "CANDIDATE_EXHAUSTIVE_QUEUE_REVIEW.md",
        "ARCHIVE_OR_WATCHLIST_DECISIONS.md",
        "NEXT_RESEARCH_DIRECTION.md",
    ]:
        assert (LATEST_DIR / name).exists()
    queue_review = (LATEST_DIR / "CANDIDATE_EXHAUSTIVE_QUEUE_REVIEW.md").read_text(encoding="utf-8")
    assert "No recent research_sample candidate is added to candidate_exhaustive now." in queue_review
    assert "does not freeze historical research" in queue_review
    next_direction = (LATEST_DIR / "NEXT_RESEARCH_DIRECTION.md").read_text(encoding="utf-8")
    assert "Do not pause the historical research program itself" in next_direction
    assert "combination-design implementation review" in next_direction


def test_triage_manifest_confirms_review_only_boundaries() -> None:
    manifest = json.loads((LATEST_DIR / "candidate_triage_manifest.json").read_text(encoding="utf-8"))
    assert manifest["new_strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["real_money_recommendation"] is False


def test_no_strategy_implementation_or_download_path_added_for_triage() -> None:
    source = (ROOT / "run_profit_exploration.py").read_text(encoding="utf-8")
    assert "candidate_testing_triage" not in source
    assert "candidate_triage" not in source
    assert "run_backtest.py" not in (LATEST_DIR / "README.md").read_text(encoding="utf-8")


def test_strategy_lab_validates_and_recent_rows_remain_non_active() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    rows = [row for row in data["strategies"] if row["id"] in RECENT_CANDIDATES]
    assert len(rows) == len(RECENT_CANDIDATES)
    for row in rows:
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["paper_forward_allowed_by_risk_framework"] is False
        assert row.get("real_money_recommendation", False) is not True


def test_advisor_upload_remains_compact_and_references_triage(tmp_path: Path) -> None:
    result = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        no_nested_zips=True,
    )
    latest = result["latest_dir"]
    assert result["manifest"]["top_level_file_count"] <= 10
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        review_index = zf.read("PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "candidate_testing_triage" in review_index
    assert "triage_complete_no_new_candidate_exhaustive_additions" in review_index
    assert "Candidate testing triage packet:" in executive
