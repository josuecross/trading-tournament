from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import run_approved_symbol_expansion_review as review


def write_file(path: Path, text: str = "placeholder\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_state(root: Path) -> None:
    write_file(root / "strategy_lab" / "APPROVED_ETF_CACHE_POLICY.md", "# Policy\n")
    write_file(root / "strategy_lab" / "strategy_registry.yaml", yaml.safe_dump({"strategies": []}, sort_keys=False))
    symbol_map = {
        "symbols": [
            {"symbol": "SPY", "group": "core", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "QQQ", "group": "core", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "EFA", "group": "international", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "EEM", "group": "international", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "VTV", "group": "value", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "VLUE", "group": "value", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
            {"symbol": "USMV", "group": "minvol", "allowed_for_strategy": True, "allowed_for_benchmark": True, "requires_explicit_prompt": False},
        ]
    }
    write_file(root / review.SYMBOL_MAP_PATH, yaml.safe_dump(symbol_map, sort_keys=False))
    proposal = {
        "status": "proposed_only_not_approved",
        "recommended": True,
        "next_action": "create_approved_symbol_expansion_review",
        "rules": {"download_now": False, "approve_automatically": False, "strategy_run_now": False, "requires_policy_review": True},
        "symbols": [{"symbol": symbol} for symbol in review.PROPOSED_SYMBOLS],
    }
    write_file(root / "evidence" / "research_lane_decision" / "latest" / "proposed_symbol_expansion_if_any.yaml", yaml.safe_dump(proposal, sort_keys=False))
    write_file(root / "evidence" / "research_lane_decision" / "latest" / "recommended_next_lane.md", "`create_approved_symbol_expansion_review`\n")
    manifest = {"strategy_run": False, "provider_api_called": False, "candidate_exhaustive_run": False, "paper_forward_review": False, "paper_forward_activation": False, "paper_forward_checkpoint": False, "real_money_recommendation": False}
    write_file(root / "evidence" / "research_lane_decision" / "latest" / "research_lane_decision_manifest.json", json.dumps(manifest))
    write_file(root / "evidence" / "research_lane_decision" / "latest" / "approved_universe_exhaustion_review.csv", "universe_group\n")
    write_file(root / "evidence" / "research_lane_decision" / "latest" / "next_lane_options.csv", "option_id\n")
    (root / "evidence" / "approved_etf_cache_readiness" / "latest").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "research_state" / "latest").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "strategy_lab" / "latest").mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def audited_fixture(tmp_path: Path) -> dict[str, object]:
    write_state(tmp_path)
    result = review.run_expansion_review(tmp_path, strict_state=True, update_map=True)
    return {"root": tmp_path, "result": result}


def test_proposed_symbols_are_not_approved_automatically(audited_fixture: dict[str, object]) -> None:
    assert set(audited_fixture["result"]["approved_symbols"]) == review.APPROVED_SUBSET
    assert len(audited_fixture["result"]["approved_symbols"]) < len(review.PROPOSED_SYMBOLS)


def test_leverage_inverse_forbidden_symbols_would_be_rejected() -> None:
    assert review.review_symbol("TQQQ")["classification"] == "reject_policy_violation"
    assert review.review_symbol("SQQQ")["classification"] == "reject_policy_violation"


def test_near_duplicate_symbols_can_be_deferred() -> None:
    assert review.review_symbol("IEFA")["classification"] == "defer_duplicate_or_low_incremental_value"
    assert review.review_symbol("ACWV")["classification"] == "defer_duplicate_or_low_incremental_value"


def test_approved_symbols_require_explicit_prompt(audited_fixture: dict[str, object]) -> None:
    symbol_map = yaml.safe_load((Path(audited_fixture["root"]) / review.SYMBOL_MAP_PATH).read_text(encoding="utf-8"))
    approved_rows = [row for row in symbol_map["symbols"] if row["symbol"] in review.APPROVED_SUBSET]
    assert approved_rows
    assert all(row["requires_explicit_prompt"] is True for row in approved_rows)


def test_approved_symbols_marked_pending_cache_bootstrap_not_cache_ready(audited_fixture: dict[str, object]) -> None:
    symbol_map = yaml.safe_load((Path(audited_fixture["root"]) / review.SYMBOL_MAP_PATH).read_text(encoding="utf-8"))
    approved_rows = [row for row in symbol_map["symbols"] if row["symbol"] in review.APPROVED_SUBSET]
    assert all(row["approved_status"] == "approved_pending_cache_bootstrap" for row in approved_rows)
    assert all(row.get("cache_ready") is not True for row in approved_rows)


def test_no_provider_download_is_called(audited_fixture: dict[str, object]) -> None:
    manifest = json.loads((Path(audited_fixture["result"]["output_dir"]) / "approved_symbol_expansion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_api_called"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["cache_bootstrap_run"] is False


def test_no_strategy_runner_is_called(audited_fixture: dict[str, object]) -> None:
    manifest = json.loads((Path(audited_fixture["result"]["output_dir"]) / "approved_symbol_expansion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_run"] is False


def test_no_candidate_exhaustive_is_run(audited_fixture: dict[str, object]) -> None:
    consistency = audited_fixture["result"]["consistency"]
    assert consistency["no_candidate_exhaustive_run"] is True


def test_no_paper_forward_active_flag_is_set(audited_fixture: dict[str, object]) -> None:
    consistency = audited_fixture["result"]["consistency"]
    assert consistency["no_paper_forward_active_flag_set"] is True


def test_no_real_money_recommendation_is_created(audited_fixture: dict[str, object]) -> None:
    consistency = audited_fixture["result"]["consistency"]
    assert consistency["no_real_money_recommendation"] is True


def test_next_action_is_explicit(audited_fixture: dict[str, object]) -> None:
    assert audited_fixture["result"]["next_action"] == "bootstrap_approved_expansion_symbols_cache"
    output = Path(audited_fixture["result"]["output_dir"])
    assert "bootstrap_approved_expansion_symbols_cache" in (output / "approved_symbol_expansion_next_action.md").read_text(encoding="utf-8")


def test_consistency_check_passes(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    consistency = json.loads((output / "approved_symbol_expansion_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
