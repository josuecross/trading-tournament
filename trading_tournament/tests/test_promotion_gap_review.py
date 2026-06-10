from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

import run_promotion_gap_review as gap


FIELDNAMES = [
    "strategy_id",
    "family",
    "instrument_lane",
    "registry_lane",
    "evidence_tier",
    "current_status",
    "implementation_status",
    "paper_forward_active",
    "real_money_recommendation",
    "candidate_exhaustive_run",
    "candidate_exhaustive_recommended",
    "promotion_review_required",
    "promotion_decision",
    "promotion_reason",
    "primary_failure_mode",
    "duplication_risk",
    "risk_budget_status",
    "latest_evidence_path",
    "metrics_source",
    "target_300_evidence",
    "target_400_evidence",
    "drawdown_evidence",
    "stop_hit_evidence",
    "stress_evidence",
    "missing_evidence",
    "evidence_needed",
    "blocked_reason",
    "duplicate_of",
    "recommended_next_action",
    "candidate_exhaustive_allowed",
    "paper_forward_allowed",
    "allowed_next_actions",
    "forbidden_next_actions",
]


def make_row(strategy_id: str, decision: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "strategy_id": strategy_id,
        "family": "synthetic_family",
        "instrument_lane": "ETF",
        "registry_lane": "profit_exploration",
        "evidence_tier": "tier1_or_tier2_exploratory",
        "current_status": "implemented_research_sample",
        "implementation_status": "implemented_research_sample",
        "paper_forward_active": "False",
        "real_money_recommendation": "False",
        "candidate_exhaustive_run": "False",
        "candidate_exhaustive_recommended": "False",
        "promotion_review_required": "False",
        "promotion_decision": decision,
        "promotion_reason": "Synthetic reason.",
        "primary_failure_mode": "none",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "inside_budget",
        "latest_evidence_path": "evidence/synthetic/latest",
        "metrics_source": "synthetic",
        "target_300_evidence": "0.25",
        "target_400_evidence": "0.08",
        "drawdown_evidence": "-350",
        "stop_hit_evidence": "0.02",
        "stress_evidence": "12.0",
        "missing_evidence": "",
        "evidence_needed": "",
        "blocked_reason": "",
        "duplicate_of": "",
        "recommended_next_action": "research_sample_review",
        "candidate_exhaustive_allowed": "False",
        "paper_forward_allowed": "False",
        "allowed_next_actions": "research_sample_review",
        "forbidden_next_actions": "observe_as_paper_forward;promote_to_real_money;add_broker_integration",
    }
    row.update(overrides)
    return row


def write_decisions(project_root: Path, rows: list[dict[str, object]]) -> Path:
    latest = project_root / "evidence" / "promotion_review" / "latest"
    latest.mkdir(parents=True)
    path = latest / "promotion_decisions.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    (project_root / "strategy_lab").mkdir()
    (project_root / "strategy_lab" / "promotion_thresholds.yaml").write_text(
        yaml.safe_dump({"promotion": {"challenge_targets": {"starting_equity": 3000}}}),
        encoding="utf-8",
    )
    return path


def synthetic_rows() -> list[dict[str, object]]:
    return [
        make_row("active_combo", "keep_active_observation", paper_forward_active="True"),
        make_row("spy_control", "keep_frozen_control", evidence_tier="benchmark"),
        make_row(
            "stock_blocked",
            "blocked",
            family="individual_stock_momentum",
            promotion_reason="Blocked by survivorship and point-in-time provider access.",
            blocked_reason="survivorship-aware provider access unresolved",
        ),
        make_row(
            "risky_row",
            "mark_too_risky",
            primary_failure_mode="drawdown_budget_breach",
            risk_budget_status="breach",
            drawdown_evidence="-850",
        ),
        make_row(
            "slow_row",
            "mark_too_slow",
            primary_failure_mode="target_dilution",
            target_300_evidence="0.01",
            target_400_evidence="0.00",
        ),
        make_row(
            "duplicate_row",
            "mark_duplicate_or_near_duplicate",
            duplicate_of="active_combo",
            duplication_risk="high",
        ),
        make_row(
            "watchlist_missing_stress",
            "keep_watchlist",
            stress_evidence="",
            missing_evidence="stress evidence missing",
        ),
        make_row("high_watchlist", "keep_watchlist"),
    ]


def test_missing_promotion_decisions_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run_promotion_review.py"):
        gap.require_core_inputs(tmp_path)


def test_failure_mode_taxonomy_covers_key_decisions() -> None:
    rows = {row["strategy_id"]: row for row in synthetic_rows()}
    assert gap.classify_failure_mode(rows["stock_blocked"]).failure_mode == "blocked_survivorship_or_point_in_time_data"
    assert gap.classify_failure_mode(rows["risky_row"]).failure_mode == "too_risky_drawdown_budget"
    assert gap.classify_failure_mode(rows["slow_row"]).failure_mode == "too_slow_target_dilution"
    assert gap.classify_failure_mode(rows["duplicate_row"]).failure_mode == "duplicate_existing_leader"
    assert gap.classify_failure_mode(rows["active_combo"]).failure_mode == "protected_active_observation"
    assert gap.classify_failure_mode(rows["spy_control"]).failure_mode == "protected_frozen_control"


def test_gap_review_outputs_required_files_and_consistency(tmp_path: Path) -> None:
    registry = tmp_path / "strategy_lab" / "strategy_registry.yaml"
    write_decisions(tmp_path, synthetic_rows())
    before_registry = registry.read_text(encoding="utf-8") if registry.exists() else ""

    result = gap.run_gap_review(project_root=tmp_path, run_id="test_run")

    latest = Path(result["latest_dir"])
    for name in gap.REQUIRED_OUTPUTS:
        assert (latest / name).exists(), name
    assert (latest / "promotion_gap_packet.zip").exists()

    consistency = json.loads((latest / "promotion_gap_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["paper_forward_activated"] is False
    assert consistency["real_money_recommendation_added"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["data_download_triggered"] is False
    assert consistency["provider_api_call_triggered"] is False
    assert (registry.read_text(encoding="utf-8") if registry.exists() else "") == before_registry


def test_closest_to_promotion_ranking_and_watchlist_actions(tmp_path: Path) -> None:
    write_decisions(tmp_path, synthetic_rows())
    gap.run_gap_review(project_root=tmp_path, run_id="rank_run")
    latest = tmp_path / "evidence" / "promotion_gap" / "latest"

    closest = list(csv.DictReader((latest / "closest_to_promotion.csv").open()))
    assert closest
    assert closest[0]["strategy_id"] == "high_watchlist"
    assert int(closest[0]["closest_to_promotion_score"]) >= int(closest[-1]["closest_to_promotion_score"])

    watchlist = {
        row["strategy_id"]: row
        for row in csv.DictReader((latest / "watchlist_next_actions.csv").open())
    }
    assert watchlist["watchlist_missing_stress"]["gap_recommended_next_action"] == "run_missing_stress_check"
    assert watchlist["high_watchlist"]["gap_recommended_next_action"] in {
        "candidate_exhaustive_review_if_thresholds_met",
        "run_duplicate_overlap_test",
    }


def test_next_research_lane_recommendation_is_specific(tmp_path: Path) -> None:
    write_decisions(tmp_path, synthetic_rows())
    gap.run_gap_review(project_root=tmp_path, run_id="lane_run")
    latest = tmp_path / "evidence" / "promotion_gap" / "latest"

    recommendation = (latest / "next_research_lane_recommendation.md").read_text(encoding="utf-8")
    action = (latest / "next_allowed_action.md").read_text(encoding="utf-8")
    assert "volatility_managed_equity_etf" in recommendation
    assert "create_volatility_managed_equity_etf_fast_exploration_review_prompt" in action
    assert "candidate_exhaustive" in action


def test_script_source_does_not_require_live_api_calls() -> None:
    source = Path("run_promotion_gap_review.py").read_text(encoding="utf-8")
    assert "requests." not in source
    assert "yfinance" not in source.lower()
    assert "run_backtest.py" not in source
    assert "run_profit_exploration.py" not in source
