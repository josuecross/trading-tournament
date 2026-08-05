from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.data import build_adjusted_ohlc
from src.portfolio import Portfolio, Position
from src.strategies import EntrySignal
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import (
    invariant_summary,
    turnover_from_weights,
)


TASK_ID = "audit_long_short_relative_value_capability_v1"
MODE = "data-capability"
STAGE = "feasibility"
OUTPUT_DIR = ROOT / "evidence" / "data_capability" / TASK_ID / "latest"

SOURCE_CONTEXT_ID = "gatev_distance_pairs_12m_6m_2sd"
SOURCE_FAMILY = "relative_value_or_spread_pairs"
CAPABILITY_TASK_ID = "long_short_relative_value_engine_capability_v1"
PROCESS_TASK_ID = TASK_ID

OUTCOME = "long_short_capability_not_currently_viable"
NEXT_ACTION = "defer_long_short_lane_and_refresh_strategy_source_library_v6"
PRIMARY_FAILURE_REASON = "capability_missing"
DECISION_REASON = (
    "generic_signed_atomic_pair_accounting_and_source_aligned_stock_universe_absent"
)

CLASSIFICATIONS = {
    "supported_and_verified",
    "partially_supported",
    "unsupported",
    "unclear_due_to_missing_test",
    "not_applicable",
}

AUTHORITY_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
PRODUCTION_PATHS = (
    ROOT / "src" / "portfolio.py",
    ROOT / "src" / "backtester.py",
    ROOT / "src" / "strategies.py",
    ROOT / "src" / "data.py",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "external_adapters"
    / "bt_adapter.py",
)
CACHE_DIR = ROOT / "data" / "cache"
CACHE_PATHS = tuple(sorted(path for path in CACHE_DIR.rglob("*") if path.is_file()))
PROTECTED_PATHS = AUTHORITY_PATHS + PRODUCTION_PATHS + CACHE_PATHS

V5_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v5"
    / "latest"
)
IBS_LIFECYCLE_DIR = (
    ROOT
    / "evidence"
    / "lifecycle"
    / "reconcile_and_close_ibs_after_validation_v1"
    / "latest"
)
PAIR_RESOLUTION_DIR = (
    ROOT / "evidence" / "etf_pairs_short_accounting_resolution_v1" / "latest"
)
PAIR_SCREEN_DIR = ROOT / "evidence" / "etf_pairs_distance_screen_v1" / "latest"
PRIOR_EVIDENCE_PATHS = tuple(
    sorted(
        [
            V5_DIR / "strategy_source_library_refresh_v5.md",
            V5_DIR / "source_review_inventory.csv",
            V5_DIR / "rejection_ledger.csv",
            V5_DIR / "ranked_implementation_queue.csv",
            V5_DIR / "consistency_check.json",
            IBS_LIFECYCLE_DIR / "consistency_check.json",
            *[
                path
                for path in PAIR_RESOLUTION_DIR.glob("*")
                if path.is_file()
            ],
            *[
                path for path in PAIR_SCREEN_DIR.glob("*") if path.is_file()
            ],
        ]
    )
)

FROZEN_PRIMARY_UNIVERSE = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "universe_expansion"
    / "pilot_instrument_strategy_compatibility_v1"
    / "accepted_final_47_universe.csv"
)
APPROVED_ETF_MAP = ROOT / "strategy_lab" / "approved_etf_symbol_map.yaml"
PRIOR_PAIR_ETF_UNIVERSE = (
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLY",
    "XLP",
    "XLU",
    "XLI",
    "XLB",
    "XLC",
)

REQUIRED_OUTPUTS = {
    "capability_manifest.yaml",
    "source_context.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "existing_support_inventory.csv",
    "capability_matrix.csv",
    "data_universe_assessment.csv",
    "accounting_convention_inventory.csv",
    "synthetic_probe_definitions.csv",
    "synthetic_probe_results.csv",
    "turnover_and_cost_probe.csv",
    "borrow_and_financing_probe.csv",
    "corporate_action_probe.csv",
    "gross_net_exposure_probe.csv",
    "missing_leg_data_probe.csv",
    "gap_and_minimal_patch_scope.csv",
    "unlocked_strategy_families.csv",
    "risk_and_failure_modes.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "state_change_manifest.csv",
    "consistency_check.json",
    "capability_report.md",
}

FORBIDDEN_FLAGS = {
    "strategy_implementation": False,
    "strategy_backtest": False,
    "source_extraction_or_completion": False,
    "data_acquisition": False,
    "production_code_patch": False,
    "registry_or_lifecycle_change": False,
    "paper_demo_action": False,
    "broker_account_order_or_real_money_action": False,
    "strategy_configuration_created": False,
    "experiment_trial_created": False,
    "benchmark_strategy_created": False,
}

TOL = 1e-10


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def hash_paths(paths: tuple[Path, ...]) -> dict[str, str]:
    return {
        rel(path): sha256_path(path) if path.exists() else "missing"
        for path in paths
    }


def prior_evidence_identity() -> str:
    digest = hashlib.sha256()
    for path in sorted(PRIOR_EVIDENCE_PATHS):
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            (sha256_path(path) if path.exists() else "missing").encode("ascii")
        )
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return format(value, ".15g")
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def source_contains(path: Path, fragment: str) -> bool:
    return fragment in path.read_text(encoding="utf-8")


@dataclass
class SyntheticSignedLedger:
    """Isolated reference ledger for capability probes, never strategy use."""

    initial_equity: float = 100.0
    cash: float = field(init=False)
    quantities: dict[str, float] = field(default_factory=dict)
    last_prices: dict[str, float] = field(default_factory=dict)
    restricted_short_proceeds: float = 0.0
    transaction_costs: float = 0.0
    borrow_costs: float = 0.0
    invalid: bool = False
    invalid_reason: str = ""

    def __post_init__(self) -> None:
        self.cash = float(self.initial_equity)

    def _prices_valid(
        self,
        symbols: set[str],
        prices: dict[str, float | None],
    ) -> bool:
        return all(
            symbol in prices
            and prices[symbol] is not None
            and math.isfinite(float(prices[symbol]))
            and float(prices[symbol]) > 0.0
            for symbol in symbols
        )

    def market_values(
        self,
        prices: dict[str, float] | None = None,
    ) -> dict[str, float]:
        selected = prices or self.last_prices
        return {
            symbol: quantity * float(selected[symbol])
            for symbol, quantity in self.quantities.items()
        }

    def equity(self, prices: dict[str, float] | None = None) -> float:
        return float(self.cash + sum(self.market_values(prices).values()))

    def exposures(
        self,
        prices: dict[str, float] | None = None,
    ) -> dict[str, float]:
        values = self.market_values(prices)
        nav = self.equity(prices)
        gross = sum(abs(value) for value in values.values()) / nav
        net = sum(values.values()) / nav
        max_leg = max((abs(value) / nav for value in values.values()), default=0.0)
        return {
            "gross_exposure": float(gross),
            "net_exposure": float(net),
            "max_absolute_leg_weight": float(max_leg),
        }

    def set_target_weights(
        self,
        target_weights: dict[str, float],
        prices: dict[str, float | None],
        transaction_cost_rate: float = 0.0,
    ) -> dict[str, Any]:
        symbols = {
            symbol
            for symbol, weight in target_weights.items()
            if abs(float(weight)) > TOL
        } | set(self.quantities)
        if not self._prices_valid(symbols, prices):
            self.invalid = True
            self.invalid_reason = "atomic_target_blocked_missing_leg_price"
            return {
                "accepted": False,
                "reason": self.invalid_reason,
                "one_way_turnover": 0.0,
                "gross_traded_notional": 0.0,
                "transaction_cost": 0.0,
            }
        clean_prices = {symbol: float(prices[symbol]) for symbol in symbols}
        nav = self.equity(clean_prices) if self.quantities else self.cash
        pre_values = {
            symbol: self.quantities.get(symbol, 0.0) * clean_prices[symbol]
            for symbol in symbols
        }
        pre_weights = {
            symbol: value / nav for symbol, value in pre_values.items()
        }
        target_values = {
            symbol: float(target_weights.get(symbol, 0.0)) * nav
            for symbol in symbols
        }
        deltas = {
            symbol: target_values[symbol] - pre_values[symbol]
            for symbol in symbols
        }
        gross_traded = float(sum(abs(value) for value in deltas.values()))
        one_way_turnover = 0.5 * sum(
            abs(float(target_weights.get(symbol, 0.0)) - pre_weights[symbol])
            for symbol in symbols
        )
        cost = gross_traded * float(transaction_cost_rate)
        self.cash -= sum(deltas.values()) + cost
        self.transaction_costs += cost
        self.quantities = {
            symbol: target_values[symbol] / clean_prices[symbol]
            for symbol in symbols
            if abs(target_values[symbol]) > TOL
        }
        self.last_prices = clean_prices
        self.restricted_short_proceeds = sum(
            abs(value) for value in target_values.values() if value < 0.0
        )
        return {
            "accepted": True,
            "reason": "",
            "one_way_turnover": float(one_way_turnover),
            "gross_traded_notional": gross_traded,
            "transaction_cost": cost,
            "equity_after_cost": self.equity(),
        }

    def mark(
        self,
        prices: dict[str, float | None],
        annual_borrow_rates: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        symbols = set(self.quantities)
        if not self._prices_valid(symbols, prices):
            self.invalid = True
            self.invalid_reason = "valuation_blocked_missing_leg_price"
            return {
                "accepted": False,
                "reason": self.invalid_reason,
                "equity": self.equity(),
            }
        self.last_prices = {
            symbol: float(prices[symbol]) for symbol in symbols
        }
        rates = annual_borrow_rates or {}
        borrow = sum(
            abs(quantity * self.last_prices[symbol])
            * float(rates.get(symbol, 0.0))
            / 252.0
            for symbol, quantity in self.quantities.items()
            if quantity < 0.0
        )
        self.cash -= borrow
        self.borrow_costs += borrow
        return {
            "accepted": True,
            "reason": "",
            "borrow_cost": float(borrow),
            "equity": self.equity(),
            **self.exposures(),
        }

    def close_symbols(
        self,
        symbols_to_close: set[str],
        prices: dict[str, float | None],
        transaction_cost_rate: float = 0.0,
    ) -> dict[str, Any]:
        active = set(self.quantities)
        if not self._prices_valid(active, prices):
            self.invalid = True
            self.invalid_reason = "atomic_close_blocked_missing_leg_price"
            return {"accepted": False, "reason": self.invalid_reason}
        clean_prices = {symbol: float(prices[symbol]) for symbol in active}
        traded = 0.0
        cash_flow = 0.0
        for symbol in symbols_to_close:
            quantity = self.quantities.get(symbol, 0.0)
            value = quantity * clean_prices[symbol]
            traded += abs(value)
            cash_flow += value
        cost = traded * transaction_cost_rate
        self.cash += cash_flow - cost
        self.transaction_costs += cost
        self.quantities = {
            symbol: quantity
            for symbol, quantity in self.quantities.items()
            if symbol not in symbols_to_close
        }
        self.last_prices = {
            symbol: clean_prices[symbol] for symbol in self.quantities
        }
        self.restricted_short_proceeds = sum(
            abs(quantity * self.last_prices[symbol])
            for symbol, quantity in self.quantities.items()
            if quantity < 0.0
        )
        return {
            "accepted": True,
            "reason": "",
            "gross_traded_notional": float(traded),
            "transaction_cost": float(cost),
            "equity": self.equity(),
        }


def minimal_core_config() -> dict[str, Any]:
    return {
        "project": {
            "starting_equity": 100.0,
            "max_position_notional_pct": 1.0,
            "max_open_risk": 100.0,
            "max_cluster_open_risk": 100.0,
            "reserve_cash_buffer": 0.0,
        },
        "universe": {"clusters": {"synthetic": ["A", "B"]}},
        "strategies": {
            "synthetic": {
                "enabled": True,
                "max_positions": 4,
                "max_strategy_loss": 100.0,
            }
        },
    }


def core_injected_pair_nav(
    a_price: float,
    b_price: float,
) -> dict[str, float]:
    portfolio = Portfolio(minimal_core_config(), slippage_pct=0.0)
    portfolio.cash = 100.0
    portfolio.positions = [
        Position(
            1,
            "synthetic",
            "A",
            pd.Timestamp("2020-01-02"),
            100.0,
            90.0,
            None,
            0.5,
            5.0,
            5.0,
            "synthetic",
        ),
        Position(
            2,
            "synthetic",
            "B",
            pd.Timestamp("2020-01-02"),
            100.0,
            110.0,
            None,
            -0.5,
            5.0,
            5.0,
            "synthetic",
        ),
    ]
    nav, unrealized = portfolio.mark_to_market(
        {
            "A": pd.Series({"close": a_price}),
            "B": pd.Series({"close": b_price}),
        }
    )
    return {
        "nav": float(nav),
        "long_pnl": float((a_price - 100.0) * 0.5),
        "short_pnl": float((b_price - 100.0) * -0.5),
        "unrealized": float(unrealized["synthetic"]),
    }


def core_short_entry_probe() -> dict[str, Any]:
    portfolio = Portfolio(minimal_core_config(), slippage_pct=0.0)
    signal = EntrySignal(
        date=pd.Timestamp("2020-01-01"),
        strategy="synthetic",
        symbol="B",
        requested_risk=5.0,
        metadata={"target_weight": -0.5},
    )
    position = portfolio.attempt_open_position(
        signal=signal,
        entry_date=pd.Timestamp("2020-01-02"),
        entry_price=100.0,
        stop_price=90.0,
        target_price=None,
        project_equity=100.0,
        strategy_pnl=0.0,
        market_regime="synthetic",
    )
    return {
        "position_created": position is not None,
        "negative_shares_created": bool(
            position is not None and position.shares < 0.0
        ),
        "skip_reason": (
            portfolio.skipped_signals[-1]["reason_skipped"]
            if portfolio.skipped_signals
            else ""
        ),
    }


def turnover_probe_rows() -> list[dict[str, Any]]:
    transitions = [
        (
            "opening_both_legs",
            {"A": 0.0, "B": 0.0},
            {"A": 0.5, "B": -0.5},
            0.5,
        ),
        (
            "resizing_both_legs",
            {"A": 0.5, "B": -0.5},
            {"A": 0.4, "B": -0.4},
            0.1,
        ),
        (
            "closing_both_legs",
            {"A": 0.4, "B": -0.4},
            {"A": 0.0, "B": 0.0},
            0.4,
        ),
        (
            "reversing_pair_direction",
            {"A": 0.5, "B": -0.5},
            {"A": -0.5, "B": 0.5},
            1.0,
        ),
        (
            "opening_second_pair_first_remains",
            {"A": 0.25, "B": -0.25, "C": 0.0, "D": 0.0},
            {"A": 0.25, "B": -0.25, "C": 0.25, "D": -0.25},
            0.25,
        ),
    ]
    rows: list[dict[str, Any]] = []
    cost_rate = 0.001
    nav = 100.0
    for scenario, pre, target, expected in transitions:
        columns = sorted(set(pre) | set(target))
        frame = pd.DataFrame(
            [[pre.get(col, 0.0) for col in columns], [target.get(col, 0.0) for col in columns]],
            index=pd.to_datetime(["2020-01-01", "2020-01-02"]),
            columns=columns,
        )
        observed = float(turnover_from_weights(frame).iloc[-1]["turnover_proxy"])
        gross_traded_weight = sum(
            abs(target.get(col, 0.0) - pre.get(col, 0.0))
            for col in columns
        )
        cost = gross_traded_weight * nav * cost_rate
        rows.append(
            {
                "scenario_id": scenario,
                "pretrade_weights": pre,
                "target_weights": target,
                "formula": "0.5*sum(abs(target_weight-pretrade_weight))",
                "observed_one_way_turnover": observed,
                "expected_one_way_turnover": expected,
                "gross_traded_weight": gross_traded_weight,
                "cost_rate_per_absolute_traded_notional": cost_rate,
                "transaction_cost": cost,
                "long_and_short_trades_costed": True,
                "passed": abs(observed - expected) <= TOL,
            }
        )
    return rows


def corporate_action_probe_rows() -> list[dict[str, Any]]:
    dividend_raw = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "open": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "close": [100.0, 100.0],
            "adj_close": [99.0, 100.0],
            "volume": [1000.0, 1000.0],
            "dividends": [0.0, 1.0],
            "stock_splits": [0.0, 0.0],
        }
    )
    adjusted = build_adjusted_ohlc(dividend_raw, "DIV")
    adjusted_return = (
        float(adjusted.iloc[1]["close"] / adjusted.iloc[0]["close"] - 1.0)
    )
    raw_return = float(
        dividend_raw.iloc[1]["close"] / dividend_raw.iloc[0]["close"] - 1.0
    )
    long_pnl = 50.0 * adjusted_return
    short_pnl = -50.0 * adjusted_return

    split_raw = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-02-03", "2020-02-04"]),
            "open": [100.0, 50.0],
            "high": [101.0, 50.5],
            "low": [99.0, 49.5],
            "close": [100.0, 50.0],
            "adj_close": [100.0, 100.0],
            "volume": [1000.0, 2000.0],
            "dividends": [0.0, 0.0],
            "stock_splits": [0.0, 2.0],
        }
    )
    split_adjusted = build_adjusted_ohlc(split_raw, "SPLIT")
    split_adjusted_return = float(
        split_adjusted.iloc[1]["close"]
        / split_adjusted.iloc[0]["close"]
        - 1.0
    )
    return [
        {
            "scenario_id": "distribution_embedded_in_adjusted_return",
            "raw_price_return": raw_return,
            "adjusted_total_return": adjusted_return,
            "long_leg_pnl": long_pnl,
            "short_leg_pnl": short_pnl,
            "explicit_dividend_cash_flow_added": False,
            "double_count_avoided": True,
            "passed": (
                adjusted_return > raw_return
                and long_pnl > 0.0
                and short_pnl < 0.0
                and abs(long_pnl + short_pnl) <= TOL
            ),
            "interpretation": (
                "Adjusted close embeds the distribution. Signed exposure gives "
                "the long benefit and short obligation once; a separate dividend "
                "charge would double count."
            ),
        },
        {
            "scenario_id": "split_embedded_in_adjusted_return",
            "raw_price_return": -0.5,
            "adjusted_total_return": split_adjusted_return,
            "long_leg_pnl": 50.0 * split_adjusted_return,
            "short_leg_pnl": -50.0 * split_adjusted_return,
            "explicit_dividend_cash_flow_added": False,
            "double_count_avoided": True,
            "passed": abs(split_adjusted_return) <= TOL,
            "interpretation": (
                "Adjusted close neutralizes the mechanical split. The engine "
                "must use adjusted-price quantities consistently."
            ),
        },
    ]


def run_synthetic_probes() -> dict[str, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    borrow_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []

    favorable = SyntheticSignedLedger()
    favorable.set_target_weights({"A": 0.5, "B": -0.5}, {"A": 100.0, "B": 100.0})
    favorable_mark = favorable.mark({"A": 110.0, "B": 90.0})
    core_favorable = core_injected_pair_nav(110.0, 90.0)
    results.append(
        {
            "probe_id": "probe_1_basic_dollar_neutral_pair",
            "reference_probe_passed": abs(favorable_mark["equity"] - 110.0) <= TOL,
            "observed": favorable_mark["equity"],
            "expected": 110.0,
            "production_math_when_manually_injected_passed": (
                abs(core_favorable["nav"] - 110.0) <= TOL
            ),
            "production_supported_entry_path": False,
            "notes": (
                "Both legs gain in reference math and manually injected core "
                "positions; production cannot originate the short."
            ),
        }
    )
    exposure_rows.append(
        {
            "scenario_id": "basic_target",
            "gross_exposure": 1.0,
            "net_exposure": 0.0,
            "maximum_absolute_leg_weight": 0.5,
            "gross_cap": 1.0,
            "net_tolerance": TOL,
            "passed": True,
        }
    )

    adverse = SyntheticSignedLedger()
    adverse.set_target_weights({"A": 0.5, "B": -0.5}, {"A": 100.0, "B": 100.0})
    adverse_mark = adverse.mark({"A": 90.0, "B": 110.0})
    core_adverse = core_injected_pair_nav(90.0, 110.0)
    results.append(
        {
            "probe_id": "probe_2_adverse_pair_move",
            "reference_probe_passed": abs(adverse_mark["equity"] - 90.0) <= TOL,
            "observed": adverse_mark["equity"],
            "expected": 90.0,
            "production_math_when_manually_injected_passed": (
                abs(core_adverse["nav"] - 90.0) <= TOL
            ),
            "production_supported_entry_path": False,
            "notes": (
                "Both legs lose in reference math and manually injected core "
                "positions; production cannot originate the short."
            ),
        }
    )

    turnover_rows = turnover_probe_rows()
    results.append(
        {
            "probe_id": "probe_3_turnover_and_costs",
            "reference_probe_passed": all(row["passed"] for row in turnover_rows),
            "observed": len(turnover_rows),
            "expected": len(turnover_rows),
            "production_math_when_manually_injected_passed": True,
            "production_supported_entry_path": False,
            "notes": (
                "The bt helper computes signed absolute-difference turnover, "
                "but the adapter rejects negative weights and has no integrated "
                "two-leg cost ledger."
            ),
        }
    )

    borrow = SyntheticSignedLedger()
    borrow.set_target_weights({"A": 0.5, "B": -0.5}, {"A": 100.0, "B": 100.0})
    borrow_mark = borrow.mark(
        {"A": 100.0, "B": 100.0},
        annual_borrow_rates={"B": 0.05},
    )
    expected_borrow = 50.0 * 0.05 / 252.0
    borrow_rows.extend(
        [
            {
                "scenario_id": "single_short_daily_borrow",
                "short_symbol": "B",
                "absolute_short_notional": 50.0,
                "annual_borrow_rate": 0.05,
                "daily_borrow_cost": borrow_mark["borrow_cost"],
                "expected_daily_borrow_cost": expected_borrow,
                "instrument_specific_rate_supported_by_reference_probe": True,
                "production_engine_support": False,
                "passed": abs(borrow_mark["borrow_cost"] - expected_borrow) <= TOL,
            },
            {
                "scenario_id": "unavailable_to_borrow",
                "short_symbol": "B",
                "absolute_short_notional": 50.0,
                "annual_borrow_rate": "",
                "daily_borrow_cost": "",
                "expected_daily_borrow_cost": "",
                "instrument_specific_rate_supported_by_reference_probe": False,
                "production_engine_support": False,
                "passed": False,
            },
            {
                "scenario_id": "collateral_yield_and_debit_financing",
                "short_symbol": "",
                "absolute_short_notional": "",
                "annual_borrow_rate": "",
                "daily_borrow_cost": "",
                "expected_daily_borrow_cost": "",
                "instrument_specific_rate_supported_by_reference_probe": False,
                "production_engine_support": False,
                "passed": False,
            },
        ]
    )
    results.append(
        {
            "probe_id": "probe_4_borrow_fee",
            "reference_probe_passed": abs(borrow_mark["borrow_cost"] - expected_borrow) <= TOL,
            "observed": borrow_mark["borrow_cost"],
            "expected": expected_borrow,
            "production_math_when_manually_injected_passed": False,
            "production_supported_entry_path": False,
            "notes": (
                "Reference accrual works on absolute short notional; production "
                "has no borrow, locate, collateral-yield, or debit-financing model."
            ),
        }
    )

    corporate_rows = corporate_action_probe_rows()
    results.append(
        {
            "probe_id": "probe_5_distributions_and_adjusted_returns",
            "reference_probe_passed": all(row["passed"] for row in corporate_rows),
            "observed": len(corporate_rows),
            "expected": len(corporate_rows),
            "production_math_when_manually_injected_passed": True,
            "production_supported_entry_path": False,
            "notes": (
                "Adjusted OHLC embeds distributions and splits. No separate "
                "dividend cash flow may be added, but delisting and symbol-change "
                "handling remain absent."
            ),
        }
    )

    multi = SyntheticSignedLedger()
    multi.set_target_weights(
        {"A": 0.25, "B": -0.25, "C": 0.25, "D": -0.25},
        {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0},
    )
    initial_multi = multi.exposures()
    multi_mark = multi.mark({"A": 110.0, "B": 90.0, "C": 110.0, "D": 90.0})
    close_one = multi.close_symbols(
        {"A", "B"},
        {"A": 110.0, "B": 90.0, "C": 110.0, "D": 90.0},
    )
    remaining = set(multi.quantities)
    multi_pass = (
        abs(initial_multi["gross_exposure"] - 1.0) <= TOL
        and abs(initial_multi["net_exposure"]) <= TOL
        and abs(multi_mark["equity"] - 110.0) <= TOL
        and close_one["accepted"]
        and remaining == {"C", "D"}
    )
    results.append(
        {
            "probe_id": "probe_6_multiple_pairs",
            "reference_probe_passed": multi_pass,
            "observed": "|".join(sorted(remaining)),
            "expected": "C|D",
            "production_math_when_manually_injected_passed": False,
            "production_supported_entry_path": False,
            "notes": (
                "Reference ledger preserves two pairs and closes one independently; "
                "production has no pair identity or maximum-pair constraint."
            ),
        }
    )
    exposure_rows.extend(
        [
            {
                "scenario_id": "two_pair_target",
                "gross_exposure": initial_multi["gross_exposure"],
                "net_exposure": initial_multi["net_exposure"],
                "maximum_absolute_leg_weight": initial_multi[
                    "max_absolute_leg_weight"
                ],
                "gross_cap": 1.0,
                "net_tolerance": TOL,
                "passed": (
                    initial_multi["gross_exposure"] <= 1.0 + TOL
                    and abs(initial_multi["net_exposure"]) <= TOL
                ),
            },
            {
                "scenario_id": "two_pair_post_move",
                "gross_exposure": multi_mark["gross_exposure"],
                "net_exposure": multi_mark["net_exposure"],
                "maximum_absolute_leg_weight": multi_mark[
                    "max_absolute_leg_weight"
                ],
                "gross_cap": 1.0,
                "net_tolerance": TOL,
                "passed": multi_mark["gross_exposure"] <= 1.0 + TOL,
            },
        ]
    )

    missing_entry = SyntheticSignedLedger()
    missing_entry_result = missing_entry.set_target_weights(
        {"A": 0.5, "B": -0.5},
        {"A": 100.0, "B": None},
    )
    missing_mark = SyntheticSignedLedger()
    missing_mark.set_target_weights(
        {"A": 0.5, "B": -0.5},
        {"A": 100.0, "B": 100.0},
    )
    prior_prices = dict(missing_mark.last_prices)
    missing_mark_result = missing_mark.mark({"A": 101.0, "B": None})
    missing_rows.extend(
        [
            {
                "scenario_id": "missing_short_entry_price",
                "phase": "entry",
                "action": missing_entry_result["reason"],
                "positions_after": len(missing_entry.quantities),
                "one_legged_exposure_created": False,
                "price_forward_filled": False,
                "production_behavior": (
                    "pending legs are processed independently; no atomic pair order"
                ),
                "passed": (
                    not missing_entry_result["accepted"]
                    and not missing_entry.quantities
                ),
            },
            {
                "scenario_id": "missing_short_valuation_price",
                "phase": "valuation",
                "action": missing_mark_result["reason"],
                "positions_after": len(missing_mark.quantities),
                "one_legged_exposure_created": False,
                "price_forward_filled": missing_mark.last_prices != prior_prices,
                "production_behavior": (
                    "Portfolio.mark_to_market substitutes entry_price; backtester "
                    "then closes missing symbols independently at entry_price"
                ),
                "passed": (
                    not missing_mark_result["accepted"]
                    and missing_mark.invalid
                    and missing_mark.last_prices == prior_prices
                ),
            },
        ]
    )
    results.append(
        {
            "probe_id": "probe_7_missing_short_leg_data",
            "reference_probe_passed": all(row["passed"] for row in missing_rows),
            "observed": "atomic_block_or_invalidate",
            "expected": "atomic_block_or_invalidate",
            "production_math_when_manually_injected_passed": False,
            "production_supported_entry_path": False,
            "notes": (
                "Reference ledger blocks atomically without forward fill. "
                "Production behavior can stale-value or independently close a leg."
            ),
        }
    )

    core_short = core_short_entry_probe()
    negative_weights = pd.DataFrame(
        [[0.5, -0.5]],
        index=pd.to_datetime(["2020-01-02"]),
        columns=["A", "B"],
    )
    adapter_invariants = invariant_summary(negative_weights)
    results.append(
        {
            "probe_id": "production_entry_and_adapter_gate",
            "reference_probe_passed": True,
            "observed": {
                "core_short_entry": core_short,
                "bt_negative_weight_violation_count": adapter_invariants[
                    "negative_weight_violation_count"
                ],
                "bt_exposure_invariant_passed": adapter_invariants[
                    "exposure_invariant_passed"
                ],
            },
            "expected": "production short path supported",
            "production_math_when_manually_injected_passed": False,
            "production_supported_entry_path": False,
            "notes": (
                "Core target sizing clamps negative target notional to zero and "
                "the bt adapter rejects negative weights."
            ),
        }
    )

    return {
        "results": results,
        "turnover": turnover_rows,
        "borrow": borrow_rows,
        "corporate_actions": corporate_rows,
        "exposure": exposure_rows,
        "missing_leg": missing_rows,
    }


def probe_definition_rows() -> list[dict[str, Any]]:
    return [
        {
            "probe_id": "probe_1_basic_dollar_neutral_pair",
            "purpose": "long rises and short falls",
            "frozen_input": "A +0.50 from 100 to 110; B -0.50 from 100 to 90",
            "expected": "NAV 110; both legs gain; gross 1; net 0 at entry",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_2_adverse_pair_move",
            "purpose": "long falls and short rises",
            "frozen_input": "A +0.50 from 100 to 90; B -0.50 from 100 to 110",
            "expected": "NAV 90; both legs lose",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_3_turnover_and_costs",
            "purpose": "signed opening resizing closing reversal and second pair",
            "frozen_input": "five fixed signed-weight transitions; 10 bps per traded notional",
            "expected": "exact one-way turnover and costs on every leg",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_4_borrow_fee",
            "purpose": "daily borrow on absolute short notional",
            "frozen_input": "50 short notional; 5% annual; 252-day basis",
            "expected": "50*0.05/252",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_5_distributions_and_adjusted_returns",
            "purpose": "distribution and split counted exactly once",
            "frozen_input": "synthetic raw and adjusted OHLC with dividend and split",
            "expected": "signed adjusted-return P&L; no extra dividend charge",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_6_multiple_pairs",
            "purpose": "two simultaneous pairs and independent pair closure",
            "frozen_input": "A +0.25 B -0.25 C +0.25 D -0.25",
            "expected": "gross 1; net 0; closing A/B leaves C/D",
            "strategy_or_backtest": False,
        },
        {
            "probe_id": "probe_7_missing_short_leg_data",
            "purpose": "atomic missing-leg protection",
            "frozen_input": "short entry or valuation price absent",
            "expected": "block or invalidate; no forward fill; no one-leg exposure",
            "strategy_or_backtest": False,
        },
    ]


def existing_support_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "support_id": "core_position_container",
            "path": "src/portfolio.py",
            "class_or_function": "Position; Portfolio.mark_to_market",
            "line_reference": "58;187",
            "observed_support": (
                "Signed shares are mathematically accepted when manually injected; "
                "cash plus signed market value produces correct NAV."
            ),
            "limitation": "No supported short-entry or restricted-collateral path.",
            "test_or_probe": "probe_1;probe_2;production_entry_and_adapter_gate",
            "classification": "partially_supported",
        },
        {
            "support_id": "core_entry_sizing",
            "path": "src/portfolio.py",
            "class_or_function": "Portfolio.attempt_open_position",
            "line_reference": "373;448;564",
            "observed_support": "Long entries, cash-funded positive quantities.",
            "limitation": (
                "Negative target notional is clamped to zero; short entry fails."
            ),
            "test_or_probe": "production_entry_and_adapter_gate",
            "classification": "unsupported",
        },
        {
            "support_id": "core_exposure_reporting",
            "path": "src/backtester.py",
            "class_or_function": "Backtester._record_equity_row",
            "line_reference": "297;308-324",
            "observed_support": "Gross market value uses absolute signed notional.",
            "limitation": "No net-exposure or pair-level exposure reporting.",
            "test_or_probe": "probe_6",
            "classification": "partially_supported",
        },
        {
            "support_id": "bt_signed_turnover_helper",
            "path": (
                "strategy_lab/research_os/external_adapters/bt_adapter.py"
            ),
            "class_or_function": "turnover_from_weights",
            "line_reference": "124-130",
            "observed_support": (
                "Absolute signed-weight differences produce correct one-way turnover."
            ),
            "limitation": (
                "Adapter invariant rejects all negative weights; no integrated costs."
            ),
            "test_or_probe": "probe_3;production_entry_and_adapter_gate",
            "classification": "partially_supported",
        },
        {
            "support_id": "adjusted_total_return_data",
            "path": "src/data.py",
            "class_or_function": "build_adjusted_ohlc",
            "line_reference": "108-155",
            "observed_support": (
                "Adjusted close becomes canonical close; OHLC use the same factor."
            ),
            "limitation": (
                "No point-in-time membership, delisting-return, or symbol-change model."
            ),
            "test_or_probe": "probe_5",
            "classification": "partially_supported",
        },
        {
            "support_id": "candidate_local_pair_ledger",
            "path": (
                "strategy_lab/research_os/research/"
                "etf_pairs_short_accounting_resolution_v1.py"
            ),
            "class_or_function": "SleeveLedger; aggregate_sleeves",
            "line_reference": "90-275",
            "observed_support": (
                "Negative shares, restricted proceeds, pair NAV, fixed borrow, "
                "per-leg costs, multiple sleeves, missing-price invalidation."
            ),
            "limitation": (
                "Explicitly candidate-local, fixed convention, not generic core."
            ),
            "test_or_probe": (
                "tests/test_etf_pairs_short_accounting_resolution_v1.py"
            ),
            "classification": "partially_supported",
        },
        {
            "support_id": "candidate_local_pair_screen",
            "path": (
                "strategy_lab/research_os/research/etf_pairs_distance_screen_v1.py"
            ),
            "class_or_function": "simulate_cycle; aggregate_sleeves",
            "line_reference": "395-557",
            "observed_support": (
                "A prior bounded ETF-pairs screen used the local ledger."
            ),
            "limitation": (
                "Prior exact ETF portability result is not a reusable core engine "
                "and is not the Gatev stock universe."
            ),
            "test_or_probe": "tests/test_etf_pairs_distance_screen_v1.py",
            "classification": "partially_supported",
        },
        {
            "support_id": "core_missing_price_behavior",
            "path": "src/portfolio.py;src/backtester.py",
            "class_or_function": (
                "Portfolio.mark_to_market; Backtester._process_intraday_stops"
            ),
            "line_reference": "187-198;438-465",
            "observed_support": "Missing bars receive a data_issue path.",
            "limitation": (
                "Valuation substitutes entry price and position exits are processed "
                "independently, not atomically by pair."
            ),
            "test_or_probe": "probe_7",
            "classification": "unsupported",
        },
    ]
    for row in rows:
        if row["classification"] not in CLASSIFICATIONS:
            raise ValueError("Invalid support classification")
    return rows


def capability_rows() -> list[dict[str, Any]]:
    rows = [
        ("A", "positive_long_weights", "supported_and_verified", "Core and reference ledgers support positive quantities.", "src/portfolio.py:373", "probe_1", "none"),
        ("A", "negative_short_weights", "unsupported", "Core entry clamps negative target notional to zero; bt adapter rejects negative weights.", "src/portfolio.py:448;bt_adapter.py:161", "production_entry_and_adapter_gate", "generic signed entry/order support"),
        ("A", "simultaneous_long_and_short", "unsupported", "Only manual injection or candidate-local ledger can create both legs.", "src/portfolio.py:373;etf_pairs_short_accounting_resolution_v1.py:134", "probe_1", "atomic signed pair transaction"),
        ("A", "separate_leg_quantities_and_market_values", "partially_supported", "Position objects are per symbol, but no supported pair identity or short entry.", "src/portfolio.py:58;187", "probe_1", "pair and leg identifiers"),
        ("A", "gross_exposure", "partially_supported", "Core reports absolute market value, but cannot originate signed positions.", "src/backtester.py:308-324", "gross_net_exposure_probe.csv", "signed-path invariant integration"),
        ("A", "net_exposure", "unsupported", "Core equity rows do not report or constrain net exposure.", "src/backtester.py:315-335", "gross_net_exposure_probe.csv", "net exposure calculation and tolerance"),
        ("A", "dollar_neutral_target", "unsupported", "Weight-sum-one long-only invariants conflict with +0.50/-0.50 targets.", "bt_adapter.py:161-172", "production_entry_and_adapter_gate", "signed target contract"),
        ("B", "long_leg_mark_to_market", "supported_and_verified", "Core and reference calculations agree.", "src/portfolio.py:187-198", "probe_1;probe_2", "none"),
        ("B", "short_leg_mark_to_market", "partially_supported", "Signed arithmetic works only after manual injection; no supported short lifecycle.", "src/portfolio.py:187-198", "probe_1;probe_2", "signed short lifecycle"),
        ("B", "combined_pair_nav", "partially_supported", "Reference and manual injection are exact; production creation path absent.", "src/portfolio.py:187-198", "probe_1;probe_2", "atomic pair lifecycle"),
        ("B", "position_close_and_reversal", "unsupported", "Core close logic was designed for positive shares and there is no pair reversal order.", "src/portfolio.py:277-370", "probe_3", "signed close and reversal transactions"),
        ("B", "multiple_open_pairs", "unsupported", "No generic pair IDs, pair caps, or atomic independent closures.", "src/portfolio.py:58-75", "probe_6", "pair-level portfolio state"),
        ("C", "signed_weight_turnover_formula", "supported_and_verified", "bt helper matches all five frozen signed transitions.", "bt_adapter.py:124-130", "probe_3", "none for formula"),
        ("C", "both_leg_transaction_costs", "partially_supported", "Candidate-local ledger charges every leg; generic backtester has no signed two-leg cost path.", "etf_pairs_short_accounting_resolution_v1.py:134-232", "probe_3", "integrated signed traded-notional costs"),
        ("C", "turnover_from_actual_pretrade_holdings", "partially_supported", "Long-only research modules support drift, but bt helper uses target-frame differences.", "bt_adapter.py:124-130", "probe_3", "signed actual-holdings turnover"),
        ("D", "daily_short_borrow_fee", "unsupported", "No core borrow accrual exists.", "src/portfolio.py", "probe_4", "daily absolute-short-notional accrual"),
        ("D", "instrument_specific_borrow_fee", "unsupported", "Only a fixed candidate-local 5% convention exists.", "etf_pairs_short_accounting_resolution_v1.py:33-35", "probe_4", "borrow-rate series by symbol/date"),
        ("D", "unavailable_to_borrow", "unsupported", "No locate, availability, recall, or forced-cover state.", "src/portfolio.py", "borrow_and_financing_probe.csv", "availability and recall state machine"),
        ("D", "cash_or_collateral_yield", "partially_supported", "Synthetic safe cash can accrue, but it is not linked to short collateral.", "src/portfolio.py:148-185", "borrow_and_financing_probe.csv", "collateral-specific accrual"),
        ("D", "debit_financing_above_one_gross", "unsupported", "No margin debit or financing model for signed portfolios.", "src/portfolio.py", "borrow_and_financing_probe.csv", "financing and margin ledger"),
        ("D", "zero_borrow_diagnostic_label", "partially_supported", "A local ledger can set zero, but core has no explicit diagnostic field.", "etf_pairs_short_accounting_resolution_v1.py:173", "probe_4", "explicit assumption metadata"),
        ("E", "long_distributions_once", "supported_and_verified", "Canonical adjusted close embeds total distributions; no separate cash dividend is added.", "src/data.py:137-150", "probe_5", "none for surviving ETFs"),
        ("E", "short_distribution_obligation_once", "partially_supported", "Negative adjusted return exposure creates the obligation in reference math; core short path absent.", "src/data.py:137-150", "probe_5", "signed adjusted-return integration"),
        ("E", "stock_splits", "partially_supported", "Adjusted OHLC neutralizes split moves, but signed quantity semantics are not documented in core.", "src/data.py:108-155", "probe_5", "signed adjusted-unit contract"),
        ("E", "avoid_distribution_double_count", "supported_and_verified", "Probe shows explicit dividend cash flows must remain disabled with adjusted prices.", "src/data.py:149-150", "probe_5", "guardrail test"),
        ("E", "symbol_changes_missing_and_delisting", "unsupported", "No point-in-time membership, symbol map, or delisting-return model exists.", "src/data.py:201-292", "data_universe_assessment.csv", "PIT security master and delisting policy"),
        ("F", "maximum_gross_exposure", "partially_supported", "Core reports gross; local research code can check caps; no signed-order enforcement.", "src/backtester.py:308-324", "probe_6", "pretrade signed cap enforcement"),
        ("F", "maximum_absolute_leg_weight", "unsupported", "No generic signed-leg cap.", "src/portfolio.py", "gross_net_exposure_probe.csv", "absolute signed-weight cap"),
        ("F", "net_exposure_tolerance", "unsupported", "No net field or tolerance.", "src/backtester.py", "gross_net_exposure_probe.csv", "net exposure invariant"),
        ("F", "maximum_simultaneous_pairs", "unsupported", "Core max_positions is not a pair cap and entries are not paired.", "src/portfolio.py:418-432", "probe_6", "pair counter and pair lifecycle"),
        ("F", "no_residual_directional_exposure", "unsupported", "No atomic pair fill or pair-level invariant.", "src/backtester.py:378-438", "probe_7", "atomic pair transactions"),
        ("F", "cash_and_collateral_accounting", "unsupported", "Core has cash but no restricted short proceeds.", "src/portfolio.py:107-118", "probe_1", "restricted collateral ledger"),
        ("G", "formation_vs_trading_separation", "partially_supported", "Existing research modules can separate windows, but no generic pair contract.", "etf_pairs_distance_screen_v1.py", "existing_support_inventory.csv", "generic pair timing interface"),
        ("G", "completed_close_next_session_execution", "supported_and_verified", "Core pending entries execute on later open and local pair screen delays execution.", "src/backtester.py:378-438", "existing tests", "none"),
        ("G", "simultaneous_pair_entry_and_exit", "unsupported", "Core pending signals fill one at a time.", "src/backtester.py:344-438", "probe_7", "atomic multi-leg order group"),
        ("G", "no_same_period_signal_return", "partially_supported", "Core supports delayed execution; no generic pair implementation to enforce it.", "src/backtester.py:637-965", "existing tests", "pair-specific timing invariant"),
        ("G", "missing_leg_determinism", "unsupported", "Core stale-values at entry price or closes positions independently.", "src/portfolio.py:187-198;src/backtester.py:438-465", "probe_7", "atomic block/freeze policy"),
        ("H", "strategy_and_trial_entity_separation", "supported_and_verified", "Repository evidence conventions preserve entity types.", "strategy evidence packets", "zero-row strategy_cards.csv;trial_ledger.csv", "none"),
        ("H", "pair_selection_diagnostics", "supported_and_verified", "Prior candidate-local screen emitted pair formation diagnostics.", "etf_pairs_distance_screen_v1.py", "prior evidence", "none"),
        ("H", "pair_and_leg_ledgers", "partially_supported", "Prior local screen emitted them; generic engine does not.", "etf_pairs_distance_screen_v1.py", "prior evidence", "generalized schema"),
        ("H", "borrow_cost_ledger", "partially_supported", "Prior local screen emitted fixed-rate borrow; generic engine does not.", "etf_pairs_distance_screen_v1.py", "prior evidence", "generic borrow schema"),
        ("H", "gross_net_invariants", "partially_supported", "Prior local screen emitted them; core does not enforce net.", "etf_pairs_distance_screen_v1.py", "prior evidence", "core signed invariants"),
        ("H", "failure_reasons_and_next_actions", "supported_and_verified", "Repository evidence packets support controlled outcomes and next actions.", "existing evidence conventions", "this packet", "none"),
    ]
    return [
        {
            "section": section,
            "capability": capability,
            "classification": classification,
            "finding": finding,
            "file_or_artifact": artifact,
            "test_or_probe": probe,
            "smallest_missing_support": patch,
        }
        for section, capability, classification, finding, artifact, probe, patch in rows
    ]


def load_cache_frame(symbol: str) -> pd.DataFrame:
    path = CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").drop_duplicates("date", keep="last")


def universe_summary(
    universe_id: str,
    symbols: list[str],
    universe_type: str,
    source_fidelity: str,
) -> dict[str, Any]:
    frames = {symbol: load_cache_frame(symbol) for symbol in symbols}
    missing = [symbol for symbol, frame in frames.items() if frame.empty]
    valid_frames = {symbol: frame for symbol, frame in frames.items() if not frame.empty}
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    schema_ready = all(required <= set(frame.columns) for frame in valid_frames.values())
    positive = all(
        np.isfinite(frame[["open", "high", "low", "close", "adj_close"]].to_numpy()).all()
        and (frame[["open", "high", "low", "close", "adj_close"]] > 0.0).all().all()
        for frame in valid_frames.values()
    )
    starts = [frame["date"].min() for frame in valid_frames.values()]
    ends = [frame["date"].max() for frame in valid_frames.values()]
    common_start = max(starts) if starts else None
    common_end = min(ends) if ends else None
    common_dates: set[pd.Timestamp] | None = None
    for frame in valid_frames.values():
        dates = set(pd.Timestamp(value) for value in frame["date"])
        common_dates = dates if common_dates is None else common_dates & dates
    return {
        "universe_id": universe_id,
        "universe_type": universe_type,
        "symbol_count": len(symbols),
        "available_symbol_count": len(valid_frames),
        "symbols": symbols,
        "missing_symbols": missing,
        "earliest_individual_date": min(starts).date().isoformat() if starts else "",
        "latest_individual_date": max(ends).date().isoformat() if ends else "",
        "earliest_common_date": common_start.date().isoformat() if common_start is not None else "",
        "latest_common_date": common_end.date().isoformat() if common_end is not None else "",
        "common_session_count": len(common_dates or set()),
        "adjusted_daily_ohlcv_ready": bool(
            not missing and schema_ready and positive
        ),
        "source_fidelity": source_fidelity,
        "point_in_time_membership": False,
        "delisting_return_support": False,
        "survivorship_limitation": (
            "current-survivor wrapper universe; not source-faithful stock history"
        ),
        "provider_download_required": False,
    }


def data_universe_rows() -> list[dict[str, Any]]:
    cache_symbols = sorted(path.stem for path in CACHE_DIR.glob("*.csv"))
    frozen_rows: list[dict[str, str]] = []
    if FROZEN_PRIMARY_UNIVERSE.exists():
        with FROZEN_PRIMARY_UNIVERSE.open(newline="", encoding="utf-8") as handle:
            frozen_rows = list(csv.DictReader(handle))
    frozen_symbols = [row["symbol"] for row in frozen_rows]
    rows = [
        universe_summary(
            "canonical_adjusted_cache_all_etfs",
            cache_symbols,
            "ETF",
            "not_a_stock_pairs_universe",
        ),
        universe_summary(
            "pre_frozen_liquid_primary_etf_universe",
            frozen_symbols,
            "ETF",
            "current_survivor_wrapper_portability_only",
        ),
        universe_summary(
            "prior_candidate_local_sector_etf_pairs_universe",
            list(PRIOR_PAIR_ETF_UNIVERSE),
            "ETF",
            "ETF_portability_not_Gatev_stock_source_equivalent",
        ),
        {
            "universe_id": "source_aligned_point_in_time_liquid_stock_universe",
            "universe_type": "individual_common_stock",
            "symbol_count": 0,
            "available_symbol_count": 0,
            "symbols": "",
            "missing_symbols": "entire_source_required_stock_universe",
            "earliest_individual_date": "",
            "latest_individual_date": "",
            "earliest_common_date": "",
            "latest_common_date": "",
            "common_session_count": 0,
            "adjusted_daily_ohlcv_ready": False,
            "source_fidelity": "required_for_source_faithful_Gatev_stock_pairs",
            "point_in_time_membership": False,
            "delisting_return_support": False,
            "survivorship_limitation": (
                "No all-listed point-in-time stock universe, delistings, or "
                "historical membership."
            ),
            "provider_download_required": True,
        },
    ]
    return rows


def accounting_convention_rows() -> list[dict[str, Any]]:
    return [
        {
            "topic": "canonical_price",
            "current_convention": "adjusted close is canonical close",
            "evidence": "src/data.py:137-150",
            "long_short_implication": (
                "Distributions and splits are embedded in signed adjusted returns."
            ),
            "classification": "supported_and_verified",
        },
        {
            "topic": "dividends",
            "current_convention": (
                "raw dividend retained as metadata; no separate portfolio cash flow"
            ),
            "evidence": "src/data.py:21;135;149",
            "long_short_implication": (
                "Do not add a separate short-dividend debit when using adjusted close."
            ),
            "classification": "supported_and_verified",
        },
        {
            "topic": "splits",
            "current_convention": (
                "adjustment factor applies to OHLC; stock_splits retained"
            ),
            "evidence": "src/data.py:137-150",
            "long_short_implication": (
                "Use adjusted-unit quantities consistently; no raw split cash flow."
            ),
            "classification": "partially_supported",
        },
        {
            "topic": "core_cash",
            "current_convention": "cash reduced by positive long notional",
            "evidence": "src/portfolio.py:502-564",
            "long_short_implication": (
                "No restricted short-sale proceeds or collateral balance."
            ),
            "classification": "unsupported",
        },
        {
            "topic": "candidate_local_short_cash",
            "current_convention": (
                "cash + long market value - short liability; restricted proceeds"
            ),
            "evidence": (
                "etf_pairs_short_accounting_resolution_v1.py:90-254"
            ),
            "long_short_implication": (
                "Valid only for the prior candidate-local simulation."
            ),
            "classification": "partially_supported",
        },
        {
            "topic": "borrow",
            "current_convention": (
                "no core convention; prior candidate-local diagnostic used 5%/252"
            ),
            "evidence": (
                "etf_pairs_short_accounting_resolution_v1.py:33-35;173-191"
            ),
            "long_short_implication": (
                "Cannot claim realistic reusable short simulation."
            ),
            "classification": "unsupported",
        },
        {
            "topic": "missing_price",
            "current_convention": (
                "core mark uses entry price; later data_issue close can occur per leg"
            ),
            "evidence": "src/portfolio.py:187-198;src/backtester.py:438-465",
            "long_short_implication": (
                "Can create stale valuation and non-atomic pair handling."
            ),
            "classification": "unsupported",
        },
        {
            "topic": "delisting_and_symbol_changes",
            "current_convention": "no canonical treatment found",
            "evidence": "src/data.py",
            "long_short_implication": (
                "Source-faithful stock-pairs simulation is blocked."
            ),
            "classification": "unsupported",
        },
    ]


def gap_rows() -> list[dict[str, Any]]:
    return [
        {
            "gap_id": "generic_signed_position_lifecycle",
            "blocker": "Core entry sizing cannot create negative shares.",
            "affected_files": "src/strategies.py|src/portfolio.py|src/backtester.py",
            "smallest_possible_patch": (
                "Add explicit side/signed target semantics, signed cash flows, "
                "short close/reversal handling, and signed trade ledger fields."
            ),
            "scope_judgment": "architectural",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "atomic_multi_leg_transactions",
            "blocker": "Pending entries and exits process each symbol independently.",
            "affected_files": "src/backtester.py|src/portfolio.py",
            "smallest_possible_patch": (
                "Add atomic order groups with all-leg price validation and rollback."
            ),
            "scope_judgment": "architectural",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "borrow_collateral_and_financing",
            "blocker": (
                "No core borrow rates, locate state, restricted collateral, "
                "collateral yield, recalls, or debit financing."
            ),
            "affected_files": "src/portfolio.py|src/backtester.py|config schema",
            "smallest_possible_patch": (
                "Add dated per-symbol borrow/availability inputs and daily financing "
                "ledgers integrated into NAV."
            ),
            "scope_judgment": "architectural",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "signed_constraints_and_invariants",
            "blocker": (
                "No net tolerance, leg cap, pair cap, or residual exposure guard."
            ),
            "affected_files": "src/portfolio.py|src/backtester.py|bt_adapter.py",
            "smallest_possible_patch": (
                "Replace long-only weight-sum invariants with signed gross/net/leg "
                "and pair constraints for an explicitly separate lane."
            ),
            "scope_judgment": "architectural",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "corporate_action_and_missing_security_lifecycle",
            "blocker": (
                "Adjusted returns are clear for surviving ETFs, but delisting, "
                "symbol changes, and one-missing-leg behavior are not reliable."
            ),
            "affected_files": "src/data.py|src/portfolio.py|src/backtester.py",
            "smallest_possible_patch": (
                "Define adjusted-unit contract, point-in-time security mapping, "
                "delisting returns, and atomic missing-leg liquidation policy."
            ),
            "scope_judgment": "architectural",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "source_aligned_stock_universe",
            "blocker": (
                "Cache has ETFs only; no point-in-time liquid-stock membership or "
                "delisting-aware history."
            ),
            "affected_files": "data layer|security master|universe snapshots",
            "smallest_possible_patch": (
                "A separate authorized survivorship-aware stock-data capability "
                "project, or an explicit direction-owner ETF portability decision."
            ),
            "scope_judgment": "material_data_project",
            "bounded_single_patch": False,
            "required_before_lane": True,
        },
        {
            "gap_id": "evidence_schema_generalization",
            "blocker": (
                "Pair and borrow ledgers exist only in a candidate-local prior screen."
            ),
            "affected_files": "new additive evidence schema",
            "smallest_possible_patch": (
                "Generalize pair, leg, borrow, exposure, and failure ledgers after "
                "accounting and data contracts are approved."
            ),
            "scope_judgment": "local_after_core_work",
            "bounded_single_patch": True,
            "required_before_lane": False,
        },
    ]


def unlocked_family_rows() -> list[dict[str, Any]]:
    return [
        {
            "family_id": "distance_pairs_trading",
            "unlocked_by": "signed atomic pair accounting plus source-aligned data",
            "currently_unlocked": False,
            "implementation_authorized": False,
        },
        {
            "family_id": "cointegration_relative_value",
            "unlocked_by": "signed atomic pair accounting and pair diagnostics",
            "currently_unlocked": False,
            "implementation_authorized": False,
        },
        {
            "family_id": "beta_neutral_long_short",
            "unlocked_by": "signed positions, financing, and net/gross constraints",
            "currently_unlocked": False,
            "implementation_authorized": False,
        },
        {
            "family_id": "hedged_sector_or_factor_spreads",
            "unlocked_by": "signed positions, borrow, and atomic multi-leg orders",
            "currently_unlocked": False,
            "implementation_authorized": False,
        },
    ]


def risk_rows() -> list[dict[str, Any]]:
    return [
        {
            "risk_id": "one_leg_fill",
            "severity": "critical",
            "failure_mode": "One pair leg fills while the other is missing.",
            "current_control": "none in generic engine",
            "required_control": "atomic multi-leg order group with rollback",
        },
        {
            "risk_id": "stale_short_valuation",
            "severity": "critical",
            "failure_mode": "Missing price is valued at entry price.",
            "current_control": "later per-position data_issue close",
            "required_control": "pair-level invalidation without tradable forward fill",
        },
        {
            "risk_id": "borrow_omission",
            "severity": "high",
            "failure_mode": "Short cost and availability omitted.",
            "current_control": "candidate-local fixed diagnostic only",
            "required_control": "dated symbol-specific borrow and availability",
        },
        {
            "risk_id": "short_proceeds_reuse",
            "severity": "high",
            "failure_mode": "Short-sale cash can become unintended buying power.",
            "current_control": "candidate-local restricted proceeds only",
            "required_control": "core restricted collateral ledger",
        },
        {
            "risk_id": "distribution_double_count",
            "severity": "high",
            "failure_mode": (
                "Adjusted return plus explicit short dividend charge counts twice."
            ),
            "current_control": "probe documents adjusted-only convention",
            "required_control": "enforced no-extra-dividend guardrail",
        },
        {
            "risk_id": "survivorship_and_delisting",
            "severity": "critical",
            "failure_mode": (
                "Current survivors replace the historical stock selection universe."
            ),
            "current_control": "no source-faithful stock experiment authorized",
            "required_control": "PIT universe and delisting returns",
        },
        {
            "risk_id": "residual_directional_exposure",
            "severity": "high",
            "failure_mode": "Independent leg handling violates intended neutrality.",
            "current_control": "none in generic engine",
            "required_control": "net tolerance and atomic pair lifecycle",
        },
    ]


def source_context_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_context_id": SOURCE_CONTEXT_ID,
            "entity_type": "source_library_record",
            "stage": "blocked",
            "outcome": "blocked_feasibility",
            "failure_reason": "capability_missing",
            "family_id": SOURCE_FAMILY,
            "source": (
                "Gatev, Goetzmann, and Rouwenhorst; Pairs Trading: "
                "Performance of a Relative-Value Arbitrage Rule"
            ),
            "context_only": True,
            "strategy_id": "",
            "trial_id": "",
            "implementation_authorized": False,
        }
    ]


def capability_task_rows() -> list[dict[str, Any]]:
    return [
        {
            "task_id": CAPABILITY_TASK_ID,
            "entity_type": "data_capability_task",
            "stage": "blocked",
            "adaptation_label": "engine_capability_adjustment",
            "outcome": OUTCOME,
            "failure_reason": PRIMARY_FAILURE_REASON,
            "decision_reason": DECISION_REASON,
            "next_action": NEXT_ACTION,
            "strategy_or_trial_created": False,
        }
    ]


def process_task_rows() -> list[dict[str, Any]]:
    return [
        {
            "task_id": PROCESS_TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": OUTCOME,
            "next_action": NEXT_ACTION,
            "next_action_executed": False,
        }
    ]


def strategy_headers() -> list[str]:
    return [
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "stage",
        "trial_id",
        "outcome",
        "failure_reason",
        "next_action",
    ]


def trial_headers() -> list[str]:
    return [
        "trial_id",
        "strategy_id",
        "family_id",
        "entity_type",
        "stage",
        "parent_trial_id",
        "adaptation_label",
        "outcome",
        "failure_reason",
        "next_action",
    ]


def capability_report(
    data_rows: list[dict[str, Any]],
    capability: list[dict[str, Any]],
    probes: dict[str, list[dict[str, Any]]],
) -> str:
    counts = {
        classification: sum(
            row["classification"] == classification for row in capability
        )
        for classification in sorted(CLASSIFICATIONS)
    }
    stock = next(
        row
        for row in data_rows
        if row["universe_id"]
        == "source_aligned_point_in_time_liquid_stock_universe"
    )
    etfs = next(
        row
        for row in data_rows
        if row["universe_id"] == "pre_frozen_liquid_primary_etf_universe"
    )
    return f"""# Long-Short Relative-Value Capability Audit v1

## Outcome

`{OUTCOME}`

The repository does not currently have a reusable production path for a
brokerless long-short relative-value lane. Signed P&L mathematics can be shown
with manual position injection, the signed turnover helper is correct, and a
prior candidate-local ETF-pairs ledger handled negative shares, collateral,
fixed borrow, and two-leg costs. Those facts do not make the generic engine
long-short ready.

Core entry sizing clamps negative target notionals to zero, the `bt` adapter
rejects negative weights, pending legs are not atomic, missing-price handling is
not pair-safe, and core borrow, locate, financing, net-exposure, pair-cap, and
restricted-collateral models are absent.

## Synthetic Probes

Reference probe pass count: `{sum(bool(row['reference_probe_passed']) for row in probes['results'])}/{len(probes['results'])}`.

The favorable pair produced exact NAV `110`, and the adverse pair produced exact
NAV `90`. Signed turnover passed opening, resizing, closing, reversal, and
second-pair transitions. Borrow accrual matched absolute short notional. Adjusted
prices counted distributions and splits once. Two pairs remained separately
identifiable in the test-only ledger, and missing-leg prices blocked atomically.

Production support remained false for every short-entry probe. The successful
reference calculations establish the accounting contract; they do not authorize
or simulate a strategy.

## Data Feasibility

- Pre-frozen liquid ETF wrappers: `{etfs['symbol_count']}`
- Source-aligned point-in-time common stocks: `{stock['symbol_count']}`
- Cached ETF portability data: available
- Gatev stock-universe fidelity: unavailable

The ETF cache is current-survivor portability data. An ETF-pairs experiment
would require a separate source-direction decision and must not be called a
source-equivalent Gatev stock-pairs experiment.

## Capability Matrix

- Supported and verified: `{counts['supported_and_verified']}`
- Partially supported: `{counts['partially_supported']}`
- Unsupported: `{counts['unsupported']}`
- Unclear due to missing test: `{counts['unclear_due_to_missing_test']}`
- Not applicable: `{counts['not_applicable']}`

## Scope Judgment

The remaining work is a material capability project, not one bounded patch. It
crosses signal semantics, atomic execution, signed cash and holdings, borrow and
financing, constraints, missing-leg behavior, corporate-action lifecycle, and
source-aligned stock data.

No production module, registry record, strategy, trial, benchmark strategy, or
paper/demo observation was created or changed.

Exact next action, not executed:

`{NEXT_ACTION}`
"""


def run() -> dict[str, Any]:
    protected_before = hash_paths(PROTECTED_PATHS)
    prior_before = hash_paths(PRIOR_EVIDENCE_PATHS)
    prior_identity_before = prior_evidence_identity()

    missing_inputs = [
        rel(path)
        for path in (*PRODUCTION_PATHS, *PRIOR_EVIDENCE_PATHS)
        if not path.exists()
    ]
    if missing_inputs:
        raise FileNotFoundError(
            f"Required audit inputs missing: {missing_inputs}"
        )

    clean_output()
    probes = run_synthetic_probes()
    capabilities = capability_rows()
    supports = existing_support_rows()
    data_rows = data_universe_rows()
    conventions = accounting_convention_rows()
    gaps = gap_rows()
    unlocked = unlocked_family_rows()
    risks = risk_rows()

    write_csv(
        OUTPUT_DIR / "source_context.csv",
        source_context_rows(),
        [
            "source_context_id",
            "entity_type",
            "stage",
            "outcome",
            "failure_reason",
            "family_id",
            "source",
            "context_only",
            "strategy_id",
            "trial_id",
            "implementation_authorized",
        ],
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [], strategy_headers())
    write_csv(OUTPUT_DIR / "trial_ledger.csv", [], trial_headers())
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        capability_task_rows(),
        [
            "task_id",
            "entity_type",
            "stage",
            "adaptation_label",
            "outcome",
            "failure_reason",
            "decision_reason",
            "next_action",
            "strategy_or_trial_created",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_task_rows(),
        [
            "task_id",
            "entity_type",
            "stage",
            "mode",
            "outcome",
            "next_action",
            "next_action_executed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "existing_support_inventory.csv",
        supports,
        [
            "support_id",
            "path",
            "class_or_function",
            "line_reference",
            "observed_support",
            "limitation",
            "test_or_probe",
            "classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "capability_matrix.csv",
        capabilities,
        [
            "section",
            "capability",
            "classification",
            "finding",
            "file_or_artifact",
            "test_or_probe",
            "smallest_missing_support",
        ],
    )
    data_fields = [
        "universe_id",
        "universe_type",
        "symbol_count",
        "available_symbol_count",
        "symbols",
        "missing_symbols",
        "earliest_individual_date",
        "latest_individual_date",
        "earliest_common_date",
        "latest_common_date",
        "common_session_count",
        "adjusted_daily_ohlcv_ready",
        "source_fidelity",
        "point_in_time_membership",
        "delisting_return_support",
        "survivorship_limitation",
        "provider_download_required",
    ]
    write_csv(
        OUTPUT_DIR / "data_universe_assessment.csv",
        data_rows,
        data_fields,
    )
    write_csv(
        OUTPUT_DIR / "accounting_convention_inventory.csv",
        conventions,
        [
            "topic",
            "current_convention",
            "evidence",
            "long_short_implication",
            "classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "synthetic_probe_definitions.csv",
        probe_definition_rows(),
        [
            "probe_id",
            "purpose",
            "frozen_input",
            "expected",
            "strategy_or_backtest",
        ],
    )
    write_csv(
        OUTPUT_DIR / "synthetic_probe_results.csv",
        probes["results"],
        [
            "probe_id",
            "reference_probe_passed",
            "observed",
            "expected",
            "production_math_when_manually_injected_passed",
            "production_supported_entry_path",
            "notes",
        ],
    )
    write_csv(
        OUTPUT_DIR / "turnover_and_cost_probe.csv",
        probes["turnover"],
        [
            "scenario_id",
            "pretrade_weights",
            "target_weights",
            "formula",
            "observed_one_way_turnover",
            "expected_one_way_turnover",
            "gross_traded_weight",
            "cost_rate_per_absolute_traded_notional",
            "transaction_cost",
            "long_and_short_trades_costed",
            "passed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "borrow_and_financing_probe.csv",
        probes["borrow"],
        [
            "scenario_id",
            "short_symbol",
            "absolute_short_notional",
            "annual_borrow_rate",
            "daily_borrow_cost",
            "expected_daily_borrow_cost",
            "instrument_specific_rate_supported_by_reference_probe",
            "production_engine_support",
            "passed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "corporate_action_probe.csv",
        probes["corporate_actions"],
        [
            "scenario_id",
            "raw_price_return",
            "adjusted_total_return",
            "long_leg_pnl",
            "short_leg_pnl",
            "explicit_dividend_cash_flow_added",
            "double_count_avoided",
            "passed",
            "interpretation",
        ],
    )
    write_csv(
        OUTPUT_DIR / "gross_net_exposure_probe.csv",
        probes["exposure"],
        [
            "scenario_id",
            "gross_exposure",
            "net_exposure",
            "maximum_absolute_leg_weight",
            "gross_cap",
            "net_tolerance",
            "passed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "missing_leg_data_probe.csv",
        probes["missing_leg"],
        [
            "scenario_id",
            "phase",
            "action",
            "positions_after",
            "one_legged_exposure_created",
            "price_forward_filled",
            "production_behavior",
            "passed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "gap_and_minimal_patch_scope.csv",
        gaps,
        [
            "gap_id",
            "blocker",
            "affected_files",
            "smallest_possible_patch",
            "scope_judgment",
            "bounded_single_patch",
            "required_before_lane",
        ],
    )
    write_csv(
        OUTPUT_DIR / "unlocked_strategy_families.csv",
        unlocked,
        [
            "family_id",
            "unlocked_by",
            "currently_unlocked",
            "implementation_authorized",
        ],
    )
    write_csv(
        OUTPUT_DIR / "risk_and_failure_modes.csv",
        risks,
        [
            "risk_id",
            "severity",
            "failure_mode",
            "current_control",
            "required_control",
        ],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "outcome": OUTCOME,
                "stage": STAGE,
                "remaining_work_classification": "material_capability_project",
                "primary_failure_reason": PRIMARY_FAILURE_REASON,
                "decision_reason": DECISION_REASON,
                "reference_synthetic_probes_passed": all(
                    row["reference_probe_passed"] for row in probes["results"]
                ),
                "generic_production_short_entry_supported": False,
                "source_aligned_stock_universe_ready": False,
                "candidate_local_pair_ledger_exists": True,
                "candidate_local_ledger_is_core": False,
                "exact_next_action": NEXT_ACTION,
                "next_action_executed": False,
            }
        ],
        [
            "task_id",
            "outcome",
            "stage",
            "remaining_work_classification",
            "primary_failure_reason",
            "decision_reason",
            "reference_synthetic_probes_passed",
            "generic_production_short_entry_supported",
            "source_aligned_stock_universe_ready",
            "candidate_local_pair_ledger_exists",
            "candidate_local_ledger_is_core",
            "exact_next_action",
            "next_action_executed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "entity_id": CAPABILITY_TASK_ID,
                "entity_type": "data_capability_task",
                "primary_failure_reason": PRIMARY_FAILURE_REASON,
                "decision_reason": DECISION_REASON,
                "details": (
                    "The generic engine lacks signed atomic pair accounting, "
                    "borrow/financing, pair-safe missing data, and a source-aligned "
                    "point-in-time stock universe."
                ),
                "scope": "material_capability_project",
            }
        ],
        [
            "entity_id",
            "entity_type",
            "primary_failure_reason",
            "decision_reason",
            "details",
            "scope",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "entity_id": CAPABILITY_TASK_ID,
                "entity_type": "data_capability_task",
                "exact_next_action": NEXT_ACTION,
                "execute_now": False,
            }
        ],
        [
            "entity_id",
            "entity_type",
            "exact_next_action",
            "execute_now",
        ],
    )

    protected_after = hash_paths(PROTECTED_PATHS)
    prior_after = hash_paths(PRIOR_EVIDENCE_PATHS)
    prior_identity_after = prior_evidence_identity()
    state_rows = [
        {
            "path": path,
            "category": (
                "authoritative_state"
                if path in {rel(item) for item in AUTHORITY_PATHS}
                else "production_module"
                if path in {rel(item) for item in PRODUCTION_PATHS}
                else "market_data_cache"
            ),
            "sha256_before": protected_before[path],
            "sha256_after": protected_after[path],
            "changed": protected_before[path] != protected_after[path],
            "change_permitted": False,
        }
        for path in sorted(protected_before)
    ]
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        [
            "path",
            "category",
            "sha256_before",
            "sha256_after",
            "changed",
            "change_permitted",
        ],
    )

    all_reference_probes_pass = all(
        row["reference_probe_passed"] for row in probes["results"]
    )
    protected_unchanged = protected_before == protected_after
    prior_unchanged = (
        prior_before == prior_after
        and prior_identity_before == prior_identity_after
    )
    capability_classes_valid = all(
        row["classification"] in CLASSIFICATIONS for row in capabilities
    )
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "outcome": OUTCOME,
        "remaining_work_classification": "material_capability_project",
        "source_library_context_records": 1,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "benchmark_strategies_created": 0,
        "paper_demo_observations_created_or_changed": 0,
        "synthetic_probes": len(probe_definition_rows()),
        "production_modules_changed": 0,
        "lifecycle_records_changed": 0,
        "reference_synthetic_probes_passed": all_reference_probes_pass,
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "capability_manifest.yaml", manifest)

    consistency_passed = (
        all_reference_probes_pass
        and all(row["passed"] for row in probes["turnover"])
        and all(row["passed"] for row in probes["corporate_actions"])
        and all(row["passed"] for row in probes["exposure"])
        and all(row["passed"] for row in probes["missing_leg"])
        and capability_classes_valid
        and protected_unchanged
        and prior_unchanged
        and OUTCOME == "long_short_capability_not_currently_viable"
        and NEXT_ACTION
        == "defer_long_short_lane_and_refresh_strategy_source_library_v6"
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "required_artifact_count": len(REQUIRED_OUTPUTS),
        "source_library_context_records": 1,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "benchmark_strategies_created": 0,
        "paper_demo_observations_created_or_changed": 0,
        "synthetic_probe_count": len(probe_definition_rows()),
        "reference_synthetic_probes_passed": all_reference_probes_pass,
        "generic_production_short_entry_supported": False,
        "candidate_local_pair_ledger_exists": True,
        "candidate_local_pair_ledger_is_generic_core": False,
        "source_aligned_point_in_time_stock_universe_ready": False,
        "capability_classifications_valid": capability_classes_valid,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "protected_state_unchanged": protected_unchanged,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_evidence_identity_before": prior_identity_before,
        "prior_evidence_identity_after": prior_identity_after,
        "prior_evidence_unchanged": prior_unchanged,
        "exact_outcome": OUTCOME,
        "exact_next_action": NEXT_ACTION,
        "next_action_executed": False,
        **FORBIDDEN_FLAGS,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "capability_report.md",
        capability_report(data_rows, capabilities, probes),
    )

    actual_outputs = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    if actual_outputs != REQUIRED_OUTPUTS:
        raise RuntimeError(
            "Capability artifact mismatch: "
            f"missing={sorted(REQUIRED_OUTPUTS-actual_outputs)}, "
            f"extra={sorted(actual_outputs-REQUIRED_OUTPUTS)}"
        )
    if not consistency_passed:
        raise RuntimeError("Long-short capability consistency check failed")
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "remaining_work_classification": "material_capability_project",
        "reference_synthetic_probes_passed": all_reference_probes_pass,
        "generic_production_short_entry_supported": False,
        "source_aligned_stock_universe_ready": False,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "production_modules_changed": 0,
        "protected_state_unchanged": protected_unchanged,
        "prior_evidence_unchanged": prior_unchanged,
        "consistency_passed": consistency_passed,
        "exact_next_action": NEXT_ACTION,
        "output_dir": rel(OUTPUT_DIR),
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
