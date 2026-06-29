from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_next_family_after_indicator_validation_preregistration as prereg


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_cache_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_date = datetime.now(timezone.utc).date()
    first_date = last_date - timedelta(days=430)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "open", "high", "low", "close", "adj_close", "volume"],
            lineterminator="\n",
        )
        writer.writeheader()
        for day in range(431):
            current = first_date + timedelta(days=day)
            price = 100.0 + day * 0.01
            writer.writerow(
                {
                    "date": current.isoformat(),
                    "open": f"{price:.2f}",
                    "high": f"{price + 1:.2f}",
                    "low": f"{price - 1:.2f}",
                    "close": f"{price:.2f}",
                    "adj_close": f"{price:.2f}",
                    "volume": 100000 + day,
                }
            )


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "pre_register_next_family_after_indicator_validation",
            "official_current_next_action": "pre_register_next_family_after_indicator_validation",
            "intraday_research_remains_paused": True,
            "expansion_paused": True,
        },
        "risk_framework": {
            "active_framework": "balanced_speculative_research_v1",
            "framework_path": "risk_framework/risk_framework.yaml",
        },
        "strategies": [
            {
                "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "managed_futures_etf_trend_wrapper_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / prereg.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / prereg.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        """# Research Roadmap

## Compact Current State

- Official current next action: `pre_register_next_family_after_indicator_validation`

## Priority Backlog

1. `managed_futures_etf_wrapper`
   - Status: `next_family_to_review`
""",
        encoding="utf-8",
    )

    write_json(
        root / prereg.MF_SAMPLE_DIR / "managed_futures_etf_wrapper_manifest.json",
        {"approved_symbols": prereg.REQUIRED_SYMBOLS, "provider_api_called": False, "data_downloaded": False},
    )
    for symbol in prereg.REQUIRED_SYMBOLS:
        write_cache_file(root / prereg.DATA_CACHE_DIR / f"{symbol}.csv")


@pytest.fixture(scope="module")
def prereg_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("next_family_after_indicator_validation")
    write_fixture(root)
    before_strategies = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = prereg.run_next_family_after_indicator_validation_preregistration(root)
    after_strategies = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before_strategies
    result["strategies_after"] = after_strategies
    return result


def output(prereg_run: dict[str, Any]) -> Path:
    return Path(prereg_run["output_dir"])


def manifest(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(prereg_run) / "next_family_preregistration_manifest.json").read_text(encoding="utf-8"))


def consistency(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(prereg_run) / "next_family_preregistration_consistency_check.json").read_text(encoding="utf-8")
    )


def test_family_preregistration_only_mode(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["family_preregistration_only"] is True


def test_no_strategy_discovery(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["strategy_discovery_run"] is False


def test_no_backtests(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["backtests_run"] is False


def test_no_new_performance_metrics(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["new_performance_metrics_computed"] is False


def test_no_indicator_library_dependency_added(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["provider_download"] is False


def test_no_intraday_data_used(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["broker_orders_cancelled"] is False


def test_no_live_orders(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["live_orders"] is False


def test_no_real_money_recommendation(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["active_strategy_state_changed"] is False
    assert prereg_run["strategies_before"] == prereg_run["strategies_after"]


def test_rejected_strategy_state_preserved(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["rejected_strategy_state_changed"] is False
    assert prereg_run["strategies_before"] == prereg_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    specs = yaml.safe_load((output(prereg_run) / "candidate_specs.yaml").read_text(encoding="utf-8"))
    candidate_ids = {candidate["candidate_id"] for candidate in specs["candidates"]}
    assert loaded["exact_rejected_variants_reopened"] is False
    assert "managed_futures_etf_trend_wrapper_v1" not in candidate_ids


def test_intraday_remains_paused(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["intraday_research_remains_paused"] is True


def test_selected_family_is_valid(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["selected_family"] in prereg.VALID_FAMILIES
    assert loaded["selected_family"] == "managed_futures_etf_wrapper"


def test_candidate_count_is_valid(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert 1 <= loaded["candidate_count"] <= 3
    assert loaded["candidate_count"] == 1


def test_candidate_specs_exist_if_candidate_count_positive(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    path = output(prereg_run) / "candidate_specs.yaml"
    assert loaded["candidate_count"] == 0 or path.exists()
    specs = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert specs["candidates"][0]["candidate_id"] == "mfv_equal_weight_trend_filter_v1"
    assert specs["candidates"][0]["rules_frozen"] is True


def test_data_availability_report_exists(prereg_run: dict[str, Any]) -> None:
    assert (output(prereg_run) / "family_data_availability_report.md").exists()
    assert manifest(prereg_run)["data_availability_status"] == "sufficient_for_preregistered_discovery"


def test_benchmark_plan_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "family_benchmark_plan.md").read_text(encoding="utf-8")
    assert "`SPY`" in text
    assert "`active_combo_vm_dsr_equal_weight_v1`" in text


def test_indicator_usage_plan_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "indicator_usage_plan.md").read_text(encoding="utf-8")
    assert "validated custom SMA" in text
    assert "external indicator-library outputs" in text


def test_do_not_run_now_file_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "do_not_run_now.md").read_text(encoding="utf-8")
    assert "strategy discovery" in text
    assert "provider downloads" in text
    assert "real-money recommendations" in text


def test_next_action_is_valid(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["next_action"] in prereg.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "run_next_family_discovery_after_indicator_validation"


def test_manifest_flags_match_strict_scope(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    for key, expected in prereg.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(prereg_run)["consistency_passed"] is True
