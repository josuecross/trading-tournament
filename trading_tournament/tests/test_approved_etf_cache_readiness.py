from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_approved_etf_cache_readiness_audit as audit


def raw_frame(symbol: str, periods: int = 300) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + 0.0002 + 0.0001 * ((idx % 5) - 2)))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": [100000] * periods,
            "Dividends": [0.0] * periods,
            "Stock Splits": [0.0] * periods,
        }
    )


def write_cache(root: Path, symbol: str, periods: int = 300) -> None:
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    audit.build_adjusted_ohlc(raw_frame(symbol, periods), symbol).to_csv(target, index=False)


def write_map(root: Path, symbols: list[dict]) -> None:
    path = root / audit.SYMBOL_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": "trading_tournament",
                "research_only": True,
                "data_label": "exploratory_non_institutional_not_real_money_ready",
                "symbols": symbols,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / audit.POLICY_PATH).write_text("policy", encoding="utf-8")


def symbol(symbol: str, group: str = "test", strategy: bool = True, benchmark: bool = True, enabled: bool = True) -> dict:
    row = {
        "symbol": symbol,
        "group": group,
        "allowed_for_strategy": strategy,
        "allowed_for_benchmark": benchmark,
        "requires_explicit_prompt": False,
        "notes": "test",
    }
    if not enabled:
        row["enabled_by_default"] = False
    return row


def test_approved_symbol_map_loads() -> None:
    data = audit.load_symbol_map(Path.cwd())
    symbols = {row["symbol"] for row in data["symbols"]}
    assert {"SPY", "XLK", "XLC", "DBMF", "SCHD", "HYG", "DBC"} <= symbols


def test_forbidden_symbols_are_not_allowed(tmp_path: Path) -> None:
    write_map(tmp_path, [symbol("AAPL")])
    with pytest.raises(ValueError):
        audit.load_symbol_map(tmp_path)


def test_audit_only_does_not_download_and_reports_missing(tmp_path: Path) -> None:
    write_map(tmp_path, [symbol("SPY"), symbol("XLK")])
    write_cache(tmp_path, "SPY")
    result = audit.run_cache_readiness_audit(tmp_path, bootstrap_approved_missing=False, downloader=lambda *args: (_ for _ in ()).throw(AssertionError("no download")))
    assert result["downloaded_symbols"] == []
    assert result["missing_symbols"] == ["XLK"]
    log = pd.read_csv(Path(result["output_dir"]) / "bootstrap_download_log.csv")
    assert log["download_attempted"].astype(str).str.lower().eq("false").all()


def test_bootstrap_mode_only_allows_approved_symbols(tmp_path: Path) -> None:
    write_map(tmp_path, [symbol("SPY"), symbol("XLK"), symbol("DBC", strategy=False, benchmark=True, enabled=False)])
    write_cache(tmp_path, "SPY")
    calls: list[str] = []

    def downloader(sym: str, start: str, end: str | None, params: dict) -> pd.DataFrame:
        calls.append(sym)
        return raw_frame(sym)

    result = audit.run_cache_readiness_audit(tmp_path, bootstrap_approved_missing=True, downloader=downloader)
    assert calls == ["XLK"]
    assert result["downloaded_symbols"] == ["XLK"]
    assert "DBC" not in result["downloaded_symbols"]
    assert set(result["downloaded_symbols"]) <= audit.bootstrap_allowed_symbols(audit.load_symbol_map(tmp_path))


def test_family_readiness_detects_missing_symbols() -> None:
    status = {sym: {"qa_status": "passed"} for sym in ["SPY", "BIL"]}
    rows = audit.family_cache_readiness_rows(status)
    dsr = {row["family"]: row for row in rows}["defensive_sector_rotation_etf"]
    assert dsr["readiness_status"] == "missing_required_symbols"
    assert "XLK" in dsr["missing_symbols"]


def test_prior_result_audit_marks_dsr_top2_incomplete_when_sector_missing() -> None:
    family_rows = audit.family_cache_readiness_rows({"SPY": {"qa_status": "passed"}, "BIL": {"qa_status": "passed"}})
    rows = audit.prior_result_rows(family_rows)
    target = {row["result_id"]: row for row in rows}["dsr_sector_top2_momentum_200d_bil_v1_promotion_review"]
    assert target["classification"] == "data_missing_incomplete"
    assert "XLK" in target["missing_symbols"]


def test_watchlist_is_not_invalid_just_because_watchlist() -> None:
    status = {sym: {"qa_status": "passed"} for spec in audit.FAMILIES.values() for sym in spec["required"]}
    family_rows = audit.family_cache_readiness_rows(status)
    rows = audit.prior_result_rows(family_rows)
    managed = {row["result_id"]: row for row in rows}["managed_futures_etf_wrapper_research_sample"]
    assert managed["classification"] == "watchlist_valid"


def test_consistency_check_passes_and_no_strategy_flags(tmp_path: Path) -> None:
    write_map(tmp_path, [symbol("SPY"), symbol("XLK")])
    write_cache(tmp_path, "SPY")
    result = audit.run_cache_readiness_audit(tmp_path, bootstrap_approved_missing=False)
    latest = Path(result["output_dir"])
    consistency = json.loads((latest / "approved_etf_cache_readiness_consistency_check.json").read_text(encoding="utf-8"))
    manifest = json.loads((latest / "approved_etf_cache_readiness_manifest.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["no_strategy_run"] is True
    assert manifest["strategy_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["real_money_recommendation"] is False
