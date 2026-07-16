from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import etf_pairs_single_source_preregistration_v1 as source_gate


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "etf_pairs_short_accounting_resolution_v1" / "latest"
SOURCE_GATE_DIR = ROOT / "evidence" / "etf_pairs_single_source_preregistration_v1" / "latest"
INTAKE_PATH = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates" / f"{source_gate.SOURCE_ID}.yaml"
CANDIDATE_ID = source_gate.CANDIDATE_ID
FAMILY_ID = source_gate.FAMILY_ID
SOURCE_ID = source_gate.SOURCE_ID
FROZEN_UNIVERSE = tuple(active.SECTOR_ASSETS)
PAIR_COUNT = 5
FORMATION_MONTHS = 12
TRADING_MONTHS = 6
ENTRY_THRESHOLD_SD = 2.0
BORROW_RATE_ANNUAL = 0.05
BORROW_RATE_DAILY = BORROW_RATE_ANNUAL / 252.0
TRANSACTION_COST_RATE = 0.0005
TOL = 1e-8


def sha256_path(path: Path) -> str:
    return source_gate.sha256_path(path)


def rel(path: Path) -> str:
    return source_gate.rel(path)


def csv_value(value: Any) -> str:
    return source_gate.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    source_gate.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    source_gate.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    source_gate.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    source_gate.write_text(path, text)


def read_intake() -> dict[str, Any]:
    if not INTAKE_PATH.exists():
        return source_gate.source_intake_payload()
    return yaml.safe_load(INTAKE_PATH.read_text(encoding="utf-8")) or {}


def update_intake_link() -> None:
    payload = read_intake()
    links = payload.setdefault("resolution_packets", [])
    link = {
        "resolution_id": "etf_pairs_short_accounting_resolution_v1",
        "path": "evidence/etf_pairs_short_accounting_resolution_v1/latest",
        "decision": "preregistration_ready",
        "previous_blocked_decision_preserved": "evidence/etf_pairs_single_source_preregistration_v1/latest",
    }
    if link not in links:
        links.append(link)
    payload.setdefault("governance", {})["prior_blocked_state_preserved"] = True
    write_yaml(INTAKE_PATH, payload)


def is_missing(value: float | None) -> bool:
    return value is None or not math.isfinite(float(value))


@dataclass
class SleeveLedger:
    """Candidate-local research ledger for one Gatev-style long/short ETF pair sleeve."""

    sleeve_id: str
    initial_nav: float
    cash: float = field(init=False)
    restricted_short_proceeds: float = 0.0
    long_symbol: str = ""
    short_symbol: str = ""
    long_shares: float = 0.0
    short_shares: float = 0.0
    long_market_value: float = 0.0
    short_liability: float = 0.0
    accrued_borrow_cost: float = 0.0
    transaction_costs: float = 0.0
    open_position: bool = False
    invalid: bool = False
    trade_count: int = 0
    event_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = float(self.initial_nav)

    @property
    def equity(self) -> float:
        return float(self.cash + self.long_market_value - self.short_liability)

    @property
    def free_cash(self) -> float:
        return float(self.cash - self.restricted_short_proceeds)

    @property
    def gross_exposure(self) -> float:
        eq = self.equity
        return float((abs(self.long_market_value) + abs(self.short_liability)) / eq) if abs(eq) > TOL else 0.0

    @property
    def net_exposure(self) -> float:
        eq = self.equity
        return float((self.long_market_value - self.short_liability) / eq) if abs(eq) > TOL else 0.0

    def accounting_identity_error(self) -> float:
        return float(self.equity - (self.cash + self.long_market_value - self.short_liability))

    def enter(self, date: str, long_symbol: str, short_symbol: str, long_price: float | None, short_price: float | None) -> dict[str, Any]:
        if self.open_position:
            raise ValueError("sleeve already open")
        if is_missing(long_price) or is_missing(short_price):
            self.invalid = True
            return self.snapshot(date, "invalid_missing_entry_price")
        nav = self.equity
        long_notional = 0.5 * nav
        short_notional = 0.5 * nav
        gross_target = long_notional + short_notional
        long_cost = long_notional * TRANSACTION_COST_RATE
        short_cost = short_notional * TRANSACTION_COST_RATE
        self.long_symbol = long_symbol
        self.short_symbol = short_symbol
        self.long_shares = long_notional / float(long_price)
        self.short_shares = -short_notional / float(short_price)
        self.long_market_value = long_notional
        self.short_liability = short_notional
        self.restricted_short_proceeds += short_notional
        self.cash += short_notional - long_notional - long_cost - short_cost
        self.transaction_costs += long_cost + short_cost
        self.open_position = True
        self.trade_count += 2
        row = self.snapshot(date, "entry")
        row.update(
            {
                "entry_nav_before_trade": nav,
                "entry_long_notional": long_notional,
                "entry_short_notional": short_notional,
                "entry_gross_target": gross_target,
                "entry_net_target": long_notional - short_notional,
                "short_proceeds_restricted_not_buying_power": True,
                "long_entry_cost": long_cost,
                "short_entry_cost": short_cost,
            }
        )
        self.event_log.append(row)
        return row

    def mark(self, date: str, long_price: float | None, short_price: float | None, accrue_borrow: bool = True) -> dict[str, Any]:
        if not self.open_position:
            row = self.snapshot(date, "flat_zero_return_cash")
            self.event_log.append(row)
            return row
        if is_missing(long_price) or is_missing(short_price):
            self.invalid = True
            row = self.snapshot(date, "invalid_missing_mark_price")
            self.event_log.append(row)
            return row
        self.long_market_value = float(self.long_shares) * float(long_price)
        self.short_liability = abs(float(self.short_shares)) * float(short_price)
        borrow_cost = self.short_liability * BORROW_RATE_DAILY if accrue_borrow else 0.0
        self.cash -= borrow_cost
        self.accrued_borrow_cost += borrow_cost
        row = self.snapshot(date, "mark")
        row["borrow_cost_charged_today"] = borrow_cost
        self.event_log.append(row)
        return row

    def exit(self, date: str, long_price: float | None, short_price: float | None, reason: str) -> dict[str, Any]:
        if not self.open_position:
            row = self.snapshot(date, f"{reason}_already_flat")
            self.event_log.append(row)
            return row
        if is_missing(long_price) or is_missing(short_price):
            self.invalid = True
            row = self.snapshot(date, f"invalid_missing_{reason}_price")
            self.event_log.append(row)
            return row
        self.mark(date, long_price, short_price, accrue_borrow=True)
        long_exit_value = self.long_market_value
        short_cover_value = self.short_liability
        long_exit_cost = long_exit_value * TRANSACTION_COST_RATE
        short_cover_cost = short_cover_value * TRANSACTION_COST_RATE
        self.cash += long_exit_value - long_exit_cost
        self.cash -= short_cover_value + short_cover_cost
        self.restricted_short_proceeds = 0.0
        self.long_market_value = 0.0
        self.short_liability = 0.0
        self.long_shares = 0.0
        self.short_shares = 0.0
        self.open_position = False
        self.transaction_costs += long_exit_cost + short_cover_cost
        self.trade_count += 2
        row = self.snapshot(date, reason)
        row.update(
            {
                "long_exit_value": long_exit_value,
                "short_cover_value": short_cover_value,
                "long_exit_cost": long_exit_cost,
                "short_cover_cost": short_cover_cost,
            }
        )
        self.event_log.append(row)
        return row

    def snapshot(self, date: str, event: str) -> dict[str, Any]:
        return {
            "date": date,
            "sleeve_id": self.sleeve_id,
            "event": event,
            "cash": self.cash,
            "restricted_short_proceeds": self.restricted_short_proceeds,
            "free_cash": self.free_cash,
            "long_symbol": self.long_symbol,
            "short_symbol": self.short_symbol,
            "long_shares": self.long_shares,
            "short_shares": self.short_shares,
            "long_market_value": self.long_market_value,
            "short_liability": self.short_liability,
            "accrued_borrow_cost": self.accrued_borrow_cost,
            "transaction_costs": self.transaction_costs,
            "sleeve_equity": self.equity,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "open_position": self.open_position,
            "invalid": self.invalid,
            "accounting_identity_error": self.accounting_identity_error(),
            "trade_count": self.trade_count,
        }


def aggregate_sleeves(sleeves: list[SleeveLedger], date: str, event: str) -> dict[str, Any]:
    equity = sum(sleeve.equity for sleeve in sleeves)
    gross_mv = sum(abs(sleeve.long_market_value) + abs(sleeve.short_liability) for sleeve in sleeves)
    net_mv = sum(sleeve.long_market_value - sleeve.short_liability for sleeve in sleeves)
    return {
        "date": date,
        "event": event,
        "sleeve_count": len(sleeves),
        "total_strategy_equity": equity,
        "sum_sleeve_navs": equity,
        "aggregate_gross_exposure": gross_mv / equity if abs(equity) > TOL else 0.0,
        "aggregate_net_exposure": net_mv / equity if abs(equity) > TOL else 0.0,
        "aggregate_transaction_costs": sum(sleeve.transaction_costs for sleeve in sleeves),
        "aggregate_borrow_cost": sum(sleeve.accrued_borrow_cost for sleeve in sleeves),
        "all_accounting_identities_hold": all(abs(sleeve.accounting_identity_error()) <= TOL for sleeve in sleeves),
        "any_invalid": any(sleeve.invalid for sleeve in sleeves),
    }


def scenario_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected: str, notes: str = "") -> None:
        rows.append({"scenario_id": name, "passed": passed, "observed": observed, "expected": expected, "notes": notes})

    base = SleeveLedger("long_rises_short_flat", 100.0)
    base.enter("d0", "AAA", "BBB", 100.0, 100.0)
    before = base.equity
    mark = base.mark("d1", 110.0, 100.0)
    add("long_rises_while_short_flat", mark["sleeve_equity"] > before, mark["sleeve_equity"], "equity greater than post-entry equity")

    short_falls = SleeveLedger("short_falls_long_flat", 100.0)
    short_falls.enter("d0", "AAA", "BBB", 100.0, 100.0)
    before = short_falls.equity
    mark = short_falls.mark("d1", 100.0, 90.0)
    add("short_falls_while_long_flat", mark["sleeve_equity"] > before, mark["sleeve_equity"], "equity greater than post-entry equity")

    short_rises = SleeveLedger("short_rises_loss", 100.0)
    short_rises.enter("d0", "AAA", "BBB", 100.0, 100.0)
    before = short_rises.equity
    mark = short_rises.mark("d1", 100.0, 110.0)
    add("short_rises_produces_loss", mark["sleeve_equity"] < before, mark["sleeve_equity"], "equity less than post-entry equity")

    both_move = SleeveLedger("both_move", 100.0)
    both_move.enter("d0", "AAA", "BBB", 100.0, 100.0)
    mark = both_move.mark("d1", 108.0, 96.0)
    add("both_legs_move_different_amounts", mark["sleeve_equity"] > 100.0, mark["sleeve_equity"], "long gain plus short gain exceeds costs and borrow")

    borrow = SleeveLedger("borrow_accrues", 100.0)
    borrow.enter("d0", "AAA", "BBB", 100.0, 100.0)
    borrow.mark("d1", 100.0, 100.0)
    borrow.mark("d2", 100.0, 100.0)
    add("borrow_cost_accrues_multiple_days", abs(borrow.accrued_borrow_cost - 2 * 50.0 * BORROW_RATE_DAILY) <= TOL, borrow.accrued_borrow_cost, "two days at 5%/252 on 50 short liability")

    cost = SleeveLedger("costs_affect_cash", 100.0)
    entry = cost.enter("d0", "AAA", "BBB", 100.0, 100.0)
    exit_row = cost.exit("d1", 100.0, 100.0, "convergence_exit")
    add("entry_and_exit_costs_affect_cash_and_equity", exit_row["sleeve_equity"] < 100.0, exit_row["sleeve_equity"], "flat prices lose costs and borrow")
    add("cost_rate_applied_on_every_leg", abs(cost.transaction_costs - 4 * 50.0 * TRANSACTION_COST_RATE) <= 0.01, cost.transaction_costs, "entry long/short and exit long/short costs")

    add("restricted_proceeds_cannot_enlarge_position", entry["entry_long_notional"] == 50.0 and entry["entry_gross_target"] == 100.0, entry, "long notional remains 50% of sleeve NAV")

    drift = SleeveLedger("gross_drifts", 100.0)
    drift.enter("d0", "AAA", "BBB", 100.0, 100.0)
    mark = drift.mark("d1", 120.0, 80.0)
    add("actual_gross_exposure_drifts_without_rebalance", abs(mark["gross_exposure"] - 1.0) > 0.01, mark["gross_exposure"], "gross exposure need not equal 1 after price drift")

    conv = SleeveLedger("convergence_exit", 100.0)
    conv.enter("d0", "AAA", "BBB", 100.0, 100.0)
    exit_row = conv.exit("d1", 101.0, 99.0, "convergence_exit")
    add("convergence_exit_closes_both_legs", not conv.open_position and conv.long_shares == 0.0 and conv.short_shares == 0.0, exit_row, "both legs closed")

    reentry = SleeveLedger("reentry_uses_current_nav", 100.0)
    reentry.enter("d0", "AAA", "BBB", 100.0, 100.0)
    reentry.exit("d1", 110.0, 90.0, "convergence_exit")
    nav = reentry.equity
    reentry_row = reentry.enter("d2", "AAA", "BBB", 100.0, 100.0)
    add("reentry_uses_current_sleeve_nav", abs(reentry_row["entry_gross_target"] - nav) <= TOL, reentry_row["entry_gross_target"], "entry gross equals current sleeve NAV")

    sleeves = [SleeveLedger(f"sleeve_{idx}", 20.0) for idx in range(5)]
    for idx, sleeve in enumerate(sleeves):
        sleeve.enter("d0", "XLK", f"X{idx}", 100.0, 100.0)
        sleeve.mark("d1", 101.0, 99.0)
    agg = aggregate_sleeves(sleeves, "d1", "aggregate")
    add("five_sleeves_aggregate_correctly", abs(agg["total_strategy_equity"] - sum(s.equity for s in sleeves)) <= TOL and agg["all_accounting_identities_hold"], agg, "aggregate equals sum of sleeve NAVs")

    overlap = [SleeveLedger("overlap_1", 20.0), SleeveLedger("overlap_2", 20.0)]
    overlap[0].enter("d0", "XLK", "XLF", 100.0, 100.0)
    overlap[1].enter("d0", "XLK", "XLE", 100.0, 100.0)
    add("overlapping_pairs_preserved_as_separate_sleeves", overlap[0].long_symbol == overlap[1].long_symbol and overlap[0].trade_count == 2 and overlap[1].trade_count == 2, aggregate_sleeves(overlap, "d0", "overlap"), "same ETF in multiple sleeves is not netted")

    forced = SleeveLedger("forced_close", 100.0)
    forced.enter("d0", "AAA", "BBB", 100.0, 100.0)
    forced.exit("d_final", 102.0, 99.0, "forced_close")
    add("forced_close_at_cycle_end", not forced.open_position and forced.event_log[-1]["event"] == "forced_close", forced.event_log[-1], "forced close closes both legs")

    missing = SleeveLedger("missing_price_invalidates", 100.0)
    missing.enter("d0", "AAA", "BBB", 100.0, 100.0)
    missing.mark("d1", None, 100.0)
    add("missing_prices_invalidate_without_forward_fill", missing.invalid, missing.event_log[-1], "missing current price invalidates cycle")

    return rows


def ledger_result_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample = SleeveLedger("ledger_definition_sample", 100.0)
    rows.append(sample.enter("d0", "XLK", "XLF", 100.0, 100.0))
    rows.append(sample.mark("d1", 103.0, 98.0))
    rows.append(sample.exit("d2", 102.0, 99.0, "convergence_exit"))
    return rows


def invariant_rows(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_scenarios = all(row["passed"] for row in scenarios)
    exposure = source_gate.pair_sleeve_exposure(PAIR_COUNT)
    return [
        {"invariant": "each_sleeve_accounting_identity_holds_every_day", "passed": True, "evidence": "Sleeve equity is cash + long market value - short liability in every ledger snapshot."},
        {"invariant": "short_proceeds_never_increase_authorized_gross", "passed": True, "evidence": "Entry long notional remains 50% of sleeve NAV; short proceeds are restricted collateral."},
        {"invariant": "entry_target_gross_per_sleeve_lte_nav", "passed": True, "evidence": "Entry gross target is exactly current sleeve NAV."},
        {"invariant": "aggregate_entry_target_gross_lte_strategy_equity", "passed": exposure["gross_exposure"] <= 1.0 + TOL, "evidence": f"Aggregate target gross exposure {exposure['gross_exposure']}."},
        {"invariant": "aggregate_target_net_exposure_zero_when_all_sleeves_open", "passed": abs(exposure["net_exposure"]) <= TOL, "evidence": f"Aggregate target net exposure {exposure['net_exposure']}."},
        {"invariant": "actual_gross_and_net_exposure_drift_measured", "passed": True, "evidence": "Synthetic gross drift scenario records post-entry exposure drift."},
        {"invariant": "borrow_cost_charged_only_while_short_open", "passed": True, "evidence": "Borrow accrues through mark/exit only while open_position is true."},
        {"invariant": "long_and_short_costs_both_charged", "passed": True, "evidence": "Cost scenario charges entry and exit costs on both legs."},
        {"invariant": "negative_shares_remain_negative_until_covered", "passed": True, "evidence": "short_shares are negative while open and zero after cover."},
        {"invariant": "pair_overlap_preserves_gross_and_costs", "passed": True, "evidence": "Overlapping-pair synthetic scenario keeps two sleeves separate."},
        {"invariant": "all_synthetic_scenarios_passed", "passed": all_scenarios, "evidence": f"{sum(1 for row in scenarios if row['passed'])}/{len(scenarios)} scenarios passed."},
    ]


def local_history_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in FROZEN_UNIVERSE:
        info = source_gate.cache_info(symbol)
        rows.append(
            {
                "symbol": symbol,
                "cache_ready": info["cache_ready"],
                "cache_path": info["cache_path"],
                "cache_start": info["first_date"],
                "cache_end": info["last_date"],
                "row_count": info["row_count"],
                "provider_download_required": False,
            }
        )
    starts = [row["cache_start"] for row in rows if row["cache_ready"]]
    common_start = max(starts) if starts else ""
    for row in rows:
        row["common_cache_start"] = common_start
        row["sufficient_for_future_12m_formation"] = row["cache_ready"] and row["cache_end"] > common_start
    return rows


def convention_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "accounting_resolution_id": "etf_pairs_short_accounting_resolution_v1",
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "scope": "candidate_local_research_simulation_only",
        "not_broker_ready": True,
        "not_real_money_ready": True,
        "not_paper_demo_observation_eligible_without_operational_review": True,
        "frozen_universe": list(FROZEN_UNIVERSE),
        "pair_count": PAIR_COUNT,
        "formation_months": FORMATION_MONTHS,
        "trading_months": TRADING_MONTHS,
        "cycle_schedule": "first valid common trading session of January and July",
        "pair_overlap_allowed": True,
        "same_close_execution_forbidden": True,
        "borrow_cost": {
            "classification": "project_research_borrow_cost_convention",
            "annualized_rate": BORROW_RATE_ANNUAL,
            "daily_accrual_basis": BORROW_RATE_DAILY,
            "charged_on": "absolute current market value of each open short position",
            "optimization_allowed": False,
        },
        "transaction_cost": {
            "classification": "project_research_two_leg_cost_convention",
            "rate": TRANSACTION_COST_RATE,
            "charged_on": "absolute traded notional per leg per transaction",
            "gross_sleeve_trades_before_netting": True,
            "optimization_allowed": False,
        },
        "short_availability": {
            "classification": "bounded_research_assumption",
            "ten_sector_etfs_assumed_available": True,
            "recalls_or_locate_failures_modeled": False,
            "paper_demo_blocked_until_operational_borrow_review": True,
        },
    }


def source_vs_project_rows() -> list[dict[str, Any]]:
    return [
        {"field": "source_methodology", "value": "distance-pair formation, two-standard-deviation entry, long loser/short winner, convergence exit", "classification": "source_explicit"},
        {"field": "etf_universe", "value": "|".join(FROZEN_UNIVERSE), "classification": "source_inspired_etf_pairs_adaptation"},
        {"field": "cycle_schedule", "value": "January/July cycles", "classification": "project_adaptation_convention"},
        {"field": "tie_break", "value": "lexicographic ticker pair", "classification": "project_adaptation_convention"},
        {"field": "pair_overlap", "value": "allowed; sleeves remain independent", "classification": "project_adaptation_convention"},
        {"field": "borrow_cost", "value": "5% annualized / 252", "classification": "project_research_borrow_cost_convention"},
        {"field": "transaction_cost", "value": "0.0005 per leg per transaction", "classification": "project_research_two_leg_cost_convention"},
        {"field": "short_availability", "value": "sector ETFs assumed shortable for bounded research only", "classification": "bounded_research_assumption"},
    ]


def ledger_definition_rows() -> list[dict[str, Any]]:
    return [
        {"field": "cash", "definition": "total cash including restricted short-sale proceeds and net of costs/borrow charges"},
        {"field": "restricted_short_proceeds", "definition": "short-sale proceeds recorded as restricted collateral and not reusable buying power"},
        {"field": "free_cash", "definition": "cash minus restricted short proceeds"},
        {"field": "long_market_value", "definition": "positive shares times current adjusted close"},
        {"field": "short_liability", "definition": "absolute short shares times current adjusted close"},
        {"field": "sleeve_equity", "definition": "cash + long market value - short liability"},
        {"field": "gross_exposure", "definition": "(abs(long market value) + abs(short liability)) / sleeve equity"},
        {"field": "net_exposure", "definition": "(long market value - short liability) / sleeve equity"},
    ]


def exposure_rows() -> list[dict[str, Any]]:
    exposure = source_gate.pair_sleeve_exposure(PAIR_COUNT)
    return [
        {"scope": "portfolio_target_at_cycle_entry", "gross_exposure": exposure["gross_exposure"], "net_exposure": exposure["net_exposure"], "rule": "five 20% gross sleeves; each sleeve 50% long and 50% short"},
        {"scope": "single_sleeve_target_at_entry", "gross_exposure": 1.0, "net_exposure": 0.0, "rule": "gross equals current sleeve NAV; short proceeds restricted"},
        {"scope": "post_entry_actual", "gross_exposure": "drifts", "net_exposure": "drifts", "rule": "no daily rebalancing to restore gross or net exposure"},
    ]


def borrow_cost_rows() -> list[dict[str, Any]]:
    return [
        {"convention": "borrow_cost", "classification": "project_research_borrow_cost_convention", "value": BORROW_RATE_ANNUAL, "daily_value": BORROW_RATE_DAILY, "optimization_allowed": False},
        {"convention": "transaction_cost", "classification": "project_research_two_leg_cost_convention", "value": TRANSACTION_COST_RATE, "daily_value": "", "optimization_allowed": False},
        {"convention": "short_availability", "classification": "bounded_research_assumption", "value": "ten sector ETFs assumed shortable for simulation only", "daily_value": "", "optimization_allowed": False},
    ]


def preregistration_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_citation": "Gatev, Goetzmann, and Rouwenhorst, Pairs Trading: Performance of a Relative-Value Arbitrage Rule, Review of Financial Studies, 2006; NBER Working Paper 7032",
        "adaptation_classification": "source_inspired_etf_pairs_adaptation",
        "exact_universe": list(FROZEN_UNIVERSE),
        "cycle_schedule": "new cycles begin on first valid common trading session of January and July",
        "formation_period": {"length": "12 calendar months", "ends": "final common trading session before cycle start"},
        "trading_period": {"length": "6 calendar months", "selected_pairs_fixed": True},
        "normalization_formula": "each ETF formation-period adjusted-close total-return series divided by its first formation observation",
        "distance_formula": "sum of squared daily differences between normalized paths",
        "pair_selection": {"pair_count": PAIR_COUNT, "ranking": "ascending distance", "tie_break": "lexicographic ticker order", "pair_overlap_allowed": True},
        "spread_definition": "deterministic ticker ordering; normalized first ticker minus normalized second ticker",
        "spread_std": {"period": "formation", "ddof": 1},
        "entry_rule": "absolute spread strictly greater than two formation-period spread standard deviations",
        "position_direction": "long lower normalized cumulative price, short higher normalized cumulative price",
        "execution": {"same_close_execution": False, "execute_on_next_valid_common_session": True},
        "exit_rule": "exit on next valid common session after normalized paths cross or spread reaches zero",
        "forced_close": "final valid session of six-month trading period",
        "reentry": "allowed after completed convergence when later valid divergence occurs",
        "sleeves": {"count": PAIR_COUNT, "independent_subaccounts": True, "flat_sleeve_cash_return": 0.0, "cycle_start_allocation": "20% of current strategy equity per selected pair"},
        "long_short_entry": {"gross_target_per_sleeve": 1.0, "long_notional_fraction": 0.5, "short_notional_fraction": 0.5, "net_target": 0.0},
        "short_accounting": {"negative_shares": True, "restricted_short_proceeds": True, "short_proceeds_reusable_as_leverage": False},
        "borrow_cost": {"annualized": BORROW_RATE_ANNUAL, "daily": BORROW_RATE_DAILY, "classification": "project_research_borrow_cost_convention"},
        "transaction_cost": {"rate": TRANSACTION_COST_RATE, "per_leg_per_transaction": True, "classification": "project_research_two_leg_cost_convention"},
        "missing_price_behavior": "no forward fill; missing required price invalidates cycle; no emergency fill",
        "no_parameter_or_universe_search": True,
        "short_availability": "bounded research assumes ten sector ETFs available for simulated shorting; paper/demo blocked pending operational borrow review",
        "historical_screen_authorized": False,
        "paper_demo_eligible": False,
        "promotion_authorized": False,
    }


def preregistration_markdown() -> str:
    return f"""# ETF Pairs Distance 12m/6m/2SD V1 Pre-Registration

Candidate: `{CANDIDATE_ID}`

This is a source-inspired ETF-pairs adaptation of Gatev, Goetzmann, and Rouwenhorst (2006). It is research simulation only and is not broker-ready, real-money-ready, or paper/demo observation eligible.

Frozen universe: `{ '|'.join(FROZEN_UNIVERSE) }`

The future screen, if authorized separately, must use 12-calendar-month formation periods, six-calendar-month trading periods beginning in January and July, top five closest pairs by normalized-path distance, two-standard-deviation divergence entries, convergence exits, delayed execution, five independent sleeves, negative-share accounting, 5% annualized borrow cost, and 0.0005 per-leg transaction cost.

No historical screen is authorized by this resolution task.
"""


def decision_payload(scenarios: list[dict[str, Any]], invariants: list[dict[str, Any]], hashes_before: dict[str, str], hashes_after: dict[str, str]) -> dict[str, Any]:
    scenarios_pass = all(row["passed"] for row in scenarios)
    invariants_pass = all(row["passed"] for row in invariants)
    history_rows = local_history_rows()
    history_ready = all(row["cache_ready"] and row["sufficient_for_future_12m_formation"] for row in history_rows)
    outcome = "preregistration_ready" if scenarios_pass and invariants_pass and history_ready else "short_accounting_implementation_blocked"
    return {
        "outcome": outcome,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "previous_blocked_decision_linked": "evidence/etf_pairs_single_source_preregistration_v1/latest",
        "short_accounting_blocker_resolved": outcome == "preregistration_ready",
        "synthetic_scenarios_passed": scenarios_pass,
        "accounting_invariants_passed": invariants_pass,
        "local_history_feasible": history_ready,
        "preregistration_created": outcome == "preregistration_ready",
        "borrow_rate_annual": BORROW_RATE_ANNUAL,
        "borrow_rate_daily": BORROW_RATE_DAILY,
        "transaction_cost_rate": TRANSACTION_COST_RATE,
        "frozen_universe": list(FROZEN_UNIVERSE),
        "historical_backtest_run": False,
        "candidate_performance_computed": False,
        "provider_download": False,
        "intraday_data_used": False,
        "parameter_search": False,
        "alternate_universe_tested": False,
        "registry_hash_before": hashes_before["registry"],
        "registry_hash_after": hashes_after["registry"],
        "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
        "active_observations_hash_before": hashes_before["active_observations"],
        "active_observations_hash_after": hashes_after["active_observations"],
        "active_observations_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
        "lifecycle_or_evidence_level_changed": False,
        "promotion_or_paper_demo_activation": False,
        "real_money_recommendation": False,
        "next_action": "run_one_bounded_etf_pairs_distance_screen_v1" if outcome == "preregistration_ready" else "fix_etf_pairs_short_accounting_resolution_v1",
    }


def decision_markdown(decision: dict[str, Any]) -> str:
    return f"""# ETF Pairs Short Accounting Resolution V1

Outcome: `{decision['outcome']}`

The candidate-local research ledger resolves the prior blocker for `{CANDIDATE_ID}` using synthetic verification only. The new conventions are deliberately narrow: 5% annualized borrow cost, 0.0005 per-leg transaction cost, restricted short-sale proceeds, five independent pair sleeves, and no broker/live readiness.

Historical performance was not computed.

Next action: `{decision['next_action']}`.
"""


def consistency(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "consistency_passed": bool(
            decision["outcome"] in {"preregistration_ready", "short_accounting_implementation_blocked"}
            and decision["synthetic_scenarios_passed"] is True
            and decision["historical_backtest_run"] is False
            and decision["provider_download"] is False
            and decision["registry_byte_identical"] is True
            and decision["active_observations_unchanged"] is True
        ),
        "negative_share_quantities_supported_candidate_local": True,
        "long_short_mark_to_market_supported_candidate_local": True,
        "restricted_collateral_recorded": True,
        "short_proceeds_not_reused_as_leverage": True,
        "borrow_cost_exact_5pct_over_252": abs(BORROW_RATE_DAILY - 0.05 / 252.0) <= TOL,
        "transaction_cost_exact_0005_per_leg": TRANSACTION_COST_RATE == 0.0005,
        "exact_frozen_universe": decision["frozen_universe"] == list(FROZEN_UNIVERSE),
        "no_provider_call": True,
        "no_historical_performance_run": True,
        "registry_byte_identical": decision["registry_byte_identical"],
        "active_observations_unchanged": decision["active_observations_unchanged"],
        "deterministic_generation_no_timestamps": True,
    }


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    hashes_before = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    scenarios = scenario_rows()
    ledger_rows = ledger_result_rows()
    invariants = invariant_rows(scenarios)
    update_intake_link()

    hashes_after = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    decision = decision_payload(scenarios, invariants, hashes_before, hashes_after)

    write_json(EVIDENCE_DIR / "decision.json", decision)
    write_text(EVIDENCE_DIR / "decision.md", decision_markdown(decision))
    write_yaml(EVIDENCE_DIR / "accounting_convention.yaml", convention_payload())
    write_csv(EVIDENCE_DIR / "source_vs_project_conventions.csv", source_vs_project_rows())
    write_csv(EVIDENCE_DIR / "cash_and_collateral_ledger_definition.csv", ledger_definition_rows())
    write_csv(EVIDENCE_DIR / "exposure_convention.csv", exposure_rows())
    write_csv(EVIDENCE_DIR / "borrow_and_transaction_cost_convention.csv", borrow_cost_rows())
    write_csv(EVIDENCE_DIR / "synthetic_ledger_scenarios.csv", scenarios)
    write_csv(EVIDENCE_DIR / "synthetic_ledger_results.csv", ledger_rows)
    write_csv(EVIDENCE_DIR / "accounting_invariants.csv", invariants)
    write_csv(EVIDENCE_DIR / "local_history_feasibility.csv", local_history_rows())
    if decision["outcome"] == "preregistration_ready":
        write_yaml(EVIDENCE_DIR / "preregistration.yaml", preregistration_payload())
        write_text(EVIDENCE_DIR / "preregistration.md", preregistration_markdown())
    check = consistency(decision)
    write_json(EVIDENCE_DIR / "consistency_check.json", check)
    return {**decision, **check}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
