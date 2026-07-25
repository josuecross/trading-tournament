from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import stats


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "driesprong_oil_signal_control_strength_audit_v1"
SOURCE_CORRECTION_TASK_ID = "driesprong_oil_us_market_source_split_correction_v1"
SOURCE_EXPANDING_VARIANT_ID = "driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1"
FAMILY_ID = "cross_asset_macro_predictive_timing"
ADAPTATION_LABEL = "benchmark_correction"
NEXT_ACTION = "direction_owner_review_driesprong_oil_control_strength_audit_v1"
RUN_CREATED_UTC = "2026-07-21T00:00:00Z"

SOURCE_DIR = (
    Path("evidence")
    / "public_source_strategy_correction"
    / SOURCE_CORRECTION_TASK_ID
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_verification"
    / TASK_ID
    / "latest"
)

SWITCHING_COST_BPS = 10
SWITCHING_COST_RATE = SWITCHING_COST_BPS / 10000.0
EXPECTED_EVALUATION_MONTHS = 242
EXPECTED_FIRST_MONTH = "2006-04"
EXPECTED_LAST_MONTH = "2026-05"
EXPECTED_MARKET_STATES = 210
EXPECTED_RISK_FREE_STATES = 32
EXPECTED_SWITCHES = 51
NUMERIC_TOLERANCE = 1e-10

OUTCOMES = {
    "dynamic_signal_incremental_after_controls",
    "dynamic_signal_control_weak",
    "dynamic_signal_mixed_control_evidence",
    "existing_evidence_reconciliation_defect",
}
TRADE_MANAGEMENT_GATES = {
    "dynamic_signal_incremental_after_controls": "overlay_research_direction_review_allowed",
    "dynamic_signal_control_weak": "overlay_research_deferred_control_weak",
    "dynamic_signal_mixed_control_evidence": "overlay_research_requires_mixed_evidence_review",
    "existing_evidence_reconciliation_defect": "overlay_research_requires_mixed_evidence_review",
}

REQUIRED_SOURCE_FILES = {
    "common_monthly_sample.csv",
    "evaluation_signal_audit.csv",
    "target_state_series.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "benchmark_metrics.csv",
    "fixed_regression_coefficients.json",
    "frozen_split_config.yaml",
}
REQUIRED_OUTPUT_FILES = {
    "existing_evidence_reconciliation.json",
    "frozen_control_config.yaml",
    "average_exposure_control_series.csv",
    "beta_matched_control_series.csv",
    "control_metrics.csv",
    "jensen_alpha_audit.json",
    "market_timing_audit.json",
    "market_timing_confusion_matrix.csv",
    "state_attribution.csv",
    "economic_attribution.json",
    "baseline_vs_controls.csv",
    "trade_management_gate.json",
    "verification_outcome.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "verification_summary.md",
}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    base = root / SOURCE_DIR
    return {name: sha256_path(base / name) for name in sorted(REQUIRED_SOURCE_FILES)}


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(root / path) for path in PROTECTED_STATE_PATHS}


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.bool_,)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)) and (math.isnan(float(value)) or math.isinf(float(value))):
        return ""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return str(float(value)) if isinstance(value, (float, np.floating)) else str(int(value))
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Period):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(to_jsonable(payload), sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_csv_frame(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().eq("true")


def equity_from_simple_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.astype(float).fillna(0.0)).cumprod()


def max_drawdown_from_returns(returns: pd.Series) -> float:
    equity = equity_from_simple_returns(returns)
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def metrics_for_returns(series_id: str, role: str, returns: pd.Series, rf_returns: pd.Series) -> dict[str, Any]:
    clean = returns.astype(float)
    rf = rf_returns.reindex(clean.index).astype(float)
    valid = clean.notna() & rf.notna()
    clean = clean[valid]
    rf = rf[valid]
    if clean.empty:
        return {
            "series_id": series_id,
            "role": role,
            "months": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "max_drawdown": float("nan"),
            "sharpe_ratio_vs_rf": float("nan"),
            "return_drawdown_proxy": float("nan"),
        }
    equity = equity_from_simple_returns(clean)
    years = max(len(clean) / 12.0, 1e-12)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(clean.std(ddof=1) * math.sqrt(12.0))
    mdd = max_drawdown_from_returns(clean)
    excess = clean - rf
    excess_std = float(excess.std(ddof=1))
    sharpe = float(excess.mean() * 12.0 / (excess_std * math.sqrt(12.0))) if excess_std > 0 else float("nan")
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    return {
        "series_id": series_id,
        "role": role,
        "start_month": str(clean.index.min()),
        "end_month": str(clean.index.max()),
        "months": int(len(clean)),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "max_drawdown": mdd,
        "sharpe_ratio_vs_rf": sharpe,
        "return_drawdown_proxy": proxy,
    }


def ols_with_hc1(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    frame = pd.DataFrame({"x": x.astype(float), "y": y.astype(float)}).dropna()
    x_values = frame["x"].to_numpy(dtype=float)
    y_values = frame["y"].to_numpy(dtype=float)
    n = len(frame)
    k = 2
    design = np.column_stack([np.ones(n), x_values])
    xtx_inv = np.linalg.inv(design.T @ design)
    coeffs = xtx_inv @ design.T @ y_values
    residuals = y_values - design @ coeffs
    meat = design.T @ np.diag(residuals**2) @ design
    hc1_scale = n / (n - k)
    covariance = hc1_scale * xtx_inv @ meat @ xtx_inv
    standard_errors = np.sqrt(np.diag(covariance))
    t_stats = coeffs / standard_errors
    p_values = 2.0 * (1.0 - stats.t.cdf(np.abs(t_stats), df=n - k))
    ss_resid = float(np.sum(residuals**2))
    ss_total = float(np.sum((y_values - y_values.mean()) ** 2))
    r_squared = 1.0 - ss_resid / ss_total if ss_total > 0 else float("nan")
    return {
        "alpha": float(coeffs[0]),
        "beta": float(coeffs[1]),
        "alpha_hc1_standard_error": float(standard_errors[0]),
        "beta_hc1_standard_error": float(standard_errors[1]),
        "alpha_hc1_t_statistic": float(t_stats[0]),
        "alpha_hc1_p_value": float(p_values[0]),
        "beta_hc1_t_statistic": float(t_stats[1]),
        "beta_hc1_p_value": float(p_values[1]),
        "r_squared": float(r_squared),
        "observation_count": int(n),
        "degrees_of_freedom": int(n - k),
        "hc1_scale_factor": float(hc1_scale),
        "standard_error_method": "White_HC1",
        "inference": "two_sided_t_distribution",
    }


def annualize_monthly_alpha(alpha: float) -> float:
    return float((1.0 + alpha) ** 12.0 - 1.0) if alpha > -1.0 else float("nan")


def prepare_evaluation(evaluation: pd.DataFrame) -> pd.DataFrame:
    frame = evaluation.copy()
    frame["evaluation_month"] = frame["evaluation_month"].astype(str)
    frame.index = pd.PeriodIndex(frame["evaluation_month"], freq="M")
    numeric_columns = [
        "market_weight",
        "risk_free_weight",
        "market_simple_return",
        "risk_free_simple_return",
        "strategy_gross_simple_return",
        "switching_cost_rate",
        "strategy_net_simple_return",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["state_changed_bool"] = bool_series(frame["state_changed"])
    return frame


def build_transactions_from_evaluation(evaluation: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    previous_state = ""
    for _, row in evaluation.reset_index(drop=True).iterrows():
        if bool(row["state_changed_bool"]):
            rows.append(
                {
                    "evaluation_month": row["evaluation_month"],
                    "from_state": previous_state,
                    "to_state": row["target_state"],
                    "switching_cost_bps": SWITCHING_COST_BPS,
                    "switching_cost_rate": SWITCHING_COST_RATE,
                    "cost_applied_once": True,
                }
            )
        previous_state = row["target_state"]
    return pd.DataFrame(rows)


def metric_matches(saved: pd.DataFrame, expected: dict[str, Any], series_id: str) -> bool:
    row = saved[saved["series_id"] == series_id]
    if row.empty:
        return False
    row = row.iloc[0]
    fields = ["total_return", "cagr", "max_drawdown", "return_drawdown_proxy"]
    for field in fields:
        saved_value = pd.to_numeric(pd.Series([row.get(field, np.nan)]), errors="coerce").iloc[0]
        expected_value = float(expected.get(field, np.nan))
        if math.isnan(saved_value) and math.isnan(expected_value):
            continue
        if abs(saved_value - expected_value) > NUMERIC_TOLERANCE:
            return False
    return True


def reconcile_existing_evidence(root: Path, source_before: dict[str, str]) -> tuple[dict[str, Any], dict[str, pd.DataFrame], dict[str, Any]]:
    base = root / SOURCE_DIR
    required_exists = {name: (base / name).exists() for name in sorted(REQUIRED_SOURCE_FILES)}
    if not all(required_exists.values()):
        reconciliation = {
            "status": "existing_evidence_reconciliation_defect",
            "required_source_files": required_exists,
            "source_hashes_before": source_before,
            "reconciliation_passed": False,
            "defect_reason": "missing required corrected-source-split evidence files",
        }
        return reconciliation, {}, {}

    common = read_csv_frame(base / "common_monthly_sample.csv")
    evaluation_raw = read_csv_frame(base / "evaluation_signal_audit.csv")
    target = read_csv_frame(base / "target_state_series.csv")
    transactions = read_csv_frame(base / "transactions.csv")
    baseline_metrics = read_csv_frame(base / "baseline_metrics.csv")
    benchmark_metrics = read_csv_frame(base / "benchmark_metrics.csv")
    coeffs = read_json(base / "fixed_regression_coefficients.json")
    split_config = read_yaml(base / "frozen_split_config.yaml")

    evaluation = prepare_evaluation(evaluation_raw)
    expected_target = evaluation[["evaluation_month", "target_state", "market_weight", "risk_free_weight"]].reset_index(drop=True)
    target_check = target.copy()
    for column in ["market_weight", "risk_free_weight"]:
        target_check[column] = pd.to_numeric(target_check[column], errors="coerce")
    target_equal = (
        list(target_check["evaluation_month"].astype(str)) == list(expected_target["evaluation_month"].astype(str))
        and list(target_check["target_state"].astype(str)) == list(expected_target["target_state"].astype(str))
        and bool(np.allclose(target_check["market_weight"], expected_target["market_weight"], atol=0.0))
        and bool(np.allclose(target_check["risk_free_weight"], expected_target["risk_free_weight"], atol=0.0))
    )

    rebuilt_transactions = build_transactions_from_evaluation(evaluation)
    tx_equal = len(rebuilt_transactions) == len(transactions)
    if tx_equal and len(transactions) > 0:
        tx = transactions.copy()
        tx["switching_cost_bps"] = pd.to_numeric(tx["switching_cost_bps"], errors="coerce")
        tx["switching_cost_rate"] = pd.to_numeric(tx["switching_cost_rate"], errors="coerce")
        tx_equal = (
            list(tx["evaluation_month"].astype(str)) == list(rebuilt_transactions["evaluation_month"].astype(str))
            and list(tx["from_state"].astype(str)) == list(rebuilt_transactions["from_state"].astype(str))
            and list(tx["to_state"].astype(str)) == list(rebuilt_transactions["to_state"].astype(str))
            and bool(np.allclose(tx["switching_cost_bps"], rebuilt_transactions["switching_cost_bps"], atol=0.0))
            and bool(np.allclose(tx["switching_cost_rate"], rebuilt_transactions["switching_cost_rate"], atol=0.0))
        )

    rf_returns = evaluation["risk_free_simple_return"]
    dynamic_metrics = metrics_for_returns(
        "source_split_10bps_baseline",
        "corrected_source_split_diagnostic",
        evaluation["strategy_net_simple_return"],
        rf_returns,
    )
    zero_cost_metrics = metrics_for_returns(
        "zero_cost_accounting_control",
        "accounting_control_only",
        evaluation["strategy_gross_simple_return"],
        rf_returns,
    )
    market_metrics = metrics_for_returns(
        "us_market_buy_and_hold",
        "required_control",
        evaluation["market_simple_return"],
        rf_returns,
    )
    rf_metrics = metrics_for_returns(
        "risk_free_only",
        "required_control",
        evaluation["risk_free_simple_return"],
        rf_returns,
    )

    first_month = str(evaluation["evaluation_month"].iloc[0]) if not evaluation.empty else ""
    last_month = str(evaluation["evaluation_month"].iloc[-1]) if not evaluation.empty else ""
    market_count = int((evaluation["target_state"] == "market").sum())
    risk_free_count = int((evaluation["target_state"] == "risk_free").sum())
    switch_count = int(evaluation["state_changed_bool"].sum())
    states_ok = set(evaluation["target_state"]) <= {"market", "risk_free"}
    weights_ok = bool(np.allclose(evaluation["market_weight"] + evaluation["risk_free_weight"], 1.0))
    cost_ok = bool(
        np.allclose(
            evaluation["switching_cost_rate"],
            np.where(evaluation["state_changed_bool"], SWITCHING_COST_RATE, 0.0),
        )
    )
    common_months_cover_eval = set(evaluation["evaluation_month"].astype(str)).issubset(
        set(common["month"].astype(str))
    )
    source_after = source_hashes(root)

    checks = {
        "required_files_present": all(required_exists.values()),
        "source_hashes_stable_during_read": source_before == source_after,
        "evaluation_month_count_matches_expected": len(evaluation) == EXPECTED_EVALUATION_MONTHS,
        "evaluation_window_matches_expected": first_month == EXPECTED_FIRST_MONTH and last_month == EXPECTED_LAST_MONTH,
        "state_counts_match_expected": market_count == EXPECTED_MARKET_STATES and risk_free_count == EXPECTED_RISK_FREE_STATES,
        "switch_count_matches_expected": switch_count == EXPECTED_SWITCHES,
        "switching_cost_matches_expected": cost_ok,
        "fixed_coefficients_estimated_once": coeffs.get("estimated_once") is True
        and coeffs.get("estimation_observations") == 241
        and coeffs.get("evaluation_observations") == EXPECTED_EVALUATION_MONTHS,
        "split_config_preserves_fixed_half_split": split_config.get("estimation_count") == 241
        and split_config.get("valid_regression_pair_count") == 483
        and split_config.get("expanding_regression") is False
        and split_config.get("rolling_regression") is False,
        "target_state_series_matches_evaluation": target_equal,
        "transactions_match_evaluation_state_changes": tx_equal,
        "baseline_metric_row_matches_recomputed_returns": metric_matches(
            baseline_metrics, dynamic_metrics, "source_split_10bps_baseline"
        )
        and metric_matches(baseline_metrics, zero_cost_metrics, "zero_cost_accounting_control"),
        "benchmark_metric_rows_match_recomputed_returns": metric_matches(
            benchmark_metrics, market_metrics, "us_market_buy_and_hold"
        )
        and metric_matches(benchmark_metrics, rf_metrics, "risk_free_only"),
        "states_are_binary_market_or_risk_free": states_ok,
        "weights_sum_to_one": weights_ok,
        "common_monthly_sample_contains_evaluation_months": common_months_cover_eval,
    }
    reconciliation_passed = all(checks.values())
    reconciliation = {
        "status": "reconciled" if reconciliation_passed else "existing_evidence_reconciliation_defect",
        "source_correction_task_id": SOURCE_CORRECTION_TASK_ID,
        "source_evidence_path": str(base),
        "required_source_files": required_exists,
        "source_hashes_before": source_before,
        "source_hashes_after": source_after,
        "checks": checks,
        "reconciliation_passed": reconciliation_passed,
        "defect_reason": "" if reconciliation_passed else "one or more corrected evidence reconciliation checks failed",
        "evaluation_months": int(len(evaluation)),
        "first_evaluation_month": first_month,
        "last_evaluation_month": last_month,
        "market_state_count": market_count,
        "risk_free_state_count": risk_free_count,
        "switch_count": switch_count,
        "switching_cost_bps": SWITCHING_COST_BPS,
        "strategy_signal_recalculated": False,
        "oil_predictor_recomputed": False,
        "fixed_coefficients_changed": False,
    }
    frames = {
        "common": common,
        "evaluation": evaluation,
        "target": target,
        "transactions": transactions,
        "baseline_metrics": baseline_metrics,
        "benchmark_metrics": benchmark_metrics,
    }
    extra = {
        "coefficients": coeffs,
        "split_config": split_config,
        "dynamic_metrics": dynamic_metrics,
        "zero_cost_metrics": zero_cost_metrics,
        "market_metrics": market_metrics,
        "rf_metrics": rf_metrics,
    }
    return reconciliation, frames, extra


def average_exposure_control(evaluation: pd.DataFrame) -> tuple[pd.Series, list[dict[str, Any]], dict[str, Any]]:
    month_count = len(evaluation)
    market_count = int((evaluation["target_state"] == "market").sum())
    weight = market_count / month_count
    rf_weight = 1.0 - weight
    returns = weight * evaluation["market_simple_return"] + rf_weight * evaluation["risk_free_simple_return"]
    equity = equity_from_simple_returns(returns)
    rows = []
    for month, value in returns.items():
        rows.append(
            {
                "evaluation_month": str(month),
                "average_market_weight": weight,
                "average_rf_weight": rf_weight,
                "market_simple_return": float(evaluation.loc[month, "market_simple_return"]),
                "risk_free_simple_return": float(evaluation.loc[month, "risk_free_simple_return"]),
                "exposure_matched_simple_return": float(value),
                "equity": float(equity.loc[month]),
                "switching_cost_rate": 0.0,
                "diagnostic_benchmark_only": True,
            }
        )
    config = {
        "average_market_weight_formula": "market_state_count / evaluation_month_count",
        "market_state_count": market_count,
        "evaluation_month_count": month_count,
        "average_market_weight": weight,
        "average_rf_weight": rf_weight,
        "ex_post_diagnostic_benchmark": True,
        "switching_cost_applied": False,
        "alternative_exposure_weights_generated": False,
    }
    return returns.rename("average_exposure_static_control"), rows, config


def beta_matched_control(evaluation: pd.DataFrame, regression: dict[str, Any]) -> tuple[pd.Series, list[dict[str, Any]], dict[str, Any]]:
    beta = float(regression["beta"])
    market_excess = evaluation["market_simple_return"] - evaluation["risk_free_simple_return"]
    returns = evaluation["risk_free_simple_return"] + beta * market_excess
    equity = equity_from_simple_returns(returns)
    rows = []
    for month, value in returns.items():
        rows.append(
            {
                "evaluation_month": str(month),
                "estimated_beta": beta,
                "market_simple_return": float(evaluation.loc[month, "market_simple_return"]),
                "risk_free_simple_return": float(evaluation.loc[month, "risk_free_simple_return"]),
                "market_excess_return": float(market_excess.loc[month]),
                "beta_matched_simple_return": float(value),
                "equity": float(equity.loc[month]),
                "switching_cost_rate": 0.0,
                "diagnostic_benchmark_only": True,
            }
        )
    config = {
        "beta_estimation_model": "strategy_excess_return_t = alpha + beta * market_excess_return_t + error_t",
        "estimated_once_over_frozen_evaluation_sample": True,
        "estimated_beta": beta,
        "beta_capped": False,
        "beta_rounded": False,
        "beta_optimized": False,
        "switching_cost_applied": False,
    }
    return returns.rename("beta_matched_static_control"), rows, config


def market_timing_audit(evaluation: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actual_bull = evaluation["market_simple_return"] > evaluation["risk_free_simple_return"]
    actual_bear = ~actual_bull
    predicted_bull = evaluation["target_state"] == "market"
    predicted_bear = evaluation["target_state"] == "risk_free"

    actual_bull_months = int(actual_bull.sum())
    actual_bear_months = int(actual_bear.sum())
    correct_bull = int((actual_bull & predicted_bull).sum())
    correct_bear = int((actual_bear & predicted_bear).sum())
    false_bull = int((actual_bear & predicted_bull).sum())
    false_bear = int((actual_bull & predicted_bear).sum())
    p2 = correct_bull / actual_bull_months if actual_bull_months else float("nan")
    p1 = correct_bear / actual_bear_months if actual_bear_months else float("nan")
    total_accuracy = (correct_bull + correct_bear) / len(evaluation)
    table = [[correct_bear, false_bull], [false_bear, correct_bull]]
    odds_ratio, p_value = stats.fisher_exact(table, alternative="greater")
    payload = {
        "actual_bull_definition": "market_return_t > rf_return_t",
        "actual_bear_definition": "market_return_t <= rf_return_t",
        "predicted_bull_definition": "target_state_t == market",
        "predicted_bear_definition": "target_state_t == risk_free",
        "actual_bull_months": actual_bull_months,
        "correct_bull_forecasts": correct_bull,
        "conditional_bull_accuracy_p2": p2,
        "actual_bear_months": actual_bear_months,
        "correct_bear_forecasts": correct_bear,
        "conditional_bear_accuracy_p1": p1,
        "p1_plus_p2": p1 + p2,
        "total_accuracy": total_accuracy,
        "henriksson_merton_nonparametric_test": "one_sided_fisher_exact_positive_timing_association",
        "timing_test_uses_conditional_bull_and_bear_accuracy": True,
        "fisher_exact_odds_ratio": float(odds_ratio) if math.isfinite(float(odds_ratio)) else None,
        "source_aligned_henriksson_merton_p_value": float(p_value),
        "observation_count": int(len(evaluation)),
    }
    matrix = [
        {
            "actual_state": "bear_market_return_lte_rf",
            "predicted_bear_count": correct_bear,
            "predicted_bull_count": false_bull,
            "actual_total": actual_bear_months,
        },
        {
            "actual_state": "bull_market_return_gt_rf",
            "predicted_bear_count": false_bear,
            "predicted_bull_count": correct_bull,
            "actual_total": actual_bull_months,
        },
    ]
    return payload, matrix


def state_attribution(evaluation: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_avoided_loss = 0.0
    total_missed_gain = 0.0
    total_cost_drag = float(evaluation["switching_cost_rate"].sum())
    final_wealth = float(equity_from_simple_returns(evaluation["strategy_net_simple_return"]).iloc[-1])
    for state in ["market", "risk_free"]:
        subset = evaluation[evaluation["target_state"] == state]
        if subset.empty:
            rows.append(
                {
                    "target_state": state,
                    "months": 0,
                    "average_market_return": "",
                    "average_market_excess_return": "",
                    "average_realized_strategy_return": "",
                    "negative_market_months": 0,
                    "worst_market_month": "",
                    "cumulative_avoided_market_loss_while_risk_free": 0.0,
                    "cumulative_missed_market_gain_while_risk_free": 0.0,
                    "net_switching_cost_drag": 0.0,
                    "contribution_to_final_wealth": 0.0,
                    "wealth_factor_from_state_months": 1.0,
                }
            )
            continue
        market_excess = subset["market_simple_return"] - subset["risk_free_simple_return"]
        avoided = 0.0
        missed = 0.0
        if state == "risk_free":
            avoided = float((subset["risk_free_simple_return"] - subset["market_simple_return"]).clip(lower=0.0).sum())
            missed = float((subset["market_simple_return"] - subset["risk_free_simple_return"]).clip(lower=0.0).sum())
            total_avoided_loss = avoided
            total_missed_gain = missed
        state_factor = float((1.0 + subset["strategy_net_simple_return"]).prod())
        rows.append(
            {
                "target_state": state,
                "months": int(len(subset)),
                "average_market_return": float(subset["market_simple_return"].mean()),
                "average_market_excess_return": float(market_excess.mean()),
                "average_realized_strategy_return": float(subset["strategy_net_simple_return"].mean()),
                "negative_market_months": int((subset["market_simple_return"] < 0.0).sum()),
                "worst_market_month": float(subset["market_simple_return"].min()),
                "cumulative_avoided_market_loss_while_risk_free": avoided,
                "cumulative_missed_market_gain_while_risk_free": missed,
                "net_switching_cost_drag": float(subset["switching_cost_rate"].sum()),
                "contribution_to_final_wealth": float(state_factor - 1.0),
                "wealth_factor_from_state_months": state_factor,
            }
        )
    payload = {
        "attribution_only": True,
        "final_strategy_wealth": final_wealth,
        "cumulative_avoided_market_loss_while_in_risk_free": total_avoided_loss,
        "cumulative_missed_market_gain_while_in_risk_free": total_missed_gain,
        "net_switching_cost_drag": total_cost_drag,
        "state_factors_multiply_to_final_wealth": bool(
            np.isclose(np.prod([row["wealth_factor_from_state_months"] for row in rows]), final_wealth)
        ),
        "filters_or_signal_changes_created": False,
    }
    return rows, payload


def build_control_metrics(
    evaluation: pd.DataFrame,
    average_returns: pd.Series,
    beta_returns: pd.Series,
    dynamic_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    rf = evaluation["risk_free_simple_return"]
    dynamic = metrics_for_returns(
        "source_split_10bps_baseline",
        "corrected_dynamic_oil_signal",
        evaluation["strategy_net_simple_return"],
        rf,
    )
    average = metrics_for_returns(
        "average_exposure_static_control",
        "ex_post_diagnostic_benchmark",
        average_returns,
        rf,
    )
    beta = metrics_for_returns(
        "beta_matched_static_control",
        "ex_post_diagnostic_benchmark",
        beta_returns,
        rf,
    )
    dynamic["switching_cost_bps"] = SWITCHING_COST_BPS
    average["switching_cost_bps"] = 0
    beta["switching_cost_bps"] = 0
    for row in [dynamic, average, beta]:
        row["diagnostic_benchmark_only"] = row["series_id"] != "source_split_10bps_baseline"
        row["dynamic_baseline_cagr_difference"] = (
            float(dynamic["cagr"]) - float(row["cagr"]) if row["series_id"] != "source_split_10bps_baseline" else 0.0
        )
        row["dynamic_baseline_return_drawdown_proxy_difference"] = (
            float(dynamic["return_drawdown_proxy"]) - float(row["return_drawdown_proxy"])
            if row["series_id"] != "source_split_10bps_baseline"
            else 0.0
        )
        row["dynamic_baseline_total_return_difference"] = (
            float(dynamic["total_return"]) - float(row["total_return"])
            if row["series_id"] != "source_split_10bps_baseline"
            else 0.0
        )
    if abs(float(dynamic_metrics["total_return"]) - float(dynamic["total_return"])) > NUMERIC_TOLERANCE:
        dynamic["saved_baseline_metric_reconciliation_note"] = "saved baseline total return mismatch"
    else:
        dynamic["saved_baseline_metric_reconciliation_note"] = "matches saved corrected baseline"
    return [dynamic, average, beta]


def baseline_vs_control_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["series_id"]: row for row in metrics}
    dynamic = by_id["source_split_10bps_baseline"]
    rows = []
    for control_id in ["average_exposure_static_control", "beta_matched_static_control"]:
        control = by_id[control_id]
        rows.append(
            {
                "baseline_id": dynamic["series_id"],
                "control_id": control_id,
                "baseline_cagr": dynamic["cagr"],
                "control_cagr": control["cagr"],
                "baseline_minus_control_cagr": float(dynamic["cagr"]) - float(control["cagr"]),
                "baseline_return_drawdown_proxy": dynamic["return_drawdown_proxy"],
                "control_return_drawdown_proxy": control["return_drawdown_proxy"],
                "baseline_minus_control_return_drawdown_proxy": float(dynamic["return_drawdown_proxy"])
                - float(control["return_drawdown_proxy"]),
                "baseline_total_return": dynamic["total_return"],
                "control_total_return": control["total_return"],
                "baseline_minus_control_total_return": float(dynamic["total_return"]) - float(control["total_return"]),
                "baseline_exceeds_control_on_cagr": float(dynamic["cagr"]) > float(control["cagr"]),
                "baseline_exceeds_control_on_return_drawdown_proxy": float(dynamic["return_drawdown_proxy"])
                > float(control["return_drawdown_proxy"]),
            }
        )
    return rows


def classify_outcome(metrics: list[dict[str, Any]], jensen: dict[str, Any], timing: dict[str, Any]) -> str:
    by_id = {row["series_id"]: row for row in metrics}
    dynamic = by_id["source_split_10bps_baseline"]
    average = by_id["average_exposure_static_control"]
    beta = by_id["beta_matched_static_control"]
    dynamic_exceeds_both_cagr = float(dynamic["cagr"]) > float(average["cagr"]) and float(dynamic["cagr"]) > float(beta["cagr"])
    dynamic_exceeds_both_proxy = float(dynamic["return_drawdown_proxy"]) > float(
        average["return_drawdown_proxy"]
    ) and float(dynamic["return_drawdown_proxy"]) > float(beta["return_drawdown_proxy"])
    alpha_significant = float(jensen["monthly_alpha"]) > 0.0 and float(jensen["alpha_hc1_p_value"]) < 0.10
    timing_significant = float(timing["source_aligned_henriksson_merton_p_value"]) < 0.10
    weak_vs_average = float(dynamic["cagr"]) <= float(average["cagr"]) and float(
        dynamic["return_drawdown_proxy"]
    ) <= float(average["return_drawdown_proxy"])
    alpha_weak = float(jensen["monthly_alpha"]) <= 0.0 or float(jensen["alpha_hc1_p_value"]) >= 0.10
    timing_weak = float(timing["source_aligned_henriksson_merton_p_value"]) >= 0.10
    if dynamic_exceeds_both_cagr and dynamic_exceeds_both_proxy and alpha_significant and timing_significant:
        return "dynamic_signal_incremental_after_controls"
    if weak_vs_average and alpha_weak and timing_weak:
        return "dynamic_signal_control_weak"
    return "dynamic_signal_mixed_control_evidence"


def frozen_control_config(avg_config: dict[str, Any], beta_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "task_type": "benchmark_correction",
        "stage": "verification",
        "adaptation_label": ADAPTATION_LABEL,
        "source_correction_task_id": SOURCE_CORRECTION_TASK_ID,
        "source_expanding_variant_id": SOURCE_EXPANDING_VARIANT_ID,
        "dynamic_baseline": {
            "source": "evaluation_signal_audit.csv",
            "modified": False,
            "strategy_signal_recalculated": False,
            "oil_predictor_recomputed": False,
            "fixed_coefficients_reestimated": False,
        },
        "average_exposure_control": avg_config,
        "beta_matched_control": beta_config,
        "no_alternative_exposure_weights_generated": True,
        "no_parameter_predictor_split_or_instrument_alternative_tested": True,
        "no_overlay_performance_experiment": True,
        "static_controls_transaction_cost_bps": 0,
    }


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_driesprong_oil_signal_control_strength_audit_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_driesprong_oil_signal_control_strength_audit_v1.py -q",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_driesprong_oil_us_market_source_split_correction_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def consistency_payload(
    output: Path,
    outcome_payload: dict[str, Any],
    reconciliation: dict[str, Any],
    source_before: dict[str, str],
    source_after: dict[str, str],
    state_before: dict[str, str],
    state_after: dict[str, str],
) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in sorted(REQUIRED_OUTPUT_FILES)}
    required["consistency_check.json"] = True
    checks = {
        "required_files_present": all(required.values()),
        "outcome_allowed": outcome_payload["outcome"] in OUTCOMES,
        "source_corrected_evidence_preserved": source_before == source_after,
        "state_files_preserved": state_before == state_after,
        "existing_evidence_reconciled_or_defect_reported": reconciliation["reconciliation_passed"] is True
        or outcome_payload["outcome"] == "existing_evidence_reconciliation_defect",
        "average_exposure_weight_frozen": outcome_payload.get("average_market_weight_numerator") == EXPECTED_MARKET_STATES
        and outcome_payload.get("average_market_weight_denominator") == EXPECTED_EVALUATION_MONTHS,
        "only_one_average_exposure_control": outcome_payload.get("average_exposure_control_count") == 1,
        "beta_estimated_once": outcome_payload.get("beta_estimate_count") == 1,
        "hc1_standard_errors_used": outcome_payload.get("jensen_standard_error_method") == "White_HC1",
        "timing_uses_conditional_bull_bear_accuracy": outcome_payload.get(
            "timing_uses_conditional_bull_and_bear_accuracy"
        )
        is True,
        "static_controls_have_no_switching_costs": outcome_payload.get("static_controls_switching_cost_bps") == 0,
        "strategy_signal_not_recalculated": outcome_payload.get("strategy_signal_recalculated") is False,
        "no_parameter_predictor_split_or_instrument_alternatives": outcome_payload.get("parameter_search_run") is False
        and outcome_payload.get("predictor_alternative_tested") is False
        and outcome_payload.get("split_alternative_tested") is False
        and outcome_payload.get("instrument_alternative_tested") is False,
        "no_overlay_performance_artifact": not any("overlay_performance" in path.name for path in output.iterdir() if path.is_file()),
        "no_broker_promotion_or_paper_demo": outcome_payload.get("broker_write_called") is False
        and outcome_payload.get("promotion_eligibility") is False
        and outcome_payload.get("paper_demo_eligibility") is False
        and outcome_payload.get("paper_demo_state_changed") is False
        and outcome_payload.get("real_money_recommendation") is False,
        "next_action_exact": outcome_payload["next_action"] == NEXT_ACTION,
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def write_defect_outputs(
    root: Path,
    output: Path,
    reconciliation: dict[str, Any],
    source_before: dict[str, str],
    state_before: dict[str, str],
) -> dict[str, Any]:
    source_after = source_hashes(root)
    state_after = state_hashes(root)
    outcome = "existing_evidence_reconciliation_defect"
    tm_gate = TRADE_MANAGEMENT_GATES[outcome]
    outcome_payload = {
        "task_id": TASK_ID,
        "task_type": "benchmark_correction",
        "stage": "verification",
        "adaptation_label": ADAPTATION_LABEL,
        "created_utc": RUN_CREATED_UTC,
        "outcome": outcome,
        "trade_management_gate": tm_gate,
        "blocker": reconciliation.get("defect_reason", "existing evidence could not be reconciled"),
        "strategy_signal_recalculated": False,
        "parameter_search_run": False,
        "predictor_alternative_tested": False,
        "split_alternative_tested": False,
        "instrument_alternative_tested": False,
        "overlay_performance_experiment_run": False,
        "broker_write_called": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_state_changed": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    write_json(output / "existing_evidence_reconciliation.json", reconciliation)
    write_yaml(output / "frozen_control_config.yaml", {"task_id": TASK_ID, "implemented": False})
    write_csv(output / "average_exposure_control_series.csv", [], ["evaluation_month"])
    write_csv(output / "beta_matched_control_series.csv", [], ["evaluation_month"])
    write_csv(output / "control_metrics.csv", [], ["series_id"])
    write_json(output / "jensen_alpha_audit.json", {"implemented": False, "blocker": outcome_payload["blocker"]})
    write_json(output / "market_timing_audit.json", {"implemented": False, "blocker": outcome_payload["blocker"]})
    write_csv(output / "market_timing_confusion_matrix.csv", [], ["actual_state"])
    write_csv(output / "state_attribution.csv", [], ["target_state"])
    write_json(output / "economic_attribution.json", {"implemented": False, "blocker": outcome_payload["blocker"]})
    write_csv(output / "baseline_vs_controls.csv", [], ["baseline_id", "control_id"])
    write_json(output / "trade_management_gate.json", {"trade_management_gate": tm_gate, "overlay_performance_experiment_run": False})
    write_json(output / "verification_outcome.json", outcome_payload)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "verification_summary.md", verification_summary(outcome_payload, [], {}, {}, []))
    consistency = consistency_payload(output, outcome_payload, reconciliation, source_before, source_after, state_before, state_after)
    write_json(output / "consistency_check.json", consistency)
    return {**outcome_payload, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def verification_summary(
    outcome_payload: dict[str, Any],
    metrics: list[dict[str, Any]],
    jensen: dict[str, Any],
    timing: dict[str, Any],
    baseline_vs_controls: list[dict[str, Any]],
) -> str:
    if outcome_payload["outcome"] == "existing_evidence_reconciliation_defect":
        return f"""# Driesprong Oil Signal Control-Strength Audit

Outcome: `{outcome_payload['outcome']}`

Blocker: `{outcome_payload.get('blocker', '')}`

The existing corrected source-split evidence could not be reconciled exactly, so no control-strength calculations were used for interpretation.

Exact next action: `{NEXT_ACTION}`
"""
    by_id = {row["series_id"]: row for row in metrics}
    dynamic = by_id["source_split_10bps_baseline"]
    avg = by_id["average_exposure_static_control"]
    beta = by_id["beta_matched_static_control"]
    return f"""# Driesprong Oil Signal Control-Strength Audit

Outcome: `{outcome_payload['outcome']}`

Trade-management gate: `{outcome_payload['trade_management_gate']}`

Existing corrected source-split packet reconciled: `true`

Evaluation window: `{outcome_payload['evaluation_first_month']}` to `{outcome_payload['evaluation_last_month']}`

Evaluation months: `{outcome_payload['evaluation_month_count']}`

Average market exposure: `{outcome_payload['average_market_weight']}` (`210 / 242`)

Dynamic baseline CAGR: `{dynamic['cagr']}`

Average-exposure control CAGR: `{avg['cagr']}`

Beta-matched control CAGR: `{beta['cagr']}`

Dynamic baseline return/drawdown proxy: `{dynamic['return_drawdown_proxy']}`

Average-exposure control return/drawdown proxy: `{avg['return_drawdown_proxy']}`

Beta-matched control return/drawdown proxy: `{beta['return_drawdown_proxy']}`

Jensen monthly alpha: `{jensen['monthly_alpha']}`

Jensen annualized alpha: `{jensen['annualized_alpha']}`

Jensen alpha HC1 p-value: `{jensen['alpha_hc1_p_value']}`

Henriksson-Merton timing p-value: `{timing['source_aligned_henriksson_merton_p_value']}`

The audit created diagnostic controls only. It did not change the oil signal, fixed coefficients, chronological split, transaction costs, strategy rules, paper/demo state, broker paths, or lifecycle state.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    source_before = source_hashes(root)
    state_before = state_hashes(root)
    reconciliation, frames, extra = reconcile_existing_evidence(root, source_before)
    if not reconciliation["reconciliation_passed"]:
        return write_defect_outputs(root, output, reconciliation, source_before, state_before)

    evaluation = frames["evaluation"]
    rf_returns = evaluation["risk_free_simple_return"]
    strategy_excess = evaluation["strategy_net_simple_return"] - rf_returns
    market_excess = evaluation["market_simple_return"] - rf_returns
    regression = ols_with_hc1(market_excess, strategy_excess)
    jensen = {
        "model": "strategy_excess_return_t = alpha + beta * market_excess_return_t + error_t",
        "monthly_alpha": regression["alpha"],
        "annualized_alpha": annualize_monthly_alpha(regression["alpha"]),
        "beta": regression["beta"],
        "alpha_hc1_standard_error": regression["alpha_hc1_standard_error"],
        "beta_hc1_standard_error": regression["beta_hc1_standard_error"],
        "alpha_hc1_t_statistic": regression["alpha_hc1_t_statistic"],
        "alpha_hc1_p_value": regression["alpha_hc1_p_value"],
        "beta_hc1_t_statistic": regression["beta_hc1_t_statistic"],
        "beta_hc1_p_value": regression["beta_hc1_p_value"],
        "r_squared": regression["r_squared"],
        "observation_count": regression["observation_count"],
        "degrees_of_freedom": regression["degrees_of_freedom"],
        "hc1_scale_factor": regression["hc1_scale_factor"],
        "standard_error_method": regression["standard_error_method"],
        "inference": regression["inference"],
    }

    avg_returns, avg_rows, avg_config = average_exposure_control(evaluation)
    beta_returns, beta_rows, beta_config = beta_matched_control(evaluation, regression)
    metrics = build_control_metrics(evaluation, avg_returns, beta_returns, extra["dynamic_metrics"])
    baseline_vs_controls = baseline_vs_control_rows(metrics)
    timing, timing_matrix = market_timing_audit(evaluation)
    state_rows, economic = state_attribution(evaluation)
    outcome = classify_outcome(metrics, jensen, timing)
    tm_gate = TRADE_MANAGEMENT_GATES[outcome]
    source_after = source_hashes(root)
    state_after = state_hashes(root)
    by_id = {row["series_id"]: row for row in metrics}
    outcome_payload = {
        "task_id": TASK_ID,
        "task_type": "benchmark_correction",
        "stage": "verification",
        "adaptation_label": ADAPTATION_LABEL,
        "created_utc": RUN_CREATED_UTC,
        "source_correction_task_id": SOURCE_CORRECTION_TASK_ID,
        "source_expanding_variant_id": SOURCE_EXPANDING_VARIANT_ID,
        "source_evidence_path": str((root / SOURCE_DIR).resolve()),
        "outcome": outcome,
        "trade_management_gate": tm_gate,
        "blocker": "none",
        "evaluation_month_count": int(len(evaluation)),
        "evaluation_first_month": EXPECTED_FIRST_MONTH,
        "evaluation_last_month": EXPECTED_LAST_MONTH,
        "market_state_count": EXPECTED_MARKET_STATES,
        "risk_free_state_count": EXPECTED_RISK_FREE_STATES,
        "switch_count": EXPECTED_SWITCHES,
        "switching_cost_bps": SWITCHING_COST_BPS,
        "average_market_weight_numerator": EXPECTED_MARKET_STATES,
        "average_market_weight_denominator": EXPECTED_EVALUATION_MONTHS,
        "average_market_weight": avg_config["average_market_weight"],
        "average_rf_weight": avg_config["average_rf_weight"],
        "average_exposure_control_count": 1,
        "beta_estimate_count": 1,
        "estimated_beta": regression["beta"],
        "monthly_alpha": jensen["monthly_alpha"],
        "annualized_alpha": jensen["annualized_alpha"],
        "alpha_hc1_p_value": jensen["alpha_hc1_p_value"],
        "market_timing_p_value": timing["source_aligned_henriksson_merton_p_value"],
        "jensen_standard_error_method": jensen["standard_error_method"],
        "timing_uses_conditional_bull_and_bear_accuracy": timing["timing_test_uses_conditional_bull_and_bear_accuracy"],
        "dynamic_cagr": by_id["source_split_10bps_baseline"]["cagr"],
        "average_exposure_control_cagr": by_id["average_exposure_static_control"]["cagr"],
        "beta_matched_control_cagr": by_id["beta_matched_static_control"]["cagr"],
        "dynamic_return_drawdown_proxy": by_id["source_split_10bps_baseline"]["return_drawdown_proxy"],
        "average_exposure_control_return_drawdown_proxy": by_id["average_exposure_static_control"]["return_drawdown_proxy"],
        "beta_matched_control_return_drawdown_proxy": by_id["beta_matched_static_control"]["return_drawdown_proxy"],
        "static_controls_switching_cost_bps": 0,
        "strategy_signal_recalculated": False,
        "oil_predictor_recomputed": False,
        "fixed_coefficients_changed": False,
        "chronological_split_changed": False,
        "transaction_cost_assumptions_changed": False,
        "data_sources_changed": False,
        "market_or_risk_free_return_definitions_changed": False,
        "parameter_search_run": False,
        "predictor_alternative_tested": False,
        "split_alternative_tested": False,
        "instrument_alternative_tested": False,
        "overlay_performance_experiment_run": False,
        "broker_write_called": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_state_changed": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "source_corrected_evidence_preserved": source_before == source_after,
        "state_files_preserved": state_before == state_after,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "existing_evidence_reconciliation.json", reconciliation)
    write_yaml(output / "frozen_control_config.yaml", frozen_control_config(avg_config, beta_config))
    write_csv(
        output / "average_exposure_control_series.csv",
        avg_rows,
        [
            "evaluation_month",
            "average_market_weight",
            "average_rf_weight",
            "market_simple_return",
            "risk_free_simple_return",
            "exposure_matched_simple_return",
            "equity",
            "switching_cost_rate",
            "diagnostic_benchmark_only",
        ],
    )
    write_csv(
        output / "beta_matched_control_series.csv",
        beta_rows,
        [
            "evaluation_month",
            "estimated_beta",
            "market_simple_return",
            "risk_free_simple_return",
            "market_excess_return",
            "beta_matched_simple_return",
            "equity",
            "switching_cost_rate",
            "diagnostic_benchmark_only",
        ],
    )
    write_csv(
        output / "control_metrics.csv",
        metrics,
        [
            "series_id",
            "role",
            "start_month",
            "end_month",
            "months",
            "total_return",
            "cagr",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_ratio_vs_rf",
            "return_drawdown_proxy",
            "switching_cost_bps",
            "diagnostic_benchmark_only",
            "dynamic_baseline_cagr_difference",
            "dynamic_baseline_return_drawdown_proxy_difference",
            "dynamic_baseline_total_return_difference",
            "saved_baseline_metric_reconciliation_note",
        ],
    )
    write_json(output / "jensen_alpha_audit.json", jensen)
    write_json(output / "market_timing_audit.json", timing)
    write_csv(
        output / "market_timing_confusion_matrix.csv",
        timing_matrix,
        ["actual_state", "predicted_bear_count", "predicted_bull_count", "actual_total"],
    )
    write_csv(
        output / "state_attribution.csv",
        state_rows,
        [
            "target_state",
            "months",
            "average_market_return",
            "average_market_excess_return",
            "average_realized_strategy_return",
            "negative_market_months",
            "worst_market_month",
            "cumulative_avoided_market_loss_while_risk_free",
            "cumulative_missed_market_gain_while_risk_free",
            "net_switching_cost_drag",
            "contribution_to_final_wealth",
            "wealth_factor_from_state_months",
        ],
    )
    write_json(output / "economic_attribution.json", economic)
    write_csv(
        output / "baseline_vs_controls.csv",
        baseline_vs_controls,
        [
            "baseline_id",
            "control_id",
            "baseline_cagr",
            "control_cagr",
            "baseline_minus_control_cagr",
            "baseline_return_drawdown_proxy",
            "control_return_drawdown_proxy",
            "baseline_minus_control_return_drawdown_proxy",
            "baseline_total_return",
            "control_total_return",
            "baseline_minus_control_total_return",
            "baseline_exceeds_control_on_cagr",
            "baseline_exceeds_control_on_return_drawdown_proxy",
        ],
    )
    write_json(
        output / "trade_management_gate.json",
        {
            "trade_management_gate": tm_gate,
            "mapping_source": outcome,
            "overlay_performance_experiment_run": False,
            "trade_management_overlays_must_not_manufacture_baseline_edge": True,
        },
    )
    write_json(output / "verification_outcome.json", outcome_payload)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "verification_summary.md", verification_summary(outcome_payload, metrics, jensen, timing, baseline_vs_controls))
    consistency = consistency_payload(output, outcome_payload, reconciliation, source_before, source_after, state_before, state_after)
    write_json(output / "consistency_check.json", consistency)
    return {**outcome_payload, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
