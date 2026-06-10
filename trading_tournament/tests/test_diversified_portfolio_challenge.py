from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

import run_challenge_audit as challenge_audit
from run_challenge_audit import (
    PORTFOLIO_SPEC_PATH,
    REQUIRED_FILES,
    build_rankings,
    build_diversified_portfolio_rows,
    load_portfolio_specs,
    write_outputs,
)


def synthetic_etf_prices(periods: int = 260) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2023-01-02", periods=periods, freq="B")
    spy = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.12, index=dates)
    spy.iloc[min(80, periods - 1): min(110, periods)] *= 0.94
    bil = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.005, index=dates)
    ief = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.02, index=dates)
    gld = pd.Series(100.0 + pd.RangeIndex(periods).to_numpy() * 0.03, index=dates)
    prices = pd.DataFrame({"SPY": spy, "BIL": bil, "IEF": ief, "GLD": gld}, index=dates)
    data = (
        prices.reset_index(names="date")
        .melt(id_vars="date", var_name="symbol", value_name="adj_close")
        .sort_values(["symbol", "date"])
    )
    return data, prices


def test_diversified_portfolio_specs_exist_and_load() -> None:
    assert PORTFOLIO_SPEC_PATH.exists()
    specs = load_portfolio_specs(PORTFOLIO_SPEC_PATH)
    assert specs
    assert {spec["id"] for spec in specs} >= {
        "portfolio_spy200d_100_v1",
        "portfolio_spy200d_80_bil_20_v1",
        "portfolio_spy200d_60_ief_20_gld_10_bil_10_v1",
    }


def test_all_portfolio_weights_sum_to_one_and_non_negative() -> None:
    specs = load_portfolio_specs(PORTFOLIO_SPEC_PATH)
    for spec in specs:
        weights = [float(value) for value in spec["sleeves"].values()]
        assert abs(sum(weights) - 1.0) < 1e-9
        assert all(weight >= 0 for weight in weights)


def test_etf_only_portfolios_contain_allowed_etf_sleeves() -> None:
    allowed = {"SPY_200d_trend_model", "BIL_cash_proxy", "IEF_buy_hold", "GLD_buy_hold", "current_no_cash_proxy_alpha_AB"}
    specs = [spec for spec in load_portfolio_specs(PORTFOLIO_SPEC_PATH) if not challenge_audit.portfolio_is_crypto(spec)]
    for spec in specs:
        assert set(spec["sleeves"]).issubset(allowed)


def test_crypto_portfolios_are_tier1_exploratory() -> None:
    specs = [spec for spec in load_portfolio_specs(PORTFOLIO_SPEC_PATH) if challenge_audit.portfolio_is_crypto(spec)]
    assert specs
    for spec in specs:
        assert spec["tier"] == "tier1_exploratory"


def test_monthly_portfolio_rebalance_logic_on_synthetic_data() -> None:
    _data, prices = synthetic_etf_prices(80)
    sleeve_returns = pd.DataFrame(
        {
            "SPY_200d_trend_model": prices["SPY"].pct_change(fill_method=None).fillna(0.0),
            "BIL_cash_proxy": prices["BIL"].pct_change(fill_method=None).fillna(0.0),
        },
        index=prices.index,
    )
    targets, unavailable, _notes = challenge_audit.build_monthly_portfolio_targets(
        prices.index,
        {"SPY_200d_trend_model": 0.8, "BIL_cash_proxy": 0.2},
        sleeve_returns,
    )
    assert unavailable == []
    monthly_changes = targets.diff().abs().sum(axis=1).gt(0).sum()
    assert monthly_changes <= 4
    assert (targets.sum(axis=1) <= 1.0 + 1e-12).all()


def test_unavailable_sleeve_allocation_is_flagged() -> None:
    _data, prices = synthetic_etf_prices(60)
    sleeve_returns = pd.DataFrame({"BIL_cash_proxy": prices["BIL"].pct_change(fill_method=None).fillna(0.0)}, index=prices.index)
    targets, unavailable, notes = challenge_audit.build_monthly_portfolio_targets(
        prices.index,
        {"missing_sleeve": 0.5, "BIL_cash_proxy": 0.5},
        sleeve_returns,
    )
    assert unavailable == ["missing_sleeve"]
    assert "flagged" in notes
    assert (targets["BIL_cash_proxy"] >= 0.5).all()


def test_portfolio_rows_are_opt_in_and_have_required_columns(monkeypatch) -> None:
    data, prices = synthetic_etf_prices(260)
    monkeypatch.setattr(challenge_audit, "load_portfolio_price_cache", lambda date_index=None: (data, prices))
    monkeypatch.setattr(
        challenge_audit,
        "exact_ab_sleeve_returns",
        lambda date_index, label: (pd.Series(0.0, index=date_index), "synthetic_ab"),
    )
    rows, rolling, _coverage, completed = build_diversified_portfolio_rows(
        "test_run",
        "smoke",
        include_diversified_portfolios=True,
        include_exploratory_crypto_portfolios=False,
    )
    assert completed is True
    assert rows
    assert rolling
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    assert {"portfolio_id", "portfolio_role", "portfolio_weights", "max_single_sleeve_weight"}.issubset(challenge.columns)
    assert {"portfolio_id", "average_portfolio_turnover", "unavailable_window_count"}.issubset(rolling_df.columns)
    assert not challenge["portfolio_id"].str.contains("crypto", case=False, na=False).any()
    assert (challenge["leverage_multiplier"].astype(float) == 1.0).all()


def test_crypto_portfolios_excluded_unless_flag_set(monkeypatch) -> None:
    data, prices = synthetic_etf_prices(260)
    monkeypatch.setattr(challenge_audit, "load_portfolio_price_cache", lambda date_index=None: (data, prices))
    monkeypatch.setattr(
        challenge_audit,
        "exact_ab_sleeve_returns",
        lambda date_index, label: (pd.Series(0.0, index=date_index), "synthetic_ab"),
    )
    rows, _rolling, _coverage, _completed = build_diversified_portfolio_rows("test_run", "smoke", True, False)
    assert not any("crypto" in row["strategy"] for row in rows)
    rows, _rolling, _coverage, _completed = build_diversified_portfolio_rows("test_run", "smoke", True, True)
    crypto_rows = [row for row in rows if "crypto" in row["strategy"]]
    assert crypto_rows
    assert all(row["credibility_tier"] == "tier1_exploratory" for row in crypto_rows)
    assert all(row["audit_verdict"] != "practical_candidate" for row in crypto_rows)


def test_portfolio_rankings_and_compact_output_contract(monkeypatch, tmp_path: Path) -> None:
    data, prices = synthetic_etf_prices(260)
    monkeypatch.setattr(challenge_audit, "load_portfolio_price_cache", lambda date_index=None: (data, prices))
    monkeypatch.setattr(
        challenge_audit,
        "exact_ab_sleeve_returns",
        lambda date_index, label: (pd.Series(0.0, index=date_index), "synthetic_ab"),
    )
    rows, rolling, coverage, _completed = build_diversified_portfolio_rows("test_run", "smoke", True, False)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    rankings = build_rankings(challenge, rolling_df)
    assert {"portfolio_id", "diversification_score", "cash_weight", "bond_weight", "gold_weight", "crypto_weight"}.issubset(rankings.columns)
    assert not rankings["audit_verdict"].eq("practical_candidate").any()
    assumptions = challenge_audit.build_assumptions(
        "smoke",
        True,
        False,
        False,
        True,
        {"SPY_200d_trend_model"},
        False,
        include_diversified_portfolios=True,
    )
    write_outputs("test_run", challenge, rolling_df, rankings, pd.DataFrame(coverage), assumptions, tmp_path / "challenge_runs")
    latest = tmp_path / "challenge_runs" / "latest"
    assert sorted(path.name for path in latest.iterdir() if path.is_file()) == sorted(REQUIRED_FILES)
    assert len([path for path in latest.iterdir() if path.is_file()]) == 10
    assert not any("ohlcv" in path.name.lower() or "raw" in path.name.lower() for path in latest.iterdir())
    assert "Diversified Portfolio Challenge" in (latest / "challenge_summary.md").read_text()
