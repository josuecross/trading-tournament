from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtester import BacktestResult, Backtester
from src.data import DataLoadResult, load_market_data
from src.indicators import indicators_ready, prepare_indicators
from src.metrics import cagr, max_drawdown, recovery_time_days, sharpe_ratio, sortino_ratio
from src.overlays import (
    CPPIOverlay,
    DecisionPhase,
    DecisionType,
    IdentityOverlay,
    ManagedIntentBatch,
    OverlayDataError,
    ReasonCode,
    TargetUnit,
    TradeManagementOverlay,
    _target_weight,
    clone_entry_signal,
    stable_hash,
)
from src.portfolio import Portfolio
from src.strategies import EntrySignal, ExitSignal
from src.utils import config_hash, git_commit_hash, load_config, sha256_file


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "cppi_n4_methodology_correction_v1"
PRIOR_OUT_DIR = ROOT / "reports" / "trade_management" / "cppi_n4_exploratory_v1"
RUN_LABEL = "trade_management_cppi_m3_5y_monthly_n4_methodology_correction_v1"
PRIOR_RUN_LABEL = "trade_management_cppi_m3_5y_monthly_n4_exploratory_v1"
STAGE = "methodology_correction|research_only_exploration"
STRATEGY_ID = "N4_inverse_vol_defensive_allocation"
RISKY_ASSETS = ["GLD", "IEF", "SPY", "TLT"]
SAFE_ASSETS = ["BIL"]
REQUIRED_SYMBOLS = ["SPY", "IEF", "TLT", "GLD", "BIL"]
SLIPPAGES = [0.0, 0.0005, 0.001]
CPPI_PARAMS = {
    "overlay_id": "OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1",
    "multiplier": 3.0,
    "horizon_years": 5.0,
    "guarantee_fraction": 1.0,
    "safe_rate": 0.05,
    "safe_rate_compounding": "continuous",
    "rebalance_frequency": "month_end",
    "execution": "next_valid_open",
    "max_risky_exposure": 1.0,
    "leverage_allowed": False,
    "cash_lock_after_scheduled_floor_breach": True,
}
STATIC_INITIAL_RISK_CAP = min(3.0 * (1.0 - float(np.exp(-0.05 * 5.0))), 1.0)
TRIAL_NAMES = [
    "BASE",
    "IDENTITY",
    "SAFE5_TRANSLATION_CONTROL",
    "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL",
    "DYNAMIC_CPPI",
]
SAFE_LEDGER_TRIALS = [
    "SAFE5_TRANSLATION_CONTROL",
    "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL",
    "DYNAMIC_CPPI",
]
BROKER_CASH_TOLERANCE = 1e-6
ACCRUAL_TOLERANCE = 1e-6
PRIOR_INVALID_REASON = "INVALID_METHODOLOGY_SAFE_LEDGER_NOT_PERSISTENT"

TEST_COMMANDS = [
    [sys.executable, "-m", "pytest", "tests/test_cppi_engine_capability.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_audit_validation.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_cppi_n4_exploratory_v1.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_cppi_n4_methodology_correction_v1.py", "-q"],
    [
        sys.executable,
        "-m",
        "py_compile",
        "src/overlays.py",
        "src/portfolio.py",
        "src/backtester.py",
        "tests/test_cppi_engine_capability.py",
        "tests/test_trade_management_cppi_n4_exploratory_v1.py",
        "tests/test_trade_management_cppi_n4_methodology_correction_v1.py",
        "run_trade_management_cppi_n4_exploratory_v1.py",
        "run_trade_management_cppi_n4_methodology_correction_v1.py",
    ],
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_git(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd or ROOT, check=False, capture_output=True, text=True)


def git_root() -> Path:
    result = run_git(["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()) if result.returncode == 0 else ROOT


def tracked_and_untracked_diff_hash() -> dict[str, Any]:
    root = git_root()
    status = run_git(["status", "--porcelain=v1", "-uall"], cwd=root).stdout
    tracked_diff = run_git(["diff", "--binary"], cwd=root).stdout
    untracked_result = run_git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=root)
    untracked: list[dict[str, str]] = []
    if untracked_result.returncode == 0 and untracked_result.stdout:
        for rel in untracked_result.stdout.split("\0"):
            if not rel:
                continue
            path = root / rel
            if path.is_file():
                untracked.append({"path": rel.replace("\\", "/"), "sha256": sha256_file(path)})
    payload = {
        "git_root": str(root),
        "dirty": bool(status.strip()),
        "status_porcelain": status,
        "tracked_diff_sha256": sha256_text(tracked_diff),
        "untracked_file_hashes": sorted(untracked, key=lambda item: item["path"]),
    }
    payload["tracked_and_untracked_diff_hash"] = stable_hash(payload)
    return payload


def n4_only_config(config: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    cfg["strategy_order"] = [STRATEGY_ID]
    cfg["universe"]["symbols"] = REQUIRED_SYMBOLS.copy()
    cfg["universe"]["clusters"] = {
        "equity_index": ["SPY"],
        "bond": ["IEF", "TLT", "BIL"],
        "commodity_alternative": ["GLD"],
    }
    for name, strategy_cfg in cfg.get("strategies", {}).items():
        strategy_cfg["enabled"] = name == STRATEGY_ID
    return cfg


def n4_config_hash(config: dict[str, Any]) -> str:
    payload = {
        "strategy_id": STRATEGY_ID,
        "strategy_config": config["strategies"][STRATEGY_ID],
        "strategy_order": [STRATEGY_ID],
        "risky_assets": RISKY_ASSETS,
        "safe_assets": SAFE_ASSETS,
    }
    return stable_hash(payload)


def data_file_hashes(load_result: DataLoadResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    coverage = load_result.coverage.copy()
    for _, row in coverage.sort_values("symbol").iterrows():
        rows.append(
            {
                "symbol": row["symbol"],
                "status": row["status"],
                "first_date": row["first_date"],
                "last_date": row["last_date"],
                "row_count": int(row["row_count"]),
                "cache_file": row["cache_file"],
                "cache_file_hash": row["cache_file_hash"],
            }
        )
    return rows


def file_hash_inventory() -> dict[str, str]:
    paths = [
        "src/portfolio.py",
        "src/backtester.py",
        "src/overlays.py",
        "src/strategies.py",
        "config.yaml",
        "run_trade_management_cppi_engine_feasibility_v1.py",
        "run_trade_management_cppi_n4_exploratory_v1.py",
        "tests/test_cppi_engine_capability.py",
        "tests/test_trade_management_overlays.py",
        "tests/test_trade_management_cppi_n4_exploratory_v1.py",
        "reports/trade_management/cppi_engine_feasibility_v1/manifest.json",
        "reports/trade_management/cppi_engine_feasibility_v1/source_of_truth_update.md",
    ]
    return {path: sha256_file(ROOT / path) for path in paths if (ROOT / path).exists()}


def indexed(prepared: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {symbol: df.sort_values("date").set_index("date", drop=False) for symbol, df in prepared.items()}


def is_month_end(calendar: list[pd.Timestamp], date: pd.Timestamp) -> bool:
    idx = calendar.index(pd.Timestamp(date))
    if idx >= len(calendar) - 1:
        return True
    return calendar[idx + 1].month != pd.Timestamp(date).month


def first_trading_on_or_after(calendar: list[pd.Timestamp], date: pd.Timestamp) -> pd.Timestamp | None:
    candidates = [value for value in calendar if value >= pd.Timestamp(date)]
    return candidates[0] if candidates else None


def freeze_episode(config: dict[str, Any], prepared: dict[str, pd.DataFrame], load_result: DataLoadResult) -> dict[str, Any]:
    idx = indexed(prepared)
    spy_dates = list(pd.to_datetime(idx["SPY"].index))
    warmup = int(config["project"]["warmup_days"])
    required_columns = ["close", "sma_200", "rv_60", "atr_20"]
    for i, decision_date in enumerate(spy_dates):
        if i < warmup or i >= len(spy_dates) - 1:
            continue
        if spy_dates[i + 1].month == decision_date.month:
            continue
        ready = True
        for symbol in REQUIRED_SYMBOLS:
            if decision_date not in idx[symbol].index:
                ready = False
                break
            row = idx[symbol].loc[decision_date]
            if not isinstance(row, pd.Series):
                row = row.iloc[-1]
            if not indicators_ready(row, required_columns):
                ready = False
                break
        if not ready:
            continue
        maturity = decision_date + pd.DateOffset(years=int(CPPI_PARAMS["horizon_years"]))
        final_valuation_date = first_trading_on_or_after(spy_dates, maturity)
        if final_valuation_date is None:
            continue
        if not all(final_valuation_date in idx[symbol].index for symbol in REQUIRED_SYMBOLS):
            continue
        warmup_start = spy_dates[i - warmup]
        effective = Backtester(prepared, config)._effective_calendar(
            str(warmup_start.date()),
            str(final_valuation_date.date()),
        )
        if not effective or pd.Timestamp(effective[0]) != pd.Timestamp(decision_date):
            continue
        raw_ranges = []
        for symbol, df in prepared.items():
            if symbol not in REQUIRED_SYMBOLS:
                continue
            raw_ranges.append(
                {
                    "symbol": symbol,
                    "first_date": str(pd.to_datetime(df["date"]).min().date()),
                    "last_date": str(pd.to_datetime(df["date"]).max().date()),
                    "rows": int(len(df)),
                }
            )
        return {
            "episode_id": f"{RUN_LABEL}_{decision_date.date().isoformat()}_{final_valuation_date.date().isoformat()}",
            "selection_rule": "earliest deterministic complete five-year N4 episode with indicator warm-up and next-open execution",
            "raw_data_start": min(row["first_date"] for row in raw_ranges),
            "raw_data_end": max(row["last_date"] for row in raw_ranges),
            "raw_data_coverage": raw_ranges,
            "warmup_days": warmup,
            "warmup_start": warmup_start.date().isoformat(),
            "first_eligible_month_end_decision_date": decision_date.date().isoformat(),
            "episode_start": decision_date.date().isoformat(),
            "initial_execution_date": spy_dates[i + 1].date().isoformat(),
            "exact_calendar_maturity_timestamp": maturity.isoformat(),
            "final_valuation_date": final_valuation_date.date().isoformat(),
            "effective_trading_days": len(effective),
            "required_data_files": data_file_hashes(load_result),
            "not_selected_by_performance": True,
            "not_a_sealed_holdout": True,
        }
    raise RuntimeError("No complete five-year N4 CPPI episode found.")


class SyntheticSafeTargetOverlay(TradeManagementOverlay):
    supported_target_units = {TargetUnit.TARGET_WEIGHT}

    def __init__(
        self,
        *,
        overlay_id: str,
        risky_assets: list[str],
        safe_assets: list[str],
        risk_free_rate: float = 0.05,
        risky_cap: float | None = None,
    ) -> None:
        super().__init__(
            risky_assets=sorted(risky_assets),
            safe_assets=sorted(safe_assets),
            risk_free_rate=float(risk_free_rate),
            risky_cap=risky_cap,
        )
        self.overlay_id = overlay_id
        self.risky_assets = set(risky_assets)
        self.safe_assets = set(safe_assets)
        self.risk_free_rate = float(risk_free_rate)
        self.risky_cap = None if risky_cap is None else float(risky_cap)
        self.pending_safe_release_date: pd.Timestamp | None = None
        self.pending_safe_sweep_date: pd.Timestamp | None = None

    def _classify_symbol(self, symbol: str) -> str:
        if symbol in self.risky_assets:
            return "risky"
        if symbol in self.safe_assets:
            return "safe"
        raise OverlayDataError(f"{self.overlay_id}: ambiguous risky/safe mapping for {symbol!r}")

    def _is_scheduled_decision(self, date: pd.Timestamp) -> bool:
        current = pd.Timestamp(date)
        calendar = [pd.Timestamp(value) for value in self.calendar]
        try:
            idx = calendar.index(current)
        except ValueError:
            return False
        if idx >= len(calendar) - 1:
            return True
        return calendar[idx + 1].month != current.month

    def _next_execution_date(self, date: pd.Timestamp) -> pd.Timestamp:
        next_dates = [pd.Timestamp(value) for value in self.calendar if pd.Timestamp(value) > pd.Timestamp(date)]
        return next_dates[0] if next_dates else pd.Timestamp(date)

    def _set_next_safe_timing(self, date: pd.Timestamp) -> None:
        next_execution = self._next_execution_date(date)
        self.pending_safe_release_date = next_execution
        self.pending_safe_sweep_date = next_execution

    def _expected_exit_cash(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_exits: list[Any] | None,
        slippage_pct: float,
        portfolio: Portfolio,
    ) -> float:
        cash = 0.0
        for pending in pending_exits or []:
            signal = getattr(pending, "signal", pending)
            trade_id = getattr(signal, "trade_id", None)
            pos = next((item for item in portfolio.positions if item.trade_id == trade_id), None)
            if pos is None:
                continue
            row = rows.get(pos.symbol)
            if row is None or pd.isna(row.get("open")):
                continue
            exit_price = float(row["open"])
            if np.isfinite(slippage_pct) and 0.0 <= slippage_pct < 1.0:
                exit_price *= 1.0 - float(slippage_pct)
            cash += max(0.0, float(pos.shares) * exit_price)
        return cash

    def _expected_entry_funding(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None,
        portfolio: Portfolio,
    ) -> float:
        nav, _ = portfolio.mark_to_market(rows)
        if not np.isfinite(nav) or nav <= 0:
            return 0.0
        max_notional_pct = float(portfolio.config["project"].get("max_position_notional_pct", 1.0))
        projected_counts = {
            strategy: len(portfolio.positions_for_strategy(strategy))
            for strategy in portfolio.config.get("strategies", {})
        }
        funding = 0.0
        for pending in pending_entries or []:
            signal = getattr(pending, "signal", pending)
            symbol = getattr(signal, "symbol", "")
            if not symbol or self._classify_symbol(symbol) != "risky":
                continue
            row = rows.get(symbol)
            if row is None or pd.isna(row.get("open")):
                continue
            if portfolio.project_stopped or signal.strategy in portfolio.disabled_strategies:
                continue
            if portfolio.has_position(signal.strategy, symbol):
                continue
            strategy_cfg = portfolio.config["strategies"][signal.strategy]
            if projected_counts.get(signal.strategy, 0) >= int(strategy_cfg["max_positions"]):
                continue
            target = _target_weight(signal)
            if target is None or target <= 0:
                continue
            target_notional = nav * min(float(target), max_notional_pct)
            funding += max(0.0, target_notional)
            projected_counts[signal.strategy] = projected_counts.get(signal.strategy, 0) + 1
        return funding

    def _required_safe_release(
        self,
        *,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None,
        pending_exits: list[Any] | None,
        slippage_pct: float,
        portfolio: Portfolio,
    ) -> tuple[float, dict[str, Any]]:
        entry_funding = self._expected_entry_funding(
            rows=rows,
            pending_entries=pending_entries,
            portfolio=portfolio,
        )
        exit_cash = self._expected_exit_cash(
            rows=rows,
            pending_exits=pending_exits,
            slippage_pct=slippage_pct,
            portfolio=portfolio,
        )
        available = max(0.0, float(portfolio.cash)) + exit_cash
        required = max(0.0, entry_funding - available)
        return required, {
            "expected_risky_purchase_funding": entry_funding,
            "expected_exit_cash_before_entries": exit_cash,
            "broker_cash_before_release": float(portfolio.cash),
            "required_safe_release": required,
        }

    def _sweep_broker_cash_to_safe(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        reason: str,
    ) -> None:
        if portfolio.cash < -1e-9 or portfolio.synthetic_safe_account_value < -1e-9:
            raise OverlayDataError(f"{self.overlay_id}: negative safe-account reconciliation.")
        amount = max(0.0, float(portfolio.cash))
        if amount <= 1e-9:
            return
        portfolio.transfer_cash_to_synthetic_safe(amount)
        self.record_event(
            timestamp=date,
            phase=DecisionPhase.POST_FILL,
            decision_type=DecisionType.RECORD_FILL,
            reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_TRANSFER,
            proposed_order={"side": "broker_cash_to_synthetic_safe", "non_orderable": True, "reason": reason},
            actual_fill={"amount": amount, "fill_time": pd.Timestamp(date).isoformat()},
            modeled_cost=0.0,
            state_after={"safe_account_value": portfolio.synthetic_safe_account_value, "broker_cash": portfolio.cash},
        )

    def _accrue_safe_account(self, date: pd.Timestamp, portfolio: Portfolio) -> float:
        opening = float(portfolio.synthetic_safe_account_value)
        previous_date = portfolio.synthetic_safe_account_last_accrual_date
        elapsed_days = (
            max(0, (pd.Timestamp(date).normalize() - previous_date.normalize()).days)
            if previous_date is not None
            else 0
        )
        accrued = portfolio.accrue_synthetic_safe_account(date, self.risk_free_rate)
        if accrued > 1e-9:
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.POSITION_LIFECYCLE,
                decision_type=DecisionType.RECORD_FILL,
                reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_ACCRUAL,
                modeled_cost=0.0,
                state_after={
                    "opening_safe_account_value": opening,
                    "safe_account_value": portfolio.synthetic_safe_account_value,
                    "elapsed_calendar_days": elapsed_days,
                    "accrued_amount": accrued,
                    "risk_free_rate": self.risk_free_rate,
                },
            )
        return accrued

    def on_before_order_fills(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        pending_entries: list[Any] | None = None,
        pending_exits: list[Any] | None = None,
        slippage_pct: float = 0.0,
    ) -> None:
        self._accrue_safe_account(date, portfolio)
        if (
            self.pending_safe_release_date is not None
            and pd.Timestamp(date) >= self.pending_safe_release_date
            and portfolio.synthetic_safe_account_value > 1e-9
        ):
            required, funding_state = self._required_safe_release(
                rows=rows,
                pending_entries=pending_entries,
                pending_exits=pending_exits,
                slippage_pct=slippage_pct,
                portfolio=portfolio,
            )
            amount = min(portfolio.synthetic_safe_account_value, required)
            if amount > 1e-9:
                portfolio.transfer_synthetic_safe_to_cash(amount)
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.POST_FILL,
                    decision_type=DecisionType.RECORD_FILL,
                    reason_code=ReasonCode.CPPI_SAFE_ACCOUNT_TRANSFER,
                    proposed_order={
                        "side": "synthetic_safe_to_broker_cash",
                        "non_orderable": True,
                        "reason": "execution_funding",
                        **funding_state,
                    },
                    actual_fill={"amount": amount, "fill_time": pd.Timestamp(date).isoformat()},
                    modeled_cost=0.0,
                    state_after={"safe_account_value": portfolio.synthetic_safe_account_value, "broker_cash": portfolio.cash},
                    data_quality_flags={
                        "required_funding_release": True,
                        "released_without_funding_requirement": required <= 1e-9,
                    },
                )
            self.pending_safe_release_date = None
        elif self.pending_safe_release_date is not None and pd.Timestamp(date) >= self.pending_safe_release_date:
            self.pending_safe_release_date = None

    def process_position_lifecycle(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        self._accrue_safe_account(date, portfolio)
        if self.pending_safe_sweep_date is not None and pd.Timestamp(date) >= self.pending_safe_sweep_date:
            self._sweep_broker_cash_to_safe(
                date=date,
                portfolio=portfolio,
                reason="post_execution_same_day_sweep",
            )
            self.pending_safe_sweep_date = None

    def on_end_of_day(
        self,
        *,
        date: pd.Timestamp,
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        slippage_pct: float,
    ) -> None:
        self._sweep_broker_cash_to_safe(
            date=date,
            portfolio=portfolio,
            reason="end_of_day_safe_persistence",
        )

    def on_signal_batch(
        self,
        *,
        date: pd.Timestamp,
        entries: list[EntrySignal],
        exits: list[ExitSignal],
        portfolio: Portfolio,
        rows: dict[str, pd.Series],
        equity: float,
        pending_exit_ids: set[int],
    ) -> ManagedIntentBatch:
        actionable = [entry for entry in entries if entry.symbol]
        scheduled = self._is_scheduled_decision(date)
        if not actionable and not exits and not scheduled:
            return ManagedIntentBatch(entries=entries, exits=exits)
        if not np.isfinite(equity) or equity <= 0:
            raise OverlayDataError(f"{self.overlay_id}: non-finite NAV.")
        if any(_target_weight(entry) is None for entry in actionable):
            self.record_unsupported_intent_unit_once(date=date, entries=actionable, phase=DecisionPhase.TARGET_TRANSFORM)
            raise OverlayDataError(f"{self.overlay_id}: target_weight required.")

        base_targets = {entry.symbol: float(_target_weight(entry) or 0.0) for entry in actionable}
        classes = {symbol: self._classify_symbol(symbol) for symbol in base_targets}
        base_risky_fraction = sum(abs(weight) for symbol, weight in base_targets.items() if classes[symbol] == "risky")
        cap = base_risky_fraction if self.risky_cap is None else min(base_risky_fraction, self.risky_cap)
        scale = cap / base_risky_fraction if base_risky_fraction > 1e-12 else 0.0
        if scale > 1.0 + 1e-12:
            raise OverlayDataError(f"{self.overlay_id}: attempted to increase base exposure.")

        managed_entries: list[EntrySignal] = []
        for entry in entries:
            target = _target_weight(entry)
            if not entry.symbol or target is None:
                continue
            classification = classes[entry.symbol]
            if classification == "safe":
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.CPPI_SAFE_ASSET_REDIRECT,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=0.0,
                    proposed_order={"synthetic_safe_account": True, "base_safe_target_weight": float(target)},
                    data_quality_flags={"same_close_execution": False, "safe_asset_redirected_to_synthetic_ledger": True},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_target = float(target) * scale
            if managed_target <= 1e-12:
                self.record_event(
                    timestamp=date,
                    phase=DecisionPhase.TARGET_TRANSFORM,
                    decision_type=DecisionType.SUPPRESS_ORDER,
                    reason_code=ReasonCode.CPPI_RESIZE,
                    signal=entry,
                    asset=entry.symbol,
                    base_target=float(target),
                    managed_target=0.0,
                    proposed_order={"base_risky_fraction": base_risky_fraction, "managed_risky_fraction": cap},
                    data_quality_flags={"base_exposure_not_increased": True, "same_close_execution": False},
                    target_unit=TargetUnit.TARGET_WEIGHT,
                )
                continue
            managed_entries.append(
                clone_entry_signal(
                    entry,
                    metadata_updates={
                        "target_weight": managed_target,
                        "overlay_base_target_weight": float(target),
                        "synthetic_safe_control_risky_scale": scale,
                        "synthetic_safe_control_risky_cap": cap,
                    },
                )
            )
            self.record_event(
                timestamp=date,
                phase=DecisionPhase.TARGET_TRANSFORM,
                decision_type=DecisionType.RESIZE_TARGET if not np.isclose(managed_target, float(target)) else DecisionType.PASS_THROUGH,
                reason_code=ReasonCode.CPPI_RESIZE,
                signal=entry,
                asset=entry.symbol,
                base_target=float(target),
                managed_target=managed_target,
                proposed_order={"base_risky_fraction": base_risky_fraction, "managed_risky_fraction": cap},
                data_quality_flags={
                    "base_exposure_not_increased": managed_target <= float(target) + 1e-12,
                    "same_close_execution": False,
                    "static_risky_cap": self.risky_cap,
                },
                target_unit=TargetUnit.TARGET_WEIGHT,
            )

        self._set_next_safe_timing(date)
        return ManagedIntentBatch(entries=managed_entries, exits=exits)


class Safe5TranslationControl(SyntheticSafeTargetOverlay):
    def __init__(self) -> None:
        super().__init__(
            overlay_id="SAFE5_TRANSLATION_CONTROL",
            risky_assets=RISKY_ASSETS,
            safe_assets=SAFE_ASSETS,
            risk_free_rate=0.05,
            risky_cap=None,
        )


class StaticCPPIInitialRiskCapControl(SyntheticSafeTargetOverlay):
    def __init__(self) -> None:
        super().__init__(
            overlay_id="STATIC_CPPI_INITIAL_RISK_CAP_CONTROL",
            risky_assets=RISKY_ASSETS,
            safe_assets=SAFE_ASSETS,
            risk_free_rate=0.05,
            risky_cap=STATIC_INITIAL_RISK_CAP,
        )


def df_hash(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return stable_hash({"empty": True, "columns": [] if df is None else list(df.columns)})
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].astype(str)
    return stable_hash({"columns": list(normalized.columns), "csv": normalized.to_csv(index=False, lineterminator="\n", na_rep="<NA>")})


def signal_ledger(result: BacktestResult) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not result.trades.empty:
        for _, trade in result.trades.iterrows():
            signal_date = str(trade.get("entry_signal_date", trade.get("signal_date", "")))
            rows.append(
                {
                    "source": "accepted_trade",
                    "signal_id": f"{trade.get('strategy')}:{trade.get('symbol')}:{signal_date}:entry",
                    "timestamp": signal_date,
                    "asset": trade.get("symbol", ""),
                    "trade_id": trade.get("trade_id", ""),
                    "entry_date": trade.get("entry_date", ""),
                    "exit_date": trade.get("exit_date", ""),
                    "exit_reason": trade.get("exit_reason", ""),
                }
            )
    if not result.skipped_signals.empty:
        for idx, skip in result.skipped_signals.iterrows():
            rows.append(
                {
                    "source": "rejected_signal",
                    "signal_id": f"{skip.get('strategy')}:{skip.get('symbol')}:{skip.get('date')}:{skip.get('signal_type')}:{idx}",
                    "timestamp": skip.get("date", ""),
                    "asset": skip.get("symbol", ""),
                    "trade_id": "",
                    "entry_date": "",
                    "exit_date": "",
                    "exit_reason": skip.get("reason_skipped", ""),
                }
            )
    return pd.DataFrame(rows)


def result_hashes(result: BacktestResult) -> dict[str, str]:
    components = {
        "daily_state_hash": df_hash(result.equity_curve),
        "trade_ledger_hash": df_hash(result.trades),
        "skipped_orders_hash": df_hash(result.skipped_signals),
        "risk_events_hash": df_hash(result.risk_events),
        "lifecycle_events_hash": df_hash(result.strategy_lifecycle_events),
        "metrics_hash": df_hash(result.strategy_metrics),
        "target_timing_hash": df_hash(result.target_timing),
        "signal_ledger_hash": df_hash(signal_ledger(result)),
    }
    components["complete_state_hash"] = stable_hash(components)
    return components


def run_trial(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    episode: dict[str, Any],
    trial_name: str,
    slippage: float,
    overlay: TradeManagementOverlay | None,
    base_strategy_hash: str,
) -> BacktestResult:
    return Backtester(prepared, config).run(
        trial_name,
        episode["warmup_start"],
        episode["final_valuation_date"],
        slippage,
        lightweight_outputs=True,
        overlay=overlay,
        run_id=f"{RUN_LABEL}_{trial_name}_{int(round(slippage * 10000))}bps",
        base_strategy_id=STRATEGY_ID,
        base_strategy_hash=base_strategy_hash,
    )


def overlay_for_trial(trial_name: str, episode: dict[str, Any]) -> TradeManagementOverlay | None:
    if trial_name == "BASE":
        return None
    if trial_name == "IDENTITY":
        return IdentityOverlay()
    if trial_name == "SAFE5_TRANSLATION_CONTROL":
        return Safe5TranslationControl()
    if trial_name == "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL":
        return StaticCPPIInitialRiskCapControl()
    if trial_name == "DYNAMIC_CPPI":
        return CPPIOverlay(
            risky_assets=set(RISKY_ASSETS),
            safe_assets=set(SAFE_ASSETS),
            horizon_years=5.0,
            guarantee_fraction=1.0,
            risk_free_rate=0.05,
            multiplier=3.0,
            max_risky_exposure=1.0,
            leverage_allowed=False,
            cash_lock_after_floor_breach=True,
            episode_start=episode["episode_start"],
        )
    raise ValueError(f"Unknown trial {trial_name}")


def price_lookup(prepared: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    return {symbol: df.sort_values("date").set_index("date")["close"].astype(float) for symbol, df in prepared.items()}


def reconstruct_position_values(
    result: BacktestResult,
    prepared: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    prices = price_lookup(prepared)
    rows: list[dict[str, Any]] = []
    trades = result.trades.copy()
    for date in equity["date"]:
        by_symbol = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
        if not trades.empty:
            for _, trade in trades.iterrows():
                entry_date = pd.Timestamp(trade["entry_date"])
                exit_date = pd.Timestamp(trade["exit_date"])
                if not (entry_date <= date < exit_date):
                    continue
                symbol = str(trade["symbol"])
                if symbol not in prices or date not in prices[symbol].index:
                    continue
                by_symbol[symbol] = by_symbol.get(symbol, 0.0) + float(trade["shares"]) * float(prices[symbol].loc[date])
        row = {"date": date.date().isoformat()}
        row.update({f"{symbol}_market_value": value for symbol, value in sorted(by_symbol.items())})
        row["risky_market_value"] = sum(by_symbol.get(symbol, 0.0) for symbol in RISKY_ASSETS)
        row["bil_market_value"] = by_symbol.get("BIL", 0.0)
        row["marked_open_positions"] = sum(by_symbol.values())
        rows.append(row)
    return pd.DataFrame(rows)


def years_remaining(date: pd.Timestamp, maturity: pd.Timestamp) -> float:
    remaining_days = max((pd.Timestamp(maturity).normalize() - pd.Timestamp(date).normalize()).days, 0)
    return float(remaining_days / 365.25)


def floor_value(initial_nav: float, date: pd.Timestamp, maturity: pd.Timestamp) -> float:
    return float(initial_nav * np.exp(-0.05 * years_remaining(date, maturity)))


def decision_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["date", "base_requested_risky_fraction", "managed_risky_fraction"])
    frame = events.copy()
    frame["date"] = pd.to_datetime(frame["timestamp"], errors="coerce").dt.date.astype(str)
    frame["base_target"] = pd.to_numeric(frame["base_target"], errors="coerce").fillna(0.0)
    frame["managed_target"] = pd.to_numeric(frame["managed_target"], errors="coerce").fillna(0.0)
    frame = frame[frame["asset"].isin(RISKY_ASSETS)]
    if frame.empty:
        return pd.DataFrame(columns=["date", "base_requested_risky_fraction", "managed_risky_fraction"])
    grouped = frame.groupby("date", as_index=False).agg(
        base_requested_risky_fraction=("base_target", lambda x: float(np.abs(x).sum())),
        managed_risky_fraction=("managed_target", lambda x: float(np.abs(x).sum())),
    )
    return grouped


def daily_state_rows(
    *,
    result: BacktestResult,
    prepared: dict[str, pd.DataFrame],
    episode: dict[str, Any],
    trial_name: str,
    slippage: float,
) -> list[dict[str, Any]]:
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    equity["date_key"] = equity["date"].dt.date.astype(str)
    positions = reconstruct_position_values(result, prepared)
    positions["date_key"] = positions["date"].astype(str)
    merged = equity.merge(
        positions.drop(columns=["date"]),
        on="date_key",
        how="left",
        suffixes=("", "_pos"),
    )
    merged["date"] = merged["date_key"]
    maturity = pd.Timestamp(episode["exact_calendar_maturity_timestamp"])
    initial_nav = float(equity["equity"].iloc[0])
    calendar = list(equity["date"])
    decision_summary = decision_event_summary(result.overlay_events)
    if not decision_summary.empty:
        merged = merged.merge(decision_summary, on="date", how="left")
    else:
        merged["base_requested_risky_fraction"] = np.nan
        merged["managed_risky_fraction"] = np.nan
    cash_lock_dates: list[pd.Timestamp] = []
    if not result.overlay_events.empty:
        lock_events = result.overlay_events[result.overlay_events["reason_code"].eq("cppi_cash_lock")]
        cash_lock_dates = [pd.Timestamp(value) for value in lock_events["timestamp"].dropna()]
    first_lock = min(cash_lock_dates) if cash_lock_dates else None
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        date = pd.Timestamp(row["date"])
        nav = float(row["equity"])
        floor = floor_value(initial_nav, date, maturity)
        cushion = nav - floor
        cap = min(3.0 * max(cushion, 0.0) / nav, 1.0) if nav > 0 else np.nan
        marked = float(row.get("marked_open_positions", 0.0) or 0.0)
        safe = float(row.get("synthetic_safe_account_value", 0.0) or 0.0)
        cash = float(row.get("cash", 0.0) or 0.0)
        reconstructed_nav = cash + safe + marked
        scheduled = is_month_end(calendar, date)
        rows.append(
            {
                "trial_name": trial_name,
                "slippage_bps_per_side": slippage * 10000.0,
                "date": date.date().isoformat(),
                "nav": nav,
                "broker_cash": cash,
                "synthetic_safe_account_value": safe,
                "marked_open_positions": marked,
                "reconstructed_nav": reconstructed_nav,
                "nav_reconciliation_error": reconstructed_nav - nav,
                "nav_reconciles": abs(reconstructed_nav - nav) <= 1e-6,
                "floor": floor,
                "nav_minus_floor": cushion,
                "nav_floor_ratio": nav / floor if floor else np.nan,
                "diagnostic_risky_cap": cap,
                "scheduled_decision": scheduled,
                "base_requested_risky_fraction": row.get("base_requested_risky_fraction", np.nan),
                "managed_risky_fraction": row.get("managed_risky_fraction", np.nan),
                "actual_risky_exposure": float(row.get("risky_market_value", 0.0) or 0.0) / nav if nav else np.nan,
                "actual_bil_exposure": float(row.get("bil_market_value", 0.0) or 0.0) / nav if nav else np.nan,
                "synthetic_safe_exposure": safe / nav if nav else np.nan,
                "broker_cash_exposure": cash / nav if nav else np.nan,
                "cash_locked": bool(first_lock is not None and date >= first_lock),
            }
        )
    return rows


def trade_turnover(trades: pd.DataFrame, equity: pd.DataFrame) -> float:
    if trades.empty or equity.empty:
        return 0.0
    entry_notional = trades["notional_value"].astype(float).abs().sum() if "notional_value" in trades else 0.0
    exit_notional = (trades["shares"].astype(float).abs() * trades["exit_price"].astype(float).abs()).sum()
    avg_nav = equity["equity"].astype(float).mean()
    return float((entry_notional + exit_notional) / avg_nav) if avg_nav else np.nan


def expected_shortfall(daily_returns: pd.Series, q: float = 0.05) -> float:
    values = daily_returns.dropna().astype(float).sort_values()
    if values.empty:
        return np.nan
    cutoff = max(1, int(np.ceil(len(values) * q)))
    return float(values.iloc[:cutoff].mean())


def metric_row(
    *,
    result: BacktestResult,
    daily_rows: list[dict[str, Any]],
    episode: dict[str, Any],
    trial_name: str,
    slippage: float,
) -> dict[str, Any]:
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    nav = equity["equity"].astype(float)
    returns = nav.pct_change()
    dd_dollars, dd_pct = max_drawdown(nav)
    total_return = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    state = pd.DataFrame(daily_rows)
    scheduled = state[state["scheduled_decision"].astype(bool)]
    dynamic = scheduled if trial_name == "DYNAMIC_CPPI" else pd.DataFrame()
    target_series = pd.to_numeric(scheduled.get("managed_risky_fraction", pd.Series(dtype=float)), errors="coerce")
    if target_series.dropna().empty:
        target_series = pd.to_numeric(scheduled.get("base_requested_risky_fraction", pd.Series(dtype=float)), errors="coerce")
    total_safe_accrual = 0.0
    if result.overlay_events is not None and not result.overlay_events.empty:
        accrual_events = result.overlay_events[result.overlay_events["reason_code"].eq("cppi_safe_account_accrual")]
        for _, event in accrual_events.iterrows():
            state_after = json_dict(event.get("state_after"))
            total_safe_accrual += float(state_after.get("accrued_amount", 0.0) or 0.0)
    base_cap_mask = pd.Series(dtype=bool)
    if not dynamic.empty:
        base_req = pd.to_numeric(dynamic["base_requested_risky_fraction"], errors="coerce").fillna(0.0)
        caps = pd.to_numeric(dynamic["diagnostic_risky_cap"], errors="coerce")
        base_cap_mask = base_req <= caps + 1e-12
    cash_locked_pct = float(state["cash_locked"].mean()) if "cash_locked" in state else 0.0
    min_cushion = float(state["nav_minus_floor"].min())
    scheduled_breaches = int(((scheduled["nav_minus_floor"] <= 0.0) if not scheduled.empty else pd.Series(dtype=bool)).sum())
    intraperiod_shortfalls = int(((state["nav_minus_floor"] < 0.0) & ~state["scheduled_decision"].astype(bool)).sum())
    cash_lock_date = ""
    if cash_locked_pct > 0:
        cash_lock_date = str(state[state["cash_locked"].astype(bool)]["date"].iloc[0])
    return {
        "trial_name": trial_name,
        "slippage_bps_per_side": slippage * 10000.0,
        "initial_nav": float(nav.iloc[0]),
        "terminal_nav": float(nav.iloc[-1]),
        "total_return": total_return,
        "annualized_return": cagr(nav, equity["date"]),
        "annualized_volatility": float(returns.std() * np.sqrt(252)),
        "maximum_drawdown": float(dd_pct),
        "maximum_drawdown_dollars": float(dd_dollars),
        "drawdown_duration_days": recovery_time_days(nav),
        "sharpe": sharpe_ratio(nav),
        "sortino": sortino_ratio(nav),
        "return_to_drawdown": total_return / abs(dd_pct) if np.isfinite(dd_pct) and abs(dd_pct) > 1e-12 else np.nan,
        "worst_daily_return": float(returns.min()),
        "expected_shortfall_5pct": expected_shortfall(returns, 0.05),
        "average_risky_exposure": float(state["actual_risky_exposure"].mean()),
        "maximum_risky_exposure": float(state["actual_risky_exposure"].max()),
        "average_target_risky_exposure": float(target_series.dropna().mean()) if not target_series.dropna().empty else np.nan,
        "average_synthetic_safe_exposure": float(state["synthetic_safe_exposure"].mean()),
        "average_bil_exposure": float(state["actual_bil_exposure"].mean()),
        "average_broker_cash": float(state["broker_cash"].mean()),
        "average_broker_cash_exposure": float(state["broker_cash_exposure"].mean()),
        "total_safe_accrual": total_safe_accrual,
        "turnover": trade_turnover(result.trades, equity),
        "orders": int(len(result.trades) * 2),
        "fills": int(len(result.trades) * 2),
        "completed_trades": int(len(result.trades)),
        "corrected_modeled_transaction_cost": float(result.trades.get("slippage_paid_estimate", pd.Series(dtype=float)).sum()),
        "maturity_guarantee": float(nav.iloc[0] * CPPI_PARAMS["guarantee_fraction"]),
        "terminal_surplus_or_shortfall_relative_to_guarantee": float(nav.iloc[-1] - nav.iloc[0] * CPPI_PARAMS["guarantee_fraction"]),
        "minimum_nav_minus_floor_cushion": min_cushion,
        "minimum_nav_floor_ratio": float(state["nav_floor_ratio"].min()),
        "intraperiod_floor_shortfall_count": intraperiod_shortfalls,
        "scheduled_floor_breach_count": scheduled_breaches,
        "gap_shortfall_amount": abs(min(0.0, min_cushion)),
        "cash_lock_date": cash_lock_date,
        "percentage_episode_cash_locked": cash_locked_pct,
        "monthly_cppi_decisions": int(len(scheduled)),
        "dynamic_risky_cap_mean": float(dynamic["diagnostic_risky_cap"].mean()) if not dynamic.empty else np.nan,
        "dynamic_risky_cap_std": float(dynamic["diagnostic_risky_cap"].std(ddof=0)) if not dynamic.empty else np.nan,
        "dynamic_risky_cap_min": float(dynamic["diagnostic_risky_cap"].min()) if not dynamic.empty else np.nan,
        "dynamic_risky_cap_max": float(dynamic["diagnostic_risky_cap"].max()) if not dynamic.empty else np.nan,
        "pct_dynamic_decisions_capped_by_base_exposure": float(base_cap_mask.mean()) if len(base_cap_mask) else np.nan,
        "pct_dynamic_decisions_at_zero_risky_exposure": float((dynamic["diagnostic_risky_cap"] <= 1e-12).mean()) if not dynamic.empty else np.nan,
        "pct_dynamic_decisions_at_100pct_risky_exposure": float((dynamic["diagnostic_risky_cap"] >= 1.0 - 1e-12).mean()) if not dynamic.empty else np.nan,
        "project_stop_hit": bool(result.metadata.get("project_stop_hit", False)),
        "killed_strategies": "|".join(result.killed_strategies),
    }


def json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    try:
        parsed = json.loads(str(value) or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def float_or_nan(value: Any) -> float:
    if value is None or value == "":
        return np.nan
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result


def safe_transfer_rows(result: BacktestResult) -> pd.DataFrame:
    if result.overlay_events.empty:
        return pd.DataFrame(columns=["date", "safe_to_broker_cash", "broker_cash_to_safe", "daily_safe_accrual", "safe_transfer_cost"])
    rows: list[dict[str, Any]] = []
    for _, event in result.overlay_events.iterrows():
        date = str(pd.Timestamp(event["timestamp"]).date()) if event.get("timestamp") else ""
        proposed = json_dict(event.get("proposed_order"))
        actual = json_dict(event.get("actual_fill"))
        state = json_dict(event.get("state_after"))
        reason = event.get("reason_code", "")
        amount = float(actual.get("amount", 0.0) or 0.0)
        rows.append(
            {
                "date": date,
                "safe_to_broker_cash": amount if proposed.get("side") == "synthetic_safe_to_broker_cash" else 0.0,
                "broker_cash_to_safe": amount if proposed.get("side") == "broker_cash_to_synthetic_safe" else 0.0,
                "daily_safe_accrual": float(state.get("accrued_amount", 0.0) or 0.0)
                if reason == "cppi_safe_account_accrual"
                else 0.0,
                "safe_transfer_cost": float(event.get("modeled_cost", 0.0) or 0.0)
                if reason == "cppi_safe_account_transfer"
                else 0.0,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["date", "safe_to_broker_cash", "broker_cash_to_safe", "daily_safe_accrual", "safe_transfer_cost"])
    return pd.DataFrame(rows).groupby("date", as_index=False).sum(numeric_only=True)


def reconciliation_rows(
    *,
    result: BacktestResult,
    daily_rows: list[dict[str, Any]],
    trial_name: str,
    slippage: float,
) -> list[dict[str, Any]]:
    state = pd.DataFrame(daily_rows)
    transfers = safe_transfer_rows(result)
    if not transfers.empty:
        state = state.merge(transfers, on="date", how="left")
    for col in ["safe_to_broker_cash", "broker_cash_to_safe", "daily_safe_accrual", "safe_transfer_cost"]:
        if col not in state:
            state[col] = 0.0
        state[col] = state[col].fillna(0.0)
    trade_costs: list[dict[str, Any]] = []
    if not result.trades.empty:
        for _, trade in result.trades.iterrows():
            trade_costs.append(
                {
                    "date": trade["exit_date"],
                    "risky_asset_purchase_or_sale": float(trade["notional_value"]) + abs(float(trade["shares"]) * float(trade["exit_price"])),
                    "transaction_cost": float(trade.get("slippage_paid_estimate", 0.0) or 0.0),
                }
            )
    trade_cost_frame = pd.DataFrame(trade_costs)
    if not trade_cost_frame.empty:
        trade_cost_frame = trade_cost_frame.groupby("date", as_index=False).sum(numeric_only=True)
        state = state.merge(trade_cost_frame, on="date", how="left")
    for col in ["risky_asset_purchase_or_sale", "transaction_cost"]:
        if col not in state:
            state[col] = 0.0
        state[col] = state[col].fillna(0.0)
    rows = []
    for _, row in state.iterrows():
        rows.append(
            {
                "trial_name": trial_name,
                "slippage_bps_per_side": slippage * 10000.0,
                "date": row["date"],
                "total_nav": row["nav"],
                "broker_cash": row["broker_cash"],
                "synthetic_safe_account_value": row["synthetic_safe_account_value"],
                "marked_open_positions": row["marked_open_positions"],
                "reconstructed_nav": row["reconstructed_nav"],
                "nav_reconciliation_error": row["nav_reconciliation_error"],
                "nav_reconciles": row["nav_reconciles"],
                "safe_to_broker_cash": row["safe_to_broker_cash"],
                "broker_cash_to_safe": row["broker_cash_to_safe"],
                "risky_asset_purchase_or_sale": row["risky_asset_purchase_or_sale"],
                "transaction_cost": row["transaction_cost"],
                "daily_safe_accrual": row["daily_safe_accrual"],
                "safe_transfer_cost": row["safe_transfer_cost"],
                "negative_synthetic_safe_balance": row["synthetic_safe_account_value"] < -1e-9,
                "internal_transfers_cost_free": abs(row["safe_transfer_cost"]) <= 1e-12,
            }
        )
    return rows


def safe_event_detail_rows(
    *,
    result: BacktestResult,
    trial_name: str,
    slippage: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if result.overlay_events.empty:
        return rows
    events = result.overlay_events[
        result.overlay_events["reason_code"].isin(["cppi_safe_account_transfer", "cppi_safe_account_accrual"])
    ].copy()
    for _, event in events.iterrows():
        timestamp = pd.Timestamp(event["timestamp"])
        proposed = json_dict(event.get("proposed_order"))
        actual = json_dict(event.get("actual_fill"))
        state = json_dict(event.get("state_after"))
        flags = json_dict(event.get("data_quality_flags"))
        amount = float(actual.get("amount", 0.0) or 0.0)
        side = str(proposed.get("side", "safe_accrual"))
        required = float(proposed.get("required_safe_release", 0.0) or 0.0)
        expected_funding = float(proposed.get("expected_risky_purchase_funding", 0.0) or 0.0)
        rows.append(
            {
                "trial_name": trial_name,
                "slippage_bps_per_side": slippage * 10000.0,
                "date": timestamp.date().isoformat(),
                "event_id": event.get("event_id", ""),
                "reason_code": event.get("reason_code", ""),
                "side": side,
                "amount": amount,
                "opening_safe_account_value": float_or_nan(state.get("opening_safe_account_value", np.nan)),
                "elapsed_calendar_days": float_or_nan(state.get("elapsed_calendar_days", np.nan)),
                "accrued_amount": float(state.get("accrued_amount", 0.0) or 0.0),
                "closing_safe_account_value": float_or_nan(state.get("safe_account_value", np.nan)),
                "broker_cash_after": float_or_nan(state.get("broker_cash", np.nan)),
                "required_safe_release": required,
                "expected_risky_purchase_funding": expected_funding,
                "expected_exit_cash_before_entries": float(proposed.get("expected_exit_cash_before_entries", 0.0) or 0.0),
                "broker_cash_before_release": float(proposed.get("broker_cash_before_release", 0.0) or 0.0),
                "released_without_funding_requirement": bool(flags.get("released_without_funding_requirement", False)),
                "internal_transfer_modeled_cost": float(event.get("modeled_cost", 0.0) or 0.0)
                if event.get("reason_code", "") == "cppi_safe_account_transfer"
                else 0.0,
                "transfer_reason": proposed.get("reason", ""),
            }
        )
    return rows


def trade_fill_dates(result: BacktestResult) -> set[str]:
    dates: set[str] = set()
    if result.trades.empty:
        return dates
    for col in ["entry_date", "exit_date"]:
        if col in result.trades:
            dates.update(pd.to_datetime(result.trades[col], errors="coerce").dropna().dt.date.astype(str).tolist())
    return dates


def safe_accrual_recalculation_rows(
    *,
    daily_rows_all: list[dict[str, Any]],
    safe_event_rows_all: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    daily = pd.DataFrame(daily_rows_all)
    events = pd.DataFrame(safe_event_rows_all)
    rows: list[dict[str, Any]] = []
    if daily.empty:
        return rows
    if events.empty:
        events = pd.DataFrame(columns=["trial_name", "slippage_bps_per_side", "date", "accrued_amount", "opening_safe_account_value", "elapsed_calendar_days"])
    accrual_events = events[events["reason_code"].eq("cppi_safe_account_accrual")] if "reason_code" in events else events.iloc[0:0]
    grouped_actual = (
        accrual_events.groupby(["trial_name", "slippage_bps_per_side", "date"], as_index=False)
        .agg(
            actual_accrual=("accrued_amount", "sum"),
            recorded_opening_safe_account_value=("opening_safe_account_value", "first"),
            recorded_elapsed_calendar_days=("elapsed_calendar_days", "first"),
        )
        if not accrual_events.empty
        else pd.DataFrame(
            columns=[
                "trial_name",
                "slippage_bps_per_side",
                "date",
                "actual_accrual",
                "recorded_opening_safe_account_value",
                "recorded_elapsed_calendar_days",
            ]
        )
    )
    for (trial_name, bps), group in daily[daily["trial_name"].isin(SAFE_LEDGER_TRIALS)].groupby(
        ["trial_name", "slippage_bps_per_side"]
    ):
        group = group.copy()
        group["date_ts"] = pd.to_datetime(group["date"])
        group = group.sort_values("date_ts")
        actual_lookup = grouped_actual[
            grouped_actual["trial_name"].eq(trial_name) & grouped_actual["slippage_bps_per_side"].eq(bps)
        ].set_index("date")
        previous_date: pd.Timestamp | None = None
        previous_safe = 0.0
        for _, row in group.iterrows():
            date = pd.Timestamp(row["date_ts"])
            elapsed = 0 if previous_date is None else max(0, (date.normalize() - previous_date.normalize()).days)
            expected = previous_safe * (float(np.exp(CPPI_PARAMS["safe_rate"] * elapsed / 365.0)) - 1.0) if previous_safe > 0 else 0.0
            actual_row = actual_lookup.loc[row["date"]] if row["date"] in actual_lookup.index else None
            if isinstance(actual_row, pd.DataFrame):
                actual_row = actual_row.iloc[0]
            actual = float(actual_row["actual_accrual"]) if actual_row is not None else 0.0
            recorded_opening = (
                float(actual_row["recorded_opening_safe_account_value"])
                if actual_row is not None and pd.notna(actual_row["recorded_opening_safe_account_value"])
                else np.nan
            )
            recorded_elapsed = (
                float(actual_row["recorded_elapsed_calendar_days"])
                if actual_row is not None and pd.notna(actual_row["recorded_elapsed_calendar_days"])
                else np.nan
            )
            rows.append(
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": bps,
                    "date": row["date"],
                    "opening_safe_account_value": previous_safe,
                    "calendar_days_elapsed": elapsed,
                    "expected_accrual_5pct_continuous_365": expected,
                    "actual_recorded_accrual": actual,
                    "accrual_reconciliation_error": actual - expected,
                    "recorded_opening_safe_account_value": recorded_opening,
                    "recorded_elapsed_calendar_days": recorded_elapsed,
                    "closing_safe_account_value": float(row["synthetic_safe_account_value"]),
                }
            )
            previous_date = date
            previous_safe = float(row["synthetic_safe_account_value"])
    return rows


def safe_persistence_diagnostic_rows(
    *,
    daily_rows_all: list[dict[str, Any]],
    safe_event_rows_all: list[dict[str, Any]],
    accrual_rows: list[dict[str, Any]],
    results: dict[tuple[float, str], BacktestResult],
) -> list[dict[str, Any]]:
    daily = pd.DataFrame(daily_rows_all)
    events = pd.DataFrame(safe_event_rows_all)
    accrual = pd.DataFrame(accrual_rows)
    rows: list[dict[str, Any]] = []
    if daily.empty:
        return rows
    if events.empty:
        events = pd.DataFrame(
            columns=[
                "trial_name",
                "slippage_bps_per_side",
                "reason_code",
                "side",
                "amount",
                "internal_transfer_modeled_cost",
                "date",
            ]
        )
    if accrual.empty:
        accrual = pd.DataFrame(
            columns=[
                "trial_name",
                "slippage_bps_per_side",
                "expected_accrual_5pct_continuous_365",
                "accrual_reconciliation_error",
            ]
        )
    for (trial_name, bps), group in daily[daily["trial_name"].isin(SAFE_LEDGER_TRIALS)].groupby(
        ["trial_name", "slippage_bps_per_side"]
    ):
        state = group.copy()
        state["intended_safe_allocation"] = state["broker_cash"].astype(float) + state["synthetic_safe_account_value"].astype(float)
        intended = state["intended_safe_allocation"] > BROKER_CASH_TOLERANCE
        held = intended & (state["synthetic_safe_account_value"].astype(float) > BROKER_CASH_TOLERANCE) & (
            state["broker_cash"].astype(float).abs() <= BROKER_CASH_TOLERANCE
        )
        unexplained_cash = state["broker_cash"].astype(float).abs() > BROKER_CASH_TOLERANCE
        event_group = events[events["trial_name"].eq(trial_name) & events["slippage_bps_per_side"].eq(bps)]
        accrual_group = accrual[accrual["trial_name"].eq(trial_name) & accrual["slippage_bps_per_side"].eq(bps)]
        fill_dates = trade_fill_dates(results[(float(bps) / 10000.0, trial_name)])
        transfer_events = event_group[event_group["reason_code"].eq("cppi_safe_account_transfer")]
        transfers_without_fills = transfer_events[
            (transfer_events["amount"].astype(float) > BROKER_CASH_TOLERANCE) & ~transfer_events["date"].astype(str).isin(fill_dates)
        ]
        total_safe_accrual = float(event_group["accrued_amount"].astype(float).sum()) if "accrued_amount" in event_group else 0.0
        theoretical_safe_accrual = (
            float(accrual_group["expected_accrual_5pct_continuous_365"].astype(float).sum()) if not accrual_group.empty else 0.0
        )
        accrual_error = (
            float(accrual_group["accrual_reconciliation_error"].astype(float).sum()) if not accrual_group.empty else 0.0
        )
        persistence_rate = float(held.sum() / intended.sum()) if int(intended.sum()) else 1.0
        rows.append(
            {
                "trial_name": trial_name,
                "slippage_bps_per_side": bps,
                "days_in_episode": int(len(state)),
                "days_with_positive_intended_safe_allocation": int(intended.sum()),
                "days_with_positive_synthetic_safe_balance": int((state["synthetic_safe_account_value"].astype(float) > BROKER_CASH_TOLERANCE).sum()),
                "safe_ledger_persistence_rate": persistence_rate,
                "days_with_unexplained_ordinary_broker_cash": int(unexplained_cash.sum()),
                "average_intended_safe_allocation": float(state["intended_safe_allocation"].mean()),
                "average_synthetic_safe_balance": float(state["synthetic_safe_account_value"].astype(float).mean()),
                "average_broker_cash": float(state["broker_cash"].astype(float).mean()),
                "total_safe_accrual": total_safe_accrual,
                "theoretical_safe_accrual_recomputed": theoretical_safe_accrual,
                "accrual_reconciliation_error": accrual_error,
                "total_safe_to_broker_transfers": float(
                    event_group[event_group["side"].eq("synthetic_safe_to_broker_cash")]["amount"].astype(float).sum()
                )
                if not event_group.empty
                else 0.0,
                "total_broker_to_safe_transfers": float(
                    event_group[event_group["side"].eq("broker_cash_to_synthetic_safe")]["amount"].astype(float).sum()
                )
                if not event_group.empty
                else 0.0,
                "transfers_on_days_without_fills": int(len(transfers_without_fills)),
                "transfer_amount_on_days_without_fills": float(transfers_without_fills["amount"].astype(float).sum())
                if not transfers_without_fills.empty
                else 0.0,
                "maximum_unexplained_end_of_day_broker_cash": float(state.loc[unexplained_cash, "broker_cash"].abs().max())
                if bool(unexplained_cash.any())
                else 0.0,
                "internal_transfer_nav_error": float(state["nav_reconciliation_error"].astype(float).abs().max()),
                "internal_transfer_modeled_cost": float(event_group["internal_transfer_modeled_cost"].astype(float).sum())
                if not event_group.empty
                else 0.0,
            }
        )
    return rows


def floor_breach_rows(
    *,
    daily_rows: list[dict[str, Any]],
    result: BacktestResult,
    trial_name: str,
    slippage: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    state = pd.DataFrame(daily_rows)
    for _, row in state[state["nav_minus_floor"] < 0.0].iterrows():
        event_type = "SCHEDULED_FLOOR_BREACH" if bool(row["scheduled_decision"]) else "INTRAPERIOD_FLOOR_SHORTFALL"
        rows.append(
            {
                "trial_name": trial_name,
                "slippage_bps_per_side": slippage * 10000.0,
                "date": row["date"],
                "event_type": event_type,
                "nav": row["nav"],
                "floor": row["floor"],
                "shortfall": abs(row["nav_minus_floor"]),
                "cash_lock_active": row["cash_locked"],
                "capital_repaired": False,
            }
        )
    if not result.overlay_events.empty:
        for _, event in result.overlay_events[result.overlay_events["reason_code"].eq("cppi_cash_lock")].iterrows():
            rows.append(
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": slippage * 10000.0,
                    "date": str(pd.Timestamp(event["timestamp"]).date()),
                    "event_type": "CASH_LOCK_ACTIVATION",
                    "nav": "",
                    "floor": "",
                    "shortfall": "",
                    "cash_lock_active": True,
                    "capital_repaired": False,
                }
            )
    return rows


def exposure_distribution_row(trial_name: str, slippage: float, daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(daily_rows)
    scheduled = frame[frame["scheduled_decision"].astype(bool)]
    return {
        "trial_name": trial_name,
        "slippage_bps_per_side": slippage * 10000.0,
        "average_actual_risky_exposure": float(frame["actual_risky_exposure"].mean()),
        "maximum_actual_risky_exposure": float(frame["actual_risky_exposure"].max()),
        "average_synthetic_safe_exposure": float(frame["synthetic_safe_exposure"].mean()),
        "average_bil_exposure": float(frame["actual_bil_exposure"].mean()),
        "average_broker_cash_exposure": float(frame["broker_cash_exposure"].mean()),
        "monthly_decision_count": int(len(scheduled)),
        "dynamic_cap_mean_on_scheduled_dates": float(scheduled["diagnostic_risky_cap"].mean()) if not scheduled.empty else np.nan,
        "dynamic_cap_std_on_scheduled_dates": float(scheduled["diagnostic_risky_cap"].std(ddof=0)) if not scheduled.empty else np.nan,
        "dynamic_cap_min_on_scheduled_dates": float(scheduled["diagnostic_risky_cap"].min()) if not scheduled.empty else np.nan,
        "dynamic_cap_max_on_scheduled_dates": float(scheduled["diagnostic_risky_cap"].max()) if not scheduled.empty else np.nan,
        "pct_zero_actual_risky_exposure_days": float((frame["actual_risky_exposure"] <= 1e-12).mean()),
        "pct_full_actual_risky_exposure_days": float((frame["actual_risky_exposure"] >= 1.0 - 1e-12).mean()),
    }


def _fill_count_before_after(result: BacktestResult, cutoff: pd.Timestamp | None) -> tuple[int, int]:
    if result.trades.empty or cutoff is None:
        return 0, 0
    dates: list[pd.Timestamp] = []
    for col in ["entry_date", "exit_date"]:
        if col in result.trades:
            dates.extend(pd.to_datetime(result.trades[col], errors="coerce").dropna().tolist())
    before = sum(pd.Timestamp(date) <= cutoff for date in dates)
    after = sum(pd.Timestamp(date) > cutoff for date in dates)
    return int(before), int(after)


def _pnl_before_after(result: BacktestResult, cutoff: pd.Timestamp | None) -> tuple[float, float]:
    if result.trades.empty or cutoff is None or "pnl" not in result.trades:
        return 0.0, 0.0
    exits = pd.to_datetime(result.trades["exit_date"], errors="coerce")
    pnl = result.trades["pnl"].astype(float)
    return float(pnl[exits <= cutoff].sum()), float(pnl[exits > cutoff].sum())


def _permanent_zero_exposure_date(group: pd.DataFrame) -> str:
    group = group.copy()
    group["date_ts"] = pd.to_datetime(group["date"])
    group = group.sort_values("date_ts").reset_index(drop=True)
    exposure = group["actual_risky_exposure"].astype(float).fillna(0.0)
    for idx in range(len(group)):
        if bool((exposure.iloc[idx:] <= 1e-12).all()):
            return pd.Timestamp(group.loc[idx, "date_ts"]).date().isoformat()
    return ""


def strategy_kill_attribution_rows(
    *,
    results: dict[tuple[float, str], BacktestResult],
    daily_rows_all: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    daily = pd.DataFrame(daily_rows_all)
    rows: list[dict[str, Any]] = []
    for slippage in SLIPPAGES:
        base_result = results[(slippage, "BASE")]
        base_kill_events = base_result.strategy_lifecycle_events[
            base_result.strategy_lifecycle_events["event_type"].eq("strategy_disabled_loss_budget")
        ]
        base_kill_date = (
            pd.Timestamp(base_kill_events.iloc[0]["date"]) if not base_kill_events.empty else None
        )
        for trial_name in TRIAL_NAMES:
            result = results[(slippage, trial_name)]
            lifecycle = result.strategy_lifecycle_events
            kill_events = lifecycle[lifecycle["event_type"].eq("strategy_disabled_loss_budget")] if not lifecycle.empty else pd.DataFrame()
            kill = kill_events.iloc[0] if not kill_events.empty else None
            group = daily[daily["trial_name"].eq(trial_name) & daily["slippage_bps_per_side"].eq(slippage * 10000.0)]
            risky_group = group[group["actual_risky_exposure"].astype(float).fillna(0.0) > 1e-12] if not group.empty else group
            last_risky = str(risky_group["date"].iloc[-1]) if not risky_group.empty else ""
            before_kill_fills, _ = _fill_count_before_after(result, pd.Timestamp(kill["date"]) if kill is not None else None)
            _, after_base_fills = _fill_count_before_after(result, base_kill_date)
            pnl_before_base, pnl_after_base = _pnl_before_after(result, base_kill_date)
            rows.append(
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": slippage * 10000.0,
                    "n4_killed": kill is not None,
                    "kill_decision_date": str(kill["date"]) if kill is not None else "",
                    "reason_code": str(kill["event_reason"]) if kill is not None else "",
                    "nav_at_kill": float(kill["project_equity"]) if kill is not None else np.nan,
                    "strategy_pnl_at_kill": float(kill["strategy_pnl"]) if kill is not None else np.nan,
                    "last_risky_position_date": last_risky,
                    "first_date_after_which_exposure_permanently_zero": _permanent_zero_exposure_date(group)
                    if not group.empty
                    else "",
                    "fills_before_own_kill": before_kill_fills,
                    "corresponding_base_kill_date": base_kill_date.date().isoformat() if base_kill_date is not None else "",
                    "fills_after_corresponding_base_kill_date": after_base_fills,
                    "terminal_pnl_before_base_kill_date": pnl_before_base,
                    "terminal_pnl_after_base_kill_date": pnl_after_base,
                    "risk_control_survival_effect": "",
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return rows
    for bps in sorted(frame["slippage_bps_per_side"].unique()):
        subset = frame[frame["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
        if "DYNAMIC_CPPI" not in subset.index or "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL" not in subset.index:
            continue
        survival_delta = float(
            subset.loc["DYNAMIC_CPPI", "terminal_pnl_after_base_kill_date"]
            - subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "terminal_pnl_after_base_kill_date"]
        )
        for row in rows:
            if row["trial_name"] == "DYNAMIC_CPPI" and row["slippage_bps_per_side"] == bps:
                row["risk_control_survival_effect"] = survival_delta
    return rows


def attribution_rows(metrics: list[dict[str, Any]], kill_attribution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(metrics)
    kill_frame = pd.DataFrame(kill_attribution)
    rows: list[dict[str, Any]] = []
    comparisons = [
        ("SAFE_SLEEVE_SUBSTITUTION", "BASE", "SAFE5_TRANSLATION_CONTROL"),
        ("STATIC_TARGET_CAP_EFFECT", "SAFE5_TRANSLATION_CONTROL", "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"),
        ("DYNAMIC_CPPI_INCREMENTAL_EFFECT", "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "DYNAMIC_CPPI"),
        ("TOTAL_DYNAMIC_MINUS_BASE", "BASE", "DYNAMIC_CPPI"),
    ]
    for bps in sorted(frame["slippage_bps_per_side"].unique()):
        subset = frame[frame["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
        kill_subset = (
            kill_frame[kill_frame["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
            if not kill_frame.empty
            else pd.DataFrame()
        )
        for effect, left, right in comparisons:
            if left not in subset.index or right not in subset.index:
                continue
            before = subset.loc[left]
            after = subset.loc[right]
            before_kill = kill_subset.loc[left] if not kill_subset.empty and left in kill_subset.index else {}
            after_kill = kill_subset.loc[right] if not kill_subset.empty and right in kill_subset.index else {}
            safe_accrual_delta = float(after.get("total_safe_accrual", 0.0) - before.get("total_safe_accrual", 0.0))
            transaction_cost_delta = float(after["corrected_modeled_transaction_cost"] - before["corrected_modeled_transaction_cost"])
            target_delta = float(after.get("average_target_risky_exposure", np.nan) - before.get("average_target_risky_exposure", np.nan))
            realized_delta = float(after["average_risky_exposure"] - before["average_risky_exposure"])
            turnover_delta = float(after["turnover"] - before["turnover"])
            post_base_delta = float(
                float(after_kill.get("terminal_pnl_after_base_kill_date", 0.0) or 0.0)
                - float(before_kill.get("terminal_pnl_after_base_kill_date", 0.0) or 0.0)
            )
            residual = float(after["terminal_nav"] - before["terminal_nav"] - safe_accrual_delta - transaction_cost_delta)
            rows.append(
                {
                    "slippage_bps_per_side": bps,
                    "effect": effect,
                    "comparison": f"{right} - {left}",
                    "terminal_nav_delta": float(after["terminal_nav"] - before["terminal_nav"]),
                    "total_return_delta": float(after["total_return"] - before["total_return"]),
                    "annualized_return_delta": float(after["annualized_return"] - before["annualized_return"]),
                    "annualized_volatility_delta": float(after["annualized_volatility"] - before["annualized_volatility"]),
                    "max_drawdown_delta": float(after["maximum_drawdown"] - before["maximum_drawdown"]),
                    "safe_rate_accrual_delta": safe_accrual_delta,
                    "target_exposure_change": target_delta,
                    "realized_exposure_change": realized_delta,
                    "strategy_kill_timing": f"{left}:{before_kill.get('kill_decision_date', '')}|{right}:{after_kill.get('kill_decision_date', '')}",
                    "post_base_kill_participation": post_base_delta,
                    "turnover_delta": turnover_delta,
                    "transaction_cost_delta": transaction_cost_delta,
                    "residual_trade_path_effect": residual,
                    "average_risky_exposure_delta": realized_delta,
                    "average_synthetic_safe_exposure_delta": float(
                        after["average_synthetic_safe_exposure"] - before["average_synthetic_safe_exposure"]
                    ),
                    "zero_cost_transaction_cost_benefit_claim_allowed": False if float(bps) == 0.0 else "",
                }
            )
    return rows


def classify_dynamic(
    metrics: list[dict[str, Any]],
    kill_attribution: list[dict[str, Any]],
    safe_diagnostics: list[dict[str, Any]],
    accrual_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(metrics)
    kill_frame = pd.DataFrame(kill_attribution)
    diag_frame = pd.DataFrame(safe_diagnostics)
    accrual_frame = pd.DataFrame(accrual_rows)
    rows: list[dict[str, Any]] = []
    for bps in sorted(frame["slippage_bps_per_side"].unique()):
        subset = frame[frame["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
        dynamic = subset.loc["DYNAMIC_CPPI"]
        static = subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"]
        labels: list[str] = []
        safe_ok = True
        diag_group = diag_frame[diag_frame["slippage_bps_per_side"].eq(bps)] if not diag_frame.empty else pd.DataFrame()
        if not diag_group.empty:
            safe_ok = bool((diag_group["safe_ledger_persistence_rate"].astype(float) >= 0.99).all()) and bool(
                (diag_group["maximum_unexplained_end_of_day_broker_cash"].astype(float) <= BROKER_CASH_TOLERANCE).all()
            )
        accrual_group = accrual_frame[accrual_frame["slippage_bps_per_side"].eq(bps)] if not accrual_frame.empty else pd.DataFrame()
        accrual_ok = True if accrual_group.empty else bool(
            (accrual_group["accrual_reconciliation_error"].astype(float).abs() <= ACCRUAL_TOLERANCE).all()
        )
        if not safe_ok or not accrual_ok or bool(dynamic.get("project_stop_hit", False)):
            labels.append("ACCOUNTING_OR_TIMING_INVALID")
        if float(dynamic.get("scheduled_floor_breach_count", 0)) > 0:
            labels.append("FLOOR_BREACH_WITH_SHORTFALL")
        kill_subset = kill_frame[kill_frame["slippage_bps_per_side"].eq(bps)].set_index("trial_name") if not kill_frame.empty else pd.DataFrame()
        if not kill_subset.empty:
            base_killed = bool(kill_subset.loc["BASE", "n4_killed"]) if "BASE" in kill_subset.index else False
            dynamic_killed = bool(kill_subset.loc["DYNAMIC_CPPI", "n4_killed"]) if "DYNAMIC_CPPI" in kill_subset.index else False
            static_killed = (
                bool(kill_subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "n4_killed"])
                if "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL" in kill_subset.index
                else False
            )
            dynamic_post = float(kill_subset.loc["DYNAMIC_CPPI", "terminal_pnl_after_base_kill_date"])
            static_post = float(kill_subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "terminal_pnl_after_base_kill_date"])
            dynamic_pre = float(kill_subset.loc["DYNAMIC_CPPI", "terminal_pnl_before_base_kill_date"])
            static_pre = float(kill_subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "terminal_pnl_before_base_kill_date"])
            survival_delta = dynamic_post - static_post
            pre_delta = dynamic_pre - static_pre
            if base_killed != dynamic_killed or static_killed != dynamic_killed:
                if abs(survival_delta) >= abs(pre_delta):
                    labels.append("RISK_CONTROL_SURVIVAL_DOMINANT")
                else:
                    labels.append("MIXED_DYNAMIC_AND_SURVIVAL_EFFECT")
            elif base_killed == dynamic_killed == static_killed:
                labels.append("ALL_CONTROLS_SHARE_KILL_STATE")
        if (
            abs(float(dynamic["terminal_nav"]) - float(static["terminal_nav"])) > 1.0
            and "ACCOUNTING_OR_TIMING_INVALID" not in labels
            and not any(label.endswith("DOMINANT") or label == "MIXED_DYNAMIC_AND_SURVIVAL_EFFECT" for label in labels)
        ):
            labels.append("DYNAMIC_AND_INCREMENTAL_AFTER_CORRECTION")
        if not labels:
            labels.append("DYNAMIC_NOT_MATERIAL_AFTER_CORRECTION")
        rows.append(
            {
                "slippage_bps_per_side": bps,
                "classification": "|".join(labels),
                "non_informative": any(
                    label in labels
                    for label in [
                        "ACCOUNTING_OR_TIMING_INVALID",
                    ]
                ),
            }
        )
    return rows


def failure_registry_rows(
    *,
    reconciliation_all: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    daily_rows_all: list[dict[str, Any]],
    safe_diagnostics: list[dict[str, Any]],
    accrual_rows: list[dict[str, Any]],
    safe_event_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    recon_frame = pd.DataFrame(reconciliation_all)
    if not recon_frame.empty:
        for bps, group in recon_frame.groupby("slippage_bps_per_side"):
            failures.append(
                {
                    "trial_name": "ALL",
                    "slippage_bps_per_side": bps,
                    "check_id": "NAV_RECONCILIATION",
                    "status": "PASS" if bool(group["nav_reconciles"].all()) else "FAIL",
                    "failure_code": "" if bool(group["nav_reconciles"].all()) else "NAV_RECONCILIATION_ERROR",
                }
            )
    for row in identity_rows:
        failures.append(
            {
                "trial_name": "BASE_IDENTITY",
                "slippage_bps_per_side": row["slippage_bps_per_side"],
                "check_id": "BASE_IDENTITY_EQUIVALENCE",
                "status": "PASS" if row["complete_state_hash_match"] else "FAIL",
                "failure_code": "" if row["complete_state_hash_match"] else "IDENTITY_HASH_MISMATCH",
            }
        )
    diag_frame = pd.DataFrame(safe_diagnostics)
    for _, row in diag_frame.iterrows():
        trial_name = row["trial_name"]
        bps = row["slippage_bps_per_side"]
        persistence_ok = float(row["safe_ledger_persistence_rate"]) >= 0.99
        broker_cash_ok = float(row["maximum_unexplained_end_of_day_broker_cash"]) <= BROKER_CASH_TOLERANCE
        internal_ok = (
            float(row["internal_transfer_modeled_cost"]) <= BROKER_CASH_TOLERANCE
            and float(row["internal_transfer_nav_error"]) <= 1e-5
        )
        failures.extend(
            [
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": bps,
                    "check_id": "SAFE_LEDGER_PERSISTENCE",
                    "status": "PASS" if persistence_ok else "FAIL",
                    "failure_code": "" if persistence_ok else "FAIL_SAFE_LEDGER_NOT_PERSISTENT",
                },
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": bps,
                    "check_id": "RESIDUAL_BROKER_CASH_SWEEP",
                    "status": "PASS" if broker_cash_ok else "FAIL",
                    "failure_code": "" if broker_cash_ok else "FAIL_RESIDUAL_BROKER_CASH_NOT_SWEPT",
                },
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": bps,
                    "check_id": "INTERNAL_TRANSFER_RECONCILIATION",
                    "status": "PASS" if internal_ok else "FAIL",
                    "failure_code": "" if internal_ok else "FAIL_INTERNAL_TRANSFER_RECONCILIATION",
                },
            ]
        )
    accrual_frame = pd.DataFrame(accrual_rows)
    if not accrual_frame.empty:
        for (trial_name, bps), group in accrual_frame.groupby(["trial_name", "slippage_bps_per_side"]):
            ok = bool((group["accrual_reconciliation_error"].astype(float).abs() <= ACCRUAL_TOLERANCE).all())
            failures.append(
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": bps,
                    "check_id": "SAFE_ACCRUAL_FORMULA",
                    "status": "PASS" if ok else "FAIL",
                    "failure_code": "" if ok else "FAIL_SAFE_ACCRUAL_FORMULA",
                }
            )
    event_frame = pd.DataFrame(safe_event_rows)
    if not event_frame.empty:
        release = event_frame[event_frame["side"].eq("synthetic_safe_to_broker_cash")]
        for (trial_name, bps), group in release.groupby(["trial_name", "slippage_bps_per_side"]):
            unnecessary = group[(group["amount"].astype(float) > BROKER_CASH_TOLERANCE) & (group["required_safe_release"].astype(float) <= BROKER_CASH_TOLERANCE)]
            excess = group[
                group["amount"].astype(float)
                > group["required_safe_release"].astype(float) + BROKER_CASH_TOLERANCE
            ]
            failures.extend(
                [
                    {
                        "trial_name": trial_name,
                        "slippage_bps_per_side": bps,
                        "check_id": "UNNECESSARY_SAFE_RELEASE",
                        "status": "PASS" if unnecessary.empty else "FAIL",
                        "failure_code": "" if unnecessary.empty else "FAIL_UNNECESSARY_SAFE_RELEASE",
                    },
                    {
                        "trial_name": trial_name,
                        "slippage_bps_per_side": bps,
                        "check_id": "EXCESS_EXECUTION_FUNDING",
                        "status": "PASS" if excess.empty else "FAIL",
                        "failure_code": "" if excess.empty else "FAIL_EXCESS_EXECUTION_FUNDING",
                    },
                ]
            )
        released_keys = set(zip(release["trial_name"], release["slippage_bps_per_side"])) if not release.empty else set()
        for trial_name in SAFE_LEDGER_TRIALS:
            for bps in sorted(pd.DataFrame(daily_rows_all)["slippage_bps_per_side"].unique()):
                if (trial_name, bps) in released_keys:
                    continue
                failures.extend(
                    [
                        {
                            "trial_name": trial_name,
                            "slippage_bps_per_side": bps,
                            "check_id": "UNNECESSARY_SAFE_RELEASE",
                            "status": "PASS",
                            "failure_code": "",
                        },
                        {
                            "trial_name": trial_name,
                            "slippage_bps_per_side": bps,
                            "check_id": "EXCESS_EXECUTION_FUNDING",
                            "status": "PASS",
                            "failure_code": "",
                        },
                    ]
                )
    daily_frame = pd.DataFrame(daily_rows_all)
    if {"scheduled_decision", "managed_risky_fraction", "base_requested_risky_fraction"} <= set(daily_frame.columns):
        dyn = daily_frame[daily_frame["trial_name"].eq("DYNAMIC_CPPI") & daily_frame["scheduled_decision"].astype(bool)]
        cap_ok = bool(
            (
                pd.to_numeric(dyn["managed_risky_fraction"], errors="coerce").fillna(0.0)
                <= pd.to_numeric(dyn["base_requested_risky_fraction"], errors="coerce").fillna(0.0) + 1e-9
            ).all()
        )
    else:
        cap_ok = True
    failures.append(
        {
            "trial_name": "DYNAMIC_CPPI",
            "slippage_bps_per_side": "ALL",
            "check_id": "CPPI_TARGET_NEVER_EXCEEDS_BASE_REQUEST",
            "status": "PASS" if cap_ok else "FAIL",
            "failure_code": "" if cap_ok else "CPPI_TARGET_EXCEEDED_BASE",
        }
    )
    failures.append(
        {
            "trial_name": "NEGATIVE_CONTROL",
            "slippage_bps_per_side": "ALL",
            "check_id": "NEGATIVE_CONTROL_STATUS",
            "status": "NON_BLOCKING",
            "failure_code": "NO_ELIGIBLE_NEGATIVE_CONTROL_UNSUPPORTED_INTENT_UNIT",
        }
    )
    return failures


def prior_defect_summary() -> dict[str, Any]:
    daily_path = PRIOR_OUT_DIR / "daily_cppi_state.csv"
    events_path = PRIOR_OUT_DIR / "cppi_events.csv"
    if not daily_path.exists() or not events_path.exists():
        return {"prior_package_found": False, "rows": [], "first_bad_release": {}}
    daily = pd.read_csv(daily_path)
    events = pd.read_csv(events_path)
    rows: list[dict[str, Any]] = []
    for trial_name in SAFE_LEDGER_TRIALS:
        group = daily[daily["trial_name"].eq(trial_name) & daily["slippage_bps_per_side"].eq(0.0)]
        accrual = 0.0
        accrual_events = events[
            events["trial_name"].eq(trial_name)
            & events["slippage_bps_per_side"].eq(0.0)
            & events["reason_code"].eq("cppi_safe_account_accrual")
        ]
        for _, event in accrual_events.iterrows():
            accrual += float(json_dict(event.get("state_after")).get("accrued_amount", 0.0) or 0.0)
        rows.append(
            {
                "trial_name": trial_name,
                "daily_observations": int(len(group)),
                "days_safe_positive": int((group["synthetic_safe_account_value"].astype(float) > 1e-9).sum()),
                "safe_positive_pct": float((group["synthetic_safe_account_value"].astype(float) > 1e-9).mean()),
                "average_synthetic_safe_ledger": float(group["synthetic_safe_account_value"].astype(float).mean()),
                "average_broker_cash": float(group["broker_cash"].astype(float).mean()),
                "total_recorded_safe_accrual": accrual,
            }
        )
    transfers = events[
        events["trial_name"].eq("SAFE5_TRANSLATION_CONTROL")
        & events["slippage_bps_per_side"].eq(0.0)
        & events["reason_code"].eq("cppi_safe_account_transfer")
    ].copy()
    first_release: dict[str, Any] = {}
    for _, event in transfers.iterrows():
        proposed = json_dict(event.get("proposed_order"))
        if proposed.get("side") != "synthetic_safe_to_broker_cash":
            continue
        actual = json_dict(event.get("actual_fill"))
        state = json_dict(event.get("state_after"))
        release_date = pd.Timestamp(event["timestamp"]).date().isoformat()
        day_state = daily[
            daily["trial_name"].eq("SAFE5_TRANSLATION_CONTROL")
            & daily["slippage_bps_per_side"].eq(0.0)
            & daily["date"].eq(release_date)
        ]
        next_sweep = transfers[
            pd.to_datetime(transfers["timestamp"], errors="coerce") > pd.Timestamp(event["timestamp"])
        ]
        next_sweep_date = ""
        if not next_sweep.empty:
            for _, sweep_event in next_sweep.iterrows():
                if json_dict(sweep_event.get("proposed_order")).get("side") == "broker_cash_to_synthetic_safe":
                    next_sweep_date = pd.Timestamp(sweep_event["timestamp"]).date().isoformat()
                    break
        first_release = {
            "first_incorrect_release_date": release_date,
            "reason_hook_executed": "pending_safe_release_date remained stale after the first execution sweep",
            "pending_market_order_required_funding": False,
            "amount_released": float(actual.get("amount", 0.0) or 0.0),
            "end_of_day_broker_cash": float(day_state["broker_cash"].iloc[0]) if not day_state.empty else float(state.get("broker_cash", np.nan)),
            "end_of_day_safe_balance": float(day_state["synthetic_safe_account_value"].iloc[0])
            if not day_state.empty
            else float(state.get("safe_account_value", np.nan)),
            "next_date_balance_swept_back": next_sweep_date,
        }
        break
    return {"prior_package_found": True, "rows": rows, "first_bad_release": first_release}


def write_defect_reproduction(summary: dict[str, Any]) -> None:
    lines = [
        "# Defect Reproduction",
        "",
        f"Prior package: `{PRIOR_OUT_DIR.as_posix()}`.",
        "",
        "The prior safe-account implementation passed NAV reconciliation but failed the economic persistence rule.",
        "The stale release hook released the synthetic safe ledger on the day after execution even when no risky purchase required funding.",
        "",
        "## Zero-Cost Prior Evidence",
        "",
    ]
    if not summary.get("prior_package_found"):
        lines.append("Prior package not found; reproduction could not be read from disk.")
    else:
        rows = pd.DataFrame(summary["rows"])
        lines.append(rows.to_markdown(index=False))
        first = summary["first_bad_release"]
        lines.extend(
            [
                "",
                "## First Incorrect Release",
                "",
                f"Date: `{first.get('first_incorrect_release_date', '')}`.",
                f"Reason the hook executed: {first.get('reason_hook_executed', '')}.",
                f"Pending market order required funding: `{first.get('pending_market_order_required_funding', '')}`.",
                f"Amount released: `{first.get('amount_released', '')}`.",
                f"End-of-day broker cash: `{first.get('end_of_day_broker_cash', '')}`.",
                f"End-of-day safe balance: `{first.get('end_of_day_safe_balance', '')}`.",
                f"Next date swept back: `{first.get('next_date_balance_swept_back', '')}`.",
                "",
                f"Rows for Safe5, static-cap, and dynamic CPPI from `{PRIOR_RUN_LABEL}` are marked `{PRIOR_INVALID_REASON}` in `trial_lineage.csv`.",
            ]
        )
    (OUT_DIR / "defect_reproduction.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def trial_lineage_rows(metrics_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics = pd.DataFrame(metrics_rows)
    for _, metric in metrics.iterrows():
        trial_name = metric["trial_name"]
        bps = float(metric["slippage_bps_per_side"])
        prior_status = "PRESERVED_MECHANICAL_CONTROL" if trial_name in {"BASE", "IDENTITY"} else PRIOR_INVALID_REASON
        supersession = "preserved_control_row" if trial_name in {"BASE", "IDENTITY"} else "superseded_by_methodology_correction"
        rows.append(
            {
                "prior_run_label": PRIOR_RUN_LABEL,
                "corrected_run_label": RUN_LABEL,
                "trial_name": trial_name,
                "slippage_bps_per_side": bps,
                "prior_row_status": prior_status,
                "corrected_row_status": "COMPLETED_CORRECTED_ACCOUNTING",
                "supersession_status": supersession,
                "prior_package": PRIOR_OUT_DIR.as_posix(),
                "corrected_package": OUT_DIR.as_posix(),
                "prior_run_id": f"{PRIOR_RUN_LABEL}_{trial_name}_{int(round(bps))}bps",
                "corrected_run_id": f"{RUN_LABEL}_{trial_name}_{int(round(bps))}bps",
            }
        )
    return rows


def write_pre_registered_files(
    *,
    config: dict[str, Any],
    load_result: DataLoadResult,
    episode: dict[str, Any],
) -> dict[str, Any]:
    worktree = tracked_and_untracked_diff_hash()
    source_payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "repo_head_commit": git_commit_hash(ROOT),
        "working_tree_dirty": worktree["dirty"],
        "git_status_porcelain": worktree["status_porcelain"],
        "tracked_and_untracked_diff_hash": worktree["tracked_and_untracked_diff_hash"],
        "tracked_diff_sha256": worktree["tracked_diff_sha256"],
        "untracked_file_hashes": worktree["untracked_file_hashes"],
        "file_hashes": file_hash_inventory(),
        "n4_configuration_hash": n4_config_hash(config),
        "full_config_hash": config_hash(config),
        "cppi_parameter_mapping": CPPI_PARAMS,
        "cppi_parameter_mapping_hash": stable_hash(CPPI_PARAMS),
        "risky_safe_mapping": {"risky_sleeve": RISKY_ASSETS, "safe_cash_proxy_sleeve": SAFE_ASSETS},
        "risky_safe_mapping_hash": stable_hash({"risky": RISKY_ASSETS, "safe": SAFE_ASSETS}),
        "data_file_hashes": data_file_hashes(load_result),
        "selection_reason": "first_deterministically_eligible_cppi_strategy",
        "stage": STAGE,
        "correction_target_run_label": PRIOR_RUN_LABEL,
        "correction_reason": PRIOR_INVALID_REASON,
        "correction_scope": "Safe5, static-cap, and dynamic-CPPI synthetic safe-ledger accounting only",
        "head_alone_is_not_code_version_when_dirty": True,
    }
    write_json(OUT_DIR / "source_and_worktree_hashes.json", source_payload)
    manifest = {
        "run_label": RUN_LABEL,
        "prior_run_label": PRIOR_RUN_LABEL,
        "task_type": "methodology_correction",
        "created_utc": source_payload["created_utc"],
        "repository_head_commit": source_payload["repo_head_commit"],
        "working_tree_dirty": source_payload["working_tree_dirty"],
        "git_status_porcelain": source_payload["git_status_porcelain"],
        "tracked_and_untracked_diff_hash": source_payload["tracked_and_untracked_diff_hash"],
        "tracked_diff_sha256": source_payload["tracked_diff_sha256"],
        "untracked_file_hashes": source_payload["untracked_file_hashes"],
        "source_and_worktree_hashes_sha256": "",
        "n4_configuration_hash": source_payload["n4_configuration_hash"],
        "cppi_parameter_mapping_hash": source_payload["cppi_parameter_mapping_hash"],
        "risky_safe_mapping": source_payload["risky_safe_mapping"],
        "risky_safe_mapping_hash": source_payload["risky_safe_mapping_hash"],
        "episode": episode,
        "selection_reason": "first_deterministically_eligible_cppi_strategy",
        "stage": STAGE,
        "correction_reason": PRIOR_INVALID_REASON,
        "frozen_experiment_unchanged": True,
        "safe_rate_accrual_convention": "continuous_5pct_actual_calendar_days_365_before_transfers_and_executions",
        "negative_control_status": "NO_ELIGIBLE_NEGATIVE_CONTROL_UNSUPPORTED_INTENT_UNIT",
        "not_selected_by_performance": True,
        "not_validation": True,
        "not_robustness": True,
        "not_promotion": True,
        "not_paper_demo_live": True,
    }
    source_path = OUT_DIR / "source_and_worktree_hashes.json"
    manifest["source_and_worktree_hashes_sha256"] = sha256_file(source_path)
    write_json(OUT_DIR / "pre_registered_correction_manifest.json", manifest)
    write_json(OUT_DIR / "episode_definition.json", episode)
    return source_payload


def write_comparison(
    *,
    episode: dict[str, Any],
    metrics: list[dict[str, Any]],
    attribution: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    safe_diagnostics: list[dict[str, Any]],
    kill_attribution: list[dict[str, Any]],
) -> None:
    metrics_frame = pd.DataFrame(metrics)
    attr_frame = pd.DataFrame(attribution)
    id_frame = pd.DataFrame(identity_rows)
    cls_frame = pd.DataFrame(classifications)
    safe_frame = pd.DataFrame(safe_diagnostics)
    kill_frame = pd.DataFrame(kill_attribution)
    summary_cols = [
        "trial_name",
        "slippage_bps_per_side",
        "terminal_nav",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "average_risky_exposure",
        "average_target_risky_exposure",
        "average_synthetic_safe_exposure",
        "average_bil_exposure",
        "total_safe_accrual",
        "minimum_nav_minus_floor_cushion",
        "scheduled_floor_breach_count",
        "cash_lock_date",
    ]
    text = [
        "# CPPI N4 Methodology Correction V1",
        "",
        f"Episode: {episode['episode_start']} decision, {episode['initial_execution_date']} first execution, {episode['final_valuation_date']} final valuation.",
        "",
        f"This methodology correction supersedes invalid safe-ledger rows from `{PRIOR_RUN_LABEL}` because `{PRIOR_INVALID_REASON}`.",
        "It is research-only. It is not tuning, robustness testing, promotion, or paper/demo/live eligibility.",
        "",
        "## Identity",
        "",
        id_frame.to_markdown(index=False) if not id_frame.empty else "No identity rows.",
        "",
        "## Safe Persistence",
        "",
        safe_frame.to_markdown(index=False) if not safe_frame.empty else "No safe diagnostics.",
        "",
        "## Metrics",
        "",
        metrics_frame[summary_cols].to_markdown(index=False),
        "",
        "## Kill Attribution",
        "",
        kill_frame.to_markdown(index=False) if not kill_frame.empty else "No kill attribution rows.",
        "",
        "## Attribution",
        "",
        attr_frame.to_markdown(index=False) if not attr_frame.empty else "No attribution rows.",
        "",
        "## Non-Degeneracy",
        "",
        cls_frame.to_markdown(index=False) if not cls_frame.empty else "No classifications.",
        "",
        "Dynamic CPPI is not described as alpha. `DYNAMIC_CPPI - BASE` is reported as a total difference with survival effects separated from allocation and safe-account effects.",
    ]
    (OUT_DIR / "comparison.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def run_test_commands() -> tuple[str, bool, list[dict[str, Any]]]:
    chunks: list[str] = []
    rows: list[dict[str, Any]] = []
    passed_all = True
    for command in TEST_COMMANDS:
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        passed = result.returncode == 0
        passed_all = passed_all and passed
        printable = " ".join(command)
        rows.append({"command": printable, "returncode": result.returncode, "passed": passed})
        chunks.append(f"$ {printable}\nreturncode={result.returncode}\n{result.stdout}{result.stderr}".rstrip())
    return "\n\n".join(chunks) + "\n", passed_all, rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_config = load_config(ROOT / "config.yaml")
    config = n4_only_config(base_config)
    load_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(load_result.data)
    episode = freeze_episode(config, prepared, load_result)

    source_payload = write_pre_registered_files(config=config, load_result=load_result, episode=episode)

    trial_registry: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    daily_rows_all: list[dict[str, Any]] = []
    events_rows: list[dict[str, Any]] = []
    safe_event_rows_all: list[dict[str, Any]] = []
    reconciliation_all: list[dict[str, Any]] = []
    breach_all: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    results: dict[tuple[float, str], BacktestResult] = {}
    base_hash = n4_config_hash(config)
    trial_names = TRIAL_NAMES

    for slippage in SLIPPAGES:
        for trial_name in trial_names:
            overlay = overlay_for_trial(trial_name, episode)
            result = run_trial(
                prepared=prepared,
                config=config,
                episode=episode,
                trial_name=trial_name,
                slippage=slippage,
                overlay=overlay,
                base_strategy_hash=base_hash,
            )
            results[(slippage, trial_name)] = result
            daily_rows = daily_state_rows(
                result=result,
                prepared=prepared,
                episode=episode,
                trial_name=trial_name,
                slippage=slippage,
            )
            daily_rows_all.extend(daily_rows)
            metrics_rows.append(metric_row(result=result, daily_rows=daily_rows, episode=episode, trial_name=trial_name, slippage=slippage))
            reconciliation_all.extend(reconciliation_rows(result=result, daily_rows=daily_rows, trial_name=trial_name, slippage=slippage))
            if trial_name in SAFE_LEDGER_TRIALS:
                safe_event_rows_all.extend(safe_event_detail_rows(result=result, trial_name=trial_name, slippage=slippage))
            breach_all.extend(floor_breach_rows(daily_rows=daily_rows, result=result, trial_name=trial_name, slippage=slippage))
            exposure_rows.append(exposure_distribution_row(trial_name, slippage, daily_rows))
            if not result.overlay_events.empty:
                events = result.overlay_events.copy()
                events.insert(0, "trial_name", trial_name)
                events.insert(1, "slippage_bps_per_side", slippage * 10000.0)
                events_rows.extend(events.to_dict("records"))
            trial_registry.append(
                {
                    "trial_name": trial_name,
                    "slippage_bps_per_side": slippage * 10000.0,
                    "overlay_id": overlay.overlay_id if overlay is not None else "BASE",
                    "status": "completed",
                    "start": result.metadata.get("effective_first_trading_date", ""),
                    "end": result.metadata.get("effective_last_trading_date", ""),
                    "episode_id": episode["episode_id"],
                    "no_other_overlay_active": True,
                }
            )

        base_result = results[(slippage, "BASE")]
        identity_result = results[(slippage, "IDENTITY")]
        base_result_hash = result_hashes(base_result)
        identity_result_hash = result_hashes(identity_result)
        identity_rows.append(
            {
                "slippage_bps_per_side": slippage * 10000.0,
                "base_complete_state_hash": base_result_hash["complete_state_hash"],
                "identity_complete_state_hash": identity_result_hash["complete_state_hash"],
                "complete_state_hash_match": base_result_hash["complete_state_hash"] == identity_result_hash["complete_state_hash"],
            }
        )

    safe_accrual_rows = safe_accrual_recalculation_rows(
        daily_rows_all=daily_rows_all,
        safe_event_rows_all=safe_event_rows_all,
    )
    safe_diagnostics = safe_persistence_diagnostic_rows(
        daily_rows_all=daily_rows_all,
        safe_event_rows_all=safe_event_rows_all,
        accrual_rows=safe_accrual_rows,
        results=results,
    )
    kill_attribution = strategy_kill_attribution_rows(results=results, daily_rows_all=daily_rows_all)
    attribution = attribution_rows(metrics_rows, kill_attribution)
    classifications = classify_dynamic(metrics_rows, kill_attribution, safe_diagnostics, safe_accrual_rows)
    failures = failure_registry_rows(
        reconciliation_all=reconciliation_all,
        identity_rows=identity_rows,
        daily_rows_all=daily_rows_all,
        safe_diagnostics=safe_diagnostics,
        accrual_rows=safe_accrual_rows,
        safe_event_rows=safe_event_rows_all,
    )
    defect_summary = prior_defect_summary()
    lineage = trial_lineage_rows(metrics_rows)

    write_defect_reproduction(defect_summary)
    write_csv(OUT_DIR / "trial_lineage.csv", lineage)
    write_csv(OUT_DIR / "trial_registry.csv", trial_registry)
    write_csv(OUT_DIR / "identity_equivalence.csv", identity_rows)
    write_csv(OUT_DIR / "metrics.csv", metrics_rows)
    pd.DataFrame(daily_rows_all).to_csv(OUT_DIR / "daily_cppi_state.csv", index=False)
    pd.DataFrame(events_rows).to_csv(OUT_DIR / "cppi_events.csv", index=False)
    pd.DataFrame(reconciliation_all).to_csv(OUT_DIR / "safe_account_reconciliation.csv", index=False)
    pd.DataFrame(safe_diagnostics).to_csv(OUT_DIR / "safe_persistence_diagnostics.csv", index=False)
    pd.DataFrame(safe_accrual_rows).to_csv(OUT_DIR / "safe_accrual_recalculation.csv", index=False)
    pd.DataFrame(kill_attribution).to_csv(OUT_DIR / "strategy_kill_attribution.csv", index=False)
    pd.DataFrame(breach_all).to_csv(OUT_DIR / "floor_breach_log.csv", index=False)
    write_csv(OUT_DIR / "exposure_distribution.csv", exposure_rows)
    write_csv(OUT_DIR / "attribution_decomposition.csv", attribution)
    write_csv(OUT_DIR / "failure_registry.csv", failures)
    write_comparison(
        episode=episode,
        metrics=metrics_rows,
        attribution=attribution,
        identity_rows=identity_rows,
        classifications=classifications,
        safe_diagnostics=safe_diagnostics,
        kill_attribution=kill_attribution,
    )
    (OUT_DIR / "source_of_truth_update.md").write_text(
        "\n".join(
            [
                "# Source Of Truth Update",
                "",
                f"Experiment: `{RUN_LABEL}`",
                "",
                f"Stage: `{STAGE}`",
                "",
                f"Supersedes only invalid Safe5/static/dynamic rows from `{PRIOR_RUN_LABEL}` marked `{PRIOR_INVALID_REASON}`.",
                "",
                f"Frozen episode: `{episode['episode_start']}` through `{episode['final_valuation_date']}`.",
                "",
                "Frozen mapping: risky sleeve `GLD|IEF|SPY|TLT`; safe/cash-proxy sleeve `BIL`.",
                "",
                "Synthetic safe ledger convention: continuous 5% accrual over actual calendar days / 365.0, before current-day transfers and executions; end-of-day broker cash is swept back to the safe ledger.",
                "",
                "Negative-control status: `NO_ELIGIBLE_NEGATIVE_CONTROL_UNSUPPORTED_INTENT_UNIT`.",
                "",
                "No tuning, new episode, new strategy, overlay combination, validation, robustness testing, promotion, paper/demo eligibility, broker path, or live action was performed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    test_text, tests_passed, test_rows = run_test_commands()
    (OUT_DIR / "test_results.txt").write_text(test_text, encoding="utf-8")
    manifest_path = OUT_DIR / "pre_registered_correction_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "completed_utc": datetime.now(UTC).isoformat(),
            "tests_passed": tests_passed,
            "test_commands": test_rows,
            "artifact_hashes": {
                path.name: sha256_file(path)
                for path in sorted(OUT_DIR.iterdir())
                if path.is_file() and path.name != "pre_registered_correction_manifest.json"
            },
            "source_payload_hash_after_run": stable_hash(source_payload),
        }
    )
    write_json(manifest_path, manifest)
    if not tests_passed:
        raise SystemExit("Experiment artifacts were generated, but verification tests failed.")


if __name__ == "__main__":
    main()
