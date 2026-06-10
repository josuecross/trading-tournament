from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml


TIER_LABELS = {
    "credibility_tier": "Tier 1 exploratory screen",
    "final_validation": False,
    "candidate_validation": False,
    "paper_forward_ready": False,
    "real_money_recommendation": False,
}


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def prepare_evidence_dirs(run_id: str) -> tuple[Path, Path]:
    root = Path("evidence/exploratory/crypto_spot_momentum")
    run_dir = root / "runs" / run_id
    latest_dir = root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    (run_dir / "charts").mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, latest_dir


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def write_json(obj: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(text: str, path: Path) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def plot_curves(equity_curves: dict[str, pd.DataFrame], run_dir: Path) -> None:
    if not equity_curves:
        return
    plt.figure(figsize=(10, 5))
    for name, curve in equity_curves.items():
        if curve.empty:
            continue
        plt.plot(pd.to_datetime(curve["date"]), curve["equity"], label=name)
    plt.title("Tier 1 Crypto Spot Exploratory Equity Curves")
    plt.ylabel("Simulated equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(run_dir / "charts" / "equity_curve.png")
    plt.close()

    plt.figure(figsize=(10, 5))
    for name, curve in equity_curves.items():
        if curve.empty:
            continue
        equity = curve["equity"].astype(float)
        dd = equity / equity.cummax() - 1.0
        plt.plot(pd.to_datetime(curve["date"]), dd, label=name)
    plt.title("Tier 1 Crypto Spot Exploratory Drawdowns")
    plt.ylabel("Drawdown")
    plt.legend()
    plt.tight_layout()
    plt.savefig(run_dir / "charts" / "drawdown_curve.png")
    plt.close()


def build_summary(
    run_id: str,
    mode: str,
    source: str,
    network_download_occurred: bool,
    strategy_results: pd.DataFrame,
    benchmark_results: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    warnings: list[str],
    promotion_decision: str,
) -> str:
    all_results = pd.concat([strategy_results, benchmark_results], ignore_index=True)
    standard = all_results[all_results["slippage_label"] == "standard"].copy()
    stress = all_results[all_results["slippage_label"] == "stress"].copy()
    best = ""
    if not standard.empty and standard["final_equity"].notna().any():
        best = str(standard.sort_values("final_equity", ascending=False).iloc[0]["strategy"])
    stress_note = "Stress results were not part of this mode."
    if not stress.empty:
        best_stress = stress.sort_values("final_equity", ascending=False).iloc[0]
        stress_note = f"Best stress-cost final equity: {best_stress['strategy']} at {best_stress['final_equity']:.2f}."

    roll_note = "No rolling windows were produced."
    if not rolling_summary.empty:
        ninety = rolling_summary[rolling_summary["horizon"] == 90]
        if not ninety.empty:
            leader = ninety.sort_values("pct_windows_target_300_before_stop", ascending=False).iloc[0]
            roll_note = (
                f"Best sampled 90-row +300-before-stop rate: {leader['strategy']} "
                f"({leader['slippage_label']}) at {leader['pct_windows_target_300_before_stop']:.2%}."
            )

    warnings_text = "\n".join(f"- {warning}" for warning in warnings)
    return f"""# Crypto Spot Momentum Exploratory Summary

## Research-Only Statement

This is a paper/demo research artifact. It does not recommend real-money trading, does not connect to an exchange, does not place orders, and does not validate a strategy.

## Tier Label

- credibility_tier: Tier 1 exploratory screen
- final_validation: false
- candidate_validation: false
- paper_forward_ready: false
- real_money_recommendation: false

## Run Identity

- run_id: {run_id}
- validation_mode: {mode}
- data_source: {source}
- network_download_occurred: {network_download_occurred}

## Strategy Rules

The lane tests long-only daily BTC/ETH spot proxies using fixed rules: equal-weight buy and hold, BTC buy and hold, ETH buy and hold, weekly time-series momentum, weekly cross-sectional momentum, and weekly dual momentum with a cash filter. Cash earns zero.

## Cost Assumptions

Standard cost uses 0.10% per side. Stress cost uses 0.30% per side when included by the selected validation mode. These are Tier 1 exploratory assumptions, not final execution evidence.

## Standard Vs Stress Results

Best standard-cost result by final equity: {best or "not available"}.

{stress_note}

## Target-Before-Stop Results

Target-before-stop is reported in `strategy_results.csv`, `benchmark_results.csv`, `target_timing.csv`, and `rolling_window_summary.csv`. A target hit is not validation; it is only a challenge metric.

## Rolling-Window Summary

{roll_note}

These rolling results are deterministic exploratory samples unless `candidate_exhaustive` is explicitly selected. They are not final validation.

## Benchmark Comparison

Benchmark rows include `crypto_buy_hold_equal_weight`, `BTC_buy_hold`, `ETH_buy_hold`, and `cash_flat` where available. Crypto benchmarks are highly volatile and do not imply investability.

## Main Reasons Not To Trust Results As Final

{warnings_text}

## Tier 2 Review

Promotion decision: `{promotion_decision}`.

Tier 2 review, if allowed, would still be research-only and would require better data, explicit exchange/source assumptions, more complete cost modeling, and stronger validation.

## No Real-Money Recommendation

No result in this packet is a real-money recommendation.
"""


def build_false_confidence_warnings() -> str:
    return """# False Confidence Warnings

- yfinance crypto data has source and revision limitations.
- Exchange-specific prices can differ materially.
- Daily bar timestamps can differ because crypto trades 24/7.
- No bid/ask spread modeling is included.
- No order book depth is modeled.
- No exchange outages are modeled.
- No crypto delisting or survivorship handling is modeled.
- No stablecoin, custody, wallet, or exchange counterparty risk is modeled.
- No tax modeling is included.
- No live execution is included.
- No broker or exchange integration exists.
- Sampled rolling results are non-final.
- A target hit does not prove a strategy is reliable.
- No real-money recommendation is made.
"""


def build_promotion_review(
    strategy_results: pd.DataFrame,
    benchmark_results: pd.DataFrame,
    rolling_summary: pd.DataFrame,
) -> tuple[str, str]:
    combined = pd.concat([strategy_results, benchmark_results], ignore_index=True)
    standard = combined[combined["slippage_label"] == "standard"]
    btc_eth = standard[standard["strategy"].isin(["BTC_buy_hold", "ETH_buy_hold", "crypto_buy_hold_equal_weight"])]
    exploratory = standard[standard["strategy"].str.startswith("crypto_") & ~standard["strategy"].eq("crypto_buy_hold_equal_weight")]

    decision = "continue_tier1"
    if not exploratory.empty and not btc_eth.empty:
        best_exploratory = exploratory["target_300_before_stop"].astype(bool).max()
        best_benchmark = btc_eth["target_300_before_stop"].astype(bool).max()
        if best_exploratory and not best_benchmark:
            decision = "approve_tier2_research_review"

    stress_damage = "not evaluated"
    if "stress" in set(combined["slippage_label"]):
        std_final = standard.groupby("strategy")["final_equity"].max()
        stress_final = combined[combined["slippage_label"] == "stress"].groupby("strategy")["final_equity"].max()
        common = std_final.index.intersection(stress_final.index)
        if len(common):
            delta = ((stress_final[common] - std_final[common]) / std_final[common]).min()
            stress_damage = "yes" if delta < -0.1 else "not materially in this screen"

    text = f"""# Promotion Gate Review

## Decision

`{decision}`

Allowed labels are `reject`, `continue_tier1`, `approve_tier2_research_review`, and `approve_tier2_credible_prototype`.

This packet does not approve `approve_tier2_credible_prototype`.

## Questions

- Did any strategy beat BTC/ETH buy-and-hold on target-before-stop? See `strategy_results.csv`, `benchmark_results.csv`, and `rolling_window_summary.csv`.
- Did any strategy reduce drawdown materially? See `drawdown_summary.csv`.
- Did stress costs destroy the result? {stress_damage}.
- Did +$300 or +$400 occur often enough to justify further research? This is only sampled Tier 1 evidence, so it cannot be final.
- Should this remain Tier 1 only? Yes unless a later Tier 2 research review is explicitly opened.
- Should Tier 2 credible prototype review be allowed? No.

## Boundary

This review is not a trading recommendation, not a validation claim, and not paper-forward approval.
"""
    return decision, text


def build_readme_for_auditor() -> str:
    return """# README For Auditor

Upload this folder to review the Tier 1 exploratory crypto spot momentum screen.

Recommended first files:

1. `EXPLORATORY_SUMMARY.md`
2. `exploratory_manifest.json`
3. `strategy_results.csv`
4. `benchmark_results.csv`
5. `rolling_window_summary.csv`
6. `false_confidence_warnings.md`
7. `promotion_gate_review.md`

Raw crypto OHLCV is intentionally excluded from this evidence packet. Cached raw/source data, if any, belongs under `data/exploratory/crypto_spot_momentum/cache/`.

This packet is non-final, non-validated, not paper-forward ready, and not a real-money recommendation.
"""


def build_data_source_notes(source: str, warnings: list[str]) -> str:
    notes = "\n".join(f"- {warning}" for warning in warnings)
    return f"""# Data Source Notes

Primary source used: `{source}`.

{notes}

For crypto, `adj_close` is set equal to `close` when adjusted close is unavailable. This is documented as a Tier 1 exploratory convention, not a final data model.
"""


def build_cost_summary(config: dict[str, Any]) -> str:
    costs = config["costs"]
    return f"""# Cost Assumption Summary

- standard_fee_slippage_per_side: {costs['standard_fee_slippage_per_side']}
- stress_fee_slippage_per_side: {costs['stress_fee_slippage_per_side']}

{costs.get('notes', '')}

No bid/ask, order-book, outage, custody, withdrawal, exchange fee tier, or tax model is included.
"""


def build_next_questions() -> str:
    return """# Next Questions For Auditor

- Are yfinance crypto bars too source-specific for this screen to be useful?
- Do simple momentum rules improve target-before-stop versus BTC/ETH buy-and-hold?
- Are drawdowns still too large for the -$600 / -20% project risk budget?
- Do stress costs materially change the conclusion?
- Are sampled rolling windows too weak to justify Tier 2?
- What exchange-specific data source would be required before Tier 2?
- Should this lane remain Tier 1 only?
"""


def write_evidence_packet(
    run_id: str,
    config: dict[str, Any],
    mode: str,
    source: str,
    network_download_occurred: bool,
    data_coverage: pd.DataFrame,
    warnings: list[str],
    strategy_results: pd.DataFrame,
    benchmark_results: pd.DataFrame,
    rolling_results: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    equity_curves: dict[str, pd.DataFrame],
    config_path: Path,
    incomplete_reason: str | None = None,
) -> tuple[Path, Path]:
    run_dir, latest_dir = prepare_evidence_dirs(run_id)

    promotion_decision, promotion_review = build_promotion_review(strategy_results, benchmark_results, rolling_summary)
    summary = build_summary(
        run_id=run_id,
        mode=mode,
        source=source,
        network_download_occurred=network_download_occurred,
        strategy_results=strategy_results,
        benchmark_results=benchmark_results,
        rolling_summary=rolling_summary,
        warnings=warnings,
        promotion_decision=promotion_decision,
    )

    config_used = yaml.safe_dump(config, sort_keys=False)
    write_markdown(build_readme_for_auditor(), run_dir / "README_FOR_AUDITOR.md")
    write_markdown(summary, run_dir / "EXPLORATORY_SUMMARY.md")
    write_markdown(build_data_source_notes(source, warnings), run_dir / "data_source_notes.md")
    write_markdown(build_cost_summary(config), run_dir / "cost_assumption_summary.md")
    write_markdown(build_false_confidence_warnings(), run_dir / "false_confidence_warnings.md")
    write_markdown(promotion_review, run_dir / "promotion_gate_review.md")
    write_markdown(build_next_questions(), run_dir / "next_questions_for_auditor.md")
    write_markdown(config_used, run_dir / "config_used.yaml")
    write_csv(data_coverage, run_dir / "data_quality_summary.csv")
    write_csv(strategy_results, run_dir / "strategy_results.csv")
    write_csv(benchmark_results, run_dir / "benchmark_results.csv")
    sample = rolling_results.head(1000) if not rolling_results.empty else rolling_results
    write_csv(sample, run_dir / "rolling_window_results_sample.csv")
    write_csv(rolling_summary, run_dir / "rolling_window_summary.csv")
    target_cols = [
        "strategy",
        "slippage_label",
        "target_300_hit",
        "target_300_first_date",
        "target_300_before_stop",
        "target_400_hit",
        "target_400_first_date",
        "target_400_before_stop",
        "any_project_stop_hit",
        "first_project_stop_date",
    ]
    all_results = pd.concat([strategy_results, benchmark_results], ignore_index=True)
    write_csv(all_results[target_cols], run_dir / "target_timing.csv")
    drawdown_cols = ["strategy", "slippage_label", "max_drawdown_dollars", "max_drawdown_pct"]
    write_csv(all_results[drawdown_cols], run_dir / "drawdown_summary.csv")
    plot_curves(equity_curves, run_dir)

    manifest = {
        **TIER_LABELS,
        "run_id": run_id,
        "created_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation_mode": mode,
        "source": source,
        "network_download_occurred": network_download_occurred,
        "raw_ohlcv_included_in_evidence": False,
        "config_path": str(config_path),
        "promotion_decision": promotion_decision,
        "incomplete_reason": incomplete_reason or "",
        "files": sorted(p.name for p in run_dir.glob("*") if p.is_file())
        + sorted(f"charts/{p.name}" for p in (run_dir / "charts").glob("*")),
    }
    write_json(manifest, run_dir / "exploratory_manifest.json")

    zip_path = run_dir / "crypto_spot_momentum_exploratory_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.rglob("*")):
            if path == zip_path or path.is_dir():
                continue
            zf.write(path, path.relative_to(run_dir))

    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    return run_dir, latest_dir
