from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from strategy_lab.research_os.research import fx_carry_external_family_evidence_aqr_currency_carry_v1 as fx


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "external_family_evidence"
    / "cross_sectional_fx_carry"
    / "aqr_currency_carry_v1"
    / "latest"
)


@pytest.fixture(scope="module", autouse=True)
def generated_official_packet() -> dict[str, object]:
    return fx.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def col_name(index: int) -> str:
    name = ""
    n = index
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def make_xlsx(headers: list[str], rows: list[list[object]]) -> bytes:
    strings: list[str] = []
    string_index: dict[str, int] = {}

    def shared(value: str) -> int:
        if value not in string_index:
            string_index[value] = len(strings)
            strings.append(value)
        return string_index[value]

    sheet_rows: list[str] = []
    all_rows = [headers, *rows]
    for row_index, row in enumerate(all_rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{col_name(col_index)}{row_index}"
            if value is None:
                continue
            if isinstance(value, str):
                cells.append(f'<c r="{ref}" t="s"><v>{shared(value)}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{escape(value)}</t></si>" for value in strings)
        + "</sst>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Century of Factor Premia" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def monthly_rows(start_year: int = 2020, start_month: int = 1, count: int = 72, value: float = 0.01) -> list[list[object]]:
    rows: list[list[object]] = []
    year = start_year
    month = start_month
    for _ in range(count):
        rows.append([f"{month:02d}/28/{year}", value])
        month += 1
        if month == 13:
            month = 1
            year += 1
    return rows


def test_wrong_workbook_url_is_rejected() -> None:
    with pytest.raises(fx.SourceValidationError):
        fx.validate_workbook_url("https://www.aqr.com/not-the-authorized-file.xlsx")


def test_missing_currencies_carry_column_is_rejected() -> None:
    payload = make_xlsx(["Date", "Currencies Momentum"], [["01/31/2020", 0.01], ["02/28/2020", 0.02]])
    with pytest.raises(fx.SourceValidationError, match="Required column"):
        fx.extract_currency_carry_series(payload)


def test_duplicate_dates_are_rejected() -> None:
    payload = make_xlsx(["Date", "Currencies Carry"], [["01/31/2020", 0.01], ["01/31/2020", 0.02]])
    series = fx.extract_currency_carry_series(payload)
    with pytest.raises(fx.SourceValidationError, match="duplicate_dates"):
        fx.validate_extracted_series(series)


def test_internal_missing_observations_are_detected() -> None:
    payload = make_xlsx(
        ["Date", "Currencies Carry"],
        [["01/31/2020", 0.01], ["02/28/2020", None], ["03/31/2020", 0.02]],
    )
    series = fx.extract_currency_carry_series(payload)
    assert series.missing_inside_valid_sample == 1
    with pytest.raises(fx.SourceValidationError, match="internal_missing_values"):
        fx.validate_extracted_series(series)


def test_percent_formatted_values_cannot_be_silently_interpreted_as_decimals() -> None:
    payload = make_xlsx(["Date", "Currencies Carry"], [["01/31/2020", 2.5], ["02/28/2020", 3.0]])
    series = fx.extract_currency_carry_series(payload)
    with pytest.raises(fx.SourceValidationError, match="values_not_decimal_monthly_returns"):
        fx.validate_extracted_series(series)


def test_extracted_date_value_sequence_hash_is_deterministic() -> None:
    payload = make_xlsx(["Date", "Currencies Carry"], monthly_rows(count=12, value=0.01))
    first = fx.sequence_hash(fx.extract_currency_carry_series(payload))
    second = fx.sequence_hash(fx.extract_currency_carry_series(payload))
    assert first == second
    assert len(first) == 64


def test_rolling_window_counts_are_correct() -> None:
    points = tuple(
        fx.ReturnPoint(dt=date(2020 + idx // 12, idx % 12 + 1, 28), value=0.01, value_text="0.01")
        for idx in range(72)
    )
    series = fx.ExtractedSeries(("Century of Factor Premia",), fx.EXPECTED_SHEET, fx.EXPECTED_COLUMN, 1, 1, 2, points, 0, 0, 0, 0, (), 72)
    assert len(fx.rolling_windows(list(series.points), 12)) == 61
    assert len(fx.rolling_windows(list(series.points), 36)) == 37
    assert len(fx.rolling_windows(list(series.points), 60)) == 13


def test_complete_year_calculations_exclude_partial_years() -> None:
    points = [
        fx.ReturnPoint(dt=date(2020, month, 28), value=0.01, value_text="0.01")
        for month in range(2, 13)
    ]
    points.extend(
        fx.ReturnPoint(dt=date(2021, month, 28), value=0.01, value_text="0.01")
        for month in range(1, 13)
    )
    points.append(fx.ReturnPoint(dt=date(2022, 1, 28), value=0.01, value_text="0.01"))
    rows = fx.complete_calendar_years(points)
    assert [row["year"] for row in rows] == [2021]


def test_no_transaction_cost_adjustment_or_holdings_reconstruction_is_applied() -> None:
    full = read_json("full_period_diagnostics.json")
    manifest = read_json("external_evidence_manifest.json")
    assert full["transaction_cost_adjustment_applied"] is False
    assert manifest["transaction_cost_adjustment_applied"] is False
    assert manifest["holdings_reconstructed"] is False
    assert manifest["deutsche_bank_strategy_replicated"] is False


def test_no_raw_workbook_or_complete_monthly_series_is_written_to_tracked_evidence() -> None:
    assert not list(EVIDENCE.rglob("*.xlsx"))
    assert not (EVIDENCE / "currencies_carry_series.csv").exists()
    assert not (EVIDENCE / "extracted_monthly_series.csv").exists()
    storage = read_json("data_storage_and_deletion_record.json")
    assert storage["raw_workbook_written_to_persistent_evidence"] is False
    assert storage["complete_monthly_series_written_to_persistent_evidence"] is False
    assert storage["raw_workbook_deleted_after_analysis"] is True


def test_no_registry_strategy_trial_paper_demo_or_broker_state_changes_occur() -> None:
    consistency = read_json("consistency_check.json")
    manifest = read_json("external_evidence_manifest.json")
    assert consistency["no_strategy_trial_or_registry_state_changed"] is True
    assert manifest["project_strategy_trial_added"] is False
    assert manifest["strategy_registry_modified"] is False
    assert manifest["active_observations_modified"] is False
    assert manifest["paper_demo_eligibility_added"] is False
    assert manifest["fx_engine_code_changed"] is False


def test_output_generation_is_deterministic_for_same_source_file(tmp_path: Path) -> None:
    payload = make_xlsx(["Date", "Currencies Carry"], monthly_rows(count=72, value=0.01))
    record = {
        "download_succeeded": True,
        "official_url_used": fx.OFFICIAL_WORKBOOK_URL,
        "intended_temporary_path": str(tmp_path / "source.xlsx"),
        "temporary_path_inside_repository": False,
        "temporary_path_inside_committed_evidence": False,
        "temporary_destination_git_tracked": False,
        "response_content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "file_size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    one = tmp_path / "one"
    two = tmp_path / "two"
    fx.generate_evidence_from_workbook_bytes(payload, record, one, "2026-07-18T00:00:00Z")
    fx.generate_evidence_from_workbook_bytes(payload, record, two, "2026-07-18T00:00:00Z")
    one_hashes = {path.relative_to(one).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in one.rglob("*") if path.is_file()}
    two_hashes = {path.relative_to(two).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in two.rglob("*") if path.is_file()}
    assert one_hashes == two_hashes
