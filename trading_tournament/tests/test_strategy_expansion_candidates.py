from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

import run_strategy_expansion_candidates_registry as registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / registry.REGISTRY_PATH
OUTPUT_DIR = ROOT / registry.OUTPUT_DIR
MANIFEST_PATH = OUTPUT_DIR / "strategy_expansion_manifest.json"
SNAPSHOT_PATH = OUTPUT_DIR / "candidate_registry_snapshot.csv"
DIVERSITY_PATH = OUTPUT_DIR / "diversity_map.csv"
TESTED_REVIEW_PATH = OUTPUT_DIR / "tested_strategy_review.md"
VARIANT_RULES_PATH = OUTPUT_DIR / "future_variant_rules.md"


def load_registry() -> dict:
    assert REGISTRY_PATH.exists(), f"missing registry: {REGISTRY_PATH}"
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_candidates() -> list[dict]:
    payload = load_registry()
    return payload["candidates"]


def load_csv(path: Path) -> list[dict[str, str]]:
    assert path.exists(), f"missing csv: {path}"
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_at_least_ten_candidates_are_registered() -> None:
    assert len(load_candidates()) >= 10


def test_candidate_ids_are_unique() -> None:
    ids = [candidate["candidate_id"] for candidate in load_candidates()]
    assert len(ids) == len(set(ids))


def test_priority_ranks_are_unique_and_ordered() -> None:
    ranks = [candidate["priority_rank"] for candidate in load_candidates()]
    assert ranks == sorted(ranks)
    assert ranks == list(range(1, len(ranks) + 1))


def test_each_candidate_has_required_fields() -> None:
    for candidate in load_candidates():
        missing = [field for field in registry.REQUIRED_CANDIDATE_FIELDS if field not in candidate]
        assert not missing, f"{candidate.get('candidate_id')} missing {missing}"


def test_intraday_candidates_are_research_only() -> None:
    intraday = [candidate for candidate in load_candidates() if candidate["timeframe"] == "intraday"]
    assert intraday
    assert all(candidate["status"] == "intraday_research_only" for candidate in intraday)


def test_intraday_candidates_are_not_demo_eligible() -> None:
    intraday = [candidate for candidate in load_candidates() if candidate["timeframe"] == "intraday"]
    assert all(candidate["demo_eligibility"] == "research_only_until_execution_ready" for candidate in intraday)


def test_no_candidate_uses_forbidden_status() -> None:
    forbidden = set(registry.FORBIDDEN_STATUS_VALUES)
    statuses = {candidate["status"] for candidate in load_candidates()}
    assert statuses.isdisjoint(forbidden)
    assert statuses <= set(registry.CONTROLLED_STATUS_VALUES)


def test_all_candidates_have_risk_controls() -> None:
    for candidate in load_candidates():
        assert candidate["risk_controls"], candidate["candidate_id"]


def test_all_candidates_have_benchmark_controls() -> None:
    for candidate in load_candidates():
        assert candidate["benchmark_controls"], candidate["candidate_id"]


def test_diversity_map_includes_required_classes() -> None:
    rows = load_csv(DIVERSITY_PATH)
    classes = {row["diversity_family"] for row in rows}
    required = {
        "mean-reversion",
        "volatility-management",
        "sector-rotation",
        "breakout",
        "intraday momentum",
        "intraday reversion",
        "risk-overlay",
    }
    assert required <= classes
    timeframes = {row["timeframe"] for row in rows}
    assert {"daily", "weekly", "intraday", "meta-overlay"} <= timeframes


def test_tested_strategy_review_includes_archived_breadth_state_lane() -> None:
    review = TESTED_REVIEW_PATH.read_text(encoding="utf-8").lower()
    assert "breadth-state regime lane" in review
    assert "archived" in review
    assert "etf-wrapper track" in review


def test_manifest_confirms_no_runs_or_actions() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["saved_candidates_only"] is True
    for key in [
        "backtests_run",
        "discovery_run",
        "candidate_exhaustive_run",
        "paper_forward_review",
        "paper_forward_activation",
        "broker_path_touched",
        "live_orders",
        "provider_download",
        "real_money_recommendation",
    ]:
        assert manifest[key] is False, key


def test_future_variant_rules_prevent_parameter_mining() -> None:
    rules = VARIANT_RULES_PATH.read_text(encoding="utf-8")
    assert "changes exactly one major dimension" in rules
    assert "Do not test many parameter values after seeing results" in rules
    assert "Each new variant must receive a new candidate ID" in rules
    assert "No post-result threshold tuning" in rules


def test_snapshot_matches_registry_candidate_count() -> None:
    assert len(load_csv(SNAPSHOT_PATH)) == len(load_candidates())
