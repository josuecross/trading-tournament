from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_risk_controlled_high_return_failure_audit as audit


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_fixture(root: Path) -> None:
    registry_path = root / audit.REGISTRY_PATH
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
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "rc_dual_momentum_paa_vol_scaled_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "rc_donchian_breakout_risk_budget_v1",
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
    roadmap_path = root / audit.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text("# Research Roadmap\n", encoding="utf-8")
    write_json(
        root / audit.DISCOVERY_DIR / "risk_controlled_discovery_manifest.json",
        {
            "promotion_candidates_count": 0,
            "invalidated_55_day_donchian_used": False,
            "candidate_ids": [
                "rc_dual_momentum_paa_vol_scaled_v1",
                "rc_donchian_breakout_risk_budget_v1",
            ],
        },
    )
    write_csv(
        root / audit.DISCOVERY_DIR / "risk_controlled_candidate_results.csv",
        [
            {
                "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
                "outcome": "discovery_reject",
                "decision_reason": "risk_buffer_fails;slippage_stress_fails",
            },
            {
                "candidate_id": "rc_donchian_breakout_risk_budget_v1",
                "outcome": "discovery_reject",
                "decision_reason": "slippage_stress_fails;skip_block_logic_dominates_results",
            },
        ],
        ["candidate_id", "outcome", "decision_reason"],
    )
    write_json(root / audit.DISCOVERY_DIR / "risk_controlled_candidate_metrics.json", {})


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("risk_controlled_failure_audit")
    write_fixture(root)
    result = audit.run_risk_controlled_high_return_failure_audit(root)
    result["root"] = root
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "risk_controlled_failure_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "risk_controlled_failure_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["audit_only"] is True


def test_no_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["backtests_run"] is False


def test_no_discovery(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["discovery_run"] is False


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


def test_no_broker_live_path(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["real_money_recommendation"] is False


def test_no_exact_rejected_variants_reopened(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["exact_rejected_variants_reopened"] is False


def test_no_new_candidates_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_strategy_candidates_created"] is False


def test_no_risk_controls_tuned(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["risk_controls_tuned"] is False


def test_no_gates_relaxed(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["gates_relaxed"] is False


def test_intraday_remains_paused(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_research_remains_paused"] is True


def test_candidate_failure_classification_exists(audit_run: dict[str, Any]) -> None:
    path = output(audit_run) / "risk_controlled_candidate_failure_classification.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["clean_reject"] for row in rows} == {"True"}


def test_dual_momentum_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "dual_momentum_vol_scaled_failure_review.md").exists()


def test_donchian_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "donchian_risk_budget_failure_review.md").exists()


def test_methodology_implementation_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "methodology_and_implementation_review.md").exists()


def test_project_state_recommendation_exists(audit_run: dict[str, Any]) -> None:
    path = output(audit_run) / "project_state_recommendation.md"
    assert path.exists()
    assert audit.NEXT_ACTION in path.read_text(encoding="utf-8")


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS
    assert manifest(audit_run)["next_action"] == "pause_expansion_and_summarize_tournament_state"


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(audit_run)["consistency_passed"] is True
