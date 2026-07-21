from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.utils import config_hash, git_commit_hash, load_config, sha256_file


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "cppi_engine_feasibility_v1"
OVERLAY_ID = "OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1"
SOURCE_LABEL = "engine_capability_adjustment;source_rule_completion;research_only_feasibility"

TEST_COMMANDS = [
    [sys.executable, "-m", "pytest", "tests/test_cppi_engine_capability.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
    [
        sys.executable,
        "-m",
        "py_compile",
        "src/overlays.py",
        "src/portfolio.py",
        "src/backtester.py",
        "tests/test_cppi_engine_capability.py",
    ],
]

STRATEGY_FAMILIES = {
    "A_ETF_sector_momentum": "sector_momentum_core",
    "B_ETF_trend_following": "etf_trend_following",
    "C_swing_trend_pullback": "daily_swing_pullback_reversal",
    "D_mean_reversion": "daily_mean_reversion",
    "E_breakout_vcb": "breakout_volatility_contraction",
    "N1_dual_momentum_taa": "cross_asset_dual_momentum_taa",
    "N2_absolute_trend_taa": "absolute_trend_taa",
    "N3_dual_momentum_vol_scaled": "cross_asset_dual_momentum_vol_scaled_taa",
    "N4_inverse_vol_defensive_allocation": "inverse_vol_defensive_allocation",
    "F_opening_range_breakout": "opening_range_breakout_shadow",
    "G_event_driven_momentum": "event_driven_momentum_shadow",
}

INTENT_KIND = {
    "A_ETF_sector_momentum": "risk_amount_weekly_rebalance",
    "B_ETF_trend_following": "risk_amount_daily_signal",
    "C_swing_trend_pullback": "risk_amount_daily_signal",
    "D_mean_reversion": "risk_amount_daily_signal",
    "E_breakout_vcb": "risk_amount_daily_signal",
    "N1_dual_momentum_taa": "monthly_target_weight",
    "N2_absolute_trend_taa": "monthly_target_weight",
    "N3_dual_momentum_vol_scaled": "monthly_target_weight",
    "N4_inverse_vol_defensive_allocation": "monthly_target_weight",
    "F_opening_range_breakout": "shadow_only_no_implemented_intent",
    "G_event_driven_momentum": "shadow_only_no_implemented_intent",
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pipe_join(values: list[str]) -> str:
    return "|".join(sorted(set(values)))


def cache_ready(symbols: list[str]) -> tuple[bool, str]:
    statuses: list[str] = []
    ready = True
    for symbol in sorted(set(symbols)):
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        ok = path.exists() and path.stat().st_size > 0
        statuses.append(f"{symbol}:{'present' if ok else 'missing'}")
        ready = ready and ok
    return ready, "; ".join(statuses)


def strategy_symbols(strategy_id: str, cfg: dict[str, Any]) -> list[str]:
    strategies = cfg.get("strategies", {})
    item = strategies.get(strategy_id, {})
    symbols: list[str] = []
    symbols.extend(item.get("risk_assets", []) or [])
    symbols.extend(item.get("defensive_assets", []) or [])
    symbols.extend(item.get("risk_off_allowed_assets", []) or [])
    symbols.extend(item.get("assets", []) or [])
    if strategy_id.startswith(("A_", "B_", "C_", "D_", "E_")):
        symbols.extend(cfg.get("universe", {}).get("symbols", []) or [])
    if strategy_id in {"N1_dual_momentum_taa", "N2_absolute_trend_taa", "N3_dual_momentum_vol_scaled", "N4_inverse_vol_defensive_allocation"}:
        symbols.extend(["SPY", "BIL", "SHY"])
    return sorted(set(symbols))


def mapping_row(strategy_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    item = cfg.get("strategies", {}).get(strategy_id, {})
    if strategy_id in {
        "A_ETF_sector_momentum",
        "B_ETF_trend_following",
        "C_swing_trend_pullback",
        "D_mean_reversion",
        "E_breakout_vcb",
    }:
        return {
            "strategy_id": strategy_id,
            "intent_kind": INTENT_KIND[strategy_id],
            "risky_assets": "",
            "safe_assets": "",
            "cash_proxy_assets": "BIL",
            "mapping_source": "not_applicable_risk_amount_intent",
            "mapping_status": "unsupported_intent_unit",
            "role_overlap_assets": "",
            "notes": "CPPI source gate supports target_weight intents only; these strategies size from requested risk amount and stops.",
        }
    if strategy_id == "N1_dual_momentum_taa":
        risky = item.get("risk_assets", []) or []
        safe = item.get("defensive_assets", []) or []
        overlap = sorted(set(risky) & set(safe))
        return {
            "strategy_id": strategy_id,
            "intent_kind": INTENT_KIND[strategy_id],
            "risky_assets": pipe_join(risky),
            "safe_assets": pipe_join(safe),
            "cash_proxy_assets": "BIL|SHY",
            "mapping_source": "config.risk_assets/config.defensive_assets",
            "mapping_status": "blocked_ambiguous_overlap",
            "role_overlap_assets": pipe_join(overlap),
            "notes": "IEF is both a risk asset and defensive asset; CPPI role mapping must be frozen before a source-backed run.",
        }
    if strategy_id == "N2_absolute_trend_taa":
        assets = [symbol for symbol in (item.get("assets", []) or []) if symbol != "BIL"]
        safe = item.get("defensive_assets", []) or []
        overlap = sorted(set(assets) & set(safe))
        return {
            "strategy_id": strategy_id,
            "intent_kind": INTENT_KIND[strategy_id],
            "risky_assets": pipe_join(assets),
            "safe_assets": pipe_join(safe),
            "cash_proxy_assets": "BIL|SHY",
            "mapping_source": "config.assets/config.defensive_assets",
            "mapping_status": "blocked_ambiguous_overlap",
            "role_overlap_assets": pipe_join(overlap),
            "notes": "IEF, TLT, and GLD can appear in both risk-on and defensive allocations; CPPI cannot infer role without methodology metadata.",
        }
    if strategy_id == "N3_dual_momentum_vol_scaled":
        risky = item.get("risk_assets", []) or []
        safe = item.get("defensive_assets", []) or []
        overlap = sorted(set(risky) & set(safe))
        return {
            "strategy_id": strategy_id,
            "intent_kind": INTENT_KIND[strategy_id],
            "risky_assets": pipe_join(risky),
            "safe_assets": pipe_join(safe),
            "cash_proxy_assets": "BIL|SHY",
            "mapping_source": "config.risk_assets/config.defensive_assets",
            "mapping_status": "blocked_ambiguous_overlap",
            "role_overlap_assets": pipe_join(overlap),
            "notes": "IEF is both a risk asset and defensive asset; volatility scaling does not resolve the CPPI role.",
        }
    if strategy_id == "N4_inverse_vol_defensive_allocation":
        risky = item.get("assets", []) or []
        return {
            "strategy_id": strategy_id,
            "intent_kind": INTENT_KIND[strategy_id],
            "risky_assets": pipe_join(risky),
            "safe_assets": "BIL",
            "cash_proxy_assets": "BIL",
            "mapping_source": "config.assets plus strategy-code BIL remainder/fallback",
            "mapping_status": "explicit_without_base_signal_change",
            "role_overlap_assets": "",
            "notes": "The base strategy lists risky allocation assets and emits BIL only as residual/fallback cash proxy.",
        }
    return {
        "strategy_id": strategy_id,
        "intent_kind": INTENT_KIND[strategy_id],
        "risky_assets": "",
        "safe_assets": "",
        "cash_proxy_assets": "",
        "mapping_source": "shadow_only",
        "mapping_status": "base_rules_not_implemented",
        "role_overlap_assets": "",
        "notes": "Shadow-only strategy lacks implemented source rules in the backtest engine.",
    }


def eligibility_rows(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    strategy_ids = list(cfg.get("strategy_order", [])) + ["F_opening_range_breakout", "G_event_driven_momentum"]
    for strategy_id in strategy_ids:
        mapping = mapping_row(strategy_id, cfg)
        mappings.append(mapping)
        symbols = strategy_symbols(strategy_id, cfg)
        ready, readiness_detail = cache_ready(symbols)
        target_weight = INTENT_KIND[strategy_id] == "monthly_target_weight"
        base_reproducible = strategy_id not in {"F_opening_range_breakout", "G_event_driven_momentum"}
        mapping_ok = mapping["mapping_status"] == "explicit_without_base_signal_change"
        eligible = bool(target_weight and mapping_ok and ready and base_reproducible)
        reasons: list[str] = []
        if not target_weight:
            reasons.append("UNSUPPORTED_INTENT_UNIT")
        if target_weight and not mapping_ok:
            reasons.append("AMBIGUOUS_OR_MISSING_RISKY_SAFE_MAPPING")
        if not ready:
            reasons.append("MISSING_CACHE_DATA")
        if not base_reproducible:
            reasons.append("BASE_RULES_NOT_IMPLEMENTED")
        rows.append(
            {
                "strategy_id": strategy_id,
                "family": STRATEGY_FAMILIES[strategy_id],
                "intent_kind": INTENT_KIND[strategy_id],
                "target_weight_compatible": str(target_weight).lower(),
                "explicit_risky_safe_mapping": str(mapping_ok).lower(),
                "data_readiness": "ready" if ready else "missing_cache",
                "data_readiness_detail": readiness_detail,
                "base_reproducibility": "implemented" if base_reproducible else "shadow_only_not_implemented",
                "cppi_eligibility": "eligible" if eligible else "ineligible",
                "ineligibility_reason": "|".join(reasons),
            }
        )
    return rows, mappings


def synthetic_test_cases() -> list[dict[str, str]]:
    return [
        {"case_id": "CPPI-001", "mechanic": "5-year episode initialization", "coverage": "test_initial_five_year_floor_and_risky_exposure_are_source_exact", "expected": "episode_start and maturity are fixed from calendar"},
        {"case_id": "CPPI-002", "mechanic": "guarantee present-value floor", "coverage": "test_initial_five_year_floor_and_risky_exposure_are_source_exact", "expected": "floor = guarantee * exp(-r * years_remaining)"},
        {"case_id": "CPPI-003", "mechanic": "floor grows to guarantee at maturity", "coverage": "test_floor_grows_to_guarantee_at_maturity", "expected": "floor equals starting NAV at maturity for 100 percent guarantee"},
        {"case_id": "CPPI-004", "mechanic": "cushion is NAV minus floor, floored at zero", "coverage": "test_risky_exposure_rises_with_cushion_and_falls_when_cushion_contracts", "expected": "lower NAV lowers cushion"},
        {"case_id": "CPPI-005", "mechanic": "risky exposure uses multiplier M=3", "coverage": "test_initial_five_year_floor_and_risky_exposure_are_source_exact", "expected": "risky fraction approximately 66.36 percent at 5 percent, 5-year, 100 percent guarantee"},
        {"case_id": "CPPI-006", "mechanic": "risky exposure capped at unlevered 100 percent", "coverage": "test_managed_targets_never_exceed_base_or_one_hundred_percent", "expected": "managed target never exceeds 1.0"},
        {"case_id": "CPPI-007", "mechanic": "risky exposure rises with cushion", "coverage": "test_risky_exposure_rises_with_cushion_and_falls_when_cushion_contracts", "expected": "higher NAV produces higher risky fraction"},
        {"case_id": "CPPI-008", "mechanic": "risky exposure falls with cushion contraction", "coverage": "test_risky_exposure_rises_with_cushion_and_falls_when_cushion_contracts", "expected": "lower NAV produces lower risky fraction"},
        {"case_id": "CPPI-009", "mechanic": "managed risky target cannot exceed base target", "coverage": "test_managed_targets_never_exceed_base_or_one_hundred_percent", "expected": "per-signal managed target <= base target"},
        {"case_id": "CPPI-010", "mechanic": "safe asset target redirects to synthetic safe account", "coverage": "test_managed_targets_never_exceed_base_or_one_hundred_percent", "expected": "BIL order suppressed and recorded as synthetic safe redirect"},
        {"case_id": "CPPI-011", "mechanic": "safe account accrues at fixed 5 percent", "coverage": "test_safe_account_accrues_exactly_and_reconciles_with_nav", "expected": "continuous compounding matches formula"},
        {"case_id": "CPPI-012", "mechanic": "safe account included in NAV", "coverage": "test_safe_account_accrues_exactly_and_reconciles_with_nav", "expected": "mark_to_market includes synthetic safe ledger"},
        {"case_id": "CPPI-013", "mechanic": "month-end calculation does not execute at same close", "coverage": "test_month_end_calculation_is_submitted_for_next_open_execution", "expected": "event flag same_close_execution=false"},
        {"case_id": "CPPI-014", "mechanic": "prior safe sleeve released before next-open order fills", "coverage": "test_month_end_calculation_is_submitted_for_next_open_execution", "expected": "safe ledger transferred to broker cash before fills"},
        {"case_id": "CPPI-015", "mechanic": "residual broker cash can be swept to synthetic safe after fills", "coverage": "test_residual_broker_cash_sweeps_to_synthetic_safe_after_next_open_fills", "expected": "non-orderable broker_cash_to_synthetic_safe transfer"},
        {"case_id": "CPPI-016", "mechanic": "gap below floor records shortfall", "coverage": "test_gap_below_floor_records_shortfall_without_repairing_capital", "expected": "cppi_gap_breach event emitted"},
        {"case_id": "CPPI-017", "mechanic": "gap shortfall is retained and capital is not repaired", "coverage": "test_gap_below_floor_records_shortfall_without_repairing_capital", "expected": "equity remains below floor by shortfall amount"},
        {"case_id": "CPPI-018", "mechanic": "cash lock is permanent before maturity", "coverage": "test_cash_lock_is_permanent_and_blocks_risky_reentry_before_maturity", "expected": "risky re-entry suppressed after floor breach"},
        {"case_id": "CPPI-019", "mechanic": "fail closed for missing NAV, unsupported intent, and ambiguous mapping", "coverage": "test_fail_closed_for_missing_nav_unsupported_intent_and_ambiguous_mapping", "expected": "OverlayDataError"},
        {"case_id": "CPPI-020", "mechanic": "identity overlay equivalence preserved", "coverage": "test_base_plus_identity_equivalence_remains_unchanged", "expected": "base and identity equity/trades match exactly"},
        {"case_id": "CPPI-021", "mechanic": "no broker/live/paper module dependency", "coverage": "test_no_paper_demo_live_broker_modules_are_imported_by_cppi_overlay", "expected": "no Alpaca/broker/live import required"},
    ]


def run_test_commands() -> tuple[str, bool, list[dict[str, Any]]]:
    chunks: list[str] = []
    rows: list[dict[str, Any]] = []
    all_passed = True
    for command in TEST_COMMANDS:
        printable = " ".join(command)
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        passed = result.returncode == 0
        all_passed = all_passed and passed
        rows.append({"command": printable, "returncode": result.returncode, "passed": passed})
        chunks.append(f"$ {printable}\nreturncode={result.returncode}\n{result.stdout}{result.stderr}".rstrip())
    return "\n\n".join(chunks) + "\n", all_passed, rows


def write_architecture_map(path: Path) -> None:
    path.write_text(
        """# CPPI Engine Feasibility Architecture Map

Verdict: MINIMAL_PATCH_REQUIRED for OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1.

## Existing surfaces inspected

1. Cash and NAV accounting: `src/portfolio.py` owns broker cash, open positions, realized PnL, and mark-to-market NAV. Before this gate, NAV was broker cash plus position market value only. The patch adds one synthetic, non-orderable safe ledger and keeps mark-to-market as the single NAV source.
2. Cash accrual: ordinary broker cash does not accrue return by default. The CPPI safe account accrues only when the CPPI overlay calls the explicit synthetic ledger accrual method.
3. Safe asset handling: no pre-existing independent safe-account abstraction was present. The patch adds `synthetic_safe_account_value`, accrual timestamp, cash-to-safe transfer, and safe-to-cash withdrawal methods on `Portfolio`.
4. Overlay timing: base strategies emit signals after the daily close. `TradeManagementOverlay.on_signal_batch` transforms those intents into pending orders, and the backtester fills pending exits/entries at the next open. The patch adds `on_before_order_fills` so CPPI can release the synthetic safe sleeve before next-open execution.
5. Intent contract: CPPI supports `target_weight` only. The monthly N1-N4 strategies emit `EntrySignal.metadata["target_weight"]`; risk-amount A-E signals remain ineligible for this source gate.
6. Strategy role mapping: risky/safe asset role is supplied to `CPPIOverlay(risky_assets=..., safe_assets=...)`, outside base signal generation. The overlay fails closed on missing or overlapping role metadata.
7. Episode state: CPPI is implemented as overlay state over the existing portfolio, not as a separate accounting engine. Episode state includes start, maturity, guarantee, floor, cushion, risky fraction, cash lock, breach timestamp, and retained shortfall.
8. Identity hashing: existing complete-state identity controls remain on the overlay path. The new CPPI unit test confirms base plus `IdentityOverlay` still reproduces base trades and equity exactly after the safe-account patch.

## CPPI lifecycle

- Episode start: first bound calendar date unless an explicit start is supplied.
- Maturity: episode start plus 5 years.
- Guarantee: 100 percent of starting equity.
- Floor: present value of the guarantee at the fixed 5 percent rate.
- Cushion: max(NAV - floor, 0).
- Risky allocation: min(3 * cushion, NAV), divided by NAV; leverage is disallowed.
- Rebalance timing: CPPI transforms month-end target-weight intents after close for next-open execution.
- Safe sleeve: safe-asset orders are suppressed and represented by synthetic safe ledger transfers, not broker orders.
- Gap breach: if NAV falls below floor, shortfall is recorded and retained; no capital repair is modeled.
- Cash lock: after a floor breach, risky entries remain suppressed before maturity.

## Capability boundary

This package does not run a performance experiment, tune parameters, promote a strategy, activate paper/demo/live execution, or import broker modules. It is limited to engine capability and source-rule feasibility.
""",
        encoding="utf-8",
    )


def write_source_of_truth_update(path: Path, first_eligible: str) -> None:
    path.write_text(
        f"""# Source Of Truth Update

Source id: `{OVERLAY_ID}`

Status: `MINIMAL_PATCH_REQUIRED_IMPLEMENTED_FOR_ENGINE_CAPABILITY`

Research lane label: `{SOURCE_LABEL}`

Canonical fixed parameters:

- Multiplier: 3
- Horizon: 5 years
- Risk-free/safe-account rate: 5 percent annual continuous compounding
- Guarantee: 100 percent of initial episode NAV
- Rebalance cadence: monthly target transformation, next-open execution
- Leverage: disabled
- Floor breach behavior: retain shortfall, no capital repair
- Cash lock: enabled after floor breach

Engine source of truth:

- Portfolio NAV includes broker cash, open positions, and `synthetic_safe_account_value`.
- The synthetic safe account is non-orderable and has no broker/live dependency.
- CPPI is an overlay over the existing backtest engine and portfolio ledger, not a parallel accounting engine.
- Strategy eligibility is target-weight-only and requires explicit risky/safe role metadata.

Deterministic future selection:

- First engine-compatible strategy by declared inventory rules: `{first_eligible}`.
- Primary monthly ETF rotation strategies with overlapping risk/defensive roles remain blocked until metadata explicitly freezes those roles.
- This is not a performance recommendation and does not authorize validation, paper trading, demo trading, live trading, promotion, or parameter tuning.
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "config.yaml")
    strategy_rows, mapping_rows = eligibility_rows(cfg)
    eligible = [row["strategy_id"] for row in strategy_rows if row["cppi_eligibility"] == "eligible"]
    first_eligible = sorted(eligible)[0] if eligible else "NONE"

    test_text, tests_passed, test_command_rows = run_test_commands()
    (OUT_DIR / "test_results.txt").write_text(test_text, encoding="utf-8")

    write_csv(
        OUT_DIR / "strategy_eligibility.csv",
        strategy_rows,
        [
            "strategy_id",
            "family",
            "intent_kind",
            "target_weight_compatible",
            "explicit_risky_safe_mapping",
            "data_readiness",
            "data_readiness_detail",
            "base_reproducibility",
            "cppi_eligibility",
            "ineligibility_reason",
        ],
    )
    write_csv(
        OUT_DIR / "intent_mapping.csv",
        mapping_rows,
        [
            "strategy_id",
            "intent_kind",
            "risky_assets",
            "safe_assets",
            "cash_proxy_assets",
            "mapping_source",
            "mapping_status",
            "role_overlap_assets",
            "notes",
        ],
    )
    write_csv(
        OUT_DIR / "synthetic_test_cases.csv",
        synthetic_test_cases(),
        ["case_id", "mechanic", "coverage", "expected"],
    )
    write_architecture_map(OUT_DIR / "architecture_map.md")
    write_source_of_truth_update(OUT_DIR / "source_of_truth_update.md", first_eligible)

    invariant_checks = {
        "overlay_id": OVERLAY_ID,
        "tests_passed": tests_passed,
        "checks": {
            "bounded_engine_capability_only": True,
            "no_comparative_performance_backtest_run": True,
            "no_parameter_search_or_tuning": True,
            "no_paper_demo_live_activation": True,
            "no_parallel_accounting_engine": True,
            "single_portfolio_nav_source": True,
            "safe_account_is_synthetic_non_orderable": True,
            "safe_account_included_in_nav": tests_passed,
            "safe_account_continuous_compounding_5pct": tests_passed,
            "cppi_floor_formula_present_value_of_guarantee": tests_passed,
            "cppi_multiplier_m3": tests_passed,
            "cppi_horizon_5_years": tests_passed,
            "cppi_guarantee_100pct_initial_nav": tests_passed,
            "cppi_unlevered_cap": tests_passed,
            "base_exposure_never_increased": tests_passed,
            "month_end_next_open_timing": tests_passed,
            "gap_shortfall_retained_no_capital_repair": tests_passed,
            "cash_lock_after_floor_breach": tests_passed,
            "fail_closed_missing_nav_unsupported_intent_ambiguous_mapping": tests_passed,
            "identity_equivalence_preserved": tests_passed,
            "no_broker_live_paper_dependency": tests_passed,
        },
        "test_commands": test_command_rows,
    }
    write_json(OUT_DIR / "invariant_checks.json", invariant_checks)

    decision = {
        "overlay_id": OVERLAY_ID,
        "decision": "MINIMAL_PATCH",
        "verdict_label": "MINIMAL_PATCH_REQUIRED",
        "implemented": True,
        "why_not_ready_before_patch": "The engine had no synthetic non-orderable safe account that accrued at the source-specified fixed return and reconciled into NAV.",
        "why_not_incompatible": "The existing overlay hook model and target_weight strategies can support CPPI as an overlay once the safe ledger and before-fill hook exist.",
        "why_not_strategy_metadata_required_as_global_verdict": "Engine capability is now present, but some strategies remain individually ineligible until risky/safe role metadata is disambiguated.",
        "safe_account_model": "Portfolio-owned synthetic ledger; no broker order, no parallel engine, included in mark_to_market NAV.",
        "fixed_source_parameters": {
            "multiplier": 3.0,
            "horizon_years": 5.0,
            "risk_free_rate": 0.05,
            "guarantee_fraction": 1.0,
            "rebalance_frequency": "month_end",
            "execution_timing": "next_open",
            "max_risky_exposure": 1.0,
            "leverage_allowed": False,
            "cash_lock_after_floor_breach": True,
        },
        "deterministic_future_selection_if_enabled": {
            "selection_rule": "eligible strategies only, then alphabetical by strategy_id; no performance judgment",
            "first_eligible_strategy_id": first_eligible,
            "primary_rotation_metadata_blocker": "N1/N2/N3 have overlapping risky/defensive roles and require explicit role freeze before source-backed CPPI runs.",
        },
        "non_goals_confirmed": [
            "no_performance_backtest",
            "no_validation",
            "no_parameter_study",
            "no_promotion",
            "no_paper_demo_live_activation",
            "no_broker_imports",
        ],
    }
    write_json(OUT_DIR / "feasibility_decision.json", decision)

    artifacts = {}
    for path in sorted(OUT_DIR.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifacts[path.name] = {"path": str(path), "sha256": sha256_file(path)}

    manifest = {
        "overlay_id": OVERLAY_ID,
        "package": "cppi_engine_feasibility_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "label": SOURCE_LABEL,
        "decision": "MINIMAL_PATCH",
        "verdict_label": "MINIMAL_PATCH_REQUIRED",
        "repo_commit": git_commit_hash(ROOT),
        "config_hash": config_hash(cfg),
        "tests_passed": tests_passed,
        "test_commands": test_command_rows,
        "artifacts": artifacts,
        "files_changed_by_capability_patch": [
            "src/portfolio.py",
            "src/backtester.py",
            "src/overlays.py",
            "tests/test_cppi_engine_capability.py",
            "run_trade_management_cppi_engine_feasibility_v1.py",
        ],
        "prior_trade_management_packages_preserved": [
            "reports/trade_management/codex_overlay_v1_canonical_exploratory",
            "reports/trade_management/family_portability_batch_v1",
            "reports/trade_management/rebalance_band_robustness_v1",
        ],
        "execution_boundaries": {
            "comparative_performance_backtest": False,
            "validation_run": False,
            "parameter_search": False,
            "paper_demo_live": False,
            "broker_import_required": False,
        },
    }
    write_json(OUT_DIR / "manifest.json", manifest)

    if not tests_passed:
        raise SystemExit("CPPI feasibility package generated but tests failed; inspect test_results.txt")


if __name__ == "__main__":
    main()
