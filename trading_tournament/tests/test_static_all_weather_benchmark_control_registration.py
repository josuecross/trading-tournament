from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_static_all_weather_benchmark_control_registration as registration


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_fixture(root: Path) -> None:
    registry_path = root / registration.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                    "current_next_action": "register_static_all_weather_as_benchmark_control_only",
                },
                "strategies": [
                    {
                        "id": "dual_momentum_paa_clean_v1",
                        "strategy_id": "dual_momentum_paa_clean_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "gld_ief_spy_defensive_rotation_v1",
                        "strategy_id": "gld_ief_spy_defensive_rotation_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "volatility_regime_spy_qqq_bil_v1",
                        "strategy_id": "volatility_regime_spy_qqq_bil_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / registration.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `register_static_all_weather_as_benchmark_control_only`\n", encoding="utf-8")
    discovery_dir = root / registration.THIRD_EXPANSION_DIR
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "third_expansion_discovery_manifest.json").write_text(
        json.dumps(
            {
                "next_action": "register_static_all_weather_as_benchmark_control_only",
                "benchmark_control_accepted_ids": [registration.BENCHMARK_CONTROL_ID],
                "promotion_candidates_count": 0,
                "candidate_exhaustive_run": False,
                "paper_forward_activation": False,
                "rejected_candidate_ids": registration.THIRD_EXPANSION_REJECTED_IDS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_csv(
        discovery_dir / "third_expansion_control_benchmark_diagnostics.csv",
        [
            {
                "candidate_id": registration.BENCHMARK_CONTROL_ID,
                "outcome": registration.BENCHMARK_CONTROL_STATUS,
                "profit_strategy_eligible": False,
            }
        ],
        ["candidate_id", "outcome", "profit_strategy_eligible"],
    )


@pytest.fixture(scope="module")
def registration_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("static_all_weather_registration")
    write_fixture(root)
    before = yaml.safe_load((root / registration.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = registration.run_static_all_weather_benchmark_control_registration(root)
    after = yaml.safe_load((root / registration.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(registration_run: dict[str, Any]) -> Path:
    return Path(registration_run["output_dir"])


def manifest(registration_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(registration_run) / "static_all_weather_benchmark_control_manifest.json").read_text(encoding="utf-8"))


def consistency(registration_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(registration_run) / "static_all_weather_benchmark_control_consistency_check.json").read_text(encoding="utf-8"))


def test_benchmark_control_registration_only(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["benchmark_control_registration_only"] is True


def test_static_all_weather_status_is_accepted_control(registration_run: dict[str, Any]) -> None:
    loaded = manifest(registration_run)
    assert loaded["benchmark_control_id"] == registration.BENCHMARK_CONTROL_ID
    assert loaded["benchmark_control_status"] == registration.BENCHMARK_CONTROL_STATUS


def test_static_all_weather_is_not_promotion_review_eligible(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["promotion_review_eligible"] is False


def test_static_all_weather_is_not_candidate_exhaustive_eligible(registration_run: dict[str, Any]) -> None:
    loaded = manifest(registration_run)
    assert loaded["candidate_exhaustive_eligible"] is False
    assert loaded["candidate_exhaustive_run"] is False


def test_static_all_weather_is_not_paper_forward_eligible(registration_run: dict[str, Any]) -> None:
    loaded = manifest(registration_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_static_all_weather_is_not_demo_active(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["paper_demo_eligible"] is False


def test_static_all_weather_is_not_live_ready(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["live_orders"] is False


def test_no_broker_live_path_is_touched(registration_run: dict[str, Any]) -> None:
    loaded = manifest(registration_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_no_new_backtest_is_run(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["backtests_run"] is False


def test_no_discovery_is_run(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["discovery_run"] is False


def test_no_provider_download_occurs(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["provider_download"] is False


def test_third_expansion_rejected_rows_remain_rejected(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["third_expansion_rejected_rows_reopened"] is False
    assert registration_run["strategies_before"] == registration_run["strategies_after"]


def test_allowed_usage_file_exists(registration_run: dict[str, Any]) -> None:
    assert (output(registration_run) / "static_all_weather_allowed_usage.md").exists()


def test_forbidden_usage_file_exists(registration_run: dict[str, Any]) -> None:
    assert (output(registration_run) / "static_all_weather_forbidden_usage.md").exists()


def test_manifest_flags_match_strict_scope(registration_run: dict[str, Any]) -> None:
    loaded = manifest(registration_run)
    for key, value in registration.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(registration_run)["consistency_passed"] is True


def test_next_action_is_valid(registration_run: dict[str, Any]) -> None:
    assert manifest(registration_run)["next_action"] in registration.VALID_NEXT_ACTIONS
