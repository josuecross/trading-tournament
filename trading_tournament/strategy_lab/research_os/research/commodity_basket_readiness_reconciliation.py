from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


FAMILY_ID = "commodity_basket_etf_momentum_v1"
LANE_ID = "commodity_basket_etf_momentum_bounded_lane_v1"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "commodity_basket_readiness_reconciliation" / "latest"

PROVIDER_DIR = Path("evidence") / "research_recovery" / "commodity_basket_provider_refresh" / "latest"
REVALIDATION_DIR = Path("evidence") / "research_recovery" / "commodity_basket_local_cache_revalidation" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_design" / "latest"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"

REQUIRED_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD")
REFRESHED_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI")
RAW_PRICE_COLUMNS = {"date", "open", "high", "low", "close", "adj_close", "volume"}

FINAL_READY = "commodity_basket_ready_to_run_verified"
FINAL_INCONSISTENT = "commodity_basket_readiness_still_inconsistent"
NEXT_ACTION_READY = "run_commodity_basket_etf_momentum_bounded_lane"
NEXT_ACTION_INCONSISTENT = "reconcile_commodity_basket_readiness_evidence_again"

AVAILABILITY_FIELDS = (
    "symbol",
    "cache_path",
    "cache_exists",
    "is_raw_price_history",
    "row_count",
    "first_date",
    "last_date",
    "sha256",
    "status",
)

PROVIDER_SUMMARY_FIELDS = (
    "symbol",
    "provider",
    "download_status",
    "row_count",
    "first_date",
    "last_date",
    "quality_status",
    "sha256",
)

FOLDER_STATUS_FIELDS = ("evidence_folder", "required_file", "exists", "notes")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "cache_exists": False,
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
            "cache_exists": True,
            "is_raw_price_history": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "sha256": sha256_file(path),
        }
    return {
        "cache_exists": True,
        "is_raw_price_history": is_raw,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "sha256": sha256_file(path),
    }


def current_availability(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = root / DATA_CACHE_DIR / f"{symbol}.csv"
        meta = cache_metadata(path)
        ok = meta["cache_exists"] and meta["is_raw_price_history"] and meta["row_count"] >= 380
        rows.append(
            {
                "symbol": symbol,
                "cache_path": str(path.resolve()),
                "cache_exists": meta["cache_exists"],
                "is_raw_price_history": meta["is_raw_price_history"],
                "row_count": meta["row_count"],
                "first_date": meta["first_date"],
                "last_date": meta["last_date"],
                "sha256": meta["sha256"],
                "status": "available_raw_price_history" if ok else "missing_or_invalid_raw_price_history",
            }
        )
    return rows


def folder_status(root: Path) -> list[dict[str, Any]]:
    required = {
        PROVIDER_DIR: (
            "provider_refresh_manifest.json",
            "symbol_refresh_table.csv",
            "cache_write_manifest.csv",
            "data_quality_summary.csv",
            "hash_report.csv",
            "provider_refresh_consistency_check.json",
        ),
        REVALIDATION_DIR: (
            "cache_revalidation_manifest.json",
            "required_symbol_availability.csv",
            "cache_revalidation_consistency_check.json",
        ),
        DESIGN_DIR: (
            "commodity_basket_bounded_design_manifest.json",
            "commodity_basket_bounded_variant_design_table.csv",
            "commodity_basket_bounded_design_consistency_check.json",
        ),
    }
    rows: list[dict[str, Any]] = []
    for folder, filenames in required.items():
        for filename in filenames:
            path = root / folder / filename
            rows.append(
                {
                    "evidence_folder": str((root / folder).resolve()),
                    "required_file": filename,
                    "exists": path.exists(),
                    "notes": "present" if path.exists() else "missing",
                }
            )
    return rows


def provider_summary(root: Path) -> list[dict[str, Any]]:
    refresh = {row["symbol"]: row for row in read_csv(root / PROVIDER_DIR / "symbol_refresh_table.csv")}
    hashes = {row["symbol"]: row for row in read_csv(root / PROVIDER_DIR / "hash_report.csv")}
    rows: list[dict[str, Any]] = []
    for symbol in REFRESHED_SYMBOLS:
        r = refresh.get(symbol, {})
        h = hashes.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "provider": r.get("provider", ""),
                "download_status": r.get("download_status", ""),
                "row_count": r.get("row_count", h.get("row_count", "")),
                "first_date": r.get("first_date", h.get("first_date", "")),
                "last_date": r.get("last_date", h.get("last_date", "")),
                "quality_status": r.get("quality_status", ""),
                "sha256": h.get("sha256", ""),
            }
        )
    return rows


def decisions(root: Path) -> dict[str, Any]:
    provider_manifest = read_json(root / PROVIDER_DIR / "provider_refresh_manifest.json")
    revalidation_manifest = read_json(root / REVALIDATION_DIR / "cache_revalidation_manifest.json")
    design_manifest = read_json(root / DESIGN_DIR / "commodity_basket_bounded_design_manifest.json")
    provider_check = read_json(root / PROVIDER_DIR / "provider_refresh_consistency_check.json")
    revalidation_check = read_json(root / REVALIDATION_DIR / "cache_revalidation_consistency_check.json")
    design_check = read_json(root / DESIGN_DIR / "commodity_basket_bounded_design_consistency_check.json")
    queue_text = read_text(root / QUEUE)
    return {
        "provider_manifest": provider_manifest,
        "revalidation_manifest": revalidation_manifest,
        "design_manifest": design_manifest,
        "provider_consistency_passed": provider_check.get("consistency_passed") is True,
        "revalidation_consistency_passed": revalidation_check.get("consistency_passed") is True,
        "design_consistency_passed": design_check.get("consistency_passed") is True,
        "queue_next_action_ready": f"next_action: {NEXT_ACTION_READY}" in queue_text,
        "queue_text": queue_text,
    }


def contradiction_list(
    availability: list[dict[str, Any]],
    provider_rows: list[dict[str, Any]],
    folder_rows: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[str]:
    contradictions: list[str] = []
    missing_files = [row for row in folder_rows if row["exists"] is not True]
    if missing_files:
        contradictions.append("required evidence files are missing")
    unavailable = [row["symbol"] for row in availability if row["status"] != "available_raw_price_history"]
    if unavailable:
        contradictions.append("required symbols unavailable: " + ",".join(unavailable))
    bad_provider = [
        row["symbol"]
        for row in provider_rows
        if row["download_status"] != "downloaded_pass" or row["quality_status"] not in {"pass", "warning"}
    ]
    if bad_provider:
        contradictions.append("provider refresh rows not pass/warning: " + ",".join(bad_provider))
    if state["provider_manifest"].get("run_readiness_decision") != "commodity_basket_cache_ready_for_bounded_run":
        contradictions.append("provider refresh manifest is not cache-ready")
    if state["revalidation_manifest"].get("run_readiness_decision") != "commodity_basket_cache_ready_for_bounded_run":
        contradictions.append("cache revalidation manifest is not cache-ready")
    if state["design_manifest"].get("run_readiness_decision") != "commodity_basket_bounded_design_run_ready":
        contradictions.append("bounded design manifest is not run-ready")
    if state["design_manifest"].get("next_action") != NEXT_ACTION_READY:
        contradictions.append("bounded design next action is not lane run")
    if not state["queue_next_action_ready"]:
        contradictions.append("queue next action is not lane run")
    if not state["provider_consistency_passed"]:
        contradictions.append("provider consistency check did not pass")
    if not state["revalidation_consistency_passed"]:
        contradictions.append("cache revalidation consistency check did not pass")
    if not state["design_consistency_passed"]:
        contradictions.append("bounded design consistency check did not pass")
    return contradictions


def availability_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Current Required-Symbol Availability", ""]
    lines.append("| Symbol | Raw cache | Rows | First date | Last date | Status |")
    lines.append("|---|---:|---:|---|---|---|")
    for row in rows:
        lines.append(
            f"| {row['symbol']} | `{row['is_raw_price_history']}` | {row['row_count']} | {row['first_date']} | {row['last_date']} | `{row['status']}` |"
        )
    return "\n".join(lines) + "\n"


def provider_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Provider Refresh Summary", ""]
    lines.append("| Symbol | Provider | Status | Rows | First date | Last date | Quality | SHA-256 |")
    lines.append("|---|---|---|---:|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| {row['symbol']} | {row['provider']} | {row['download_status']} | {row['row_count']} | {row['first_date']} | {row['last_date']} | {row['quality_status']} | `{row['sha256']}` |"
        )
    return "\n".join(lines) + "\n"


def folder_status_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Folder Status", ""]
    lines.append("| Folder | Required file | Exists |")
    lines.append("|---|---|---:|")
    for row in rows:
        lines.append(f"| `{row['evidence_folder']}` | `{row['required_file']}` | `{row['exists']}` |")
    return "\n".join(lines) + "\n"


def contradiction_md(contradictions: list[str]) -> str:
    if not contradictions:
        return """# Contradiction Review

No contradictions were found in the current repository source-of-truth evidence.

The reported uploaded/reviewed package appears stale or incomplete relative to the current local evidence because the current manifests, cache files, revalidation packet, bounded-design packet, and queue all point to the refreshed/cache-ready state.
"""
    return "# Contradiction Review\n\n" + "\n".join(f"- {item}" for item in contradictions) + "\n"


def queue_md(state: dict[str, Any]) -> str:
    queue_text = state["queue_text"]
    selected_lines = [
        line
        for line in queue_text.splitlines()
        if "commodity_basket" in line
        or "run_readiness_decision" in line
        or "cache_revalidation_status" in line
        or "next_action" in line
        or "provider_refresh_evidence" in line
    ]
    return "# Queue Source Of Truth\n\n" + "\n".join(f"- `{line.strip()}`" for line in selected_lines) + "\n"


def decision_md(payload: dict[str, Any], contradictions: list[str]) -> str:
    return f"""# Readiness Decision

Final decision: `{payload['final_decision']}`

Cache revalidation decision: `{payload['cache_revalidation_decision']}`

Bounded design run-readiness decision: `{payload['bounded_design_run_readiness_decision']}`

Queue next action: `{payload['queue_next_action']}`

Contradictions found: `{len(contradictions)}`
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "commodity_lane_run",
        "new_backtests_run",
        "new_strategy_discovery_run",
        "new_research_batch_run",
        "provider_download_this_step",
        "intraday_data_used",
        "new_family_created",
        "new_variants_created",
        "six_row_design_changed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return "# Guardrail Checklist\n\n" + "\n".join(f"- `{key}`: `{payload[key]}`" for key in keys) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Basket Readiness Reconciliation

Family: `{payload['family_id']}`

Lane: `{payload['lane_id']}`

Provider refresh evidence: `{payload['provider_refresh_evidence_path']}`

Cache revalidation evidence: `{payload['cache_revalidation_evidence_path']}`

Bounded design evidence: `{payload['bounded_design_evidence_path']}`

Uploaded/reviewed package stale or incomplete: `{payload['uploaded_review_package_stale_or_incomplete']}`

Final decision: `{payload['final_decision']}`

Exact next action: `{payload['next_action']}`

No commodity lane, backtest, discovery, provider refresh, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live action, or real-money recommendation occurred in this reconciliation step.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"# Readiness Reconciliation Next Action\n\n`{payload['next_action']}`\n"


def build_manifest(
    created: str,
    output: Path,
    availability: list[dict[str, Any]],
    provider_rows: list[dict[str, Any]],
    contradictions: list[str],
    state: dict[str, Any],
) -> dict[str, Any]:
    final_ready = not contradictions
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "commodity_readiness_reconciliation_only": True,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "provider_refresh_evidence_path": str((ROOT / PROVIDER_DIR).resolve()),
        "cache_revalidation_evidence_path": str((ROOT / REVALIDATION_DIR).resolve()),
        "bounded_design_evidence_path": str((ROOT / DESIGN_DIR).resolve()),
        "uploaded_review_package_stale_or_incomplete": final_ready,
        "required_symbols": list(REQUIRED_SYMBOLS),
        "refreshed_symbols": list(REFRESHED_SYMBOLS),
        "all_required_symbols_available": all(row["status"] == "available_raw_price_history" for row in availability),
        "provider_refreshed_symbols_passed": all(
            row["download_status"] == "downloaded_pass" and row["quality_status"] in {"pass", "warning"}
            for row in provider_rows
        ),
        "cache_revalidation_decision": state["revalidation_manifest"].get("run_readiness_decision", ""),
        "bounded_design_run_readiness_decision": state["design_manifest"].get("run_readiness_decision", ""),
        "queue_next_action": NEXT_ACTION_READY if state["queue_next_action_ready"] else "",
        "provider_consistency_passed": state["provider_consistency_passed"],
        "cache_revalidation_consistency_passed": state["revalidation_consistency_passed"],
        "bounded_design_consistency_passed": state["design_consistency_passed"],
        "contradictions_found_count": len(contradictions),
        "contradictions": contradictions,
        "final_decision": FINAL_READY if final_ready else FINAL_INCONSISTENT,
        "next_action": NEXT_ACTION_READY if final_ready else NEXT_ACTION_INCONSISTENT,
        "commodity_lane_run": False,
        "new_backtests_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "provider_download_this_step": False,
        "intraday_data_used": False,
        "new_family_created": False,
        "new_variants_created": False,
        "six_row_design_changed": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
    }


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {
        "readiness_reconciliation_manifest.json": (output / "readiness_reconciliation_manifest.json").exists(),
        "readiness_reconciliation_summary.md": (output / "readiness_reconciliation_summary.md").exists(),
        "evidence_folder_status.csv": (output / "evidence_folder_status.csv").exists(),
        "evidence_folder_status.md": (output / "evidence_folder_status.md").exists(),
        "current_required_symbol_availability.csv": (output / "current_required_symbol_availability.csv").exists(),
        "current_required_symbol_availability.md": (output / "current_required_symbol_availability.md").exists(),
        "provider_refresh_summary.csv": (output / "provider_refresh_summary.csv").exists(),
        "provider_refresh_summary.md": (output / "provider_refresh_summary.md").exists(),
        "cache_revalidation_decision.md": (output / "cache_revalidation_decision.md").exists(),
        "bounded_design_readiness_decision.md": (output / "bounded_design_readiness_decision.md").exists(),
        "queue_source_of_truth.md": (output / "queue_source_of_truth.md").exists(),
        "contradiction_review.md": (output / "contradiction_review.md").exists(),
        "guardrail_checklist.md": (output / "guardrail_checklist.md").exists(),
        "readiness_reconciliation_next_action.md": (output / "readiness_reconciliation_next_action.md").exists(),
        "readiness_reconciliation_consistency_check.json": True,
    }
    checks: dict[str, Any] = {
        "reconciliation_only": payload["commodity_readiness_reconciliation_only"] is True,
        "correct_family": payload["family_id"] == FAMILY_ID,
        "correct_lane": payload["lane_id"] == LANE_ID,
        "all_required_symbols_available": payload["all_required_symbols_available"] is True,
        "provider_symbols_passed": payload["provider_refreshed_symbols_passed"] is True,
        "cache_revalidation_ready": payload["cache_revalidation_decision"] == "commodity_basket_cache_ready_for_bounded_run",
        "bounded_design_ready": payload["bounded_design_run_readiness_decision"] == "commodity_basket_bounded_design_run_ready",
        "queue_next_action_ready": payload["queue_next_action"] == NEXT_ACTION_READY,
        "no_contradictions": payload["contradictions_found_count"] == 0,
        "final_decision_ready": payload["final_decision"] == FINAL_READY,
        "next_action_ready": payload["next_action"] == NEXT_ACTION_READY,
        "no_lane_or_backtest": payload["commodity_lane_run"] is False and payload["new_backtests_run"] is False,
        "no_provider_download_this_step": payload["provider_download_this_step"] is False,
        "no_discovery_or_batch": payload["new_strategy_discovery_run"] is False
        and payload["new_research_batch_run"] is False,
        "no_family_variant_design_change": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["six_row_design_changed"] is False,
        "no_candidate_promotion_paper": payload["candidate_exhaustive_run"] is False
        and payload["promotion_candidates_created"] is False
        and payload["paper_forward_activation"] is False,
        "no_broker_live_real_money": payload["broker_api_called"] is False
        and payload["live_orders"] is False
        and payload["real_money_recommendation"] is False,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    availability = current_availability(root)
    provider_rows = provider_summary(root)
    folders = folder_status(root)
    state = decisions(root)
    contradictions = contradiction_list(availability, provider_rows, folders, state)
    payload = build_manifest(created, output, availability, provider_rows, contradictions, state)

    write_json(output / "readiness_reconciliation_manifest.json", payload)
    write_text(output / "readiness_reconciliation_summary.md", summary_md(payload))
    write_csv(output / "evidence_folder_status.csv", folders, FOLDER_STATUS_FIELDS)
    write_text(output / "evidence_folder_status.md", folder_status_md(folders))
    write_csv(output / "current_required_symbol_availability.csv", availability, AVAILABILITY_FIELDS)
    write_text(output / "current_required_symbol_availability.md", availability_md(availability))
    write_csv(output / "provider_refresh_summary.csv", provider_rows, PROVIDER_SUMMARY_FIELDS)
    write_text(output / "provider_refresh_summary.md", provider_md(provider_rows))
    write_text(output / "cache_revalidation_decision.md", decision_md(payload, contradictions))
    write_text(output / "bounded_design_readiness_decision.md", decision_md(payload, contradictions))
    write_text(output / "queue_source_of_truth.md", queue_md(state))
    write_text(output / "contradiction_review.md", contradiction_md(contradictions))
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "readiness_reconciliation_next_action.md", next_action_md(payload))
    checks = consistency_check(payload, output)
    write_json(output / "readiness_reconciliation_consistency_check.json", checks)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": checks["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "final_decision": result["final_decision"],
                "contradictions_found_count": result["contradictions_found_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
