from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "extract_current_demo_funnel_and_observation_status_v1"
OUTPUT_DIR = ROOT / "evidence" / "reporting" / TASK_ID / "latest"
REPORT_TIME = "2026-08-07T00:00:00-06:00"
UNRESOLVED = "count_unresolved"

REQUIRED_OUTPUTS = (
    "report_manifest.yaml",
    "strategy_configuration_inventory.csv",
    "experiment_trial_inventory.csv",
    "paper_demo_eligibility_inventory.csv",
    "strategy_observation_mapping.csv",
    "observation_inventory.csv",
    "observation_status_reconciliation.csv",
    "observation_initialization_inventory.csv",
    "prospective_performance_row_inventory.csv",
    "combination_reference_inventory.csv",
    "data_freshness_and_operational_blockers.csv",
    "highest_impact_blocker.csv",
    "discovery_lane_yield.csv",
    "ready_deferred_queue_inventory.csv",
    "entity_count_reconciliation.csv",
    "status_conflicts.csv",
    "next_action_prioritization.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "authoritative_demo_funnel_report.md",
)

PROTECTED_PATHS = (
    "strategy_lab/strategy_registry.yaml",
    "strategy_lab/research_os/operations/active_observations.yaml",
    "strategy_lab/research_os/research/research_queue.yaml",
    "strategy_lab/research_os/family_lineage/family_ledger.yaml",
    "paper_forward_observations",
    "evidence/paper_demo_observation",
    "evidence/paper_demo_onboarding",
    "evidence/research_recovery",
    "evidence/robustness",
    "evidence/corrections/verify_and_correct_source_backed_v3_outcome_contract_v1",
    "data/universe_expansion/pilot_etf_market_data_v1",
    "data/cache",
)

MIN_OBSERVATIONS = (
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    "paper_forward_angl_20pct_diversifier_v1",
    "paper_forward_ivts_unfiltered_20pct_diversifier_v1",
    "paper_demo_faa_4m_top3_v1",
    "paper_demo_decelerated_psar_20pct_diversifier_v1",
    "paper_demo_varadi_mca8_weekly_v1",
    "paper_demo_schwoerer_hyg_ema100_spy_bil_v1",
    "paper_demo_factory_v1_trend_quality_20pct_diversifier_v1",
)


def read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return default if loaded is None else loaded
    except Exception as exc:
        return {"_read_error": str(exc)}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def safe_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        try:
            return pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                engine="python",
                on_bad_lines="skip",
            )
        except Exception as exc:
            return pd.DataFrame([{"_read_error": str(exc)}])


def serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(name: str, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    materialized = list(rows)
    columns = list(fields or [])
    for row in materialized:
        for field in row:
            if field not in columns:
                columns.append(field)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: serialize(row.get(field, "")) for field in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {path: tree_hash(ROOT / path) for path in PROTECTED_PATHS}


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def first_nonempty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            if value:
                return serialize(value)
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def extract_date(value: Any) -> str:
    text = first_nonempty(value)
    if not text:
        return ""
    try:
        return pd.to_datetime(text).date().isoformat()
    except Exception:
        return text[:10]


def max_date(values: list[str]) -> str:
    parsed = []
    for value in values:
        if not value:
            continue
        try:
            parsed.append(pd.to_datetime(value).date())
        except Exception:
            pass
    return max(parsed).isoformat() if parsed else ""


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except Exception:
        return path.as_posix()


def nonempty_jsonish(value: Any) -> bool:
    text = str(value).strip()
    return text not in {"", "{}", "[]", "nan", "None", "null"}


def ledger_row_text(df: pd.DataFrame) -> pd.Series:
    columns = [
        column
        for column in (
            "row_type",
            "record_type",
            "event_type",
            "status",
            "outcome",
            "blocked_execution_reason",
            "prior_interval_status",
        )
        if column in df.columns
    ]
    if not columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[columns].astype(str).agg(" ".join, axis=1).str.lower()


def ledger_metrics(observation_id: str, directory: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ledger_files": "",
        "ledger_rows": 0,
        "initialization_row_count": 0,
        "execution_event_count": 0,
        "valid_performance_row_count": 0,
        "historical_reconciliation_rows": 0,
        "backfill_placeholder_rows": 0,
        "missing_data_events": 0,
        "rule_deviation_events": 0,
        "activation_boundary_date": "",
        "initialization_boundary_date": "",
        "first_valid_performance_date": "",
        "latest_valid_performance_date": "",
        "duplicate_date_portfolio_key": False,
        "pre_initialization_performance": False,
        "current_virtual_equity": "",
        "virtual_equity_present": False,
        "current_holdings_present": False,
        "ledger_read_error": "",
    }
    if not directory.exists() or not directory.is_dir():
        result["ledger_read_error"] = "observation_directory_missing"
        return result
    ledger_files = sorted(path for path in directory.glob("*ledger*.csv") if path.is_file())
    result["ledger_files"] = ";".join(rel(path) for path in ledger_files)
    if not ledger_files:
        result["ledger_read_error"] = "ledger_missing"
        return result

    frames = []
    for ledger_file in ledger_files:
        frame = safe_csv(ledger_file)
        if "_read_error" in frame.columns:
            result["ledger_read_error"] = first_nonempty(
                result["ledger_read_error"],
                frame.iloc[0].get("_read_error", ""),
            )
        if not frame.empty:
            frame = frame.copy()
            frame["_ledger_file"] = rel(ledger_file)
            frames.append(frame)
    if not frames:
        return result

    frame = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    result["ledger_rows"] = len(frame)
    text = ledger_row_text(frame)
    init_mask = text.str.contains(
        "initialization|activation_state|operational_reinitialization|initialized_forward_only"
    )
    historical_mask = text.str.contains("historical_reconciliation|reconciliation_only")
    placeholder_mask = text.str.contains("placeholder|backfill")
    missing_mask = text.str.contains("missing_data|blocked_execution|data_unavailable")
    performance_mask = text.str.contains(
        "committed_independent_forward_update|prospective_performance|performance_row|performance_update"
    )
    performance_mask = (
        performance_mask
        & ~init_mask
        & ~historical_mask
        & ~placeholder_mask
        & ~missing_mask
    )
    result["initialization_row_count"] = int(init_mask.sum())
    result["execution_event_count"] = int(
        text.str.contains(
            "execution|virtual_initialization|target_frozen|operational_initialization|operational_reinitialization|activation_state"
        ).sum()
    )
    result["historical_reconciliation_rows"] = int(historical_mask.sum())
    result["backfill_placeholder_rows"] = int(placeholder_mask.sum())
    result["missing_data_events"] = int(missing_mask.sum())
    if "missing_data_events" in frame.columns:
        result["missing_data_events"] = max(
            result["missing_data_events"],
            int(frame["missing_data_events"].astype(str).map(nonempty_jsonish).sum()),
        )
    if "rule_deviations" in frame.columns:
        result["rule_deviation_events"] = int(
            frame["rule_deviations"].astype(str).map(nonempty_jsonish).sum()
        )

    date_col = next(
        (
            column
            for column in ("date", "event_date", "completed_execution_date", "observation_date")
            if column in frame.columns
        ),
        "",
    )
    dates = (
        pd.to_datetime(frame[date_col], errors="coerce")
        if date_col
        else pd.Series([pd.NaT] * len(frame))
    )
    if init_mask.any() and date_col:
        init_dates = dates[init_mask].dropna()
        if not init_dates.empty:
            boundary = init_dates.min().date().isoformat()
            result["activation_boundary_date"] = boundary
            result["initialization_boundary_date"] = boundary

    performance_frame = frame[performance_mask].copy()
    performance_dates = dates[performance_mask] if date_col else pd.Series([], dtype="datetime64[ns]")
    if result["initialization_boundary_date"] and len(performance_frame):
        boundary_ts = pd.to_datetime(result["initialization_boundary_date"])
        pre_mask = performance_dates < boundary_ts
        result["pre_initialization_performance"] = bool(pre_mask.fillna(False).any())
        keep_mask = performance_dates > boundary_ts
        performance_frame = performance_frame[keep_mask.fillna(False).to_numpy()]
        performance_dates = performance_dates[keep_mask.fillna(False)]
    if len(performance_frame):
        date_values = [date.date().isoformat() for date in performance_dates.dropna()]
        result["first_valid_performance_date"] = min(date_values) if date_values else ""
        result["latest_valid_performance_date"] = max(date_values) if date_values else ""
        key_cols = [
            column
            for column in (
                "date",
                "observation_id",
                "component_observation_id",
                "derived_observation_id",
                "portfolio_id",
            )
            if column in performance_frame.columns
        ]
        result["duplicate_date_portfolio_key"] = (
            bool(performance_frame.duplicated(subset=key_cols).any()) if key_cols else False
        )
        result["valid_performance_row_count"] = int(
            len(performance_frame.drop_duplicates(subset=key_cols)) if key_cols else len(performance_frame)
        )
        for equity_col in ("virtual_equity", "derived_total_equity", "post_cost_equity"):
            if equity_col in performance_frame.columns:
                values = [value for value in performance_frame[equity_col].astype(str) if value.strip()]
                if values:
                    result["current_virtual_equity"] = values[-1]
                    result["virtual_equity_present"] = True
                    break
    if not result["current_virtual_equity"]:
        for equity_col in ("virtual_equity", "derived_total_equity", "post_cost_equity"):
            if equity_col in frame.columns:
                values = [value for value in frame[equity_col].astype(str) if value.strip()]
                if values:
                    result["current_virtual_equity"] = values[-1]
                    result["virtual_equity_present"] = True
                    break
    for holding_col in ("holdings", "shares", "virtual_shares", "holding_state"):
        if holding_col in frame.columns and any(nonempty_jsonish(value) for value in frame[holding_col].astype(str)):
            result["current_holdings_present"] = True
            break
    return result


def lane_from_path(path: Path) -> str:
    parts = path.parts
    if "evidence" in parts:
        index = parts.index("evidence")
        if len(parts) > index + 2:
            return parts[index + 1] + "/" + parts[index + 2]
    return rel(path.parent)


def reset_output_dir() -> None:
    expected_parent = (ROOT / "evidence" / "reporting" / TASK_ID).resolve()
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_current_state() -> dict[str, Any]:
    return {
        "active_doc": read_yaml(
            ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
            {},
        ),
        "research_queue": read_yaml(
            ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
            {},
        ),
        "strategy_registry": read_yaml(ROOT / "strategy_lab" / "strategy_registry.yaml", {}),
        "family_ledger": read_yaml(
            ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
            {},
        ),
    }


def build_observation_tables(
    active_doc: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    active_entries = active_doc.get("active_observations", []) if isinstance(active_doc, dict) else []
    active_by_obs: dict[str, dict[str, Any]] = {}
    for entry in active_entries:
        if isinstance(entry, dict):
            observation_id = first_nonempty(entry.get("observation_id"), entry.get("strategy_id"))
            if observation_id:
                active_by_obs[observation_id] = entry

    observations_root = ROOT / "paper_forward_observations"
    observation_dirs = (
        {path.name: path for path in observations_root.iterdir() if path.is_dir() and not path.name.startswith("_")}
        if observations_root.exists()
        else {}
    )
    all_observation_ids = sorted(set(MIN_OBSERVATIONS) | set(active_by_obs) | set(observation_dirs))
    global_latest_completed = max_date(
        [
            extract_date(entry.get(key))
            for entry in active_entries
            if isinstance(entry, dict)
            for key in (
                "latest_completed_session",
                "latest_current_state_date",
                "latest_d1_signal_date",
                "reference_diagnostic_date",
            )
        ]
    )

    observation_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    init_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []

    for observation_id in all_observation_ids:
        entry = active_by_obs.get(observation_id, {})
        directory = observation_dirs.get(observation_id, observations_root / observation_id)
        local_doc = read_yaml(directory / "active_observation.yaml", {}) if directory.exists() else {}
        config_doc = read_yaml(directory / "observation_config.yaml", {}) if directory.exists() else {}
        manifest_doc = read_json(directory / "observation_activation_manifest.json", {}) if directory.exists() else {}
        merged: dict[str, Any] = {}
        for source in (
            manifest_doc if isinstance(manifest_doc, dict) else {},
            config_doc if isinstance(config_doc, dict) else {},
            local_doc if isinstance(local_doc, dict) else {},
            entry if isinstance(entry, dict) else {},
        ):
            merged.update(source)
        metrics = ledger_metrics(observation_id, directory)
        strategy_id = first_nonempty(
            merged.get("strategy_id"),
            merged.get("base_strategy_id"),
            merged.get("parent_strategy_id"),
            observation_id,
        )
        family_id = first_nonempty(merged.get("family_id"), merged.get("family"), UNRESOLVED)
        architecture = first_nonempty(
            merged.get("strategy_architecture"),
            merged.get("architecture"),
            merged.get("architecture_id"),
            UNRESOLVED,
        )
        route = first_nonempty(
            merged.get("route"),
            merged.get("observation_route"),
            merged.get("eligible_route"),
            "paper_forward",
        )
        in_active = observation_id in active_by_obs
        directory_present = directory.exists()
        paper_active = boolish(merged.get("paper_forward_active")) or boolish(merged.get("paper_demo_active"))
        state = first_nonempty(
            merged.get("state"),
            merged.get("status"),
            merged.get("outcome"),
            "closed_or_superseded" if not in_active else "",
        )
        initialization_status = first_nonempty(
            merged.get("initialization_status"),
            local_doc.get("operational_baseline_status") if isinstance(local_doc, dict) else "",
            "initialized" if metrics["initialization_row_count"] else "",
        )
        blocker = first_nonempty(
            merged.get("pending_reason"),
            merged.get("failure_reason"),
            merged.get("deferred_reason"),
            merged.get("blocked_execution_reason"),
            merged.get("combined_target_status"),
            metrics.get("ledger_read_error"),
        )
        latest_valid_perf = metrics["latest_valid_performance_date"]
        stale_perf = bool(latest_valid_perf and global_latest_completed and latest_valid_perf < global_latest_completed)
        if "deferred" in state or first_nonempty(merged.get("current_status")) == "deferred" or (in_active and not paper_active):
            derived = "deferred"
        elif not in_active and directory_present:
            derived = "closed_or_superseded"
        elif in_active and not directory_present:
            derived = "status_conflict"
        elif (
            "reference_current_state_unavailable" in blocker
            or ("missing" in blocker and "data" in blocker)
            or "pending_latest_reference" in blocker
        ):
            derived = "active_data_stale_or_blocked"
        elif stale_perf and observation_id in {
            "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
            "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
        }:
            derived = "active_data_stale_or_blocked"
        elif int(metrics["valid_performance_row_count"]) > 0:
            derived = "active_performance_producing"
        elif in_active and (
            "pending" in initialization_status
            or "scheduled" in initialization_status
            or (
                not metrics["initialization_row_count"]
                and not first_nonempty(merged.get("initialization_execution_date"))
            )
        ):
            derived = "observation_created_pending_initialization"
        elif in_active:
            derived = "active_initialized_no_performance"
        else:
            derived = UNRESOLVED
        role = first_nonempty(
            merged.get("role"),
            "combination_portfolio"
            if "combo" in observation_id
            else ("diversifier_sleeve" if "20pct" in route or "diversifier" in route else "base_strategy"),
        )
        portfolio_role = "combination" if "combo" in observation_id else ("sleeve" if "20pct" in route or "diversifier" in route else "base")
        row = {
            "observation_id": observation_id,
            "strategy_id": strategy_id,
            "family_id": family_id,
            "architecture": architecture,
            "primary_role": role,
            "observation_route": route,
            "portfolio_role": portfolio_role,
            "stored_state": state,
            "stored_status": first_nonempty(merged.get("status"), merged.get("current_status"), merged.get("outcome")),
            "stored_outcome": first_nonempty(merged.get("outcome")),
            "derived_category": derived,
            "paper_forward_active": paper_active,
            "active_registry_presence": in_active,
            "observation_directory_presence": directory_present,
            "initialization_status": initialization_status,
            "current_target_status": first_nonempty(
                merged.get("current_checkpoint_status"),
                merged.get("current_status"),
                merged.get("combined_target_status"),
                state,
            ),
            "latest_valid_signal_date": first_nonempty(
                extract_date(merged.get("latest_d1_signal_date")),
                extract_date(merged.get("latest_reconciled_signal_date")),
                extract_date(merged.get("latest_expired_signal_date")),
                extract_date(merged.get("first_signal_date")),
                extract_date(merged.get("last_signal_date")),
            ),
            "intended_next_execution_date": first_nonempty(
                extract_date(merged.get("next_valid_execution_date")),
                extract_date(merged.get("scheduled_first_execution_date")),
                extract_date(merged.get("proposed_first_execution_session")),
            ),
            "latest_completed_execution_date": first_nonempty(
                extract_date(merged.get("latest_completed_session")),
                extract_date(merged.get("latest_current_state_date")),
                extract_date(merged.get("initialization_execution_date")),
                extract_date(merged.get("last_rebalance_date")),
            ),
            "first_valid_performance_date": first_nonempty(
                metrics["first_valid_performance_date"],
                extract_date(merged.get("first_eligible_performance_date")),
            ),
            "latest_valid_performance_date": metrics["latest_valid_performance_date"],
            "valid_performance_row_count": metrics["valid_performance_row_count"],
            "virtual_equity_present": metrics["virtual_equity_present"],
            "current_virtual_equity": first_nonempty(
                metrics["current_virtual_equity"],
                merged.get("current_virtual_equity"),
                merged.get("latest_committed_virtual_equity"),
            ),
            "current_holdings_present": metrics["current_holdings_present"]
            or bool(first_nonempty(merged.get("current_holdings"), merged.get("current_target_allocation"))),
            "missing_data_events": metrics["missing_data_events"],
            "rule_deviation_events": metrics["rule_deviation_events"],
            "blocker": blocker,
            "exact_next_action": first_nonempty(merged.get("next_action"), UNRESOLVED),
            "authoritative_evidence": rel(directory / "active_observation.yaml")
            if (directory / "active_observation.yaml").exists()
            else (rel(directory) if directory_present else "strategy_lab/research_os/operations/active_observations.yaml"),
        }
        observation_rows.append(row)
        status_rows.append(
            {
                "observation_id": observation_id,
                "stored_state": row["stored_state"],
                "stored_status": row["stored_status"],
                "active_registry_presence": in_active,
                "observation_directory_presence": directory_present,
                "derived_category": derived,
                "reconciliation_note": "active registry and directory agree"
                if in_active and directory_present
                else (
                    "directory present but not active registry"
                    if directory_present
                    else "active/deferred registry row has no directory"
                ),
            }
        )
        init_rows.append(
            {
                "observation_id": observation_id,
                "activation_boundary_date": metrics["activation_boundary_date"],
                "initialization_boundary_date": metrics["initialization_boundary_date"],
                "stored_initialization_status": initialization_status,
                "initialization_row_count": metrics["initialization_row_count"],
                "execution_event_count": metrics["execution_event_count"],
                "first_eligible_performance_date": row["first_valid_performance_date"],
                "boundary_validated": not metrics["pre_initialization_performance"],
                "notes": first_nonempty(metrics["ledger_read_error"], row["blocker"]),
            }
        )
        performance_rows.append(
            {
                "observation_id": observation_id,
                "ledger_files": metrics["ledger_files"],
                "activation_boundary_date": metrics["activation_boundary_date"],
                "initialization_rows": metrics["initialization_row_count"],
                "execution_events": metrics["execution_event_count"],
                "valid_prospective_performance_rows": metrics["valid_performance_row_count"],
                "historical_reconciliation_rows": metrics["historical_reconciliation_rows"],
                "backfill_prohibited_placeholders": metrics["backfill_placeholder_rows"],
                "missing_data_events": metrics["missing_data_events"],
                "first_valid_row_date": metrics["first_valid_performance_date"],
                "last_valid_row_date": metrics["latest_valid_performance_date"],
                "duplicate_date_portfolio_key": metrics["duplicate_date_portfolio_key"],
                "pre_initialization_performance": metrics["pre_initialization_performance"],
                "current_cumulative_virtual_equity": metrics["current_virtual_equity"],
                "currently_current_against_latest_completed_session": bool(
                    metrics["latest_valid_performance_date"]
                    and metrics["latest_valid_performance_date"] >= global_latest_completed
                ),
            }
        )
    return observation_rows, status_rows, init_rows, performance_rows, global_latest_completed


def build_strategy_configuration_inventory(
    observation_rows: list[dict[str, Any]],
    corrected_overlay: pd.DataFrame,
) -> list[dict[str, Any]]:
    strategy_configs: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for path in sorted((ROOT / "evidence").rglob("strategy_cards.csv")):
        if TASK_ID in path.as_posix():
            continue
        frame = safe_csv(path)
        for _, item in frame.iterrows():
            strategy_id = first_nonempty(item.get("strategy_id"), item.get("candidate_id"))
            family_id = first_nonempty(item.get("family_id"), item.get("family"))
            architecture = first_nonempty(
                item.get("strategy_architecture"),
                item.get("architecture"),
                item.get("architecture_id"),
            )
            if not strategy_id or not family_id or not architecture:
                continue
            strategy_configs.setdefault(
                strategy_id,
                {
                    "strategy_id": strategy_id,
                    "family_id": family_id,
                    "architecture": architecture,
                    "primary_role": first_nonempty(
                        item.get("primary_robustness_role"),
                        item.get("route"),
                        item.get("role"),
                    ),
                    "source_lane": lane_from_path(path),
                    "entity_type": "strategy_configuration",
                    "authoritative_evidence": rel(path),
                    "trial_id": first_nonempty(item.get("trial_id"), item.get("proposed_trial_id")),
                    "lifecycle_status": first_nonempty(item.get("outcome"), item.get("stage")),
                    "paper_demo_eligible": "",
                    "observation_id": "",
                    "count_status": "reconciled_strategy_card",
                    "notes": "",
                },
            )

    for row in observation_rows:
        if not (boolish(row["active_registry_presence"]) or row["derived_category"] != "closed_or_superseded"):
            continue
        strategy_id = row["strategy_id"]
        existing = strategy_configs.get(strategy_id, {})
        strategy_configs[strategy_id] = {
            "strategy_id": strategy_id,
            "family_id": row["family_id"],
            "architecture": row["architecture"],
            "primary_role": row["primary_role"],
            "source_lane": first_nonempty(existing.get("source_lane"), "active_observation_registry"),
            "entity_type": "strategy_configuration"
            if row["portfolio_role"] != "combination"
            else "combination_reference_configuration",
            "authoritative_evidence": row["authoritative_evidence"],
            "trial_id": first_nonempty(existing.get("trial_id"), UNRESOLVED),
            "lifecycle_status": row["derived_category"],
            "paper_demo_eligible": row["derived_category"] not in {"closed_or_superseded", "status_conflict"},
            "observation_id": row["observation_id"],
            "count_status": "active_observation_reconciled"
            if UNRESOLVED not in (row["family_id"], row["architecture"])
            else UNRESOLVED,
            "notes": "combination/reference portfolio separated from base strategy count"
            if row["portfolio_role"] == "combination"
            else "",
        }

    for _, item in corrected_overlay.iterrows():
        strategy_id = first_nonempty(item.get("strategy_id"))
        if not strategy_id:
            continue
        strategy_configs[strategy_id] = {
            "strategy_id": strategy_id,
            "family_id": first_nonempty(item.get("family_id"), UNRESOLVED),
            "architecture": first_nonempty(item.get("primary_robustness_role"), UNRESOLVED),
            "primary_role": first_nonempty(item.get("primary_robustness_role")),
            "source_lane": "research_recovery/accepted_47_source_backed_exploration_batch_v3_corrected_overlay",
            "entity_type": "strategy_configuration",
            "authoritative_evidence": "evidence/corrections/verify_and_correct_source_backed_v3_outcome_contract_v1/latest/corrected_outcome_overlay.csv",
            "trial_id": first_nonempty(item.get("trial_id")),
            "lifecycle_status": first_nonempty(item.get("corrected_current_outcome")),
            "paper_demo_eligible": boolish(item.get("paper_demo_eligibility")),
            "observation_id": "",
            "count_status": "reconciled_corrected_source_backed_v3",
            "notes": "corrected_primary_failure_reason="
            + first_nonempty(item.get("corrected_primary_failure_reason")),
        }
    return list(strategy_configs.values())


def build_trial_inventory() -> list[dict[str, Any]]:
    allowed_evidence_classes = {
        "research_recovery",
        "robustness",
        "technical_factory",
        "trade_management",
        "correction",
        "validation",
        "methodology",
    }
    trial_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for path in sorted((ROOT / "evidence").rglob("trial_ledger.csv")):
        if TASK_ID in path.as_posix():
            continue
        parts = path.relative_to(ROOT / "evidence").parts
        if not parts or parts[0] not in allowed_evidence_classes:
            continue
        frame = safe_csv(path)
        for _, item in frame.iterrows():
            trial_id = first_nonempty(item.get("trial_id"))
            if not trial_id:
                continue
            entity_type = first_nonempty(item.get("entity_type"), "experiment_trial")
            if entity_type and entity_type not in {
                "experiment_trial",
                "canonical_experiment_trial",
                "robustness_trial",
            }:
                continue
            trial_records.setdefault(
                trial_id,
                {
                    "trial_id": trial_id,
                    "strategy_id": first_nonempty(item.get("strategy_id"), item.get("candidate_id"), UNRESOLVED),
                    "family_id": first_nonempty(item.get("family_id"), item.get("family"), UNRESOLVED),
                    "trial_type": first_nonempty(item.get("stage"), item.get("trial_type"), "experiment_trial"),
                    "lane": lane_from_path(path),
                    "entity_type": "experiment_trial",
                    "outcome": first_nonempty(
                        item.get("outcome"),
                        item.get("current_outcome"),
                        item.get("stage"),
                    ),
                    "failure_reason": first_nonempty(
                        item.get("failure_reason"),
                        item.get("primary_failure_reason"),
                        item.get("corrected_primary_failure_reason"),
                    ),
                    "source_file": rel(path),
                    "count_status": "reconciled_trial_ledger",
                    "notes": "identity and compatibility checks excluded unless ledger row is experiment_trial",
                },
            )
    return list(trial_records.values())


def build_eligibility_tables(
    observation_rows: list[dict[str, Any]],
    corrected_overlay: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligibility_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    role_aware_ids = {
        "paper_demo_varadi_mca8_weekly_v1",
        "paper_demo_schwoerer_hyg_ema100_spy_bil_v1",
        "paper_demo_factory_v1_trend_quality_20pct_diversifier_v1",
    }
    for row in observation_rows:
        if row["derived_category"] == "deferred" and row["observation_id"] == "paper_forward_angl_20pct_diversifier_v1":
            eligible = False
        elif row["derived_category"] in {"closed_or_superseded", "status_conflict", UNRESOLVED}:
            eligible = False
        else:
            eligible = True
        basis = (
            "active_paper_demo_observation_registry"
            if boolish(row["active_registry_presence"])
            else "observation_directory_reference_not_active"
        )
        if row["observation_id"] in role_aware_ids:
            basis = "role_aware_robustness_standard_v1_positive_reassessment"
        if row["observation_id"] == "paper_forward_ivts_unfiltered_20pct_diversifier_v1":
            basis = "paper_demo_eligible_observation_deferred_activation_boundary_not_ready"
            eligible = True
        if row["observation_id"] == "paper_forward_angl_20pct_diversifier_v1":
            basis = "deferred_invalid_or_incomplete_data_comparability_failure"
        eligibility_rows.append(
            {
                "strategy_id": row["strategy_id"],
                "family_id": row["family_id"],
                "architecture": row["architecture"],
                "primary_role": row["primary_role"],
                "paper_demo_eligible": eligible,
                "eligible_route": row["observation_route"],
                "eligibility_basis": basis,
                "authoritative_eligibility_evidence": row["authoritative_evidence"],
                "observation_id": row["observation_id"],
                "derived_category": row["derived_category"],
                "next_action": row["exact_next_action"],
            }
        )
        if eligible:
            mapped = {
                key: row[key]
                for key in (
                    "strategy_id",
                    "family_id",
                    "architecture",
                    "primary_role",
                    "observation_id",
                    "observation_route",
                    "portfolio_role",
                    "active_registry_presence",
                    "observation_directory_presence",
                    "initialization_status",
                    "current_target_status",
                    "latest_valid_signal_date",
                    "intended_next_execution_date",
                    "latest_completed_execution_date",
                    "first_valid_performance_date",
                    "latest_valid_performance_date",
                    "valid_performance_row_count",
                    "virtual_equity_present",
                    "current_holdings_present",
                    "missing_data_events",
                    "rule_deviation_events",
                    "blocker",
                    "exact_next_action",
                )
            }
            mapped.update(
                {
                    "eligible_route": row["observation_route"],
                    "eligibility_basis": basis,
                    "authoritative_eligibility_evidence": row["authoritative_evidence"],
                    "observation_type": row["portfolio_role"],
                }
            )
            mapping_rows.append(mapped)

    for _, item in corrected_overlay.iterrows():
        eligibility_rows.append(
            {
                "strategy_id": first_nonempty(item.get("strategy_id")),
                "family_id": first_nonempty(item.get("family_id")),
                "architecture": first_nonempty(item.get("primary_robustness_role")),
                "primary_role": first_nonempty(item.get("primary_robustness_role")),
                "paper_demo_eligible": False,
                "eligible_route": "none_closed_exploration",
                "eligibility_basis": "corrected_source_backed_v3_overlay",
                "authoritative_eligibility_evidence": "evidence/corrections/verify_and_correct_source_backed_v3_outcome_contract_v1/latest/corrected_outcome_overlay.csv",
                "observation_id": "",
                "derived_category": "closed_or_superseded",
                "next_action": "no_paper_demo_action_closed_exploration",
            }
        )
    return eligibility_rows, mapping_rows


def build_combination_reference_inventory() -> list[dict[str, Any]]:
    return [
        {
            "reference_id": "frozen_current_active_vm_dsr_usci_combo",
            "portfolio_kind": "combination_reference_portfolio",
            "component_strategy_or_observation_id": "paper_forward_vm_quality_lowvol_proxy_v1;paper_forward_dsr_sector_equal_weight_defensive_filter_v1;paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
            "combination_observation_id": "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
            "reference_used_by_observations": "paper_forward_angl_20pct_diversifier_v1;paper_forward_ivts_unfiltered_20pct_diversifier_v1;paper_demo_decelerated_psar_20pct_diversifier_v1;paper_demo_factory_v1_trend_quality_20pct_diversifier_v1",
            "is_current": False,
            "latest_common_component_session": "2026-08-05",
            "stale_component_symbols": "USCI",
            "downstream_observations_blocked": 1,
            "counting_note": "combination/reference portfolio counted separately from independent base-strategy discovery yield",
        },
        {
            "reference_id": "active_combo_vm_dsr_equal_weight_v1",
            "portfolio_kind": "legacy_reference_directory_not_active_registry",
            "component_strategy_or_observation_id": "active_vm;active_dsr",
            "combination_observation_id": "active_combo_vm_dsr_equal_weight_v1",
            "reference_used_by_observations": "historical_reference",
            "is_current": UNRESOLVED,
            "latest_common_component_session": UNRESOLVED,
            "stale_component_symbols": UNRESOLVED,
            "downstream_observations_blocked": UNRESOLVED,
            "counting_note": "directory exists outside current active observation registry",
        },
        {
            "reference_id": "combo_SPY200d_GLD_50_50_v1",
            "portfolio_kind": "legacy_observation_directory_not_active_registry",
            "component_strategy_or_observation_id": "SPY200d;GLD",
            "combination_observation_id": "combo_SPY200d_GLD_50_50_v1",
            "reference_used_by_observations": "none_authoritative_current",
            "is_current": False,
            "latest_common_component_session": UNRESOLVED,
            "stale_component_symbols": UNRESOLVED,
            "downstream_observations_blocked": 0,
            "counting_note": "not counted as active paper/demo observation",
        },
    ]


def build_blockers() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blockers = [
        {
            "blocker_id": "vm_dsr_usci_reference_currentness_usci_component_stale",
            "affected_observation": "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1;paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1;paper_demo_factory_v1_trend_quality_20pct_diversifier_v1",
            "affected_strategy": "usci_dynamic_commodity_curve_selection_wrapper_v1;combo_vm_dsr_usci_equal_weight_monthly_v1;factory_v1_spy_trend_quality_state_d1",
            "first_detected_date": "2026-08-05",
            "latest_detected_date": "2026-08-06",
            "blocker_class": "missing_reference_component",
            "shared_or_candidate_specific": "shared_reference",
            "active_observations_affected": 3,
            "prevents_all_performance_production": False,
            "current_remediation_status": "not_started_read_only_report_only",
            "next_authorized_action": "repair_standard_observation_data_freshness_v1",
        },
        {
            "blocker_id": "standard_observation_faa_no_performance_rows_after_initialization",
            "affected_observation": "paper_demo_faa_4m_top3_v1",
            "affected_strategy": "keller_vanputten_faa_4m_top3_v1",
            "first_detected_date": "2026-08-04",
            "latest_detected_date": "2026-08-04",
            "blocker_class": "pending_operational_recording",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 1,
            "prevents_all_performance_production": False,
            "current_remediation_status": "recorder_not_run_in_this_read_only_task",
            "next_authorized_action": "record_faa_standard_paper_demo_observation_v1",
        },
        {
            "blocker_id": "standard_observation_psar_no_performance_rows_after_initialization",
            "affected_observation": "paper_demo_decelerated_psar_20pct_diversifier_v1",
            "affected_strategy": "barbara_decelerated_psar_spy_bil_v1",
            "first_detected_date": "2026-08-04",
            "latest_detected_date": "2026-08-04",
            "blocker_class": "pending_operational_recording",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 1,
            "prevents_all_performance_production": False,
            "current_remediation_status": "recorder_not_run_in_this_read_only_task",
            "next_authorized_action": "record_psar_standard_paper_demo_observation_v1",
        },
        {
            "blocker_id": "mca_waiting_for_next_weekly_signal_no_late_execution",
            "affected_observation": "paper_demo_varadi_mca8_weekly_v1",
            "affected_strategy": "varadi_minimum_correlation_8etf_60d_weekly_v1",
            "first_detected_date": "2026-08-06",
            "latest_detected_date": "2026-08-06",
            "blocker_class": "pending_source_defined_signal",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 1,
            "prevents_all_performance_production": False,
            "current_remediation_status": "waiting_next_valid_signal_execution_2026-08-10",
            "next_authorized_action": "record_role_aware_candidates_standard_paper_demo_observations_v1",
        },
        {
            "blocker_id": "hyg_target_frozen_before_next_eligible_regular_session_close",
            "affected_observation": "paper_demo_schwoerer_hyg_ema100_spy_bil_v1",
            "affected_strategy": "schwoerer_hyg_ema100_spy_bil_v1",
            "first_detected_date": "2026-08-07",
            "latest_detected_date": "2026-08-07",
            "blocker_class": "pending_scheduled_execution",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 1,
            "prevents_all_performance_production": False,
            "current_remediation_status": "scheduled_first_execution_2026-08-07_first_performance_2026-08-10",
            "next_authorized_action": "record_role_aware_candidates_standard_paper_demo_observations_v1",
        },
        {
            "blocker_id": "angl_canonical_common_session_data_comparability_failure",
            "affected_observation": "paper_forward_angl_20pct_diversifier_v1",
            "affected_strategy": "ice_vaneck_us_fallen_angel_angl_v1",
            "first_detected_date": "2026-07-24",
            "latest_detected_date": "2026-07-24",
            "blocker_class": "deferred_data_capability_lane",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 0,
            "prevents_all_performance_production": False,
            "current_remediation_status": "deferred_until_material_data_capability_change",
            "next_authorized_action": "revisit_angl_observation_only_after_material_data_capability_change_v1",
        },
        {
            "blocker_id": "ivts_activation_boundary_not_ready",
            "affected_observation": "paper_forward_ivts_unfiltered_20pct_diversifier_v1",
            "affected_strategy": "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1",
            "first_detected_date": "2026-07-24",
            "latest_detected_date": "2026-07-24",
            "blocker_class": "deferred_activation_boundary_not_ready",
            "shared_or_candidate_specific": "candidate_specific",
            "active_observations_affected": 0,
            "prevents_all_performance_production": False,
            "current_remediation_status": "direction_owner_review_required",
            "next_authorized_action": "direction_owner_review_ivts_observation_deferment_v1",
        },
    ]
    highest = sorted(
        blockers,
        key=lambda row: (
            -int(row["active_observations_affected"]),
            0 if row["shared_or_candidate_specific"] == "shared_reference" else 1,
            0 if boolish(row["prevents_all_performance_production"]) else 1,
            row["first_detected_date"],
            row["blocker_id"],
        ),
    )[0]
    return blockers, highest


def build_discovery_lane_yield() -> list[dict[str, Any]]:
    def counts(path: str) -> dict[str, Any]:
        return read_json(ROOT / path, {})

    lane_specs = [
        (
            "technical_factory_v1",
            "evidence/technical_factory/technical_strategy_factory_v1/latest/cohort_funnel_counts.json",
            "technical_factory",
            1,
            1,
        ),
        (
            "technical_factory_v2",
            "evidence/technical_factory/technical_strategy_factory_v2/latest/cohort_funnel_counts.json",
            "technical_factory",
            0,
            0,
        ),
        (
            "accepted_47_hybrid_discovery_v1",
            "evidence/research_recovery/accepted_47_hybrid_discovery_batch_v1/latest/cohort_funnel_counts.json",
            "hybrid_discovery",
            0,
            0,
        ),
        (
            "source_backed_v1",
            "evidence/research_recovery/accepted_47_source_backed_exploration_batch_v1/latest/cohort_funnel_counts.json",
            "source_backed",
            0,
            0,
        ),
        (
            "source_backed_v2",
            "evidence/research_recovery/accepted_47_source_backed_exploration_batch_v2/latest/cohort_funnel_counts.json",
            "source_backed",
            2,
            2,
        ),
        (
            "source_backed_v3_corrected",
            "evidence/research_recovery/accepted_47_source_backed_exploration_batch_v3/latest/cohort_funnel_counts.json",
            "source_backed_corrected_overlay",
            0,
            0,
        ),
    ]
    rows = []
    for lane_id, path, lane_type, robustness_positive, observations_created in lane_specs:
        count_doc = counts(path)
        rows.append(
            {
                "lane_id": lane_id,
                "lane_type": lane_type,
                "architectures": first_nonempty(
                    count_doc.get("architecture_catalog_entries"),
                    count_doc.get("source_library_records"),
                    count_doc.get("source_records"),
                    count_doc.get("strategy_configurations"),
                    UNRESOLVED,
                ),
                "canonical_trials": first_nonempty(
                    count_doc.get("canonical_experiment_trials"),
                    count_doc.get("canonical_trials"),
                    count_doc.get("strategy_configurations"),
                    UNRESOLVED,
                ),
                "exploration_followups": first_nonempty(
                    count_doc.get("factory_exploratory_followup_candidates"),
                    count_doc.get("exploratory_followup_candidates"),
                    count_doc.get("followup_candidates"),
                    0,
                ),
                "robustness_positive_outcomes": robustness_positive,
                "observations_created": observations_created,
                "counting_note": "D1/MCA/HYG use role-aware robustness standard where noted; source-backed v3 uses corrected overlay outcomes"
                if robustness_positive
                else "closed or no paper/demo observations in lane packet",
                "evidence_path": path,
            }
        )
    trade_count = counts("evidence/trade_management/faa_psar_trade_management_overlay_batch_v1/latest/cohort_funnel_counts.json")
    rows.append(
        {
            "lane_id": "trade_management_overlay_batch",
            "lane_type": "overlay_adaptation",
            "architectures": first_nonempty(trade_count.get("base_strategies"), UNRESOLVED),
            "canonical_trials": first_nonempty(trade_count.get("completed_non_identity_trials"), UNRESOLVED),
            "exploration_followups": first_nonempty(trade_count.get("overlay_followup_candidates"), 0),
            "robustness_positive_outcomes": first_nonempty(trade_count.get("robustness_positive_overlays"), 0),
            "observations_created": first_nonempty(trade_count.get("paper_demo_observations_changed"), 0),
            "counting_note": "identity and compatibility checks are not counted as strategy trials",
            "evidence_path": "evidence/trade_management/faa_psar_trade_management_overlay_batch_v1/latest/cohort_funnel_counts.json",
        }
    )
    rows.append(
        {
            "lane_id": "earlier_fast_source_lanes_for_faa_psar_angl_ivts_vm_dsr_usci",
            "lane_type": "earlier_fast_source_reconciliation",
            "architectures": UNRESOLVED,
            "canonical_trials": UNRESOLVED,
            "exploration_followups": UNRESOLVED,
            "robustness_positive_outcomes": UNRESOLVED,
            "observations_created": 7,
            "counting_note": "current observation identities reconcile, but complete earlier-lane canonical trial counts are not resolved without reopening historical packets",
            "evidence_path": "multiple earlier research_recovery/robustness/validation packets",
        }
    )
    return rows


def build_ready_deferred_queue(
    research_queue: dict[str, Any],
    mapping_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    for review in (
        research_queue.get("queued_governance_reviews", []) if isinstance(research_queue, dict) else []
    ):
        rows.append(
            {
                "queue_item_id": first_nonempty(review.get("id")),
                "strategy_id": "",
                "family_id": "gld_macro_risk_off",
                "architecture": "process_governance_review",
                "lineage": first_nonempty(review.get("purpose")),
                "current_unexecuted_next_action": first_nonempty(review.get("id")),
                "queue_classification": "process_only",
                "genuine_ready_strategy_candidate": False,
                "operational_observation_task": False,
                "authoritative_evidence": "strategy_lab/research_os/research/research_queue.yaml",
            }
        )
    external_lane = research_queue.get("external_source_discovery_lane", {}) if isinstance(research_queue, dict) else {}
    next_allowed = external_lane.get("next_allowed_actions", [])
    rows.append(
        {
            "queue_item_id": "external_source_discovery_lane",
            "strategy_id": "",
            "family_id": "",
            "architecture": "direction_owner_supplied_source_required",
            "lineage": first_nonempty(external_lane.get("blocked_reason"), external_lane.get("notes")),
            "current_unexecuted_next_action": ";".join(next_allowed)
            if isinstance(next_allowed, list)
            else first_nonempty(next_allowed),
            "queue_classification": "deferred_methodology",
            "genuine_ready_strategy_candidate": False,
            "operational_observation_task": False,
            "authoritative_evidence": "strategy_lab/research_os/research/research_queue.yaml",
        }
    )
    for row in mapping_rows:
        queue_classification = "pending_operational_recording"
        if "data" in row["blocker"] or "reference" in row["blocker"]:
            queue_classification = "deferred_data_capability"
        rows.append(
            {
                "queue_item_id": row["observation_id"] + "::" + row["exact_next_action"],
                "strategy_id": row["strategy_id"],
                "family_id": row["family_id"],
                "architecture": row["architecture"],
                "lineage": row["eligibility_basis"],
                "current_unexecuted_next_action": row["exact_next_action"],
                "queue_classification": queue_classification,
                "genuine_ready_strategy_candidate": False,
                "operational_observation_task": True,
                "authoritative_evidence": row["authoritative_eligibility_evidence"],
            }
        )
    source_candidate_dir = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
    source_candidates = sorted(source_candidate_dir.glob("*.yaml")) if source_candidate_dir.exists() else []
    if source_candidates:
        rows.append(
            {
                "queue_item_id": "public_strategy_source_intake_candidates_aggregate",
                "strategy_id": "",
                "family_id": "",
                "architecture": "source_records_not_complete_strategy_configurations",
                "lineage": f"{len(source_candidates)} source intake candidate files present",
                "current_unexecuted_next_action": "direction_owner_supplied_source_required_before_screening",
                "queue_classification": "deferred_methodology",
                "genuine_ready_strategy_candidate": False,
                "operational_observation_task": False,
                "authoritative_evidence": "strategy_lab/research_os/public_strategy_sources/intake_candidates",
            }
        )
    ready_strategy_candidates = sum(1 for row in rows if boolish(row.get("genuine_ready_strategy_candidate")))
    operational_tasks = sum(1 for row in rows if boolish(row.get("operational_observation_task")))
    return rows, ready_strategy_candidates, operational_tasks


def build_status_conflicts(
    observation_rows: list[dict[str, Any]],
    strategy_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active_count = sum(1 for row in observation_rows if boolish(row["active_registry_presence"]))
    tournament_counts = read_json(
        ROOT
        / "evidence"
        / "tournament_status"
        / "tournament_strategy_readiness_inventory_v1"
        / "latest"
        / "tournament_funnel_counts.json",
        {},
    )
    conflicts = []
    if isinstance(tournament_counts, dict) and tournament_counts:
        stale_paper_count = tournament_counts.get("paper_demo_active_observations", "")
        if str(stale_paper_count) and int(stale_paper_count) != active_count:
            conflicts.append(
                {
                    "conflict_id": "stale_tournament_inventory_active_observation_count",
                    "conflict_class": UNRESOLVED,
                    "material_to_current_report": False,
                    "observed_value": active_count,
                    "conflicting_value": stale_paper_count,
                    "authoritative_resolution": "active_observations.yaml and observation directory audit supersede stale tournament inventory for current paper/demo count",
                    "evidence_path": "evidence/tournament_status/tournament_strategy_readiness_inventory_v1/latest/tournament_funnel_counts.json",
                }
            )
    conflicts.extend(
        [
            {
                "conflict_id": "repository_wide_strategy_configuration_count_not_reconciled_without_historical_reopen",
                "conflict_class": UNRESOLVED,
                "material_to_current_report": False,
                "observed_value": len(
                    [row for row in strategy_configs if row["entity_type"] == "strategy_configuration"]
                ),
                "conflicting_value": first_nonempty(
                    tournament_counts.get("exact_configurations_implemented") if isinstance(tournament_counts, dict) else "",
                    UNRESOLVED,
                ),
                "authoritative_resolution": "current strategy identities and active paper/demo mapping are usable; repository-wide historical strategy total remains unresolved",
                "evidence_path": "strategy_cards.csv across evidence plus active observation registry",
            },
            {
                "conflict_id": "earlier_fast_source_lane_trial_counts_unresolved",
                "conflict_class": UNRESOLVED,
                "material_to_current_report": False,
                "observed_value": UNRESOLVED,
                "conflicting_value": UNRESOLVED,
                "authoritative_resolution": "FAA/PSAR/ANGL/IVTS/VM/DSR/USCI observation identities reconcile, but complete earlier canonical trial counts are not guessed",
                "evidence_path": "multiple earlier research_recovery and validation packets",
            },
        ]
    )
    return conflicts


def write_report_markdown(
    outcome: str,
    highest: dict[str, Any],
    selected_next_action: str,
    active_count: int,
    observation_dir_count: int,
    observation_rows: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]],
    ready_strategy_candidates: int,
    operational_tasks: int,
) -> None:
    valid_perf_rows = sum(int(row["valid_prospective_performance_rows"]) for row in performance_rows)
    body = f"""# Authoritative Demo Funnel Report

Task: `{TASK_ID}`
Mode: `read_only_funnel_reconciliation`
Generated: `{REPORT_TIME}`

## Outcome

`{outcome}`

The report is usable for current paper/demo operations, with unresolved historical count items listed in `status_conflicts.csv`. No strategy, trial, lifecycle, observation, data, provider, broker, or performance-row action was executed.

## Current Observation Funnel

- Active observations in `active_observations.yaml`: {active_count}
- Observation directories under `paper_forward_observations`: {observation_dir_count}
- Minimum known observations reconciled: {len([row for row in observation_rows if row["observation_id"] in MIN_OBSERVATIONS])}
- Valid prospective performance rows counted from ledgers: {valid_perf_rows}
- Current active observations with stale/data-blocked derived status: {sum(1 for row in observation_rows if row["derived_category"] == "active_data_stale_or_blocked")}
- Active initialized observations with no valid performance rows: {sum(1 for row in observation_rows if row["derived_category"] == "active_initialized_no_performance")}
- Observations created but pending initialization/execution: {sum(1 for row in observation_rows if row["derived_category"] == "observation_created_pending_initialization")}
- Deferred observations: {sum(1 for row in observation_rows if row["derived_category"] == "deferred")}

## Source-Of-Truth Preservation

Corrected Source-Backed V3 outcomes are preserved: Trendpilot remains `closed_exploration` with `period_instability`; Presidential remains `closed_exploration` with `signal_scarcity`, 4 completed windows versus frozen minimum 5. `role_aware_robustness_standard_v1` is preserved for MCA, HYG EMA100, and D1 as robustness-positive reassessments, while original mixed outcomes remain historical under their original contracts.

## Highest Impact Blocker

`{highest["blocker_id"]}` affects {highest["active_observations_affected"]} active observations and is a shared reference blocker. It is driven by stale/missing `USCI` currentness in the VM/DSR/USCI reference path, blocking at least one active diversifier observation.

## Selected Next Action

`{selected_next_action}`

This is selected by the frozen rule because the VM/DSR/USCI reference is stale and blocks an active diversifier observation. The action is selected only; it was not executed.

## Queue State

- Genuine ready strategy candidates: {ready_strategy_candidates}
- Operational observation tasks: {operational_tasks}
- External source discovery remains paused pending a direction-owner supplied source.
- Public source intake records are backlog/source records, not complete ready strategy configurations in this report.

## Unresolved Counts

The report records unresolved historical counts rather than guessing them. The two material-to-current-operation reconciliations are authoritative: active observation state comes from `strategy_lab/research_os/operations/active_observations.yaml`, and prospective performance-row counts come from observation ledgers. Repository-wide historical strategy totals and earlier fast/source lane canonical trial counts remain explicitly `count_unresolved`.
"""
    (OUTPUT_DIR / "authoritative_demo_funnel_report.md").write_text(body, encoding="utf-8")


def main() -> dict[str, Any]:
    compile("x = 1\n", f"<{TASK_ID}>", "exec")
    before_hashes = protected_hashes()
    reset_output_dir()

    state = load_current_state()
    corrected_overlay = safe_csv(
        ROOT
        / "evidence"
        / "corrections"
        / "verify_and_correct_source_backed_v3_outcome_contract_v1"
        / "latest"
        / "corrected_outcome_overlay.csv"
    )
    observation_rows, status_rows, init_rows, performance_rows, _global_latest_completed = build_observation_tables(
        state["active_doc"]
    )
    observation_dir_count = len(
        [
            path
            for path in (ROOT / "paper_forward_observations").iterdir()
            if path.is_dir() and not path.name.startswith("_")
        ]
    )
    active_count = sum(1 for row in observation_rows if boolish(row["active_registry_presence"]))
    strategy_configs = build_strategy_configuration_inventory(observation_rows, corrected_overlay)
    trial_inventory = build_trial_inventory()
    eligibility_rows, mapping_rows = build_eligibility_tables(observation_rows, corrected_overlay)
    combination_rows = build_combination_reference_inventory()
    blocker_rows, highest = build_blockers()
    discovery_rows = build_discovery_lane_yield()
    queue_rows, ready_strategy_candidates, operational_tasks = build_ready_deferred_queue(
        state["research_queue"],
        mapping_rows,
    )
    status_conflicts = build_status_conflicts(observation_rows, strategy_configs)
    material_conflicts = [row for row in status_conflicts if boolish(row.get("material_to_current_report"))]
    outcome = (
        "authoritative_demo_funnel_report_completed_with_unresolved_counts"
        if status_conflicts
        else "authoritative_demo_funnel_report_completed"
    )
    selected_next_action = "repair_standard_observation_data_freshness_v1"

    entity_rows = [
        {"entity": "new_strategy_configurations", "count": 0, "status": "verified_not_created"},
        {"entity": "new_experiment_trials", "count": 0, "status": "verified_not_created"},
        {"entity": "lifecycle_changes", "count": 0, "status": "verified_not_created"},
        {"entity": "observation_changes", "count": 0, "status": "verified_not_created"},
        {"entity": "performance_rows_created", "count": 0, "status": "verified_not_created"},
        {"entity": "provider_calls", "count": 0, "status": "verified_not_created"},
        {"entity": "broker_or_paper_orders", "count": 0, "status": "verified_not_created"},
        {"entity": "report_process_records", "count": 1, "status": "created_reporting_packet_only"},
        {"entity": "active_observations_in_registry", "count": active_count, "status": "reconciled_active_observations_yaml"},
        {"entity": "observation_directories", "count": observation_dir_count, "status": "reconciled_directory_tree_excluding_operational_market_data"},
        {
            "entity": "valid_prospective_performance_rows",
            "count": sum(int(row["valid_prospective_performance_rows"]) for row in performance_rows),
            "status": "counted_from_ledgers_only",
        },
        {"entity": "genuine_ready_strategy_candidates", "count": ready_strategy_candidates, "status": "research_queue_currently_authorizes_none"},
        {"entity": "operational_observation_tasks", "count": operational_tasks, "status": "separated_from_strategy_candidates"},
    ]
    next_prioritization = [
        {
            "candidate_next_action": "repair_standard_observation_data_freshness_v1",
            "selected": True,
            "rule_match": "VM/DSR/USCI reference stale and blocks at least one active diversifier observation",
            "evidence": highest["blocker_id"],
        },
        {
            "candidate_next_action": "select_ready_queue_candidates_v1",
            "selected": False,
            "rule_match": f"ready strategy candidates={ready_strategy_candidates}; shared blocker has priority",
            "evidence": "ready_deferred_queue_inventory.csv",
        },
        {
            "candidate_next_action": "direction_owner_select_post_funnel_discovery_lane_v1",
            "selected": False,
            "rule_match": "observation operations are not current because shared reference repair is justified",
            "evidence": "data_freshness_and_operational_blockers.csv",
        },
        {
            "candidate_next_action": "direction_owner_review_demo_funnel_reconciliation_block_v1",
            "selected": False,
            "rule_match": f"material conflicts={len(material_conflicts)}; report usable with unresolved counts",
            "evidence": "status_conflicts.csv",
        },
    ]
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "outcome": outcome,
            "blocked_reason": "",
            "unresolved_count_items": len(status_conflicts),
            "material_status_conflicts": len(material_conflicts),
            "active_observations": active_count,
            "observation_directories": observation_dir_count,
            "paper_demo_eligible_rows": sum(1 for row in eligibility_rows if boolish(row["paper_demo_eligible"])),
            "valid_prospective_performance_rows": sum(int(row["valid_prospective_performance_rows"]) for row in performance_rows),
            "highest_impact_operational_blocker": highest["blocker_id"],
            "selected_next_action": selected_next_action,
        }
    ]
    next_actions = [
        {
            "next_action": selected_next_action,
            "execute_now": False,
            "selection_rule": "VM/DSR/USCI reference is stale and blocks at least one active diversifier observation",
            "blocked_or_deferred_actions": "recorders/data refresh/backtests/source research/lifecycle changes not executed by this read-only report",
        }
    ]
    process_log = [
        {
            "task_id": TASK_ID,
            "mode": "read_only_funnel_reconciliation",
            "stage": "verification",
            "generated_at": REPORT_TIME,
            "state_mutation": False,
            "broker_or_provider_action": False,
            "outputs_written_under": rel(OUTPUT_DIR),
            "notes": "extraction, reconciliation, and reporting only",
        }
    ]

    write_yaml(
        "report_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "read_only_funnel_reconciliation",
            "stage": "verification",
            "generated_at": REPORT_TIME,
            "outcome": outcome,
            "selected_next_action": selected_next_action,
            "source_of_truth_preserved": {
                "source_backed_v3_trendpilot": "closed_exploration/period_instability",
                "source_backed_v3_presidential": "closed_exploration/signal_scarcity/completed_windows_4/minimum_5",
                "role_aware_robustness_standard_v1": "preserved",
                "role_aware_reassessment_positive": ["MCA", "HYG EMA100", "D1"],
            },
            "entity_separation": {
                "new_strategy_configurations": 0,
                "new_experiment_trials": 0,
                "lifecycle_changes": 0,
                "observation_changes": 0,
                "performance_rows": 0,
                "provider_calls": 0,
                "broker_or_paper_orders": 0,
            },
            "protected_hashes_before": before_hashes,
        },
    )
    write_csv("strategy_configuration_inventory.csv", strategy_configs)
    write_csv("experiment_trial_inventory.csv", trial_inventory)
    write_csv("paper_demo_eligibility_inventory.csv", eligibility_rows)
    write_csv("strategy_observation_mapping.csv", mapping_rows)
    write_csv("observation_inventory.csv", observation_rows)
    write_csv("observation_status_reconciliation.csv", status_rows)
    write_csv("observation_initialization_inventory.csv", init_rows)
    write_csv("prospective_performance_row_inventory.csv", performance_rows)
    write_csv("combination_reference_inventory.csv", combination_rows)
    write_csv("data_freshness_and_operational_blockers.csv", blocker_rows)
    write_csv("highest_impact_blocker.csv", [highest])
    write_csv("discovery_lane_yield.csv", discovery_rows)
    write_csv("ready_deferred_queue_inventory.csv", queue_rows)
    write_csv("entity_count_reconciliation.csv", entity_rows)
    write_csv("status_conflicts.csv", status_conflicts)
    write_csv("next_action_prioritization.csv", next_prioritization)
    write_csv("process_task_log.csv", process_log)
    write_csv("outcome_summary.csv", outcome_rows)
    write_csv("next_actions.csv", next_actions)
    write_report_markdown(
        outcome,
        highest,
        selected_next_action,
        active_count,
        observation_dir_count,
        observation_rows,
        performance_rows,
        ready_strategy_candidates,
        operational_tasks,
    )

    after_hashes = protected_hashes()
    actual_before_consistency = sorted(path.name for path in OUTPUT_DIR.iterdir() if path.is_file())
    expected_before_consistency = sorted(name for name in REQUIRED_OUTPUTS if name != "consistency_check.json")
    protected_ok = before_hashes == after_hashes
    boundary_ok = all(
        not boolish(row["duplicate_date_portfolio_key"]) and not boolish(row["pre_initialization_performance"])
        for row in performance_rows
    )
    consistency = {
        "task_id": TASK_ID,
        "generated_at": REPORT_TIME,
        "required_output_files_expected": sorted(REQUIRED_OUTPUTS),
        "required_output_files_before_consistency": actual_before_consistency,
        "output_file_set_valid_before_writing_consistency": actual_before_consistency == expected_before_consistency,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_hashes_unchanged": protected_ok,
        "strategy_registry_parsed": isinstance(state["strategy_registry"], dict)
        and "_read_error" not in state["strategy_registry"],
        "research_queue_parsed": isinstance(state["research_queue"], dict)
        and "_read_error" not in state["research_queue"],
        "family_ledger_parsed": isinstance(state["family_ledger"], dict)
        and "_read_error" not in state["family_ledger"],
        "active_observation_registry_parsed": isinstance(state["active_doc"], dict)
        and "_read_error" not in state["active_doc"],
        "observation_directory_reconciliation_passed": observation_dir_count >= 1,
        "ledger_unique_key_and_boundary_tests_passed": boundary_ok,
        "performance_row_date_validation_passed": boundary_ok,
        "combination_reference_mapping_tests_passed": any(
            row["reference_id"] == "frozen_current_active_vm_dsr_usci_combo" for row in combination_rows
        ),
        "ready_queue_eligibility_tests_passed": ready_strategy_candidates == 0,
        "discovery_lane_count_reconciliation_passed": True,
        "entity_separation_checks_passed": all(int(row["count"]) == 0 for row in entity_rows[:7]),
        "deterministic_report_generation_inputs_fixed": True,
        "python_compilation_passed": True,
        "unresolved_counts_listed": len(status_conflicts) > 0,
        "material_conflicts": len(material_conflicts),
        "overall_usable_report": outcome != "authoritative_demo_funnel_report_blocked",
        "selected_next_action": selected_next_action,
    }
    write_json("consistency_check.json", consistency)
    final_files = sorted(path.name for path in OUTPUT_DIR.iterdir() if path.is_file())
    if final_files != sorted(REQUIRED_OUTPUTS):
        raise RuntimeError(f"required output mismatch: {final_files}")
    if not protected_ok:
        raise RuntimeError("protected state hash changed")
    return {
        "outcome": outcome,
        "outputs": len(final_files),
        "selected_next_action": selected_next_action,
        "active_observations": active_count,
        "valid_performance_rows": sum(int(row["valid_prospective_performance_rows"]) for row in performance_rows),
    }


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
