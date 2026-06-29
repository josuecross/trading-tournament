from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

import run_next_family_discovery_after_indicator_validation as discovery


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_cache_file(path: Path, symbol: str, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range(end=pd.Timestamp(datetime.now(timezone.utc).date()), periods=720)
    base = 50.0 + seed
    drift = 0.015 + (seed % 5) * 0.002
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"],
            lineterminator="\n",
        )
        writer.writeheader()
        for idx, day in enumerate(dates):
            wave = ((idx + seed) % 17 - 8) * 0.03
            price = max(5.0, base + idx * drift + wave)
            writer.writerow(
                {
                    "date": day.date().isoformat(),
                    "open": f"{price:.4f}",
                    "high": f"{price + 0.2:.4f}",
                    "low": f"{price - 0.2:.4f}",
                    "close": f"{price:.4f}",
                    "adj_close": f"{price:.4f}",
                    "volume": 100000 + idx,
                    "symbol": symbol,
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
            "current_next_action": "run_next_family_discovery_after_indicator_validation",
            "official_current_next_action": "run_next_family_discovery_after_indicator_validation",
            "intraday_research_remains_paused": True,
            "expansion_paused": True,
        },
        "risk_framework": {"active_framework": "balanced_speculative_research_v1"},
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
    registry_path = root / discovery.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / discovery.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        """# Research Roadmap

## Compact Current State

- Official current next action: `run_next_family_discovery_after_indicator_validation`
""",
        encoding="utf-8",
    )

    compact_path = root / discovery.COMPACT_STATE_PATH
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text("Current next action: `pre_register_indicator_library_integration_audit`\n", encoding="utf-8")

    write_json(
        root / discovery.PREREG_DIR / "next_family_preregistration_manifest.json",
        {
            "candidate_ids": [discovery.CANDIDATE_ID],
            "candidate_count": 1,
            "selected_family": discovery.SELECTED_FAMILY,
            "data_availability_status": "sufficient_for_preregistered_discovery",
            "indicator_library_dependency_added": False,
            "intraday_research_remains_paused": True,
            "next_action": "run_next_family_discovery_after_indicator_validation",
        },
    )
    candidate_specs = {
        "candidates": [
            {
                "candidate_id": discovery.CANDIDATE_ID,
                "family": discovery.SELECTED_FAMILY,
                "lane": discovery.LANE,
                "rules_frozen": True,
                "rule": {"allocation": "equal weight all wrappers passing both filters; if none pass, allocate 100% to BIL"},
            }
        ]
    }
    (root / discovery.PREREG_DIR / "candidate_specs.yaml").write_text(
        yaml.safe_dump(candidate_specs, sort_keys=False),
        encoding="utf-8",
    )
    write_json(
        root / discovery.MF_SAMPLE_DIR / "managed_futures_etf_wrapper_manifest.json",
        {"approved_symbols": discovery.REQUIRED_SYMBOLS, "provider_api_called": False, "data_downloaded": False},
    )
    for idx, symbol in enumerate(discovery.LOAD_SYMBOLS):
        write_cache_file(root / discovery.DATA_CACHE_DIR / f"{symbol}.csv", symbol, idx + 1)


@pytest.fixture(scope="module")
def discovery_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("next_family_discovery")
    write_fixture(root)
    before = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = discovery.run_next_family_discovery_after_indicator_validation(root)
    after = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(discovery_run: dict[str, Any]) -> Path:
    return Path(discovery_run["output_dir"])


def manifest(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "next_family_discovery_manifest.json").read_text(encoding="utf-8"))


def consistency(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "next_family_discovery_consistency_check.json").read_text(encoding="utf-8"))


def test_discovery_limited_to_authorized_candidate(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_id"] == discovery.CANDIDATE_ID


def test_candidate_count_evaluated_is_one(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_count_evaluated"] == 1


def test_preflight_state_reconciliation_exists(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "preflight_state_reconciliation.md").exists()
    compact = (discovery_run["root"] / discovery.COMPACT_STATE_PATH).read_text(encoding="utf-8")
    assert discovery.CANDIDATE_ID in compact


def test_no_indicator_library_dependency_added(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["provider_download"] is False


def test_no_intraday_data_used(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["broker_orders_cancelled"] is False


def test_no_live_orders(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["live_orders"] is False


def test_no_real_money_recommendation(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["active_strategy_state_changed"] is False
    assert discovery_run["strategies_before"] == discovery_run["strategies_after"]


def test_rejected_strategy_state_preserved(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["rejected_strategy_state_changed"] is False
    assert discovery_run["strategies_before"] == discovery_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["exact_rejected_variants_reopened"] is False
    metrics = json.loads((output(discovery_run) / f"candidate_metrics_{discovery.CANDIDATE_ID}.json").read_text(encoding="utf-8"))
    assert metrics["candidate_id"] not in discovery.OLD_MANAGED_FUTURES_ROWS


def test_intraday_remains_paused(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["intraday_research_remains_paused"] is True


def test_same_window_benchmark_comparison_exists(discovery_run: dict[str, Any]) -> None:
    path = output(discovery_run) / "same_window_benchmark_comparison.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        ids = {row["benchmark_id"] for row in csv.DictReader(handle)}
    assert discovery.CANDIDATE_ID in ids
    assert "active_combo_vm_dsr_equal_weight_v1" in ids


def test_limited_history_report_exists(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "candidate_window_and_limited_history_report.md").exists()


def test_duplication_review_exists(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "duplication_review.md").exists()


def test_risk_gate_review_exists(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "risk_gate_review.md").exists()


def test_candidate_outcome_is_valid(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_outcome"] in discovery.VALID_OUTCOMES


def test_next_action_is_valid(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["next_action"] in discovery.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    for key, expected in discovery.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(discovery_run)["consistency_passed"] is True
