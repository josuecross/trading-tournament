from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import fast_source_library_batch_v7 as v7
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


TASK_ID = "v7_candidate_diversifier_incremental_value_followup_v1"
MODE = "fast-progress"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
V7_DIR = ROOT / "evidence" / "research_recovery" / v7.BATCH_ID / "latest"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-10
PORTFOLIO_START = pd.Timestamp("2010-08-10")
PORTFOLIO_END = pd.Timestamp("2026-06-18")
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"

NEXT_REVIEW = "direction_owner_review_v7_diversifier_incremental_value_followup_v1"
NEXT_ALL_CLOSED = "refresh_strategy_source_library_v5"
NEXT_BLOCKED = "direction_owner_review_v7_diversifier_followup_block_v1"

EXPECTED_STRATEGY_IDS = (
    "kritzman_absorption_ratio_sector_spy_ief_v1",
    "gervais_kaniel_mingelgrin_high_volume_sector_v1",
)

V7_REQUIRED_FILES = (
    "batch_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "consistency_check.json",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)

FORBIDDEN_FLAGS = {
    "validation_or_robustness": False,
    "source_research_or_completion": False,
    "strategy_rule_parameter_instrument_or_execution_change": False,
    "result_driven_control_or_period_change": False,
    "lifecycle_or_registry_change": False,
    "promotion_or_paper_demo_action": False,
    "provider_download": False,
    "broker_account_order_or_real_money_action": False,
    "source_library_v5_started": False,
}

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "blocked_feasibility",
}

ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "excess_drawdown",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}


@dataclass(frozen=True)
class FollowupCard:
    strategy_id: str
    family_id: str
    display_name: str
    parent_trial_id: str
    prior_failure_reason: str
    candidate_portfolio_id: str
    same_purpose_control_id: str
    exposure_control_id: str
    controls: tuple[str, ...]
    simple_controls: tuple[str, ...]
    expected_sharpe: float
    expected_drawdown: float
    expected_primary_sharpe: float
    expected_primary_drawdown: float

    @property
    def trial_id(self) -> str:
        return f"{TASK_ID}__{self.strategy_id}__child"


CARDS = (
    FollowupCard(
        strategy_id=EXPECTED_STRATEGY_IDS[0],
        family_id="pca_systemic_fragility_regime",
        display_name="Sector Absorption-Ratio Fragility Regime",
        parent_trial_id=(
            "fast_source_v7__kritzman_absorption_ratio_sector_spy_ief_v1__canonical"
        ),
        prior_failure_reason="weak_vs_primary_control",
        candidate_portfolio_id=(
            "kritzman_absorption_ratio_sector_spy_ief_v1_candidate_20pct"
        ),
        same_purpose_control_id=(
            "average_pairwise_correlation_shift_spy_ief_v1_20pct_control"
        ),
        exposure_control_id=(
            "monthly_static_exposure_matched_SPY_IEF_20pct_control"
        ),
        controls=(
            "average_pairwise_correlation_shift_spy_ief_v1",
            "monthly_static_50_50_SPY_IEF",
            "monthly_static_exposure_matched_SPY_IEF",
            "IEF",
            "BIL",
        ),
        simple_controls=("IEF", "BIL"),
        expected_sharpe=0.871813,
        expected_drawdown=-0.176881,
        expected_primary_sharpe=0.888650,
        expected_primary_drawdown=-0.187235,
    ),
    FollowupCard(
        strategy_id=EXPECTED_STRATEGY_IDS[1],
        family_id="abnormal_volume_visibility_premium",
        display_name="High-Volume Sector Visibility Event",
        parent_trial_id=(
            "fast_source_v7__gervais_kaniel_mingelgrin_high_volume_sector_v1__canonical"
        ),
        prior_failure_reason="period_instability",
        candidate_portfolio_id=(
            "gervais_kaniel_mingelgrin_high_volume_sector_v1_candidate_20pct"
        ),
        same_purpose_control_id=(
            "absolute_return_shock_sector_event_v1_20pct_control"
        ),
        exposure_control_id=(
            "monthly_static_exposure_matched_SPY_BIL_20pct_control"
        ),
        controls=(
            "absolute_return_shock_sector_event_v1",
            "equal_weight_nine_sectors_during_event_windows",
            "monthly_static_exposure_matched_SPY_BIL",
            "BIL",
        ),
        simple_controls=("BIL",),
        expected_sharpe=0.883158,
        expected_drawdown=-0.207348,
        expected_primary_sharpe=0.816849,
        expected_primary_drawdown=-0.211545,
    ),
)

EXPECTED_REFERENCE_SHARPE = 0.837509
EXPECTED_REFERENCE_DRAWDOWN = -0.206373


def rel(path: str | Path) -> str:
    return v7.rel(path)


def file_hash(path: Path) -> str:
    return v7.file_hash(path)


def csv_value(value: Any) -> str:
    return v7.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    v7.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    v7.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    v7.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    v7.write_text(path, text)


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def aggregate_hash(hashes: dict[str, str]) -> str:
    material = "\n".join(f"{key}|{value}" for key, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def prior_evidence_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted((ROOT / "evidence").rglob("*")):
        if not path.is_file():
            continue
        if OUTPUT_DIR.resolve() in path.resolve().parents:
            continue
        files.append(path)
    return files


def evidence_identity_map(paths: Iterable[Path]) -> dict[str, str]:
    identities: dict[str, str] = {}
    for path in paths:
        stat = path.stat()
        material = f"{stat.st_size}|{stat.st_mtime_ns}"
        identities[rel(path)] = "sha256:" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return identities


def validate_authoritative_v7() -> dict[str, Any]:
    missing = [name for name in V7_REQUIRED_FILES if not (V7_DIR / name).exists()]
    if missing:
        raise RuntimeError(f"Missing authoritative V7 evidence: {missing}")
    trials = {
        row["strategy_id"]: row for row in read_csv(V7_DIR / "trial_ledger.csv")
    }
    outcomes = {
        row["strategy_id"]: row for row in read_csv(V7_DIR / "outcome_summary.csv")
    }
    portfolio_rows = read_csv(V7_DIR / "portfolio_contribution_results.csv")
    consistency = json.loads(
        (V7_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    for card in CARDS:
        trial = trials.get(card.strategy_id)
        outcome = outcomes.get(card.strategy_id)
        if not trial or not outcome:
            raise RuntimeError(f"Missing V7 parent evidence for {card.strategy_id}")
        if (
            trial["trial_id"] != card.parent_trial_id
            or trial["stage"] != "exploration"
            or trial["route"] != "standalone"
            or trial["outcome"] != "closed_exploration"
            or trial["failure_reason"] != card.prior_failure_reason
        ):
            raise RuntimeError(f"V7 parent trial drift for {card.strategy_id}")
    relevant = [
        row
        for row in portfolio_rows
        if row["strategy_id"] in EXPECTED_STRATEGY_IDS
        and row["cost_assumption_bps"] == "5"
    ]
    if not relevant:
        raise RuntimeError("V7 portfolio contribution rows unavailable")
    if {
        (row["evaluation_start"], row["evaluation_end"]) for row in relevant
    } != {("2010-08-10", "2026-06-18"), ("2010-08-10", "2018-07-11"), ("2018-07-12", "2026-06-18")}:
        raise RuntimeError("V7 portfolio period drift")
    if not consistency.get("consistency_passed"):
        raise RuntimeError("Authoritative V7 consistency check did not pass")
    return {
        "trials": trials,
        "outcomes": outcomes,
        "portfolio_rows": portfolio_rows,
        "consistency": consistency,
    }


def frozen_v7_card(strategy_id: str) -> v7.CandidateCard:
    return next(card for card in v7.CARDS if card.strategy_id == strategy_id)


def initial_buy_hold_events(
    index: pd.DatetimeIndex, columns: tuple[str, ...], symbol: str
) -> pd.DataFrame:
    target = {item: 0.0 for item in columns}
    target[symbol] = 1.0
    return accounting.initial_event(index, columns, target)


def reconstruct_sleeves(card: FollowupCard) -> dict[str, Any]:
    source_card = frozen_v7_card(card.strategy_id)
    prepared = v7.prepare_candidate(source_card)
    prices = prepared["prices"]
    events: dict[str, pd.DataFrame] = {
        "candidate": prepared["candidate_events"],
        **prepared["control_events"],
    }
    for symbol in card.simple_controls:
        events[symbol] = initial_buy_hold_events(
            prices.index, tuple(prices.columns), symbol
        )
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        for sleeve_id, target_events in events.items():
            paths[(sleeve_id, cost)] = accounting.simulate_path(
                prices,
                target_events,
                cost,
                prepared["timing_convention"],
            )
    if card.strategy_id == EXPECTED_STRATEGY_IDS[0]:
        exposure = float(
            prepared["control_events"][
                "monthly_static_exposure_matched_SPY_IEF"
            ].iloc[0]["SPY"]
        )
        expected = 0.641084462982
    else:
        exposure = float(
            prepared["control_events"][
                "monthly_static_exposure_matched_SPY_BIL"
            ].iloc[0]["SPY"]
        )
        expected = 0.15849843587069865
    if not math.isclose(exposure, expected, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"Frozen V7 exposure-control weight drift: {card.strategy_id}")
    return {
        "source_card": source_card,
        "prepared": prepared,
        "prices": prices,
        "sleeve_paths": paths,
        "exposure_matched_spy_weight": exposure,
    }


def portfolio_id(sleeve_id: str, card: FollowupCard) -> str:
    if sleeve_id == "candidate":
        return card.candidate_portfolio_id
    return f"{sleeve_id}_20pct_control"


def construct_portfolios(
    card: FollowupCard,
    reconstructed: dict[str, Any],
    reference: pd.Series,
) -> dict[tuple[str, float], dict[str, Any]]:
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        payloads[("frozen_reference_100pct", cost)] = (
            portfolio_accounting.reference_payload(reference, cost)
        )
        for sleeve_id in ("candidate", *card.controls):
            sleeve = reconstructed["sleeve_paths"][(sleeve_id, cost)]["returns"]
            aligned = pd.concat(
                [reference.rename("reference"), sleeve.rename("sleeve")],
                axis=1,
                join="inner",
            ).dropna()
            if (
                aligned.index.min() != PORTFOLIO_START
                or aligned.index.max() != PORTFOLIO_END
                or not aligned.index.equals(reference.index)
            ):
                raise RuntimeError(
                    f"Frozen portfolio date alignment failed for {card.strategy_id}"
                )
            identifier = portfolio_id(sleeve_id, card)
            payloads[(identifier, cost)] = (
                portfolio_accounting.simulate_two_component_portfolio(
                    aligned["reference"],
                    aligned["sleeve"],
                    identifier,
                    cost,
                )
            )
    return payloads


def period_definitions(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex | None]]:
    halves = v7.prior_batch.split_periods(index)
    return [("full_period", None), *halves]


def metrics(
    path: dict[str, Any], period: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    value = dict(v7.portfolio_metrics(path, period))
    value["rebalance_count"] = value["trade_or_rebalance_count"]
    return value


REPRODUCTION_METRICS = (
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
)


def reproduction_rows(
    card: FollowupCard,
    portfolios: dict[tuple[str, float], dict[str, Any]],
    authoritative_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], bool]:
    expected = {
        (row["portfolio_id"], row["period_label"]): row
        for row in authoritative_rows
        if row["strategy_id"] == card.strategy_id
        and row["cost_assumption_bps"] == "5"
        and row["portfolio_id"]
        in {
            "frozen_reference_100pct",
            card.candidate_portfolio_id,
            card.same_purpose_control_id,
        }
    }
    rows: list[dict[str, Any]] = []
    passed = True
    for identifier in (
        "frozen_reference_100pct",
        card.candidate_portfolio_id,
        card.same_purpose_control_id,
    ):
        path = portfolios[(identifier, PRIMARY_COST_BPS)]
        for label, period in period_definitions(path["returns"].index):
            current = metrics(path, period)
            source = expected[(identifier, label)]
            for metric in REPRODUCTION_METRICS:
                actual = float(current[metric])
                expected_value = float(source[metric])
                difference = actual - expected_value
                metric_pass = math.isclose(
                    actual,
                    expected_value,
                    rel_tol=0.0,
                    abs_tol=REPRODUCTION_TOLERANCE,
                )
                passed = passed and metric_pass
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "parent_trial_id": card.parent_trial_id,
                        "portfolio_id": identifier,
                        "period_label": label,
                        "metric": metric,
                        "v7_value": expected_value,
                        "recomputed_value": actual,
                        "difference": difference,
                        "tolerance": REPRODUCTION_TOLERANCE,
                        "reproduction_pass": metric_pass,
                    }
                )
    full_candidate = metrics(
        portfolios[(card.candidate_portfolio_id, PRIMARY_COST_BPS)]
    )
    full_primary = metrics(
        portfolios[(card.same_purpose_control_id, PRIMARY_COST_BPS)]
    )
    full_reference = metrics(
        portfolios[("frozen_reference_100pct", PRIMARY_COST_BPS)]
    )
    approximate = (
        math.isclose(
            full_candidate["sharpe_ratio"], card.expected_sharpe, abs_tol=1e-5
        )
        and math.isclose(
            full_candidate["maximum_drawdown"],
            card.expected_drawdown,
            abs_tol=1e-5,
        )
        and math.isclose(
            full_primary["sharpe_ratio"],
            card.expected_primary_sharpe,
            abs_tol=1e-5,
        )
        and math.isclose(
            full_primary["maximum_drawdown"],
            card.expected_primary_drawdown,
            abs_tol=1e-5,
        )
        and math.isclose(
            full_reference["sharpe_ratio"],
            EXPECTED_REFERENCE_SHARPE,
            abs_tol=1e-5,
        )
        and math.isclose(
            full_reference["maximum_drawdown"],
            EXPECTED_REFERENCE_DRAWDOWN,
            abs_tol=1e-5,
        )
    )
    rows.append(
        {
            "strategy_id": card.strategy_id,
            "parent_trial_id": card.parent_trial_id,
            "portfolio_id": "predeclared_approximate_values",
            "period_label": "full_period",
            "metric": "aggregate_approximate_expectation",
            "v7_value": "prompt_expected_values",
            "recomputed_value": "recomputed_full_period_values",
            "difference": "",
            "tolerance": 1e-5,
            "reproduction_pass": approximate,
        }
    )
    return rows, bool(passed and approximate)


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return v7.dominates(control, candidate)


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return (
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"])
    )


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return (
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def simple_replication(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return dominates(control, candidate) or (
        abs(
            float(control["sharpe_ratio"]) - float(candidate["sharpe_ratio"])
        )
        <= 0.01
        and float(control["cagr"]) >= float(candidate["cagr"])
        and float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"])
    )


def classify(result: dict[str, Any]) -> None:
    if not result["reproduction_pass"]:
        result.update(
            outcome="blocked_feasibility",
            failure_reason="data_or_comparability_failure",
            decision_reason="V7 portfolio reproduction failed",
        )
        return
    card: FollowupCard = result["card"]
    portfolios = result["portfolios"]
    candidate = metrics(
        portfolios[(card.candidate_portfolio_id, PRIMARY_COST_BPS)]
    )
    reference = metrics(
        portfolios[("frozen_reference_100pct", PRIMARY_COST_BPS)]
    )
    controls = {
        control_id: metrics(
            portfolios[(portfolio_id(control_id, card), PRIMARY_COST_BPS)]
        )
        for control_id in card.controls
    }
    all_metrics = [candidate, reference, *controls.values()]
    if not all(value["invariant_pass"] for value in all_metrics):
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="portfolio numeric, timing, weight, or exposure invariant failed",
        )
        return
    improves_sharpe = candidate["sharpe_ratio"] > reference["sharpe_ratio"]
    improves_drawdown = candidate["maximum_drawdown"] > reference["maximum_drawdown"]
    if not (improves_sharpe or improves_drawdown) or worse_on_both(
        candidate, reference
    ):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="candidate does not incrementally improve the frozen reference",
        )
        return
    dominating = [
        control_id
        for control_id, control in controls.items()
        if dominates(control, candidate)
    ]
    if dominating:
        result.update(
            outcome="closed_exploration",
            failure_reason=(
                "weak_vs_primary_control"
                if card.controls[0] in dominating
                else "benchmark_like_behavior"
            ),
            decision_reason="80/20 control dominates candidate: " + ",".join(dominating),
        )
        return
    primary = controls[card.controls[0]]
    exposure = controls[
        card.exposure_control_id.removesuffix("_20pct_control")
    ]
    if not material_advantage(candidate, primary):
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason="full-period advantage below materiality versus same-purpose control",
        )
        return
    if not material_advantage(candidate, exposure):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="full-period advantage below materiality versus exposure-matched control",
        )
        return
    critical_ids = (
        card.same_purpose_control_id,
        card.exposure_control_id,
    )
    for label, period in v7.prior_batch.split_periods(
        portfolios[(card.candidate_portfolio_id, PRIMARY_COST_BPS)]["returns"].index
    ):
        candidate_half = metrics(
            portfolios[(card.candidate_portfolio_id, PRIMARY_COST_BPS)], period
        )
        for critical_id in critical_ids:
            control_half = metrics(
                portfolios[(critical_id, PRIMARY_COST_BPS)], period
            )
            if worse_on_both(candidate_half, control_half):
                result.update(
                    outcome="closed_exploration",
                    failure_reason="period_instability",
                    decision_reason=(
                        f"candidate worse on Sharpe and drawdown versus {critical_id} "
                        f"in {label}"
                    ),
                )
                return
    replicated = [
        control_id
        for control_id in card.simple_controls
        if simple_replication(controls[control_id], candidate)
    ]
    if replicated:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="simple IEF/BIL sleeve economically replicates result: "
            + ",".join(replicated),
        )
        return
    candidate_10 = metrics(portfolios[(card.candidate_portfolio_id, 10.0)])
    for critical_id in critical_ids:
        control_10 = metrics(portfolios[(critical_id, 10.0)])
        if worse_on_both(candidate_10, control_10):
            result.update(
                outcome="closed_exploration",
                failure_reason="cost_drag",
                decision_reason=(
                    f"10-bps candidate unfavorable on Sharpe and drawdown versus "
                    f"{critical_id}"
                ),
            )
            return
    result.update(
        outcome="exploratory_followup_candidate_diversifier",
        failure_reason="",
        decision_reason="all preregistered diversifier incremental-value gates passed",
    )


def candidate_next_action(result: dict[str, Any]) -> str:
    if result["outcome"] == "exploratory_followup_candidate_diversifier":
        return f"direction_owner_review_{result['card'].strategy_id}_diversifier_followup"
    if result["outcome"] == "closed_exploration":
        return "retain_V7_standalone_closure_and_close_diversifier_child"
    return f"direction_owner_review_{result['card'].strategy_id}_followup_block"


def strategy_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: FollowupCard = result["card"]
        source = result["reconstructed"]["source_card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": source.strategy_architecture,
                "source_or_research_lineage": source.source_or_research_lineage,
                "instrument_universe": source.universe,
                "parameters": source.parameters,
                "benchmark_or_control": card.controls,
                "stage": STAGE,
                "evaluation_route": "diversifier_only",
                "trial_id": card.trial_id,
                "parent_trial_id": card.parent_trial_id,
                "adaptation_label": "exploratory_variant",
                "prior_standalone_stage": "exploration",
                "prior_standalone_route": "standalone",
                "prior_standalone_outcome": "closed_exploration",
                "prior_standalone_failure_reason": card.prior_failure_reason,
                "prior_standalone_outcome_changed": False,
                "authoritative_lifecycle_changed": False,
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": candidate_next_action(result),
            }
        )
    return rows


def trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: FollowupCard = result["card"]
        source = result["reconstructed"]["source_card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "experiment_trial",
                "strategy_architecture": source.strategy_architecture,
                "source_or_research_lineage": source.source_or_research_lineage,
                "instrument_universe": source.universe,
                "parameters": source.parameters,
                "benchmark_or_control": card.controls,
                "stage": STAGE,
                "evaluation_route": "diversifier_only",
                "trial_id": card.trial_id,
                "parent_trial_id": card.parent_trial_id,
                "adaptation_label": "exploratory_variant",
                "changed_fields_from_parent": (
                    "evaluation_route_and_predeclared_portfolio_controls_only"
                ),
                "strategy_rule_changed": False,
                "parameters_changed": False,
                "instruments_changed": False,
                "execution_changed": False,
                "cost_model_changed": False,
                "source_rule_changed": False,
                "portfolio_route_changed": True,
                "result_driven_parameter_change": False,
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": candidate_next_action(result),
                "counted_as_new_strategy": False,
                "counted_as_new_trial": True,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        definitions = (
            ("frozen_current_active_vm_dsr_usci_combo", "frozen_reference"),
            *[
                (
                    control_id,
                    "frozen_same_purpose_control"
                    if position == 0
                    else (
                        "frozen_exposure_matched_control"
                        if portfolio_id(control_id, card)
                        == card.exposure_control_id
                        else "static_or_simple_control"
                    ),
                )
                for position, control_id in enumerate(card.controls)
            ],
        )
        for control_id, role in definitions:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": role,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_risky_exposure",
    "turnover",
    "trade_or_rebalance_count",
    "rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


def result_tables(
    results: list[dict[str, Any]]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    full: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        card: FollowupCard = result["card"]
        for (identifier, cost), path in sorted(result["portfolios"].items()):
            role = (
                "frozen_reference"
                if identifier == "frozen_reference_100pct"
                else (
                    "candidate"
                    if identifier == card.candidate_portfolio_id
                    else "benchmark_control"
                )
            )
            for label, period in period_definitions(path["returns"].index):
                value = metrics(path, period)
                row = {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "portfolio_id": identifier,
                    "record_role": role,
                    "portfolio_construction": "monthly_rebalanced_80_20",
                    "cost_assumption_bps": cost,
                    "period_label": label,
                    "period_role": (
                        "full_period_exploration"
                        if label == "full_period"
                        else "exact_V7_chronological_half_not_clean_sealed_untouched_or_validation"
                    ),
                    **value,
                }
                (full if label == "full_period" else halves).append(row)
            full_metrics = metrics(path)
            sleeve_id = next(
                (
                    sleeve
                    for sleeve in ("candidate", *card.controls)
                    if portfolio_id(sleeve, card) == identifier
                ),
                "",
            )
            sleeve_path = (
                result["reconstructed"]["sleeve_paths"].get((sleeve_id, cost))
                if sleeve_id
                else None
            )
            embedded_turnover = (
                float(sleeve_path["turnover"].sum()) if sleeve_path else 0.0
            )
            embedded_cost = float(sleeve_path["cost"].sum()) if sleeve_path else 0.0
            turnover.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "portfolio_id": identifier,
                    "cost_assumption_bps": cost,
                    "outer_portfolio_one_way_turnover": full_metrics["turnover"],
                    "embedded_sleeve_one_way_turnover": embedded_turnover,
                    "embedded_sleeve_cost_drag": embedded_cost,
                    "outer_portfolio_transaction_cost_drag": full_metrics[
                        "transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "natural_drift_between_rebalances": True,
                    "fixed_weight_daily_return_blend_used": False,
                }
            )
            invariants.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "portfolio_id": identifier,
                    "cost_assumption_bps": cost,
                    "explicit_zero_weights": True,
                    "natural_drift_between_rebalances": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "leverage_or_shorting_used": False,
                    "fixed_weight_daily_return_blend_used": False,
                    **{
                        field: full_metrics[field]
                        for field in (
                            "maximum_gross_exposure",
                            "maximum_daily_weight_sum",
                            "numeric_invariant_status",
                            "timing_invariant_status",
                            "exposure_invariant_status",
                            "weight_invariant_status",
                            "invariant_pass",
                        )
                    },
                }
            )
    return full, halves, turnover, invariants


def comparison_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: FollowupCard = result["card"]
        for cost in COST_BPS:
            candidate_path = result["portfolios"][
                (card.candidate_portfolio_id, cost)
            ]
            for label, period in period_definitions(candidate_path["returns"].index):
                candidate = metrics(candidate_path, period)
                for identifier in (
                    "frozen_reference_100pct",
                    *[
                        portfolio_id(control_id, card)
                        for control_id in card.controls
                    ],
                ):
                    control = metrics(result["portfolios"][(identifier, cost)], period)
                    rows.append(
                        {
                            "strategy_id": card.strategy_id,
                            "trial_id": card.trial_id,
                            "cost_assumption_bps": cost,
                            "period_label": label,
                            "candidate_portfolio_id": card.candidate_portfolio_id,
                            "comparison_portfolio_id": identifier,
                            "comparison_role": (
                                "frozen_reference"
                                if identifier == "frozen_reference_100pct"
                                else (
                                    "critical_same_purpose"
                                    if identifier == card.same_purpose_control_id
                                    else (
                                        "critical_exposure_matched"
                                        if identifier == card.exposure_control_id
                                        else "static_or_simple_control"
                                    )
                                )
                            ),
                            "cagr_difference": candidate["cagr"] - control["cagr"],
                            "sharpe_difference": (
                                candidate["sharpe_ratio"]
                                - control["sharpe_ratio"]
                            ),
                            "maximum_drawdown_difference": (
                                candidate["maximum_drawdown"]
                                - control["maximum_drawdown"]
                            ),
                            "control_dominates_candidate": dominates(
                                control, candidate
                            ),
                            "candidate_material_advantage": material_advantage(
                                candidate, control
                            ),
                            "candidate_worse_on_sharpe_and_drawdown": worse_on_both(
                                candidate, control
                            ),
                            "simple_replication": (
                                simple_replication(control, candidate)
                                if identifier
                                in {
                                    portfolio_id(value, card)
                                    for value in card.simple_controls
                                }
                                else False
                            ),
                        }
                    )
    return rows


def batch_next_action(results: list[dict[str, Any]]) -> str:
    if any(
        result["outcome"] == "exploratory_followup_candidate_diversifier"
        for result in results
    ):
        return NEXT_REVIEW
    if all(result["outcome"] == "blocked_feasibility" for result in results):
        return NEXT_BLOCKED
    return NEXT_ALL_CLOSED


def deterministic_core_hash() -> str:
    material = [
        {
            "strategy_id": card.strategy_id,
            "parent_trial_id": card.parent_trial_id,
            "candidate_portfolio_id": card.candidate_portfolio_id,
            "same_purpose_control_id": card.same_purpose_control_id,
            "exposure_control_id": card.exposure_control_id,
            "controls": card.controls,
            "simple_controls": card.simple_controls,
            "portfolio_start": PORTFOLIO_START.date().isoformat(),
            "portfolio_end": PORTFOLIO_END.date().isoformat(),
            "costs": COST_BPS,
            "route": "diversifier_only",
        }
        for card in CARDS
    ]
    return "sha256:" + hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_report(
    results: list[dict[str, Any]], next_action: str, funnel: dict[str, Any]
) -> str:
    lines = [
        "# V7 Candidate Diversifier Incremental-Value Follow-up V1",
        "",
        "## Scope",
        "",
        "Exactly two closed V7 standalone configurations were carried forward into "
        "two new diversifier-only exploratory child trials. Their strategy rules, "
        "parameters, instruments, timing, cost model, and standalone outcomes were "
        "not changed.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['card'].strategy_id}`: `{result['outcome']}` "
            f"(`{result['failure_reason'] or 'none'}`; {result['decision_reason']})"
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "- V7 portfolio rows reproduced before the additional controls were assessed.",
            "- Period: `2010-08-10` through `2026-06-18`.",
            "- Primary cost: `5 bps`; diagnostics: `0` and `10 bps`.",
            "- Portfolios use monthly 80/20 targets, natural drift, following-session-close execution, actual turnover, and cost deductions.",
            "- Chronological halves are exploratory diagnostics, not validation or holdouts.",
            "",
            "## Entity Counts",
            "",
            f"- Existing strategy identities: `{funnel['existing_strategy_identities']}`",
            f"- New child trials: `{funnel['new_child_experiment_trials']}`",
            f"- Benchmark references: `{funnel['benchmark_references']}`",
            f"- Process tasks: `{funnel['process_tasks']}`",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action was recorded and not executed.",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    if tuple(card.strategy_id for card in CARDS) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Follow-up candidate scope drift")
    authoritative = validate_authoritative_v7()
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_paths = [
        ROOT / "data" / "cache" / f"{symbol}.csv"
        for symbol in v7.COMMON_REQUIRED_SYMBOLS
    ]
    cache_before = map_hashes(cache_paths)
    v7_paths = [V7_DIR / name for name in V7_REQUIRED_FILES]
    v7_hashes_before = map_hashes(v7_paths)
    prior_files = prior_evidence_files()
    prior_before = evidence_identity_map(prior_files)
    prior_aggregate_before = aggregate_hash(prior_before)

    clean_output()
    reference = market.active_vm_dsr_usci_reference_returns().loc[
        PORTFOLIO_START:PORTFOLIO_END
    ]
    if (
        reference.index.min() != PORTFOLIO_START
        or reference.index.max() != PORTFOLIO_END
    ):
        raise RuntimeError("Frozen reference period is unavailable")

    results: list[dict[str, Any]] = []
    reproduction: list[dict[str, Any]] = []
    for card in CARDS:
        reconstructed = reconstruct_sleeves(card)
        portfolios = construct_portfolios(card, reconstructed, reference)
        reproduction_part, reproduction_pass = reproduction_rows(
            card, portfolios, authoritative["portfolio_rows"]
        )
        reproduction.extend(reproduction_part)
        result = {
            "card": card,
            "reconstructed": reconstructed,
            "portfolios": portfolios,
            "reproduction_pass": reproduction_pass,
            "outcome": "",
            "failure_reason": "",
            "decision_reason": "",
        }
        classify(result)
        results.append(result)

    next_action = batch_next_action(results)
    strategies = strategy_rows(results)
    trials = trial_rows(results)
    benchmarks = benchmark_rows()
    full, halves, turnover, invariants = result_tables(results)
    comparisons = comparison_rows(results)
    outcomes = [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "trial_id": result["card"].trial_id,
            "parent_trial_id": result["card"].parent_trial_id,
            "stage": STAGE,
            "evaluation_route": "diversifier_only",
            "prior_standalone_outcome": "closed_exploration",
            "prior_standalone_outcome_changed": False,
            "reproduction_pass": result["reproduction_pass"],
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "next_action": candidate_next_action(result),
            "validation_claimed": False,
            "paper_demo_eligible": False,
        }
        for result in results
    ]
    failures = [
        {
            "strategy_id": result["card"].strategy_id,
            "trial_id": result["card"].trial_id,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
        }
        for result in results
        if result["failure_reason"]
    ]
    next_rows = [
        {
            "scope": "child_trial",
            "strategy_id": result["card"].strategy_id,
            "trial_id": result["card"].trial_id,
            "outcome": result["outcome"],
            "exact_next_action": candidate_next_action(result),
            "execute_in_this_task": False,
        }
        for result in results
    ]
    next_rows.append(
        {
            "scope": "task",
            "strategy_id": "",
            "trial_id": "",
            "outcome": "followup_completed",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }
    )
    process = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "followup_completed",
            "exact_next_action": next_action,
            "strategy_counted": False,
            "trial_counted": False,
            "execute_next_action_now": False,
        }
    ]
    definitions: list[dict[str, Any]] = []
    for result in results:
        card: FollowupCard = result["card"]
        exposure = result["reconstructed"]["exposure_matched_spy_weight"]
        for identifier in (
            "frozen_reference_100pct",
            card.candidate_portfolio_id,
            *[portfolio_id(control_id, card) for control_id in card.controls],
        ):
            definitions.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "portfolio_id": identifier,
                    "construction": (
                        "100pct_frozen_reference"
                        if identifier == "frozen_reference_100pct"
                        else "monthly_rebalanced_80pct_reference_plus_20pct_frozen_sleeve"
                    ),
                    "reference_weight": (
                        1.0 if identifier == "frozen_reference_100pct" else 0.8
                    ),
                    "sleeve_weight": (
                        0.0 if identifier == "frozen_reference_100pct" else 0.2
                    ),
                    "exposure_matched_SPY_weight": (
                        exposure
                        if "exposure_matched" in identifier
                        else ""
                    ),
                    "natural_drift": True,
                    "rebalance_signal": "month_end_close",
                    "execution": "following_session_close",
                    "costs_bps": COST_BPS,
                    "optimized": False,
                }
            )

    funnel = {
        "existing_strategy_identities": 2,
        "prior_standalone_trials_carried_as_parent_references": 2,
        "new_child_experiment_trials": 2,
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "exploratory_followup_candidate_diversifier": sum(
            result["outcome"] == "exploratory_followup_candidate_diversifier"
            for result in results
        ),
        "closed_exploration": sum(
            result["outcome"] == "closed_exploration" for result in results
        ),
        "blocked_feasibility": sum(
            result["outcome"] == "blocked_feasibility" for result in results
        ),
        "outcome_count_reconciles": len(results) == 2,
        "exact_next_action": next_action,
    }

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_after = map_hashes(cache_paths)
    v7_hashes_after = map_hashes(v7_paths)
    prior_after = evidence_identity_map(prior_files)
    prior_aggregate_after = aggregate_hash(prior_after)
    metadata_complete = all(
        all(
            row[field] not in ("", "unknown", "unmapped", None)
            for field in (
                "strategy_id",
                "family_id",
                "display_name",
                "entity_type",
                "strategy_architecture",
                "source_or_research_lineage",
                "instrument_universe",
                "parameters",
                "benchmark_or_control",
                "stage",
                "trial_id",
                "parent_trial_id",
                "adaptation_label",
                "outcome",
                "next_action",
            )
        )
        for row in strategies + trials
    )
    all_invariants = all(row["invariant_pass"] for row in invariants)
    consistency = {
        "status": "pass",
        "consistency_passed": bool(
            tuple(result["card"].strategy_id for result in results)
            == EXPECTED_STRATEGY_IDS
            and len(strategies) == len(trials) == 2
            and len({row["trial_id"] for row in trials}) == 2
            and all(row["parent_trial_id"] for row in trials)
            and all(row["adaptation_label"] == "exploratory_variant" for row in trials)
            and metadata_complete
            and all(result["outcome"] in ALLOWED_OUTCOMES for result in results)
            and all(
                result["failure_reason"] in ALLOWED_FAILURE_REASONS
                for result in results
            )
            and protected_before == protected_after
            and cache_before == cache_after
            and v7_hashes_before == v7_hashes_after
            and prior_aggregate_before == prior_aggregate_after
            and all_invariants
            and funnel["outcome_count_reconciles"]
            and not any(FORBIDDEN_FLAGS.values())
        ),
        "exact_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "exactly_two_existing_strategy_identities": len(strategies) == 2,
        "exactly_two_new_child_trials": len(trials) == 2,
        "no_new_strategy_id_created": True,
        "parent_trial_ids": [card.parent_trial_id for card in CARDS],
        "child_trial_ids": [card.trial_id for card in CARDS],
        "child_lineage_fields_frozen": all(
            row["changed_fields_from_parent"]
            == "evaluation_route_and_predeclared_portfolio_controls_only"
            and not row["strategy_rule_changed"]
            and not row["parameters_changed"]
            and not row["instruments_changed"]
            and not row["execution_changed"]
            and not row["cost_model_changed"]
            and not row["source_rule_changed"]
            and row["portfolio_route_changed"]
            and not row["result_driven_parameter_change"]
            for row in trials
        ),
        "required_metadata_complete": metadata_complete,
        "V7_reproduction_passed_by_strategy": {
            result["card"].strategy_id: result["reproduction_pass"]
            for result in results
        },
        "frozen_portfolio_start": PORTFOLIO_START.date().isoformat(),
        "frozen_portfolio_end": PORTFOLIO_END.date().isoformat(),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "cache_unchanged": cache_before == cache_after,
        "V7_evidence_hashes_before": v7_hashes_before,
        "V7_evidence_hashes_after": v7_hashes_after,
        "V7_evidence_unchanged": v7_hashes_before == v7_hashes_after,
        "prior_evidence_file_count": len(prior_files),
        "prior_evidence_reconciliation_method": (
            "deterministic_path_size_mtime_identity_manifest"
        ),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_aggregate_before == prior_aggregate_after,
        "all_portfolio_invariants_passed": all_invariants,
        "monthly_rebalanced_80_20_with_natural_drift": True,
        "fixed_weight_daily_return_blend_used": False,
        "authoritative_lifecycle_changed": False,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "deterministic_frozen_core_hash": deterministic_core_hash(),
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    if not consistency["consistency_passed"]:
        consistency["status"] = "fail"

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "existing_strategy_identity_count": 2,
        "new_child_experiment_trial_count": 2,
        "evaluation_route": "diversifier_only",
        "portfolio_start": PORTFOLIO_START.date().isoformat(),
        "portfolio_end": PORTFOLIO_END.date().isoformat(),
        "portfolio_construction": "monthly_rebalanced_80_20",
        "cost_assumptions_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "reproduction_tolerance": REPRODUCTION_TOLERANCE,
        "prior_standalone_outcomes_changed": False,
        "validation_claimed": False,
        "authoritative_lifecycle_changed": False,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", process, list(process[0]))
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        list(reproduction[0]),
    )
    result_fields = [
        "strategy_id",
        "trial_id",
        "portfolio_id",
        "record_role",
        "portfolio_construction",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "full_period_portfolio_results.csv",
        full,
        result_fields,
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_portfolio_results.csv",
        halves,
        result_fields,
    )
    write_csv(
        OUTPUT_DIR / "portfolio_control_definitions.csv",
        definitions,
        list(definitions[0]),
    )
    write_csv(
        OUTPUT_DIR / "incremental_value_comparison.csv",
        comparisons,
        list(comparisons[0]),
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover,
        list(turnover[0]),
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariants,
        list(invariants[0]),
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        outcomes,
        list(outcomes[0]),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "failure_reason",
            "decision_reason",
        ],
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcomes, list(outcomes[0]))
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "followup_report.md",
        build_report(results, next_action, funnel),
    )
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "followup_candidate_count": funnel[
            "exploratory_followup_candidate_diversifier"
        ],
        "exact_next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
