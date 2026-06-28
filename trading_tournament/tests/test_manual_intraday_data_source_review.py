from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_manual_intraday_data_source_review as review


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
                    "current_next_action": "manual_intraday_data_source_review_required",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "rejected_daily_variant_v1",
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
    roadmap = root / review.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\nCurrent next action: `manual_intraday_data_source_review_required`\n",
        encoding="utf-8",
    )
    previous = root / review.FIX_PACKET_DIR / "intraday_blocker_fix_manifest.json"
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_text(
        json.dumps(
            {
                "blockers_fixed_count": 6,
                "blockers_partially_fixed_count": 2,
                "critical_blockers_remaining_count": 2,
                "intraday_cache_contract_created": True,
                "intraday_data_present": False,
                "intraday_data_source_approved": False,
                "readiness_verdict_after_fix": "manual_intraday_data_source_review_required",
                "next_action": "manual_intraday_data_source_review_required",
            }
        ),
        encoding="utf-8",
    )
    (root / review.CONFIG_PATH).write_text(
        yaml.safe_dump(
            {
                "data": {
                    "cache_dir": "data/cache",
                    "intraday_dir": "data/intraday",
                    "yfinance": {"auto_adjust": False},
                }
            }
        ),
        encoding="utf-8",
    )
    approved_map = root / review.APPROVED_SYMBOL_MAP_PATH
    approved_map.parent.mkdir(parents=True, exist_ok=True)
    approved_map.write_text(
        yaml.safe_dump(
            {
                "symbols": [
                    {"symbol": "SPY", "allowed_for_strategy": True},
                    {"symbol": "QQQ", "allowed_for_strategy": True},
                    {"symbol": "BIL", "allowed_for_strategy": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    fast_policy = root / review.FAST_DATA_POLICY_PATH
    fast_policy.parent.mkdir(parents=True, exist_ok=True)
    fast_policy.write_text(
        "For ETF wrappers, daily yfinance-compatible data is exploratory. Intraday requires separate data, execution, risk, and terms reviews.",
        encoding="utf-8",
    )
    global_config = root / review.GLOBAL_ACQUISITION_CONFIG_PATH
    global_config.parent.mkdir(parents=True, exist_ok=True)
    global_config.write_text("provider: yfinance_compatible\n", encoding="utf-8")
    alpaca_daily = root / review.ALPACA_DAILY_BARS_PATH
    alpaca_daily.parent.mkdir(parents=True, exist_ok=True)
    alpaca_daily.write_text('pd.to_datetime(bar.get("t"), utc=True)\ntimeframe="1Day"\n', encoding="utf-8")
    alpaca_cache = root / review.ALPACA_CACHE_PATH
    alpaca_cache.parent.mkdir(parents=True, exist_ok=True)
    alpaca_cache.write_text('return root / f"{symbol}_1Day.csv"\n', encoding="utf-8")


@pytest.fixture(scope="module")
def review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("manual_intraday_data_source_review")
    write_fixture(root)
    before = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_manual_intraday_data_source_review(root)
    after = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(review_run: dict[str, Any]) -> Path:
    return Path(review_run["output_dir"])


def manifest(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "intraday_data_source_review_manifest.json").read_text(encoding="utf-8"))


def consistency(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "intraday_data_source_review_consistency_check.json").read_text(encoding="utf-8"))


def test_data_source_review_only_mode(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["data_source_review_only"] is True


def test_no_intraday_backtests(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["intraday_backtests_run"] is False


def test_no_new_discovery(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["new_discovery_run"] is False


def test_no_new_performance_metrics(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["provider_download"] is False


def test_no_provider_api_call(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["provider_api_called"] is False


def test_no_intraday_cache_bootstrap(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert loaded["intraday_cache_bootstrapped"] is False
    assert loaded["intraday_data_downloaded"] is False


def test_no_candidate_exhaustive(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["broker_orders_cancelled"] is False


def test_no_live_orders(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["live_orders"] is False


def test_no_strategy_state_changes(review_run: dict[str, Any]) -> None:
    assert review_run["strategies_before"] == review_run["strategies_after"]


def test_candidate_source_inventory_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "intraday_candidate_source_inventory.csv").exists()


def test_source_fit_assessment_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "intraday_source_fit_assessment.csv").exists()


def test_license_terms_review_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "intraday_license_terms_review_needed.md").exists()


def test_cache_bootstrap_requirements_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "intraday_cache_bootstrap_requirements.md").exists()


def test_decision_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "intraday_data_source_decision.md").exists()


def test_next_action_is_valid(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["next_action"] in review.VALID_NEXT_ACTIONS
    assert manifest(review_run)["next_action"] == "manual_intraday_data_source_review_required"


def test_manifest_flags_match_strict_scope(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    for key, value in review.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert loaded["approved_intraday_data_source_found"] is False
    assert loaded["manual_terms_review_required"] is True
    assert loaded["local_intraday_data_present"] is False
    assert consistency(review_run)["consistency_passed"] is True
