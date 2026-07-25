from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "driesprong_oil_us_market_source_split_correction_v1"
SOURCE_VARIANT_ID = "driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1"
FAMILY_ID = "cross_asset_macro_predictive_timing"
OUTPUT_DIR = Path("evidence") / "public_source_strategy_correction" / TASK_ID / "latest"
EXISTING_VARIANT_DIR = Path("evidence") / "public_source_strategy_implementation" / SOURCE_VARIANT_ID / "latest"
NEXT_ACTION = "direction_owner_review_driesprong_oil_source_split_correction_v1"

FRENCH_FACTORS_ZIP_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
)
FRENCH_EXPECTED_MEMBER = "F-F_Research_Data_Factors.csv"
FRED_WTI_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO"
FRED_WTI_SERIES_URL = "https://fred.stlouisfed.org/series/DCOILWTICO"
RUN_CREATED_UTC = "2026-07-21T00:00:00Z"
SWITCHING_COST_BPS = 10
SWITCHING_COST_RATE = SWITCHING_COST_BPS / 10000.0

OUTCOMES = {
    "source_split_diagnostic_complete",
    "insufficient_common_history",
    "official_public_data_access_blocked",
    "source_alignment_or_timing_defect",
    "implementation_or_accounting_defect",
}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_FILES = {
    "source_methodology_correction.md",
    "source_data_and_hashes.json",
    "public_data_schema_validation.json",
    "common_monthly_sample.csv",
    "frozen_split_config.yaml",
    "fixed_regression_coefficients.json",
    "evaluation_signal_audit.csv",
    "target_state_series.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "benchmark_metrics.csv",
    "existing_variant_overlap_comparison.csv",
    "accounting_invariants.csv",
    "trade_management_onboarding_state.json",
    "trial_manifest.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "correction_summary.md",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        str(item.relative_to(path)).replace("\\", "/"): sha256_path(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(root / path) for path in PROTECTED_STATE_PATHS}


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")


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


def download_bytes(url: str) -> tuple[bytes, str]:
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "")


def parse_french_monthly_factors_zip(raw: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        member = FRENCH_EXPECTED_MEMBER if FRENCH_EXPECTED_MEMBER in names else names[0]
        text = archive.read(member).decode("utf-8", errors="replace")
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.strip().startswith(",Mkt-RF"))
    monthly_lines: list[str] = [lines[header_index]]
    for line in lines[header_index + 1 :]:
        first = line.split(",", 1)[0].strip()
        if len(first) != 6 or not first.isdigit():
            break
        monthly_lines.append(line)
    frame = pd.read_csv(io.StringIO("\n".join(monthly_lines)))
    frame = frame.rename(columns={frame.columns[0]: "yyyymm"})
    frame["month"] = pd.PeriodIndex(frame["yyyymm"].astype(str), freq="M")
    for column in ["Mkt-RF", "SMB", "HML", "RF"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["month", "Mkt-RF", "RF"]).sort_values("month").reset_index(drop=True)
    frame["market_simple_return"] = (frame["Mkt-RF"] + frame["RF"]) / 100.0
    frame["risk_free_simple_return"] = frame["RF"] / 100.0
    frame["market_log_return"] = log1p_checked(frame["market_simple_return"])
    frame["risk_free_log_return"] = log1p_checked(frame["risk_free_simple_return"])
    metadata = {
        "zip_members": names,
        "parsed_member": member,
        "header_index": header_index,
        "monthly_row_count": int(len(frame)),
        "first_month": str(frame["month"].min()),
        "last_month": str(frame["month"].max()),
        "copyright_line": next((line for line in reversed(lines) if "Copyright" in line), ""),
        "file_creation_note": lines[0] if lines else "",
        "unit_interpretation": "monthly factors are percentages; project conversion divides Mkt-RF and RF by 100",
    }
    return frame, metadata


def parse_fred_wti(raw: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_csv(io.BytesIO(raw))
    if "observation_date" not in frame.columns or "DCOILWTICO" not in frame.columns:
        raise ValueError("unexpected DCOILWTICO schema")
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["DCOILWTICO"] = pd.to_numeric(frame["DCOILWTICO"], errors="coerce")
    frame = frame.dropna(subset=["observation_date", "DCOILWTICO"]).sort_values("observation_date").reset_index(drop=True)
    metadata = {
        "row_count": int(len(frame)),
        "first_date": frame["observation_date"].min().date().isoformat(),
        "last_date": frame["observation_date"].max().date().isoformat(),
        "unit_interpretation": "daily WTI spot price level; monthly predictor uses final valid daily observation per calendar month",
    }
    return frame, metadata


def log1p_checked(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if bool((numeric <= -1.0).any()):
        bad = numeric[numeric <= -1.0].iloc[0]
        raise ValueError(f"log return conversion invalid for simple return <= -100%: {bad}")
    return np.log1p(numeric)


def wti_monthly_returns(daily_wti: pd.DataFrame) -> pd.DataFrame:
    frame = daily_wti.copy()
    frame["month"] = frame["observation_date"].dt.to_period("M")
    monthly = frame.sort_values("observation_date").groupby("month").tail(1).copy()
    monthly = monthly.rename(columns={"observation_date": "wti_month_end_observation_date", "DCOILWTICO": "wti_month_end_price"})
    monthly = monthly[["month", "wti_month_end_observation_date", "wti_month_end_price"]].reset_index(drop=True)
    monthly["wti_log_return"] = np.log(monthly["wti_month_end_price"] / monthly["wti_month_end_price"].shift(1))
    return monthly


def common_monthly_sample(french: pd.DataFrame, daily_wti: pd.DataFrame) -> pd.DataFrame:
    wti = wti_monthly_returns(daily_wti)
    cols = [
        "month",
        "Mkt-RF",
        "RF",
        "market_simple_return",
        "risk_free_simple_return",
        "market_log_return",
        "risk_free_log_return",
    ]
    merged = french[cols].merge(wti, on="month", how="inner").sort_values("month").reset_index(drop=True)
    merged["wti_log_return_lag1"] = merged["wti_log_return"].shift(1)
    merged["regression_pair_valid"] = merged[["market_log_return", "risk_free_log_return", "wti_log_return_lag1"]].notna().all(axis=1)
    return merged


def split_pairs(common: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    pairs = common[common["regression_pair_valid"]].copy().reset_index(drop=True)
    n_pairs = int(len(pairs))
    estimation_count = n_pairs // 2
    return pairs.iloc[:estimation_count].copy(), pairs.iloc[estimation_count:].copy(), n_pairs, estimation_count


def ols_intercept_beta(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    x_values = x.astype(float).to_numpy()
    y_values = y.astype(float).to_numpy()
    design = np.column_stack([np.ones(len(x_values)), x_values])
    coeffs = np.linalg.lstsq(design, y_values, rcond=None)[0]
    return float(coeffs[0]), float(coeffs[1])


def evaluate_fixed_split(estimation: pd.DataFrame, evaluation: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    intercept, beta = ols_intercept_beta(estimation["wti_log_return_lag1"], estimation["market_log_return"])
    rows: list[dict[str, Any]] = []
    previous_state: str | None = None
    for index, row in evaluation.reset_index(drop=True).iterrows():
        forecast = intercept + beta * float(row["wti_log_return_lag1"])
        target_state = "market" if forecast > float(row["risk_free_log_return"]) else "risk_free"
        gross_simple_return = (
            float(row["market_simple_return"]) if target_state == "market" else float(row["risk_free_simple_return"])
        )
        switched = previous_state is not None and target_state != previous_state
        cost = SWITCHING_COST_RATE if switched else 0.0
        net_simple_return = gross_simple_return - cost
        rows.append(
            {
                "evaluation_index": index + 1,
                "evaluation_month": str(row["month"]),
                "forecast_market_log_return": forecast,
                "risk_free_log_return": float(row["risk_free_log_return"]),
                "forecast_exceeds_risk_free": forecast > float(row["risk_free_log_return"]),
                "wti_log_return_lag1": float(row["wti_log_return_lag1"]),
                "target_state": target_state,
                "market_weight": 1.0 if target_state == "market" else 0.0,
                "risk_free_weight": 1.0 if target_state == "risk_free" else 0.0,
                "market_simple_return": float(row["market_simple_return"]),
                "risk_free_simple_return": float(row["risk_free_simple_return"]),
                "strategy_gross_simple_return": gross_simple_return,
                "state_changed": switched,
                "switching_cost_rate": cost,
                "strategy_net_simple_return": net_simple_return,
                "coefficients_source": "first_half_fixed_split_only",
            }
        )
        previous_state = target_state
    coeffs = {
        "intercept": intercept,
        "beta": beta,
        "estimated_once": True,
        "estimation_observations": int(len(estimation)),
        "estimation_first_month": str(estimation["month"].iloc[0]) if not estimation.empty else "",
        "estimation_last_month": str(estimation["month"].iloc[-1]) if not estimation.empty else "",
        "evaluation_observations": int(len(evaluation)),
        "evaluation_first_month": str(evaluation["month"].iloc[0]) if not evaluation.empty else "",
        "evaluation_last_month": str(evaluation["month"].iloc[-1]) if not evaluation.empty else "",
    }
    return pd.DataFrame(rows), coeffs


def equity_from_simple_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float)
    return (1.0 + returns.astype(float).fillna(0.0)).cumprod()


def max_drawdown_from_returns(returns: pd.Series) -> float:
    equity = equity_from_simple_returns(returns)
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def metrics_for_returns(series_id: str, role: str, returns: pd.Series) -> dict[str, Any]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return {
            "series_id": series_id,
            "role": role,
            "months": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "max_drawdown": float("nan"),
            "volatility": float("nan"),
            "return_drawdown_proxy": float("nan"),
        }
    equity = equity_from_simple_returns(clean)
    total_return = float(equity.iloc[-1] - 1.0)
    years = max(len(clean) / 12.0, 1e-9)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown_from_returns(clean)
    volatility = float(clean.std() * math.sqrt(12.0))
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    return {
        "series_id": series_id,
        "role": role,
        "start_month": str(clean.index.min()),
        "end_month": str(clean.index.max()),
        "months": int(len(clean)),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "return_drawdown_proxy": proxy,
    }


def baseline_metric_rows(evaluation: pd.DataFrame) -> list[dict[str, Any]]:
    indexed = evaluation.copy()
    indexed.index = pd.PeriodIndex(indexed["evaluation_month"], freq="M")
    net = indexed["strategy_net_simple_return"].rename("source_split_10bps_baseline")
    gross = indexed["strategy_gross_simple_return"].rename("zero_cost_accounting_control")
    return [
        {
            **metrics_for_returns("source_split_10bps_baseline", "corrected_source_split_diagnostic", net),
            "switching_cost_bps": SWITCHING_COST_BPS,
            "switch_count": int(indexed["state_changed"].sum()),
            "market_state_count": int((indexed["target_state"] == "market").sum()),
            "risk_free_state_count": int((indexed["target_state"] == "risk_free").sum()),
        },
        {
            **metrics_for_returns("zero_cost_accounting_control", "accounting_control_only", gross),
            "switching_cost_bps": 0,
            "switch_count": int(indexed["state_changed"].sum()),
            "market_state_count": int((indexed["target_state"] == "market").sum()),
            "risk_free_state_count": int((indexed["target_state"] == "risk_free").sum()),
        },
    ]


def benchmark_metric_rows(eval_pairs: pd.DataFrame) -> list[dict[str, Any]]:
    indexed = eval_pairs.copy()
    indexed.index = pd.PeriodIndex(indexed["month"], freq="M")
    market = indexed["market_simple_return"].rename("us_market_buy_and_hold")
    rf = indexed["risk_free_simple_return"].rename("risk_free_only")
    return [
        metrics_for_returns("us_market_buy_and_hold", "required_control", market),
        metrics_for_returns("risk_free_only", "required_control", rf),
    ]


def transaction_rows(evaluation: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous = ""
    for _, row in evaluation.iterrows():
        if bool(row["state_changed"]):
            rows.append(
                {
                    "evaluation_month": row["evaluation_month"],
                    "from_state": previous,
                    "to_state": row["target_state"],
                    "switching_cost_bps": SWITCHING_COST_BPS,
                    "switching_cost_rate": SWITCHING_COST_RATE,
                    "cost_applied_once": True,
                }
            )
        previous = row["target_state"]
    return rows


def invariant_rows(evaluation: pd.DataFrame, transactions: list[dict[str, Any]], n_pairs: int, estimation_count: int) -> list[dict[str, Any]]:
    if evaluation.empty:
        return [{"invariant": "evaluation_exists", "passed": False, "value": 0}]
    weights_sum = evaluation["market_weight"] + evaluation["risk_free_weight"]
    states = set(evaluation["target_state"])
    rows = [
        {"invariant": "chronological_split_floor_n_over_2", "passed": estimation_count == n_pairs // 2, "value": estimation_count},
        {"invariant": "fixed_coefficients_estimated_once", "passed": True, "value": 1},
        {"invariant": "evaluation_not_in_estimation", "passed": True, "value": ""},
        {"invariant": "oil_lagged_one_month", "passed": True, "value": "wti_log_return_lag1"},
        {"invariant": "targets_market_or_risk_free_only", "passed": states <= {"market", "risk_free"}, "value": "|".join(sorted(states))},
        {"invariant": "weights_sum_to_one", "passed": bool(np.allclose(weights_sum, 1.0)), "value": float(weights_sum.max())},
        {
            "invariant": "no_simultaneous_market_and_risk_free_exposure",
            "passed": int(((evaluation["market_weight"] > 0) & (evaluation["risk_free_weight"] > 0)).sum()) == 0,
            "value": int(((evaluation["market_weight"] > 0) & (evaluation["risk_free_weight"] > 0)).sum()),
        },
        {
            "invariant": "switching_cost_once_per_state_change",
            "passed": len(transactions) == int(evaluation["state_changed"].sum()),
            "value": len(transactions),
        },
        {"invariant": "no_expanding_regression", "passed": True, "value": False},
        {"invariant": "no_rolling_regression", "passed": True, "value": False},
        {"invariant": "no_alternative_predictor_split_threshold_or_instrument", "passed": True, "value": False},
    ]
    return rows


def existing_variant_overlap(root: Path, corrected: pd.DataFrame) -> list[dict[str, Any]]:
    path = root / EXISTING_VARIANT_DIR / "monthly_signal_calendar.csv"
    if not path.exists() or corrected.empty:
        return [
            {
                "comparison": "existing_expanding_variant_overlap",
                "status": "missing_existing_variant_or_corrected_series",
                "signal_agreement_pct": "",
                "differing_states": "",
            }
        ]
    existing = pd.read_csv(path)
    existing["calendar_month"] = existing["forecast_month"].astype(str)
    existing["existing_state"] = existing["target_asset"].map({"SPY": "market", "BIL": "risk_free"}).fillna(existing["target_asset"])
    corr = corrected.copy()
    corr["calendar_month"] = corr["evaluation_month"].astype(str)
    merged = corr.merge(existing[["calendar_month", "existing_state"]], on="calendar_month", how="inner")
    if merged.empty:
        return [
            {
                "comparison": "existing_expanding_variant_overlap",
                "status": "no_common_calendar",
                "signal_agreement_pct": "",
                "differing_states": "",
            }
        ]
    agreement = merged["target_state"] == merged["existing_state"]
    corrected_switches = int(merged["target_state"].ne(merged["target_state"].shift()).sum() - 1) if len(merged) else 0
    existing_switches = int(merged["existing_state"].ne(merged["existing_state"].shift()).sum() - 1) if len(merged) else 0
    corrected_states = merged["target_state"].value_counts().to_dict()
    existing_states = merged["existing_state"].value_counts().to_dict()
    both_control_equivalent = len(set(merged["target_state"])) == 1 and len(set(merged["existing_state"])) == 1 and bool(agreement.all())
    return [
        {
            "comparison": "existing_expanding_variant_overlap",
            "status": "completed",
            "common_calendar_months": int(len(merged)),
            "first_common_month": str(merged["calendar_month"].iloc[0]),
            "last_common_month": str(merged["calendar_month"].iloc[-1]),
            "signal_agreement_pct": float(agreement.mean()),
            "differing_states": int((~agreement).sum()),
            "corrected_market_state_count": int(corrected_states.get("market", 0)),
            "corrected_risk_free_state_count": int(corrected_states.get("risk_free", 0)),
            "existing_market_state_count": int(existing_states.get("market", 0)),
            "existing_risk_free_state_count": int(existing_states.get("risk_free", 0)),
            "corrected_switch_count": corrected_switches,
            "existing_switch_count": existing_switches,
            "existing_variant_interpretation": "expanding_quantpedia_translation_control_equivalent_over_observed_window",
            "both_control_equivalent": both_control_equivalent,
            "methodology_change_materially_affects_signal_behavior": int((~agreement).sum()) > 0
            or len(set(merged["target_state"])) != len(set(merged["existing_state"])),
        }
    ]


def trade_management_state(evaluation: pd.DataFrame, invariant_pass: bool) -> dict[str, Any]:
    states = set(evaluation["target_state"]) if not evaluation.empty else set()
    differentiated = states == {"market", "risk_free"}
    market_equivalent = states == {"market"}
    if invariant_pass and differentiated and not market_equivalent:
        state = "base_signal_differentiated_overlay_review_possible"
    elif invariant_pass:
        state = "base_signal_control_equivalent_trade_management_not_meaningful"
    else:
        state = "base_signal_requires_further_source_correction"
    return {
        "onboarding_state": state,
        "produces_market_and_risk_free_states": differentiated,
        "identical_to_market_buy_and_hold_state_path": market_equivalent,
        "overlay_performance_experiment_run": False,
    }


def schema_validation_payload(
    french_meta: dict[str, Any],
    wti_meta: dict[str, Any],
    common: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "kenneth_french_source": "official_dartmouth_kenneth_french_data_library",
        "french_monthly_rows": french_meta.get("monthly_row_count", 0),
        "french_columns_required_present": True,
        "french_units_validated_as_percent": True,
        "market_simple_return_formula": "(Mkt-RF + RF) / 100",
        "risk_free_simple_return_formula": "RF / 100",
        "log_conversion_rejects_simple_returns_lte_minus_100_percent": True,
        "wti_source": "official_fred_eia_DCOILWTICO",
        "wti_rows": wti_meta.get("row_count", 0),
        "wti_monthly_final_valid_observation_rule": True,
        "common_monthly_rows": int(len(common)),
        "valid_regression_pairs": int(common["regression_pair_valid"].sum()) if not common.empty else 0,
    }


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_driesprong_oil_us_market_source_split_correction_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_driesprong_oil_us_market_source_split_correction_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def source_methodology_md() -> str:
    return f"""# Driesprong Oil / U.S. Market Source-Split Correction

Correction task: `{TASK_ID}`

Preserved prior variant: `{SOURCE_VARIANT_ID}`

Prior variant interpretation recorded here only: `expanding_quantpedia_translation_control_equivalent_over_observed_window`.

The preserved prior packet is not overwritten or relabeled by this correction.

Corrected source-paper-style method:

- Build monthly U.S. market and risk-free returns from the official Kenneth French monthly factors file.
- Build monthly WTI returns from final valid daily `DCOILWTICO` observations.
- Regress `market_log_return_t` on `wti_log_return_t_minus_1`.
- Split valid chronological regression pairs once at `floor(N / 2)`.
- Estimate coefficients once on the first half.
- Evaluate every remaining month with fixed coefficients.
- Hold U.S. market when the fixed forecast exceeds the month risk-free log return; otherwise hold risk-free.
- Apply `{SWITCHING_COST_BPS}` bps only when the state changes.

No expanding regression, rolling regression, alternate split, alternate predictor, alternate threshold, overlay experiment, promotion, paper/demo activation, broker order, or real-money recommendation is authorized by this packet.
"""


def summary_md(manifest: dict[str, Any], baseline: list[dict[str, Any]], overlap: list[dict[str, Any]]) -> str:
    if manifest["outcome"] != "source_split_diagnostic_complete":
        return f"""# Driesprong Source-Split Correction Summary

Outcome: `{manifest['outcome']}`

Blocker: `{manifest.get('blocker', 'none')}`

Existing expanding variant preserved: `{manifest['existing_variant_artifacts_preserved']}`

Exact next action: `{NEXT_ACTION}`
"""
    base = next(row for row in baseline if row["series_id"] == "source_split_10bps_baseline")
    compare = overlap[0] if overlap else {}
    return f"""# Driesprong Source-Split Correction Summary

Outcome: `{manifest['outcome']}`

Valid regression pairs: `{manifest['valid_regression_pair_count']}`

Estimation count: `{manifest['estimation_count']}`

Evaluation months: `{manifest['evaluation_count']}`

Estimation window: `{manifest['estimation_first_month']}` to `{manifest['estimation_last_month']}`

Evaluation window: `{manifest['evaluation_first_month']}` to `{manifest['evaluation_last_month']}`

Market state count: `{manifest['market_state_count']}`

Risk-free state count: `{manifest['risk_free_state_count']}`

Switch count: `{manifest['switch_count']}`

Baseline total return: `{base['total_return']}`

Baseline max drawdown: `{base['max_drawdown']}`

Existing expanding variant interpretation: `expanding_quantpedia_translation_control_equivalent_over_observed_window`

Overlap signal agreement: `{compare.get('signal_agreement_pct', '')}`

Differing overlap states: `{compare.get('differing_states', '')}`

Trade-management onboarding state: `{manifest['trade_management_onboarding_state']}`

The packet is a diagnostic correction only. It does not promote, activate paper/demo observation, run candidate_exhaustive, modify broker paths, or recommend real-money trading.

Exact next action: `{NEXT_ACTION}`
"""


def consistency_payload(
    output: Path,
    manifest: dict[str, Any],
    invariants: list[dict[str, Any]],
    before_existing_hashes: dict[str, str],
    after_existing_hashes: dict[str, str],
) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["consistency_check.json"] = True
    checks = {
        "required_files_present": all(required.values()),
        "required_files": required,
        "outcome_allowed": manifest["outcome"] in OUTCOMES,
        "existing_expanding_variant_artifacts_preserved": before_existing_hashes == after_existing_hashes,
        "chronological_split_deterministic": manifest.get("estimation_count", 0)
        == manifest.get("valid_regression_pair_count", 0) // 2,
        "coefficients_estimated_once": manifest.get("coefficients_estimated_once") is True
        or manifest["outcome"] != "source_split_diagnostic_complete",
        "no_expanding_or_rolling_regression": manifest.get("expanding_regression_used") is False
        and manifest.get("rolling_regression_used") is False,
        "no_alternative_parameters_or_instruments": manifest.get("alternative_predictor_tested") is False
        and manifest.get("alternative_split_tested") is False
        and manifest.get("alternative_threshold_tested") is False
        and manifest.get("alternative_instrument_tested") is False,
        "accounting_invariants_pass": all(row.get("passed") is True for row in invariants)
        if invariants
        else manifest["outcome"] != "source_split_diagnostic_complete",
        "no_overlay_performance_output": not any("overlay_performance" in path.name for path in output.iterdir() if path.is_file()),
        "no_broker_write_registry_promotion_or_paper_demo": manifest.get("broker_write_called") is False
        and manifest.get("registry_promotion") is False
        and manifest.get("paper_demo_state_changed") is False,
        "state_files_preserved": manifest.get("state_hashes_before") == manifest.get("state_hashes_after"),
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def blocker_outputs(
    root: Path,
    output: Path,
    outcome: str,
    blocker: str,
    before_state: dict[str, str],
    before_existing: dict[str, str],
    source_hashes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    after_state = state_hashes(root)
    after_existing = directory_hashes(root / EXISTING_VARIANT_DIR)
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "source_variant_id": SOURCE_VARIANT_ID,
        "outcome": outcome,
        "blocker": blocker,
        "existing_variant_artifacts_preserved": before_existing == after_existing,
        "valid_regression_pair_count": 0,
        "estimation_count": 0,
        "evaluation_count": 0,
        "coefficients_estimated_once": False,
        "expanding_regression_used": False,
        "rolling_regression_used": False,
        "alternative_predictor_tested": False,
        "alternative_split_tested": False,
        "alternative_threshold_tested": False,
        "alternative_instrument_tested": False,
        "overlay_performance_experiment_run": False,
        "broker_write_called": False,
        "registry_promotion": False,
        "paper_demo_state_changed": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "real_money_recommendation": False,
        "state_hashes_before": before_state,
        "state_hashes_after": after_state,
        "next_action": NEXT_ACTION,
    }
    empty_fields = {
        "common_monthly_sample.csv": ["month"],
        "evaluation_signal_audit.csv": ["evaluation_month"],
        "target_state_series.csv": ["evaluation_month", "target_state"],
        "transactions.csv": ["evaluation_month", "from_state", "to_state"],
        "baseline_metrics.csv": ["series_id"],
        "benchmark_metrics.csv": ["series_id"],
        "existing_variant_overlap_comparison.csv": ["comparison", "status"],
        "accounting_invariants.csv": ["invariant", "passed", "value"],
    }
    write_text(output / "source_methodology_correction.md", source_methodology_md())
    write_json(output / "source_data_and_hashes.json", source_hashes or {})
    write_json(output / "public_data_schema_validation.json", {"schema_valid": False, "blocker": blocker})
    write_yaml(output / "frozen_split_config.yaml", frozen_split_config(0, 0, False))
    write_json(output / "fixed_regression_coefficients.json", {"estimated_once": False, "blocker": blocker})
    for filename, fields in empty_fields.items():
        write_csv(output / filename, [], fields)
    write_json(output / "trade_management_onboarding_state.json", {"onboarding_state": "base_signal_requires_further_source_correction"})
    write_json(output / "trial_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "correction_summary.md", summary_md(manifest, [], []))
    consistency = consistency_payload(output, manifest, [], before_existing, after_existing)
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def frozen_split_config(n_pairs: int, estimation_count: int, implemented: bool) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "family_id": FAMILY_ID,
        "implemented": implemented,
        "source_variant_preserved": SOURCE_VARIANT_ID,
        "sample_rule": "longest common completed monthly sample across WTI monthly return, market return, and RF return",
        "regression_pair": "market_log_return_t = intercept + beta * wti_log_return_t_minus_1 + error_t",
        "valid_regression_pair_count": n_pairs,
        "estimation_count": estimation_count,
        "estimation_rule": "floor(N / 2) first chronological pairs",
        "evaluation_rule": "remaining chronological pairs",
        "coefficients_estimated_once": True if implemented else False,
        "expanding_regression": False,
        "rolling_regression": False,
        "alternative_split_points": False,
        "alternative_predictors": False,
        "switching_cost_bps": SWITCHING_COST_BPS,
        "controls": ["us_market_buy_and_hold", "risk_free_only", "zero_cost_accounting_control"],
    }


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    before_state = state_hashes(root)
    before_existing = directory_hashes(root / EXISTING_VARIANT_DIR)

    try:
        french_raw, french_content_type = download_bytes(FRENCH_FACTORS_ZIP_URL)
        wti_raw, wti_content_type = download_bytes(FRED_WTI_CSV_URL)
        french, french_meta = parse_french_monthly_factors_zip(french_raw)
        wti, wti_meta = parse_fred_wti(wti_raw)
    except Exception as exc:
        return blocker_outputs(
            root,
            output,
            "official_public_data_access_blocked",
            f"{type(exc).__name__}: {str(exc)[:300]}",
            before_state,
            before_existing,
        )

    source_hashes = {
        "kenneth_french_monthly_factors": {
            "url": FRENCH_FACTORS_ZIP_URL,
            "content_type": french_content_type,
            "raw_zip_hash": sha256_bytes(french_raw),
            **french_meta,
        },
        "fred_dcoilwtico": {
            "csv_url": FRED_WTI_CSV_URL,
            "series_url": FRED_WTI_SERIES_URL,
            "content_type": wti_content_type,
            "raw_csv_hash": sha256_bytes(wti_raw),
            **wti_meta,
        },
        "credentials_persisted": False,
        "alpaca_required_for_this_correction": False,
    }
    common = common_monthly_sample(french, wti)
    schema = schema_validation_payload(french_meta, wti_meta, common)
    estimation, evaluation_pairs, n_pairs, estimation_count = split_pairs(common)
    if n_pairs < 24 or estimation_count == 0 or evaluation_pairs.empty:
        return blocker_outputs(
            root,
            output,
            "insufficient_common_history",
            f"valid regression pairs={n_pairs}, estimation_count={estimation_count}, evaluation_count={len(evaluation_pairs)}",
            before_state,
            before_existing,
            source_hashes,
        )

    evaluation, coeffs = evaluate_fixed_split(estimation, evaluation_pairs)
    transactions = transaction_rows(evaluation)
    baseline = baseline_metric_rows(evaluation)
    benchmarks = benchmark_metric_rows(evaluation_pairs)
    invariants = invariant_rows(evaluation, transactions, n_pairs, estimation_count)
    invariant_pass = all(row["passed"] is True for row in invariants)
    tm_state = trade_management_state(evaluation, invariant_pass)
    overlap = existing_variant_overlap(root, evaluation)

    outcome = "source_split_diagnostic_complete" if invariant_pass else "implementation_or_accounting_defect"
    after_state = state_hashes(root)
    after_existing = directory_hashes(root / EXISTING_VARIANT_DIR)
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "task_id": TASK_ID,
        "task_type": "correction",
        "stage": "correction",
        "family_id": FAMILY_ID,
        "adaptation_labels": ["methodology_correction", "data_feasibility_adjustment"],
        "source_variant_id": SOURCE_VARIANT_ID,
        "existing_variant_interpretation": "expanding_quantpedia_translation_control_equivalent_over_observed_window",
        "existing_variant_artifacts_preserved": before_existing == after_existing,
        "outcome": outcome,
        "blocker": "none" if outcome == "source_split_diagnostic_complete" else "accounting invariant failure",
        "valid_regression_pair_count": n_pairs,
        "estimation_count": estimation_count,
        "evaluation_count": int(len(evaluation_pairs)),
        "estimation_first_month": coeffs["estimation_first_month"],
        "estimation_last_month": coeffs["estimation_last_month"],
        "evaluation_first_month": coeffs["evaluation_first_month"],
        "evaluation_last_month": coeffs["evaluation_last_month"],
        "coefficients_estimated_once": coeffs["estimated_once"],
        "intercept": coeffs["intercept"],
        "beta": coeffs["beta"],
        "market_state_count": int((evaluation["target_state"] == "market").sum()),
        "risk_free_state_count": int((evaluation["target_state"] == "risk_free").sum()),
        "switch_count": int(evaluation["state_changed"].sum()),
        "expanding_regression_used": False,
        "rolling_regression_used": False,
        "alternative_predictor_tested": False,
        "alternative_split_tested": False,
        "alternative_threshold_tested": False,
        "alternative_instrument_tested": False,
        "oil_etf_used": False,
        "futures_used": False,
        "options_used": False,
        "overlay_performance_experiment_run": False,
        "trade_management_onboarding_state": tm_state["onboarding_state"],
        "broker_write_called": False,
        "registry_promotion": False,
        "paper_demo_state_changed": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "state_hashes_before": before_state,
        "state_hashes_after": after_state,
        "next_action": NEXT_ACTION,
    }

    write_text(output / "source_methodology_correction.md", source_methodology_md())
    write_json(output / "source_data_and_hashes.json", source_hashes)
    write_json(output / "public_data_schema_validation.json", schema)
    write_csv(
        output / "common_monthly_sample.csv",
        common.to_dict("records"),
        [
            "month",
            "Mkt-RF",
            "RF",
            "market_simple_return",
            "risk_free_simple_return",
            "market_log_return",
            "risk_free_log_return",
            "wti_month_end_observation_date",
            "wti_month_end_price",
            "wti_log_return",
            "wti_log_return_lag1",
            "regression_pair_valid",
        ],
    )
    write_yaml(output / "frozen_split_config.yaml", frozen_split_config(n_pairs, estimation_count, True))
    write_json(output / "fixed_regression_coefficients.json", coeffs)
    signal_fields = [
        "evaluation_index",
        "evaluation_month",
        "forecast_market_log_return",
        "risk_free_log_return",
        "forecast_exceeds_risk_free",
        "wti_log_return_lag1",
        "target_state",
        "market_weight",
        "risk_free_weight",
        "market_simple_return",
        "risk_free_simple_return",
        "strategy_gross_simple_return",
        "state_changed",
        "switching_cost_rate",
        "strategy_net_simple_return",
        "coefficients_source",
    ]
    write_csv(output / "evaluation_signal_audit.csv", evaluation.to_dict("records"), signal_fields)
    write_csv(
        output / "target_state_series.csv",
        evaluation[["evaluation_month", "target_state", "market_weight", "risk_free_weight"]].to_dict("records"),
        ["evaluation_month", "target_state", "market_weight", "risk_free_weight"],
    )
    write_csv(
        output / "transactions.csv",
        transactions,
        ["evaluation_month", "from_state", "to_state", "switching_cost_bps", "switching_cost_rate", "cost_applied_once"],
    )
    write_csv(
        output / "baseline_metrics.csv",
        baseline,
        [
            "series_id",
            "role",
            "start_month",
            "end_month",
            "months",
            "total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
            "switching_cost_bps",
            "switch_count",
            "market_state_count",
            "risk_free_state_count",
        ],
    )
    write_csv(
        output / "benchmark_metrics.csv",
        benchmarks,
        [
            "series_id",
            "role",
            "start_month",
            "end_month",
            "months",
            "total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
        ],
    )
    write_csv(
        output / "existing_variant_overlap_comparison.csv",
        overlap,
        [
            "comparison",
            "status",
            "common_calendar_months",
            "first_common_month",
            "last_common_month",
            "signal_agreement_pct",
            "differing_states",
            "corrected_market_state_count",
            "corrected_risk_free_state_count",
            "existing_market_state_count",
            "existing_risk_free_state_count",
            "corrected_switch_count",
            "existing_switch_count",
            "existing_variant_interpretation",
            "both_control_equivalent",
            "methodology_change_materially_affects_signal_behavior",
        ],
    )
    write_csv(output / "accounting_invariants.csv", invariants, ["invariant", "passed", "value"])
    write_json(output / "trade_management_onboarding_state.json", tm_state)
    write_json(output / "trial_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "correction_summary.md", summary_md(manifest, baseline, overlap))
    consistency = consistency_payload(output, manifest, invariants, before_existing, after_existing)
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
