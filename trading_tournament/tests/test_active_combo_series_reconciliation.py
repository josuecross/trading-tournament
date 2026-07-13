from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import active_combo_series_reconciliation as reconciliation


def write_price_cache(root: Path, symbol: str, periods: int = 620, drift: float = 0.0002) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for idx, symbol in enumerate(active.REQUIRED_CACHE_SYMBOLS + active.OPTIONAL_BENCHMARK_SYMBOLS):
        write_price_cache(root, symbol, drift=0.00006 + idx * 0.000006)


def registry_row(row_id: str, active_flag: bool) -> dict[str, object]:
    return {
        "id": row_id,
        "display_name": row_id,
        "status": "active_paper_demo_observation" if active_flag else "keep_watchlist",
        "paper_forward_active": active_flag,
        "rules_frozen": active_flag,
        "frozen": active_flag,
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "real_money_recommendation": False,
    }


def write_registry(root: Path) -> None:
    rows = [
        registry_row(active.VM_ID, True),
        registry_row(active.DSR_ID, True),
        registry_row(active.SPY_200D_ID, True),
        registry_row("gror_balanced_momentum_60_40_v1", False),
    ]
    path = root / combo.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True, "etf_discovery_status": "paused"},
                "risk_framework": {},
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_checkpoint(root: Path) -> None:
    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / "current_research_checkpoint_manifest.json").write_text(
        json.dumps({"stale_candidate_exhaustive_flags": [], "stale_promotion_review_flags": []}),
        encoding="utf-8",
    )
    with (checkpoint / "candidate_pipeline_status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "count", "rows", "status", "next_action"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {"stage": "promotion_review_candidates", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
                {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
                {"stage": "paper_forward_active", "count": 2, "rows": f"{active.VM_ID};{active.DSR_ID}", "status": "protected", "next_action": "observe_only"},
            ]
        )


def write_active_observations(root: Path) -> None:
    observations = {
        active.VM_ID: {"observation_id": active.VM_ID, "base_strategy_id": "vm_quality_lowvol_proxy_v1", "status": "active_paper_demo_observation", "paper_forward_active": True, "frozen": True, "rules_frozen": True},
        active.DSR_ID: {"observation_id": active.DSR_ID, "base_strategy_id": "dsr_sector_equal_weight_defensive_filter_v1", "status": "active_paper_demo_observation", "paper_forward_active": True, "frozen": True, "rules_frozen": True},
    }
    for strategy_id, payload in observations.items():
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_control_registries(root: Path) -> None:
    path = root / reconciliation.BENCHMARK_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"controls": {combo.COMBO_ID: {"status": "benchmark_watchlist_reference", "role": "active VM/DSR combo reference only"}}}, sort_keys=False),
        encoding="utf-8",
    )
    ops = root / reconciliation.ACTIVE_OBSERVATIONS_PATH
    ops.parent.mkdir(parents=True, exist_ok=True)
    ops.write_text(yaml.safe_dump({"references": ["active_combo"]}, sort_keys=False), encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def synthetic_reconciliation(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    tmp_path = tmp_path_factory.mktemp("active_combo_reconciliation")
    write_registry(tmp_path)
    write_checkpoint(tmp_path)
    write_active_observations(tmp_path)
    write_control_registries(tmp_path)
    write_required_cache(tmp_path)
    combo.run_active_combo_benchmark_reporting(tmp_path, strict_state=False)
    result = reconciliation.run_active_combo_series_reconciliation(tmp_path)
    return {"root": tmp_path, "result": result}


def test_canonical_combo_identity_is_resolved(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    rows = list(csv.DictReader((root / reconciliation.OUTPUT_DIR / "combo_identity_and_lineage.csv").open(encoding="utf-8")))
    assert rows[0]["combo_id"] == combo.COMBO_ID
    assert rows[0]["role"] == "benchmark_reference_only"
    assert rows[0]["lifecycle_status"] == "benchmark_watchlist_reference"


def test_frozen_components_and_no_inferred_weights(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    rows = list(csv.DictReader((root / reconciliation.OUTPUT_DIR / "component_definition.csv").open(encoding="utf-8")))
    assert [row["component_strategy_id"] for row in rows] == [active.VM_ID, active.DSR_ID]
    assert [row["allocation"] for row in rows] == ["0.5", "0.5"]
    assert all(row["frozen"] == "True" and row["rules_frozen"] == "True" for row in rows)


def test_reconstruction_is_exact_and_deterministic(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    output = root / reconciliation.OUTPUT_DIR
    first_hash = file_hash(output / "combo_daily_series.csv")
    reconciliation.run_active_combo_series_reconciliation(root)
    second_hash = file_hash(output / "combo_daily_series.csv")
    manifest = json.loads((output / "active_combo_series_reconciliation.json").read_text(encoding="utf-8"))
    assert first_hash == second_hash
    assert manifest["reconstructability_classification"] == "exactly_reconstructable"
    assert manifest["source_series_reproduced"] is True


def test_alignment_exposure_and_cash_invariants_pass(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    output = root / reconciliation.OUTPUT_DIR
    manifest = json.loads((output / "active_combo_series_reconciliation.json").read_text(encoding="utf-8"))
    consistency = json.loads((output / "reconciliation_consistency_check.json").read_text(encoding="utf-8"))
    assert manifest["max_daily_exposure"] <= 1.0
    assert manifest["weight_invariant_passed"] is True
    assert manifest["bil_remainder_passed"] is True
    assert manifest["date_alignment_passed"] is True
    assert consistency["no_unverified_dsr_metric_used"] is True


def test_no_summary_metrics_are_used_as_portfolio_inputs(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    text = (root / reconciliation.OUTPUT_DIR / "missing_or_conflicting_inputs.csv").read_text(encoding="utf-8")
    source = Path("run_active_combo_benchmark_reporting.py").read_text(encoding="utf-8")
    assert "all_required_inputs,available" in text
    assert "4071.04" not in source


def test_checkpoint_inclusion_is_allowed_only_after_exact_reconstruction(synthetic_reconciliation: dict[str, object]) -> None:
    root = Path(synthetic_reconciliation["root"])
    rows = list(csv.DictReader((root / reconciliation.OUTPUT_DIR / "checkpoint_integration_review.csv").open(encoding="utf-8")))
    assert rows[0]["include_in_checkpoint"] == "True"
    assert rows[0]["recommended_action"] == "compare_only"
