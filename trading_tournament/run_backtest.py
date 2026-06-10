from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from src.backtester import Backtester
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.reporting import write_report_artifacts
from src.utils import (
    config_hash,
    create_run_dir,
    get_package_versions,
    git_commit_hash,
    load_config,
    pip_freeze,
    platform_metadata,
    refresh_latest,
    validate_required_imports,
    write_json,
    write_yaml,
)
from src.validation import (
    VARIANTS,
    apply_validation_mode,
    build_rolling_window_results,
    candidate_gate_results,
    create_evidence_bundle,
    data_quality_markdown,
    data_quality_summary,
    add_variant_decisions,
    make_audit_packet,
    regime_summary,
    r_multiple_diagnostics,
    run_independent_rolling_validation,
    run_strategy_variants,
    skipped_signal_sample,
    skipped_signal_summary,
    strategy_health,
    summarize_rolling_windows,
    symbol_contribution,
    validation_mode_settings,
)


ROOT = Path(__file__).resolve().parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the trading tournament paper/demo backtest.")
    parser.add_argument(
        "--validation-mode",
        default="research_sample",
        choices=["smoke", "research_sample", "candidate_exhaustive", "nightly_full_exhaustive"],
        help="Rolling validation workflow mode. Defaults to research_sample.",
    )
    parser.add_argument("--skip-rolling", action="store_true", help="Skip independent rolling validation.")
    parser.add_argument("--reuse-rolling-cache", action="store_true", help="Reuse matching rolling result cache entries.")
    parser.add_argument("--force-rolling-recompute", action="store_true", help="Ignore rolling cache entries.")
    parser.add_argument("--max-workers", type=int, default=None, help="Maximum rolling worker processes.")
    parser.add_argument("--rolling-time-budget-minutes", type=float, default=None, help="Stop rolling after this many minutes.")
    parser.add_argument("--profile-rolling", action="store_true", help="Print rolling throughput and ETA details.")
    return parser.parse_args(argv)


def _period_end(config: dict, period_cfg: dict) -> str | None:
    return period_cfg.get("end") or config["data"].get("end_date")


def run_comparative(
    backtester: Backtester,
    config: dict,
    main_result,
) -> pd.DataFrame:
    rows = []
    slippages = {
        "standard": float(config["execution"]["standard_slippage_pct_per_side"]),
        "stress": float(config["execution"]["stress_slippage_pct_per_side"]),
    }
    for period, period_cfg in config["date_ranges"].items():
        for label, slippage in slippages.items():
            try:
                if (
                    period == "full"
                    and label == "standard"
                    and main_result.metadata.get("period_name") == "full"
                ):
                    result = main_result
                else:
                    result = backtester.run(period, str(period_cfg["start"]), _period_end(config, period_cfg), slippage)
                combined = result.strategy_metrics.loc[
                    result.strategy_metrics["name"] == "combined_tournament"
                ].iloc[0]
                rows.append(
                    {
                        "period": period,
                        "slippage_label": label,
                        "slippage_pct_per_side": slippage,
                        "final_equity": combined["final_equity"],
                        "total_return": combined["total_return"],
                        "max_drawdown": combined["max_drawdown"],
                        "max_drawdown_pct": combined["max_drawdown_pct"],
                        "number_of_trades": combined["number_of_trades"],
                        "project_stop_hit": combined["project_stop_hit"],
                        "target_300_hit": result.metadata.get("target_300_hit", False),
                        "target_300_before_any_stop": result.metadata.get("target_300_before_any_stop", False),
                        "target_400_hit": result.metadata.get("target_400_hit", False),
                        "target_400_before_any_stop": result.metadata.get("target_400_before_any_stop", False),
                        "absolute_floor_stop_hit": result.metadata.get("absolute_floor_stop_hit", False),
                        "trailing_drawdown_stop_hit": result.metadata.get("trailing_drawdown_stop_hit", False),
                        "any_project_stop_hit": result.metadata.get("any_project_stop_hit", result.metadata.get("project_stop_hit", False)),
                        "killed_strategies": ",".join(result.killed_strategies),
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "period": period,
                        "slippage_label": label,
                        "slippage_pct_per_side": slippage,
                        "final_equity": float("nan"),
                        "total_return": float("nan"),
                        "max_drawdown": float("nan"),
                        "max_drawdown_pct": float("nan"),
                        "number_of_trades": 0,
                        "project_stop_hit": False,
                        "target_300_hit": False,
                        "target_300_before_any_stop": False,
                        "target_400_hit": False,
                        "target_400_before_any_stop": False,
                        "absolute_floor_stop_hit": False,
                        "trailing_drawdown_stop_hit": False,
                        "any_project_stop_hit": False,
                        "killed_strategies": "",
                        "error": str(exc),
                    }
                )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = ROOT / "config.yaml"
    config = apply_validation_mode(load_config(config_path), args.validation_mode)
    config["project_root"] = str(ROOT)
    if args.max_workers is not None:
        config.setdefault("rolling_validation", {})["parallel_workers"] = int(args.max_workers)
    run_dir = create_run_dir(ROOT / "results")

    try:
        package_versions = validate_required_imports()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    write_yaml(run_dir / "config_used.yaml", config)
    write_json(run_dir / "package_versions.json", package_versions)
    (run_dir / "pip_freeze.txt").write_text(pip_freeze(), encoding="utf-8")

    print(f"Loading market data into {run_dir}...", flush=True)
    data_result = load_market_data(config, ROOT)
    data_result.coverage.to_csv(run_dir / "data_coverage.csv", index=False)
    prepared = prepare_indicators(data_result.data)

    full_cfg = config["date_ranges"]["full"]
    standard_slippage = float(config["execution"]["standard_slippage_pct_per_side"])
    backtester = Backtester(prepared, config)
    print("Running full-period standard-slippage tournament...", flush=True)
    main_result = backtester.run("full", str(full_cfg["start"]), _period_end(config, full_cfg), standard_slippage)

    print("Running comparative period/slippage checks...", flush=True)
    comparative = run_comparative(backtester, config, main_result)
    print("Running fixed strategy variant comparisons...", flush=True)
    mode_settings = validation_mode_settings(config)
    mode_variants = mode_settings.get("variants", [])
    variant_names = list(VARIANTS.keys()) if mode_variants == "all" else list(mode_variants)
    variants = run_strategy_variants(
        prepared,
        config,
        variant_names=variant_names,
        slippage_labels=list(mode_settings.get("slippage_labels", ["standard", "stress"])),
    )
    gate = candidate_gate_results(variants)
    gate.to_csv(run_dir / "candidate_gate_results.csv", index=False)
    print("Running independent rolling-window validation workflow...", flush=True)
    rolling_start = time.time()
    independent_rolling, sample_plan, cache_manifest, rolling_status = run_independent_rolling_validation(
        prepared,
        config,
        run_dir,
        gate,
        run_id=run_dir.name,
        skip_rolling=args.skip_rolling,
        reuse_cache=args.reuse_rolling_cache,
        force_recompute=args.force_rolling_recompute,
        max_workers=args.max_workers,
        rolling_time_budget_minutes=args.rolling_time_budget_minutes,
        profile_rolling=args.profile_rolling,
    )
    independent_summary = pd.read_csv(run_dir / "independent_rolling_window_summary.csv") if (run_dir / "independent_rolling_window_summary.csv").exists() else pd.DataFrame()
    rolling_runtime_seconds = time.time() - rolling_start
    variants = add_variant_decisions(variants, independent_summary)
    print("Building rolling-window audit diagnostics...", flush=True)
    rolling = build_rolling_window_results(main_result, config)
    rolling_summary = summarize_rolling_windows(rolling)

    skipped_summary = skipped_signal_summary(main_result.skipped_signals)
    skipped_sample = skipped_signal_sample(main_result.skipped_signals)
    health = strategy_health(main_result, variants)
    r_diag, top_by_r, top_by_pnl, bottom_by_pnl = r_multiple_diagnostics(main_result.trades, config)
    symbols = symbol_contribution(main_result.trades)
    regimes = regime_summary(main_result.trades)
    data_quality = data_quality_summary(data_result.coverage, main_result.trades)
    audit_tables = {
        "skipped_signal_summary": skipped_summary,
        "skipped_signal_sample": skipped_sample,
        "strategy_health": health,
        "r_multiple_diagnostics": r_diag,
        "top_trades_by_r": top_by_r,
        "top_trades_by_pnl": top_by_pnl,
        "bottom_trades_by_pnl": bottom_by_pnl,
        "symbol_contribution": symbols,
        "regime_summary": regimes,
        "data_quality_summary": data_quality,
    }

    all_dates = pd.concat([df["date"] for df in prepared.values()])
    full_end = str(pd.to_datetime(all_dates).max().date())
    metadata = {
        **platform_metadata(),
        "run_timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "git_commit_hash": git_commit_hash(ROOT),
        "config_hash": config_hash(config),
        "data_source": data_result.data_source,
        "yfinance_download_parameters": data_result.yfinance_params,
        "package_versions": get_package_versions(),
        "full_backtest_start": full_cfg["start"],
        "full_backtest_end": full_end,
        "effective_first_trading_date_after_warmup": main_result.metadata["effective_first_trading_date"],
        "effective_last_trading_date_after_warmup": main_result.metadata["effective_last_trading_date"],
        "slippage_assumptions_used": {
            "standard": config["execution"]["standard_slippage_pct_per_side"],
            "stress": config["execution"]["stress_slippage_pct_per_side"],
        },
        "project_stop_mode": config["project"]["project_stop"]["mode"],
        "validation_mode": config.get("validation", {}).get("mode", args.validation_mode),
        "rolling_validation": config.get("rolling_validation", {}),
        "rolling_validation_status": rolling_status,
        "rolling_runtime_seconds": rolling_runtime_seconds,
        "rolling_cache_manifest_rows": int(len(cache_manifest)),
        "main_run": main_result.metadata,
    }
    write_json(run_dir / "run_metadata.json", metadata)
    rolling.to_csv(run_dir / "rolling_window_results.csv", index=False)
    independent_rolling.to_csv(run_dir / "independent_rolling_window_results.csv", index=False)
    independent_summary.to_csv(run_dir / "independent_rolling_window_summary.csv", index=False)
    (run_dir / "data_quality_summary.md").write_text(data_quality_markdown(data_quality), encoding="utf-8")
    write_report_artifacts(
        main_result,
        config,
        metadata,
        run_dir,
        comparative,
        rolling_summary,
        variants,
        audit_tables,
    )
    make_audit_packet(
        run_dir,
        run_dir.name,
        main_result,
        config,
        metadata,
        data_result.coverage,
        comparative,
        rolling_summary,
        variants,
        audit_tables,
    )
    evidence_dir, headline, consistency = create_evidence_bundle(
        run_dir,
        ROOT / "evidence",
        run_dir.name,
        main_result,
        config,
        metadata,
        data_result.coverage,
        comparative,
        rolling_summary,
        independent_rolling,
        independent_summary,
        variants,
        audit_tables,
        rolling_status,
        gate,
    )
    refresh_latest(run_dir, ROOT / "results" / "latest")

    print(f"Backtest complete: {run_dir}", flush=True)
    print(f"Latest copy: {ROOT / 'results' / 'latest'}", flush=True)
    print(f"Evidence complete: {evidence_dir}", flush=True)
    print(f"Evidence consistency passed: {consistency['passed']}", flush=True)
    print(
        "Rolling validation: "
        f"mode={rolling_status.get('validation_mode')} "
        f"method={rolling_status.get('rolling_method')} "
        f"windows={rolling_status.get('number_of_windows')} "
        f"final={rolling_status.get('final_validation_completed')} "
        f"elapsed={rolling_runtime_seconds:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
