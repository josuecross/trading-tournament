from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_advisor_consistency_check import build_consistency_report, consistency_report_markdown, write_report_outputs


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "evidence" / "advisor_upload"
PACKET_SPEC = REPO_ROOT / "advisor_audit" / "advisor_packet_spec.yaml"
ALLOWED_SUFFIXES = {".md", ".csv", ".json", ".yaml", ".yml", ".png", ".txt"}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "cache", "raw"}
REPRO_ALLOWLIST = {
    "config_used.yaml",
    "run_metadata.json",
    "package_versions.json",
    "pip_freeze.txt",
    "data_quality_summary.csv",
    "data_coverage.csv",
    "consistency_check.json",
    "headline_metrics.json",
    "key_findings.json",
    "risk_events.csv",
    "strategy_lifecycle_events.csv",
    "strategy_health.csv",
    "symbol_contribution.csv",
    "skipped_signal_summary.csv",
    "trade_audit_sample.csv",
    "top_trades_by_pnl.csv",
    "bottom_trades_by_pnl.csv",
}


@dataclass
class FileEntry:
    source: Path | None
    arcname: str
    content: bytes | None = None


@dataclass
class PacketBuild:
    name: str
    source_paths: list[str]
    entries: list[FileEntry] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    notes: str = ""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def safe_read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class _ListWriter:
    def __init__(self, out: list[str]):
        self.out = out

    def write(self, text: str) -> int:
        self.out.append(text)
        return len(text)


def clean_value(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ""
    except TypeError:
        pass
    if not isinstance(value, (list, tuple, dict)):
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
    return value


def csv_bytes(rows: list[dict[str, Any]], columns: list[str] | None = None) -> bytes:
    if columns is None:
        columns = sorted({key for row in rows for key in row})
    out: list[str] = []
    writer = csv.DictWriter(_ListWriter(out), fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: clean_value(row.get(key, "")) for key in columns})
    return "".join(out).encode("utf-8")


def md_bytes(text: str) -> bytes:
    return text.strip().encode("utf-8") + b"\n"


def json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")


def is_forbidden_path(path: Path, no_nested_zips: bool = True) -> bool:
    parts = {part.lower() for part in path.parts}
    if any(part in parts for part in EXCLUDED_PARTS):
        return True
    lower = path.as_posix().lower()
    if "data/cache" in lower or "data/raw" in lower:
        return True
    if path.name.startswith("."):
        return True
    if no_nested_zips and path.suffix.lower() == ".zip":
        return True
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return True
    if "ohlcv" in lower:
        return True
    return False


def collect_from_path(source: Path, no_nested_zips: bool = True, allowlist: set[str] | None = None) -> tuple[list[FileEntry], list[str]]:
    entries: list[FileEntry] = []
    missing: list[str] = []
    if not source.exists():
        missing.append(source.as_posix())
        return entries, missing
    paths = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
    for path in paths:
        if allowlist is not None and path.name not in allowlist:
            continue
        if is_forbidden_path(path, no_nested_zips=no_nested_zips):
            continue
        entries.append(FileEntry(source=path, arcname=f"source/{rel(path)}"))
    return entries, missing


def add_generated(entries: list[FileEntry], name: str, content: bytes) -> None:
    entries.append(FileEntry(source=None, arcname=name, content=content))


def row_count_for_content(arcname: str, content: bytes) -> int | str:
    suffix = Path(arcname).suffix.lower()
    if suffix == ".csv":
        try:
            text = content.decode("utf-8")
            rows = list(csv.reader(text.splitlines()))
            return max(0, len(rows) - 1)
        except Exception:
            return "unreadable"
    if suffix == ".json":
        try:
            parsed = json.loads(content.decode("utf-8"))
            if isinstance(parsed, list):
                return len(parsed)
            if isinstance(parsed, dict):
                return len(parsed)
        except Exception:
            return "unreadable"
    return ""


def summarize_dates_and_tiers(entries: list[FileEntry]) -> tuple[str, str, list[str], str, list[str]]:
    dates: list[pd.Timestamp] = []
    tiers: set[str] = set()
    finality: set[str] = set()
    run_ids: set[str] = set()
    for entry in entries:
        if Path(entry.arcname).suffix.lower() != ".csv":
            continue
        content = entry.content if entry.content is not None else read_bytes(entry.source) if entry.source else b""
        try:
            frame = pd.read_csv(io.BytesIO(content))
        except Exception:
            continue
        for col in ["start_date", "end_date", "observation_start_date", "observation_end_date", "latest_observation_end_date"]:
            if col in frame:
                parsed = pd.to_datetime(frame[col], errors="coerce").dropna()
                dates.extend(parsed.tolist())
        if "credibility_tier" in frame:
            tiers.update(frame["credibility_tier"].dropna().astype(str).unique())
        if "final_validation_completed" in frame:
            vals = frame["final_validation_completed"].dropna().astype(str).unique()
            finality.update(f"final_validation_completed={val}" for val in vals)
        if "sampled_results_are_final" in frame:
            vals = frame["sampled_results_are_final"].dropna().astype(str).unique()
            finality.update(f"sampled_results_are_final={val}" for val in vals)
        if "run_id" in frame:
            run_ids.update(frame["run_id"].dropna().astype(str).unique())
    data_start = min(dates).date().isoformat() if dates else ""
    data_end = max(dates).date().isoformat() if dates else ""
    return data_start, data_end, sorted(tiers), "; ".join(sorted(finality)), sorted(run_ids)


def base_packet_readme(packet_name: str, notes: str = "") -> bytes:
    return md_bytes(
        f"""
        # {packet_name}

        This advisor packet is research-only paper/demo evidence. It contains no broker integration, no live orders, no order placement, and no real-money recommendation.

        Review `PACKET_MANIFEST.json`, `SOURCE_PATHS.csv`, `ROW_COUNTS.csv`, and `SHA256SUMS.csv` before interpreting results.

        {notes}
        """
    )


def build_packet_manifest(packet: PacketBuild, entries: list[FileEntry], created: str) -> dict[str, Any]:
    data_start, data_end, tiers, finality, run_ids = summarize_dates_and_tiers(entries)
    consistency_status = ""
    consistency_errors_count = 0
    consistency_warnings_count = 0
    for entry in entries:
        if entry.arcname == "ADVISOR_CONSISTENCY_REPORT.json":
            content = entry.content if entry.content is not None else read_bytes(entry.source) if entry.source else b""
            try:
                consistency = json.loads(content.decode("utf-8"))
                consistency_status = str(consistency.get("consistency_status", ""))
                consistency_errors_count = int(consistency.get("error_count", 0))
                consistency_warnings_count = int(consistency.get("warning_count", 0))
            except Exception:
                consistency_status = "unreadable"
                consistency_errors_count = 1
    return {
        "packet_name": packet.name,
        "created_timestamp_utc": created,
        "repo_path": str(REPO_ROOT),
        "source_paths": packet.source_paths,
        "file_count": len(entries),
        "missing_files": packet.missing_files,
        "run_ids": run_ids,
        "data_start": data_start,
        "data_end": data_end,
        "evidence_tiers_present": tiers,
        "finality_status": finality,
        "raw_data_included": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "consistency_status": consistency_status,
        "consistency_errors_count": consistency_errors_count,
        "consistency_warnings_count": consistency_warnings_count,
        "notes": packet.notes,
    }


def finalize_packet(packet: PacketBuild, latest_dir: Path, created: str, no_nested_zips: bool) -> Path:
    entries = list(packet.entries)
    add_generated(entries, "README_FOR_ADVISOR.md", base_packet_readme(packet.name, packet.notes))
    source_rows = []
    for source in packet.source_paths:
        source_rows.append({"source_path": source, "included": Path(source).exists(), "packet": packet.name})
    for missing in packet.missing_files:
        source_rows.append({"source_path": missing, "included": False, "packet": packet.name})
    add_generated(entries, "SOURCE_PATHS.csv", csv_bytes(source_rows, ["packet", "source_path", "included"]))

    row_rows: list[dict[str, Any]] = []
    sha_rows: list[dict[str, Any]] = []
    materialized: list[tuple[str, bytes]] = []
    for entry in entries:
        data = entry.content if entry.content is not None else read_bytes(entry.source) if entry.source else b""
        materialized.append((entry.arcname, data))
        row_rows.append({"file": entry.arcname, "row_count": row_count_for_content(entry.arcname, data)})
        sha_rows.append({"file": entry.arcname, "sha256": sha256_bytes(data)})
    add_generated(entries, "ROW_COUNTS.csv", csv_bytes(row_rows, ["file", "row_count"]))
    add_generated(entries, "SHA256SUMS.csv", csv_bytes(sha_rows, ["file", "sha256"]))

    manifest_entries = list(entries)
    manifest = build_packet_manifest(packet, manifest_entries, created)
    add_generated(entries, "PACKET_MANIFEST.json", json_bytes(manifest))

    zip_path = latest_dir / f"{packet.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        seen: set[str] = set()
        for entry in entries:
            if no_nested_zips and entry.arcname.lower().endswith(".zip"):
                continue
            data = entry.content if entry.content is not None else read_bytes(entry.source) if entry.source else b""
            arcname = entry.arcname
            if arcname in seen:
                stem = Path(arcname).stem
                suffix = Path(arcname).suffix
                parent = Path(arcname).parent.as_posix()
                arcname = f"{parent}/{stem}_{len(seen)}{suffix}" if parent != "." else f"{stem}_{len(seen)}{suffix}"
            seen.add(arcname)
            zf.writestr(arcname, data)
    return zip_path


def challenge_generated_files() -> list[FileEntry]:
    base = REPO_ROOT / "evidence" / "challenge_runs" / "latest"
    results = safe_read_csv(base / "challenge_results.csv")
    rolling = safe_read_csv(base / "rolling_window_summary.csv")
    rankings = safe_read_csv(base / "strategy_rankings.csv")
    entries: list[FileEntry] = []
    finality_rows: list[dict[str, Any]] = []
    if not rolling.empty:
        for _, row in rolling.iterrows():
            finality_rows.append({
                "lane": row.get("lane", ""),
                "strategy": row.get("strategy", ""),
                "family_id": row.get("family_id", ""),
                "horizon": row.get("horizon", ""),
                "standard_or_stress": row.get("standard_or_stress", ""),
                "rolling_method": row.get("rolling_method", ""),
                "number_of_windows": row.get("number_of_windows", ""),
                "possible_window_count": row.get("possible_window_count", ""),
                "sampled_results_are_final": row.get("sampled_results_are_final", ""),
                "final_validation_completed": row.get("final_validation_completed", ""),
                "rolling_status": row.get("rolling_status", ""),
            })
    add_generated(entries, "ROW_FINALITY_MATRIX.csv", csv_bytes(finality_rows))

    family_rows: list[dict[str, Any]] = []
    if not rankings.empty:
        family = rankings[rankings.get("lane", pd.Series()).astype(str).eq("independent_family_challenge")]
        for _, row in family.iterrows():
            family_rows.append({
                "rank_overall": row.get("rank_overall", ""),
                "family_id": row.get("family_id", ""),
                "strategy": row.get("strategy", ""),
                "credibility_tier": row.get("credibility_tier", ""),
                "run_status": row.get("run_status", ""),
                "final_validation_completed": row.get("final_validation_completed", ""),
                "target_300_rate": row.get("pct_90d_target_300_before_stop", ""),
                "target_400_rate": row.get("pct_90d_target_400_before_stop", ""),
                "stop_hit_rate": row.get("pct_90d_any_stop_hit", ""),
                "worst_drawdown": row.get("worst_90d_max_drawdown", ""),
                "audit_verdict": row.get("audit_verdict", ""),
            })
    add_generated(entries, "FAMILY_COMPARISON_MATRIX.csv", csv_bytes(family_rows))

    best_exact = ""
    if family_rows:
        completed = [row for row in family_rows if row.get("run_status") == "completed" and str(row.get("final_validation_completed")) == "True"]
        if completed:
            best_exact = completed[0].get("family_id", "")
    decision = f"""
    # Best Family Decision

    The current exact independent-family packet ranks `{best_exact or 'unavailable'}` as the best overall family tradeoff. GLD remains the highest exact target-rate family when present, but it carries materially worse drawdown/stop behavior than SPY_200d. A/A-B strategy-family rows remain incomplete unless a fresh-window exact rolling stream is exposed; no summary-metric approximation is used.

    This is research-only paper/demo evidence and not a real-money recommendation.
    """
    add_generated(entries, "BEST_FAMILY_DECISION.md", md_bytes(decision))
    return entries


def advisor_index_generated_files(created: str) -> list[FileEntry]:
    challenge_base = REPO_ROOT / "evidence" / "challenge_runs" / "latest"
    family_exploratory = REPO_ROOT / "evidence" / "challenge_runs" / "family_exploratory_latest"
    paper_base = REPO_ROOT / "evidence" / "paper_forward_runs" / "latest"
    profit_base = REPO_ROOT / "evidence" / "profit_exploration" / "latest"
    candidate_base = REPO_ROOT / "evidence" / "strategy_candidate_queue" / "latest"
    promotion_base = REPO_ROOT / "evidence" / "promotion_reviews" / "combo_SPY200d_GLD_50_50_v1" / "latest"
    generic_promotion_review_base = REPO_ROOT / "evidence" / "promotion_review" / "latest"
    combo_observation_plan_base = REPO_ROOT / "evidence" / "paper_forward_observation_plans" / "combo_SPY200d_GLD_50_50_v1" / "latest"
    combo_observation_activation_base = REPO_ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest"
    combo_rule_hash_base = REPO_ROOT / "evidence" / "rule_hash_reviews" / "combo_SPY200d_GLD_50_50_v1" / "latest"
    implementation_base = REPO_ROOT / "evidence" / "implementation_reviews" / "qqq_spy_gld_ief_dual_momentum_v1" / "latest"
    value_implementation_base = REPO_ROOT / "evidence" / "implementation_reviews" / "value_momentum_factor_etf_rotation_v1" / "latest"
    sector_implementation_base = REPO_ROOT / "evidence" / "implementation_reviews" / "sector_top2_momentum_simple_v1" / "latest"
    managed_futures_implementation_base = REPO_ROOT / "evidence" / "implementation_reviews" / "managed_futures_proxy_etf_trend_v1" / "latest"
    value_data_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_reviews" / "value_momentum_factor_etf_rotation_v1" / "latest"
    managed_futures_data_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_reviews" / "managed_futures_proxy_etf_trend_v1" / "latest"
    value_provider_terms_base = REPO_ROOT / "evidence" / "data_acquisition_reviews" / "value_momentum_factor_etf_rotation_v1" / "provider_terms_security_review" / "latest"
    managed_futures_provider_terms_base = REPO_ROOT / "evidence" / "data_acquisition_reviews" / "managed_futures_proxy_etf_trend_v1" / "provider_terms_security_review" / "latest"
    value_data_acquisition_run_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "value_momentum_factor_etf_rotation_v1" / "latest"
    managed_futures_data_acquisition_run_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "managed_futures_proxy_etf_trend_v1" / "latest"
    paper_forward_cache_update_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "paper_forward_observation_cache_update" / "latest"
    managed_futures_methodology_base = REPO_ROOT / "evidence" / "methodology_reviews" / "managed_futures_proxy_etf_trend_v1" / "latest"
    candidate_triage_base = REPO_ROOT / "evidence" / "candidate_triage" / "latest"
    historical_research_base = REPO_ROOT / "evidence" / "historical_research_expansion" / "latest"
    research_state_base = REPO_ROOT / "evidence" / "research_state" / "latest"
    research_diagnostics_base = REPO_ROOT / "evidence" / "research_diagnostics" / "latest"
    active_combo_base = REPO_ROOT / "evidence" / "active_combo_benchmark" / "latest"
    individual_stock_gate1b_base = REPO_ROOT / "evidence" / "research_memos" / "gate1b" / "individual_stock_momentum" / "latest"
    individual_stock_gate1c_base = REPO_ROOT / "evidence" / "research_memos" / "gate1c" / "individual_stock_momentum" / "latest"
    individual_stock_gate1d_base = REPO_ROOT / "evidence" / "research_memos" / "gate1d" / "individual_stock_momentum" / "latest"
    individual_stock_gate1e_base = REPO_ROOT / "evidence" / "research_memos" / "gate1e" / "individual_stock_momentum" / "latest"
    individual_stock_gate1f_base = REPO_ROOT / "evidence" / "research_memos" / "gate1f" / "individual_stock_momentum" / "latest"
    queue_reprioritization_base = REPO_ROOT / "evidence" / "research_memos" / "queue_reprioritization" / "latest"
    commodity_review_base = REPO_ROOT / "evidence" / "research_memos" / "commodity_basket_etf_momentum" / "latest"
    commodity_data_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_reviews" / "commodity_basket_etf_momentum_v1" / "latest"
    commodity_fast_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "commodity_basket_fast_exploratory" / "latest"
    commodity_exploratory_base = REPO_ROOT / "evidence" / "commodity_exploratory" / "latest"
    commodity_risk_control_base = REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest"
    commodity_risk_control_verdict_audit_base = REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_verdict_audit" / "latest"
    commodity_risk_control_diagnostics_completion_base = REPO_ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_diagnostics_completion" / "latest"
    crypto_fast_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "crypto_spot_fast_exploratory" / "latest"
    crypto_tier2_risk_control_base = REPO_ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest"
    global_multi_asset_fast_acquisition_base = REPO_ROOT / "evidence" / "data_acquisition_runs" / "global_multi_asset_fast_exploratory" / "latest"
    global_multi_asset_batch1_base = REPO_ROOT / "evidence" / "multi_asset_lab" / "fast_exploration_batch1" / "latest"
    combination_batch1_base = REPO_ROOT / "evidence" / "combination_lab" / "latest"
    combination_batch1_verdict_audit_base = REPO_ROOT / "evidence" / "combination_lab" / "batch1_verdict_audit" / "latest"
    combination_batch1_diagnostics_completion_base = REPO_ROOT / "evidence" / "combination_lab" / "batch1_diagnostics_completion" / "latest"
    rankings = safe_read_csv(challenge_base / "strategy_rankings.csv")
    challenge_results = safe_read_csv(challenge_base / "challenge_results.csv")
    rolling = safe_read_csv(challenge_base / "rolling_window_summary.csv")
    paper = safe_read_csv(paper_base / "paper_forward_status.csv")
    profit_rankings = safe_read_csv(profit_base / "profit_rankings.csv")
    profit_results = safe_read_csv(profit_base / "profit_exploration_results.csv")
    candidate_queue = safe_read_csv(candidate_base / "candidate_queue_matrix.csv")
    promotion_manifest = safe_read_json(promotion_base / "promotion_review_manifest.json") or {}
    generic_promotion_review_manifest = safe_read_json(generic_promotion_review_base / "promotion_review_manifest.json") or {}
    combo_observation_plan_manifest = safe_read_json(combo_observation_plan_base / "observation_plan_manifest.json") or {}
    combo_observation_activation_manifest = safe_read_json(combo_observation_activation_base / "observation_activation_manifest.json") or {}
    combo_rule_hash_manifest = safe_read_json(combo_rule_hash_base / "rule_hash_review_manifest.json") or {}
    implementation_manifest = safe_read_json(implementation_base / "implementation_review_manifest.json") or {}
    value_implementation_manifest = safe_read_json(value_implementation_base / "implementation_review_manifest.json") or {}
    sector_implementation_manifest = safe_read_json(sector_implementation_base / "implementation_review_manifest.json") or {}
    managed_futures_implementation_manifest = safe_read_json(managed_futures_implementation_base / "implementation_review_manifest.json") or {}
    value_data_acquisition_manifest = safe_read_json(value_data_acquisition_base / "data_acquisition_manifest.json") or {}
    managed_futures_data_acquisition_manifest = safe_read_json(managed_futures_data_acquisition_base / "data_acquisition_manifest.json") or {}
    value_provider_terms_manifest = safe_read_json(value_provider_terms_base / "provider_terms_review_manifest.json") or {}
    managed_futures_provider_terms_manifest = safe_read_json(managed_futures_provider_terms_base / "provider_terms_review_manifest.json") or {}
    value_data_acquisition_run_manifest = safe_read_json(value_data_acquisition_run_base / "acquisition_manifest.json") or {}
    managed_futures_data_acquisition_run_manifest = safe_read_json(managed_futures_data_acquisition_run_base / "acquisition_manifest.json") or {}
    paper_forward_cache_update_manifest = safe_read_json(paper_forward_cache_update_base / "cache_update_manifest.json") or {}
    managed_futures_methodology_manifest = safe_read_json(managed_futures_methodology_base / "methodology_review_manifest.json") or {}
    candidate_triage_manifest = safe_read_json(candidate_triage_base / "candidate_triage_manifest.json") or {}
    historical_research_manifest = safe_read_json(historical_research_base / "historical_research_manifest.json") or {}
    research_state_manifest = safe_read_json(research_state_base / "research_state_manifest.json") or {}
    research_diagnostics_manifest = safe_read_json(research_diagnostics_base / "research_diagnostics_manifest.json") or {}
    active_combo_manifest = safe_read_json(active_combo_base / "active_combo_manifest.json") or {}
    individual_stock_gate1b_manifest = safe_read_json(individual_stock_gate1b_base / "gate1b_manifest.json") or {}
    individual_stock_gate1c_manifest = safe_read_json(individual_stock_gate1c_base / "gate1c_manifest.json") or {}
    individual_stock_gate1d_manifest = safe_read_json(individual_stock_gate1d_base / "gate1d_manifest.json") or {}
    individual_stock_gate1e_manifest = safe_read_json(individual_stock_gate1e_base / "gate1e_manifest.json") or {}
    individual_stock_gate1f_manifest = safe_read_json(individual_stock_gate1f_base / "gate1f_manifest.json") or {}
    queue_reprioritization_manifest = safe_read_json(queue_reprioritization_base / "queue_reprioritization_manifest.json") or {}
    commodity_review_manifest = safe_read_json(commodity_review_base / "commodity_review_manifest.json") or {}
    commodity_data_acquisition_manifest = safe_read_json(commodity_data_acquisition_base / "commodity_data_acquisition_manifest.json") or {}
    commodity_fast_acquisition_manifest = safe_read_json(commodity_fast_acquisition_base / "acquisition_manifest.json") or {}
    commodity_exploratory_manifest = safe_read_json(commodity_exploratory_base / "commodity_exploratory_manifest.json") or {}
    commodity_risk_control_manifest = safe_read_json(commodity_risk_control_base / "risk_control_batch1_manifest.json") or {}
    commodity_risk_control_verdict_audit_manifest = safe_read_json(
        commodity_risk_control_verdict_audit_base / "risk_control_batch1_verdict_audit_manifest.json"
    ) or {}
    commodity_risk_control_diagnostics_completion_manifest = safe_read_json(
        commodity_risk_control_diagnostics_completion_base / "risk_control_batch1_diagnostics_completion_manifest.json"
    ) or {}
    crypto_fast_acquisition_manifest = safe_read_json(crypto_fast_acquisition_base / "acquisition_manifest.json") or {}
    crypto_tier2_risk_control_manifest = safe_read_json(crypto_tier2_risk_control_base / "tier2_risk_control_batch1_manifest.json") or {}
    global_multi_asset_fast_acquisition_manifest = safe_read_json(global_multi_asset_fast_acquisition_base / "acquisition_manifest.json") or {}
    global_multi_asset_batch1_manifest = safe_read_json(global_multi_asset_batch1_base / "fast_exploration_batch1_manifest.json") or {}
    combination_batch1_manifest = safe_read_json(combination_batch1_base / "combination_batch1_manifest.json") or {}
    combination_batch1_verdict_audit_manifest = safe_read_json(
        combination_batch1_verdict_audit_base / "batch1_verdict_audit_manifest.json"
    ) or {}
    combination_batch1_diagnostics_completion_manifest = safe_read_json(
        combination_batch1_diagnostics_completion_base / "batch1_diagnostics_completion_manifest.json"
    ) or {}
    registry = safe_read_csv(REPO_ROOT / "evidence" / "strategy_lab" / "latest" / "strategy_registry_snapshot.csv")
    exploratory_rankings = safe_read_csv(family_exploratory / "strategy_rankings.csv")
    consistency_report = build_consistency_report(include_advisor_zip_texts=False)
    consistency_status = consistency_report.get("consistency_status", "unknown")
    consistency_errors = consistency_report.get("errors", [])
    consistency_warnings = consistency_report.get("warnings", [])
    contradictions_text = (
        "; ".join(f"{item.get('rule_id')}: {item.get('message')}" for item in consistency_errors[:5])
        if consistency_errors
        else "; ".join(f"{item.get('rule_id')}: {item.get('message')}" for item in consistency_warnings[:5])
        if consistency_warnings
        else "none detected"
    )
    finality_clear = bool(
        consistency_report.get("run_level_finality_false_detected")
        and consistency_report.get("row_level_exact_evidence_present")
        and not any(item.get("rule_id") == "run_level_vs_row_level_finality" for item in consistency_errors)
    )

    completed_family = rankings[
        rankings.get("lane", pd.Series(dtype=str)).astype(str).eq("independent_family_challenge")
        & rankings.get("run_status", pd.Series(dtype=str)).astype(str).eq("completed")
    ] if not rankings.empty else pd.DataFrame()
    best_exact = completed_family.iloc[0].to_dict() if not completed_family.empty else {}
    exploratory_family = exploratory_rankings[
        exploratory_rankings.get("credibility_tier", pd.Series(dtype=str)).astype(str).eq("tier1_exploratory")
    ] if not exploratory_rankings.empty else pd.DataFrame()
    best_exploratory = exploratory_family.sort_values("pct_90d_target_300_before_stop", ascending=False).iloc[0].to_dict() if not exploratory_family.empty and "pct_90d_target_300_before_stop" in exploratory_family else {}
    profit_integrity_status = "unavailable"
    profit_decision_usable = False
    if not profit_rankings.empty and "accounting_integrity_status" in profit_rankings:
        completed_profit = profit_rankings[profit_rankings.get("run_status", pd.Series(dtype=str)).astype(str).eq("completed")]
        profit_integrity_status = "passed" if not completed_profit.empty and completed_profit["accounting_integrity_status"].astype(str).eq("passed").all() else "failed"
        profit_decision_usable = bool(
            not completed_profit.empty
            and completed_profit.get("profit_results_usable", pd.Series(dtype=bool)).astype(str).str.lower().isin(["true", "1"]).all()
            and profit_integrity_status == "passed"
        )
    if not profit_rankings.empty and "profit_results_usable" in profit_rankings:
        usable_mask = profit_rankings["profit_results_usable"].astype(str).str.lower().isin(["true", "1"])
        best_profit_frame = profit_rankings[usable_mask]
    else:
        best_profit_frame = pd.DataFrame()
    best_profit_sort = "rank_balanced_drawdown_aware_v2" if "rank_balanced_drawdown_aware_v2" in best_profit_frame else "rank_overall"
    best_profit = best_profit_frame.sort_values(best_profit_sort).iloc[0].to_dict() if not best_profit_frame.empty and best_profit_sort in best_profit_frame else {}
    best_profit_verdict_field = "practical_verdict_v2" if "practical_verdict_v2" in best_profit else "profit_verdict"
    candidate_queue_exists = candidate_base.exists() and not candidate_queue.empty
    promotion_review_exists = promotion_base.exists()
    generic_promotion_review_exists = (generic_promotion_review_base / "promotion_review_manifest.json").exists()
    combo_observation_plan_exists = (combo_observation_plan_base / "observation_plan_manifest.json").exists()
    combo_observation_activation_exists = (combo_observation_activation_base / "observation_activation_manifest.json").exists()
    combo_rule_hash_exists = (combo_rule_hash_base / "rule_hash_review_manifest.json").exists()
    implementation_review_exists = implementation_base.exists()
    value_implementation_review_exists = value_implementation_base.exists()
    sector_implementation_review_exists = sector_implementation_base.exists()
    managed_futures_implementation_review_exists = managed_futures_implementation_base.exists()
    value_data_acquisition_review_exists = value_data_acquisition_base.exists()
    managed_futures_data_acquisition_review_exists = managed_futures_data_acquisition_base.exists()
    value_provider_terms_review_exists = value_provider_terms_base.exists()
    managed_futures_provider_terms_review_exists = managed_futures_provider_terms_base.exists()
    value_data_acquisition_run_exists = (value_data_acquisition_run_base / "acquisition_manifest.json").exists()
    managed_futures_data_acquisition_run_exists = (managed_futures_data_acquisition_run_base / "acquisition_manifest.json").exists()
    paper_forward_cache_update_exists = (paper_forward_cache_update_base / "cache_update_manifest.json").exists()
    managed_futures_methodology_review_exists = (managed_futures_methodology_base / "methodology_review_manifest.json").exists()
    candidate_triage_exists = (candidate_triage_base / "candidate_triage_manifest.json").exists()
    historical_research_exists = (historical_research_base / "historical_research_manifest.json").exists()
    research_state_exists = (research_state_base / "research_state_manifest.json").exists()
    research_diagnostics_exists = (research_diagnostics_base / "research_diagnostics_manifest.json").exists()
    individual_stock_gate1b_exists = (individual_stock_gate1b_base / "gate1b_manifest.json").exists()
    individual_stock_gate1c_exists = (individual_stock_gate1c_base / "gate1c_manifest.json").exists()
    individual_stock_gate1d_exists = (individual_stock_gate1d_base / "gate1d_manifest.json").exists()
    individual_stock_gate1e_exists = (individual_stock_gate1e_base / "gate1e_manifest.json").exists()
    individual_stock_gate1f_exists = (individual_stock_gate1f_base / "gate1f_manifest.json").exists()
    queue_reprioritization_exists = (queue_reprioritization_base / "queue_reprioritization_manifest.json").exists()
    commodity_review_exists = (commodity_review_base / "commodity_review_manifest.json").exists()
    commodity_data_acquisition_exists = (commodity_data_acquisition_base / "commodity_data_acquisition_manifest.json").exists()
    commodity_fast_acquisition_exists = (commodity_fast_acquisition_base / "acquisition_manifest.json").exists()
    commodity_exploratory_exists = (commodity_exploratory_base / "commodity_exploratory_manifest.json").exists()
    commodity_risk_control_exists = (commodity_risk_control_base / "risk_control_batch1_manifest.json").exists()
    commodity_risk_control_verdict_audit_exists = (
        commodity_risk_control_verdict_audit_base / "risk_control_batch1_verdict_audit_manifest.json"
    ).exists()
    commodity_risk_control_diagnostics_completion_exists = (
        commodity_risk_control_diagnostics_completion_base / "risk_control_batch1_diagnostics_completion_manifest.json"
    ).exists()
    crypto_fast_acquisition_exists = (crypto_fast_acquisition_base / "acquisition_manifest.json").exists()
    crypto_tier2_risk_control_exists = (crypto_tier2_risk_control_base / "tier2_risk_control_batch1_manifest.json").exists()
    global_multi_asset_fast_acquisition_exists = (global_multi_asset_fast_acquisition_base / "acquisition_manifest.json").exists()
    global_multi_asset_batch1_exists = (global_multi_asset_batch1_base / "fast_exploration_batch1_manifest.json").exists()
    combination_batch1_exists = (combination_batch1_base / "combination_batch1_manifest.json").exists()
    combination_batch1_verdict_audit_exists = (
        combination_batch1_verdict_audit_base / "batch1_verdict_audit_manifest.json"
    ).exists()
    combination_batch1_diagnostics_completion_exists = (
        combination_batch1_diagnostics_completion_base / "batch1_diagnostics_completion_manifest.json"
    ).exists()
    promotion_decision = promotion_manifest.get("decision", "unavailable" if not promotion_review_exists else "missing_manifest")
    generic_promotion_review_decision = (
        f"candidate_exhaustive_queue_count={generic_promotion_review_manifest.get('candidate_exhaustive_queue_count', 'unavailable')}"
        if generic_promotion_review_exists
        else "unavailable"
    )
    combo_observation_plan_decision = combo_observation_plan_manifest.get("decision", "unavailable" if not combo_observation_plan_exists else "missing_manifest")
    combo_observation_activation_status = combo_observation_activation_manifest.get("activation_status", "unavailable" if not combo_observation_activation_exists else "missing_manifest")
    combo_rule_hash_decision = combo_rule_hash_manifest.get("decision", "unavailable" if not combo_rule_hash_exists else "missing_manifest")
    implementation_decision = implementation_manifest.get("decision", "unavailable" if not implementation_review_exists else "missing_manifest")
    value_implementation_decision = value_implementation_manifest.get("decision", "unavailable" if not value_implementation_review_exists else "missing_manifest")
    sector_implementation_decision = sector_implementation_manifest.get("decision", "unavailable" if not sector_implementation_review_exists else "missing_manifest")
    managed_futures_implementation_decision = managed_futures_implementation_manifest.get("decision", "unavailable" if not managed_futures_implementation_review_exists else "missing_manifest")
    value_data_acquisition_decision = value_data_acquisition_manifest.get("decision", "unavailable" if not value_data_acquisition_review_exists else "missing_manifest")
    managed_futures_data_acquisition_decision = managed_futures_data_acquisition_manifest.get("decision", "unavailable" if not managed_futures_data_acquisition_review_exists else "missing_manifest")
    value_provider_terms_decision = value_provider_terms_manifest.get("decision", "unavailable" if not value_provider_terms_review_exists else "missing_manifest")
    managed_futures_provider_terms_decision = managed_futures_provider_terms_manifest.get("decision", "unavailable" if not managed_futures_provider_terms_review_exists else "missing_manifest")
    value_data_acquisition_run_status = value_data_acquisition_run_manifest.get("strategy_lab_status", "unavailable" if not value_data_acquisition_run_exists else "missing_manifest")
    managed_futures_data_acquisition_run_status = managed_futures_data_acquisition_run_manifest.get("strategy_lab_status", "unavailable" if not managed_futures_data_acquisition_run_exists else "missing_manifest")
    paper_forward_cache_update_status = (
        "activation_date_supported"
        if paper_forward_cache_update_manifest.get("requested_activation_date_supported") is True
        else "activation_date_not_supported"
        if paper_forward_cache_update_exists
        else "unavailable"
    )
    managed_futures_methodology_decision = managed_futures_methodology_manifest.get("decision", "unavailable" if not managed_futures_methodology_review_exists else "missing_manifest")
    candidate_triage_decision = candidate_triage_manifest.get("decision", "unavailable" if not candidate_triage_exists else "missing_manifest")
    historical_research_phase = historical_research_manifest.get("current_phase", "unavailable" if not historical_research_exists else "missing_manifest")
    research_state_phase = research_state_manifest.get("current_phase", "unavailable" if not research_state_exists else "missing_manifest")
    research_diagnostics_status = (
        "attribution_diagnostics_available"
        if research_diagnostics_manifest.get("attribution_diagnostics_available") is True
        else "unavailable"
        if not research_diagnostics_exists
        else "missing_or_disabled"
    )
    individual_stock_gate1b_decision = individual_stock_gate1b_manifest.get(
        "decision",
        "unavailable" if not individual_stock_gate1b_exists else "missing_manifest",
    )
    individual_stock_gate1c_decision = individual_stock_gate1c_manifest.get(
        "decision",
        "unavailable" if not individual_stock_gate1c_exists else "missing_manifest",
    )
    individual_stock_gate1d_decision = individual_stock_gate1d_manifest.get(
        "decision",
        "unavailable" if not individual_stock_gate1d_exists else "missing_manifest",
    )
    individual_stock_gate1e_decision = individual_stock_gate1e_manifest.get(
        "decision",
        "unavailable" if not individual_stock_gate1e_exists else "missing_manifest",
    )
    individual_stock_gate1f_decision = individual_stock_gate1f_manifest.get(
        "decision",
        "unavailable" if not individual_stock_gate1f_exists else "missing_manifest",
    )
    queue_reprioritization_decision = queue_reprioritization_manifest.get(
        "decision",
        "unavailable" if not queue_reprioritization_exists else "missing_manifest",
    )
    commodity_review_decision = commodity_review_manifest.get(
        "decision",
        "unavailable" if not commodity_review_exists else "missing_manifest",
    )
    commodity_data_acquisition_decision = commodity_data_acquisition_manifest.get(
        "decision",
        "unavailable" if not commodity_data_acquisition_exists else "missing_manifest",
    )
    commodity_fast_acquisition_status = commodity_fast_acquisition_manifest.get(
        "quality_counts",
        "unavailable" if not commodity_fast_acquisition_exists else "missing_manifest",
    )
    commodity_exploratory_decision = commodity_exploratory_manifest.get(
        "verdict",
        "unavailable" if not commodity_exploratory_exists else "missing_manifest",
    )
    commodity_risk_control_decision = (
        "candidate_exhaustive_review_recommended"
        if commodity_risk_control_manifest.get("candidate_exhaustive_recommended") is True
        else "no_candidate_exhaustive_review"
        if commodity_risk_control_exists
        else "unavailable"
    )
    commodity_risk_control_verdict_audit_decision = commodity_risk_control_verdict_audit_manifest.get(
        "candidate_exhaustive_decision",
        "unavailable" if not commodity_risk_control_verdict_audit_exists else "missing_manifest",
    )
    commodity_risk_control_diagnostics_completion_decision = commodity_risk_control_diagnostics_completion_manifest.get(
        "decision",
        "unavailable" if not commodity_risk_control_diagnostics_completion_exists else "missing_manifest",
    )
    crypto_fast_acquisition_status = (
        "cache_confirmed_no_download"
        if crypto_fast_acquisition_exists and not crypto_fast_acquisition_manifest.get("data_downloaded", False)
        else "downloaded"
        if crypto_fast_acquisition_exists
        else "unavailable"
    )
    crypto_tier2_risk_control_decision = (
        "candidate_exhaustive_review_required"
        if crypto_tier2_risk_control_manifest.get("candidate_exhaustive_recommended") is True
        else "no_candidate_exhaustive_review"
        if crypto_tier2_risk_control_exists
        else "unavailable"
    )
    global_multi_asset_fast_acquisition_status = (
        "downloaded_missing_approved_symbols"
        if global_multi_asset_fast_acquisition_exists and global_multi_asset_fast_acquisition_manifest.get("data_downloaded", False)
        else "cache_confirmed_no_download"
        if global_multi_asset_fast_acquisition_exists
        else "unavailable"
    )
    global_multi_asset_batch1_decision = (
        "candidate_exhaustive_review_required"
        if global_multi_asset_batch1_manifest.get("candidate_exhaustive_recommended") is True
        else "no_candidate_exhaustive_review"
        if global_multi_asset_batch1_exists
        else "unavailable"
    )
    combination_batch1_decision = combination_batch1_manifest.get("overall_verdict", "unavailable" if not combination_batch1_exists else "missing_manifest")
    combination_batch1_verdict_audit_decision = combination_batch1_verdict_audit_manifest.get(
        "verdict_audit_decision",
        "unavailable" if not combination_batch1_verdict_audit_exists else "missing_manifest",
    )
    combination_batch1_diagnostics_completion_decision = combination_batch1_diagnostics_completion_manifest.get(
        "diagnostics_completion_decision",
        "unavailable" if not combination_batch1_diagnostics_completion_exists else "missing_manifest",
    )
    implementation_review_candidates = []
    data_gated_candidates = []
    rejected_candidates = []
    if candidate_queue_exists:
        implementation_review_candidates = candidate_queue[
            candidate_queue.get("recommended_next_action", pd.Series(dtype=str)).astype(str).isin([
                "evaluate_after_current_finalists",
                "symbol_availability_and_proxy_review",
                "exact_stream_or_clean_implementation_review",
            ])
        ].get("candidate_id", pd.Series(dtype=str)).astype(str).head(5).tolist()
        data_gated_candidates = candidate_queue[
            candidate_queue.get("current_status", pd.Series(dtype=str)).astype(str).eq("data_gated")
        ].get("candidate_id", pd.Series(dtype=str)).astype(str).tolist()
        rejected_candidates = candidate_queue[
            candidate_queue.get("current_status", pd.Series(dtype=str)).astype(str).isin(["reject_for_now", "defer", "complexity_gated", "execution_gated"])
        ].get("candidate_id", pd.Series(dtype=str)).astype(str).tolist()

    incomplete = challenge_results[
        challenge_results.get("run_status", pd.Series(dtype=str)).astype(str).eq("incomplete_evidence")
    ] if not challenge_results.empty else pd.DataFrame()
    blocked = challenge_results[
        challenge_results.get("run_status", pd.Series(dtype=str)).astype(str).eq("blocked_by_gate")
    ] if not challenge_results.empty else pd.DataFrame()

    executive = f"""
    # Advisor Executive State

    Created: {created}

    Boundary: research-only paper/demo evidence. No real-money recommendation, broker integration, live orders, order placement, or AI trading gate.

    Main goal: determine whether independent simulated $3,000 challenge accounts can reach +$300 or +$400 before a -$600 / -20% stop, while preserving evidence tier separation.

    Active paper-forward candidate: SPY_200d_trend_model, with frozen rules.

    Best exact family: {best_exact.get('family_id', 'unavailable')} / {best_exact.get('strategy', 'unavailable')}.

    Best exploratory family: {best_exploratory.get('family_id', 'none included')} / {best_exploratory.get('strategy', 'none included')}; exploratory evidence is non-final and Tier 1 only.

    Profit exploration accounting integrity: {profit_integrity_status}. Profit exploration decision-usable: {profit_decision_usable}.

    Best profit exploration tradeoff: {best_profit.get('experiment_id', 'unavailable' if profit_decision_usable else 'not decision-usable')} / {best_profit.get(best_profit_verdict_field, 'blocked_by_integrity' if not profit_decision_usable else 'unavailable')}.

    Strategy candidate queue exists: {candidate_queue_exists}.

    Highest priority queued candidates: {', '.join(implementation_review_candidates) or 'none'}.

    Data-gated queued candidates: {', '.join(data_gated_candidates) or 'none'}.

    Rejected/deferred queued candidates: {', '.join(rejected_candidates) or 'none'}.

    Combo promotion review packet: {rel(promotion_base) if promotion_review_exists else 'unavailable'}; decision: {promotion_decision}.

    Generic promotion review packet: {rel(generic_promotion_review_base) if generic_promotion_review_exists else 'unavailable'}; decision: {generic_promotion_review_decision}; candidate_exhaustive run: {generic_promotion_review_manifest.get('candidate_exhaustive_run', False)}.

    Combo paper-forward observation plan packet: {rel(combo_observation_plan_base) if combo_observation_plan_exists else 'unavailable'}; decision: {combo_observation_plan_decision}.

    Combo paper-forward observation activation packet: {rel(combo_observation_activation_base) if combo_observation_activation_exists else 'unavailable'}; status: {combo_observation_activation_status}.

    Combo rule-hash resolution packet: {rel(combo_rule_hash_base) if combo_rule_hash_exists else 'unavailable'}; decision: {combo_rule_hash_decision}.

    QQQ implementation review packet: {rel(implementation_base) if implementation_review_exists else 'unavailable'}; decision: {implementation_decision}.

    Value/momentum factor ETF implementation review packet: {rel(value_implementation_base) if value_implementation_review_exists else 'unavailable'}; decision: {value_implementation_decision}.

    Sector top2 ETF implementation review packet: {rel(sector_implementation_base) if sector_implementation_review_exists else 'unavailable'}; decision: {sector_implementation_decision}.

    Managed-futures proxy implementation review packet: {rel(managed_futures_implementation_base) if managed_futures_implementation_review_exists else 'unavailable'}; decision: {managed_futures_implementation_decision}.

    Value/momentum factor ETF data acquisition review packet: {rel(value_data_acquisition_base) if value_data_acquisition_review_exists else 'unavailable'}; decision: {value_data_acquisition_decision}.

    Managed-futures proxy data acquisition review packet: {rel(managed_futures_data_acquisition_base) if managed_futures_data_acquisition_review_exists else 'unavailable'}; decision: {managed_futures_data_acquisition_decision}.

    Value/momentum factor ETF provider terms/security review packet: {rel(value_provider_terms_base) if value_provider_terms_review_exists else 'unavailable'}; decision: {value_provider_terms_decision}.

    Managed-futures proxy provider terms/security review packet: {rel(managed_futures_provider_terms_base) if managed_futures_provider_terms_review_exists else 'unavailable'}; decision: {managed_futures_provider_terms_decision}.

    Value/momentum factor ETF data acquisition run packet: {rel(value_data_acquisition_run_base) if value_data_acquisition_run_exists else 'unavailable'}; status: {value_data_acquisition_run_status}.

    Managed-futures proxy data acquisition run packet: {rel(managed_futures_data_acquisition_run_base) if managed_futures_data_acquisition_run_exists else 'unavailable'}; status: {managed_futures_data_acquisition_run_status}.

    Managed-futures proxy methodology review packet: {rel(managed_futures_methodology_base) if managed_futures_methodology_review_exists else 'unavailable'}; decision: {managed_futures_methodology_decision}.

    Candidate testing triage packet: {rel(candidate_triage_base) if candidate_triage_exists else 'unavailable'}; decision: {candidate_triage_decision}.

    Historical research expansion packet: {rel(historical_research_base) if historical_research_exists else 'unavailable'}; phase: {historical_research_phase}.

    Current-state research dashboard: {rel(research_state_base) if research_state_exists else 'unavailable'}; phase: {research_state_phase}.

    Historical attribution diagnostics packet: {rel(research_diagnostics_base) if research_diagnostics_exists else 'unavailable'}; status: {research_diagnostics_status}.

    Individual stock momentum Gate 1B packet: {rel(individual_stock_gate1b_base) if individual_stock_gate1b_exists else 'unavailable'}; decision: {individual_stock_gate1b_decision}.

    Individual stock momentum Gate 1C packet: {rel(individual_stock_gate1c_base) if individual_stock_gate1c_exists else 'unavailable'}; decision: {individual_stock_gate1c_decision}.

    Individual stock momentum Gate 1D packet: {rel(individual_stock_gate1d_base) if individual_stock_gate1d_exists else 'unavailable'}; decision: {individual_stock_gate1d_decision}.

    Individual stock momentum Gate 1E packet: {rel(individual_stock_gate1e_base) if individual_stock_gate1e_exists else 'unavailable'}; decision: {individual_stock_gate1e_decision}.

    Individual stock momentum Gate 1F Sharadar fallback packet: {rel(individual_stock_gate1f_base) if individual_stock_gate1f_exists else 'unavailable'}; decision: {individual_stock_gate1f_decision}.

    Historical research queue reprioritization packet: {rel(queue_reprioritization_base) if queue_reprioritization_exists else 'unavailable'}; decision: {queue_reprioritization_decision}; next family: {queue_reprioritization_manifest.get('next_family', 'unavailable')}; next action: {queue_reprioritization_manifest.get('next_allowed_action', 'unavailable')}.

    Commodity basket ETF product/data review packet: {rel(commodity_review_base) if commodity_review_exists else 'unavailable'}; decision: {commodity_review_decision}; products: {', '.join(commodity_review_manifest.get('products_reviewed', [])) if isinstance(commodity_review_manifest.get('products_reviewed', []), list) else 'unavailable'}; next action: {commodity_review_manifest.get('next_allowed_action', 'unavailable')}.

    Commodity basket ETF data acquisition review packet: {rel(commodity_data_acquisition_base) if commodity_data_acquisition_exists else 'unavailable'}; decision: {commodity_data_acquisition_decision}; future download symbols approved: {', '.join(commodity_data_acquisition_manifest.get('future_download_symbols_approved', [])) if isinstance(commodity_data_acquisition_manifest.get('future_download_symbols_approved', []), list) else 'unavailable'}; next action: {commodity_data_acquisition_manifest.get('next_allowed_action', 'unavailable')}.

    Fast commodity exploratory acquisition packet: {rel(commodity_fast_acquisition_base) if commodity_fast_acquisition_exists else 'unavailable'}; downloaded symbols: {', '.join(commodity_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(commodity_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}; failed symbols: {', '.join(commodity_fast_acquisition_manifest.get('failed_symbols', [])) if isinstance(commodity_fast_acquisition_manifest.get('failed_symbols', []), list) else 'unavailable'}; raw OHLCV in advisor packet: {commodity_fast_acquisition_manifest.get('raw_ohlcv_included', False)}.

    Commodity basket exploratory screen packet: {rel(commodity_exploratory_base) if commodity_exploratory_exists else 'unavailable'}; verdict: {commodity_exploratory_decision}; candidate_exhaustive run: {commodity_exploratory_manifest.get('candidate_exhaustive_run', False)}.

    Commodity Risk-Control Batch 1 packet: {rel(commodity_risk_control_base) if commodity_risk_control_exists else 'unavailable'}; decision: {commodity_risk_control_decision}; best candidate: {commodity_risk_control_manifest.get('best_risk_control_candidate', 'unavailable')}; candidate_exhaustive run: {commodity_risk_control_manifest.get('candidate_exhaustive_run', False)}.

    Commodity Risk-Control Batch 1 verdict audit packet: {rel(commodity_risk_control_verdict_audit_base) if commodity_risk_control_verdict_audit_exists else 'unavailable'}; decision: {commodity_risk_control_verdict_audit_decision}; candidate_exhaustive run: {commodity_risk_control_verdict_audit_manifest.get('candidate_exhaustive_run', False)}.

    Commodity Risk-Control Batch 1 diagnostics completion packet: {rel(commodity_risk_control_diagnostics_completion_base) if commodity_risk_control_diagnostics_completion_exists else 'unavailable'}; decision: {commodity_risk_control_diagnostics_completion_decision}; candidate_exhaustive recommended: {commodity_risk_control_diagnostics_completion_manifest.get('candidate_exhaustive_review_recommended', False)}; candidate_exhaustive run: {commodity_risk_control_diagnostics_completion_manifest.get('candidate_exhaustive_run', False)}.

    Crypto spot fast acquisition/cache packet: {rel(crypto_fast_acquisition_base) if crypto_fast_acquisition_exists else 'unavailable'}; status: {crypto_fast_acquisition_status}; cache-confirmed symbols: {', '.join(crypto_fast_acquisition_manifest.get('cache_confirmed_symbols', [])) if isinstance(crypto_fast_acquisition_manifest.get('cache_confirmed_symbols', []), list) else 'unavailable'}; downloaded symbols: {', '.join(crypto_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(crypto_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}; raw OHLCV in advisor packet: {crypto_fast_acquisition_manifest.get('raw_ohlcv_in_evidence', False)}.

    Crypto Spot Tier 2 Risk-Control Batch 1 packet: {rel(crypto_tier2_risk_control_base) if crypto_tier2_risk_control_exists else 'unavailable'}; decision: {crypto_tier2_risk_control_decision}; best candidate: {crypto_tier2_risk_control_manifest.get('best_risk_control_candidate', 'unavailable')}; candidate_exhaustive run: {crypto_tier2_risk_control_manifest.get('candidate_exhaustive_run', False)}.

    Global multi-asset fast acquisition packet: {rel(global_multi_asset_fast_acquisition_base) if global_multi_asset_fast_acquisition_exists else 'unavailable'}; status: {global_multi_asset_fast_acquisition_status}; cache-confirmed symbols: {', '.join(global_multi_asset_fast_acquisition_manifest.get('cache_confirmed_symbols', [])) if isinstance(global_multi_asset_fast_acquisition_manifest.get('cache_confirmed_symbols', []), list) else 'unavailable'}; downloaded symbols: {', '.join(global_multi_asset_fast_acquisition_manifest.get('downloaded_symbols', [])) if isinstance(global_multi_asset_fast_acquisition_manifest.get('downloaded_symbols', []), list) else 'unavailable'}; raw OHLCV in advisor packet: {global_multi_asset_fast_acquisition_manifest.get('raw_ohlcv_included', False)}.

    Global Multi-Asset ETF Fast Exploration Batch 1 packet: {rel(global_multi_asset_batch1_base) if global_multi_asset_batch1_exists else 'unavailable'}; decision: {global_multi_asset_batch1_decision}; best candidate: {global_multi_asset_batch1_manifest.get('best_multi_asset_candidate', 'unavailable')}; candidate_exhaustive run: {global_multi_asset_batch1_manifest.get('candidate_exhaustive_run', False)}.

    Historical Combination Batch 1 packet: {rel(combination_batch1_base) if combination_batch1_exists else 'unavailable'}; verdict: {combination_batch1_decision}.
    Historical Combination Batch 1 verdict audit: {rel(combination_batch1_verdict_audit_base) if combination_batch1_verdict_audit_exists else 'unavailable'}; verdict: {combination_batch1_verdict_audit_decision}.
    Historical Combination Batch 1 diagnostics completion: {rel(combination_batch1_diagnostics_completion_base) if combination_batch1_diagnostics_completion_exists else 'unavailable'}; decision: {combination_batch1_diagnostics_completion_decision}.

    Current phase correction: active paper/demo observation does not freeze historical research; forward checkpoint timing only blocks forward-observation judgment.

    Blocked families: {', '.join(blocked.get('family_id', pd.Series(dtype=str)).dropna().astype(str).unique().tolist()) or 'none reported'}.

    Incomplete families: {', '.join(incomplete.get('family_id', pd.Series(dtype=str)).dropna().astype(str).unique().tolist()) or 'none reported'}.

    consistency_status: {consistency_status}

    Current known contradictions: {contradictions_text}.

    Challenge summary internally consistent: {not bool(consistency_errors)}.

    Run-level and row-level finality clearly separated: {finality_clear}.

    Biggest evidence issue: A_ETF_sector_momentum and current_no_cash_proxy_alpha_AB are not accepted as completed independent-family rows unless a fresh-window exact rolling stream is exposed.

    Recommended next decision: create a combination-design implementation review or improve diagnostics; do not tune the active combo or replace SPY_200d.
    """

    decision_rows = [
        {
            "decision_area": "primary_family_candidate",
            "current_status": f"{best_exact.get('strategy', 'SPY_200d_trend_model')} leads exact family tradeoff",
            "evidence_source": "01_CHALLENGE_AND_FAMILY_AUDIT.zip",
            "confidence_level": "exact ETF family evidence",
            "next_action": "continue paper-forward observation discipline",
            "blocker": "",
        },
        {
            "decision_area": "profit_exploration",
            "current_status": f"{best_profit.get('experiment_id', 'unavailable')} leads profit/risk score" if best_profit else "not available",
            "evidence_source": "07_PROFIT_EXPLORATION.zip" if profit_base.exists() else "",
            "confidence_level": best_profit.get("evidence_tier", "unavailable"),
            "next_action": "candidate_exhaustive_or_tier_review_if_promising",
            "blocker": "profit exploration accounting integrity failed" if not profit_decision_usable and profit_base.exists() else "profit exploration is not paper-forward and is not a real-money recommendation",
        },
        {
            "decision_area": "A_AB_family_completion",
            "current_status": "incomplete_evidence",
            "evidence_source": "01_CHALLENGE_AND_FAMILY_AUDIT.zip",
            "confidence_level": "blocked from ranking",
            "next_action": "expose exact fresh-window rolling stream only if possible",
            "blocker": "no compact accepted daily rolling stream",
        },
        {
            "decision_area": "exploratory_crypto",
            "current_status": "Tier 1 exploratory only",
            "evidence_source": "05_EXPLORATORY_LANES.zip",
            "confidence_level": "non-final",
            "next_action": "do not promote without separate gate evidence",
            "blocker": "execution/data/risk modeling limitations",
        },
        {
            "decision_area": "blocked_families",
            "current_status": "reported but not run",
            "evidence_source": "04_RESEARCH_DIRECTION_AND_GATES.zip",
            "confidence_level": "gate-level",
            "next_action": "gate review only",
            "blocker": "data/execution/risk models missing",
        },
        {
            "decision_area": "strategy_candidate_queue",
            "current_status": "queue exists" if candidate_queue_exists else "not available",
            "evidence_source": "08_STRATEGY_CANDIDATE_QUEUE.zip" if candidate_queue_exists else "",
            "confidence_level": "queue_only_not_implemented",
            "next_action": "review gates after current finalist validation",
            "blocker": "all candidates implementation_allowed_now=false",
        },
        {
            "decision_area": "generic_promotion_review",
            "current_status": str(generic_promotion_review_decision),
            "evidence_source": rel(generic_promotion_review_base) if generic_promotion_review_exists else "",
            "confidence_level": "promotion_review_only_no_execution",
            "next_action": "run candidate_exhaustive only from explicit future prompt if queued",
            "blocker": "does not activate paper-forward, run candidate_exhaustive, or make real-money recommendation",
        },
        {
            "decision_area": "historical_research_expansion",
            "current_status": str(historical_research_phase),
            "evidence_source": rel(historical_research_base) if historical_research_exists else "",
            "confidence_level": "governance_phase_decision",
            "next_action": "combination_design_review_or_diagnostics_improvement",
            "blocker": "forward checkpoint not ready for judgment; historical research still allowed in parallel",
        },
    ]
    if queue_reprioritization_exists:
        decision_rows.append(
            {
                "decision_area": "historical_research_queue_reprioritization",
                "current_status": str(queue_reprioritization_decision),
                "evidence_source": rel(queue_reprioritization_base),
                "confidence_level": "queue_review_only_no_implementation",
                "next_action": str(queue_reprioritization_manifest.get("next_allowed_action", "")),
                "blocker": "individual-stock momentum remains provider-blocked; commodity basket ETF momentum is review-only until product/data gates pass",
            }
        )
    if commodity_review_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_basket_etf_product_data_review",
                "current_status": str(commodity_review_decision),
                "evidence_source": rel(commodity_review_base),
                "confidence_level": "product_data_review_only_no_implementation",
                "next_action": str(commodity_review_manifest.get("next_allowed_action", "")),
                "blocker": "candidate commodity basket symbols are not locally cached; controlled data-acquisition review is required before any download or implementation",
            }
        )
    if commodity_data_acquisition_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_basket_etf_data_acquisition_review",
                "current_status": str(commodity_data_acquisition_decision),
                "evidence_source": rel(commodity_data_acquisition_base),
                "confidence_level": "data_acquisition_review_only_no_download",
                "next_action": str(commodity_data_acquisition_manifest.get("next_allowed_action", "")),
                "blocker": "product identity and terms/cache-rights review required before any future commodity wrapper download prompt",
            }
        )
    if commodity_fast_acquisition_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_fast_exploratory_acquisition",
                "current_status": str(commodity_fast_acquisition_status),
                "evidence_source": rel(commodity_fast_acquisition_base),
                "confidence_level": "metadata_quality_packet_only",
                "next_action": "commodity_research_sample_review",
                "blocker": "raw OHLCV excluded from advisor; product identity/wrapper review remains deferred",
            }
        )
    if commodity_exploratory_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_basket_exploratory_screen",
                "current_status": str(commodity_exploratory_decision),
                "evidence_source": rel(commodity_exploratory_base),
                "confidence_level": "fast_exploratory_public_data_research_sample",
                "next_action": "research_sample_review",
                "blocker": "not candidate_exhaustive, not paper-forward, product/wrapper review still required",
            }
        )
    if commodity_risk_control_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_risk_control_batch1",
                "current_status": str(commodity_risk_control_decision),
                "evidence_source": rel(commodity_risk_control_base),
                "confidence_level": "fast_exploratory_public_data_research_sample",
                "next_action": "commodity_risk_control_research_sample_review",
                "blocker": "candidate_exhaustive not run; product/wrapper review still required",
            }
        )
    if commodity_risk_control_verdict_audit_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_risk_control_batch1_verdict_audit",
                "current_status": str(commodity_risk_control_verdict_audit_decision),
                "evidence_source": rel(commodity_risk_control_verdict_audit_base),
                "confidence_level": "verdict_diagnostics_audit_existing_evidence_only",
                "next_action": "commodity_target_window_component_diagnostics_review",
                "blocker": "superseded by diagnostics completion; no commodity candidate_exhaustive run",
            }
        )
    if commodity_risk_control_diagnostics_completion_exists:
        decision_rows.append(
            {
                "decision_area": "commodity_risk_control_batch1_diagnostics_completion",
                "current_status": str(commodity_risk_control_diagnostics_completion_decision),
                "evidence_source": rel(commodity_risk_control_diagnostics_completion_base),
                "confidence_level": "diagnostics_completion_cached_data_only",
                "next_action": "watchlist_only_no_candidate_exhaustive",
                "blocker": "limited incremental target windows and high combo correlation; product/wrapper review still required if reopened",
            }
        )
    if crypto_fast_acquisition_exists:
        decision_rows.append(
            {
                "decision_area": "crypto_spot_fast_acquisition",
                "current_status": str(crypto_fast_acquisition_status),
                "evidence_source": rel(crypto_fast_acquisition_base),
                "confidence_level": "metadata_quality_packet_only",
                "next_action": "crypto_tier2_research_sample_review",
                "blocker": "raw OHLCV excluded from advisor; exchange/cost/24-7 review remains deferred",
            }
        )
    if crypto_tier2_risk_control_exists:
        decision_rows.append(
            {
                "decision_area": "crypto_spot_tier2_risk_control_batch1",
                "current_status": str(crypto_tier2_risk_control_decision),
                "evidence_source": rel(crypto_tier2_risk_control_base),
                "confidence_level": "tier2_exploratory_research_sample",
                "next_action": "research_sample_review",
                "blocker": "candidate_exhaustive not run; no paper-forward, exchange execution, leverage, margin, futures, perpetuals, or options",
            }
        )
    if global_multi_asset_fast_acquisition_exists:
        decision_rows.append(
            {
                "decision_area": "global_multi_asset_fast_acquisition",
                "current_status": str(global_multi_asset_fast_acquisition_status),
                "evidence_source": rel(global_multi_asset_fast_acquisition_base),
                "confidence_level": "metadata_quality_packet_only",
                "next_action": "global_multi_asset_research_sample_review",
                "blocker": "raw OHLCV excluded from advisor; ETF/fund wrapper product review remains deferred",
            }
        )
    if global_multi_asset_batch1_exists:
        decision_rows.append(
            {
                "decision_area": "global_multi_asset_fast_exploration_batch1",
                "current_status": str(global_multi_asset_batch1_decision),
                "evidence_source": rel(global_multi_asset_batch1_base),
                "confidence_level": "fast_exploratory_public_data_research_sample",
                "next_action": "research_sample_review",
                "blocker": "candidate_exhaustive not run; no paper-forward, leverage, margin, shorting, futures, options, forex, intraday, broker, live-order, or real-money action",
            }
        )
    if promotion_review_exists:
        decision_rows.append(
            {
                "decision_area": "combo_promotion_review",
                "current_status": str(promotion_decision),
                "evidence_source": rel(promotion_base),
                "confidence_level": "review_packet_from_full_candidate_exhaustive",
                "next_action": "create_new_paper_forward_observation_plan",
                "blocker": "paper_forward_active remains false; no automatic replacement of SPY_200d",
            }
        )
    if implementation_review_exists:
        decision_rows.append(
            {
                "decision_area": "qqq_implementation_review",
                "current_status": str(implementation_decision),
                "evidence_source": rel(implementation_base),
                "confidence_level": "implementation_gate_review",
                "next_action": "create_research_sample_implementation_prompt",
                "blocker": "strategy remains not implemented; duplicate and equity-beta gates must be preserved",
            }
        )
    if value_implementation_review_exists:
        decision_rows.append(
            {
                "decision_area": "value_momentum_factor_etf_implementation_review",
                "current_status": str(value_implementation_decision),
                "evidence_source": rel(value_implementation_base),
                "confidence_level": "proxy_inception_data_gate_review",
                "next_action": "provider_terms_review",
                "blocker": "core factor ETF proxies require acquisition review; strategy remains not implemented",
            }
        )
    if sector_implementation_review_exists:
        decision_rows.append(
            {
                "decision_area": "sector_top2_implementation_review",
                "current_status": str(sector_implementation_decision),
                "evidence_source": rel(sector_implementation_base),
                "confidence_level": "sector_universe_stream_gate_review",
                "next_action": "universe_review",
                "blocker": "implementation remains future-only; XLC/XLRE universe policy and exact stream requirements must be fixed before code",
            }
        )
    if managed_futures_implementation_review_exists:
        decision_rows.append(
            {
                "decision_area": "managed_futures_proxy_implementation_review",
                "current_status": str(managed_futures_implementation_decision),
                "evidence_source": rel(managed_futures_implementation_base),
                "confidence_level": "proxy_inception_data_gate_review",
                "next_action": "data_acquisition_review",
                "blocker": "DBMF/KMLM/CTA/FMF/WTMF are not locally cached; no strategy implementation allowed",
            }
        )
    if value_data_acquisition_review_exists:
        decision_rows.append(
            {
                "decision_area": "value_momentum_factor_etf_data_acquisition_review",
                "current_status": str(value_data_acquisition_decision),
                "evidence_source": rel(value_data_acquisition_base),
                "confidence_level": "data_source_acquisition_review_only",
                "next_action": "provider_terms_review",
                "blocker": "no provider download or API key approved yet; no strategy implementation allowed",
            }
        )
    if managed_futures_data_acquisition_review_exists:
        decision_rows.append(
            {
                "decision_area": "managed_futures_proxy_data_acquisition_review",
                "current_status": str(managed_futures_data_acquisition_decision),
                "evidence_source": rel(managed_futures_data_acquisition_base),
                "confidence_level": "data_source_acquisition_review_only",
                "next_action": "provider_terms_review",
                "blocker": "provider terms/security review is required before any download; no strategy implementation allowed",
            }
        )
    if value_provider_terms_review_exists:
        decision_rows.append(
            {
                "decision_area": "value_momentum_factor_etf_provider_terms_security_review",
                "current_status": str(value_provider_terms_decision),
                "evidence_source": rel(value_provider_terms_base),
                "confidence_level": "provider_terms_security_review_only",
                "next_action": "create_data_download_prompt",
                "blocker": "future prompt may download only MTUM/VLUE/VTV/QUAL/USMV/SPLV and must stop before strategy/backtest",
            }
        )
    if managed_futures_provider_terms_review_exists:
        decision_rows.append(
            {
                "decision_area": "managed_futures_proxy_provider_terms_security_review",
                "current_status": str(managed_futures_provider_terms_decision),
                "evidence_source": rel(managed_futures_provider_terms_base),
                "confidence_level": "provider_terms_security_review_only",
                "next_action": "create_data_download_prompt",
                "blocker": "future prompt may download only DBMF/KMLM and must stop before strategy/backtest/futures logic",
            }
        )
    if value_data_acquisition_run_exists:
        decision_rows.append(
            {
                "decision_area": "value_momentum_factor_etf_data_acquisition_run",
                "current_status": str(value_data_acquisition_run_status),
                "evidence_source": rel(value_data_acquisition_run_base),
                "confidence_level": "metadata_quality_packet_only",
                "next_action": "update_implementation_review_after_data_quality",
                "blocker": "strategy remains not implemented; no backtest has been run",
            }
        )
    if managed_futures_data_acquisition_run_exists:
        decision_rows.append(
            {
                "decision_area": "managed_futures_proxy_data_acquisition_run",
                "current_status": str(managed_futures_data_acquisition_run_status),
                "evidence_source": rel(managed_futures_data_acquisition_run_base),
                "confidence_level": "metadata_quality_packet_only",
                "next_action": "issuer_methodology_review",
                "blocker": "strategy remains not implemented; issuer/fund methodology review is required",
            }
        )
    if managed_futures_methodology_review_exists:
        decision_rows.append(
            {
                "decision_area": "managed_futures_proxy_methodology_review",
                "current_status": str(managed_futures_methodology_decision),
                "evidence_source": rel(managed_futures_methodology_base),
                "confidence_level": "fund_wrapper_proxy_methodology_review_only",
                "next_action": "create_research_sample_implementation_prompt",
                "blocker": "strategy remains not implemented; short-history and fund-wrapper proxy labels are required",
            }
        )

    family_status = []
    if not rankings.empty:
        for _, row in rankings[rankings.get("lane", pd.Series()).astype(str).eq("independent_family_challenge")].iterrows():
            family_status.append({
                "family_id": row.get("family_id", ""),
                "family_group": row.get("family_group", ""),
                "evidence_tier": row.get("credibility_tier", ""),
                "exact_or_sampled": "exact" if str(row.get("final_validation_completed", "")) == "True" else ("incomplete" if row.get("run_status") != "completed" else "sampled_or_nonfinal"),
                "run_status": row.get("run_status", ""),
                "target_300_rate": row.get("pct_90d_target_300_before_stop", ""),
                "target_400_rate": row.get("pct_90d_target_400_before_stop", ""),
                "stop_hit_rate": row.get("pct_90d_any_stop_hit", ""),
                "worst_drawdown": row.get("worst_90d_max_drawdown", ""),
                "current_verdict": row.get("audit_verdict", ""),
                "next_action": "observe/control" if row.get("run_status") == "completed" else "gate_or_stream_completion",
            })

    tier_rows = []
    for frame, packet in [
        (rankings, "01_CHALLENGE_AND_FAMILY_AUDIT.zip"),
        (profit_rankings, "07_PROFIT_EXPLORATION.zip"),
        (registry, "03_RISK_AND_STRATEGY_GOVERNANCE.zip"),
    ]:
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            item_id = row.get("family_id") or row.get("strategy") or row.get("id") or row.get("display_name", "")
            if not item_id:
                item_id = row.get("experiment_id", "")
            tier_rows.append({
                "item_id": item_id,
                "lane": row.get("lane", ""),
                "tier": row.get("credibility_tier", row.get("current_tier", "")),
                "finality": row.get("final_validation_completed", row.get("status", "")),
                "paper_forward_allowed": row.get("paper_forward_allowed_by_risk_framework", row.get("paper_forward_active", "")),
                "real_money_recommendation": False,
                "source_packet": packet,
            })
    if not candidate_queue.empty:
        for _, row in candidate_queue.iterrows():
            tier_rows.append({
                "item_id": row.get("candidate_id", ""),
                "lane": "strategy_candidate_queue",
                "tier": row.get("evidence_tier", ""),
                "finality": row.get("current_status", ""),
                "paper_forward_allowed": row.get("paper_forward_allowed_now", False),
                "real_money_recommendation": False,
                "source_packet": "08_STRATEGY_CANDIDATE_QUEUE.zip",
            })
    if promotion_review_exists:
        tier_rows.append({
            "item_id": "combo_SPY200d_GLD_50_50_v1_promotion_review",
            "lane": "promotion_review",
            "tier": "tier3_candidate_validation",
            "finality": promotion_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(promotion_base),
        })
    if combo_observation_plan_exists:
        tier_rows.append({
            "item_id": "combo_SPY200d_GLD_50_50_v1_observation_plan_review",
            "lane": "paper_forward_observation_plan_review",
            "tier": "tier3_candidate_validation",
            "finality": combo_observation_plan_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(combo_observation_plan_base),
        })
    if implementation_review_exists:
        tier_rows.append({
            "item_id": "qqq_spy_gld_ief_dual_momentum_v1_implementation_review",
            "lane": "implementation_review",
            "tier": "tier1_research_queue",
            "finality": implementation_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(implementation_base),
        })
    if value_implementation_review_exists:
        tier_rows.append({
            "item_id": "value_momentum_factor_etf_rotation_v1_implementation_review",
            "lane": "implementation_review",
            "tier": "tier1_research_queue",
            "finality": value_implementation_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(value_implementation_base),
        })
    if sector_implementation_review_exists:
        tier_rows.append({
            "item_id": "sector_top2_momentum_simple_v1_implementation_review",
            "lane": "implementation_review",
            "tier": "tier1_research_queue",
            "finality": sector_implementation_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(sector_implementation_base),
        })
    if managed_futures_implementation_review_exists:
        tier_rows.append({
            "item_id": "managed_futures_proxy_etf_trend_v1_implementation_review",
            "lane": "implementation_review",
            "tier": "tier1_research_queue",
            "finality": managed_futures_implementation_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(managed_futures_implementation_base),
        })
    if value_data_acquisition_review_exists:
        tier_rows.append({
            "item_id": "value_momentum_factor_etf_rotation_v1_data_acquisition_review",
            "lane": "data_acquisition_review",
            "tier": "tier1_research_queue",
            "finality": value_data_acquisition_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(value_data_acquisition_base),
        })
    if managed_futures_data_acquisition_review_exists:
        tier_rows.append({
            "item_id": "managed_futures_proxy_etf_trend_v1_data_acquisition_review",
            "lane": "data_acquisition_review",
            "tier": "tier1_research_queue",
            "finality": managed_futures_data_acquisition_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(managed_futures_data_acquisition_base),
        })
    if value_provider_terms_review_exists:
        tier_rows.append({
            "item_id": "value_momentum_factor_etf_rotation_v1_provider_terms_security_review",
            "lane": "provider_terms_security_review",
            "tier": "tier1_research_queue",
            "finality": value_provider_terms_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(value_provider_terms_base),
        })
    if managed_futures_provider_terms_review_exists:
        tier_rows.append({
            "item_id": "managed_futures_proxy_etf_trend_v1_provider_terms_security_review",
            "lane": "provider_terms_security_review",
            "tier": "tier1_research_queue",
            "finality": managed_futures_provider_terms_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(managed_futures_provider_terms_base),
        })
    if value_data_acquisition_run_exists:
        tier_rows.append({
            "item_id": "value_momentum_factor_etf_rotation_v1_data_acquisition_run",
            "lane": "data_acquisition_run",
            "tier": "tier1_research_queue",
            "finality": value_data_acquisition_run_status,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(value_data_acquisition_run_base),
        })
    if managed_futures_data_acquisition_run_exists:
        tier_rows.append({
            "item_id": "managed_futures_proxy_etf_trend_v1_data_acquisition_run",
            "lane": "data_acquisition_run",
            "tier": "tier1_research_queue",
            "finality": managed_futures_data_acquisition_run_status,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(managed_futures_data_acquisition_run_base),
        })
    if managed_futures_methodology_review_exists:
        tier_rows.append({
            "item_id": "managed_futures_proxy_etf_trend_v1_methodology_review",
            "lane": "methodology_review",
            "tier": "tier1_research_queue",
            "finality": managed_futures_methodology_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(managed_futures_methodology_base),
        })
    if candidate_triage_exists:
        tier_rows.append({
            "item_id": "candidate_testing_triage_and_diversification_audit",
            "lane": "candidate_triage",
            "tier": "tier2_credible_prototype",
            "finality": candidate_triage_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(candidate_triage_base),
        })
    if historical_research_exists:
        tier_rows.append({
            "item_id": "historical_research_expansion_parallel_to_paper_demo_observation",
            "lane": "historical_research_expansion",
            "tier": "tier0_research_map",
            "finality": historical_research_phase,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(historical_research_base),
        })
    if research_state_exists:
        tier_rows.append({
            "item_id": "current_state_research_dashboard",
            "lane": "research_state_dashboard",
            "tier": "tier0_research_map",
            "finality": research_state_phase,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(research_state_base),
        })
    if research_diagnostics_exists:
        tier_rows.append({
            "item_id": "historical_attribution_diagnostics_infrastructure",
            "lane": "research_diagnostics",
            "tier": "tier0_research_infrastructure",
            "finality": research_diagnostics_status,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(research_diagnostics_base),
        })
    if individual_stock_gate1b_exists:
        tier_rows.append({
            "item_id": "individual_stock_momentum_gate1b_v1",
            "lane": "research_memo_gate1b",
            "tier": "tier1_research_queue",
            "finality": individual_stock_gate1b_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(individual_stock_gate1b_base),
        })
    if individual_stock_gate1c_exists:
        tier_rows.append({
            "item_id": "individual_stock_momentum_gate1c_provider_cost_access_review",
            "lane": "research_memo_gate1c",
            "tier": "tier1_research_queue",
            "finality": individual_stock_gate1c_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(individual_stock_gate1c_base),
        })
    if individual_stock_gate1d_exists:
        tier_rows.append({
            "item_id": "individual_stock_momentum_gate1d_provider_terms_security_review",
            "lane": "research_memo_gate1d",
            "tier": "tier1_research_queue",
            "finality": individual_stock_gate1d_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(individual_stock_gate1d_base),
        })
    if individual_stock_gate1e_exists:
        tier_rows.append({
            "item_id": "individual_stock_momentum_gate1e_norgate_acquisition_preflight",
            "lane": "research_memo_gate1e",
            "tier": "tier1_research_queue",
            "finality": individual_stock_gate1e_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(individual_stock_gate1e_base),
        })
    if individual_stock_gate1f_exists:
        tier_rows.append({
            "item_id": "individual_stock_momentum_gate1f_sharadar_fallback_review",
            "lane": "research_memo_gate1f",
            "tier": "tier1_research_queue",
            "finality": individual_stock_gate1f_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(individual_stock_gate1f_base),
        })
    if queue_reprioritization_exists:
        tier_rows.append({
            "item_id": "historical_research_queue_reprioritization_after_stock_data_blockers",
            "lane": "research_queue_reprioritization",
            "tier": "tier0_research_map",
            "finality": queue_reprioritization_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(queue_reprioritization_base),
        })
    if commodity_review_exists:
        tier_rows.append({
            "item_id": "commodity_basket_etf_momentum_v1_product_data_review",
            "lane": "commodity_product_data_review",
            "tier": "tier1_research_queue",
            "finality": commodity_review_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(commodity_review_base),
        })
    if commodity_data_acquisition_exists:
        tier_rows.append({
            "item_id": "commodity_basket_etf_momentum_v1_data_acquisition_review",
            "lane": "commodity_data_acquisition_review",
            "tier": "tier1_research_queue",
            "finality": commodity_data_acquisition_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(commodity_data_acquisition_base),
        })
    if commodity_fast_acquisition_exists:
        tier_rows.append({
            "item_id": "commodity_basket_fast_exploratory_acquisition",
            "lane": "commodity_data_acquisition_run",
            "tier": "tier1_exploratory",
            "finality": str(commodity_fast_acquisition_status),
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(commodity_fast_acquisition_base),
        })
    if commodity_exploratory_exists:
        tier_rows.append({
            "item_id": "commodity_basket_tsmom_top2_v1",
            "lane": "commodity_exploratory_research_sample",
            "tier": "tier1_or_tier2_exploratory",
            "finality": commodity_exploratory_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(commodity_exploratory_base),
        })
    if commodity_risk_control_exists:
        tier_rows.append({
            "item_id": "commodity_risk_control_batch1",
            "lane": "commodity_risk_control_research_sample",
            "tier": "tier1_or_tier2_exploratory",
            "finality": commodity_risk_control_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(commodity_risk_control_base),
        })
    if global_multi_asset_fast_acquisition_exists:
        tier_rows.append({
            "item_id": "global_multi_asset_fast_exploratory_acquisition",
            "lane": "global_multi_asset_data_acquisition_run",
            "tier": "tier1_exploratory",
            "finality": str(global_multi_asset_fast_acquisition_status),
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(global_multi_asset_fast_acquisition_base),
        })
    if global_multi_asset_batch1_exists:
        tier_rows.append({
            "item_id": "global_multi_asset_fast_exploration_batch1",
            "lane": "global_multi_asset_research_sample",
            "tier": "tier1_or_tier2_exploratory",
            "finality": global_multi_asset_batch1_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(global_multi_asset_batch1_base),
        })
    if combination_batch1_exists:
        tier_rows.append({
            "item_id": "historical_combination_research_sample_batch1",
            "lane": "combination_lab",
            "tier": "tier2_credible_prototype",
            "finality": combination_batch1_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(combination_batch1_base),
        })
    if combination_batch1_verdict_audit_exists:
        tier_rows.append({
            "item_id": "historical_combination_batch1_verdict_audit",
            "lane": "combination_lab",
            "tier": "tier2_credible_prototype",
            "finality": combination_batch1_verdict_audit_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(combination_batch1_verdict_audit_base),
        })
    if combination_batch1_diagnostics_completion_exists:
        tier_rows.append({
            "item_id": "historical_combination_batch1_diagnostics_completion",
            "lane": "combination_lab",
            "tier": "tier2_credible_prototype",
            "finality": combination_batch1_diagnostics_completion_decision,
            "paper_forward_allowed": False,
            "real_money_recommendation": False,
            "source_packet": rel(combination_batch1_diagnostics_completion_base),
        })

    missing_rows = []
    for _, row in incomplete.iterrows():
        missing_rows.append({
            "item_id": row.get("family_id", row.get("strategy", "")),
            "missing_or_incomplete": "incomplete_evidence",
            "source": "challenge_results.csv",
            "reason": row.get("main_failure_mode", row.get("notes", "")),
        })
    for _, row in blocked.iterrows():
        missing_rows.append({
            "item_id": row.get("family_id", row.get("strategy", "")),
            "missing_or_incomplete": "blocked_by_gate",
            "source": "challenge_results.csv",
            "reason": row.get("blocked_reason", ""),
        })

    latest_rows = []
    for label, path in {
        "challenge_latest": challenge_base,
        "paper_forward_latest": paper_base,
        "risk_framework_latest": REPO_ROOT / "evidence" / "risk_framework" / "latest",
        "strategy_lab_latest": REPO_ROOT / "evidence" / "strategy_lab" / "latest",
        "family_exploratory_latest": family_exploratory,
        "profit_exploration_latest": profit_base,
        "strategy_candidate_queue_latest": candidate_base,
        "combo_promotion_review_latest": promotion_base,
        "generic_promotion_review_latest": generic_promotion_review_base,
        "combo_paper_forward_observation_activation_latest": combo_observation_activation_base,
        "combo_rule_hash_review_latest": combo_rule_hash_base,
        "qqq_implementation_review_latest": implementation_base,
        "value_momentum_implementation_review_latest": value_implementation_base,
        "sector_top2_implementation_review_latest": sector_implementation_base,
        "value_momentum_data_acquisition_review_latest": value_data_acquisition_base,
        "value_momentum_provider_terms_security_review_latest": value_provider_terms_base,
        "managed_futures_provider_terms_security_review_latest": managed_futures_provider_terms_base,
        "value_momentum_data_acquisition_run_latest": value_data_acquisition_run_base,
        "managed_futures_data_acquisition_run_latest": managed_futures_data_acquisition_run_base,
        "paper_forward_observation_cache_update_latest": paper_forward_cache_update_base,
        "managed_futures_methodology_review_latest": managed_futures_methodology_base,
        "historical_research_expansion_latest": historical_research_base,
        "research_state_dashboard_latest": research_state_base,
        "research_diagnostics_latest": research_diagnostics_base,
        "active_combo_benchmark_latest": active_combo_base,
        "individual_stock_momentum_gate1b_latest": individual_stock_gate1b_base,
        "individual_stock_momentum_gate1c_latest": individual_stock_gate1c_base,
        "individual_stock_momentum_gate1d_latest": individual_stock_gate1d_base,
        "individual_stock_momentum_gate1e_latest": individual_stock_gate1e_base,
        "individual_stock_momentum_gate1f_latest": individual_stock_gate1f_base,
        "historical_research_queue_reprioritization_latest": queue_reprioritization_base,
        "commodity_basket_etf_review_latest": commodity_review_base,
        "commodity_basket_etf_data_acquisition_review_latest": commodity_data_acquisition_base,
        "commodity_fast_exploratory_acquisition_latest": commodity_fast_acquisition_base,
        "commodity_exploratory_latest": commodity_exploratory_base,
        "commodity_risk_control_batch1_latest": commodity_risk_control_base,
        "commodity_risk_control_batch1_verdict_audit_latest": commodity_risk_control_verdict_audit_base,
        "commodity_risk_control_batch1_diagnostics_completion_latest": commodity_risk_control_diagnostics_completion_base,
        "crypto_spot_fast_acquisition_latest": crypto_fast_acquisition_base,
        "crypto_tier2_risk_control_batch1_latest": crypto_tier2_risk_control_base,
        "global_multi_asset_fast_acquisition_latest": global_multi_asset_fast_acquisition_base,
        "global_multi_asset_fast_exploration_batch1_latest": global_multi_asset_batch1_base,
        "combination_lab_batch1_latest": combination_batch1_base,
        "combination_lab_batch1_verdict_audit_latest": combination_batch1_verdict_audit_base,
        "combination_lab_batch1_diagnostics_completion_latest": combination_batch1_diagnostics_completion_base,
    }.items():
        latest_rows.append({
            "run_label": label,
            "path": rel(path) if path.exists() else path.as_posix(),
            "exists": path.exists(),
            "file_count": len([p for p in path.iterdir() if p.is_file()]) if path.exists() and path.is_dir() else "",
        })

    review_rows: list[dict[str, Any]] = []
    if promotion_review_exists:
        review_rows.append({
            "review_packet": "combo_promotion_review",
            "subject_id": "combo_SPY200d_GLD_50_50_v1",
            "review_type": "promotion_review",
            "decision": promotion_decision,
            "latest_path": rel(promotion_base),
            "file_count": len([p for p in promotion_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/promotion_reviews/combo_SPY200d_GLD_50_50_v1/latest_promotion_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Review supports creating a separate paper-forward observation plan; it does not activate the row.",
        })
    if generic_promotion_review_exists:
        review_rows.append({
            "review_packet": "generic_promotion_review",
            "subject_id": "all_strategy_lab_rows",
            "review_type": "promotion_review",
            "decision": generic_promotion_review_decision,
            "latest_path": rel(generic_promotion_review_base),
            "file_count": len([p for p in generic_promotion_review_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/promotion_review/latest_promotion_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Generic promotion review classifies rows for candidate_exhaustive queue, watchlist, blocked, duplicate, or protected status. It does not run candidate_exhaustive or activate paper-forward.",
        })
    if combo_observation_plan_exists:
        review_rows.append({
            "review_packet": "combo_paper_forward_observation_plan_review",
            "subject_id": "combo_SPY200d_GLD_50_50_v1",
            "review_type": "paper_forward_observation_plan_review",
            "decision": combo_observation_plan_decision,
            "latest_path": rel(combo_observation_plan_base),
            "file_count": len([p for p in combo_observation_plan_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/paper_forward_observation_plans/combo_SPY200d_GLD_50_50_v1/latest_observation_plan_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Observation plan review approves only a future activation prompt; combo is not active and SPY_200d is not replaced.",
        })
    if combo_observation_activation_exists:
        review_rows.append({
            "review_packet": "combo_paper_forward_observation_activation",
            "subject_id": "combo_SPY200d_GLD_50_50_v1",
            "review_type": "paper_forward_observation_activation",
            "decision": combo_observation_activation_status,
            "latest_path": rel(combo_observation_activation_base),
            "file_count": len([p for p in combo_observation_activation_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/paper_forward_observations/combo_SPY200d_GLD_50_50_v1/latest_observation_activation_packet.zip",
            "paper_forward_active": bool(combo_observation_activation_manifest.get("paper_forward_active", False)),
            "real_money_recommendation": False,
            "notes": "Activation packet prepared the combo as a separate paper/demo observation track; full activation is waiting for cached data after source/spec rule-hash verification. SPY_200d is not replaced.",
        })
    if combo_rule_hash_exists:
        review_rows.append({
            "review_packet": "combo_rule_hash_resolution",
            "subject_id": "combo_SPY200d_GLD_50_50_v1",
            "review_type": "canonical_rule_hash_resolution",
            "decision": combo_rule_hash_decision,
            "latest_path": rel(combo_rule_hash_base),
            "file_count": len([p for p in combo_rule_hash_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/rule_hash_reviews/combo_SPY200d_GLD_50_50_v1/latest_rule_hash_review_packet.zip",
            "paper_forward_active": bool(combo_rule_hash_manifest.get("paper_forward_active", False)),
            "real_money_recommendation": False,
            "notes": (
                "Rule hash was reconstructed from source/spec evidence for paper/demo governance; "
                f"canonical_rule_hash={combo_rule_hash_manifest.get('canonical_rule_hash', 'unavailable')}. "
                "This does not change strategy rules, activate real-money trading, or replace SPY_200d."
            ),
        })
    if implementation_review_exists:
        review_rows.append({
            "review_packet": "qqq_implementation_review",
            "subject_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "review_type": "implementation_review",
            "decision": implementation_decision,
            "latest_path": rel(implementation_base),
            "file_count": len([p for p in implementation_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest_implementation_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Review allows a future research_sample implementation prompt only; no strategy code exists here.",
        })
    if value_implementation_review_exists:
        review_rows.append({
            "review_packet": "value_momentum_factor_etf_implementation_review",
            "subject_id": "value_momentum_factor_etf_rotation_v1",
            "review_type": "proxy_inception_implementation_review",
            "decision": value_implementation_decision,
            "latest_path": rel(value_implementation_base),
            "file_count": len([p for p in value_implementation_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/implementation_reviews/value_momentum_factor_etf_rotation_v1/latest_implementation_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Review approves a future fixed-rule research_sample implementation prompt only; no strategy code exists here.",
        })
    if sector_implementation_review_exists:
        review_rows.append({
            "review_packet": "sector_top2_implementation_review",
            "subject_id": "sector_top2_momentum_simple_v1",
            "review_type": "sector_universe_stream_implementation_review",
            "decision": sector_implementation_decision,
            "latest_path": rel(sector_implementation_base),
            "file_count": len([p for p in sector_implementation_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/implementation_reviews/sector_top2_momentum_simple_v1/latest_implementation_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Review is conditional on a fixed sector universe policy and exact fresh-window stream; no strategy code exists here.",
        })
    if managed_futures_implementation_review_exists:
        review_rows.append({
            "review_packet": "managed_futures_proxy_implementation_review",
            "subject_id": "managed_futures_proxy_etf_trend_v1",
            "review_type": "proxy_inception_implementation_review",
            "decision": managed_futures_implementation_decision,
            "latest_path": rel(managed_futures_implementation_base),
            "file_count": len([p for p in managed_futures_implementation_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/implementation_reviews/managed_futures_proxy_etf_trend_v1/latest_implementation_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Review requires future data acquisition review for DBMF/KMLM/CTA/FMF/WTMF before any research_sample implementation prompt.",
        })
    if managed_futures_methodology_review_exists:
        review_rows.append({
            "review_packet": "managed_futures_proxy_methodology_review",
            "subject_id": "managed_futures_proxy_etf_trend_v1",
            "review_type": "issuer_fund_methodology_review",
            "decision": managed_futures_methodology_decision,
            "latest_path": rel(managed_futures_methodology_base),
            "file_count": len([p for p in managed_futures_methodology_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/methodology_reviews/managed_futures_proxy_etf_trend_v1/latest_methodology_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "DBMF/KMLM are accepted only as short-history fund-wrapper proxies for a future research_sample prompt; no strategy code exists here.",
        })
    if candidate_triage_exists:
        review_rows.append({
            "review_packet": "candidate_testing_triage",
            "subject_id": "recent_profit_exploration_research_sample_candidates",
            "review_type": "candidate_testing_triage_and_diversification_audit",
            "decision": candidate_triage_decision,
            "latest_path": rel(candidate_triage_base),
            "file_count": len([p for p in candidate_triage_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/candidate_triage/latest_candidate_triage_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Triage keeps QQQ/value-momentum as archive references, sector/managed-futures as watchlist, combo/top2 as active review, and adds no new candidate_exhaustive rows.",
        })
    if historical_research_exists:
        review_rows.append({
            "review_packet": "historical_research_expansion",
            "subject_id": "historical_research_expansion_parallel_to_paper_demo_observation",
            "review_type": "current_phase_and_historical_research_roadmap",
            "decision": historical_research_phase,
            "latest_path": rel(historical_research_base),
            "file_count": len([p for p in historical_research_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/historical_research_expansion/latest_historical_research_expansion_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Corrects phase: active paper/demo observation does not freeze historical research; combination-design review and diagnostics work may continue under gates.",
        })
    if research_state_exists:
        review_rows.append({
            "review_packet": "research_state_dashboard",
            "subject_id": "current_project_state",
            "review_type": "current_state_dashboard",
            "decision": research_state_phase,
            "latest_path": rel(research_state_base),
            "file_count": len([p for p in research_state_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_state/latest_research_state_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Dashboard reads existing latest evidence only and confirms combo active, SPY_200d frozen control, and historical research continuing in parallel.",
        })
    if research_diagnostics_exists:
        review_rows.append({
            "review_packet": "historical_attribution_diagnostics",
            "subject_id": "historical_research_attribution_diagnostics",
            "review_type": "diagnostics_infrastructure",
            "decision": research_diagnostics_status,
            "latest_path": rel(research_diagnostics_base),
            "file_count": len([p for p in research_diagnostics_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_diagnostics/latest_research_diagnostics_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Reusable attribution diagnostics are available for future historical research; no new strategy, candidate_exhaustive, backtest, data download, or paper-forward rule change is included.",
        })
    if individual_stock_gate1b_exists:
        review_rows.append({
            "review_packet": "individual_stock_momentum_gate1b",
            "subject_id": "individual_stock_momentum_gate1b_v1",
            "review_type": "gate1b_provider_survivorship_cost_review",
            "decision": individual_stock_gate1b_decision,
            "latest_path": rel(individual_stock_gate1b_base),
            "file_count": len([p for p in individual_stock_gate1b_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/gate1b/individual_stock_momentum/latest_gate1b_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Gate 1B keeps individual stock momentum blocked pending provider/cost/access review; no stock strategy, loader, data download, backtest, or paper-forward approval.",
        })
    if individual_stock_gate1c_exists:
        review_rows.append({
            "review_packet": "individual_stock_momentum_gate1c",
            "subject_id": "individual_stock_momentum_gate1c_provider_cost_access_review",
            "review_type": "gate1c_provider_cost_access_review",
            "decision": individual_stock_gate1c_decision,
            "latest_path": rel(individual_stock_gate1c_base),
            "file_count": len([p for p in individual_stock_gate1c_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/gate1c/individual_stock_momentum/latest_gate1c_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Gate 1C chooses provider-before-acquisition as the next governance step; no stock strategy, stock loader, provider call, data download, backtest, or paper-forward approval.",
        })
    if individual_stock_gate1d_exists:
        review_rows.append({
            "review_packet": "individual_stock_momentum_gate1d",
            "subject_id": "individual_stock_momentum_gate1d_provider_terms_security_review",
            "review_type": "gate1d_provider_terms_security_field_coverage_review",
            "decision": individual_stock_gate1d_decision,
            "latest_path": rel(individual_stock_gate1d_base),
            "file_count": len([p for p in individual_stock_gate1d_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/gate1d/individual_stock_momentum/latest_gate1d_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Gate 1D selects Norgate for a future Gate 1E controlled acquisition review only; no stock strategy, stock loader, provider API call, data download, backtest, or paper-forward approval.",
        })
    if individual_stock_gate1e_exists:
        review_rows.append({
            "review_packet": "individual_stock_momentum_gate1e",
            "subject_id": "individual_stock_momentum_gate1e_norgate_acquisition_preflight",
            "review_type": "gate1e_norgate_acquisition_preflight",
            "decision": individual_stock_gate1e_decision,
            "latest_path": rel(individual_stock_gate1e_base),
            "file_count": len([p for p in individual_stock_gate1e_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/gate1e/individual_stock_momentum/latest_gate1e_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Gate 1E preflight blocks Norgate acquisition because local access and user terms/cache-rights acceptance are not documented; no stock strategy, stock loader, provider API call, data download, backtest, or paper-forward approval.",
        })
    if individual_stock_gate1f_exists:
        review_rows.append({
            "review_packet": "individual_stock_momentum_gate1f_sharadar_fallback",
            "subject_id": "individual_stock_momentum_gate1f_sharadar_fallback_review",
            "review_type": "gate1f_sharadar_fallback_provider_review",
            "decision": individual_stock_gate1f_decision,
            "latest_path": rel(individual_stock_gate1f_base),
            "file_count": len([p for p in individual_stock_gate1f_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/gate1f/individual_stock_momentum/latest_gate1f_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Gate 1F reviews Sharadar as fallback after Norgate access was blocked; package and terms selection are still required before any API call, sample, loader, or backtest.",
        })
    if queue_reprioritization_exists:
        review_rows.append({
            "review_packet": "historical_research_queue_reprioritization",
            "subject_id": "historical_research_queue_reprioritization_after_stock_data_blockers",
            "review_type": "queue_reprioritization_after_stock_data_blockers",
            "decision": queue_reprioritization_decision,
            "latest_path": rel(queue_reprioritization_base),
            "file_count": len([p for p in queue_reprioritization_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/queue_reprioritization/latest_queue_reprioritization_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "After stock-provider blockers, the queue selected commodity_basket_etf_momentum_v1 for a future product/data review only with next action create_commodity_basket_etf_momentum_review; no strategy implementation, data loader, provider API call, data download, backtest, or paper-forward change.",
        })
    if commodity_review_exists:
        review_rows.append({
            "review_packet": "commodity_basket_etf_product_data_review",
            "subject_id": "commodity_basket_etf_momentum_v1",
            "review_type": "commodity_etf_product_data_review",
            "decision": commodity_review_decision,
            "latest_path": rel(commodity_review_base),
            "file_count": len([p for p in commodity_review_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/research_memos/commodity_basket_etf_momentum/latest_commodity_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Commodity basket ETF review covered DBC, PDBC, COMT, GSG, and USCI; none is locally cached, so only commodity_data_acquisition_review is approved as a future controlled data-acquisition review, with no implementation/download/backtest/Profit Exploration.",
        })
    if commodity_data_acquisition_exists:
        review_rows.append({
            "review_packet": "commodity_basket_etf_data_acquisition_review",
            "subject_id": "commodity_basket_etf_momentum_v1",
            "review_type": "commodity_etf_wrapper_data_acquisition_review",
            "decision": commodity_data_acquisition_decision,
            "latest_path": rel(commodity_data_acquisition_base),
            "file_count": len([p for p in commodity_data_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_reviews/commodity_basket_etf_momentum_v1/latest_data_acquisition_review_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Commodity data acquisition review covered DBC, PDBC, COMT, GSG, and USCI; decision conditional_pending_product_identity_terms_review approves no future download symbols yet, prefers PDBC/COMT only after terms review, and records no data download/provider API/backtest/Profit Exploration.",
        })
    if commodity_fast_acquisition_exists:
        review_rows.append({
            "review_packet": "commodity_fast_exploratory_acquisition",
            "subject_id": "commodity_basket_fast_exploratory",
            "review_type": "fast_exploratory_etf_fund_wrapper_acquisition",
            "decision": str(commodity_fast_acquisition_status),
            "latest_path": rel(commodity_fast_acquisition_base),
            "file_count": len([p for p in commodity_fast_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/commodity_basket_fast_exploratory/latest_fast_commodity_acquisition_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Fast exploratory acquisition metadata only; raw OHLCV remains in data/cache and is not included in advisor upload.",
        })
    if commodity_exploratory_exists:
        review_rows.append({
            "review_packet": "commodity_basket_exploratory_screen",
            "subject_id": "commodity_basket_tsmom_top2_v1",
            "review_type": "fast_exploratory_commodity_wrapper_research_sample",
            "decision": commodity_exploratory_decision,
            "latest_path": rel(commodity_exploratory_base),
            "file_count": len([p for p in commodity_exploratory_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/commodity_exploratory/latest_commodity_exploratory_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Fast exploratory research_sample only; no candidate_exhaustive, paper-forward activation, broker integration, live orders, or real-money recommendation.",
        })
    if commodity_risk_control_exists:
        review_rows.append({
            "review_packet": "commodity_risk_control_batch1",
            "subject_id": "commodity_basket_etf_momentum_v1",
            "review_type": "fast_exploratory_commodity_risk_control_research_sample",
            "decision": commodity_risk_control_decision,
            "latest_path": rel(commodity_risk_control_base),
            "file_count": len([p for p in commodity_risk_control_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/commodity_lab/risk_control_batch1/latest_risk_control_batch1_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Risk-control research_sample only; no candidate_exhaustive, paper-forward activation, broker integration, live orders, or real-money recommendation.",
        })
    if commodity_risk_control_verdict_audit_exists:
        review_rows.append({
            "review_packet": "commodity_risk_control_batch1_verdict_audit",
            "subject_id": "commodity_basket_etf_momentum_v1",
            "review_type": "commodity_wrapper_verdict_diagnostics_and_candidate_exhaustive_audit",
            "decision": commodity_risk_control_verdict_audit_decision,
            "latest_path": rel(commodity_risk_control_verdict_audit_base),
            "file_count": len([p for p in commodity_risk_control_verdict_audit_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/commodity_lab/risk_control_batch1_verdict_audit/latest_risk_control_batch1_verdict_audit_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Audit uses existing evidence only and is superseded by diagnostics completion; no candidate_exhaustive, paper-forward activation, broker integration, live orders, or real-money recommendation.",
        })
    if commodity_risk_control_diagnostics_completion_exists:
        review_rows.append({
            "review_packet": "commodity_risk_control_batch1_diagnostics_completion",
            "subject_id": "combo_plus_commodity_basket_80_20_v1",
            "review_type": "commodity_wrapper_target_window_component_drawdown_diagnostics_completion",
            "decision": commodity_risk_control_diagnostics_completion_decision,
            "latest_path": rel(commodity_risk_control_diagnostics_completion_base),
            "file_count": len([p for p in commodity_risk_control_diagnostics_completion_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest_risk_control_batch1_diagnostics_completion_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Diagnostics completion supports watchlist-only for combo_plus_commodity_basket_80_20_v1; no candidate_exhaustive, data download, backtest, or paper-forward change.",
        })
    if crypto_fast_acquisition_exists:
        review_rows.append({
            "review_packet": "crypto_spot_fast_acquisition",
            "subject_id": "crypto_spot_fast_exploratory",
            "review_type": "fast_exploratory_crypto_spot_cache_status",
            "decision": str(crypto_fast_acquisition_status),
            "latest_path": rel(crypto_fast_acquisition_base),
            "file_count": len([p for p in crypto_fast_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/crypto_spot_fast_exploratory/latest_crypto_spot_fast_acquisition_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "BTC/ETH cache status only; raw OHLCV excluded from advisor upload and no exchange, broker, or real-money behavior.",
        })
    if crypto_tier2_risk_control_exists:
        review_rows.append({
            "review_packet": "crypto_spot_tier2_risk_control_batch1",
            "subject_id": "crypto_spot_tier2_risk_control_batch1",
            "review_type": "crypto_spot_tier2_research_sample",
            "decision": crypto_tier2_risk_control_decision,
            "latest_path": rel(crypto_tier2_risk_control_base),
            "file_count": len([p for p in crypto_tier2_risk_control_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/crypto_lab/tier2_risk_control_batch1/latest_tier2_risk_control_batch1_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Fast exploratory BTC/ETH spot-only risk-control research_sample; no candidate_exhaustive, leverage, margin, futures, perpetuals, options, broker integration, live orders, or real-money recommendation.",
        })
    if global_multi_asset_fast_acquisition_exists:
        review_rows.append({
            "review_packet": "global_multi_asset_fast_acquisition",
            "subject_id": "global_multi_asset_fast_exploratory",
            "review_type": "fast_exploratory_etf_fund_wrapper_acquisition",
            "decision": str(global_multi_asset_fast_acquisition_status),
            "latest_path": rel(global_multi_asset_fast_acquisition_base),
            "file_count": len([p for p in global_multi_asset_fast_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/global_multi_asset_fast_exploratory/latest_global_multi_asset_acquisition_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Cache-first ETF/fund wrapper acquisition metadata only; raw OHLCV remains in data/cache and is not included in advisor upload.",
        })
    if global_multi_asset_batch1_exists:
        review_rows.append({
            "review_packet": "global_multi_asset_fast_exploration_batch1",
            "subject_id": "global_multi_asset_fast_exploration_batch1",
            "review_type": "fast_exploratory_global_multi_asset_etf_research_sample",
            "decision": global_multi_asset_batch1_decision,
            "latest_path": rel(global_multi_asset_batch1_base),
            "file_count": len([p for p in global_multi_asset_batch1_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/multi_asset_lab/fast_exploration_batch1/latest_fast_exploration_batch1_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Fast exploratory research_sample only; no candidate_exhaustive, paper-forward activation, broker integration, live orders, leverage, margin, shorting, futures, options, forex, intraday logic, or real-money recommendation.",
        })
    if combination_batch1_exists:
        review_rows.append({
            "review_packet": "historical_combination_batch1",
            "subject_id": "historical_combination_research_sample_batch1",
            "review_type": "fixed_combination_research_sample_batch",
            "decision": combination_batch1_decision,
            "latest_path": rel(combination_batch1_base),
            "file_count": len([p for p in combination_batch1_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/combination_lab/latest_combination_batch1_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Batch 1 tested exactly three fixed predeclared combinations as research_sample only; no candidate_exhaustive, no data download, and no paper-forward rule change.",
        })
    if combination_batch1_verdict_audit_exists:
        review_rows.append({
            "review_packet": "historical_combination_batch1_verdict_audit",
            "subject_id": "historical_combination_research_sample_batch1",
            "review_type": "verdict_scoring_and_candidate_exhaustive_audit",
            "decision": combination_batch1_verdict_audit_decision,
            "latest_path": rel(combination_batch1_verdict_audit_base),
            "file_count": len([p for p in combination_batch1_verdict_audit_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/combination_lab/batch1_verdict_audit/latest_batch1_verdict_audit_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Audit corrected overly broad Batch 1 verdict labels and kept candidate_exhaustive blocked pending more diagnostics.",
        })
    if combination_batch1_diagnostics_completion_exists:
        review_rows.append({
            "review_packet": "historical_combination_batch1_diagnostics_completion",
            "subject_id": "historical_combination_research_sample_batch1",
            "review_type": "target_window_component_and_drawdown_diagnostics_completion",
            "decision": combination_batch1_diagnostics_completion_decision,
            "latest_path": rel(combination_batch1_diagnostics_completion_base),
            "file_count": len([p for p in combination_batch1_diagnostics_completion_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/combination_lab/batch1_diagnostics_completion/latest_batch1_diagnostics_completion_packet.zip",
            "paper_forward_active": False,
            "real_money_recommendation": False,
            "notes": "Diagnostics completed target-window co-movement, component contribution availability, common-history sensitivity, and drawdown-overlap review; Batch 1 remains short-history watchlist only with no candidate_exhaustive run.",
        })

    data_acquisition_rows: list[dict[str, Any]] = []
    if value_data_acquisition_review_exists:
        data_acquisition_rows.append({
            "review_packet": "value_momentum_factor_etf_data_acquisition_review",
            "subject_id": "value_momentum_factor_etf_rotation_v1",
            "review_type": "data_source_acquisition_review",
            "decision": value_data_acquisition_decision,
            "latest_path": rel(value_data_acquisition_base),
            "file_count": len([p for p in value_data_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_reviews/value_momentum_factor_etf_rotation_v1/latest_data_acquisition_review_packet.zip",
            "data_downloaded": False,
            "api_key_or_secret_written": False,
            "raw_ohlcv_included": False,
            "real_money_recommendation": False,
            "notes": "Missing local cache now means provider/acquisition review is required, not permanent data unavailability.",
        })
    if managed_futures_data_acquisition_review_exists:
        data_acquisition_rows.append({
            "review_packet": "managed_futures_proxy_data_acquisition_review",
            "subject_id": "managed_futures_proxy_etf_trend_v1",
            "review_type": "data_source_acquisition_review",
            "decision": managed_futures_data_acquisition_decision,
            "latest_path": rel(managed_futures_data_acquisition_base),
            "file_count": len([p for p in managed_futures_data_acquisition_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_reviews/managed_futures_proxy_etf_trend_v1/latest_data_acquisition_review_packet.zip",
            "data_downloaded": False,
            "api_key_or_secret_written": False,
            "raw_ohlcv_included": False,
            "real_money_recommendation": False,
            "notes": "Provider terms/security review is approved as the next gate for DBMF/KMLM/CTA/FMF/WTMF; no download is approved by this packet.",
        })
    if value_provider_terms_review_exists:
        data_acquisition_rows.append({
            "review_packet": "value_momentum_factor_etf_provider_terms_security_review",
            "subject_id": "value_momentum_factor_etf_rotation_v1",
            "review_type": "provider_terms_security_review",
            "decision": value_provider_terms_decision,
            "latest_path": rel(value_provider_terms_base),
            "file_count": len([p for p in value_provider_terms_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_reviews/value_momentum_factor_etf_rotation_v1/provider_terms_security_review/latest_provider_terms_security_review_packet.zip",
            "data_downloaded": False,
            "api_key_or_secret_written": False,
            "raw_ohlcv_included": False,
            "real_money_recommendation": False,
            "notes": "Future yfinance-compatible prompt may acquire only MTUM, VLUE, VTV, QUAL, USMV, and SPLV with metadata and quality checks.",
        })
    if managed_futures_provider_terms_review_exists:
        data_acquisition_rows.append({
            "review_packet": "managed_futures_proxy_provider_terms_security_review",
            "subject_id": "managed_futures_proxy_etf_trend_v1",
            "review_type": "provider_terms_security_review",
            "decision": managed_futures_provider_terms_decision,
            "latest_path": rel(managed_futures_provider_terms_base),
            "file_count": len([p for p in managed_futures_provider_terms_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_reviews/managed_futures_proxy_etf_trend_v1/provider_terms_security_review/latest_provider_terms_security_review_packet.zip",
            "data_downloaded": False,
            "api_key_or_secret_written": False,
            "raw_ohlcv_included": False,
            "real_money_recommendation": False,
            "notes": "Future yfinance-compatible prompt may acquire DBMF and KMLM only; CTA requires ticker identity review and FMF/WTMF remain optional.",
        })
    if value_data_acquisition_run_exists:
        data_acquisition_rows.append({
            "review_packet": "value_momentum_factor_etf_data_acquisition_run",
            "subject_id": "value_momentum_factor_etf_rotation_v1",
            "review_type": "data_acquisition_run_metadata_quality",
            "decision": value_data_acquisition_run_status,
            "latest_path": rel(value_data_acquisition_run_base),
            "file_count": len([p for p in value_data_acquisition_run_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/value_momentum_factor_etf_rotation_v1/latest_data_acquisition_packet.zip",
            "data_downloaded": bool(value_data_acquisition_run_manifest.get("data_downloaded", False)),
            "api_key_or_secret_written": bool(value_data_acquisition_run_manifest.get("api_key_or_secret_written", False)),
            "raw_ohlcv_included": bool(value_data_acquisition_run_manifest.get("raw_ohlcv_included", False)),
            "real_money_recommendation": False,
            "notes": "Metadata-only acquisition packet; raw OHLCV remains in data/cache and is not included in advisor upload.",
        })
    if managed_futures_data_acquisition_run_exists:
        data_acquisition_rows.append({
            "review_packet": "managed_futures_proxy_data_acquisition_run",
            "subject_id": "managed_futures_proxy_etf_trend_v1",
            "review_type": "data_acquisition_run_metadata_quality",
            "decision": managed_futures_data_acquisition_run_status,
            "latest_path": rel(managed_futures_data_acquisition_run_base),
            "file_count": len([p for p in managed_futures_data_acquisition_run_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/managed_futures_proxy_etf_trend_v1/latest_data_acquisition_packet.zip",
            "data_downloaded": bool(managed_futures_data_acquisition_run_manifest.get("data_downloaded", False)),
            "api_key_or_secret_written": bool(managed_futures_data_acquisition_run_manifest.get("api_key_or_secret_written", False)),
            "raw_ohlcv_included": bool(managed_futures_data_acquisition_run_manifest.get("raw_ohlcv_included", False)),
            "real_money_recommendation": False,
            "notes": "Metadata-only DBMF/KMLM acquisition packet; raw OHLCV remains in data/cache and is not included in advisor upload.",
        })
    if paper_forward_cache_update_exists:
        data_acquisition_rows.append({
            "review_packet": "paper_forward_observation_cache_update",
            "subject_id": "combo_SPY200d_GLD_50_50_v1_observation_activation",
            "review_type": "controlled_cache_update_metadata_quality",
            "decision": paper_forward_cache_update_status,
            "latest_path": rel(paper_forward_cache_update_base),
            "file_count": len([p for p in paper_forward_cache_update_base.iterdir() if p.is_file()]),
            "zip_path": "evidence/data_acquisition_runs/paper_forward_observation_cache_update/latest_cache_update_packet.zip",
            "data_downloaded": bool(paper_forward_cache_update_manifest.get("data_downloaded_or_refreshed", False)),
            "api_key_or_secret_written": bool(paper_forward_cache_update_manifest.get("api_key_or_secret_written", False)),
            "raw_ohlcv_included": bool(paper_forward_cache_update_manifest.get("raw_ohlcv_included", False)),
            "real_money_recommendation": False,
            "notes": (
                "Controlled SPY/GLD/BIL cache update for combo paper/demo observation activation; "
                f"latest_common_cached_date={paper_forward_cache_update_manifest.get('latest_common_cached_date', 'unavailable')}; "
                f"requested_activation_date_supported={paper_forward_cache_update_manifest.get('requested_activation_date_supported', 'unavailable')}."
            ),
        })

    known_issues = """
    # Known Issues And Contradictions

    - Packet-level challenge finality can be incomplete while individual ETF benchmark-like family rows are exact. Read row-level finality columns.
    - A_ETF_sector_momentum and current_no_cash_proxy_alpha_AB have existing Backtester variant paths, but are not accepted as independent-family completed rows because the compact family challenge requires fresh-window rolling streams.
    - GLD has higher target rates than SPY_200d in exact family rows, but materially worse drawdown/stop behavior.
    - Crypto target potential, if present, is Tier 1 exploratory only and not candidate-grade.
    """

    open_questions = """
    # Open Questions For Advisor

    1. Which fixed-rule combination-design review should come first?
    2. Which correlation/co-movement diagnostics are required before the next historical research_sample?
    3. Are any blocked families worth gate-review work before more ETF diagnostics?
    4. Does the advisor agree that paper-forward checkpoint timing should not freeze historical research?
    """

    entries: list[FileEntry] = []
    add_generated(entries, "ADVISOR_EXECUTIVE_STATE.md", md_bytes(executive))
    add_generated(entries, "CURRENT_DECISION_MATRIX.csv", csv_bytes(decision_rows))
    add_generated(entries, "LATEST_RUNS_INDEX.csv", csv_bytes(latest_rows))
    add_generated(entries, "EVIDENCE_TIER_MAP.csv", csv_bytes(tier_rows))
    add_generated(entries, "FAMILY_STATUS_MATRIX.csv", csv_bytes(family_status))
    add_generated(entries, "OPEN_QUESTIONS_FOR_ADVISOR.md", md_bytes(open_questions))
    add_generated(entries, "KNOWN_ISSUES_AND_CONTRADICTIONS.md", md_bytes(known_issues))
    add_generated(entries, "MISSING_OR_INCOMPLETE_EVIDENCE.csv", csv_bytes(missing_rows))
    add_generated(entries, "PROFIT_EXPLORATION_DECISION_MATRIX.csv", csv_bytes(profit_decision_rows(profit_rankings, profit_results)))
    add_generated(entries, "CANDIDATE_QUEUE_DECISION_MATRIX.csv", csv_bytes(candidate_queue_decision_rows(candidate_queue)))
    add_generated(entries, "PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv", csv_bytes(review_rows))
    add_generated(entries, "DATA_ACQUISITION_REVIEW_INDEX.csv", csv_bytes(data_acquisition_rows))
    add_generated(entries, "ADVISOR_CONSISTENCY_REPORT.json", json_bytes(consistency_report))
    add_generated(entries, "ADVISOR_CONSISTENCY_REPORT.md", md_bytes(consistency_report_markdown(consistency_report)))
    return entries


def profit_decision_rows(profit_rankings: pd.DataFrame, profit_results: pd.DataFrame) -> list[dict[str, Any]]:
    if profit_rankings.empty:
        return []
    rows: list[dict[str, Any]] = []
    sort_col = "rank_balanced_drawdown_aware_v2" if "rank_balanced_drawdown_aware_v2" in profit_rankings else "rank_overall"
    for _, row in profit_rankings.sort_values(sort_col).head(12).iterrows():
        rows.append(
            {
                "experiment_id": row.get("experiment_id", ""),
                "display_name": row.get("display_name", ""),
                "evidence_tier": row.get("evidence_tier", ""),
                "run_status": row.get("run_status", ""),
                "p_90d_target_300_before_stop": row.get("p_90d_target_300_before_stop", ""),
                "p_90d_target_400_before_stop": row.get("p_90d_target_400_before_stop", ""),
                "p_90d_target_600_before_stop": row.get("p_90d_target_600_before_stop", ""),
                "p_90d_any_stop_hit": row.get("p_90d_any_stop_hit", ""),
                "median_90d_stop_enforced_final_equity": row.get("median_90d_stop_enforced_final_equity", ""),
                "p95_90d_stop_enforced_final_equity": row.get("p95_90d_stop_enforced_final_equity", ""),
                "worst_90d_max_drawdown": row.get("worst_90d_max_drawdown", ""),
                "final_score": row.get("final_score", ""),
                "balanced_drawdown_aware_score_v2": row.get("balanced_drawdown_aware_score_v2", ""),
                "rank_balanced_drawdown_aware_v2": row.get("rank_balanced_drawdown_aware_v2", ""),
                "profit_verdict": row.get("profit_verdict", ""),
                "practical_verdict_v2": row.get("practical_verdict_v2", ""),
                "accounting_integrity_status": row.get("accounting_integrity_status", ""),
                "profit_results_usable": row.get("profit_results_usable", ""),
                "ranking_blocked_reason": row.get("ranking_blocked_reason", ""),
                "candidate_exhaustive_queue_rank": row.get("candidate_exhaustive_queue_rank", ""),
                "deserves_candidate_exhaustive": row.get("deserves_candidate_exhaustive", ""),
                "queue_reason": row.get("queue_reason", ""),
                "source_packet": "07_PROFIT_EXPLORATION.zip",
            }
        )
    return rows


def candidate_queue_decision_rows(candidate_queue: pd.DataFrame) -> list[dict[str, Any]]:
    if candidate_queue.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in candidate_queue.iterrows():
        rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "display_name": row.get("display_name", ""),
                "current_status": row.get("current_status", ""),
                "evidence_tier": row.get("evidence_tier", ""),
                "recommended_next_action": row.get("recommended_next_action", ""),
                "implementation_allowed_now": row.get("implementation_allowed_now", ""),
                "paper_forward_allowed_now": row.get("paper_forward_allowed_now", ""),
                "real_money_recommendation": row.get("real_money_recommendation", False),
                "requires_new_data": row.get("requires_new_data", ""),
                "current_engine_can_test": row.get("current_engine_can_test", ""),
                "target_potential": row.get("target_potential", ""),
                "stop_risk": row.get("stop_risk", ""),
                "data_gate_status": row.get("data_gate_status", ""),
                "execution_gate_status": row.get("execution_gate_status", ""),
                "risk_model_gate_status": row.get("risk_model_gate_status", ""),
                "reason_to_test": row.get("reason_to_test", ""),
                "reason_to_reject_or_defer": row.get("reason_to_reject_or_defer", ""),
                "source_packet": "08_STRATEGY_CANDIDATE_QUEUE.zip",
            }
        )
    return rows


def gate_status_matrix() -> list[FileEntry]:
    registry = safe_read_csv(REPO_ROOT / "evidence" / "strategy_lab" / "latest" / "strategy_registry_snapshot.csv")
    rows = []
    if not registry.empty:
        blocked = registry[
            registry.get("implementation_status", pd.Series(dtype=str)).astype(str).eq("blocked_by_gate")
            | registry.get("credibility_tier", pd.Series(dtype=str)).astype(str).eq("blocked")
        ]
        for _, row in blocked.iterrows():
            rows.append({
                "item_id": row.get("id", ""),
                "lane": row.get("lane", ""),
                "status": row.get("status", ""),
                "implementation_status": row.get("implementation_status", ""),
                "allowed_next_action": row.get("allowed_next_action", ""),
                "blocker": row.get("notes", ""),
            })
    return [FileEntry(source=None, arcname="GATE_STATUS_MATRIX.csv", content=csv_bytes(rows))]


def exploratory_generated_files() -> list[FileEntry]:
    rows = [
        {
            "lane": "crypto_spot_momentum",
            "tier": "tier1_exploratory",
            "finality": "non_final",
            "candidate_grade": False,
            "source": "evidence/exploratory/crypto_spot_momentum/latest",
        }
    ]
    warning = """
    # Exploratory Not Final Warning

    Crypto spot momentum evidence is Tier 1 exploratory only. It is not validated, not paper-forward ready, not real-money suitable, and not a recommendation. It lacks broker/exchange execution modeling, bid/ask/order-book modeling, custody/outage treatment, and stronger data controls.
    """
    return [
        FileEntry(source=None, arcname="EXPLORATORY_LANES_INDEX.csv", content=csv_bytes(rows)),
        FileEntry(source=None, arcname="EXPLORATORY_NOT_FINAL_WARNING.md", content=md_bytes(warning)),
    ]


def build_packet(name: str, sources: list[str], no_nested_zips: bool, generated: list[FileEntry] | None = None, allowlist: set[str] | None = None) -> PacketBuild:
    packet = PacketBuild(name=name, source_paths=sources)
    packet.entries.extend(generated or [])
    for source in sources:
        if source.startswith("generated"):
            continue
        entries, missing = collect_from_path(REPO_ROOT / source, no_nested_zips=no_nested_zips, allowlist=allowlist)
        packet.entries.extend(entries)
        packet.missing_files.extend(missing)
    return packet


def build_all_packets(output_root: Path, include_optional: bool = True, include_repro_debug: bool = True, strict: bool = False, no_nested_zips: bool = True) -> dict[str, Any]:
    created = utc_now()
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)

    packets = [
        build_packet("00_ADVISOR_INDEX", ["generated summaries and indexes"], no_nested_zips, advisor_index_generated_files(created)),
        build_packet("01_CHALLENGE_AND_FAMILY_AUDIT", ["evidence/challenge_runs/latest"], no_nested_zips, challenge_generated_files()),
        build_packet("02_PAPER_FORWARD_AUDIT", [
            "evidence/paper_forward_runs/latest",
            "evidence/paper_forward_runs/paper_forward_checkpoints.csv",
            "evidence/paper_forward_runs/monthly_decision_checkpoints.csv",
        ], no_nested_zips),
        build_packet("03_RISK_AND_STRATEGY_GOVERNANCE", [
            "evidence/risk_framework/latest",
            "evidence/strategy_lab/latest",
            "evidence/promotion_review/latest",
            "risk_framework/risk_framework.yaml",
            "strategy_lab/strategy_registry.yaml",
            "strategy_lab/PROMOTION_POLICY.md",
            "strategy_lab/promotion_thresholds.yaml",
            "strategy_lab/policies",
        ], no_nested_zips),
        build_packet("04_RESEARCH_DIRECTION_AND_GATES", [
            "docs/research_direction",
            "family_lab",
            "portfolio_lab",
            "docs/research_memos/gate1/individual_stock_momentum",
            "docs/research_memos/gate1/individual_stock_momentum/vendor_verification",
            "research_memos/gate1b/individual_stock_momentum",
            "research_memos/gate1c/individual_stock_momentum",
            "research_memos/gate1d/individual_stock_momentum",
            "research_memos/gate1e/individual_stock_momentum",
            "research_memos/gate1f/individual_stock_momentum",
            "research_memos/queue_reprioritization",
            "research_memos/commodity_basket_etf_momentum",
            "data_acquisition_reviews/commodity_basket_etf_momentum_v1",
            "data_policy",
            "data_acquisition_runs/commodity_basket_fast_exploratory",
            "data_acquisition_runs/crypto_spot_fast_exploratory",
            "data_acquisition_runs/global_multi_asset_fast_exploratory",
            "multi_asset_lab/fast_exploration_batch1",
            "evidence/active_combo_benchmark/latest",
            "commodity_lab/risk_control_batch1",
            "commodity_lab/risk_control_batch1_verdict_audit",
            "commodity_lab/risk_control_batch1_diagnostics_completion",
            "crypto_lab/tier2_risk_control_batch1",
        ], no_nested_zips, gate_status_matrix()),
    ]
    if include_optional and ((REPO_ROOT / "exploratory/crypto_spot_momentum").exists() or (REPO_ROOT / "evidence/exploratory/crypto_spot_momentum/latest").exists()):
        packets.append(build_packet("05_EXPLORATORY_LANES", [
            "exploratory/crypto_spot_momentum/README.md",
            "exploratory/crypto_spot_momentum/config.yaml",
            "evidence/exploratory/crypto_spot_momentum/latest",
        ], no_nested_zips, exploratory_generated_files()))
    if include_repro_debug and ((REPO_ROOT / "results/latest").exists() or (REPO_ROOT / "evidence/latest").exists()):
        packets.append(build_packet("06_REPRO_DEBUG", [
            "results/latest",
            "evidence/latest",
        ], no_nested_zips, allowlist=REPRO_ALLOWLIST))
    if (REPO_ROOT / "evidence/profit_exploration/latest").exists():
        packets.append(build_packet("07_PROFIT_EXPLORATION", [
            "evidence/profit_exploration/latest",
            "evidence/commodity_exploratory/latest",
            "evidence/commodity_lab/risk_control_batch1/latest",
            "evidence/commodity_lab/risk_control_batch1_verdict_audit/latest",
            "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
            "evidence/crypto_lab/tier2_risk_control_batch1/latest",
            "evidence/data_acquisition_runs/global_multi_asset_fast_exploratory/latest",
            "evidence/multi_asset_lab/fast_exploration_batch1/latest",
        ], no_nested_zips))
    if (REPO_ROOT / "evidence/strategy_candidate_queue/latest").exists():
        packets.append(build_packet("08_STRATEGY_CANDIDATE_QUEUE", [
            "evidence/strategy_candidate_queue/latest",
        ], no_nested_zips))

    missing_required = [missing for packet in packets[:5] for missing in packet.missing_files]
    if strict and missing_required:
        raise SystemExit(f"Required advisor packet sources missing: {missing_required}")

    zip_paths = [finalize_packet(packet, latest_dir, created, no_nested_zips) for packet in packets]
    final_consistency_report = build_consistency_report(advisor_latest=latest_dir, include_advisor_zip_texts=True)
    write_report_outputs(final_consistency_report, latest_dir, write_top_level=False, update_index_zip=True)
    manifest = {
        "created_timestamp_utc": created,
        "repo_path": str(REPO_ROOT),
        "top_level_file_count": len([p for p in latest_dir.iterdir() if p.is_file()]),
        "zip_files": [path.name for path in zip_paths],
        "consistency_status": final_consistency_report.get("consistency_status", ""),
        "consistency_errors_count": final_consistency_report.get("error_count", 0),
        "consistency_warnings_count": final_consistency_report.get("warning_count", 0),
        "missing_files": {packet.name: packet.missing_files for packet in packets if packet.missing_files},
        "raw_data_included": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "notes": "Advisor upload packet generated from existing evidence only; no backtests or downloads were run.",
    }
    (latest_dir / "advisor_upload_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["top_level_file_count"] = len([p for p in latest_dir.iterdir() if p.is_file()])
    (latest_dir / "advisor_upload_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"latest_dir": latest_dir, "zip_paths": zip_paths, "manifest": manifest}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact advisor audit upload packets from existing evidence.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--include-optional", action="store_true", default=True)
    parser.add_argument("--include-repro-debug", action="store_true", default=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--no-nested-zips", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_all_packets(
        Path(args.output_root),
        include_optional=args.include_optional,
        include_repro_debug=args.include_repro_debug,
        strict=args.strict,
        no_nested_zips=args.no_nested_zips,
    )
    print(f"advisor_upload_latest_dir={result['latest_dir']}")
    print(f"advisor_upload_file_count={result['manifest']['top_level_file_count']}")
    print("advisor_upload_zips=" + ",".join(path.name for path in result["zip_paths"]))
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
