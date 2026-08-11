from __future__ import annotations

import csv

import pytest

from execution_lab.alpaca_micro_live_v1.execution.imported_strategy_data_preflight import run_preflight

pytestmark = pytest.mark.alpaca_micro_live


def test_data_preflight_reports_missing_hyg_cache_without_network(tmp_path) -> None:
    result = run_preflight(first_batch=True, output_dir=tmp_path / "out", cache_dir=tmp_path / "cache")
    assert result["missing_or_insufficient"] == 1
    row = list(csv.DictReader((tmp_path / "out" / "data_preflight_report.csv").open(encoding="utf-8")))[0]
    assert row["required_symbol"] == "HYG"
    assert row["readonly_alpaca_bootstrap_needed"] == "true"
    assert row["network_used"] == "false"


def test_data_preflight_reports_sufficient_cache_without_network(tmp_path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with (cache / "HYG_1Day.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "close"])
        writer.writeheader()
        for idx in range(100):
            writer.writerow({"date": f"2026-01-{(idx % 28) + 1:02d}", "close": "100"})
    result = run_preflight(first_batch=True, output_dir=tmp_path / "out", cache_dir=cache)
    row = list(csv.DictReader((tmp_path / "out" / "data_preflight_report.csv").open(encoding="utf-8")))[0]
    assert result["missing_or_insufficient"] == 0
    assert row["status"] == "cache_sufficient"
    assert result["network_used"] is False


def test_explicit_readonly_bootstrap_is_separate_from_default_path(monkeypatch, tmp_path) -> None:
    called = {"value": False}

    def fake_bootstrap(_rows, _cache_dir):
        called["value"] = True

    import execution_lab.alpaca_micro_live_v1.execution.imported_strategy_data_preflight as module

    monkeypatch.setattr(module, "_readonly_bootstrap", fake_bootstrap)
    run_preflight(first_batch=True, output_dir=tmp_path / "default", cache_dir=tmp_path / "cache")
    assert called["value"] is False
    run_preflight(first_batch=True, output_dir=tmp_path / "explicit", cache_dir=tmp_path / "cache", allow_readonly_alpaca_fetch=True, write_cache=True)
    assert called["value"] is True
