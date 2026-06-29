from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_indicator_validation_harness_preregistration as prereg


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
            "current_next_action": "pre_register_indicator_validation_harness",
            "official_current_next_action": "pre_register_indicator_validation_harness",
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
                "id": "rc_donchian_breakout_risk_budget_v1",
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

- Official current next action: `pre_register_indicator_validation_harness`

## Priority Backlog

- Historical section.
""",
        encoding="utf-8",
    )

    for path, text in {
        prereg.INDICATOR_CODE_PATH: "def sma(series, window):\n    return series\n",
        prereg.STRATEGY_CODE_PATH: "from .indicators import indicators_ready\n",
        prereg.BACKTESTER_CODE_PATH: "INDICATOR_COLUMNS = ['sma_200']\n",
        prereg.APPROVED_INDICATORS_PATH: "new_dependency_added: false\n",
        prereg.INDICATOR_POLICY_PATH: "# Indicator Policy\n",
    }.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    write_json(
        root / prereg.PRIOR_AUDIT_DIR / "indicator_library_audit_manifest.json",
        {
            "dependency_decision": "no_dependency_added_policy_only",
            "selected_library": "current_custom_indicators_only",
            "library_dependency_added": False,
            "next_action": "pre_register_indicator_validation_harness",
        },
    )


@pytest.fixture(scope="module")
def prereg_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("indicator_validation_prereg")
    write_fixture(root)
    before = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = prereg.run_indicator_validation_harness_preregistration(root)
    after = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(prereg_run: dict[str, Any]) -> Path:
    return Path(prereg_run["output_dir"])


def manifest(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(prereg_run) / "indicator_validation_harness_manifest.json").read_text(encoding="utf-8"))


def consistency(prereg_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(prereg_run) / "indicator_validation_harness_consistency_check.json").read_text(encoding="utf-8"))


def test_indicator_validation_preregistration_only_mode(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["indicator_validation_preregistration_only"] is True


def test_no_indicator_library_dependency_added(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["indicator_library_dependency_added"] is False


def test_no_strategy_discovery(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["strategy_discovery_run"] is False


def test_no_backtests(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["backtests_run"] is False


def test_no_new_performance_metrics(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["new_performance_metrics_computed"] is False


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
    assert manifest(prereg_run)["exact_rejected_variants_reopened"] is False


def test_expansion_remains_paused(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["expansion_remains_paused"] is True


def test_intraday_remains_paused(prereg_run: dict[str, Any]) -> None:
    assert manifest(prereg_run)["intraday_research_remains_paused"] is True


def test_fixture_plan_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "indicator_fixture_plan.md").read_text(encoding="utf-8")
    assert "flat_price_fixture" in text
    assert "known_manual_calculation_fixture" in text
    assert manifest(prereg_run)["fixture_types_count"] == 7


def test_lookahead_prevention_plan_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "indicator_lookahead_prevention_plan.md").read_text(encoding="utf-8")
    assert "current signal bar" in text
    assert "incomplete current period" in text
    assert manifest(prereg_run)["lookahead_checks_defined"] == 6


def test_indicator_validation_status_matrix_exists(prereg_run: dict[str, Any]) -> None:
    path = output(prereg_run) / "indicator_validation_status_matrix.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 15
    statuses = {row["validation_status"] for row in rows}
    assert "validation_planned" in statuses
    assert "gated_requires_validation" in statuses


def test_parity_test_policy_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "indicator_parity_test_policy.md").read_text(encoding="utf-8")
    assert "No new indicator library is installed" in text
    assert "parity-tested" in text
    assert manifest(prereg_run)["parity_policy_defined"] is True


def test_do_not_run_now_file_exists(prereg_run: dict[str, Any]) -> None:
    text = (output(prereg_run) / "indicator_validation_do_not_run_now.md").read_text(encoding="utf-8")
    assert "strategy discovery" in text
    assert "provider downloads" in text
    assert "real-money recommendations" in text


def test_next_action_is_valid(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["next_action"] in prereg.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "implement_indicator_validation_harness"


def test_manifest_flags_match_strict_scope(prereg_run: dict[str, Any]) -> None:
    loaded = manifest(prereg_run)
    for key, expected in prereg.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(prereg_run)["consistency_passed"] is True
