from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

import run_tournament_lane_gate_framework as framework


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_fixture(root: Path) -> None:
    registry_path = root / framework.REGISTRY_PATH
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
                    "current_next_action": "revise_tournament_gates_by_lane",
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "rejected_duplicate_test_v1",
                        "strategy_id": "rejected_duplicate_test_v1",
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
    roadmap = root / framework.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `revise_tournament_gates_by_lane`\n", encoding="utf-8")
    write_csv(
        root / framework.ROOT_CAUSE_DIR / "failure_reason_dashboard.csv",
        [
            {"strategy_id": "a", "primary_failure_reason": "duplication_or_high_correlation"},
            {"strategy_id": "b", "primary_failure_reason": "risk_buffer_or_drawdown"},
            {"strategy_id": "c", "primary_failure_reason": "data_or_incomplete_evidence"},
        ],
        ["strategy_id", "primary_failure_reason"],
    )


@pytest.fixture(scope="module")
def framework_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("lane_gate_framework")
    write_fixture(root)
    before = yaml.safe_load((root / framework.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = framework.run_tournament_lane_gate_framework(root)
    after = yaml.safe_load((root / framework.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = str(root)
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(framework_run: dict[str, object]) -> Path:
    return Path(framework_run["output_dir"])


def manifest(framework_run: dict[str, object]) -> dict[str, object]:
    return json.loads((output(framework_run) / "tournament_lane_gate_manifest.json").read_text(encoding="utf-8"))


def lane_yaml(framework_run: dict[str, object]) -> dict[str, object]:
    return yaml.safe_load((output(framework_run) / "lane_gate_framework.yaml").read_text(encoding="utf-8"))


def lanes(framework_run: dict[str, object]) -> dict[str, object]:
    return lane_yaml(framework_run)["lanes"]


def test_governance_only_mode(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["governance_only"] is True


def test_no_new_backtests(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["new_backtests_run"] is False


def test_no_new_discovery(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["new_discovery_run"] is False


def test_no_provider_download(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["provider_download"] is False


def test_no_candidate_exhaustive(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(framework_run: dict[str, object]) -> None:
    loaded = manifest(framework_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(framework_run: dict[str, object]) -> None:
    loaded = manifest(framework_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_five_lanes_are_defined(framework_run: dict[str, object]) -> None:
    assert set(lanes(framework_run)) == set(framework.LANE_IDS)


def test_each_lane_has_benchmark_group(framework_run: dict[str, object]) -> None:
    assert all(lane["benchmark_group"] for lane in lanes(framework_run).values())


def test_each_lane_has_risk_gates(framework_run: dict[str, object]) -> None:
    assert all(lane["risk_gates"] for lane in lanes(framework_run).values())


def test_each_lane_has_performance_gates(framework_run: dict[str, object]) -> None:
    assert all(lane["performance_gates"] for lane in lanes(framework_run).values())


def test_each_lane_has_promotion_and_rejection_rules(framework_run: dict[str, object]) -> None:
    assert all(lane["promotion_review_rules"] and lane["rejection_rules"] for lane in lanes(framework_run).values())


def test_intraday_lane_is_research_only(framework_run: dict[str, object]) -> None:
    intraday = lanes(framework_run)["intraday_research_only_lane"]
    assert "Research-only" in " ".join(intraday["demo_eligibility_rules"])
    assert "not demo eligible" in " ".join(intraday["demo_eligibility_rules"])


def test_macro_gld_lane_requires_same_window_benchmarks(framework_run: dict[str, object]) -> None:
    macro = lanes(framework_run)["macro_gld_duration_risk_off_lane"]
    text = " ".join(macro["benchmark_group"] + macro["performance_gates"])
    assert "same-window" in text


def test_diversifier_lane_includes_marginal_contribution_gates(framework_run: dict[str, object]) -> None:
    diversifier = lanes(framework_run)["diversifier_contribution_lane"]
    assert "Marginal contribution" in " ".join(diversifier["performance_gates"])


def test_moderate_tactical_lane_allows_lane_specific_trade_frequency(framework_run: dict[str, object]) -> None:
    tactical = lanes(framework_run)["moderate_tactical_etf_lane"]
    assert tactical["gate_decisions"]["max trades per week"] == "lane-specific"
    assert tactical["gate_decisions"]["max trades per day"] == "lane-specific"


def test_conservative_lane_keeps_strict_drawdown_risk_buffer(framework_run: dict[str, object]) -> None:
    conservative = lanes(framework_run)["conservative_etf_allocation_lane"]
    assert "Strict drawdown gate." in conservative["risk_gates"]
    assert "Strict risk buffer gate." in conservative["risk_gates"]


def test_no_accepted_or_rejected_strategy_state_is_changed(framework_run: dict[str, object]) -> None:
    assert framework_run["strategies_before"] == framework_run["strategies_after"]
    consistency = json.loads((output(framework_run) / "tournament_lane_gate_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["accepted_rejected_strategy_state_unchanged"] is True


def test_old_gld_gror_state_is_not_resumed(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["old_gld_gror_state_resumed"] is False


def test_next_action_is_valid(framework_run: dict[str, object]) -> None:
    assert manifest(framework_run)["next_action"] in framework.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(framework_run: dict[str, object]) -> None:
    loaded = manifest(framework_run)
    for key, value in framework.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert json.loads((output(framework_run) / "tournament_lane_gate_consistency_check.json").read_text(encoding="utf-8"))["consistency_passed"] is True
