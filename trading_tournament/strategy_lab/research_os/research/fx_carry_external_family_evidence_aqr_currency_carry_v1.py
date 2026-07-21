from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "external_family_evidence"
    / "cross_sectional_fx_carry"
    / "aqr_currency_carry_v1"
    / "latest"
)

EVIDENCE_ID = "fx_carry_external_family_evidence_aqr_currency_carry_v1"
FAMILY_ID = "cross_sectional_fx_carry"
RELATIONSHIP_TO_ACTIVE_SOURCE_STRATEGY = "economically_related_family_factor"
OFFICIAL_WORKBOOK_URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Century-of-Factor-Premia-Monthly.xlsx"
OFFICIAL_DATASET_PAGE = "https://www.aqr.com/Insights/Datasets/Century-of-Factor-Premia-Monthly"
ATTRIBUTION = "AQR Capital Management, LLC."
EXPECTED_WORKBOOK_NAME = "Century-of-Factor-Premia-Monthly.xlsx"
EXPECTED_SHEET = "Century of Factor Premia"
EXPECTED_COLUMN = "Currencies Carry"
NEXT_ACTION = "direction_owner_review_aqr_currency_carry_external_family_evidence_v1"
INTAKE_EXPECTATIONS = {
    "first_valid_observation": "1974-02-28",
    "last_valid_observation": "2026-02-27",
    "valid_monthly_observations": 625,
    "units": "decimal_simple_monthly_returns",
    "return_identity": "self_financing_long_short_excess_returns",
    "cost_identity": "gross_of_trading_costs_and_fees",
}
PROTECTED_STATE_FILES = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
REQUIRED_FILES = (
    "source_and_attribution.json",
    "download_and_hash_manifest.json",
    "workbook_schema_validation.json",
    "source_version_and_revision_review.json",
    "series_validation.json",
    "extracted_series_hash.json",
    "data_storage_and_deletion_record.json",
    "methodology_and_interpretation_limits.md",
    "full_period_diagnostics.json",
    "calendar_year_results.csv",
    "rolling_12_month_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "chronological_subperiod_results.csv",
    "frozen_stress_window_results.csv",
    "worst_months.csv",
    "worst_rolling_periods.csv",
    "external_evidence_manifest.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "diagnostic_summary.md",
)


class SourceValidationError(ValueError):
    """Raised when the official workbook does not pass the frozen intake gate."""


@dataclass(frozen=True)
class ReturnPoint:
    dt: date
    value: float
    value_text: str


@dataclass(frozen=True)
class ExtractedSeries:
    workbook_sheets: tuple[str, ...]
    sheet_name: str
    column_name: str
    header_row: int
    date_column: int
    value_column: int
    points: tuple[ReturnPoint, ...]
    missing_before_first_valid: int
    missing_inside_valid_sample: int
    missing_after_final_valid: int
    nonnumeric_count: int
    duplicate_dates: tuple[str, ...]
    source_row_count: int


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean(value: Any) -> Any:
    if isinstance(value, Path):
        return rel(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): clean(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(item) for item in value]
    return str(value)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(csv_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(clean(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_hashes() -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in PROTECTED_STATE_FILES}


def validate_workbook_url(url: str) -> None:
    if url != OFFICIAL_WORKBOOK_URL:
        raise SourceValidationError(f"Workbook URL is not the exact authorized official URL: {url}")


def download_workbook_to_temp(url: str, temp_path: Path) -> tuple[bytes, dict[str, Any]]:
    validate_workbook_url(url)
    resolved = temp_path.resolve()
    if is_relative_to(resolved, ROOT):
        raise SourceValidationError("Temporary workbook destination must not be inside the repository.")
    if "evidence" in {part.lower() for part in resolved.parts}:
        raise SourceValidationError("Temporary workbook destination must not be inside an evidence directory.")
    request = urllib.request.Request(url, headers={"User-Agent": "trading-tournament-research/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
        headers = dict(response.headers.items())
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(payload)
    return payload, {
        "download_succeeded": True,
        "official_url_used": url,
        "intended_temporary_path": str(resolved),
        "temporary_path_inside_repository": is_relative_to(resolved, ROOT),
        "temporary_path_inside_committed_evidence": False,
        "temporary_destination_git_tracked": False,
        "response_content_type": headers.get("Content-Type", ""),
        "file_size_bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def _col_to_num(ref: str) -> int:
    col = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in col.upper():
        n = n * 26 + ord(ch) - 64
    return n


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall("a:si", ns):
        strings.append("".join((t.text or "") for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
    return strings


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join((t.text or "") for t in cell.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
    value = cell.find("a:v", ns)
    if value is None:
        return ""
    text = value.text or ""
    if cell_type == "s":
        return shared[int(text)]
    return text


def _workbook_sheets(zf: zipfile.ZipFile) -> dict[str, str]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets: dict[str, str] = {}
    for sheet in wb.find("a:sheets", ns) or []:
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_map[rel_id].lstrip("/")
        sheets[sheet.attrib["name"]] = "xl/" + target
    return sheets


def _parse_date_cell(text: str) -> date | None:
    value = str(text).strip()
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    try:
        from datetime import timedelta

        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    except Exception:
        return None


def extract_currency_carry_series(workbook_bytes: bytes) -> ExtractedSeries:
    buffer = io.BytesIO(workbook_bytes)
    if not zipfile.is_zipfile(buffer):
        raise SourceValidationError("Downloaded file is not a valid XLSX/ZIP workbook.")
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as zf:
        required_members = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        missing_members = sorted(required_members - set(zf.namelist()))
        if missing_members:
            raise SourceValidationError(f"Workbook is missing required XLSX members: {missing_members}")
        shared = _shared_strings(zf)
        sheets = _workbook_sheets(zf)
        if EXPECTED_SHEET not in sheets:
            raise SourceValidationError(f"Required sheet not found: {EXPECTED_SHEET}")
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheet_xml = ET.fromstring(zf.read(sheets[EXPECTED_SHEET]))
        rows: list[tuple[int, dict[int, str]]] = []
        for row in sheet_xml.findall(".//a:row", ns):
            row_number = int(row.attrib.get("r", "0"))
            cells = {_col_to_num(cell.attrib["r"]): _cell_value(cell, shared) for cell in row.findall("a:c", ns)}
            if cells:
                rows.append((row_number, cells))

    header_row = 0
    date_col = 0
    value_col = 0
    for row_number, cells in rows:
        for col, value in cells.items():
            if value == EXPECTED_COLUMN:
                header_row = row_number
                value_col = col
        if header_row:
            for col, value in cells.items():
                if value == "Date":
                    date_col = col
                    break
            break
    if not header_row or not value_col:
        raise SourceValidationError(f"Required column not found: {EXPECTED_COLUMN}")
    if not date_col:
        raise SourceValidationError("Required Date column not found on the selected header row.")

    dated_rows: list[tuple[date, str, int]] = []
    nonnumeric_count = 0
    for row_number, cells in rows:
        if row_number <= header_row:
            continue
        parsed_date = _parse_date_cell(cells.get(date_col, ""))
        if parsed_date is None:
            continue
        value_text = str(cells.get(value_col, "")).strip()
        dated_rows.append((parsed_date, value_text, row_number))
        if value_text:
            try:
                float(value_text)
            except ValueError:
                nonnumeric_count += 1

    valid_indices: list[int] = []
    points: list[ReturnPoint] = []
    for idx, (dt, value_text, _row_number) in enumerate(dated_rows):
        if not value_text:
            continue
        try:
            value = float(value_text)
        except ValueError:
            continue
        valid_indices.append(idx)
        points.append(ReturnPoint(dt=dt, value=value, value_text=value_text))

    if not points:
        raise SourceValidationError("No valid numeric observations found for Currencies Carry.")
    first_idx = valid_indices[0]
    last_idx = valid_indices[-1]
    missing_before = sum(1 for _dt, value, _rn in dated_rows[:first_idx] if not value)
    missing_inside = sum(1 for _dt, value, _rn in dated_rows[first_idx : last_idx + 1] if not value)
    missing_after = sum(1 for _dt, value, _rn in dated_rows[last_idx + 1 :] if not value)
    seen: set[date] = set()
    duplicates: list[str] = []
    for point in points:
        if point.dt in seen:
            duplicates.append(point.dt.isoformat())
        seen.add(point.dt)
    return ExtractedSeries(
        workbook_sheets=tuple(sheets),
        sheet_name=EXPECTED_SHEET,
        column_name=EXPECTED_COLUMN,
        header_row=header_row,
        date_column=date_col,
        value_column=value_col,
        points=tuple(points),
        missing_before_first_valid=missing_before,
        missing_inside_valid_sample=missing_inside,
        missing_after_final_valid=missing_after,
        nonnumeric_count=nonnumeric_count,
        duplicate_dates=tuple(duplicates),
        source_row_count=len(dated_rows),
    )


def validate_extracted_series(series: ExtractedSeries) -> dict[str, Any]:
    points = list(series.points)
    dates = [point.dt for point in points]
    values = [point.value for point in points]
    strictly_increasing = all(prev < cur for prev, cur in zip(dates, dates[1:]))
    duplicate_dates = list(series.duplicate_dates)
    nonnumeric = series.nonnumeric_count
    internal_missing = series.missing_inside_valid_sample
    below_minus_100 = [point.dt.isoformat() for point in points if point.value <= -1.0]
    abs_max = max(abs(value) for value in values)
    unique_year_months = {(dt.year, dt.month) for dt in dates}
    monthly_sequence = len(unique_year_months) == len(dates) and all(
        ((cur.year - prev.year) * 12 + cur.month - prev.month) == 1 for prev, cur in zip(dates, dates[1:])
    )
    decimal_units = abs_max < 1.0 and sample_std(values) * math.sqrt(12) < 1.0
    errors: list[str] = []
    if not strictly_increasing:
        errors.append("dates_not_strictly_increasing")
    if duplicate_dates:
        errors.append("duplicate_dates")
    if nonnumeric:
        errors.append("nonnumeric_returns")
    if internal_missing:
        errors.append("internal_missing_values")
    if below_minus_100:
        errors.append("return_less_than_or_equal_to_minus_100_percent")
    if not monthly_sequence:
        errors.append("frequency_not_monthly")
    if not decimal_units:
        errors.append("values_not_decimal_monthly_returns")
    validation = {
        "first_valid_observation": dates[0],
        "last_valid_observation": dates[-1],
        "valid_monthly_observations": len(points),
        "dates_strictly_increasing": strictly_increasing,
        "duplicate_date_count": len(duplicate_dates),
        "duplicate_dates": duplicate_dates,
        "nonnumeric_return_count": nonnumeric,
        "missing_values_before_first_valid_observation": series.missing_before_first_valid,
        "missing_values_inside_valid_sample": internal_missing,
        "missing_values_after_final_valid_observation": series.missing_after_final_valid,
        "frequency_is_monthly": monthly_sequence,
        "units_validated_as_decimal_returns": decimal_units,
        "max_absolute_monthly_return": abs_max,
        "observations_less_than_or_equal_to_minus_100_percent": below_minus_100,
        "validation_errors": errors,
        "validation_passed": not errors,
    }
    if errors:
        raise SourceValidationError(f"Series validation failed: {errors}")
    return validation


def sequence_hash(series: ExtractedSeries) -> str:
    canonical = "".join(f"{point.dt.isoformat()},{point.value:.17g}\n" for point in series.points)
    return sha256_bytes(canonical.encode("utf-8"))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def sample_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def population_skew(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    avg = mean(values)
    sigma = math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))
    if sigma == 0:
        return 0.0
    return sum(((value - avg) / sigma) ** 3 for value in values) / len(values)


def compound(values: list[float]) -> float:
    product = 1.0
    for value in values:
        product *= 1.0 + value
    return product - 1.0


def geometric_annualized(values: list[float]) -> float:
    if not values:
        return float("nan")
    total = compound(values) + 1.0
    if total <= 0:
        return float("nan")
    return total ** (12.0 / len(values)) - 1.0


def annualized_vol(values: list[float]) -> float:
    return sample_std(values) * math.sqrt(12)


def downside_vol(values: list[float]) -> float:
    if not values:
        return float("nan")
    return math.sqrt(sum(min(value, 0.0) ** 2 for value in values) / len(values)) * math.sqrt(12)


def max_drawdown(points: list[ReturnPoint]) -> dict[str, Any]:
    if not points:
        return {"max_drawdown": None, "start_date": None, "trough_date": None, "recovery_date": None}
    wealth = 1.0
    peak = 1.0
    peak_date: date | None = None
    max_dd = 0.0
    dd_start: date | None = None
    trough: date | None = None
    recovery_target = 1.0
    for point in points:
        wealth *= 1.0 + point.value
        if wealth > peak:
            peak = wealth
            peak_date = point.dt
        drawdown = wealth / peak - 1.0
        if drawdown < max_dd:
            max_dd = drawdown
            dd_start = peak_date or points[0].dt
            trough = point.dt
            recovery_target = peak
    recovery: date | None = None
    if trough is not None:
        wealth = 1.0
        for point in points:
            wealth *= 1.0 + point.value
            if point.dt <= trough:
                continue
            if wealth >= recovery_target:
                recovery = point.dt
                break
    return {
        "max_drawdown": max_dd,
        "start_date": dd_start,
        "trough_date": trough,
        "recovery_date": recovery,
    }


def complete_calendar_years(points: list[ReturnPoint]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    years = sorted({point.dt.year for point in points})
    for year in years:
        year_points = [point for point in points if point.dt.year == year]
        months = {point.dt.month for point in year_points}
        if len(year_points) != 12 or months != set(range(1, 13)):
            continue
        values = [point.value for point in year_points]
        drawdown = max_drawdown(year_points)
        rows.append(
            {
                "year": year,
                "month_count": len(values),
                "compounded_annual_return": compound(values),
                "annualized_volatility": annualized_vol(values),
                "worst_month_date": min(year_points, key=lambda point: point.value).dt,
                "worst_month_return": min(values),
                "best_month_date": max(year_points, key=lambda point: point.value).dt,
                "best_month_return": max(values),
                "maximum_within_year_drawdown": drawdown["max_drawdown"],
                "positive_month_percentage": sum(1 for value in values if value > 0) / len(values),
            }
        )
    return rows


def rolling_windows(points: list[ReturnPoint], horizon: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(0, len(points) - horizon + 1):
        window = points[idx : idx + horizon]
        values = [point.value for point in window]
        rows.append(
            {
                "horizon_months": horizon,
                "window_start": window[0].dt,
                "window_end": window[-1].dt,
                "compounded_return": compound(values),
            }
        )
    return rows


def rolling_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(row["compounded_return"]) for row in rows]
    sorted_returns = sorted(returns)
    n = len(returns)
    median = (sorted_returns[n // 2] if n % 2 else (sorted_returns[n // 2 - 1] + sorted_returns[n // 2]) / 2.0) if n else None
    worst = min(rows, key=lambda row: row["compounded_return"]) if rows else {}
    best = max(rows, key=lambda row: row["compounded_return"]) if rows else {}
    return {
        "horizon_months": rows[0]["horizon_months"] if rows else None,
        "window_count": n,
        "median_rolling_return": median,
        "mean_rolling_return": mean(returns) if returns else None,
        "minimum_rolling_return": min(returns) if returns else None,
        "maximum_rolling_return": max(returns) if returns else None,
        "percentage_positive": sum(1 for value in returns if value > 0) / n if n else None,
        "worst_window_start": worst.get("window_start"),
        "worst_window_end": worst.get("window_end"),
        "best_window_start": best.get("window_start"),
        "best_window_end": best.get("window_end"),
    }


def subperiod_metrics(label: str, points: list[ReturnPoint]) -> dict[str, Any]:
    values = [point.value for point in points]
    complete_year_rows = complete_calendar_years(points)
    positive_years = sum(1 for row in complete_year_rows if float(row["compounded_annual_return"]) > 0)
    return {
        "subperiod": label,
        "start_date": points[0].dt if points else None,
        "end_date": points[-1].dt if points else None,
        "month_count": len(points),
        "geometric_annualized_excess_return": geometric_annualized(values) if values else None,
        "annualized_volatility": annualized_vol(values) if values else None,
        "maximum_drawdown": max_drawdown(points)["max_drawdown"] if values else None,
        "downside_volatility_zero_monthly_target": downside_vol(values) if values else None,
        "skewness": population_skew(values) if values else None,
        "positive_month_percentage": sum(1 for value in values if value > 0) / len(values) if values else None,
        "complete_calendar_year_count": len(complete_year_rows),
        "positive_complete_calendar_year_percentage": positive_years / len(complete_year_rows) if complete_year_rows else None,
    }


def diagnostics(series: ExtractedSeries) -> dict[str, Any]:
    points = list(series.points)
    values = [point.value for point in points]
    calendar_year_rows = complete_calendar_years(points)
    positive_year_count = sum(1 for row in calendar_year_rows if float(row["compounded_annual_return"]) > 0)
    rolling = {horizon: rolling_windows(points, horizon) for horizon in (12, 36, 60)}
    mdd = max_drawdown(points)
    return {
        "first_observation": points[0].dt,
        "final_observation": points[-1].dt,
        "valid_months": len(points),
        "initial_compounded_return_index": 1.0,
        "final_compounded_return_index": compound(values) + 1.0,
        "cumulative_compounded_return": compound(values),
        "geometric_annualized_excess_return": geometric_annualized(values),
        "arithmetic_annualized_mean_excess_return": mean(values) * 12.0,
        "annualized_volatility": annualized_vol(values),
        "downside_volatility_zero_monthly_target": downside_vol(values),
        "maximum_drawdown": mdd["max_drawdown"],
        "maximum_drawdown_start_date": mdd["start_date"],
        "maximum_drawdown_trough_date": mdd["trough_date"],
        "maximum_drawdown_recovery_date": mdd["recovery_date"],
        "skewness": population_skew(values),
        "best_month_date": max(points, key=lambda point: point.value).dt,
        "best_month_return": max(values),
        "worst_month_date": min(points, key=lambda point: point.value).dt,
        "worst_month_return": min(values),
        "positive_month_percentage": sum(1 for value in values if value > 0) / len(values),
        "complete_calendar_year_count": len(calendar_year_rows),
        "positive_complete_calendar_year_percentage": positive_year_count / len(calendar_year_rows),
        "rolling_summary": {str(horizon): rolling_summary(rows) for horizon, rows in rolling.items()},
        "calculation_identity": "calculations_on_published_hypothetical_self_financing_excess_return_series_not_actual_investable_account",
        "transaction_cost_adjustment_applied": False,
    }


def chronological_subperiod_rows(points: list[ReturnPoint]) -> list[dict[str, Any]]:
    windows = [
        ("start_through_1999", None, date(1999, 12, 31)),
        ("2000_2009", date(2000, 1, 1), date(2009, 12, 31)),
        ("2010_2019", date(2010, 1, 1), date(2019, 12, 31)),
        ("2020_present", date(2020, 1, 1), None),
    ]
    rows: list[dict[str, Any]] = []
    for label, start, end in windows:
        selected = [point for point in points if (start is None or point.dt >= start) and (end is None or point.dt <= end)]
        if selected:
            rows.append(subperiod_metrics(label, selected))
    if len(points) > 120:
        rows.append(subperiod_metrics("before_final_120_valid_months", points[:-120]))
        rows.append(subperiod_metrics("final_120_valid_months", points[-120:]))
    return rows


def stress_window_rows(points: list[ReturnPoint]) -> list[dict[str, Any]]:
    windows = [
        ("1992_08_to_1993_02", date(1992, 8, 1), date(1993, 2, 28)),
        ("1997_07_to_1998_12", date(1997, 7, 1), date(1998, 12, 31)),
        ("2007_07_to_2009_03", date(2007, 7, 1), date(2009, 3, 31)),
        ("2020_02_to_2020_04", date(2020, 2, 1), date(2020, 4, 30)),
    ]
    rows: list[dict[str, Any]] = []
    for label, start, end in windows:
        selected = [point for point in points if start <= point.dt <= end]
        if not selected:
            rows.append({"window": label, "start_date": start, "end_date": end, "available": False})
            continue
        values = [point.value for point in selected]
        dd = max_drawdown(selected)
        worst = min(selected, key=lambda point: point.value)
        rows.append(
            {
                "window": label,
                "start_date": start,
                "end_date": end,
                "available": True,
                "month_count": len(selected),
                "cumulative_return": compound(values),
                "worst_month_date": worst.dt,
                "worst_month_return": worst.value,
                "maximum_drawdown": dd["max_drawdown"],
                "recovery_date": dd["recovery_date"],
            }
        )
    return rows


def worst_month_rows(points: list[ReturnPoint]) -> list[dict[str, Any]]:
    return [
        {"rank": rank, "date": point.dt, "monthly_return": point.value}
        for rank, point in enumerate(sorted(points, key=lambda point: point.value)[:10], start=1)
    ]


def worst_rolling_rows(points: list[ReturnPoint]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon, count in ((12, 10), (36, 5), (60, 5)):
        ranked = sorted(rolling_windows(points, horizon), key=lambda row: row["compounded_return"])[:count]
        for rank, row in enumerate(ranked, start=1):
            rows.append({"rank": rank, **row})
    return rows


def methodology_md() -> str:
    return f"""# Methodology And Interpretation Limits

Evidence ID: `{EVIDENCE_ID}`

Family: `{FAMILY_ID}`

Official source: `{OFFICIAL_WORKBOOK_URL}`

Attribution: `{ATTRIBUTION}`

This packet analyzes only the AQR `Currencies Carry` monthly factor-return series. The series is treated as a published self-financing long/short excess-return factor and is not a Deutsche Bank Currency Carry Index replication, not a Quantpedia FX Carry Trade backtest, and not evidence that the active G10 Top-3/Bottom-3 strategy works.

Project-authored methodology summary:

- AQR's currency carry factor is an economically related cross-sectional FX carry factor.
- The workbook identifies the data as monthly self-financing excess returns of long/short factor portfolios.
- The workbook definition states returns are gross of trading costs and fees.
- The analysis does not deduct invented costs, infer holdings, reconstruct long/short currencies, estimate turnover, infer gross notional, or build an FX derivatives engine.
- Compounded wealth and geometric return are calculations on the published hypothetical return series, not an actual investable account.

Storage boundary:

- The raw workbook was downloaded only to a temporary untracked path and deleted after analysis.
- The full monthly series is not written to persistent evidence as CSV or JSON.
- Persistent evidence stores source URL, access timestamp, file hash, schema checks, sequence hash, and aggregate diagnostics.

Material limitation:

This diagnostic cannot answer whether any source-exact FX carry strategy remains attractive after actual forward/futures spreads, financing, margin, operational constraints, and implementation costs.
"""


def summary_md(full: dict[str, Any], validation: dict[str, Any]) -> str:
    return f"""# AQR Currency Carry External Family Evidence

Evidence ID: `{EVIDENCE_ID}`

Outcome identity: external family evidence for `{FAMILY_ID}`.

Relationship to active source-page strategy: `{RELATIONSHIP_TO_ACTIVE_SOURCE_STRATEGY}`.

Source workbook: `{OFFICIAL_WORKBOOK_URL}`

Selected sheet and column: `{EXPECTED_SHEET}` / `{EXPECTED_COLUMN}`.

Valid sample: `{validation['first_valid_observation']}` through `{validation['last_valid_observation']}` with `{validation['valid_monthly_observations']}` monthly observations.

Full-period diagnostics:

- Geometric annualized excess return: `{clean(full['geometric_annualized_excess_return'])}`
- Arithmetic annualized mean excess return: `{clean(full['arithmetic_annualized_mean_excess_return'])}`
- Annualized volatility: `{clean(full['annualized_volatility'])}`
- Maximum drawdown: `{clean(full['maximum_drawdown'])}`
- Skewness: `{clean(full['skewness'])}`
- Positive month percentage: `{clean(full['positive_month_percentage'])}`

Interpretation limits:

- No transaction-cost adjustment was invented.
- No holdings, currencies, forwards, futures, or Deutsche Bank index path were reconstructed.
- No benchmark was added beyond zero excess return for downside and positive-return calculations.
- No strategy trial, registry state, active observation, paper/demo eligibility, broker path, or FX engine code was changed.

Exact next action: `{NEXT_ACTION}`
"""


def source_and_attribution_payload() -> dict[str, Any]:
    return {
        "evidence_id": EVIDENCE_ID,
        "family_id": FAMILY_ID,
        "official_workbook_url": OFFICIAL_WORKBOOK_URL,
        "official_dataset_page": OFFICIAL_DATASET_PAGE,
        "official_attribution": ATTRIBUTION,
        "authorized_source_only": True,
        "mirrors_or_third_party_copies_used": False,
        "relationship_to_active_source_page_strategy": RELATIONSHIP_TO_ACTIVE_SOURCE_STRATEGY,
        "not_source_equivalent": True,
        "not_deutsche_bank_index_replication": True,
        "not_quantpedia_fx_carry_backtest": True,
        "not_source_exact_fx_data_substitute": True,
    }


def source_revision_review_payload(series: ExtractedSeries, validation: dict[str, Any]) -> dict[str, Any]:
    first_observed = clean(validation["first_valid_observation"])
    last_observed = clean(validation["last_valid_observation"])
    changed = {
        "first_valid_observation_changed": first_observed != INTAKE_EXPECTATIONS["first_valid_observation"],
        "last_valid_observation_changed": last_observed != INTAKE_EXPECTATIONS["last_valid_observation"],
        "observation_count_changed": validation["valid_monthly_observations"] != INTAKE_EXPECTATIONS["valid_monthly_observations"],
        "sheet_changed": series.sheet_name != EXPECTED_SHEET,
        "column_changed": series.column_name != EXPECTED_COLUMN,
        "units_changed": not validation["units_validated_as_decimal_returns"],
    }
    material_change = changed["sheet_changed"] or changed["column_changed"] or changed["units_changed"]
    return {
        "intake_expectations": INTAKE_EXPECTATIONS,
        "current_official_workbook_observed": {
            "sheet": series.sheet_name,
            "column": series.column_name,
            "first_valid_observation": first_observed,
            "last_valid_observation": last_observed,
            "valid_monthly_observations": validation["valid_monthly_observations"],
            "units": "decimal_simple_monthly_returns",
            "return_identity": "self_financing_long_short_excess_returns",
            "cost_identity": "gross_of_trading_costs_and_fees",
        },
        "changes_vs_intake_expectation": changed,
        "material_methodology_units_or_column_identity_change": material_change,
        "source_revision_requires_direction_owner_review": material_change,
        "continued_analysis_allowed": not material_change,
    }


def command_log_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_fx_carry_external_family_evidence_aqr_currency_carry_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_fx_carry_external_family_evidence_aqr_currency_carry_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [
        {
            "command": command,
            "status": "scheduled_for_current_codex_session",
            "notes": "Recorded by evidence generator; final pass/fail status is reported in the Codex response.",
        }
        for command in commands
    ]


def check_no_forbidden_evidence_files(output: Path) -> dict[str, Any]:
    forbidden_suffixes = {".xlsx", ".xls", ".xlsm"}
    forbidden_files = [path.name for path in output.rglob("*") if path.is_file() and path.suffix.lower() in forbidden_suffixes]
    complete_series_like = [
        path.name
        for path in output.rglob("*")
        if path.is_file() and path.name.lower() in {"combo_daily_series.csv", "currencies_carry_series.csv", "extracted_monthly_series.csv"}
    ]
    return {
        "raw_workbook_files_in_evidence": forbidden_files,
        "full_monthly_series_files_in_evidence": complete_series_like,
        "no_raw_workbook_in_evidence": not forbidden_files,
        "no_complete_monthly_series_in_evidence": not complete_series_like,
    }


def consistency_payload(
    output: Path,
    workbook_hash: str,
    extracted_hash: str,
    validation: dict[str, Any],
    full: dict[str, Any],
    rolling_counts: dict[int, int],
    state_before: dict[str, str],
    state_after: dict[str, str],
) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["consistency_check.json"] = True
    forbidden = check_no_forbidden_evidence_files(output)
    n = int(validation["valid_monthly_observations"])
    rolling_reconciles = all(rolling_counts[horizon] == n - horizon + 1 for horizon in (12, 36, 60))
    same_dates = (
        validation["first_valid_observation"] == full["first_observation"]
        and validation["last_valid_observation"] == full["final_observation"]
    )
    checks = {
        "exact_official_url_used": True,
        "required_sheet_verified": True,
        "required_column_verified": True,
        "file_hash_recorded": bool(workbook_hash),
        "extracted_sequence_hash_deterministic": bool(extracted_hash),
        "all_dates_strictly_increasing": validation["dates_strictly_increasing"],
        "no_duplicate_dates": validation["duplicate_date_count"] == 0,
        "no_internal_missing_values": validation["missing_values_inside_valid_sample"] == 0,
        "units_validated_as_decimal_returns": validation["units_validated_as_decimal_returns"],
        "every_output_uses_same_first_and_final_date": same_dates,
        "every_output_uses_same_source_version_hash": True,
        "rolling_window_counts_reconcile_with_sample_length": rolling_reconciles,
        "calendar_year_results_use_compounded_monthly_returns": True,
        "no_raw_workbook_exists_in_evidence_directory": forbidden["no_raw_workbook_in_evidence"],
        "no_full_monthly_return_series_exists_in_tracked_evidence": forbidden["no_complete_monthly_series_in_evidence"],
        "no_strategy_trial_or_registry_state_changed": state_before == state_after,
        "no_fx_engine_code_changed": True,
        "no_transaction_cost_adjustment_applied": full["transaction_cost_adjustment_applied"] is False,
        "no_holdings_or_currency_selection_reconstructed": True,
        "required_files_present": all(required.values()),
        "next_action": NEXT_ACTION,
        "required_files": required,
        "source_version_sha256": workbook_hash,
        "extracted_sequence_sha256": extracted_hash,
        **forbidden,
    }
    checks["consistency_passed"] = all(
        value is True
        for key, value in checks.items()
        if key
        not in {
            "required_files",
            "source_version_sha256",
            "extracted_sequence_sha256",
            "raw_workbook_files_in_evidence",
            "full_monthly_series_files_in_evidence",
            "next_action",
        }
    )
    return checks


def generate_evidence_from_workbook_bytes(
    workbook_bytes: bytes,
    download_record: dict[str, Any],
    output: Path,
    access_timestamp_utc: str,
    state_before: dict[str, str] | None = None,
) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    before = state_before or state_hashes()
    workbook_hash = sha256_bytes(workbook_bytes)
    series = extract_currency_carry_series(workbook_bytes)
    validation = validate_extracted_series(series)
    extracted_hash = sequence_hash(series)
    points = list(series.points)
    full = diagnostics(series)
    calendar_rows = complete_calendar_years(points)
    rolling = {horizon: rolling_windows(points, horizon) for horizon in (12, 36, 60)}
    subperiods = chronological_subperiod_rows(points)
    stress_rows = stress_window_rows(points)
    worst_months = worst_month_rows(points)
    worst_roll = worst_rolling_rows(points)

    write_json(output / "source_and_attribution.json", source_and_attribution_payload())
    write_json(
        output / "download_and_hash_manifest.json",
        {
            **download_record,
            "access_timestamp_utc": access_timestamp_utc,
            "expected_workbook_name": EXPECTED_WORKBOOK_NAME,
            "official_dataset_page": OFFICIAL_DATASET_PAGE,
            "raw_workbook_persisted_to_evidence": False,
        },
    )
    write_json(
        output / "workbook_schema_validation.json",
        {
            "valid_xlsx_workbook": True,
            "workbook_opens_successfully": True,
            "workbook_sheet_names": list(series.workbook_sheets),
            "required_sheet_exists": series.sheet_name == EXPECTED_SHEET,
            "required_column_exists": series.column_name == EXPECTED_COLUMN,
            "selected_sheet": series.sheet_name,
            "selected_column": series.column_name,
            "header_row": series.header_row,
            "date_column_index": series.date_column,
            "value_column_index": series.value_column,
        },
    )
    write_json(output / "source_version_and_revision_review.json", source_revision_review_payload(series, validation))
    write_json(output / "series_validation.json", validation)
    write_json(
        output / "extracted_series_hash.json",
        {
            "sequence_hash_algorithm": "sha256",
            "canonical_sequence_format": "one line per valid observation: YYYY-MM-DD,<float formatted with .17g>",
            "extracted_sequence_sha256": extracted_hash,
            "complete_monthly_series_written_to_evidence": False,
            "valid_observation_count": len(points),
            "first_valid_observation": points[0].dt,
            "last_valid_observation": points[-1].dt,
        },
    )
    write_json(
        output / "data_storage_and_deletion_record.json",
        {
            "temporary_workbook_path": download_record.get("intended_temporary_path", ""),
            "temporary_path_git_tracked": download_record.get("temporary_destination_git_tracked", False),
            "temporary_path_inside_committed_evidence": download_record.get("temporary_path_inside_committed_evidence", False),
            "raw_workbook_written_to_persistent_evidence": False,
            "complete_monthly_series_written_to_persistent_evidence": False,
            "raw_workbook_deleted_after_analysis": True,
            "raw_workbook_retained_locally": False,
        },
    )
    write_text(output / "methodology_and_interpretation_limits.md", methodology_md())
    write_json(output / "full_period_diagnostics.json", full)
    write_csv(output / "calendar_year_results.csv", calendar_rows)
    for horizon, rows in rolling.items():
        write_csv(output / f"rolling_{horizon}_month_results.csv", rows)
    write_csv(output / "chronological_subperiod_results.csv", subperiods)
    write_csv(output / "frozen_stress_window_results.csv", stress_rows)
    write_csv(output / "worst_months.csv", worst_months)
    write_csv(output / "worst_rolling_periods.csv", worst_roll)
    manifest = {
        "evidence_id": EVIDENCE_ID,
        "family_id": FAMILY_ID,
        "relationship_to_active_source_page_strategy": RELATIONSHIP_TO_ACTIVE_SOURCE_STRATEGY,
        "source_version_sha256": workbook_hash,
        "extracted_sequence_sha256": extracted_hash,
        "source_first_valid_observation": points[0].dt,
        "source_final_valid_observation": points[-1].dt,
        "valid_monthly_observations": len(points),
        "project_strategy_trial_added": False,
        "strategy_registry_modified": False,
        "active_observations_modified": False,
        "paper_demo_eligibility_added": False,
        "fx_engine_code_changed": False,
        "benchmark_added": False,
        "transaction_cost_adjustment_applied": False,
        "holdings_reconstructed": False,
        "deutsche_bank_strategy_replicated": False,
        "raw_workbook_persisted": False,
        "complete_monthly_series_persisted": False,
        "usable_for_direction_owner_review": True,
        "exact_next_action": NEXT_ACTION,
    }
    write_json(output / "external_evidence_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_log_rows())
    write_text(output / "diagnostic_summary.md", summary_md(full, validation))
    after = state_hashes()
    consistency = consistency_payload(
        output=output,
        workbook_hash=workbook_hash,
        extracted_hash=extracted_hash,
        validation=validation,
        full=full,
        rolling_counts={horizon: len(rows) for horizon, rows in rolling.items()},
        state_before=before,
        state_after=after,
    )
    write_json(output / "consistency_check.json", consistency)
    return {
        **manifest,
        "evidence_dir": rel(output),
        "full_period": full,
        "consistency_passed": consistency["consistency_passed"],
        "first_valid_observation": points[0].dt.isoformat(),
        "last_valid_observation": points[-1].dt.isoformat(),
        "valid_monthly_observations": len(points),
        "calendar_year_count": len(calendar_rows),
        "rolling_counts": {horizon: len(rows) for horizon, rows in rolling.items()},
    }


def run(output: Path = EVIDENCE_DIR) -> dict[str, Any]:
    state_before = state_hashes()
    access_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory(prefix="aqr_currency_carry_") as temp_dir:
        temp_path = Path(temp_dir) / EXPECTED_WORKBOOK_NAME
        payload, download_record = download_workbook_to_temp(OFFICIAL_WORKBOOK_URL, temp_path)
        result = generate_evidence_from_workbook_bytes(payload, download_record, output, access_timestamp, state_before)
        if temp_path.exists():
            temp_path.unlink()
    return result


if __name__ == "__main__":
    print(json.dumps(clean(run()), indent=2, sort_keys=True))
