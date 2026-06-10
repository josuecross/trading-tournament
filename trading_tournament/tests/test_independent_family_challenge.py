from __future__ import annotations

from pathlib import Path

import pandas as pd

import run_challenge_audit as challenge_audit
from run_challenge_audit import (
    FAMILY_SPEC_PATH,
    REQUIRED_FILES,
    build_independent_family_rows,
    build_rankings,
    load_family_specs,
    write_outputs,
)


def synthetic_family_prices(periods: int = 280) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2023-01-02", periods=periods, freq="B")
    step = pd.RangeIndex(periods).to_numpy()
    prices = pd.DataFrame(
        {
            "SPY": 100.0 + step * 0.14,
            "BIL": 100.0 + step * 0.005,
            "IEF": 100.0 + step * 0.02,
            "GLD": 100.0 + step * 0.06,
        },
        index=dates,
    )
    prices.loc[dates[90:115], "SPY"] *= 0.93
    data = (
        prices.reset_index(names="date")
        .melt(id_vars="date", var_name="symbol", value_name="adj_close")
        .sort_values(["symbol", "date"])
    )
    return data, prices


def patch_heavy_family_adapters(monkeypatch) -> None:
    def fake_exact_full(run_id, spec, variant_name, labels, runtime_deadline=None):
        reason = f"synthetic test does not expose exact adapter {variant_name}"
        return ([challenge_audit.blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason)], [], False)

    def fake_exact_rolling(run_id, spec, variant_name, mode, runtime_deadline=None):
        reason = f"synthetic test does not expose exact adapter {variant_name}"
        return ([challenge_audit.blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason)], False)

    def fake_crypto(run_id, spec, mode, no_network, reuse_cache, runtime_deadline=None):
        reason = "synthetic test does not load crypto cache"
        return (
            [challenge_audit.blank_family_challenge_row(run_id, spec, "incomplete_evidence", reason)],
            [challenge_audit.blank_family_rolling_row(run_id, spec, "incomplete_evidence", reason)],
            [],
            False,
        )

    monkeypatch.setattr(challenge_audit, "build_exact_strategy_family_full_rows", fake_exact_full)
    monkeypatch.setattr(challenge_audit, "build_exact_strategy_family_rolling_rows", fake_exact_rolling)
    monkeypatch.setattr(challenge_audit, "build_crypto_family_rows", fake_crypto)


def test_independent_family_specs_exist_and_load() -> None:
    assert FAMILY_SPEC_PATH.exists()
    specs = load_family_specs(FAMILY_SPEC_PATH)
    assert specs
    required = {"family_id", "family_group", "implementation_status", "credibility_tier", "run_allowed", "role"}
    for spec in specs:
        assert required.issubset(spec), spec.get("family_id")


def test_family_rows_are_independent_accounts_not_portfolios(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, rolling, _coverage, _completed = build_independent_family_rows(
        "family_test",
        "smoke",
        include_family_challenge=True,
        include_exploratory_crypto_families=False,
    )
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    assert not challenge.empty
    family_rows = challenge[challenge["lane"].eq("independent_family_challenge")]
    assert family_rows["independent_family_account"].astype(bool).all()
    assert not family_rows["shared_capital_with_other_families"].astype(bool).any()
    assert not family_rows["portfolio_mix"].astype(bool).any()
    assert rolling


def test_blocked_family_rows_are_reported_without_performance_metrics(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, _rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, False)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    blocked = challenge[challenge["run_status"].eq("blocked_by_gate")]
    assert not blocked.empty
    assert blocked["blocked_reason"].notna().all()
    metric_cols = ["unconditional_final_equity", "stop_enforced_final_equity", "max_drawdown_dollars", "target_300_before_stop"]
    assert blocked[metric_cols].isna().all().all()


def test_crypto_family_rows_are_excluded_unless_flag_set(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, _rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, False)
    assert not any("crypto" in str(row.get("family_group", "")).lower() for row in rows)
    rows, _rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, True)
    crypto_rows = [row for row in rows if "crypto" in str(row.get("family_group", "")).lower()]
    assert crypto_rows
    assert all(row["credibility_tier"] == "tier1_exploratory" for row in crypto_rows)
    assert all(row["audit_verdict"] != "practical_candidate" for row in crypto_rows)


def test_incomplete_family_rows_use_incomplete_evidence_status(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, _rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, True)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    incomplete = challenge[challenge["run_status"].eq("incomplete_evidence")]
    assert not incomplete.empty
    assert not incomplete["audit_verdict"].eq("practical_candidate").any()


def test_ab_family_rows_are_exact_or_explicitly_incomplete_without_metrics(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, False)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    family_ids = {"family_etf_sector_momentum_A_v1", "family_etf_ab_no_cash_v1"}
    ab_rows = challenge[challenge["family_id"].isin(family_ids)]
    assert {row for row in ab_rows["family_id"].dropna().unique()} == family_ids
    for _, row in ab_rows.iterrows():
        assert row["run_status"] in {"completed", "incomplete_evidence"}
        if row["run_status"] == "incomplete_evidence":
            assert pd.isna(row["unconditional_final_equity"])
            assert pd.isna(row["stop_enforced_final_equity"])
            assert pd.isna(row["target_300_before_stop"])
            assert "summary metrics" in str(row["notes"])
            assert rolling_df[rolling_df["family_id"].eq(row["family_id"])].empty


def test_family_challenge_does_not_include_portfolio_mix_rows(monkeypatch, tmp_path: Path) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, rolling, coverage, completed = build_independent_family_rows("family_test", "smoke", True, False)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    rankings = build_rankings(challenge, rolling_df)
    assert {"family_id", "family_group", "family_comparison_score"}.issubset(rankings.columns)
    assert not challenge["lane"].eq("diversified_portfolio_challenge").any()
    assert not rankings[rankings["run_status"].eq("blocked_by_gate")]["audit_verdict"].eq("practical_candidate").any()
    assumptions = challenge_audit.build_assumptions(
        "smoke",
        include_etf=True,
        include_crypto=False,
        include_leverage=False,
        include_benchmarks=True,
        finalists=set(),
        final_validation_completed=completed,
        include_family_challenge=True,
    )
    write_outputs("family_test", challenge, rolling_df, rankings, pd.DataFrame(coverage), assumptions, tmp_path / "challenge_runs")
    latest = tmp_path / "challenge_runs" / "latest"
    assert sorted(path.name for path in latest.iterdir() if path.is_file()) == sorted(REQUIRED_FILES)
    assert len([path for path in latest.iterdir() if path.is_file()]) == 10
    summary_text = (latest / "challenge_summary.md").read_text()
    assert "Independent Family Challenge" in summary_text
    assert "ETF Strategy Family Stream Completion" in summary_text
    assert "Run-level finality can be false while row-level exact evidence exists" in summary_text
    assert "A/B exact family comparison remains unresolved" in summary_text
    assert "ETF benchmark rolling rows are unavailable" not in summary_text
    assert "SPY_buy_hold row unavailable" not in summary_text
    assert "No A/A-B family row was populated from summary metrics" in summary_text
    assert not any("ohlcv" in path.name.lower() or "raw" in path.name.lower() for path in latest.iterdir())


def test_rankings_include_family_evidence_finality_fields(monkeypatch) -> None:
    data, prices = synthetic_family_prices()
    monkeypatch.setattr(challenge_audit, "family_price_cache", lambda date_index=None: (data, prices))
    patch_heavy_family_adapters(monkeypatch)
    rows, rolling, _coverage, _completed = build_independent_family_rows("family_test", "smoke", True, False)
    challenge = pd.DataFrame(rows).reindex(columns=challenge_audit.CHALLENGE_COLUMNS)
    rolling_df = pd.DataFrame(rolling).reindex(columns=challenge_audit.ROLLING_COLUMNS)
    rankings = build_rankings(challenge, rolling_df)
    assert {"final_validation_completed", "sampled_results_are_final"}.issubset(rankings.columns)
