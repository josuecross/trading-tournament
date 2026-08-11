from __future__ import annotations

import csv
import json

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution.imported_strategy_dry_run import run_imported_strategy_dry_run

pytestmark = pytest.mark.alpaca_micro_live


def _write_spec(root, strategy_id: str, package_id: str, *, frozen_reference: bool = False) -> None:
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


def test_imported_strategy_dry_run_writes_evidence_and_blocks_missing_provider(tmp_path) -> None:
    generated = tmp_path / "generated"
    _write_spec(generated, "ice_vaneck_us_fallen_angel_angl_v1", "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1", frozen_reference=True)
    _write_spec(generated, "schwoerer_hyg_ema100_spy_bil_v1", "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1")
    _write_spec(generated, "barbara_decelerated_psar_spy_bil_v1", "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1", frozen_reference=True)
    _write_spec(generated, "factory_v1_spy_trend_quality_state_d1", "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1", frozen_reference=True)
    result = run_imported_strategy_dry_run(
        first_batch=True,
        output_dir=tmp_path / "out",
        registry_path=tmp_path / "dry_run_import_registry.yaml",
        generated_spec_dir=generated,
        cache_dir=tmp_path / "cache",
        as_of="2026-08-11",
    )
    assert result["strategies_selected"] == 4
    assert result["blocked_dry_run_targets"] == 4
    rows = list(csv.DictReader((tmp_path / "out" / "first_batch_dry_run_status.csv").open(encoding="utf-8")))
    assert any("frozen_reference_source_missing" in row["blocked_reason"] for row in rows)
    assert any("data_requirement_gap" in row["blocked_reason"] for row in rows)
    safety = json.loads((tmp_path / "out" / "safety_check.json").read_text(encoding="utf-8"))
    assert safety["broker_order_endpoints_called"] is False
    assert safety["paper_orders_submitted"] is False
    assert safety["live_orders_submitted"] is False


def test_generated_strategy_never_becomes_runtime_ready_or_paper_enabled(tmp_path) -> None:
    generated = tmp_path / "generated"
    _write_spec(generated, "ice_vaneck_us_fallen_angel_angl_v1", "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1", frozen_reference=True)
    run_imported_strategy_dry_run(
        strategy_id="ice_vaneck_us_fallen_angel_angl_v1",
        output_dir=tmp_path / "out",
        registry_path=tmp_path / "dry_run_import_registry.yaml",
        generated_spec_dir=generated,
        cache_dir=tmp_path / "cache",
    )
    spec = yaml.safe_load((generated / "ice_vaneck_us_fallen_angel_angl_v1.yaml").read_text(encoding="utf-8"))
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False
    assert spec["live_trading_allowed"] is False


def test_imported_dry_run_has_no_tournament_or_broker_network_dependency() -> None:
    import execution_lab.alpaca_micro_live_v1.execution.imported_strategy_dry_run as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "from trading_tournament" not in source
    assert "import trading_tournament" not in source
    assert "submit_order(" not in source
    assert "AlpacaClient" not in source
    assert "requests" not in source
    assert "httpx" not in source
