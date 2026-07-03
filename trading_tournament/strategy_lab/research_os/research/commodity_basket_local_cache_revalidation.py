from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


FAMILY_ID = "commodity_basket_etf_momentum_v1"
LANE_ID = "commodity_basket_etf_momentum_bounded_lane_v1"
STEP_ID = "restore_or_revalidate_local_commodity_cache_before_bounded_run"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "commodity_basket_local_cache_revalidation" / "latest"

DESIGN_DIR = Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_design" / "latest"
COMMODITY_EXPLORATORY_DIR = Path("evidence") / "commodity_exploratory" / "latest"
COMMODITY_DIAGNOSTICS_DIR = (
    Path("evidence") / "commodity_lab" / "risk_control_batch1_diagnostics_completion" / "latest"
)
COMMODITY_ACQUISITION_DIR = Path("evidence") / "data_acquisition_runs" / "commodity_basket_fast_exploratory" / "latest"
COMMODITY_ACQUISITION_ZIP = (
    Path("evidence") / "data_acquisition_runs" / "commodity_basket_fast_exploratory" / "latest_fast_commodity_acquisition_packet.zip"
)
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
SYMBOL_MAP = Path("strategy_lab") / "approved_etf_symbol_map.yaml"

REQUIRED_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD")
COMMODITY_WRAPPERS = ("DBC", "PDBC", "COMT", "GSG", "USCI")
RAW_PRICE_COLUMNS = {"date", "open", "high", "low", "close", "adj_close", "volume"}

RUN_READY = "commodity_basket_cache_ready_for_bounded_run"
RUN_BLOCKED = "commodity_basket_cache_still_blocked"
NEXT_ACTION_READY = "run_commodity_basket_etf_momentum_bounded_lane"
NEXT_ACTION_BLOCKED = "provide_existing_raw_commodity_cache_files_or_authorize_provider_refresh"
VALID_NEXT_ACTIONS = {NEXT_ACTION_READY, NEXT_ACTION_BLOCKED}

AVAILABILITY_FIELDS = (
    "symbol",
    "required_for_lane",
    "current_cache_path",
    "current_cache_exists",
    "current_cache_is_raw_price_history",
    "row_count",
    "first_date",
    "last_date",
    "sha256",
    "historical_manifest_rows_written",
    "historical_manifest_sha256",
    "safe_to_restore_from_existing_artifact",
    "status",
    "notes",
)

LOCATION_FIELDS = (
    "location",
    "exists",
    "artifact_type",
    "raw_price_history_found",
    "summary_only",
    "notes",
)

RESTORE_FIELDS = (
    "symbol",
    "action",
    "source_path",
    "target_path",
    "status",
    "notes",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_lines(root: Path, args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode not in {0, 1}:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def raw_csv_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "is_raw_price_history": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "sha256": "",
        }
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            is_raw = RAW_PRICE_COLUMNS.issubset(fields)
            row_count = 0
            first_date = ""
            last_date = ""
            for row in reader:
                row_count += 1
                date = row.get("date", "")
                if row_count == 1:
                    first_date = date
                last_date = date
    except (OSError, UnicodeDecodeError, csv.Error):
        return {
            "exists": True,
            "is_raw_price_history": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "sha256": file_sha256(path),
        }
    return {
        "exists": True,
        "is_raw_price_history": is_raw,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "sha256": file_sha256(path),
    }


def acquisition_manifest_by_symbol(root: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(root / COMMODITY_ACQUISITION_DIR / "cache_write_manifest.csv")
    return {row.get("symbol", ""): row for row in rows}


def availability_rows(root: Path) -> list[dict[str, Any]]:
    historical = acquisition_manifest_by_symbol(root)
    rows = []
    for symbol in REQUIRED_SYMBOLS:
        path = root / DATA_CACHE_DIR / f"{symbol}.csv"
        meta = raw_csv_metadata(path)
        hist = historical.get(symbol, {})
        current_ok = meta["exists"] and meta["is_raw_price_history"] and meta["row_count"] > 200
        rows.append(
            {
                "symbol": symbol,
                "required_for_lane": True,
                "current_cache_path": str(path),
                "current_cache_exists": meta["exists"],
                "current_cache_is_raw_price_history": meta["is_raw_price_history"],
                "row_count": meta["row_count"],
                "first_date": meta["first_date"],
                "last_date": meta["last_date"],
                "sha256": meta["sha256"],
                "historical_manifest_rows_written": hist.get("rows_written", ""),
                "historical_manifest_sha256": hist.get("sha256", ""),
                "safe_to_restore_from_existing_artifact": False,
                "status": "available_raw_price_history" if current_ok else "missing_current_raw_price_history",
                "notes": "present in current canonical cache"
                if current_ok
                else "no current raw price CSV found in canonical cache; historical manifest is metadata only",
            }
        )
    return rows


def zip_members(root: Path) -> list[str]:
    path = root / COMMODITY_ACQUISITION_ZIP
    if not path.exists():
        return []
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except zipfile.BadZipFile:
        return []


def locations_inspected(root: Path) -> list[dict[str, Any]]:
    members = zip_members(root)
    location_rows = [
        {
            "location": str((root / DATA_CACHE_DIR).resolve()),
            "exists": (root / DATA_CACHE_DIR).exists(),
            "artifact_type": "canonical_current_cache",
            "raw_price_history_found": any((root / DATA_CACHE_DIR / f"{symbol}.csv").exists() for symbol in COMMODITY_WRAPPERS),
            "summary_only": False,
            "notes": "canonical cache used by sandbox/research code via DATA_CACHE_DIR",
        },
        {
            "location": str((root / COMMODITY_ACQUISITION_DIR).resolve()),
            "exists": (root / COMMODITY_ACQUISITION_DIR).exists(),
            "artifact_type": "prior_acquisition_evidence",
            "raw_price_history_found": False,
            "summary_only": True,
            "notes": "contains manifests, row counts, hashes, and QA summaries; raw_ohlcv_in_evidence=false",
        },
        {
            "location": str((root / COMMODITY_ACQUISITION_ZIP).resolve()),
            "exists": (root / COMMODITY_ACQUISITION_ZIP).exists(),
            "artifact_type": "prior_acquisition_zip_packet",
            "raw_price_history_found": any(member.upper().endswith(tuple(f"{symbol}.CSV" for symbol in COMMODITY_WRAPPERS)) for member in members),
            "summary_only": True,
            "notes": "zip members: " + "|".join(members) if members else "zip missing or unreadable",
        },
        {
            "location": str((root / COMMODITY_EXPLORATORY_DIR).resolve()),
            "exists": (root / COMMODITY_EXPLORATORY_DIR).exists(),
            "artifact_type": "exploratory_results_evidence",
            "raw_price_history_found": False,
            "summary_only": True,
            "notes": "contains result, risk, status, ranking, and summary artifacts only",
        },
        {
            "location": str((root / COMMODITY_DIAGNOSTICS_DIR).resolve()),
            "exists": (root / COMMODITY_DIAGNOSTICS_DIR).exists(),
            "artifact_type": "risk_control_diagnostics_evidence",
            "raw_price_history_found": False,
            "summary_only": True,
            "notes": "contains diagnostics and contribution summaries only",
        },
        {
            "location": str((root / SYMBOL_MAP).resolve()),
            "exists": (root / SYMBOL_MAP).exists(),
            "artifact_type": "symbol_policy_metadata",
            "raw_price_history_found": False,
            "summary_only": True,
            "notes": "policy metadata only; DBC is benchmark-only/disabled-by-default in approved ETF map",
        },
    ]
    return location_rows


def restored_rows(root: Path, availability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in availability:
        if row["symbol"] in COMMODITY_WRAPPERS:
            rows.append(
                {
                    "symbol": row["symbol"],
                    "action": "none",
                    "source_path": "",
                    "target_path": row["current_cache_path"],
                    "status": "not_restored_no_existing_raw_price_artifact",
                    "notes": "metadata/hash/summary evidence is insufficient to reconstruct raw price history",
                }
            )
    return rows


def readiness(availability: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    missing = [
        row["symbol"]
        for row in availability
        if row["symbol"] in REQUIRED_SYMBOLS and row["status"] != "available_raw_price_history"
    ]
    if missing:
        return RUN_BLOCKED, NEXT_ACTION_BLOCKED, missing
    return RUN_READY, NEXT_ACTION_READY, []


def build_manifest(
    root: Path,
    created: str,
    output: Path,
    availability: list[dict[str, Any]],
    location_rows: list[dict[str, Any]],
    restored: list[dict[str, Any]],
) -> dict[str, Any]:
    decision, next_action, missing = readiness(availability)
    expected_queue_action = NEXT_ACTION_READY if decision == RUN_READY else NEXT_ACTION_BLOCKED
    tracked = git_lines(root, ["ls-files", *[f"data/cache/{symbol}.csv" for symbol in COMMODITY_WRAPPERS]])
    history = git_lines(
        root,
        [
            "log",
            "--all",
            "--name-only",
            "--pretty=format:",
            "--",
            *[f"data/cache/{symbol}.csv" for symbol in COMMODITY_WRAPPERS],
        ],
    )
    queue_text = read_text(root / QUEUE)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "commodity_cache_revalidation_only": True,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "step_id": STEP_ID,
        "canonical_cache_root": str((root / DATA_CACHE_DIR).resolve()),
        "required_symbols": list(REQUIRED_SYMBOLS),
        "commodity_wrapper_symbols": list(COMMODITY_WRAPPERS),
        "current_available_raw_symbols": [
            row["symbol"] for row in availability if row["status"] == "available_raw_price_history"
        ],
        "missing_symbols": missing,
        "restored_symbols": [row["symbol"] for row in restored if row["status"].startswith("restored")],
        "reindexed_symbols": [row["symbol"] for row in restored if row["status"].startswith("reindexed")],
        "raw_price_history_found_for_all_required_symbols": not missing,
        "summary_metrics_converted_to_price_history": False,
        "provider_download": False,
        "internet_used": False,
        "intraday_data_used": False,
        "new_backtests_run": False,
        "commodity_lane_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_family_created": False,
        "new_variants_created": False,
        "six_row_design_changed": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "git_tracked_raw_commodity_files_found": tracked,
        "git_history_raw_commodity_files_found": sorted(set(history)),
        "locations_inspected_count": len(location_rows),
        "summary_only_locations_count": sum(1 for row in location_rows if row["summary_only"]),
        "raw_price_locations_with_commodity_wrappers_count": sum(
            1 for row in location_rows if row["raw_price_history_found"]
        ),
        "queue_source_of_truth_updated": f"next_action: {expected_queue_action}" in queue_text,
        "run_readiness_decision": decision,
        "next_action": next_action,
    }


def availability_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Required Symbol Availability", ""]
    lines.append("| Symbol | Current cache | Raw price history | Rows | First date | Last date | Status |")
    lines.append("|---|---:|---:|---:|---|---|---|")
    for row in rows:
        lines.append(
            "| {symbol} | {exists} | {raw} | {row_count} | {first} | {last} | {status} |".format(
                symbol=row["symbol"],
                exists=row["current_cache_exists"],
                raw=row["current_cache_is_raw_price_history"],
                row_count=row["row_count"],
                first=row["first_date"],
                last=row["last_date"],
                status=row["status"],
            )
        )
    return "\n".join(lines) + "\n"


def locations_md(rows: list[dict[str, Any]], title: str) -> str:
    lines = [f"# {title}", ""]
    lines.append("| Location | Exists | Type | Raw price found | Summary only | Notes |")
    lines.append("|---|---:|---|---:|---:|---|")
    for row in rows:
        lines.append(
            f"| `{row['location']}` | `{row['exists']}` | `{row['artifact_type']}` | `{row['raw_price_history_found']}` | `{row['summary_only']}` | {row['notes']} |"
        )
    return "\n".join(lines) + "\n"


def restored_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Restored / Reindexed Symbols", ""]
    if not rows:
        return "# Restored / Reindexed Symbols\n\nNo commodity wrapper symbols required restoration.\n"
    lines.append("| Symbol | Action | Source | Target | Status | Notes |")
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| {row['symbol']} | {row['action']} | `{row['source_path']}` | `{row['target_path']}` | {row['status']} | {row['notes']} |"
        )
    return "\n".join(lines) + "\n"


def missing_md(payload: dict[str, Any]) -> str:
    missing = payload["missing_symbols"]
    return f"""# Missing Symbols

Missing required symbols: `{', '.join(missing) if missing else 'none'}`

Missing commodity wrapper symbols: `{', '.join(symbol for symbol in missing if symbol in COMMODITY_WRAPPERS) if missing else 'none'}`

The prior acquisition evidence records that raw files were once written and includes hashes/row counts, but raw OHLCV was excluded from evidence. Summary metrics and report tables were not converted into price history.
"""


def raw_vs_summary_md(payload: dict[str, Any]) -> str:
    return f"""# Raw Price History Versus Summary Evidence

Current canonical cache root: `{payload['canonical_cache_root']}`

Raw current symbols available: `{', '.join(payload['current_available_raw_symbols']) or 'none'}`

Raw commodity wrapper files tracked by git: `{', '.join(payload['git_tracked_raw_commodity_files_found']) or 'none'}`

Raw commodity wrapper files found in git history: `{', '.join(payload['git_history_raw_commodity_files_found']) or 'none'}`

Prior commodity evidence includes:

- `cache_write_manifest.csv`: cache paths, row counts, and SHA-256 hashes.
- `data_quality_summary.csv`: QA metadata and first/last dates.
- exploratory result CSVs: target-window/risk summaries.
- diagnostics completion CSV/MD files: contribution and comovement summaries.

These artifacts are not raw price history. They cannot be used to restore OHLCV rows without fabricating data.
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "summary_metrics_converted_to_price_history",
        "provider_download",
        "internet_used",
        "intraday_data_used",
        "new_backtests_run",
        "commodity_lane_run",
        "new_strategy_discovery_run",
        "new_research_batch_run",
        "new_family_created",
        "new_variants_created",
        "six_row_design_changed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
        "macro_gld_continued",
        "volatility_throttle_continued",
        "managed_futures_reopened",
    ]
    return "# Guardrail Checklist\n\n" + "\n".join(f"- `{key}`: `{payload[key]}`" for key in keys) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Basket Local Cache Revalidation

Family: `{payload['family_id']}`

Lane: `{payload['lane_id']}`

Current raw symbols available: `{', '.join(payload['current_available_raw_symbols']) or 'none'}`

Missing symbols: `{', '.join(payload['missing_symbols']) or 'none'}`

Restored symbols: `{', '.join(payload['restored_symbols']) or 'none'}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`

No commodity lane, backtest, discovery, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live action, or real-money recommendation occurred.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Cache Revalidation Next Action

Exact next action:

`{payload['next_action']}`

Do not execute it in this task.
"""


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {
        "cache_revalidation_manifest.json": (output / "cache_revalidation_manifest.json").exists(),
        "required_symbol_availability.csv": (output / "required_symbol_availability.csv").exists(),
        "required_symbol_availability.md": (output / "required_symbol_availability.md").exists(),
        "current_cache_locations_inspected.md": (output / "current_cache_locations_inspected.md").exists(),
        "historical_cache_evidence_locations_inspected.md": (
            output / "historical_cache_evidence_locations_inspected.md"
        ).exists(),
        "restored_reindexed_symbols.csv": (output / "restored_reindexed_symbols.csv").exists(),
        "restored_reindexed_symbols.md": (output / "restored_reindexed_symbols.md").exists(),
        "missing_symbols.md": (output / "missing_symbols.md").exists(),
        "raw_price_history_vs_summary_evidence.md": (output / "raw_price_history_vs_summary_evidence.md").exists(),
        "guardrail_checklist.md": (output / "guardrail_checklist.md").exists(),
        "commodity_cache_revalidation_summary.md": (output / "commodity_cache_revalidation_summary.md").exists(),
        "commodity_cache_revalidation_next_action.md": (
            output / "commodity_cache_revalidation_next_action.md"
        ).exists(),
        "cache_revalidation_consistency_check.json": True,
    }
    checks: dict[str, Any] = {
        "revalidation_only": payload["commodity_cache_revalidation_only"] is True,
        "correct_family": payload["family_id"] == FAMILY_ID,
        "correct_lane": payload["lane_id"] == LANE_ID,
        "canonical_cache_root_identified": payload["canonical_cache_root"].endswith(str(DATA_CACHE_DIR)),
        "no_summary_to_price_conversion": payload["summary_metrics_converted_to_price_history"] is False,
        "no_provider_download": payload["provider_download"] is False,
        "no_intraday": payload["intraday_data_used"] is False,
        "no_lane_or_backtest": payload["commodity_lane_run"] is False and payload["new_backtests_run"] is False,
        "no_discovery_or_batch": payload["new_strategy_discovery_run"] is False
        and payload["new_research_batch_run"] is False,
        "no_family_or_variant_change": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["six_row_design_changed"] is False,
        "no_candidate_promotion_paper": payload["candidate_exhaustive_run"] is False
        and payload["promotion_candidates_created"] is False
        and payload["paper_forward_activation"] is False
        and payload["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": payload["broker_api_called"] is False
        and payload["broker_orders_submitted"] is False
        and payload["broker_orders_cancelled"] is False
        and payload["broker_orders_reconciled"] is False
        and payload["live_orders"] is False
        and payload["real_money_recommendation"] is False,
        "excluded_work_not_continued": payload["macro_gld_continued"] is False
        and payload["volatility_throttle_continued"] is False
        and payload["managed_futures_reopened"] is False,
        "active_state_preserved": payload["active_vm_preserved"] is True
        and payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "readiness_valid": payload["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "blocked_has_missing_symbols": payload["run_readiness_decision"] != RUN_BLOCKED
        or set(payload["missing_symbols"]) >= set(COMMODITY_WRAPPERS),
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    availability = availability_rows(root)
    locations = locations_inspected(root)
    restored = restored_rows(root, availability)
    payload = build_manifest(root, created, output, availability, locations, restored)

    current_locations = [row for row in locations if row["artifact_type"] == "canonical_current_cache"]
    historical_locations = [row for row in locations if row["artifact_type"] != "canonical_current_cache"]

    write_json(output / "cache_revalidation_manifest.json", payload)
    write_csv(output / "required_symbol_availability.csv", availability, AVAILABILITY_FIELDS)
    write_text(output / "required_symbol_availability.md", availability_md(availability))
    write_text(output / "current_cache_locations_inspected.md", locations_md(current_locations, "Current Cache Locations Inspected"))
    write_text(
        output / "historical_cache_evidence_locations_inspected.md",
        locations_md(historical_locations, "Historical Cache / Evidence Locations Inspected"),
    )
    write_csv(output / "restored_reindexed_symbols.csv", restored, RESTORE_FIELDS)
    write_text(output / "restored_reindexed_symbols.md", restored_md(restored))
    write_text(output / "missing_symbols.md", missing_md(payload))
    write_text(output / "raw_price_history_vs_summary_evidence.md", raw_vs_summary_md(payload))
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "commodity_cache_revalidation_summary.md", summary_md(payload))
    write_text(output / "commodity_cache_revalidation_next_action.md", next_action_md(payload))
    checks = consistency_check(payload, output)
    write_json(output / "cache_revalidation_consistency_check.json", checks)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": checks["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "family_id": result["family_id"],
                "lane_id": result["lane_id"],
                "missing_symbols": result["missing_symbols"],
                "restored_symbols": result["restored_symbols"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
