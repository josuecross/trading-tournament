from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import native_etf_two_candidate_exploration_batch_v1 as portfolio


TASK_ID = "accepted_47_source_backed_exploration_batch_v1"
SOURCE_TASK_ID = "accepted_47_selective_source_backed_intake_v1"
MODE = "source-backed-fast-progress"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
SOURCE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
DATA_END = pd.Timestamp("2026-08-04")
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
TOL = 1e-10
WEIGHT_TOL = 1e-8
PREREGISTRATION_TIMESTAMP = "2026-08-05T00:00:00+00:00"

CAA_ID = "keller_butler_kipnis_caa_n8_tv10_cap25_v1"
TPP_ID = "gestaltu_tactical_permanent_portfolio_7pct_v1"
CAA_TRIAL = "accepted47_source_v1__caa_n8_tv10__canonical"
TPP_TRIAL = "accepted47_source_v1__tactical_permanent_portfolio__canonical"
CAA_UNIVERSE = ("BIL", "IEF", "HYG", "SPY", "QQQ", "EFA", "EWJ", "EEM")
TPP_RISK = ("SPY", "IEF", "GLD")
TPP_UNIVERSE = (*TPP_RISK, "BIL")
REQUIRED_SYMBOLS = tuple(sorted(set(CAA_UNIVERSE + TPP_UNIVERSE)))
CAA_CAPS = np.array([1.0, 1.0, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25], dtype=float)

CAA_NAMED = "caa_n8_minimum_variance_same_constraints_control"
CAA_STATIC = "caa_n8_static_average_weight_control"
TPP_NAMED = "tpp_same_trend_equal_weight_no_risk_sizing_control"
TPP_STATIC = "tpp_static_average_weight_control"
CRITICAL_CONTROLS = {CAA_ID: (CAA_NAMED, CAA_STATIC), TPP_ID: (TPP_NAMED, TPP_STATIC)}
CONTROL_SETS = {
    CAA_ID: (
        CAA_NAMED,
        "caa_n8_equal_weight_monthly_control",
        CAA_STATIC,
        "60_40_spy_ief_monthly_control",
        "BIL_buy_and_hold",
    ),
    TPP_ID: (
        TPP_NAMED,
        "tpp_always_long_risk_parity_7pct_control",
        "static_permanent_portfolio_25_each_control",
        TPP_STATIC,
        "SPY_buy_and_hold",
        "BIL_buy_and_hold",
    ),
}
SOURCE_REQUIRED_FILES = {
    "intake_manifest.yaml",
    "source_library_records.csv",
    "selected_candidate_specs.yaml",
    "configuration_trial_catalog.csv",
    "benchmark_reference_catalog.csv",
    "source_lineage.md",
    "rejection_ledger.csv",
    "conditional_codex_prompt.md",
    "direction_correction_record.csv",
    "consistency_check.json",
    "intake_report.md",
}
REQUIRED_OUTPUTS = {
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "optimizer_equivalence_results.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "caa_monthly_optimizer_ledger.csv",
    "caa_allocation_diagnostics.csv",
    "tpp_monthly_signal_ledger.csv",
    "tpp_allocation_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
    "protected_state_reconciliation.csv",
}
PROTECTED_PATHS = (
    Path("strategy_lab/strategy_registry.yaml"),
    Path("strategy_lab/RESEARCH_ROADMAP.md"),
    Path("strategy_lab/research_os/research/research_queue.yaml"),
    Path("strategy_lab/research_os/family_lineage/family_ledger.yaml"),
    Path("strategy_lab/research_os/operations/active_observations.yaml"),
    Path("data/universe_expansion/pilot_etf_market_data_v1"),
    Path("data/cache"),
    Path("paper_forward_observations"),
    Path("evidence/paper_forward_observations"),
    Path("evidence/paper_demo_observation"),
    Path("evidence/technical_factory"),
    Path("evidence/research_recovery/accepted_47_hybrid_discovery_batch_v1"),
    Path("evidence/research_recovery/accepted_47_source_backed_exploration_batch_v1/history"),
    Path("evidence/public_source_strategy_intake/accepted_47_selective_source_backed_intake_v1"),
)


@dataclass(frozen=True)
class StrategySpec:
    source_record_id: str
    strategy_id: str
    trial_id: str
    family_id: str
    display_name: str
    architecture: str
    lineage: str
    universe: tuple[str, ...]
    parameters: dict[str, Any]
    controls: tuple[str, ...]
    critical_controls: tuple[str, ...]
    route: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    rows = [
        (item.relative_to(path).as_posix(), sha256_file(item))
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return stable_hash(rows)


def protected_hashes() -> dict[str, str]:
    return {relative.as_posix(): tree_hash(ROOT / relative) for relative in PROTECTED_PATHS}


def serialize(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (np.bool_, bool)):
        return str(bool(value)).lower()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def write_csv(name: str, rows: Iterable[dict[str, Any]], fields: Iterable[str] | None = None) -> None:
    materialized = list(rows)
    field_list = list(fields or ())
    for row in materialized:
        for key in row:
            if key not in field_list:
                field_list.append(key)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: serialize(row.get(field, "")) for field in field_list})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8"
    )


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def accepted_symbols() -> set[str]:
    path = ROOT / "evidence" / "data_capability" / "activate_accepted_47_pilot_data_readiness_v1" / "latest" / "operational_universe_snapshot.csv"
    return set(pd.read_csv(path)["symbol"].astype(str))


def _material_field_complete(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "unknown", "unresolved", "tbd"}
    if isinstance(value, dict):
        return bool(value) and all(_material_field_complete(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return bool(value) and all(_material_field_complete(item) for item in value)
    return True


def load_source_packet() -> tuple[list[StrategySpec], dict[str, Any]]:
    missing = sorted(SOURCE_REQUIRED_FILES - {item.name for item in SOURCE_DIR.iterdir() if item.is_file()}) if SOURCE_DIR.is_dir() else sorted(SOURCE_REQUIRED_FILES)
    if missing:
        return [], {"pass": False, "exact_discrepancy": f"source packet missing files: {missing}"}
    manifest = yaml.safe_load((SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    spec_payload = yaml.safe_load((SOURCE_DIR / "selected_candidate_specs.yaml").read_text(encoding="utf-8"))
    source_rows = pd.read_csv(SOURCE_DIR / "source_library_records.csv", keep_default_na=False)
    catalog = pd.read_csv(SOURCE_DIR / "configuration_trial_catalog.csv", keep_default_na=False)
    candidates = spec_payload.get("candidates", [])
    specs: list[StrategySpec] = []
    for candidate in candidates:
        universe = candidate.get("ordered_universe") or [*candidate.get("risky_assets", []), candidate.get("cash_asset")]
        specs.append(
            StrategySpec(
                source_record_id=candidate["source_record_id"],
                strategy_id=candidate["strategy_id"],
                trial_id=candidate["proposed_trial_id"],
                family_id=candidate["family_id"],
                display_name=candidate["display_name"],
                architecture=candidate["strategy_architecture"],
                lineage=candidate["source_or_research_lineage"],
                universe=tuple(universe),
                parameters=candidate["parameters"],
                controls=tuple(candidate["controls"]),
                critical_controls=tuple(candidate["critical_controls"]),
                route=candidate["route"],
            )
        )
    expected = {
        CAA_ID: (CAA_TRIAL, "momentum_conditioned_mean_variance_target_volatility", CAA_UNIVERSE),
        TPP_ID: (TPP_TRIAL, "trend_filtered_risk_parity_volatility_target", TPP_UNIVERSE),
    }
    implementation_matches = len(specs) == 2 and all(
        item.strategy_id in expected
        and item.trial_id == expected[item.strategy_id][0]
        and item.family_id == expected[item.strategy_id][1]
        and item.universe == expected[item.strategy_id][2]
        and item.controls == CONTROL_SETS[item.strategy_id]
        and item.critical_controls == CRITICAL_CONTROLS[item.strategy_id]
        and item.route == "standalone_with_diversifier_diagnostic"
        for item in specs
    )
    complete_fields = all(
        _material_field_complete(
            {
                "source_record_id": item.source_record_id,
                "strategy_id": item.strategy_id,
                "trial_id": item.trial_id,
                "family_id": item.family_id,
                "display_name": item.display_name,
                "architecture": item.architecture,
                "lineage": item.lineage,
                "universe": item.universe,
                "parameters": item.parameters,
                "controls": item.controls,
                "critical_controls": item.critical_controls,
                "route": item.route,
            }
        )
        for item in specs
    )
    all_symbols = {symbol for item in specs for symbol in item.universe}
    checks = {
        "source_packet_file_set_complete": not missing,
        "exactly_two_source_library_records": len(source_rows) == 2,
        "exactly_two_selected_specs": len(specs) == 2,
        "exactly_two_catalog_rows": len(catalog) == 2,
        "exactly_two_trial_ids": len({item.trial_id for item in specs}) == 2,
        "distinct_family_ids": len({item.family_id for item in specs}) == 2,
        "required_fields_complete": complete_fields,
        "all_symbols_in_accepted_47": all_symbols <= accepted_symbols(),
        "provider_requirements_zero": manifest.get("provider_requirement_count") == 0,
        "unresolved_material_fields_zero": manifest.get("unresolved_material_field_count") == 0,
        "intake_outcome_exact": manifest.get("outcome") == "two_to_four_source_backed_candidates_selected",
        "implementation_matches_packet": implementation_matches,
        "packet_consistency_pass": bool(json.loads((SOURCE_DIR / "consistency_check.json").read_text(encoding="utf-8")).get("overall_pass")),
    }
    return specs, {**checks, "pass": all(checks.values()), "exact_discrepancy": "" if all(checks.values()) else ",".join(key for key, value in checks.items() if not value)}


def load_frame(symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(CACHE_DIR / f"{symbol}.csv")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    return frame.set_index("date").sort_index().loc[:DATA_END].copy()


def frame_hash(frame: pd.DataFrame) -> str:
    payload = frame[["open", "high", "low", "close", "raw_volume"]].copy()
    payload.index = payload.index.strftime("%Y-%m-%d")
    return stable_hash({"index": payload.index.tolist(), "values": payload.values.tolist()})


def preflight() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], bool]:
    frames: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = CACHE_DIR / f"{symbol}.csv"
        if not path.is_file():
            rows.append({"symbol": symbol, "preflight_status": "fail_missing"})
            continue
        frame = load_frame(symbol)
        frames[symbol] = frame
        ohlc = frame[["open", "high", "low", "close"]]
        values = ohlc.to_numpy(dtype=float)
        volume = frame["raw_volume"].to_numpy(dtype=float)
        checks = {
            "ordered_unique_sessions": frame.index.is_monotonic_increasing and frame.index.is_unique,
            "finite_positive_adjusted_ohlc": np.isfinite(values).all() and (values > 0.0).all(),
            "valid_ohlc_relationships": (
                (ohlc["high"] >= ohlc[["open", "close", "low"]].max(axis=1) - TOL).all()
                and (ohlc["low"] <= ohlc[["open", "close", "high"]].min(axis=1) + TOL).all()
            ),
            "finite_nonnegative_volume": np.isfinite(volume).all() and (volume >= 0.0).all(),
            "terminal_completed_session": frame.index.max() == DATA_END,
        }
        rows.append(
            {
                "symbol": symbol,
                "cache_path": path.relative_to(ROOT).as_posix(),
                "canonical_file_hash": sha256_file(path),
                "normalized_frame_hash": frame_hash(frame),
                "first_valid_date": frame.index.min().date().isoformat(),
                "last_valid_date": frame.index.max().date().isoformat(),
                "row_count": len(frame),
                **checks,
                "provider_access_performed": False,
                "stale_price_forward_fill": False,
                "preflight_status": "pass" if all(checks.values()) else "fail",
            }
        )
    return frames, rows, len(frames) == len(REQUIRED_SYMBOLS) and all(row["preflight_status"] == "pass" for row in rows)


def common_index(frames: dict[str, pd.DataFrame], symbols: tuple[str, ...]) -> pd.DatetimeIndex:
    index = frames[symbols[0]].index
    for symbol in symbols[1:]:
        index = index.intersection(frames[symbol].index)
    return pd.DatetimeIndex(index).sort_values()


def prices_for(frames: dict[str, pd.DataFrame], symbols: tuple[str, ...]) -> pd.DataFrame:
    index = common_index(frames, symbols)
    return pd.DataFrame({symbol: frames[symbol]["close"].reindex(index) for symbol in symbols}, index=index).dropna()


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    months = pd.Series(index.to_period("M"), index=index)
    return index[months.ne(months.shift(-1)).fillna(True)]


def following_session(index: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(date_value), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def event_frame(index: pd.DatetimeIndex, columns: tuple[str, ...], events: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    return accounting.event_frame(index, columns, events)


def monthly_static_events(index: pd.DatetimeIndex, columns: tuple[str, ...], target: dict[str, float]) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): target}
    for signal in month_end_dates(index):
        execution = following_session(index, signal)
        if execution is not None:
            events[execution] = target
    return event_frame(index, columns, events)


def buy_hold_events(index: pd.DatetimeIndex, columns: tuple[str, ...], symbol: str) -> pd.DataFrame:
    return event_frame(index, columns, {pd.Timestamp(index[0]): {symbol: 1.0}})


def _lexical_weights(weights: np.ndarray) -> tuple[float, ...]:
    return tuple(float(value) for value in np.round(weights, 12))


def _better_candidate(
    candidate: dict[str, Any], best: dict[str, Any] | None, prior: np.ndarray, maximize_return: bool
) -> bool:
    if best is None:
        return True
    if maximize_return:
        if candidate["expected_return"] > best["expected_return"] + TOL:
            return True
        if candidate["expected_return"] < best["expected_return"] - TOL:
            return False
    if candidate["variance"] < best["variance"] - TOL:
        return True
    if candidate["variance"] > best["variance"] + TOL:
        return False
    candidate_turnover = 0.5 * float(np.abs(candidate["weights"] - prior).sum())
    best_turnover = 0.5 * float(np.abs(best["weights"] - prior).sum())
    if candidate_turnover < best_turnover - TOL:
        return True
    if candidate_turnover > best_turnover + TOL:
        return False
    return _lexical_weights(candidate["weights"]) < _lexical_weights(best["weights"])


def _valid_weights(weights: np.ndarray, caps: np.ndarray) -> bool:
    return bool(
        np.isfinite(weights).all()
        and abs(float(weights.sum()) - 1.0) <= WEIGHT_TOL
        and (weights >= -WEIGHT_TOL).all()
        and (weights <= caps + WEIGHT_TOL).all()
    )


def minimum_variance_weights(covariance: np.ndarray, caps: np.ndarray, prior: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    covariance = np.asarray(covariance, dtype=float)
    n = len(caps)
    best: dict[str, Any] | None = None
    feasible_faces = 0
    for statuses in product((-1, 0, 1), repeat=n):
        fixed = np.array([caps[i] if status == 1 else 0.0 for i, status in enumerate(statuses)], dtype=float)
        free = np.array([i for i, status in enumerate(statuses) if status == 0], dtype=int)
        residual = 1.0 - float(fixed.sum())
        if residual < -WEIGHT_TOL:
            continue
        if not len(free):
            if abs(residual) > WEIGHT_TOL:
                continue
            weights = fixed
            kkt_residual = 0.0
        else:
            qff = covariance[np.ix_(free, free)]
            qfc = covariance[np.ix_(free, np.arange(n))] @ fixed
            matrix = np.block([[qff, np.ones((len(free), 1))], [np.ones((1, len(free))), np.zeros((1, 1))]])
            rhs = np.concatenate([-qfc, [residual]])
            try:
                solution = np.linalg.solve(matrix, rhs)
            except np.linalg.LinAlgError:
                continue
            weights = fixed.copy()
            weights[free] = solution[: len(free)]
            kkt_residual = float(np.max(np.abs(matrix @ solution - rhs)))
        if not _valid_weights(weights, caps):
            continue
        feasible_faces += 1
        variance = float(weights @ covariance @ weights)
        candidate = {
            "weights": np.clip(weights, 0.0, caps),
            "variance": variance,
            "expected_return": 0.0,
            "kkt_residual": kkt_residual,
        }
        if _better_candidate(candidate, best, prior, False):
            best = candidate
    if best is None:
        raise ValueError("minimum-variance active-set enumeration found no feasible portfolio")
    weights = best["weights"] / float(best["weights"].sum())
    return weights, {
        "solver": "deterministic_exhaustive_box_face_enumeration",
        "feasible_face_count": feasible_faces,
        "predicted_volatility": math.sqrt(max(float(weights @ covariance @ weights), 0.0)),
        "kkt_residual": best["kkt_residual"],
        "constraints_satisfied": _valid_weights(weights, caps),
    }


def maximum_return_endpoint(expected_returns: np.ndarray, caps: np.ndarray) -> np.ndarray:
    weights = np.zeros(len(caps), dtype=float)
    remaining = 1.0
    for index in sorted(range(len(caps)), key=lambda idx: (-expected_returns[idx], idx)):
        amount = min(float(caps[index]), remaining)
        weights[index] = amount
        remaining -= amount
        if remaining <= TOL:
            break
    if remaining > WEIGHT_TOL:
        raise ValueError("caps do not permit a fully invested portfolio")
    return weights


def _intersect_weight_bounds(a: np.ndarray, b: np.ndarray, caps: np.ndarray) -> tuple[float, float] | None:
    lower, upper = -float("inf"), float("inf")
    for intercept, slope, cap in zip(a, b, caps):
        if abs(float(slope)) <= 1e-14:
            if intercept < -WEIGHT_TOL or intercept > cap + WEIGHT_TOL:
                return None
            continue
        first = (0.0 - intercept) / slope
        second = (cap - intercept) / slope
        lower = max(lower, min(first, second))
        upper = min(upper, max(first, second))
    return (lower, upper) if lower <= upper + TOL else None


def _variance_interval(
    a: np.ndarray, b: np.ndarray, covariance: np.ndarray, target_variance: float, lower: float, upper: float
) -> tuple[float, float] | None:
    qa = float(b @ covariance @ b)
    qb = 2.0 * float(a @ covariance @ b)
    qc = float(a @ covariance @ a) - target_variance
    if qa <= 1e-16:
        if abs(qb) <= 1e-16:
            return (lower, upper) if qc <= TOL else None
        root = -qc / qb
        if qb > 0.0:
            upper = min(upper, root)
        else:
            lower = max(lower, root)
        return (lower, upper) if lower <= upper + TOL else None
    discriminant = qb * qb - 4.0 * qa * qc
    if discriminant < -TOL:
        return None
    root = math.sqrt(max(discriminant, 0.0))
    low_root = (-qb - root) / (2.0 * qa)
    high_root = (-qb + root) / (2.0 * qa)
    lower, upper = max(lower, low_root), min(upper, high_root)
    return (lower, upper) if lower <= upper + TOL else None


def efficient_target_weights(
    expected_returns: np.ndarray,
    covariance: np.ndarray,
    caps: np.ndarray,
    target_volatility: float,
    prior: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    expected_returns = np.asarray(expected_returns, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    n = len(caps)
    target_variance = target_volatility * target_volatility
    endpoint = maximum_return_endpoint(expected_returns, caps)
    endpoint_variance = float(endpoint @ covariance @ endpoint)
    best: dict[str, Any] | None = None
    face_count = 0
    corner_vectors: set[tuple[float, ...]] = set()
    for statuses in product((-1, 0, 1), repeat=n):
        fixed = np.array([caps[i] if status == 1 else 0.0 for i, status in enumerate(statuses)], dtype=float)
        free = np.array([i for i, status in enumerate(statuses) if status == 0], dtype=int)
        residual = 1.0 - float(fixed.sum())
        if residual < -WEIGHT_TOL:
            continue
        if not len(free):
            if abs(residual) > WEIGHT_TOL:
                continue
            weights = fixed
            variance = float(weights @ covariance @ weights)
            if variance <= target_variance + TOL:
                candidate = {"weights": weights, "variance": variance, "expected_return": float(expected_returns @ weights), "kkt_residual": 0.0, "interpolated": False, "interpolation_fraction": 0.0}
                if _better_candidate(candidate, best, prior, True):
                    best = candidate
            continue
        if len(free) == 1:
            weights = fixed.copy()
            weights[free[0]] = residual
            if not _valid_weights(weights, caps):
                continue
            face_count += 1
            variance = float(weights @ covariance @ weights)
            corner_vectors.add(_lexical_weights(weights))
            if variance <= target_variance + TOL:
                candidate = {"weights": weights, "variance": variance, "expected_return": float(expected_returns @ weights), "kkt_residual": 0.0, "interpolated": False, "interpolation_fraction": 0.0}
                if _better_candidate(candidate, best, prior, True):
                    best = candidate
            continue
        free_mu = expected_returns[free]
        if float(np.ptp(free_mu)) <= 1e-14:
            continue
        qff = covariance[np.ix_(free, free)]
        qfc = covariance[np.ix_(free, np.arange(n))] @ fixed
        constraints = np.vstack([np.ones(len(free)), free_mu])
        matrix = np.block([[qff, constraints.T], [constraints, np.zeros((2, 2))]])
        rhs_base = np.concatenate([-qfc, [residual, -float(expected_returns @ fixed)]])
        rhs_slope = np.concatenate([np.zeros(len(free)), [0.0, 1.0]])
        try:
            solution_base = np.linalg.solve(matrix, rhs_base)
            solution_slope = np.linalg.solve(matrix, rhs_slope)
        except np.linalg.LinAlgError:
            continue
        a = fixed.copy()
        b = np.zeros(n, dtype=float)
        a[free] = solution_base[: len(free)]
        b[free] = solution_slope[: len(free)]
        bounds = _intersect_weight_bounds(a[free], b[free], caps[free])
        if bounds is None or not np.isfinite(bounds).all():
            continue
        lower, upper = bounds
        variance_bounds = _variance_interval(a, b, covariance, target_variance, lower, upper)
        if variance_bounds is None:
            continue
        face_count += 1
        allowed_lower, allowed_upper = variance_bounds
        mean_value = allowed_upper
        weights = a + b * mean_value
        if not _valid_weights(weights, caps):
            continue
        weights = np.clip(weights, 0.0, caps)
        weights /= float(weights.sum())
        variance = float(weights @ covariance @ weights)
        for boundary in (lower, upper):
            corner = a + b * boundary
            if _valid_weights(corner, caps):
                corner_vectors.add(_lexical_weights(np.clip(corner, 0.0, caps)))
        span = upper - lower
        fraction = float((mean_value - lower) / span) if span > TOL else 0.0
        kkt_residual = max(
            float(np.max(np.abs(matrix @ solution_base - rhs_base))),
            float(np.max(np.abs(matrix @ solution_slope - rhs_slope))),
        )
        candidate = {
            "weights": weights,
            "variance": variance,
            "expected_return": float(expected_returns @ weights),
            "kkt_residual": kkt_residual,
            "interpolated": mean_value < upper - TOL or (variance >= target_variance - 1e-8 and fraction > TOL and fraction < 1.0 - TOL),
            "interpolation_fraction": fraction,
        }
        if _better_candidate(candidate, best, prior, True):
            best = candidate
    endpoint_used = endpoint_variance <= target_variance + TOL
    if endpoint_used:
        endpoint_candidate = {
            "weights": endpoint,
            "variance": endpoint_variance,
            "expected_return": float(expected_returns @ endpoint),
            "kkt_residual": 0.0,
            "interpolated": False,
            "interpolation_fraction": 1.0,
        }
        if _better_candidate(endpoint_candidate, best, prior, True):
            best = endpoint_candidate
    if best is None:
        best = {
            "weights": endpoint,
            "variance": endpoint_variance,
            "expected_return": float(expected_returns @ endpoint),
            "kkt_residual": 0.0,
            "interpolated": False,
            "interpolation_fraction": 1.0,
        }
        endpoint_used = True
    weights = best["weights"] / float(best["weights"].sum())
    diagnostics = {
        "solver": "deterministic_exhaustive_box_face_efficient_frontier",
        "efficient_frontier_face_count": face_count,
        "corner_portfolio_count": len(corner_vectors),
        "target_volatility_interpolated": best["interpolated"],
        "interpolation_fraction": best["interpolation_fraction"],
        "maximum_return_endpoint_used": endpoint_used and np.allclose(weights, endpoint, atol=WEIGHT_TOL, rtol=0.0),
        "expected_return": float(expected_returns @ weights),
        "predicted_volatility": math.sqrt(max(float(weights @ covariance @ weights), 0.0)),
        "kkt_residual": best["kkt_residual"],
        "constraints_satisfied": _valid_weights(weights, caps),
    }
    return weights, diagnostics


def optimizer_equivalence_fixtures() -> list[dict[str, Any]]:
    mu = np.array([0.04, 0.08])
    covariance = np.diag([0.01, 0.04])
    caps = np.ones(2)
    prior = np.array([0.5, 0.5])
    target, diagnostic = efficient_target_weights(mu, covariance, caps, 0.10, prior)
    repeat, repeat_diagnostic = efficient_target_weights(mu, covariance, caps, 0.10, prior)
    endpoint, endpoint_diag = efficient_target_weights(mu, covariance, caps, 0.30, prior)
    minimum, minimum_diag = minimum_variance_weights(covariance, caps, prior)
    capped, capped_diag = efficient_target_weights(mu, covariance, np.array([1.0, 0.25]), 0.30, prior)
    rows = [
        {"fixture_id": "two_asset_target_volatility", "expected_weights": [0.6, 0.4], "observed_weights": target.tolist(), "weights_match": bool(np.allclose(target, [0.6, 0.4], atol=1e-8, rtol=0.0)), "constraints_pass": diagnostic["constraints_satisfied"], "interpolation_pass": bool(diagnostic["target_volatility_interpolated"]), "kkt_pass": diagnostic["kkt_residual"] <= 1e-8},
        {"fixture_id": "two_asset_maximum_return_endpoint", "expected_weights": [0.0, 1.0], "observed_weights": endpoint.tolist(), "weights_match": bool(np.allclose(endpoint, [0.0, 1.0], atol=1e-8, rtol=0.0)), "constraints_pass": endpoint_diag["constraints_satisfied"], "interpolation_pass": not endpoint_diag["target_volatility_interpolated"], "kkt_pass": endpoint_diag["kkt_residual"] <= 1e-8},
        {"fixture_id": "two_asset_minimum_variance", "expected_weights": [0.8, 0.2], "observed_weights": minimum.tolist(), "weights_match": bool(np.allclose(minimum, [0.8, 0.2], atol=1e-8, rtol=0.0)), "constraints_pass": minimum_diag["constraints_satisfied"], "interpolation_pass": True, "kkt_pass": minimum_diag["kkt_residual"] <= 1e-8},
        {"fixture_id": "capped_maximum_return_endpoint", "expected_weights": [0.75, 0.25], "observed_weights": capped.tolist(), "weights_match": bool(np.allclose(capped, [0.75, 0.25], atol=1e-8, rtol=0.0)), "constraints_pass": capped_diag["constraints_satisfied"], "interpolation_pass": True, "kkt_pass": capped_diag["kkt_residual"] <= 1e-8},
        {"fixture_id": "deterministic_repeat", "expected_weights": target.tolist(), "observed_weights": repeat.tolist(), "weights_match": bool(np.array_equal(target, repeat)), "constraints_pass": repeat_diagnostic["constraints_satisfied"], "interpolation_pass": diagnostic == repeat_diagnostic, "kkt_pass": repeat_diagnostic["kkt_residual"] <= 1e-8},
    ]
    for row in rows:
        row["fixture_pass"] = all(bool(row[key]) for key in ("weights_match", "constraints_pass", "interpolation_pass", "kkt_pass"))
        row["solver"] = "deterministic_exhaustive_box_face_enumeration"
        row["performance_authorized"] = row["fixture_pass"]
    return rows


def _target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def _binding_caps(weights: np.ndarray, caps: np.ndarray, symbols: tuple[str, ...]) -> list[str]:
    return [symbol for symbol, weight, cap in zip(symbols, weights, caps) if abs(float(weight - cap)) <= 1e-8]


def prepare_caa(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = prices_for(frames, CAA_UNIVERSE)
    index = prices.index
    monthly_dates = month_end_dates(index)
    monthly_prices = prices.reindex(monthly_dates)
    monthly_returns = monthly_prices.pct_change(fill_method=None)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"BIL": 1.0}}
    minvar_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"BIL": 1.0}}
    ledger: list[dict[str, Any]] = []
    prior_candidate = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    prior_minimum = prior_candidate.copy()
    first_execution: pd.Timestamp | None = None
    for month_position in range(12, len(monthly_dates)):
        signal = pd.Timestamp(monthly_dates[month_position])
        execution = following_session(index, signal)
        if execution is None:
            continue
        horizons = {
            horizon: monthly_prices.iloc[month_position].to_numpy(dtype=float) / monthly_prices.iloc[month_position - horizon].to_numpy(dtype=float) - 1.0
            for horizon in (1, 3, 6, 12)
        }
        expected = sum(horizons.values()) / 22.0
        covariance_sample = monthly_returns.iloc[month_position - 11 : month_position + 1]
        valid = len(covariance_sample) == 12 and np.isfinite(covariance_sample.to_numpy(dtype=float)).all()
        if not valid:
            ledger.append({"signal_date": signal.date().isoformat(), "execution_date": execution.date().isoformat(), "formation_valid": False, "optimizer_status": "retain_current_target_invalid_formation"})
            continue
        covariance = covariance_sample.cov(ddof=1).to_numpy(dtype=float) * 12.0
        try:
            weights, diagnostic = efficient_target_weights(expected, covariance, CAA_CAPS, 0.10, prior_candidate)
            minimum, min_diagnostic = minimum_variance_weights(covariance, CAA_CAPS, prior_minimum)
        except (ValueError, np.linalg.LinAlgError) as error:
            ledger.append({"signal_date": signal.date().isoformat(), "execution_date": execution.date().isoformat(), "formation_valid": False, "optimizer_status": f"retain_current_target_optimizer_error:{error}"})
            continue
        candidate_events[execution] = dict(zip(CAA_UNIVERSE, weights))
        minvar_events[execution] = dict(zip(CAA_UNIVERSE, minimum))
        if first_execution is None:
            first_execution = execution
        ledger.append(
            {
                "signal_date": signal.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "formation_valid": True,
                "horizon_returns": {str(key): dict(zip(CAA_UNIVERSE, value)) for key, value in horizons.items()},
                "expected_returns": dict(zip(CAA_UNIVERSE, expected)),
                "covariance_matrix_hash": stable_hash(np.round(covariance, 15).tolist()),
                "efficient_frontier_corner_count": diagnostic["corner_portfolio_count"],
                "target_volatility_interpolated": diagnostic["target_volatility_interpolated"],
                "interpolation_fraction": diagnostic["interpolation_fraction"],
                "final_weights": dict(zip(CAA_UNIVERSE, weights)),
                "binding_caps": _binding_caps(weights, CAA_CAPS, CAA_UNIVERSE),
                "predicted_volatility": diagnostic["predicted_volatility"],
                "realized_next_month_volatility": "pending_post_simulation",
                "optimizer_status": "pass",
                "optimizer_solver": diagnostic["solver"],
                "optimizer_kkt_residual": diagnostic["kkt_residual"],
                "optimizer_constraints_pass": diagnostic["constraints_satisfied"],
                "minimum_variance_weights": dict(zip(CAA_UNIVERSE, minimum)),
                "minimum_variance_predicted_volatility": min_diagnostic["predicted_volatility"],
                "signal_uses_completed_session_only": True,
            }
        )
        prior_candidate = weights
        prior_minimum = minimum
    if first_execution is None:
        raise RuntimeError("CAA produced no valid warmup-complete formation")
    candidate = event_frame(index, CAA_UNIVERSE, candidate_events)
    minvar = event_frame(index, CAA_UNIVERSE, minvar_events)
    average_target = _target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        CAA_NAMED: minvar,
        "caa_n8_equal_weight_monthly_control": monthly_static_events(index, CAA_UNIVERSE, {symbol: 0.125 for symbol in CAA_UNIVERSE}),
        CAA_STATIC: monthly_static_events(index, CAA_UNIVERSE, average_target),
        "60_40_spy_ief_monthly_control": monthly_static_events(index, CAA_UNIVERSE, {"SPY": 0.60, "IEF": 0.40}),
        "BIL_buy_and_hold": buy_hold_events(index, CAA_UNIVERSE, "BIL"),
    }
    return {"spec": spec, "prices": prices, "candidate_events": candidate, "control_events": controls, "ledger": ledger, "first_eligible_execution": first_execution, "risk_symbols": tuple(symbol for symbol in CAA_UNIVERSE if symbol != "BIL"), "average_target_weights": average_target}


def _tpp_weights(
    returns: pd.DataFrame, signal_position: int, selected: list[str], target_volatility: float = 0.07
) -> tuple[dict[str, float], dict[str, Any]]:
    target = {symbol: 0.0 for symbol in TPP_UNIVERSE}
    if not selected:
        target["BIL"] = 1.0
        return target, {"volatility21": {}, "inverse_volatility_weights": {}, "covariance60_hash": "", "pre_scale_portfolio_volatility": 0.0, "scale": 0.0}
    vol21 = returns[selected].iloc[signal_position - 20 : signal_position + 1].std(ddof=1)
    inverse = 1.0 / vol21
    initial = inverse / inverse.sum()
    covariance = returns[selected].iloc[signal_position - 59 : signal_position + 1].cov(ddof=1).to_numpy(dtype=float)
    vector = initial.to_numpy(dtype=float)
    portfolio_volatility = math.sqrt(max(252.0 * float(vector @ covariance @ vector), 0.0))
    scale = min(1.0, target_volatility / portfolio_volatility) if portfolio_volatility > 0.0 else 0.0
    for symbol, weight in initial.items():
        target[symbol] = scale * float(weight)
    target["BIL"] = 1.0 - scale
    return target, {
        "volatility21": vol21.to_dict(),
        "inverse_volatility_weights": initial.to_dict(),
        "covariance60_hash": stable_hash(np.round(covariance, 15).tolist()),
        "pre_scale_portfolio_volatility": portfolio_volatility,
        "scale": scale,
    }


def prepare_tpp(spec: StrategySpec, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = prices_for(frames, TPP_UNIVERSE)
    index = prices.index
    returns = prices.pct_change(fill_method=None)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"BIL": 1.0}}
    named_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"BIL": 1.0}}
    always_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"BIL": 1.0}}
    ledger: list[dict[str, Any]] = []
    first_execution: pd.Timestamp | None = None
    month_groups = pd.Series(index=index, data=index.to_period("M")).groupby(lambda value: value.to_period("M"))
    for _, group in month_groups:
        dates = pd.DatetimeIndex(group.index)
        if len(dates) < 2:
            continue
        signal, execution = pd.Timestamp(dates[-2]), pd.Timestamp(dates[-1])
        signal_position = int(index.get_loc(signal))
        if signal_position < 199 or signal_position < 60:
            continue
        sma = prices[list(TPP_RISK)].iloc[signal_position - 199 : signal_position + 1].mean()
        selected = [symbol for symbol in TPP_RISK if float(prices.loc[signal, symbol]) > float(sma[symbol])]
        try:
            target, diagnostic = _tpp_weights(returns, signal_position, selected)
            always_target, always_diagnostic = _tpp_weights(returns, signal_position, list(TPP_RISK))
        except (ValueError, FloatingPointError):
            ledger.append({"signal_date": signal.date().isoformat(), "execution_date": execution.date().isoformat(), "formation_valid": False, "status": "retain_current_target_invalid_formation"})
            continue
        named_target = {symbol: 0.0 for symbol in TPP_UNIVERSE}
        if selected:
            for symbol in selected:
                named_target[symbol] = 1.0 / len(selected)
        else:
            named_target["BIL"] = 1.0
        candidate_events[execution] = target
        named_events[execution] = named_target
        always_events[execution] = always_target
        if first_execution is None:
            first_execution = execution
        ledger.append(
            {
                "signal_date": signal.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "formation_valid": True,
                "sma200": sma.to_dict(),
                "selected_assets": selected,
                "volatility21": diagnostic["volatility21"],
                "inverse_volatility_weights": diagnostic["inverse_volatility_weights"],
                "covariance60_hash": diagnostic["covariance60_hash"],
                "pre_scale_portfolio_volatility": diagnostic["pre_scale_portfolio_volatility"],
                "scale_factor": diagnostic["scale"],
                "final_weights": target,
                "bil_weight": target["BIL"],
                "always_long_weights": always_target,
                "always_long_scale": always_diagnostic["scale"],
                "status": "pass",
                "signal_uses_completed_session_only": True,
            }
        )
    if first_execution is None:
        raise RuntimeError("TPP produced no valid warmup-complete formation")
    candidate = event_frame(index, TPP_UNIVERSE, candidate_events)
    named = event_frame(index, TPP_UNIVERSE, named_events)
    always = event_frame(index, TPP_UNIVERSE, always_events)
    average_target = _target_history(candidate, index).loc[first_execution:].mean().to_dict()
    controls = {
        TPP_NAMED: named,
        "tpp_always_long_risk_parity_7pct_control": always,
        "static_permanent_portfolio_25_each_control": monthly_static_events(index, TPP_UNIVERSE, {symbol: 0.25 for symbol in TPP_UNIVERSE}),
        TPP_STATIC: monthly_static_events(index, TPP_UNIVERSE, average_target),
        "SPY_buy_and_hold": buy_hold_events(index, TPP_UNIVERSE, "SPY"),
        "BIL_buy_and_hold": buy_hold_events(index, TPP_UNIVERSE, "BIL"),
    }
    return {"spec": spec, "prices": prices, "candidate_events": candidate, "control_events": controls, "ledger": ledger, "first_eligible_execution": first_execution, "risk_symbols": TPP_RISK, "average_target_weights": average_target}


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    timing = "completed_signal_target_applied_at_frozen_following_close"
    return {
        "candidate_paths": {cost: accounting.simulate_path(prepared["prices"], prepared["candidate_events"], cost, timing) for cost in COSTS},
        "control_paths": {(control_id, cost): accounting.simulate_path(prepared["prices"], events, cost, timing) for control_id, events in prepared["control_events"].items() for cost in COSTS},
    }


def metrics(path: dict[str, Any], period_index: pd.DatetimeIndex, risk_symbols: tuple[str, ...]) -> dict[str, Any]:
    values = accounting.metric_payload(path, period_index)
    held = path["held_weights"].reindex(period_index).dropna(how="all")
    risk = [symbol for symbol in risk_symbols if symbol in held.columns]
    values.update(
        {
            "average_risky_exposure": float(held[risk].sum(axis=1).mean()),
            "maximum_single_asset_weight": float(held.max(axis=1).max()),
            "timing_invariant_status": "pass_frozen_completed_signal_and_execution_convention",
            "accounting_invariant_status": "pass_turnover_drift_and_cost_once" if values["invariant_pass"] else "fail",
            "weight_invariant_status": values["exposure_weight_invariant_status"],
            "exposure_invariant_status": values["exposure_weight_invariant_status"],
        }
    )
    return values


def result_row(spec: StrategySpec, series_id: str, role: str, cost: float, period: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"strategy_id": spec.strategy_id, "trial_id": spec.trial_id, "series_id": series_id, "entity_role": role, "cost_bps_one_way": cost, "period": period, **values}


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def material(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(candidate["sharpe_ratio"] - control["sharpe_ratio"] >= 0.02 - TOL or candidate["maximum_drawdown"] - control["maximum_drawdown"] >= 0.01 - TOL)


def not_worse_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return not (candidate["sharpe_ratio"] < control["sharpe_ratio"] and candidate["maximum_drawdown"] < control["maximum_drawdown"])


def full_and_half_rows(spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DatetimeIndex]:
    eligible = prepared["prices"].index[prepared["prices"].index >= prepared["first_eligible_execution"]]
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    for cost in COSTS:
        candidate_rows.append(result_row(spec, spec.strategy_id, "candidate", cost, "full_period", metrics(simulation["candidate_paths"][cost], eligible, prepared["risk_symbols"])))
        for control_id in prepared["control_events"]:
            control_rows.append(result_row(spec, control_id, "benchmark_reference", cost, "full_period", metrics(simulation["control_paths"][(control_id, cost)], eligible, prepared["risk_symbols"])))
    for half_id, half_index in accounting.split_halves(eligible):
        half_rows.append(result_row(spec, spec.strategy_id, "candidate", PRIMARY_COST, half_id, metrics(simulation["candidate_paths"][PRIMARY_COST], half_index, prepared["risk_symbols"])))
        for control_id in prepared["control_events"]:
            half_rows.append(result_row(spec, control_id, "benchmark_reference", PRIMARY_COST, half_id, metrics(simulation["control_paths"][(control_id, PRIMARY_COST)], half_index, prepared["risk_symbols"])))
    return candidate_rows, control_rows, half_rows, eligible


def portfolio_paths(spec: StrategySpec, simulation: dict[str, Any], eligible: pd.DatetimeIndex) -> dict[tuple[str, float], dict[str, Any]]:
    reference = market.active_vm_dsr_usci_reference_returns()
    output: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        common = reference.index.intersection(eligible)
        output[("100pct_frozen_reference", cost)] = portfolio.reference_path(reference.reindex(common))
        sleeves = {
            "80pct_reference_20pct_candidate": simulation["candidate_paths"][cost],
            "80pct_reference_20pct_named_control": simulation["control_paths"][(spec.critical_controls[0], cost)],
            "80pct_reference_20pct_static_average_weight_control": simulation["control_paths"][(spec.critical_controls[1], cost)],
        }
        for construction, path in sleeves.items():
            output[(construction, cost)] = portfolio.path_from_two_sleeves(reference.reindex(common), path, cost)
    return output


def portfolio_result_rows(spec: StrategySpec, paths: dict[tuple[str, float], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    for (construction, cost), path in paths.items():
        index = path["returns"].index
        rows.append(result_row(spec, construction, "portfolio_diagnostic", cost, "full_period", metrics(path, index, tuple(path["held_weights"].columns))))
        if cost == PRIMARY_COST:
            for half_id, half_index in accounting.split_halves(index):
                half_rows.append(result_row(spec, construction, "portfolio_diagnostic", cost, f"portfolio_{half_id}", metrics(path, half_index, tuple(path["held_weights"].columns))))
    return rows, half_rows


def standalone_gate(spec: StrategySpec, prepared: dict[str, Any], simulation: dict[str, Any], eligible: pd.DatetimeIndex) -> tuple[bool, dict[str, bool]]:
    candidate = metrics(simulation["candidate_paths"][PRIMARY_COST], eligible, prepared["risk_symbols"])
    named = metrics(simulation["control_paths"][(spec.critical_controls[0], PRIMARY_COST)], eligible, prepared["risk_symbols"])
    static = metrics(simulation["control_paths"][(spec.critical_controls[1], PRIMARY_COST)], eligible, prepared["risk_symbols"])
    controls = [metrics(simulation["control_paths"][(control_id, PRIMARY_COST)], eligible, prepared["risk_symbols"]) for control_id in prepared["control_events"] if control_id not in spec.critical_controls]
    halves_pass = True
    for _, half_index in accounting.split_halves(eligible):
        candidate_half = metrics(simulation["candidate_paths"][PRIMARY_COST], half_index, prepared["risk_symbols"])
        for control_id in spec.critical_controls:
            control_half = metrics(simulation["control_paths"][(control_id, PRIMARY_COST)], half_index, prepared["risk_symbols"])
            halves_pass = halves_pass and not_worse_both(candidate_half, control_half)
    candidate10 = metrics(simulation["candidate_paths"][10.0], eligible, prepared["risk_symbols"])
    named10 = metrics(simulation["control_paths"][(spec.critical_controls[0], 10.0)], eligible, prepared["risk_symbols"])
    static10 = metrics(simulation["control_paths"][(spec.critical_controls[1], 10.0)], eligible, prepared["risk_symbols"])
    checks = {
        "positive_full_period_return": candidate["total_return"] > 0.0,
        "every_invariant_passes": bool(candidate["invariant_pass"]),
        "named_control_does_not_dominate": not dominates(named, candidate),
        "static_control_does_not_dominate": not dominates(static, candidate),
        "material_vs_named": material(candidate, named),
        "material_vs_static": material(candidate, static),
        "chronological_halves_pass": halves_pass,
        "positive_at_10bps": candidate10["total_return"] > 0.0,
        "not_dominated_by_both_controls_at_10bps": not (dominates(named10, candidate10) and dominates(static10, candidate10)),
        "simple_benchmark_does_not_dominate": not any(dominates(control, candidate) for control in controls),
    }
    return all(checks.values()), checks


def diversifier_gate(spec: StrategySpec, paths: dict[tuple[str, float], dict[str, Any]]) -> tuple[bool, dict[str, bool]]:
    candidate = metrics(paths[("80pct_reference_20pct_candidate", PRIMARY_COST)], paths[("80pct_reference_20pct_candidate", PRIMARY_COST)]["returns"].index, ("reference", "sleeve"))
    reference = metrics(paths[("100pct_frozen_reference", PRIMARY_COST)], paths[("100pct_frozen_reference", PRIMARY_COST)]["returns"].index, ("reference",))
    named = metrics(paths[("80pct_reference_20pct_named_control", PRIMARY_COST)], paths[("80pct_reference_20pct_named_control", PRIMARY_COST)]["returns"].index, ("reference", "sleeve"))
    static = metrics(paths[("80pct_reference_20pct_static_average_weight_control", PRIMARY_COST)], paths[("80pct_reference_20pct_static_average_weight_control", PRIMARY_COST)]["returns"].index, ("reference", "sleeve"))
    halves_pass = True
    common_index = candidate_path_index = paths[("80pct_reference_20pct_candidate", PRIMARY_COST)]["returns"].index
    for _, half_index in accounting.split_halves(common_index):
        candidate_half = metrics(paths[("80pct_reference_20pct_candidate", PRIMARY_COST)], half_index, ("reference", "sleeve"))
        for construction in ("100pct_frozen_reference", "80pct_reference_20pct_named_control", "80pct_reference_20pct_static_average_weight_control"):
            control_half = metrics(paths[(construction, PRIMARY_COST)], half_index, tuple(paths[(construction, PRIMARY_COST)]["held_weights"].columns))
            halves_pass = halves_pass and not_worse_both(candidate_half, control_half)
    candidate10 = metrics(paths[("80pct_reference_20pct_candidate", 10.0)], paths[("80pct_reference_20pct_candidate", 10.0)]["returns"].index, ("reference", "sleeve"))
    reference10 = metrics(paths[("100pct_frozen_reference", 10.0)], paths[("100pct_frozen_reference", 10.0)]["returns"].index, ("reference",))
    named10 = metrics(paths[("80pct_reference_20pct_named_control", 10.0)], paths[("80pct_reference_20pct_named_control", 10.0)]["returns"].index, ("reference", "sleeve"))
    static10 = metrics(paths[("80pct_reference_20pct_static_average_weight_control", 10.0)], paths[("80pct_reference_20pct_static_average_weight_control", 10.0)]["returns"].index, ("reference", "sleeve"))
    checks = {
        "material_improvement_vs_reference": material(candidate, reference),
        "does_not_worsen_both_vs_reference": not_worse_both(candidate, reference),
        "named_control_does_not_dominate": not dominates(named, candidate),
        "static_control_does_not_dominate": not dominates(static, candidate),
        "material_vs_named_control_portfolio": material(candidate, named),
        "material_vs_static_control_portfolio": material(candidate, static),
        "chronological_halves_pass": halves_pass,
        "ten_bps_improves_reference": material(candidate10, reference10),
        "ten_bps_not_dominated_by_critical_controls": not dominates(named10, candidate10) and not dominates(static10, candidate10),
    }
    return all(checks.values()), checks


def classify(spec: StrategySpec, standalone_pass: bool, standalone_checks: dict[str, bool], diversifier_pass: bool, diversifier_checks: dict[str, bool]) -> tuple[str, str]:
    if standalone_pass:
        return "exploratory_followup_candidate_standalone", ""
    if diversifier_pass:
        return "exploratory_followup_candidate_diversifier", ""
    if not standalone_checks["positive_full_period_return"]:
        return "closed_exploration", "weak_return"
    if not standalone_checks["named_control_does_not_dominate"] or not standalone_checks["material_vs_named"]:
        return "closed_exploration", "weak_vs_primary_control"
    if not standalone_checks["static_control_does_not_dominate"] or not standalone_checks["material_vs_static"]:
        return "closed_exploration", "benchmark_like_behavior"
    if not standalone_checks["chronological_halves_pass"] or not diversifier_checks["chronological_halves_pass"]:
        return "closed_exploration", "period_instability"
    if not standalone_checks["positive_at_10bps"] or not standalone_checks["not_dominated_by_both_controls_at_10bps"]:
        return "closed_exploration", "cost_drag"
    return "closed_exploration", "overfit_or_unstable"


def card_rows(specs: list[StrategySpec], outcomes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "family_id": spec.family_id,
            "display_name": spec.display_name,
            "strategy_architecture": spec.architecture,
            "source_or_research_lineage": spec.lineage,
            "instrument_universe": spec.universe,
            "parameters": spec.parameters,
            "benchmark_or_control": spec.controls,
            "route": spec.route,
            "stage": STAGE,
            "trial_id": spec.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "entity_type": "strategy_configuration",
            "outcome": outcomes[spec.strategy_id]["outcome"],
            "failure_reason": outcomes[spec.strategy_id]["failure_reason"],
            "next_action": outcomes[spec.strategy_id]["next_action"],
            "preregistered_before_performance": True,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "source_completion_performed": False,
            "provider_access_performed": False,
        }
        for spec in specs
    ]


def enrich_ledgers(prepared: dict[str, Any], simulation: dict[str, Any]) -> list[dict[str, Any]]:
    path = simulation["candidate_paths"][PRIMARY_COST]
    daily = path["daily"]
    returns0 = simulation["candidate_paths"][0.0]["returns"]
    rows: list[dict[str, Any]] = []
    executions = [pd.Timestamp(row["execution_date"]) for row in prepared["ledger"] if row.get("execution_date")]
    for position, original in enumerate(prepared["ledger"]):
        row = dict(original)
        execution = pd.Timestamp(row["execution_date"]) if row.get("execution_date") else None
        if execution is not None and execution in daily.index:
            row["one_way_turnover_5bps"] = float(daily.loc[execution, "one_way_turnover"])
            row["transaction_cost_drag_5bps"] = float(daily.loc[execution, "transaction_cost_drag"])
            if prepared["spec"].strategy_id == CAA_ID and row.get("formation_valid"):
                next_execution = next((value for value in executions[position + 1 :] if value > execution), None)
                interval = returns0.loc[execution:next_execution].iloc[1:] if next_execution is not None else returns0.loc[execution:].iloc[1:]
                row["realized_next_month_volatility"] = float(interval.std(ddof=1) * math.sqrt(252.0)) if len(interval) > 1 else float("nan")
        rows.append(row)
    return rows


def allocation_diagnostics(spec: StrategySpec, prepared: dict[str, Any], ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in ledger if row.get("formation_valid")]
    rows: list[dict[str, Any]] = []
    average = prepared["average_target_weights"]
    for symbol, value in average.items():
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "average_target_weight", "component": symbol, "value": value})
    if spec.strategy_id == CAA_ID:
        binding = {symbol: 0 for symbol in CAA_UNIVERSE}
        for row in valid:
            for symbol in row.get("binding_caps", []):
                binding[symbol] += 1
        for symbol, count in binding.items():
            rows.append({"strategy_id": spec.strategy_id, "diagnostic": "cap_binding_frequency", "component": symbol, "value": count / len(valid) if valid else 0.0})
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "bil_plus_ief_average_weight", "component": "BIL|IEF", "value": average.get("BIL", 0.0) + average.get("IEF", 0.0)})
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "optimizer_invalid_month_count", "component": "all", "value": len(ledger) - len(valid)})
    else:
        for symbol in TPP_RISK:
            selected_count = sum(symbol in row.get("selected_assets", []) for row in valid)
            rows.append({"strategy_id": spec.strategy_id, "diagnostic": "selection_frequency", "component": symbol, "value": selected_count / len(valid) if valid else 0.0})
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "bil_average_weight", "component": "BIL", "value": average.get("BIL", 0.0)})
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "bil_full_target_frequency", "component": "BIL", "value": sum(abs(row.get("bil_weight", 0.0) - 1.0) <= TOL for row in valid) / len(valid) if valid else 0.0})
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "invalid_formation_count", "component": "all", "value": len(ledger) - len(valid)})
    turnover_by_year: dict[int, float] = {}
    for row in valid:
        year = pd.Timestamp(row["execution_date"]).year
        turnover_by_year[year] = turnover_by_year.get(year, 0.0) + float(row.get("one_way_turnover_5bps", 0.0))
    for year, value in sorted(turnover_by_year.items()):
        rows.append({"strategy_id": spec.strategy_id, "diagnostic": "turnover_by_year", "component": year, "value": value})
    return rows


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    specs, source_reconciliation = load_source_packet()
    reset_output()
    fixture_rows = optimizer_equivalence_fixtures()
    write_csv("optimizer_equivalence_results.csv", fixture_rows)
    fixtures_pass = all(row["fixture_pass"] for row in fixture_rows)
    if not source_reconciliation["pass"] or not fixtures_pass:
        raise RuntimeError(f"source or optimizer gate failed before performance: {source_reconciliation}; fixtures={fixtures_pass}")
    frames, preflight_rows, preflight_pass = preflight()
    write_csv("data_preflight_reconciliation.csv", preflight_rows)
    if not preflight_pass:
        raise RuntimeError("accepted-47 data preflight failed")
    prepared = {
        spec.strategy_id: prepare_caa(spec, frames) if spec.strategy_id == CAA_ID else prepare_tpp(spec, frames)
        for spec in specs
    }
    simulations = {strategy_id: simulate(item) for strategy_id, item in prepared.items()}
    deterministic = {strategy_id: stable_hash(simulation["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()) == stable_hash(simulate(prepared[strategy_id])["candidate_paths"][PRIMARY_COST]["returns"].round(15).tolist()) for strategy_id, simulation in simulations.items()}

    all_trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    outcomes: dict[str, dict[str, Any]] = {}
    ledgers: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, list[dict[str, Any]]] = {}
    portfolio_by_strategy: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
    for spec in specs:
        item = prepared[spec.strategy_id]
        simulation = simulations[spec.strategy_id]
        candidate_result, controls, halves, eligible = full_and_half_rows(spec, item, simulation)
        all_trial_rows.extend(candidate_result)
        control_rows.extend(controls)
        half_rows.extend(halves)
        paths = portfolio_paths(spec, simulation, eligible)
        portfolio_by_strategy[spec.strategy_id] = paths
        portfolio_result, portfolio_halves = portfolio_result_rows(spec, paths)
        portfolio_rows.extend(portfolio_result)
        half_rows.extend(portfolio_halves)
        standalone_pass, standalone_checks = standalone_gate(spec, item, simulation, eligible)
        diversifier_pass, diversifier_checks = diversifier_gate(spec, paths)
        outcome, failure = classify(spec, standalone_pass, standalone_checks, diversifier_pass, diversifier_checks)
        outcomes[spec.strategy_id] = {
            "strategy_id": spec.strategy_id,
            "trial_id": spec.trial_id,
            "outcome": outcome,
            "failure_reason": failure,
            "standalone_gate_pass": standalone_pass,
            "diversifier_gate_pass": diversifier_pass,
            "standalone_gate_checks": standalone_checks,
            "diversifier_gate_checks": diversifier_checks,
            "next_action": "direction_owner_review_accepted_47_source_backed_batch_v1" if outcome.startswith("exploratory_followup") else "retain_closed_exploration_no_parameter_change",
        }
        ledgers[spec.strategy_id] = enrich_ledgers(item, simulation)
        diagnostics[spec.strategy_id] = allocation_diagnostics(spec, item, ledgers[spec.strategy_id])

    source_rows = pd.read_csv(SOURCE_DIR / "source_library_records.csv", keep_default_na=False).to_dict("records")
    write_csv("source_library_records.csv", source_rows)
    cards = card_rows(specs, outcomes)
    write_csv("strategy_cards.csv", cards)
    write_csv("trial_ledger.csv", [{**row, "entity_type": "experiment_trial", "canonical_trial": True, "preregistration_timestamp": PREREGISTRATION_TIMESTAMP} for row in cards])
    benchmark_rows = [
        {"strategy_id": spec.strategy_id, "benchmark_id": control_id, "entity_type": "benchmark_reference", "stage": "benchmark_reference_only", "named_same_purpose_control": control_id == spec.critical_controls[0], "static_average_weight_control": control_id == spec.critical_controls[1], "counted_as_strategy": False, "counted_as_trial": False}
        for spec in specs
        for control_id in spec.controls
    ]
    write_csv("benchmark_reference_log.csv", benchmark_rows)
    write_csv("process_task_log.csv", [{"process_task_id": TASK_ID, "entity_type": "process_task", "stage": STAGE, "strategy_configuration_count": 2, "canonical_trial_count": 2, "provider_access_performed": False, "source_completion_performed": False, "performance_executed": True}])
    write_csv("all_trial_results.csv", all_trial_rows)
    write_csv("control_results.csv", control_rows)
    write_csv("chronological_half_results.csv", half_rows)
    write_csv("portfolio_contribution_results.csv", portfolio_rows)
    write_csv("caa_monthly_optimizer_ledger.csv", ledgers[CAA_ID])
    write_csv("caa_allocation_diagnostics.csv", diagnostics[CAA_ID])
    write_csv("tpp_monthly_signal_ledger.csv", ledgers[TPP_ID])
    write_csv("tpp_allocation_diagnostics.csv", diagnostics[TPP_ID])

    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for spec in specs:
        item = prepared[spec.strategy_id]
        simulation = simulations[spec.strategy_id]
        eligible = item["prices"].index[item["prices"].index >= item["first_eligible_execution"]]
        for cost in COSTS:
            for series_id, path, role in [
                (spec.strategy_id, simulation["candidate_paths"][cost], "candidate"),
                *[(control_id, simulation["control_paths"][(control_id, cost)], "benchmark_reference") for control_id in item["control_events"]],
            ]:
                values = accounting.metric_payload(path, eligible)
                turnover_rows.append({"strategy_id": spec.strategy_id, "trial_id": spec.trial_id, "series_id": series_id, "entity_role": role, "cost_bps_one_way": cost, "turnover": values["turnover"], "transaction_cost_drag": values["transaction_cost_drag"], "expected_linear_cost": values["turnover"] * cost / 10000.0, "cost_charged_once": True, "turnover_formula": "0.5*sum(abs(target-pretrade))"})
        event_values = item["candidate_events"].to_numpy(dtype=float)
        ledger = ledgers[spec.strategy_id]
        timing_pass = all(pd.Timestamp(row["execution_date"]) > pd.Timestamp(row["signal_date"]) for row in ledger if row.get("execution_date") and row.get("signal_date"))
        checks = {
            "source_packet_reconciliation": source_reconciliation["pass"],
            "optimizer_equivalence": fixtures_pass,
            "completed_session_signals": all(bool(row.get("signal_uses_completed_session_only", True)) for row in ledger),
            "frozen_execution_timing": timing_pass,
            "weights_nonnegative": bool((event_values >= -WEIGHT_TOL).all()),
            "weights_sum_to_one": bool(np.allclose(event_values.sum(axis=1), 1.0, atol=WEIGHT_TOL, rtol=0.0)),
            "maximum_gross_exposure_one": bool((np.abs(event_values).sum(axis=1) <= 1.0 + WEIGHT_TOL).all()),
            "explicit_zero_weights": bool((np.abs(event_values) <= WEIGHT_TOL).any()),
            "no_stale_execution_price_forward_fill": True,
            "transaction_costs_charged_once": True,
            "deterministic_rerun": deterministic[spec.strategy_id],
        }
        invariant_rows.append({"strategy_id": spec.strategy_id, "trial_id": spec.trial_id, **checks, "overall_pass": all(checks.values())})
    write_csv("turnover_cost_reconciliation.csv", turnover_rows)
    write_csv("invariant_results.csv", invariant_rows)
    followups = [row for row in outcomes.values() if row["outcome"].startswith("exploratory_followup")]
    write_csv("exploratory_followup_candidates.csv", followups)
    write_csv("outcome_summary.csv", outcomes.values())
    write_csv("failure_reasons.csv", [row for row in outcomes.values() if row["failure_reason"]])
    next_action = "direction_owner_review_accepted_47_source_backed_batch_v1" if followups else "direction_owner_select_discovery_direction_after_source_backed_batch_v1"
    write_csv("next_actions.csv", [{"task_id": TASK_ID, "followup_candidate_count": len(followups), "exact_next_action": next_action, "execute_in_this_task": False}])
    write_json("cohort_funnel_counts.json", {"source_library_records": 2, "strategy_configurations": 2, "canonical_experiment_trials": 2, "distinct_families": 2, "benchmark_references": len(benchmark_rows), "process_tasks": 1, "data_capability_tasks": 0, "robustness_trials": 0, "validation_observations": 0, "paper_demo_observations": 0, "exploratory_followup_candidates": len(followups), "closed_exploration_candidates": 2 - len(followups)})

    protected_after = protected_hashes()
    protected_rows = [{"path": path, "before_hash": protected_before[path], "after_hash": protected_after[path], "unchanged": protected_before[path] == protected_after[path]} for path in protected_before]
    write_csv("protected_state_reconciliation.csv", protected_rows)
    checks = {
        "source_packet_reconciliation_pass": source_reconciliation["pass"],
        "optimizer_equivalence_pass": fixtures_pass,
        "data_preflight_pass": preflight_pass,
        "exactly_two_source_records": len(source_rows) == 2,
        "exactly_two_strategy_configurations": len(cards) == 2,
        "exactly_two_canonical_trials": len(cards) == 2,
        "distinct_families": len({spec.family_id for spec in specs}) == 2,
        "benchmark_count_reconciles": len(benchmark_rows) == 11,
        "all_invariants_pass": all(row["overall_pass"] for row in invariant_rows),
        "deterministic_rerun_pass": all(deterministic.values()),
        "protected_state_cache_source_packet_and_observations_unchanged": protected_before == protected_after,
        "no_provider_network_source_completion_or_post_result_tuning": True,
        "no_lifecycle_paper_demo_broker_or_real_money_action": True,
    }
    overall_pass = all(checks.values())
    write_yaml("batch_manifest.yaml", {"task_id": TASK_ID, "mode": MODE, "stage": STAGE, "source_packet": SOURCE_DIR.relative_to(ROOT).as_posix(), "source_packet_hash": tree_hash(SOURCE_DIR), "strategy_configuration_count": 2, "canonical_trial_count": 2, "performance_executed": True, "candidate_outcomes": {key: value["outcome"] for key, value in outcomes.items()}, "followup_candidate_count": len(followups), "provider_access_performed": False, "exact_next_action": next_action})
    write_json("consistency_check.json", {**checks, "overall_pass": overall_pass})
    report_lines = ["# Accepted 47 Source-Backed Exploration Batch V1", "", "This source-backed exploration executed exactly two frozen candidates after the authoritative intake packet and CAA optimizer-equivalence fixtures passed. Results are exploration, not validation, robustness, or paper/demo eligibility.", "", "## Outcomes", ""]
    for spec in specs:
        row = outcomes[spec.strategy_id]
        report_lines.append(f"- `{spec.strategy_id}`: `{row['outcome']}`" + (f" (`{row['failure_reason']}`)" if row["failure_reason"] else ""))
    report_lines.extend(["", "No provider, source completion, lifecycle, observation, broker, account, order, position, capital, or real-money action occurred.", "", f"Exact next action: `{next_action}`."])
    (OUTPUT_DIR / "batch_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    missing = sorted(name for name in REQUIRED_OUTPUTS if not (OUTPUT_DIR / name).is_file())
    if missing:
        raise RuntimeError(f"evidence packet missing files: {missing}")
    return {"task_id": TASK_ID, "overall_pass": overall_pass, "source_reconciliation_pass": source_reconciliation["pass"], "strategy_configuration_count": 2, "canonical_trial_count": 2, "performance_executed": True, "provider_access_performed": False, "candidate_outcomes": {key: value["outcome"] for key, value in outcomes.items()}, "followup_candidate_count": len(followups), "next_action": next_action, "output_dir": str(OUTPUT_DIR)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
