from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_approved_expansion_symbols_cache_bootstrap as bootstrap


def synthetic_raw(symbol: str, periods: int = 520) -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-01", periods=periods)
    base = 40.0 + len(symbol)
    prices = [base + idx * 0.05 for idx in range(periods)]
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": [1000000] * periods,
            "Dividends": [0.0] * periods,
            "Stock Splits": [0.0] * periods,
        }
    )


def write_normal_cache(root: Path, symbol: str, periods: int = 520) -> None:
    bootstrap.write_normalized_cache(root, symbol, synthetic_raw(symbol, periods=periods))


def write_bad_cache(root: Path, symbol: str, periods: int = 100, duplicate: bool = False) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    if duplicate and len(dates) > 1:
        dates = dates.insert(1, dates[0])
    prices = [50.0 + idx * 0.1 for idx in range(len(dates))]
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_state(root: Path) -> None:
    write_text(root / "strategy_lab" / "APPROVED_ETF_CACHE_POLICY.md", "# policy\n")
    symbol_rows = []
    for symbol in bootstrap.APPROVED_EXPANSION_SYMBOLS:
        symbol_rows.append(
            {
                "symbol": symbol,
                "group": "expansion",
                "allowed_for_strategy": True,
                "allowed_for_benchmark": True,
                "requires_explicit_prompt": True,
                "approved_status": "approved_pending_cache_bootstrap",
                "approval_source": "approved_symbol_expansion_review",
                "cache_ready": False,
            }
        )
    for symbol in bootstrap.DEFERRED_EXPANSION_SYMBOLS:
        symbol_rows.append(
            {
                "symbol": symbol,
                "group": "deferred",
                "allowed_for_strategy": False,
                "allowed_for_benchmark": False,
                "requires_explicit_prompt": True,
                "approved_status": "not_approved",
            }
        )
    write_text(root / bootstrap.SYMBOL_MAP_PATH, yaml.safe_dump({"symbols": symbol_rows}, sort_keys=False))
    selected = {"status": "approved_pending_cache_bootstrap", "cache_ready": False, "symbols": bootstrap.APPROVED_EXPANSION_SYMBOLS}
    write_text(root / bootstrap.EXPANSION_REVIEW_DIR / "approved_symbol_expansion_selected_symbols.yaml", yaml.safe_dump(selected, sort_keys=False))
    write_text(root / bootstrap.EXPANSION_REVIEW_DIR / "approved_symbol_expansion_next_action.md", "`bootstrap_approved_expansion_symbols_cache`\n")
    (root / bootstrap.READINESS_DIR).mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "research_state" / "latest").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "strategy_lab" / "latest").mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def prepared_root(tmp_path: Path) -> Path:
    write_state(tmp_path)
    return tmp_path


def test_only_approved_pending_bootstrap_symbols_are_targeted(prepared_root: Path) -> None:
    assert bootstrap.target_symbols(prepared_root) == bootstrap.APPROVED_EXPANSION_SYMBOLS


def test_deferred_symbols_are_not_downloaded(prepared_root: Path) -> None:
    calls: list[str] = []

    def downloader(symbol: str, start: str, end: str | None, params: dict) -> pd.DataFrame:
        calls.append(symbol)
        return synthetic_raw(symbol)

    result = bootstrap.run_cache_bootstrap(prepared_root, downloader=downloader, strict_state=True)
    assert set(calls) == set(bootstrap.APPROVED_EXPANSION_SYMBOLS)
    assert not (set(calls) & set(bootstrap.DEFERRED_EXPANSION_SYMBOLS))
    assert set(result["manifest"]["symbols_forbidden_not_attempted"]) == set(bootstrap.DEFERRED_EXPANSION_SYMBOLS)


def test_existing_cache_is_detected(prepared_root: Path) -> None:
    write_normal_cache(prepared_root, "EWJ")
    calls: list[str] = []

    def downloader(symbol: str, start: str, end: str | None, params: dict) -> pd.DataFrame:
        calls.append(symbol)
        return synthetic_raw(symbol)

    result = bootstrap.run_cache_bootstrap(prepared_root, downloader=downloader, strict_state=True)
    assert result["manifest"]["symbols_already_present"] == ["EWJ"]
    assert "EWJ" not in calls


def test_missing_approved_symbols_are_reported(prepared_root: Path) -> None:
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True, allow_download=False)
    assert set(result["manifest"]["symbols_failed"]) == set(bootstrap.APPROVED_EXPANSION_SYMBOLS)
    assert result["manifest"]["data_downloaded"] is False


def test_forbidden_unapproved_symbols_are_rejected() -> None:
    with pytest.raises(ValueError, match="AAPL"):
        bootstrap.validate_requested_symbols(["EWJ", "AAPL"])


def test_qa_passes_with_enough_synthetic_history(prepared_root: Path) -> None:
    write_normal_cache(prepared_root, "EWJ", periods=bootstrap.REQUIRED_WARMUP_ROWS)
    qa = bootstrap.qa_cache_file(prepared_root, "EWJ")
    assert qa["qa_status"] == "passed"
    assert qa["enough_history_200d_sma"] is True
    assert qa["enough_history_126d_return"] is True
    assert qa["enough_history_60d_volatility"] is True


def test_duplicate_dates_fail_qa(prepared_root: Path) -> None:
    write_bad_cache(prepared_root, "EWJ", periods=bootstrap.REQUIRED_WARMUP_ROWS, duplicate=True)
    qa = bootstrap.qa_cache_file(prepared_root, "EWJ")
    assert qa["qa_status"] == "failed"
    assert qa["duplicate_dates"] > 0


def test_insufficient_warmup_fails_qa(prepared_root: Path) -> None:
    write_bad_cache(prepared_root, "EWJ", periods=100)
    qa = bootstrap.qa_cache_file(prepared_root, "EWJ")
    assert qa["qa_status"] == "failed"
    assert qa["enough_history_200d_sma"] is False


def test_symbol_map_marks_only_qa_passed_symbols_cache_ready(prepared_root: Path) -> None:
    write_normal_cache(prepared_root, "EWJ")
    result = bootstrap.run_cache_bootstrap(prepared_root, symbols=["EWJ", "EWU"], strict_state=True, allow_download=False)
    symbol_map = yaml.safe_load((prepared_root / bootstrap.SYMBOL_MAP_PATH).read_text(encoding="utf-8"))
    rows = {row["symbol"]: row for row in symbol_map["symbols"]}
    assert rows["EWJ"]["approved_status"] == "approved_cache_ready"
    assert rows["EWJ"]["cache_ready"] is True
    assert rows["EWU"]["approved_status"] == "approved_pending_cache_bootstrap"
    assert rows["EWU"]["cache_ready"] is False
    assert result["manifest"]["symbols_failed"] == ["EWU"]


def test_no_strategy_runner_is_called(prepared_root: Path) -> None:
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True, allow_download=False)
    assert result["manifest"]["strategy_discovery_run"] is False
    assert result["consistency"]["no_strategy_runner_called"] is True


def test_no_candidate_exhaustive_is_run(prepared_root: Path) -> None:
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True, allow_download=False)
    assert result["manifest"]["candidate_exhaustive_run"] is False


def test_no_paper_forward_active_flag_is_set(prepared_root: Path) -> None:
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True, allow_download=False)
    assert result["manifest"]["paper_forward_action_run"] is False
    assert result["consistency"]["no_paper_forward_active_flag_set"] is True


def test_no_real_money_recommendation_is_created(prepared_root: Path) -> None:
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True, allow_download=False)
    assert result["manifest"]["real_money_recommendation"] is False


def test_next_action_is_explicit(prepared_root: Path) -> None:
    for symbol in bootstrap.APPROVED_EXPANSION_SYMBOLS:
        write_normal_cache(prepared_root, symbol)
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True)
    assert result["manifest"]["next_action"] == "run_expanded_universe_discovery_batch"
    assert "run_expanded_universe_discovery_batch" in (Path(result["output_dir"]) / "approved_expansion_cache_next_action.md").read_text(encoding="utf-8")


def test_consistency_check_passes(prepared_root: Path) -> None:
    for symbol in bootstrap.APPROVED_EXPANSION_SYMBOLS:
        write_normal_cache(prepared_root, symbol)
    result = bootstrap.run_cache_bootstrap(prepared_root, strict_state=True)
    consistency = json.loads((Path(result["output_dir"]) / "approved_expansion_cache_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
