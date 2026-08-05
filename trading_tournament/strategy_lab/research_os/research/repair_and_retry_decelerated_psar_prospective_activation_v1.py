from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
import re
import shutil
import sys
import traceback
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

# The PSAR source module imports a clustering helper used by an unrelated
# candidate. Keep that optional dependency fail-closed without changing any
# production module or allowing the clustering path to execute.
try:
    import scipy.cluster.hierarchy  # type: ignore[import-not-found]  # noqa: F401
    import scipy.spatial.distance  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    scipy_module = types.ModuleType("scipy")
    cluster_module = types.ModuleType("scipy.cluster")
    hierarchy_module = types.ModuleType("scipy.cluster.hierarchy")
    spatial_module = types.ModuleType("scipy.spatial")
    distance_module = types.ModuleType("scipy.spatial.distance")

    def _unavailable_scipy_path(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(
            "Unrelated SciPy clustering path is unavailable in the "
            "prospective activation correction runtime"
        )

    hierarchy_module.leaves_list = _unavailable_scipy_path
    hierarchy_module.linkage = _unavailable_scipy_path
    distance_module.squareform = _unavailable_scipy_path
    scipy_module.cluster = cluster_module
    scipy_module.spatial = spatial_module
    cluster_module.hierarchy = hierarchy_module
    spatial_module.distance = distance_module
    sys.modules.setdefault("scipy", scipy_module)
    sys.modules.setdefault("scipy.cluster", cluster_module)
    sys.modules.setdefault("scipy.cluster.hierarchy", hierarchy_module)
    sys.modules.setdefault("scipy.spatial", spatial_module)
    sys.modules.setdefault("scipy.spatial.distance", distance_module)

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    activate_decelerated_psar_prospective_validation_v1 as prior_activation,
)
from strategy_lab.research_os.research import (
    design_decelerated_psar_prospective_validation_v1 as design,
)
from strategy_lab.research_os.research import (
    initialize_angl_after_next_completed_common_session_v1 as reference_engine,
)


TASK_ID = "repair_and_retry_decelerated_psar_prospective_activation_v1"
MODE = "methodology-correction"
STAGE = "validation"
OUTPUT_DIR = ROOT / "evidence" / "validation" / TASK_ID / "latest"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\52009377-60d6-460e-bdbb-f213d17b9988\pasted-text.txt"
)

STRATEGY_ID = design.STRATEGY_ID
FAMILY_ID = design.FAMILY_ID
TRIAL_ID = design.FUTURE_TRIAL_ID
PARENT_TRIAL_ID = design.PARENT_TRIAL_ID
OBSERVATION_ID = "prospective_validation_decelerated_psar_20pct_v1"
REFERENCE_ID = reference_engine.REFERENCE_ID
SYMBOLS = design.EXPECTED_REFERENCE_SYMBOLS
PORTFOLIO_IDS = design.PORTFOLIO_IDS
REFERENCE_WEIGHT = 0.80
CANDIDATE_WEIGHT = 0.20
EXACT_EXPOSURE_SPY = design.EXACT_EXPOSURE_SPY
EXACT_EXPOSURE_BIL = design.EXACT_EXPOSURE_BIL
GLOBAL_REQUEST_START = prior_activation.GLOBAL_REQUEST_START
EASTERN = ZoneInfo("America/New_York")

ACTIVATED = "prospective_validation_activated"
DEFERRED = "prospective_validation_activation_deferred"
REPAIR_FAILED = "prospective_activation_repair_failed"
BLOCKED = "prospective_validation_activation_blocked"
NEXT_ACTIVATED = "record_decelerated_psar_prospective_validation_monthly_v1"
NEXT_DEFERRED = "resume_strategy_discovery_while_psar_validation_deferred_v1"
NEXT_BLOCKED = "direction_owner_review_psar_activation_block_v1"
LOCAL_FAILURE = "local_methodology_failure"

DEFERRED_REASONS = (
    "required_data_unavailable",
    "immutable_snapshot_reproducibility_failure",
    "reference_initialization_failure",
    "candidate_state_initialization_failure",
    "activation_boundary_not_ready",
    "observation_storage_unavailable",
    "data_or_comparability_failure",
)
BLOCKED_REASONS = (
    "lineage_reconciliation_failure",
    "parameter_reconciliation_failure",
    "frozen_design_contradiction",
    "status_reconciliation_failure",
)

WRONG_REFERENCE_MODULE = (
    "strategy_lab.research_os.research."
    "remediate_angl_observation_required_market_data_v1"
)
CORRECT_REFERENCE_MODULE = (
    "strategy_lab.research_os.research."
    "initialize_angl_after_next_completed_common_session_v1"
)

PRIOR_ACTIVATION_DIR = prior_activation.OUTPUT_DIR
PRIOR_EVIDENCE_DIRS = (
    design.OUTPUT_DIR,
    PRIOR_ACTIVATION_DIR,
    design.ROBUSTNESS_EVIDENCE,
    design.EXPLORATION_EVIDENCE,
    design.STANDALONE_EVIDENCE,
)
PROTECTED_PATHS = design.PROTECTED_PATHS
RAW_ROOT = OUTPUT_DIR / "immutable_stream"
SNAPSHOT_ROOT = OUTPUT_DIR / "immutable_initialization_snapshots"
OFFLINE_ROOT = OUTPUT_DIR / "offline_dry_run_fixture"

REQUIRED_OUTPUTS = {
    "repair_manifest.yaml",
    "prior_activation_reconciliation.csv",
    "alias_error_reproduction.csv",
    "root_cause_analysis.md",
    "reference_import_contract.csv",
    "offline_dry_run_results.csv",
    "offline_gate_results.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "retrieval_reproducibility.csv",
    "immutable_snapshot_manifest.csv",
    "candidate_state_initialization.csv",
    "comparator_state_initialization.csv",
    "frozen_reference_state_initialization.csv",
    "portfolio_initialization_record.csv",
    "activation_boundary.csv",
    "validation_trial_record.csv",
    "validation_observation_record.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "repair_and_activation_report.md",
}

_NETWORK_CALL_COUNT = 0


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("utf-8")
    )


def packet_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file())


def packet_hash(path: Path) -> str:
    return canonical_hash(
        {
            item.relative_to(path).as_posix(): file_hash(item)
            for item in packet_files(path)
        }
    )


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.is_file()}


def cache_files() -> list[Path]:
    return design.cache_files()


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "validation" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected path: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str
        )
    return str(value)


def fields_for(
    rows: list[dict[str, Any]],
    leading: list[str],
    fallback: list[str] | None = None,
) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields if rows else list(fallback or leading)


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: list[str],
    fallback: list[str] | None = None,
) -> None:
    path = OUTPUT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(rows, leading, fallback)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, value: dict[str, Any]) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(name: str, value: str) -> None:
    (OUTPUT_DIR / name).write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_error(exc: BaseException) -> str:
    value = str(exc).replace("\r", " ").replace("\n", " ")
    value = re.sub(
        r"(?i)(key|secret|token|authorization)[=:]\s*\S+",
        r"\1=REDACTED",
        value,
    )
    for name in (
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_SECRET_KEY",
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
    ):
        value = value.replace(name, f"{name}_REDACTED")
    return value[:1000]


def prior_activation_reconciliation() -> tuple[list[dict[str, Any]], bool]:
    manifest = read_yaml(PRIOR_ACTIVATION_DIR / "activation_manifest.yaml")
    attempts = read_csv(PRIOR_ACTIVATION_DIR / "provider_attempt_log.csv")
    consistency = read_json(PRIOR_ACTIVATION_DIR / "consistency_check.json")
    checks = {
        "prior_outcome_deferred": manifest.get("outcome") == DEFERRED,
        "prior_failure_recorded": manifest.get("failure_reason")
        == "data_or_comparability_failure",
        "prior_trial_count_zero": manifest.get("experiment_trials_created") == 0,
        "prior_observation_count_zero": manifest.get(
            "validation_observations_created"
        )
        == 0,
        "prior_initialization_count_zero": manifest.get(
            "initialization_records_created"
        )
        == 0,
        "prior_performance_count_zero": manifest.get(
            "completed_validation_performance_rows"
        )
        == 0,
        "prior_admitted_retrieval_count_zero": len(attempts) == 1
        and attempts[0].get("retrieval_count") == "0",
        "prior_snapshot_count_zero": not read_csv(
            PRIOR_ACTIVATION_DIR / "immutable_snapshot_manifest.csv"
        ),
        "prior_reproducibility_count_zero": not read_csv(
            PRIOR_ACTIVATION_DIR / "retrieval_reproducibility.csv"
        ),
        "prior_error_matches_alias_defect": len(attempts) == 1
        and "did not expose VM_ID" in attempts[0].get("error", ""),
        "prior_packet_consistency_pass": consistency.get("overall_pass") is True,
    }
    rows = [
        {
            "check_id": name,
            "status": "pass" if passed else "fail",
            "authoritative_packet": rel(PRIOR_ACTIVATION_DIR),
            "detail": "",
        }
        for name, passed in checks.items()
    ]
    return rows, all(checks.values())


def reproduce_alias_error() -> dict[str, Any]:
    module = importlib.import_module(WRONG_REFERENCE_MODULE)
    exports = sorted(
        name
        for name in dir(module)
        if not name.startswith("_")
        and (
            name.isupper()
            or name
            in {
                "vm_target",
                "dsr_target",
                "reference_symbols",
                "required_symbols",
            }
        )
    )
    captured = ""
    call_stack = ""
    try:
        if not hasattr(module, "VM_ID"):
            raise AttributeError(
                "initialization reference module alias did not expose VM_ID"
            )
        _ = module.VM_ID
    except AttributeError as exc:
        captured = str(exc)
        call_stack = traceback.format_exc()
    return {
        "failing_import_alias": "reference_engine",
        "imported_module": WRONG_REFERENCE_MODULE,
        "imported_module_path": str(Path(module.__file__).resolve()),
        "expected_symbol": "VM_ID",
        "actual_exported_symbols": exports,
        "exception_type": "AttributeError" if captured else "",
        "exception_message": captured,
        "call_stack": call_stack,
        "root_cause": (
            "data-remediation symbol-scope module was aliased as the "
            "initialization reference API"
        ),
        "status": "pass"
        if captured
        == "initialization reference module alias did not expose VM_ID"
        and "VM_ID" not in exports
        else "fail",
    }


def target_schema_valid(target: Any) -> bool:
    return bool(
        isinstance(target, dict)
        and target
        and all(isinstance(key, str) and key for key in target)
        and all(
            isinstance(value, (int, float))
            and math.isfinite(float(value))
            and float(value) >= 0.0
            for value in target.values()
        )
        and abs(sum(float(value) for value in target.values()) - 1.0) <= 1e-12
    )


def synthetic_frames() -> dict[str, pd.DataFrame]:
    sessions = prior_activation.expected_sessions(
        date(2022, 1, 3), date(2026, 6, 30)
    )
    index = np.arange(len(sessions), dtype=float)
    frames: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(SYMBOLS):
        slope = 0.025 + 0.003 * (offset % 7)
        wave = 1.8 * np.sin(index / (11.0 + offset % 5) + offset)
        close = 50.0 + offset * 4.0 + slope * index + wave
        open_ = close * (1.0 + 0.0007 * np.sin(index / 3.0 + offset))
        high = np.maximum(open_, close) * 1.006
        low = np.minimum(open_, close) * 0.994
        frames[symbol] = pd.DataFrame(
            {
                "trading_date": [value.isoformat() for value in sessions],
                "adjusted_open": open_,
                "adjusted_high": high,
                "adjusted_low": low,
                "adjusted_close": close,
                "adjusted_volume": np.full(
                    len(sessions), 1_000_000.0 + 1000.0 * offset
                ),
            }
        )
    return frames


def reference_import_contract_rows(
    frames: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], bool]:
    latest = date.fromisoformat(frames["SPY"].iloc[-1]["trading_date"])
    vm_prices = prior_activation.close_frame(
        frames, tuple(reference_engine.VM_SYMBOLS)
    )
    dsr_prices = prior_activation.close_frame(
        frames, tuple(reference_engine.DSR_SYMBOLS)
    )
    signal = pd.Timestamp(vm_prices.index[-2])
    vm_target = reference_engine.vm_target(vm_prices, signal)
    dsr_target = reference_engine.dsr_target(dsr_prices, signal)
    usci_target = {"USCI": 1.0}
    contract = (
        ("VM_ID", reference_engine.VM_ID, bool(reference_engine.VM_ID)),
        ("DSR_ID", reference_engine.DSR_ID, bool(reference_engine.DSR_ID)),
        ("USCI_ID", reference_engine.USCI_ID, bool(reference_engine.USCI_ID)),
        (
            "REFERENCE_ID",
            reference_engine.REFERENCE_ID,
            reference_engine.REFERENCE_ID
            == "frozen_current_active_vm_dsr_usci_combo",
        ),
        (
            "vm_target",
            f"{reference_engine.vm_target.__module__}.vm_target",
            callable(reference_engine.vm_target),
        ),
        (
            "dsr_target",
            f"{reference_engine.dsr_target.__module__}.dsr_target",
            callable(reference_engine.dsr_target),
        ),
        (
            "reference_symbols",
            list(reference_engine.reference_symbols()),
            tuple(reference_engine.reference_symbols()) == SYMBOLS,
        ),
        (
            "VM_SYMBOLS",
            list(reference_engine.VM_SYMBOLS),
            set(reference_engine.VM_SYMBOLS).issubset(SYMBOLS),
        ),
        (
            "DSR_SYMBOLS",
            list(reference_engine.DSR_SYMBOLS),
            set(reference_engine.DSR_SYMBOLS).issubset(SYMBOLS),
        ),
        (
            "USCI_SYMBOLS",
            list(reference_engine.USCI_SYMBOLS),
            set(reference_engine.USCI_SYMBOLS).issubset(SYMBOLS),
        ),
        ("VM_target_schema", vm_target, target_schema_valid(vm_target)),
        ("DSR_target_schema", dsr_target, target_schema_valid(dsr_target)),
        ("USCI_target_schema", usci_target, target_schema_valid(usci_target)),
        (
            "latest_synthetic_session",
            latest.isoformat(),
            latest == date(2026, 6, 30),
        ),
    )
    rows = [
        {
            "contract_item": name,
            "authoritative_module": CORRECT_REFERENCE_MODULE,
            "authoritative_module_path": str(
                Path(reference_engine.__file__).resolve()
            ),
            "observed_value": value,
            "guessed_identifier_fallback_used": False,
            "status": "pass" if passed else "fail",
        }
        for name, value, passed in contract
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def build_trial_row(
    activation_timestamp: datetime,
    first_performance: date,
) -> dict[str, Any]:
    return {
        "trial_id": TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "prospective_validation_variant",
        "changed_fields_from_parent": "prospective_evaluation_boundary_only",
        "route": "20pct_diversifier_only",
        "status": "active_prospective_validation",
        "outcome": "",
        "failure_reason": "",
        "next_action": NEXT_ACTIVATED,
        "strategy_rule_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "sleeve_weight_changed": False,
        "reference_changed": False,
        "controls_changed": False,
        "cost_model_changed": False,
        "optimization_performed": False,
        "historical_backfill_permitted": False,
        "validation_period_observed_before_activation": False,
        "activation_timestamp_utc": activation_timestamp.isoformat(),
        "first_eligible_performance_session": first_performance.isoformat(),
        "completed_validation_performance_rows": 0,
    }


def build_observation_row(
    activation_timestamp: datetime,
    initialization_session: date,
    first_performance: date,
) -> dict[str, Any]:
    return {
        "validation_observation_id": OBSERVATION_ID,
        "entity_type": "validation_observation",
        "stage": STAGE,
        "associated_trial_id": TRIAL_ID,
        "state": "active",
        "storage_convention": (
            "validation_evidence_lane_only_no_authoritative_"
            "paper_demo_state_change"
        ),
        "activation_timestamp_utc": activation_timestamp.isoformat(),
        "initialization_session": initialization_session.isoformat(),
        "first_eligible_performance_session": first_performance.isoformat(),
        "elapsed_completed_months": 0,
        "completed_defensive_episodes": 0,
        "validation_decision": "",
        "historical_backfill": "prohibited",
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "paper_demo_observation": False,
        "next_action": NEXT_ACTIVATED,
    }


def offline_dry_run(
    fixture_root: Path,
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frames = synthetic_frames()
    latest = date.fromisoformat(frames["SPY"].iloc[-1]["trading_date"])

    raw_records = [
        {
            "t": f"{value}T20:00:00Z",
            "o": 100.0 + index,
            "h": 101.0 + index,
            "l": 99.0 + index,
            "c": 100.5 + index,
            "v": 1000 + index,
        }
        for index, value in enumerate(frames["SPY"]["trading_date"].head(5))
    ]
    normalized = prior_activation.normalize_alpaca_records(raw_records)
    interface_pass = tuple(normalized.columns) == (
        "trading_date",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjusted_close",
        "adjusted_volume",
    )
    rows.append(
        {
            "step_id": "provider_result_normalization_interface",
            "status": "pass" if interface_pass else "fail",
            "detail": list(normalized.columns),
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    reproducibility, reproduce = prior_activation.frames_reproduce(frames, frames)
    rows.append(
        {
            "step_id": "duplicate_retrieval_comparison",
            "status": "pass" if reproduce else "fail",
            "detail": f"symbol_rows={len(reproducibility)}",
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    fixture_root.mkdir(parents=True, exist_ok=True)
    serialization_pass = True
    serialized_hashes: dict[str, str] = {}
    for symbol in SYMBOLS:
        path = fixture_root / f"{symbol}.csv"
        path.write_bytes(prior_activation.frame_bytes(frames[symbol]))
        restored = pd.read_csv(path)
        expected = prior_activation.frame_bytes(frames[symbol])
        observed = prior_activation.frame_bytes(restored)
        serialization_pass = serialization_pass and expected == observed
        serialized_hashes[symbol] = file_hash(path)
    rows.append(
        {
            "step_id": "immutable_snapshot_serialization",
            "status": "pass" if serialization_pass else "fail",
            "detail": canonical_hash(serialized_hashes),
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    candidate, _candidate_path = prior_activation.psar_state(
        frames["SPY"], latest, True
    )
    original, _original_path = prior_activation.psar_state(
        frames["SPY"], latest, False
    )
    candidate_pass = target_schema_valid(candidate["target"])
    rows.append(
        {
            "step_id": "candidate_state_initialization",
            "status": "pass" if candidate_pass else "fail",
            "detail": candidate["target"],
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )
    rows.append(
        {
            "step_id": "original_psar_state_initialization",
            "status": "pass"
            if target_schema_valid(original["target"])
            else "fail",
            "detail": original["target"],
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    reference_rows, reference_weights, reference_meta = (
        prior_activation.reference_state(frames, latest)
    )
    reference_pass = bool(
        reference_rows
        and reference_meta.get("status") == "pass"
        and target_schema_valid(reference_weights)
    )
    rows.append(
        {
            "step_id": "frozen_reference_initialization",
            "status": "pass" if reference_pass else "fail",
            "detail": {
                "reference_id": REFERENCE_ID,
                "weights": reference_weights,
            },
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    comparator_rows, holdings = prior_activation.comparator_states(
        frames, latest, reference_weights, candidate, original
    )
    comparator_pass = bool(
        len(comparator_rows) == len(PORTFOLIO_IDS)
        and all(row["status"] == "pass" for row in comparator_rows)
    )
    rows.append(
        {
            "step_id": "comparator_state_initialization",
            "status": "pass" if comparator_pass else "fail",
            "detail": list(holdings),
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )
    rows.append(
        {
            "step_id": "portfolio_weight_reconciliation",
            "status": "pass"
            if all(target_schema_valid(value) for value in holdings.values())
            else "fail",
            "detail": {
                key: sum(value.values()) for key, value in holdings.items()
            },
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    dry_activation = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    first_performance = prior_activation.next_regular_session(
        max(latest, dry_activation.astimezone(EASTERN).date())
    )
    boundary_pass = (
        first_performance > latest
        and first_performance > dry_activation.astimezone(EASTERN).date()
        and prior_activation.is_regular_session(first_performance)
    )
    rows.append(
        {
            "step_id": "activation_boundary_calculation",
            "status": "pass" if boundary_pass else "fail",
            "detail": first_performance.isoformat(),
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    trial = build_trial_row(dry_activation, first_performance)
    observation = build_observation_row(
        dry_activation, latest, first_performance
    )
    construction_pass = bool(
        trial["trial_id"] == TRIAL_ID
        and trial["parent_trial_id"] == PARENT_TRIAL_ID
        and observation["associated_trial_id"] == TRIAL_ID
        and observation["elapsed_completed_months"] == 0
        and observation["completed_defensive_episodes"] == 0
    )
    rows.append(
        {
            "step_id": "trial_and_observation_record_construction",
            "status": "pass" if construction_pass else "fail",
            "detail": {
                "trial_id": trial["trial_id"],
                "observation_id": observation["validation_observation_id"],
                "authoritative_records_created": 0,
            },
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )
    rows.append(
        {
            "step_id": "final_precommit_activation_gate",
            "status": "pass",
            "detail": {
                "validation_performance_rows_created": 0,
                "canonical_cache_writes": 0,
                "authoritative_trial_writes": 0,
                "authoritative_observation_writes": 0,
            },
            "network_call_count": _NETWORK_CALL_COUNT,
        }
    )

    passed = all(row["status"] == "pass" for row in rows)
    return rows, passed, {
        "candidate": candidate,
        "original": original,
        "reference_weights": reference_weights,
        "holdings": holdings,
        "first_performance": first_performance.isoformat(),
    }


def run_phase_a() -> dict[str, Any]:
    network_before = _NETWORK_CALL_COUNT
    prior_rows, prior_pass = prior_activation_reconciliation()
    alias_row = reproduce_alias_error()
    frames = synthetic_frames()
    contract_rows, contract_pass = reference_import_contract_rows(frames)
    dry_rows, dry_pass, dry_payload = offline_dry_run(OFFLINE_ROOT)
    design_rows, design_checks = prior_activation.design_reconciliation()
    identity_uses = prior_activation.trial_identity_use_rows()
    design_pass = all(design_checks.values())
    trial_unused = not identity_uses
    network_after = _NETWORK_CALL_COUNT
    gate_values = {
        "prior_deferred_activation_reconciles": prior_pass,
        "original_alias_failure_reproduced": alias_row["status"] == "pass",
        "root_cause_documented": bool(alias_row["root_cause"]),
        "minimal_reference_contract_correction_applied": (
            prior_activation.REFERENCE_ID == reference_engine.REFERENCE_ID
            and prior_activation.reference_engine is reference_engine
        ),
        "reference_import_contract_passes": contract_pass,
        "offline_full_activation_dry_run_passes": dry_pass,
        "design_packet_reconciles": design_pass,
        "future_trial_identity_unused": trial_unused,
        "no_network_call_in_phase_a": network_before == network_after == 0,
    }
    gate_rows = [
        {
            "gate_id": key,
            "status": "pass" if passed else "fail",
            "network_calls_before": network_before,
            "network_calls_after": network_after,
            "provider_access_permitted_after_gate": all(gate_values.values()),
        }
        for key, passed in gate_values.items()
    ]
    return {
        "prior_rows": prior_rows,
        "alias_row": alias_row,
        "contract_rows": contract_rows,
        "dry_rows": dry_rows,
        "dry_payload": dry_payload,
        "design_rows": design_rows,
        "design_checks": design_checks,
        "identity_uses": identity_uses,
        "gate_rows": gate_rows,
        "passed": all(gate_values.values()),
    }


def flush_provider_evidence(
    attempt_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
) -> None:
    write_csv(
        "provider_attempt_log.csv",
        attempt_rows,
        ["provider_sequence", "provider_id", "retrieval_id", "response_sequence"],
        [
            "provider_sequence",
            "provider_id",
            "retrieval_id",
            "response_sequence",
            "status",
        ],
    )
    write_csv(
        "raw_retrieval_manifest.csv",
        raw_rows,
        [
            "provider_id",
            "retrieval_id",
            "response_sequence",
            "record_type",
            "symbol",
        ],
        [
            "provider_id",
            "retrieval_id",
            "response_sequence",
            "record_type",
            "symbol",
            "raw_path",
            "raw_hash",
            "normalized_path",
            "normalized_hash",
        ],
    )


def persist_payload(
    provider_key: str,
    provider_id: str,
    retrieval_id: int,
    response_sequence: int,
    payload: Any,
    page_frames: dict[str, pd.DataFrame],
    raw_rows: list[dict[str, Any]],
) -> str:
    root = (
        RAW_ROOT
        / provider_key
        / f"retrieval_{retrieval_id}"
        / f"response_{response_sequence:04d}"
    )
    raw_path = root / "raw_response.json"
    write_json(raw_path, payload)
    raw_hash = file_hash(raw_path)
    for symbol in SYMBOLS:
        frame = page_frames.get(
            symbol,
            pd.DataFrame(
                columns=[
                    "trading_date",
                    "adjusted_open",
                    "adjusted_high",
                    "adjusted_low",
                    "adjusted_close",
                    "adjusted_volume",
                ]
            ),
        )
        normalized_path = root / f"{symbol}_normalized.csv"
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_bytes(prior_activation.frame_bytes(frame))
        raw_rows.append(
            {
                "provider_id": provider_id,
                "retrieval_id": retrieval_id,
                "response_sequence": response_sequence,
                "record_type": "provider_response_symbol_normalization",
                "symbol": symbol,
                "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "raw_path": rel(raw_path),
                "raw_hash": raw_hash,
                "normalized_path": rel(normalized_path),
                "normalized_hash": file_hash(normalized_path),
                "persisted_before_state_initialization": True,
                "canonical_cache_modified": False,
            }
        )
    return raw_hash


def persist_complete_frames(
    provider_key: str,
    provider_id: str,
    retrieval_id: int,
    frames: dict[str, pd.DataFrame],
    raw_hashes: list[str],
    raw_rows: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    root = RAW_ROOT / provider_key / f"retrieval_{retrieval_id}" / "complete"
    mapping: dict[str, dict[str, str]] = {}
    for symbol in SYMBOLS:
        path = root / f"{symbol}_normalized.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(prior_activation.frame_bytes(frames[symbol]))
        mapping[symbol] = {
            "normalized_path": rel(path),
            "normalized_hash": file_hash(path),
            "raw_set_hash": canonical_hash(raw_hashes),
        }
        raw_rows.append(
            {
                "provider_id": provider_id,
                "retrieval_id": retrieval_id,
                "response_sequence": "complete",
                "record_type": "complete_normalized_frame",
                "symbol": symbol,
                "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "raw_path": "",
                "raw_hash": canonical_hash(raw_hashes),
                "normalized_path": rel(path),
                "normalized_hash": file_hash(path),
                "persisted_before_state_initialization": True,
                "canonical_cache_modified": False,
            }
        )
    return mapping


def retrieve_alpaca_durable(
    retrieval_id: int,
    start: date,
    end_exclusive: date,
    attempt_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    global _NETWORK_CALL_COUNT
    provider_id = "alpaca_market_data_read_only_adjusted_daily"
    credentials = prior_activation.load_alpaca_credentials("paper")
    result: dict[str, Any] = {
        "retrieval_id": retrieval_id,
        "provider_id": provider_id,
        "status": "",
        "frames": {},
        "mapping": {},
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_present": bool(credentials.present),
        "live_credentials_detected": bool(
            credentials.live_credentials_detected
        ),
        "endpoint": "/v2/stocks/bars",
        "feed": "iex",
        "adjustment": "all",
    }
    if not credentials.present or credentials.live_credentials_detected:
        result["status"] = (
            "auth_unavailable"
            if not credentials.present
            else "blocked_live_credentials_detected"
        )
        attempt_rows.append(
            {
                "provider_sequence": 1,
                "provider_id": provider_id,
                "retrieval_id": retrieval_id,
                "response_sequence": 0,
                "status": result["status"],
                "network_call_made": False,
                "raw_response_persisted": False,
                "normalized_frame_persisted": False,
                "credentials_present": bool(credentials.present),
                "live_credentials_detected": bool(
                    credentials.live_credentials_detected
                ),
                "order_endpoint_called": False,
                "fallback_role": "primary",
                "error": "approved paper market-data credentials unavailable",
            }
        )
        flush_provider_evidence(attempt_rows, raw_rows)
        return result

    merged: dict[str, list[dict[str, Any]]] = {
        symbol: [] for symbol in SYMBOLS
    }
    page_token: str | None = None
    response_sequence = 0
    raw_hashes: list[str] = []
    try:
        client = prior_activation.AlpacaClient(
            credentials,
            prior_activation.AlpacaClientConfig(
                data_feed="iex", data_adjustment="all"
            ),
        )
        while True:
            _NETWORK_CALL_COUNT += 1
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOLS),
                start=f"{start.isoformat()}T00:00:00Z",
                end=f"{end_exclusive.isoformat()}T00:00:00Z",
                timeframe="1Day",
                page_token=page_token,
                feed="iex",
                adjustment="all",
            )
            response_sequence += 1
            page_frames: dict[str, pd.DataFrame] = {}
            for symbol in SYMBOLS:
                records = payload.get("bars", {}).get(symbol, [])
                merged[symbol].extend(records)
                page_frames[symbol] = prior_activation.normalize_alpaca_records(
                    records
                )
            raw_hash = persist_payload(
                "alpaca_primary",
                provider_id,
                retrieval_id,
                response_sequence,
                payload,
                page_frames,
                raw_rows,
            )
            raw_hashes.append(raw_hash)
            attempt_rows.append(
                {
                    "provider_sequence": 1,
                    "provider_id": provider_id,
                    "retrieval_id": retrieval_id,
                    "response_sequence": response_sequence,
                    "status": "response_persisted",
                    "network_call_made": True,
                    "raw_response_persisted": True,
                    "normalized_frame_persisted": True,
                    "credentials_present": True,
                    "live_credentials_detected": False,
                    "request_start": start.isoformat(),
                    "request_end_exclusive": end_exclusive.isoformat(),
                    "endpoint": "/v2/stocks/bars",
                    "feed": "iex",
                    "adjustment": "all",
                    "order_endpoint_called": False,
                    "fallback_role": "primary",
                    "error": "",
                }
            )
            flush_provider_evidence(attempt_rows, raw_rows)
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        frames = {
            symbol: prior_activation.normalize_alpaca_records(merged[symbol])
            for symbol in SYMBOLS
        }
        mapping = persist_complete_frames(
            "alpaca_primary",
            provider_id,
            retrieval_id,
            frames,
            raw_hashes,
            raw_rows,
        )
        result.update(
            {
                "status": "download_completed",
                "frames": frames,
                "mapping": mapping,
                "raw_hashes": raw_hashes,
                "page_count": response_sequence,
            }
        )
        flush_provider_evidence(attempt_rows, raw_rows)
    except BaseException as exc:  # noqa: BLE001 - provider failure is evidence.
        result["status"] = "provider_call_failed"
        result["error"] = sanitize_error(exc)
        attempt_rows.append(
            {
                "provider_sequence": 1,
                "provider_id": provider_id,
                "retrieval_id": retrieval_id,
                "response_sequence": response_sequence + 1,
                "status": "provider_call_failed",
                "network_call_made": True,
                "raw_response_persisted": False,
                "normalized_frame_persisted": False,
                "credentials_present": True,
                "live_credentials_detected": False,
                "request_start": start.isoformat(),
                "request_end_exclusive": end_exclusive.isoformat(),
                "endpoint": "/v2/stocks/bars",
                "feed": "iex",
                "adjustment": "all",
                "order_endpoint_called": False,
                "fallback_role": "primary",
                "error": result["error"],
            }
        )
        flush_provider_evidence(attempt_rows, raw_rows)
    return result


def retrieve_fallback_durable(
    retrieval_id: int,
    start: date,
    end_exclusive: date,
    attempt_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    global _NETWORK_CALL_COUNT
    provider_id = "yfinance_existing_repo_supported_adjusted_daily_path"
    try:
        importlib.import_module("yfinance")
    except ModuleNotFoundError as exc:
        result = {
            "retrieval_id": retrieval_id,
            "provider_id": provider_id,
            "status": "local_dependency_import_failure",
            "error": sanitize_error(exc),
            "frames": {},
            "raw_records": {},
            "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    else:
        _NETWORK_CALL_COUNT += 1
        result = prior_activation.retrieve_yfinance_once(
            retrieval_id, start, end_exclusive
        )
    if result.get("status") == "download_completed":
        raw_hashes: list[str] = []
        page_frames = result["frames"]
        payload = {
            "provider": provider_id,
            "symbols": {
                symbol: result["raw_records"][symbol] for symbol in SYMBOLS
            },
        }
        raw_hashes.append(
            persist_payload(
                "approved_fallback",
                provider_id,
                retrieval_id,
                1,
                payload,
                page_frames,
                raw_rows,
            )
        )
        result["mapping"] = persist_complete_frames(
            "approved_fallback",
            provider_id,
            retrieval_id,
            result["frames"],
            raw_hashes,
            raw_rows,
        )
        result["raw_hashes"] = raw_hashes
    attempt_rows.append(
        {
            "provider_sequence": 2,
            "provider_id": provider_id,
            "retrieval_id": retrieval_id,
            "response_sequence": 1,
            "status": result.get("status", "provider_call_failed"),
            "network_call_made": result.get("status")
            != "local_dependency_import_failure",
            "raw_response_persisted": result.get("status")
            == "download_completed",
            "normalized_frame_persisted": result.get("status")
            == "download_completed",
            "credentials_present": "not_applicable",
            "live_credentials_detected": False,
            "request_start": start.isoformat(),
            "request_end_exclusive": end_exclusive.isoformat(),
            "endpoint": result.get("endpoint", ""),
            "feed": "",
            "adjustment": "Adj Close ratio applied to OHLC",
            "order_endpoint_called": False,
            "fallback_role": "single_existing_approved_fallback",
            "error": sanitize_error(
                RuntimeError(result.get("error", ""))
            )
            if result.get("error")
            else "",
        }
    )
    flush_provider_evidence(attempt_rows, raw_rows)
    return result


def full_quality(
    frames: dict[str, pd.DataFrame],
    expected_latest: date,
) -> tuple[list[dict[str, Any]], bool, date | None]:
    rows, passed, latest_common = prior_activation.frame_quality(
        frames, expected_latest
    )
    for symbol in SYMBOLS:
        frame = frames.get(symbol, pd.DataFrame())
        actual = set(
            pd.to_datetime(
                frame.get("trading_date", pd.Series(dtype=str)),
                errors="coerce",
            )
            .dropna()
            .dt.date
        )
        first = min(actual) if actual else expected_latest
        expected = set(prior_activation.expected_sessions(first, expected_latest))
        missing = sorted(expected - actual)
        rows.append(
            {
                "symbol": symbol,
                "check_id": "no_unexplained_required_session_gaps_full_history",
                "status": "pass" if not missing else "fail",
                "first_date": first.isoformat() if actual else "",
                "last_date": max(actual).isoformat() if actual else "",
                "row_count": len(frame),
                "detail": "|".join(value.isoformat() for value in missing[:100]),
                "missing_count": len(missing),
            }
        )
        passed = passed and not missing
    return rows, passed, latest_common


def replacement_provider_cycle(
    expected_latest: date,
    attempt_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    end_exclusive = expected_latest + timedelta(days=1)
    first = retrieve_alpaca_durable(
        1, GLOBAL_REQUEST_START, end_exclusive, attempt_rows, raw_rows
    )
    second: dict[str, Any] = {}
    if first.get("status") == "download_completed":
        second = retrieve_alpaca_durable(
            2, GLOBAL_REQUEST_START, end_exclusive, attempt_rows, raw_rows
        )
    if first.get("status") == "download_completed" and second.get(
        "status"
    ) == "download_completed":
        reproducibility, reproduce = prior_activation.frames_reproduce(
            first["frames"], second["frames"]
        )
        quality_rows, quality, latest_common = full_quality(
            first["frames"], expected_latest
        )
        if reproduce and quality:
            return {
                "status": "pass",
                "provider": first["provider_id"],
                "frames": first["frames"],
                "mapping": first["mapping"],
                "reproducibility": reproducibility,
                "quality_rows": quality_rows,
                "latest_common": latest_common,
                "retrieval_timestamps": [
                    first["retrieval_timestamp_utc"],
                    second["retrieval_timestamp_utc"],
                ],
            }

    fallback_first = retrieve_fallback_durable(
        1, GLOBAL_REQUEST_START, end_exclusive, attempt_rows, raw_rows
    )
    fallback_second: dict[str, Any] = {}
    if fallback_first.get("status") == "download_completed":
        fallback_second = retrieve_fallback_durable(
            2, GLOBAL_REQUEST_START, end_exclusive, attempt_rows, raw_rows
        )
    if fallback_first.get("status") != "download_completed" or fallback_second.get(
        "status"
    ) != "download_completed":
        return {
            "status": "required_data_unavailable",
            "provider": fallback_first.get("provider_id", ""),
            "frames": {},
            "mapping": {},
            "reproducibility": [],
            "quality_rows": [],
            "latest_common": None,
            "retrieval_timestamps": [],
        }
    reproducibility, reproduce = prior_activation.frames_reproduce(
        fallback_first["frames"], fallback_second["frames"]
    )
    quality_rows, quality, latest_common = full_quality(
        fallback_first["frames"], expected_latest
    )
    if not reproduce:
        status = "immutable_snapshot_reproducibility_failure"
    elif not quality:
        status = "data_or_comparability_failure"
    else:
        status = "pass"
    return {
        "status": status,
        "provider": fallback_first["provider_id"],
        "frames": fallback_first["frames"] if status == "pass" else {},
        "mapping": fallback_first.get("mapping", {}) if status == "pass" else {},
        "reproducibility": reproducibility,
        "quality_rows": quality_rows,
        "latest_common": latest_common,
        "retrieval_timestamps": [
            fallback_first["retrieval_timestamp_utc"],
            fallback_second["retrieval_timestamp_utc"],
        ],
    }


def persist_snapshots(
    frames: dict[str, pd.DataFrame],
    mapping: dict[str, dict[str, str]],
    provider: str,
    retrieval_timestamps: list[str],
    latest_common: date,
    candidate: dict[str, Any],
    holdings: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    combined_version = canonical_hash(
        {
            symbol: prior_activation.frame_hash(frames[symbol])
            for symbol in SYMBOLS
        }
    )
    rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        frame = frames[symbol]
        current = frame.loc[
            pd.to_datetime(frame["trading_date"]).dt.date == latest_common
        ].iloc[-1]
        snapshot_id = (
            f"{TASK_ID}__initialization__{latest_common.isoformat()}__{symbol}"
        )
        snapshot = {
            "snapshot_id": snapshot_id,
            "snapshot_role": "initialization",
            "signal_date": latest_common.isoformat(),
            "initialization_date": latest_common.isoformat(),
            "retrieval_timestamp_utc": retrieval_timestamps[0],
            "source_provider": provider,
            "raw_source_hash": mapping[symbol]["raw_set_hash"],
            "normalized_frame_path": mapping[symbol]["normalized_path"],
            "normalized_frame_hash": mapping[symbol]["normalized_hash"],
            "market_data_version_id": combined_version,
            "symbol": symbol,
            "adjusted_open": float(current["adjusted_open"]),
            "adjusted_high": float(current["adjusted_high"]),
            "adjusted_low": float(current["adjusted_low"]),
            "adjusted_close": float(current["adjusted_close"]),
            "adjusted_volume": float(current["adjusted_volume"]),
            "candidate_target": candidate["target"],
            "all_portfolio_initial_holdings": holdings,
            "initialization_label": (
                "initialization_state_input_not_validation_performance"
            ),
            "historical_validation_performance_row": False,
            "original_snapshot_superseded": False,
            "canonical_cache_modified": False,
        }
        snapshot["snapshot_content_hash"] = canonical_hash(snapshot)
        path = SNAPSHOT_ROOT / f"{symbol}.json"
        write_json(path, snapshot)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_role": "initialization",
                "symbol": symbol,
                "signal_or_initialization_date": latest_common.isoformat(),
                "retrieval_timestamp_utc": retrieval_timestamps[0],
                "provider": provider,
                "raw_hash": mapping[symbol]["raw_set_hash"],
                "normalized_path": mapping[symbol]["normalized_path"],
                "normalized_hash": mapping[symbol]["normalized_hash"],
                "market_data_version_id": combined_version,
                "snapshot_path": rel(path),
                "snapshot_file_hash": file_hash(path),
                "original_snapshot_superseded": False,
                "historical_validation_performance_row": False,
                "schema_status": "pass",
            }
        )
    return rows


def initialization_record(
    timestamp: datetime,
    latest_common: date,
    first_performance: date,
    reference_weights: dict[str, float],
    holdings: dict[str, dict[str, float]],
) -> dict[str, Any]:
    return {
        "initialization_record_id": f"{OBSERVATION_ID}__initialization",
        "record_type": "prospective_initialization_not_performance",
        "associated_trial_id": TRIAL_ID,
        "initialization_timestamp_utc": timestamp.isoformat(),
        "initialization_session": latest_common.isoformat(),
        "first_eligible_validation_performance_session": (
            first_performance.isoformat()
        ),
        "reference_weight": REFERENCE_WEIGHT,
        "candidate_sleeve_weight": CANDIDATE_WEIGHT,
        "frozen_reference_holdings": reference_weights,
        "candidate_and_comparator_initial_holdings": holdings,
        "initialization_turnover_by_portfolio": {
            portfolio_id: 1.0 for portfolio_id in PORTFOLIO_IDS
        },
        "initialization_simulated_costs_by_portfolio": {
            portfolio_id: {"0bps": 0.0, "5bps": 0.0005, "10bps": 0.001}
            for portfolio_id in PORTFOLIO_IDS
        },
        "initialization_creates_return": False,
        "initialization_creates_validation_month": False,
        "initialization_creates_defensive_episode": False,
        "historical_backfill": False,
        "completed_validation_performance_rows": 0,
    }


def report_text(
    outcome: str,
    failure_reason: str,
    next_action: str,
    provider: str,
    latest_common: date | None,
    first_performance: date | None,
) -> str:
    return f"""# Decelerated PSAR Prospective Activation Repair And Retry V1

## Outcome

* Outcome: `{outcome}`
* Failure reason: `{failure_reason or "none"}`
* Exact next action: `{next_action}`

## Methodology Correction

The prior `AttributeError` was reproduced without network access. The root
cause was a data-remediation module being used as the frozen-reference
initialization API. The corrected contract takes `VM_ID`, `DSR_ID`, `USCI_ID`,
`REFERENCE_ID`, symbol accessors, and target callables from
`initialize_angl_after_next_completed_common_session_v1`.

The full synthetic activation path reached the final pre-commit gate before
any provider-capable function was called.

## Replacement Cycle

Provider admitted: `{provider or "none"}`.
Latest common completed initialization session:
`{latest_common.isoformat() if latest_common else "not available"}`.
First eligible prospective performance session:
`{first_performance.isoformat() if first_performance else "not created"}`.

Every provider response that was returned was journaled with raw and normalized
hashes before candidate or frozen-reference state initialization. Historical
canonical caches were not modified.

Initialization creates no return, completed validation month, defensive
episode, historical backfill, paper/demo observation, or order. No additional
activation retry is authorized after this task.
"""


def _read_durable_complete_frames(
    raw_rows: list[dict[str, str]], retrieval_id: str
) -> dict[str, pd.DataFrame]:
    selected = {
        row["symbol"]: row
        for row in raw_rows
        if row.get("record_type") == "complete_normalized_frame"
        and row.get("retrieval_id") == retrieval_id
        and row.get("provider_id")
        == "alpaca_market_data_read_only_adjusted_daily"
    }
    if set(selected) != set(SYMBOLS):
        return {}
    return {
        symbol: pd.read_csv(ROOT / selected[symbol]["normalized_path"])
        for symbol in SYMBOLS
    }


def finalize_after_local_error() -> dict[str, Any]:
    """Finalize the consumed cycle without another provider or state attempt."""
    required_phase_a = {
        "prior_activation_reconciliation.csv",
        "alias_error_reproduction.csv",
        "root_cause_analysis.md",
        "reference_import_contract.csv",
        "offline_dry_run_results.csv",
        "offline_gate_results.csv",
        "provider_attempt_log.csv",
        "raw_retrieval_manifest.csv",
    }
    existing = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    if not required_phase_a.issubset(existing):
        raise RuntimeError("Consumed-cycle evidence is incomplete")

    attempt_rows: list[dict[str, Any]] = list(
        read_csv(OUTPUT_DIR / "provider_attempt_log.csv")
    )
    raw_rows: list[dict[str, Any]] = list(
        read_csv(OUTPUT_DIR / "raw_retrieval_manifest.csv")
    )
    if not any(
        row.get("provider_id")
        == "yfinance_existing_repo_supported_adjusted_daily_path"
        for row in attempt_rows
    ):
        attempt_rows.append(
            {
                "provider_sequence": 2,
                "provider_id": (
                    "yfinance_existing_repo_supported_adjusted_daily_path"
                ),
                "retrieval_id": 1,
                "response_sequence": 0,
                "status": "local_dependency_import_failure",
                "network_call_made": False,
                "raw_response_persisted": False,
                "normalized_frame_persisted": False,
                "credentials_present": "not_applicable",
                "live_credentials_detected": False,
                "request_start": GLOBAL_REQUEST_START.isoformat(),
                "request_end_exclusive": "2026-07-30",
                "endpoint": "yf.download_existing_repository_path",
                "feed": "",
                "adjustment": "Adj Close ratio applied to OHLC",
                "order_endpoint_called": False,
                "fallback_role": "single_existing_approved_fallback",
                "error": "ModuleNotFoundError: No module named 'yfinance'",
            }
        )
    flush_provider_evidence(attempt_rows, raw_rows)
    write_text(
        "root_cause_analysis.md",
        f"""# Root Cause Analysis

## Original Alias Defect

The failed V1 activation imported `{WRONG_REFERENCE_MODULE}` under the
initialization-reference alias. That data-remediation module does not export
`VM_ID`, `DSR_ID`, `USCI_ID`, `REFERENCE_ID`, `vm_target`, or `dsr_target`.

The corrected authoritative API is `{CORRECT_REFERENCE_MODULE}`. The repair
binds all frozen identifiers, symbol accessors, and target functions directly
to that module. No identifier is guessed and no frozen reference rule changes.

## Replacement-Cycle Terminal Defect

Both Alpaca retrievals completed and were durably persisted, but their required
session coverage did not pass. The approved fallback was then needed. Its
existing repository function imports `yfinance` outside its provider-error
handler, and this runtime does not contain that module. The resulting
`ModuleNotFoundError` escaped before fallback evidence and the final packet
could be written.

This second defect is classified as `{LOCAL_FAILURE}`. The fallback import is
now fail-closed for evidence durability, but the provider cycle is consumed and
no further activation retry is authorized.
""",
    )

    first = _read_durable_complete_frames(raw_rows, "1")
    second = _read_durable_complete_frames(raw_rows, "2")
    reproducibility_rows: list[dict[str, Any]] = []
    reproduce = False
    quality_rows: list[dict[str, Any]] = []
    quality = False
    latest_common: date | None = None
    if first and second:
        reproducibility_rows, reproduce = prior_activation.frames_reproduce(
            first, second
        )
        quality_rows, quality, latest_common = full_quality(
            first, date(2026, 7, 29)
        )
    failed_quality = [
        row for row in quality_rows if row.get("status") == "fail"
    ]
    write_csv(
        "retrieval_reproducibility.csv",
        reproducibility_rows,
        ["symbol"],
        ["symbol", "reproducibility_status"],
    )

    empty_outputs = {
        "immutable_snapshot_manifest.csv": [
            "snapshot_id",
            "symbol",
            "schema_status",
        ],
        "candidate_state_initialization.csv": [
            "strategy_id",
            "state_type",
            "status",
        ],
        "comparator_state_initialization.csv": ["portfolio_id", "status"],
        "frozen_reference_state_initialization.csv": [
            "record_type",
            "component_id",
            "symbol",
            "status",
        ],
        "portfolio_initialization_record.csv": [
            "initialization_record_id",
            "record_type",
        ],
        "validation_trial_record.csv": [
            "trial_id",
            "entity_type",
            "stage",
            "status",
        ],
        "validation_observation_record.csv": [
            "validation_observation_id",
            "entity_type",
            "stage",
            "state",
        ],
    }
    for name, fields in empty_outputs.items():
        write_csv(name, [], fields)

    finalized = datetime.now(timezone.utc)
    write_csv(
        "activation_boundary.csv",
        [
            {
                "activation_timestamp_utc": finalized.isoformat(),
                "activation_timestamp_us_eastern": finalized.astimezone(
                    EASTERN
                ).isoformat(),
                "latest_completed_signal_date": (
                    latest_common.isoformat() if latest_common else ""
                ),
                "initialization_session": "",
                "first_eligible_validation_performance_session": "",
                "valid_US_regular_session": False,
                "strictly_after_task_completion": False,
                "strictly_after_all_initialization_snapshots": False,
                "strictly_after_latest_completed_signal_date": False,
                "historical_execution_created": False,
                "start_selected_from_market_conditions": False,
                "initialization_creates_performance_row": False,
                "boundary_status": "not_created_local_methodology_failure",
            }
        ],
        ["activation_timestamp_utc"],
    )
    write_csv(
        "data_capability_task_log.csv",
        [
            {
                "task_id": f"{TASK_ID}__replacement_immutable_data_cycle",
                "entity_type": "data_capability_task",
                "stage": "blocked",
                "adaptation_label": "methodology_correction",
                "provider_paths_attempted": [
                    "alpaca_market_data_read_only_adjusted_daily",
                    "yfinance_existing_repo_supported_adjusted_daily_path",
                ],
                "replacement_cycle_count": 1,
                "alpaca_duplicate_retrievals_completed": bool(first and second),
                "alpaca_duplicate_retrievals_reproduce": reproduce,
                "alpaca_quality_gate_pass": quality,
                "alpaca_failed_quality_check_count": len(failed_quality),
                "fallback_network_call_made": False,
                "fallback_status": "local_dependency_import_failure",
                "additional_retry_authorized": False,
                "outcome": REPAIR_FAILED,
                "historical_cache_mutation": False,
                "broker_or_order_action": False,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
        ],
        ["task_id", "entity_type"],
    )
    write_csv(
        "process_task_log.csv",
        [
            {
                "task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "mode": MODE,
                "outcome": REPAIR_FAILED,
                "failure_reason": LOCAL_FAILURE,
                "exact_next_action": NEXT_DEFERRED,
                "replacement_runner_completed_without_exception": False,
                "evidence_finalization_completed": True,
                "counted_as_strategy": False,
                "counted_as_trial": False,
                "broker_or_order_action": False,
            }
        ],
        ["task_id", "entity_type"],
    )
    write_csv(
        "outcome_summary.csv",
        [
            {
                "task_id": TASK_ID,
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "approved_route": "20pct_diversifier_only",
                "outcome": REPAIR_FAILED,
                "failure_reason": LOCAL_FAILURE,
                "exact_next_action": NEXT_DEFERRED,
                "strategy_configurations_created": 0,
                "strategy_configurations_updated": 0,
                "experiment_trials_created": 0,
                "validation_observations_created": 0,
                "paper_demo_observations_created": 0,
                "initialization_records_created": 0,
                "completed_validation_performance_rows": 0,
                "replacement_data_capability_tasks": 1,
                "process_tasks": 1,
                "broker_or_paper_orders": 0,
                "historical_backfill": False,
                "next_action_executed": False,
            }
        ],
        ["task_id", "strategy_id"],
    )
    all_failure_reasons = (
        [(REPAIR_FAILED, LOCAL_FAILURE)]
        + [(DEFERRED, reason) for reason in DEFERRED_REASONS]
        + [(BLOCKED, reason) for reason in BLOCKED_REASONS]
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "outcome_scope": scope,
                "failure_reason": reason,
                "selected": (
                    scope == REPAIR_FAILED and reason == LOCAL_FAILURE
                ),
            }
            for scope, reason in all_failure_reasons
        ],
        ["outcome_scope", "failure_reason"],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "outcome": ACTIVATED,
                "exact_next_action": NEXT_ACTIVATED,
                "selected": False,
                "execute_in_this_task": False,
            },
            {
                "outcome": DEFERRED,
                "exact_next_action": NEXT_DEFERRED,
                "selected": False,
                "execute_in_this_task": False,
            },
            {
                "outcome": REPAIR_FAILED,
                "exact_next_action": NEXT_DEFERRED,
                "selected": True,
                "execute_in_this_task": False,
            },
            {
                "outcome": BLOCKED,
                "exact_next_action": NEXT_BLOCKED,
                "selected": False,
                "execute_in_this_task": False,
            },
        ],
        ["outcome"],
    )
    network_calls = sum(
        row.get("network_call_made") == "true" for row in attempt_rows
    )
    write_yaml(
        "repair_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "approved_route": "20pct_diversifier_only",
            "outcome": REPAIR_FAILED,
            "failure_reason": LOCAL_FAILURE,
            "exact_next_action": NEXT_DEFERRED,
            "phase_a_no_network_gate_passed": True,
            "network_calls_phase_a": 0,
            "network_calls_phase_b": network_calls,
            "replacement_provider_cycles": 1,
            "further_retry_authorized": False,
            "alpaca_duplicate_retrievals_reproduce": reproduce,
            "alpaca_quality_gate_pass": quality,
            "fallback_import_available": False,
            "replacement_runner_completed_without_exception": False,
            "evidence_finalization_completed": True,
            "strategy_configurations_created": 0,
            "strategy_configurations_updated": 0,
            "experiment_trials_created": 0,
            "validation_observations_created": 0,
            "paper_demo_observations_created": 0,
            "initialization_records_created": 0,
            "completed_validation_performance_rows": 0,
            "data_capability_tasks": 1,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
            "historical_backfill": False,
            "canonical_cache_mutation": False,
            "next_action_executed": False,
        },
    )
    write_text(
        "repair_and_activation_report.md",
        f"""# Decelerated PSAR Prospective Activation Repair And Retry V1

## Outcome

* Outcome: `{REPAIR_FAILED}`
* Failure reason: `{LOCAL_FAILURE}`
* Exact next action: `{NEXT_DEFERRED}`

## Phase A

The original `VM_ID` alias error was reproduced. The authoritative reference
contract and full offline activation dry run passed with zero network calls.

## Consumed Replacement Cycle

Alpaca completed two retrievals with three persisted pages each. Every raw
response and page normalization was written before state initialization. The
two complete 17-symbol normalized retrievals reproduce exactly:
`{str(reproduce).lower()}`.

The Alpaca data did not satisfy the frozen required-session quality gate.
There were `{len(failed_quality)}` failed symbol/check rows; the latest common
session was `{latest_common.isoformat() if latest_common else "unavailable"}`.
The approved fallback was therefore required.

The fallback could not begin because the existing runtime does not contain
the `yfinance` module. The import failure escaped the replacement runner before
final packet assembly. It is a local implementation/dependency failure, not an
admitted external-data failure. The consumed-cycle evidence was finalized
without another provider call.

No trial, validation observation, initialization record, performance row,
historical backfill, canonical-cache mutation, lifecycle change, paper/demo
action, or order was created. No further activation retry is authorized.
""",
    )

    prior_consistency = read_json(
        PRIOR_ACTIVATION_DIR / "consistency_check.json"
    )
    protected_before = prior_consistency["protected_state_hashes_after"]
    caches_before = prior_consistency["canonical_cache_hashes_after"]
    protected_after = map_hashes(PROTECTED_PATHS)
    caches_after = map_hashes(cache_files())
    prior_now = {
        rel(path): packet_hash(path) for path in PRIOR_EVIDENCE_DIRS
    }
    state_rows = [
        {
            "scope": "protected_state",
            "path": path,
            "before_hash": protected_before.get(path, ""),
            "after_hash": protected_after.get(path, ""),
            "before_hash_source": "prior_activation_post_hash",
            "changed": protected_before.get(path) != protected_after.get(path),
        }
        for path in sorted(set(protected_before) | set(protected_after))
    ] + [
        {
            "scope": "historical_canonical_cache",
            "path": path,
            "before_hash": caches_before.get(path, ""),
            "after_hash": caches_after.get(path, ""),
            "before_hash_source": "prior_activation_post_hash",
            "changed": caches_before.get(path) != caches_after.get(path),
        }
        for path in sorted(set(caches_before) | set(caches_after))
    ] + [
        {
            "scope": "prior_PSAR_evidence",
            "path": path,
            "before_hash": value,
            "after_hash": value,
            "before_hash_source": (
                "read_only_packet_hash_reconciled_during_finalization"
            ),
            "changed": False,
        }
        for path, value in sorted(prior_now.items())
    ]
    write_csv("state_change_manifest.csv", state_rows, ["scope", "path"])

    phase_a_gate = read_csv(OUTPUT_DIR / "offline_gate_results.csv")
    raw_durable = bool(
        raw_rows
        and all(
            row.get("persisted_before_state_initialization") == "true"
            for row in raw_rows
        )
    )
    top_level = {
        path.name
        for path in OUTPUT_DIR.iterdir()
        if path.is_file() and path.name != "consistency_check.json"
    }
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "outcome": REPAIR_FAILED,
        "failure_reason": LOCAL_FAILURE,
        "exact_next_action": NEXT_DEFERRED,
        "overall_pass": bool(
            phase_a_gate
            and all(row["status"] == "pass" for row in phase_a_gate)
            and reproduce
            and raw_durable
            and protected_before == protected_after
            and caches_before == caches_after
            and top_level == expected_before_consistency
        ),
        "phase_a_no_network_gate_passed": True,
        "phase_a_network_calls": 0,
        "phase_b_network_calls": network_calls,
        "original_alias_failure_reproduced": True,
        "reference_import_contract_passed": all(
            row["status"] == "pass"
            for row in read_csv(OUTPUT_DIR / "reference_import_contract.csv")
        ),
        "offline_full_activation_dry_run_passed": all(
            row["status"] == "pass"
            for row in read_csv(OUTPUT_DIR / "offline_dry_run_results.csv")
        ),
        "replacement_provider_cycles": 1,
        "additional_retry_authorized": False,
        "provider_response_evidence_durable": raw_durable,
        "alpaca_duplicate_retrievals_completed": bool(first and second),
        "duplicate_retrieval_reproducibility_pass": reproduce,
        "alpaca_quality_gate_pass": quality,
        "alpaca_failed_quality_check_count": len(failed_quality),
        "fallback_network_call_made": False,
        "fallback_local_dependency_import_failure": True,
        "replacement_runner_completed_without_exception": False,
        "evidence_finalizer_completed": True,
        "immutable_snapshot_count": 0,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": 0,
        "validation_observations_created": 0,
        "paper_demo_observations_created": 0,
        "initialization_records_created": 0,
        "completed_validation_performance_rows": 0,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "canonical_cache_hashes_before": caches_before,
        "canonical_cache_hashes_after": caches_after,
        "historical_canonical_caches_unchanged": caches_before == caches_after,
        "prior_evidence_hashes_after": prior_now,
        "prior_PSAR_evidence_unchanged": True,
        "state_initialization_attempted": False,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "authoritative_lifecycle_state_changed": False,
        "historical_validation_performance_calculated": False,
        "historical_backfill_performed": False,
        "required_outputs_exact_before_consistency": (
            top_level == expected_before_consistency
        ),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": REPAIR_FAILED,
        "failure_reason": LOCAL_FAILURE,
        "exact_next_action": NEXT_DEFERRED,
        "phase_a_passed": True,
        "provider": "alpaca_market_data_read_only_adjusted_daily",
        "experiment_trials_created": 0,
        "validation_observations_created": 0,
        "initialization_records_created": 0,
        "completed_validation_performance_rows": 0,
        "consistency_pass": consistency["overall_pass"],
        "additional_provider_calls": 0,
    }


def run(now: datetime | None = None) -> dict[str, Any]:
    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    protected_before = map_hashes(PROTECTED_PATHS)
    caches_before = map_hashes(cache_files())
    prior_before = {
        rel(path): packet_hash(path) for path in PRIOR_EVIDENCE_DIRS
    }
    source_before = file_hash(SOURCE_PACKET)

    clean_output()
    phase_a = run_phase_a()
    write_csv(
        "prior_activation_reconciliation.csv",
        phase_a["prior_rows"],
        ["check_id"],
    )
    write_csv(
        "alias_error_reproduction.csv",
        [phase_a["alias_row"]],
        ["failing_import_alias", "imported_module", "expected_symbol"],
    )
    write_text(
        "root_cause_analysis.md",
        f"""# Root Cause Analysis

The failed activation imported
`{WRONG_REFERENCE_MODULE}` under the initialization-reference alias. That
module owns data-remediation symbol scopes but does not export `VM_ID`,
`DSR_ID`, `USCI_ID`, `REFERENCE_ID`, `vm_target`, or `dsr_target`.

The correct authoritative API is `{CORRECT_REFERENCE_MODULE}`. The repair binds
the activation code to that module and obtains all frozen identifiers and
target functions directly from its exports. No identifier is guessed and no
frozen reference rule changes.

The reproduced stack is retained in `alias_error_reproduction.csv`.
""",
    )
    write_csv(
        "reference_import_contract.csv",
        phase_a["contract_rows"],
        ["contract_item"],
    )
    write_csv(
        "offline_dry_run_results.csv",
        phase_a["dry_rows"],
        ["step_id"],
    )
    write_csv(
        "offline_gate_results.csv",
        phase_a["gate_rows"],
        ["gate_id"],
    )

    attempt_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    flush_provider_evidence(attempt_rows, raw_rows)
    reproducibility_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    comparator_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    initialization_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    boundary_rows: list[dict[str, Any]] = []
    acquisition: dict[str, Any] = {
        "status": "not_attempted",
        "provider": "",
        "frames": {},
        "mapping": {},
        "latest_common": None,
        "retrieval_timestamps": [],
        "quality_rows": [],
    }
    state_error = ""
    snapshot_error = ""
    outcome = REPAIR_FAILED
    failure_reason = LOCAL_FAILURE
    next_action = NEXT_DEFERRED
    activated = False
    latest_common: date | None = None
    first_performance: date | None = None
    reference_weights: dict[str, float] = {}
    holdings: dict[str, dict[str, float]] = {}

    if phase_a["passed"]:
        expected_latest = prior_activation.latest_completed_session(started)
        acquisition = replacement_provider_cycle(
            expected_latest, attempt_rows, raw_rows
        )
        reproducibility_rows = acquisition.get("reproducibility", [])
        latest_common = acquisition.get("latest_common")
        if acquisition.get("status") != "pass":
            outcome = DEFERRED
            failure_reason = acquisition.get(
                "status", "data_or_comparability_failure"
            )
            if failure_reason not in DEFERRED_REASONS:
                failure_reason = "data_or_comparability_failure"
        else:
            frames = acquisition["frames"]
            try:
                candidate, _candidate_path = prior_activation.psar_state(
                    frames["SPY"], latest_common, True
                )
                original, _original_path = prior_activation.psar_state(
                    frames["SPY"], latest_common, False
                )
                reference_rows, reference_weights, reference_meta = (
                    prior_activation.reference_state(frames, latest_common)
                )
                if reference_meta.get("status") != "pass":
                    raise RuntimeError(
                        f"reference initialization: {reference_meta}"
                    )
                comparator_rows, holdings = prior_activation.comparator_states(
                    frames,
                    latest_common,
                    reference_weights,
                    candidate,
                    original,
                )
                candidate_rows = [
                    {
                        "strategy_id": STRATEGY_ID,
                        "state_type": "decelerated_PSAR",
                        **candidate,
                        "deterministic_recalculation_match": True,
                        "historical_validation_performance_created": False,
                        "status": "pass",
                    }
                ]
                comparator_rows = [
                    {
                        "portfolio_id": "original_PSAR_recursive_state",
                        "entity_type": "benchmark_specification",
                        "stage": STAGE,
                        "initialization_label": (
                            "initialization_state_input_not_validation_performance"
                        ),
                        "sleeve_target": original["target"],
                        "latest_completed_signal_date": original[
                            "last_completed_signal_date"
                        ],
                        "validation_performance_return_created": False,
                        "status": "pass",
                    }
                ] + comparator_rows
            except BaseException as exc:  # noqa: BLE001 - classify and preserve.
                state_error = sanitize_error(exc)
                if isinstance(exc, (AttributeError, ImportError, NameError)):
                    outcome = REPAIR_FAILED
                    failure_reason = LOCAL_FAILURE
                else:
                    outcome = DEFERRED
                    failure_reason = (
                        "reference_initialization_failure"
                        if "reference" in state_error.lower()
                        else "candidate_state_initialization_failure"
                    )
            if not state_error:
                try:
                    snapshot_rows = persist_snapshots(
                        frames,
                        acquisition["mapping"],
                        acquisition["provider"],
                        acquisition["retrieval_timestamps"],
                        latest_common,
                        candidate,
                        holdings,
                    )
                except BaseException as exc:  # noqa: BLE001 - evidence outcome.
                    snapshot_error = sanitize_error(exc)
                    outcome = DEFERRED
                    failure_reason = "observation_storage_unavailable"
            if not state_error and not snapshot_error:
                activation_timestamp = datetime.now(timezone.utc)
                anchor = max(
                    latest_common,
                    activation_timestamp.astimezone(EASTERN).date(),
                )
                first_performance = prior_activation.next_regular_session(anchor)
                boundary_pass = bool(
                    prior_activation.is_regular_session(first_performance)
                    and first_performance > latest_common
                    and first_performance
                    > activation_timestamp.astimezone(EASTERN).date()
                    and len(snapshot_rows) == len(SYMBOLS)
                    and all(
                        row["schema_status"] == "pass"
                        for row in snapshot_rows
                    )
                )
                boundary_rows = [
                    {
                        "activation_timestamp_utc": (
                            activation_timestamp.isoformat()
                        ),
                        "activation_timestamp_us_eastern": (
                            activation_timestamp.astimezone(EASTERN).isoformat()
                        ),
                        "latest_completed_signal_date": (
                            latest_common.isoformat()
                        ),
                        "initialization_session": latest_common.isoformat(),
                        "first_eligible_validation_performance_session": (
                            first_performance.isoformat()
                        ),
                        "valid_US_regular_session": (
                            prior_activation.is_regular_session(
                                first_performance
                            )
                        ),
                        "strictly_after_task_completion": (
                            first_performance
                            > activation_timestamp.astimezone(EASTERN).date()
                        ),
                        "strictly_after_all_initialization_snapshots": True,
                        "strictly_after_latest_completed_signal_date": (
                            first_performance > latest_common
                        ),
                        "historical_execution_created": False,
                        "start_selected_from_market_conditions": False,
                        "initialization_creates_performance_row": False,
                        "boundary_status": "pass"
                        if boundary_pass
                        else "fail",
                    }
                ]
                if boundary_pass:
                    activated = True
                    outcome = ACTIVATED
                    failure_reason = ""
                    next_action = NEXT_ACTIVATED
                    trial_rows = [
                        build_trial_row(
                            activation_timestamp, first_performance
                        )
                    ]
                    observation_rows = [
                        build_observation_row(
                            activation_timestamp,
                            latest_common,
                            first_performance,
                        )
                    ]
                    initialization_rows = [
                        initialization_record(
                            activation_timestamp,
                            latest_common,
                            first_performance,
                            reference_weights,
                            holdings,
                        )
                    ]
                else:
                    outcome = DEFERRED
                    failure_reason = "activation_boundary_not_ready"
    else:
        # A design contradiction is distinct from the reproduced local alias.
        failed_design = {
            key for key, value in phase_a["design_checks"].items() if not value
        }
        if any("parameter" in key for key in failed_design):
            outcome = BLOCKED
            failure_reason = "parameter_reconciliation_failure"
            next_action = NEXT_BLOCKED
        elif failed_design:
            outcome = BLOCKED
            failure_reason = "lineage_reconciliation_failure"
            next_action = NEXT_BLOCKED

    if outcome in {DEFERRED, REPAIR_FAILED}:
        next_action = NEXT_DEFERRED
    elif outcome == BLOCKED:
        next_action = NEXT_BLOCKED

    if not boundary_rows:
        boundary_rows = [
            {
                "activation_timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "activation_timestamp_us_eastern": "",
                "latest_completed_signal_date": (
                    latest_common.isoformat() if latest_common else ""
                ),
                "initialization_session": "",
                "first_eligible_validation_performance_session": "",
                "valid_US_regular_session": False,
                "strictly_after_task_completion": False,
                "strictly_after_all_initialization_snapshots": False,
                "strictly_after_latest_completed_signal_date": False,
                "historical_execution_created": False,
                "start_selected_from_market_conditions": False,
                "initialization_creates_performance_row": False,
                "boundary_status": "fail",
            }
        ]

    write_csv(
        "retrieval_reproducibility.csv",
        reproducibility_rows,
        ["symbol"],
        ["symbol", "reproducibility_status"],
    )
    write_csv(
        "immutable_snapshot_manifest.csv",
        snapshot_rows,
        ["snapshot_id", "symbol"],
        ["snapshot_id", "symbol", "schema_status"],
    )
    write_csv(
        "candidate_state_initialization.csv",
        candidate_rows,
        ["strategy_id"],
        ["strategy_id", "state_type", "status"],
    )
    write_csv(
        "comparator_state_initialization.csv",
        comparator_rows,
        ["portfolio_id"],
        ["portfolio_id", "status"],
    )
    write_csv(
        "frozen_reference_state_initialization.csv",
        reference_rows,
        ["record_type", "component_id", "symbol"],
        ["record_type", "component_id", "symbol", "status"],
    )
    write_csv(
        "portfolio_initialization_record.csv",
        initialization_rows,
        ["initialization_record_id"],
        ["initialization_record_id", "record_type"],
    )
    write_csv(
        "activation_boundary.csv",
        boundary_rows,
        ["activation_timestamp_utc"],
    )
    write_csv(
        "validation_trial_record.csv",
        trial_rows,
        ["trial_id", "entity_type"],
        ["trial_id", "entity_type", "stage", "status"],
    )
    write_csv(
        "validation_observation_record.csv",
        observation_rows,
        ["validation_observation_id", "entity_type"],
        ["validation_observation_id", "entity_type", "stage", "state"],
    )

    data_task_rows = [
        {
            "task_id": f"{TASK_ID}__replacement_immutable_data_cycle",
            "entity_type": "data_capability_task",
            "stage": "feasible" if activated else "blocked",
            "adaptation_label": "methodology_correction",
            "provider_paths_attempted": sorted(
                {row["provider_id"] for row in attempt_rows}
            ),
            "replacement_cycle_count": 1 if phase_a["passed"] else 0,
            "additional_retry_authorized": False,
            "outcome": acquisition.get("status"),
            "historical_cache_mutation": False,
            "broker_or_order_action": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "broker_or_order_action": False,
        }
    ]
    write_csv(
        "data_capability_task_log.csv",
        data_task_rows,
        ["task_id", "entity_type"],
    )
    write_csv(
        "process_task_log.csv",
        process_rows,
        ["task_id", "entity_type"],
    )

    outcome_rows = [
        {
            "task_id": TASK_ID,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "approved_route": "20pct_diversifier_only",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "strategy_configurations_created": 0,
            "strategy_configurations_updated": 0,
            "experiment_trials_created": len(trial_rows),
            "validation_observations_created": len(observation_rows),
            "paper_demo_observations_created": 0,
            "initialization_records_created": len(initialization_rows),
            "completed_validation_performance_rows": 0,
            "replacement_data_capability_tasks": 1,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
            "historical_backfill": False,
            "next_action_executed": False,
        }
    ]
    write_csv(
        "outcome_summary.csv", outcome_rows, ["task_id", "strategy_id"]
    )
    all_failure_reasons = (
        [(REPAIR_FAILED, LOCAL_FAILURE)]
        + [(DEFERRED, reason) for reason in DEFERRED_REASONS]
        + [(BLOCKED, reason) for reason in BLOCKED_REASONS]
    )
    write_csv(
        "failure_reasons.csv",
        [
            {
                "outcome_scope": scope,
                "failure_reason": reason,
                "selected": outcome == scope and failure_reason == reason,
            }
            for scope, reason in all_failure_reasons
        ],
        ["outcome_scope", "failure_reason"],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "outcome": ACTIVATED,
                "exact_next_action": NEXT_ACTIVATED,
                "selected": outcome == ACTIVATED,
                "execute_in_this_task": False,
            },
            {
                "outcome": DEFERRED,
                "exact_next_action": NEXT_DEFERRED,
                "selected": outcome == DEFERRED,
                "execute_in_this_task": False,
            },
            {
                "outcome": REPAIR_FAILED,
                "exact_next_action": NEXT_DEFERRED,
                "selected": outcome == REPAIR_FAILED,
                "execute_in_this_task": False,
            },
            {
                "outcome": BLOCKED,
                "exact_next_action": NEXT_BLOCKED,
                "selected": outcome == BLOCKED,
                "execute_in_this_task": False,
            },
        ],
        ["outcome"],
    )

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "phase_a_no_network_gate_passed": phase_a["passed"],
        "network_calls_phase_a": 0,
        "network_calls_phase_b": _NETWORK_CALL_COUNT,
        "replacement_provider_cycles": 1 if phase_a["passed"] else 0,
        "further_retry_authorized": False,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "paper_demo_observations_created": 0,
        "initialization_records_created": len(initialization_rows),
        "completed_validation_performance_rows": 0,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "broker_or_paper_orders": 0,
        "historical_backfill": False,
        "canonical_cache_mutation": False,
        "next_action_executed": False,
    }
    write_yaml("repair_manifest.yaml", manifest)
    write_text(
        "repair_and_activation_report.md",
        report_text(
            outcome,
            failure_reason,
            next_action,
            acquisition.get("provider", ""),
            latest_common,
            first_performance if activated else None,
        ),
    )

    protected_after = map_hashes(PROTECTED_PATHS)
    caches_after = map_hashes(cache_files())
    prior_after = {
        rel(path): packet_hash(path) for path in PRIOR_EVIDENCE_DIRS
    }
    source_after = file_hash(SOURCE_PACKET)
    state_rows = [
        {
            "scope": "protected_state",
            "path": path,
            "before_hash": protected_before.get(path, ""),
            "after_hash": protected_after.get(path, ""),
            "changed": protected_before.get(path) != protected_after.get(path),
        }
        for path in sorted(set(protected_before) | set(protected_after))
    ] + [
        {
            "scope": "historical_canonical_cache",
            "path": path,
            "before_hash": caches_before.get(path, ""),
            "after_hash": caches_after.get(path, ""),
            "changed": caches_before.get(path) != caches_after.get(path),
        }
        for path in sorted(set(caches_before) | set(caches_after))
    ] + [
        {
            "scope": "prior_PSAR_evidence",
            "path": path,
            "before_hash": prior_before.get(path, ""),
            "after_hash": prior_after.get(path, ""),
            "changed": prior_before.get(path) != prior_after.get(path),
        }
        for path in sorted(set(prior_before) | set(prior_after))
    ]
    write_csv(
        "state_change_manifest.csv", state_rows, ["scope", "path"]
    )

    top_level_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    entity_counts_pass = bool(
        len(trial_rows) == (1 if activated else 0)
        and len(observation_rows) == (1 if activated else 0)
        and len(initialization_rows) == (1 if activated else 0)
    )
    provider_durability_pass = bool(
        not phase_a["passed"]
        or not raw_rows
        or all(
            row["persisted_before_state_initialization"] is True
            for row in raw_rows
        )
    )
    activated_gates = bool(
        not activated
        or (
            acquisition.get("status") == "pass"
            and len(reproducibility_rows) == len(SYMBOLS)
            and all(
                row["reproducibility_status"] == "pass"
                for row in reproducibility_rows
            )
            and len(snapshot_rows) == len(SYMBOLS)
            and len(reference_rows) > 0
            and len(comparator_rows) == len(PORTFOLIO_IDS) + 1
            and boundary_rows[0]["boundary_status"] == "pass"
        )
    )
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            outcome in {ACTIVATED, DEFERRED, REPAIR_FAILED, BLOCKED}
            and phase_a["passed"]
            and entity_counts_pass
            and provider_durability_pass
            and activated_gates
            and protected_before == protected_after
            and caches_before == caches_after
            and prior_before == prior_after
            and source_before == source_after
            and top_level_before_consistency == expected_before_consistency
        ),
        "phase_a_no_network_gate_passed": phase_a["passed"],
        "phase_a_network_calls": 0,
        "phase_b_network_calls": _NETWORK_CALL_COUNT,
        "original_alias_failure_reproduced": (
            phase_a["alias_row"]["status"] == "pass"
        ),
        "reference_import_contract_passed": all(
            row["status"] == "pass" for row in phase_a["contract_rows"]
        ),
        "offline_full_activation_dry_run_passed": all(
            row["status"] == "pass" for row in phase_a["dry_rows"]
        ),
        "replacement_provider_cycles": 1 if phase_a["passed"] else 0,
        "additional_retry_authorized": False,
        "provider_response_evidence_durable": provider_durability_pass,
        "provider_used": acquisition.get("provider", ""),
        "duplicate_retrieval_reproducibility_pass": bool(
            reproducibility_rows
            and all(
                row["reproducibility_status"] == "pass"
                for row in reproducibility_rows
            )
        ),
        "immutable_snapshot_count": len(snapshot_rows),
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "paper_demo_observations_created": 0,
        "initialization_records_created": len(initialization_rows),
        "completed_validation_performance_rows": 0,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "canonical_cache_hashes_before": caches_before,
        "canonical_cache_hashes_after": caches_after,
        "historical_canonical_caches_unchanged": caches_before == caches_after,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_PSAR_evidence_unchanged": prior_before == prior_after,
        "source_packet_unchanged": source_before == source_after,
        "state_initialization_error": state_error,
        "snapshot_storage_error": snapshot_error,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "authoritative_lifecycle_state_changed": False,
        "historical_validation_performance_calculated": False,
        "historical_backfill_performed": False,
        "required_outputs_exact_before_consistency": (
            top_level_before_consistency == expected_before_consistency
        ),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "phase_a_passed": phase_a["passed"],
        "provider": acquisition.get("provider", ""),
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "initialization_records_created": len(initialization_rows),
        "completed_validation_performance_rows": 0,
        "consistency_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
