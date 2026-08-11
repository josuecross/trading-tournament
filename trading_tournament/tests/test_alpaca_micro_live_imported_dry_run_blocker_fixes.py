from __future__ import annotations

import csv
import json

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution.imported_strategy_dry_run import run_imported_strategy_dry_run

pytestmark = pytest.mark.alpaca_micro_live


def _write_spec(root, strategy_id: str, package_id: str, *, frozen_reference: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{strategy_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "strategy_id": strategy_id,
                "handoff_package_id": package_id,
                "enabled": False,
                "runtime_ready": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "conformance": {"status": "fixture_passed"},
                "provider_requirements": ["frozen_reference"] if frozen_reference else ["alpaca_equity_etf_daily_bars"],
                "required_instruments": ["FROZEN_REFERENCE"] if frozen_reference else ["HYG", "SPY", "BIL"],
            }
        ),
        encoding="utf-8",
    )


def test_imported_dry_run_uses_frozen_provider_only_when_available(tmp_path) -> None:
    package_id = "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1"
    _write_spec(tmp_path / "generated", "ice_vaneck_us_fallen_angel_angl_v1", package_id, frozen_reference=True)
    result = run_imported_strategy_dry_run(
        strategy_id="ice_vaneck_us_fallen_angel_angl_v1",
        output_dir=tmp_path / "out",
        blocker_fix_output_dir=tmp_path / "fixes",
        registry_path=tmp_path / "registry.yaml",
        generated_spec_dir=tmp_path / "generated",
        immutable_root=tmp_path / "immutable",
    )
    assert result["blocked_dry_run_targets"] == 1
    package = tmp_path / "immutable" / package_id
    package.mkdir(parents=True)
    (package / "frozen_reference_virtual_sleeve.json").write_text(json.dumps({"schema_id": "frozen_reference_virtual_sleeve_v1", "target_weights": {"SPY": 1.0}}), encoding="utf-8")
    result = run_imported_strategy_dry_run(
        strategy_id="ice_vaneck_us_fallen_angel_angl_v1",
        output_dir=tmp_path / "out2",
        blocker_fix_output_dir=tmp_path / "fixes2",
        registry_path=tmp_path / "registry.yaml",
        generated_spec_dir=tmp_path / "generated",
        immutable_root=tmp_path / "immutable",
    )
    assert result["target_generated"] == 1
    rows = list(csv.DictReader((tmp_path / "out2" / "first_batch_dry_run_status.csv").open(encoding="utf-8")))
    assert rows[0]["target_generation_status"] == "dry_run_target_generated_disabled"
    assert rows[0]["blocked_reason"] == ""


def test_missing_providers_stay_blocked_and_do_not_enable_strategy(tmp_path) -> None:
    package_id = "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1"
    _write_spec(tmp_path / "generated", "barbara_decelerated_psar_spy_bil_v1", package_id, frozen_reference=True)
    run_imported_strategy_dry_run(
        strategy_id="barbara_decelerated_psar_spy_bil_v1",
        output_dir=tmp_path / "out",
        blocker_fix_output_dir=tmp_path / "fixes",
        registry_path=tmp_path / "registry.yaml",
        generated_spec_dir=tmp_path / "generated",
        immutable_root=tmp_path / "immutable",
    )
    spec = yaml.safe_load((tmp_path / "generated" / "barbara_decelerated_psar_spy_bil_v1.yaml").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((tmp_path / "out" / "first_batch_dry_run_status.csv").open(encoding="utf-8")))
    assert "frozen_reference_source_missing" in rows[0]["blocked_reason"]
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False
    assert spec["live_trading_allowed"] is False


def test_blocker_fix_evidence_safety_has_no_orders_or_network(tmp_path) -> None:
    package_id = "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1"
    _write_spec(tmp_path / "generated", "factory_v1_spy_trend_quality_state_d1", package_id, frozen_reference=True)
    run_imported_strategy_dry_run(
        strategy_id="factory_v1_spy_trend_quality_state_d1",
        output_dir=tmp_path / "out",
        blocker_fix_output_dir=tmp_path / "fixes",
        registry_path=tmp_path / "registry.yaml",
        generated_spec_dir=tmp_path / "generated",
        immutable_root=tmp_path / "immutable",
    )
    safety = json.loads((tmp_path / "fixes" / "safety_check.json").read_text(encoding="utf-8"))
    assert safety["broker_order_endpoints_called"] is False
    assert safety["paper_orders_submitted"] is False
    assert safety["live_orders_submitted"] is False
    assert safety["generated_specs_runtime_ready"] is False
