from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_indicator_library_integration_audit as audit


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "pre_register_indicator_library_integration_audit",
            "official_current_next_action": "pre_register_indicator_library_integration_audit",
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
    registry_path = root / audit.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / audit.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        """# Research Roadmap

## Compact Current State

- Official current next action: `audit_risk_controlled_high_return_discovery_failures`

## Priority Backlog

- Historical section.
""",
        encoding="utf-8",
    )

    indicator_policy = root / audit.INDICATOR_POLICY_PATH
    indicator_policy.parent.mkdir(parents=True, exist_ok=True)
    indicator_policy.write_text("# Indicator Policy\n", encoding="utf-8")
    approved = root / audit.APPROVED_INDICATORS_PATH
    approved.write_text("new_dependency_added: false\n", encoding="utf-8")
    requirements = root / audit.REQUIREMENTS_PATH
    requirements.write_text("pandas\nnumpy\npyyaml\npytest\n", encoding="utf-8")
    custom = root / audit.CUSTOM_INDICATOR_PATH
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("def sma(series, window):\n    return series\n", encoding="utf-8")


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("indicator_library_audit")
    write_fixture(root)
    before = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_indicator_library_integration_audit(root)
    after = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "indicator_library_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "indicator_library_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_indicator_governance_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["indicator_governance_only"] is True


def test_no_strategy_discovery(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["strategy_discovery_run"] is False


def test_no_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["backtests_run"] is False


def test_no_new_performance_metrics(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_intraday_data_used(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["broker_orders_cancelled"] is False


def test_no_live_orders(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["live_orders"] is False


def test_no_real_money_recommendation(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["active_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_rejected_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["rejected_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_research_remains_paused"] is True


def test_expansion_remains_paused(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["expansion_remains_paused"] is True


def test_current_indicator_inventory_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "current_indicator_usage_inventory.md").exists()


def test_candidate_library_review_exists(audit_run: dict[str, Any]) -> None:
    path = output(audit_run) / "candidate_indicator_library_review.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "`ta`" in text
    assert "`TA-Lib`" in text
    assert "`vectorbt_indicator_layer_only`" in text


def test_indicator_allowlist_exists(audit_run: dict[str, Any]) -> None:
    data = yaml.safe_load((output(audit_run) / "approved_indicator_allowlist.yaml").read_text(encoding="utf-8"))
    assert "trend" in data["allowed_initial_categories"]
    assert data["library_dependency_added"] is False


def test_forbidden_indicator_usage_file_exists(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "forbidden_indicator_usage.md").read_text(encoding="utf-8")
    assert "broad indicator mining" in text
    assert "intraday indicator strategies" in text


def test_validation_policy_exists(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "indicator_validation_policy.md").read_text(encoding="utf-8")
    assert "lookahead" in text.lower()
    assert "synthetic fixtures" in text


def test_overfitting_controls_exist(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "indicator_overfitting_controls.md").read_text(encoding="utf-8")
    assert "family hypothesis" in text
    assert "No indicator grid" in text


def test_dependency_decision_is_valid(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["dependency_decision"] in audit.VALID_DECISIONS
    assert loaded["dependency_decision"] == "no_dependency_added_policy_only"
    assert loaded["library_dependency_added"] is False


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["next_action"] in audit.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "pre_register_indicator_validation_harness"


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["roadmap_next_action_reconciled"] is True
    assert consistency(audit_run)["consistency_passed"] is True
