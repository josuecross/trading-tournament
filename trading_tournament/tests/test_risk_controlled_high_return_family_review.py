from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_risk_controlled_high_return_family_review as review


def write_cache(root: Path, symbol: str, rows: int = 1500) -> None:
    path = root / "data" / "cache" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    start = date(2020, 1, 1)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        day = start
        written = 0
        while written < rows:
            if day.weekday() < 5:
                price = 100 + written * 0.01
                writer.writerow(
                    {
                        "date": day.isoformat(),
                        "open": f"{price:.2f}",
                        "high": f"{price + 1:.2f}",
                        "low": f"{price - 1:.2f}",
                        "close": f"{price:.2f}",
                        "adj_close": f"{price:.2f}",
                        "volume": "1000000",
                        "symbol": symbol,
                    }
                )
                written += 1
            day += timedelta(days=1)


def write_fixture(root: Path) -> None:
    registry_path = root / review.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "pre_register_risk_controlled_high_return_family_review",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "dual_momentum_paa_clean_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "donchian_atr_breakout_etf_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / review.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\nCurrent next action: `pre_register_risk_controlled_high_return_family_review`\n",
        encoding="utf-8",
    )
    approved = root / review.APPROVED_SYMBOL_MAP_PATH
    approved.parent.mkdir(parents=True, exist_ok=True)
    approved.write_text(
        yaml.safe_dump(
            {
                "symbols": [
                    {"symbol": symbol, "allowed_for_strategy": True, "approved_status": "approved_cache_ready"}
                    for symbol in review.required_symbols()
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for symbol in review.required_symbols():
        write_cache(root, symbol)

    third_failure = root / review.THIRD_FAILURE_DIR / "third_expansion_failure_audit_manifest.json"
    third_failure.parent.mkdir(parents=True, exist_ok=True)
    third_failure.write_text(
        json.dumps(
            {
                "exact_rejected_variants_closed": True,
                "daily_weekly_expansion_should_pause": True,
            }
        ),
        encoding="utf-8",
    )
    intraday_pause = root / review.INTRADAY_PAUSE_DIR / "intraday_data_constraints_pause_manifest.json"
    intraday_pause.parent.mkdir(parents=True, exist_ok=True)
    intraday_pause.write_text(
        json.dumps(
            {
                "intraday_research_paused": True,
                "next_action": "pre_register_risk_controlled_high_return_family_review",
            }
        ),
        encoding="utf-8",
    )
    second_metrics = root / review.SECOND_DISCOVERY_DIR / "second_expansion_candidate_metrics.json"
    second_metrics.parent.mkdir(parents=True, exist_ok=True)
    second_metrics.write_text(json.dumps({"donchian_atr_breakout_etf_v1": {"outcome": "discovery_reject"}}), encoding="utf-8")
    third_metrics = root / review.THIRD_DISCOVERY_DIR / "third_expansion_candidate_metrics.json"
    third_metrics.parent.mkdir(parents=True, exist_ok=True)
    third_metrics.write_text(json.dumps({"dual_momentum_paa_clean_v1": {"outcome": "discovery_reject"}}), encoding="utf-8")


@pytest.fixture(scope="module")
def review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("risk_controlled_high_return_family_review")
    write_fixture(root)
    before = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_risk_controlled_high_return_family_review(root)
    after = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(review_run: dict[str, Any]) -> Path:
    return Path(review_run["output_dir"])


def manifest(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "risk_controlled_high_return_manifest.json").read_text(encoding="utf-8"))


def consistency(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "risk_controlled_consistency_check.json").read_text(encoding="utf-8"))


def test_pre_registration_only(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["pre_registration_only"] is True


def test_family_review_only(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["family_review_only"] is True


def test_no_backtests(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["backtests_run"] is False


def test_no_discovery(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["discovery_run"] is False


def test_no_new_performance_metrics(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["provider_download"] is False


def test_no_intraday_data_used(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_exact_rejected_variants_remain_closed(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["exact_rejected_variants_reopened"] is False


def test_parent_rejected_rows_are_documented(review_run: dict[str, Any]) -> None:
    assert sorted(manifest(review_run)["parent_rejected_rows"]) == [
        "donchian_atr_breakout_etf_v1",
        "dual_momentum_paa_clean_v1",
    ]


def test_candidate_count_valid(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert 1 <= loaded["candidate_count"] <= 3


def test_every_candidate_has_new_hypothesis(review_run: dict[str, Any]) -> None:
    assert all(candidate["new_hypothesis"] for candidate in manifest(review_run)["candidate_specs"])


def test_every_candidate_changes_exactly_one_major_dimension(review_run: dict[str, Any]) -> None:
    dimensions = [candidate["one_major_changed_dimension"] for candidate in manifest(review_run)["candidate_specs"]]
    assert dimensions == ["volatility_scaling", "risk_budget_sizing"]


def test_every_candidate_has_valid_lane_assignment(review_run: dict[str, Any]) -> None:
    lanes = {candidate["lane"] for candidate in manifest(review_run)["candidate_specs"]}
    assert lanes <= {"macro_gld_duration_risk_off_lane", "moderate_tactical_etf_lane"}


def test_data_availability_report_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "risk_controlled_data_availability_report.md").exists()


def test_acceptance_gates_exist(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "risk_controlled_acceptance_gates.md").exists()


def test_rejection_gates_exist(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "risk_controlled_rejection_gates.md").exists()


def test_do_not_run_now_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "risk_controlled_do_not_run_now.md").exists()


def test_next_action_is_valid(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["next_action"] in review.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    for key, value in review.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(review_run)["consistency_passed"] is True
