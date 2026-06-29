from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_pause_expansion_summary as pause


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "intraday_research_remains_paused": True,
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
                "id": "rc_dual_momentum_paa_vol_scaled_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / pause.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    roadmap_path = root / pause.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text("# Research Roadmap\n", encoding="utf-8")
    compact_path = root / pause.COMPACT_STATE_PATH
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text("# Current Tournament State\n", encoding="utf-8")
    write_json(
        root / pause.RISK_AUDIT_DIR / "risk_controlled_failure_audit_manifest.json",
        {"promotion_candidates_current_count": 0, "next_action": "pause_expansion_and_summarize_tournament_state"},
    )


@pytest.fixture(scope="module")
def pause_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("pause_expansion_summary")
    write_fixture(root)
    before = yaml.safe_load((root / pause.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = pause.run_pause_expansion_summary(root)
    after = yaml.safe_load((root / pause.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(pause_run: dict[str, Any]) -> Path:
    return Path(pause_run["output_dir"])


def manifest(pause_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(pause_run) / "pause_expansion_summary_manifest.json").read_text(encoding="utf-8"))


def consistency(pause_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(pause_run) / "pause_expansion_consistency_check.json").read_text(encoding="utf-8"))


def test_pause_checkpoint_only_mode(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["pause_checkpoint_only"] is True


def test_expansion_paused(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["expansion_paused"] is True


def test_no_strategy_discovery(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["strategy_discovery_run"] is False


def test_no_backtests(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["backtests_run"] is False


def test_no_new_performance_metrics(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["provider_download"] is False


def test_no_intraday_data_used(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(pause_run: dict[str, Any]) -> None:
    loaded = manifest(pause_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["broker_orders_cancelled"] is False


def test_no_live_orders(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["live_orders"] is False


def test_no_real_money_recommendation(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["active_strategy_state_changed"] is False
    assert pause_run["strategies_before"] == pause_run["strategies_after"]


def test_rejected_strategy_state_preserved(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["rejected_strategy_state_changed"] is False
    assert pause_run["strategies_before"] == pause_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["intraday_research_remains_paused"] is True


def test_active_benchmark_state_file_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "active_and_benchmark_state.md").exists()


def test_closed_variants_summary_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "closed_exact_variants_summary.md").exists()


def test_family_status_checkpoint_exists(pause_run: dict[str, Any]) -> None:
    path = output(pause_run) / "family_status_checkpoint.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 10


def test_lessons_learned_summary_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "lessons_learned_summary.md").exists()


def test_forbidden_next_steps_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "forbidden_next_steps.md").exists()


def test_next_action_is_valid(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["next_action"] in pause.VALID_NEXT_ACTIONS
    assert manifest(pause_run)["next_action"] == "pre_register_indicator_library_integration_audit"


def test_manifest_flags_match_strict_scope(pause_run: dict[str, Any]) -> None:
    loaded = manifest(pause_run)
    for key, expected in pause.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(pause_run)["consistency_passed"] is True
