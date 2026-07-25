from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - repository environments normally include PyYAML.
    yaml = None


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1" / "latest"
)

TASK_ID = "tournament_strategy_readiness_inventory_v1"
TASK_OUTCOME_COMPLETE = "tournament_readiness_report_complete"
TASK_OUTCOME_WITH_CONFLICTS = "tournament_readiness_report_complete_with_conflicts"
NEXT_ACTION = "direction_owner_audit_tournament_strategy_readiness_report_v1"

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
]

STAGES = [
    "exploration_completed_not_advanced",
    "exploratory_followup_candidate",
    "validation_or_promotion_review_candidate",
    "paper_demo_eligible_not_active",
    "paper_demo_active_observation",
    "benchmark_or_reference_only",
    "blocked_or_deferred",
    "closed_no_advancement",
    "status_reconciliation_required",
]

STAGE_RANK = {
    "paper_demo_active_observation": 90,
    "paper_demo_eligible_not_active": 80,
    "validation_or_promotion_review_candidate": 70,
    "exploratory_followup_candidate": 60,
    "exploration_completed_not_advanced": 50,
    "benchmark_or_reference_only": 40,
    "closed_no_advancement": 30,
    "blocked_or_deferred": 20,
    "status_reconciliation_required": 10,
}

DEMO_READY_STAGES = {"paper_demo_eligible_not_active", "paper_demo_active_observation"}
ADVANCED_RESULT_STAGES = {
    "validation_or_promotion_review_candidate",
    "paper_demo_eligible_not_active",
    "paper_demo_active_observation",
}

ACTIVE_OBSERVATION_EVIDENCE = {
    "paper_forward_vm_quality_lowvol_proxy_v1": {
        "base_strategy_id": "vm_quality_lowvol_proxy_v1",
        "family_id": "volatility_managed_equity_etf",
        "display_name": "VM quality low-vol proxy",
        "evidence_path": "evidence/paper_forward_activations/vm_quality_lowvol_proxy_v1/latest",
        "activation_manifest": "manifest.json",
        "configuration_file": "paper_forward_vm_quality_lowvol_proxy_v1_active_observation.yaml",
        "primary_instrument_universe": "SPLV|USMV|QUAL|SPY|BIL",
        "strategy_architecture": "quality_low_vol_rotation_with_spy_regime_and_bil_fallback",
        "classification": "long_cash_rotation",
        "primary_benchmark_control": "SPY_200d_trend_model|BIL_cash_proxy",
    },
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": {
        "base_strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
        "family_id": "defensive_sector_rotation_etf",
        "display_name": "DSR sector equal-weight defensive filter",
        "evidence_path": "evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1/latest",
        "activation_manifest": "manifest.json",
        "configuration_file": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1_active_observation.yaml",
        "primary_instrument_universe": "XLK|XLV|XLY|XLP|XLF|XLI|XLE|XLU|XLB|XLRE|BIL",
        "strategy_architecture": "sector_equal_weight_with_200d_defensive_filter_and_bil_remainder",
        "classification": "long_cash_rotation",
        "primary_benchmark_control": "SPY_200d_trend_model|BIL_cash_proxy",
    },
    "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1": {
        "base_strategy_id": "usci_dynamic_commodity_curve_selection_wrapper_v1",
        "family_id": "commodity_curve_selection",
        "display_name": "USCI dynamic commodity curve-selection wrapper",
        "evidence_path": "evidence/usci_paper_forward_eligibility_review_v1/latest",
        "activation_manifest": "paper_forward_decision.json",
        "configuration_file": "observation_configuration.json",
        "primary_instrument_universe": "USCI",
        "strategy_architecture": "static_single_wrapper_observation",
        "classification": "long_only_wrapper_observation",
        "primary_benchmark_control": "DBC|BIL|SPY",
    },
    "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1": {
        "base_strategy_id": "combo_vm_dsr_usci_equal_weight_monthly_v1",
        "family_id": "multi_strategy_diversified_portfolio",
        "display_name": "Equal-weight VM/DSR/USCI paper-forward combo",
        "evidence_path": "evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest",
        "activation_manifest": "paper_forward_decision.json",
        "configuration_file": "observation_configuration.json",
        "primary_instrument_universe": "paper_forward_vm_quality_lowvol_proxy_v1|paper_forward_dsr_sector_equal_weight_defensive_filter_v1|paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "strategy_architecture": "equal_weight_observation_portfolio_of_existing_active_observations",
        "classification": "multi_strategy_combo_observation",
        "primary_benchmark_control": "active_combo_vm_dsr_equal_weight_v1",
    },
}

RECENT_FAST_LANES = [
    {
        "display_name": "ADX/DMI",
        "strategy_id": "adx_dmi_spy_bil_primary_v1",
        "family_id": "equity_index_adx_dmi_trend_strength",
        "evidence_path": "evidence/research_recovery/public_source_adx_dmi_bounded_bt_results_audit/latest",
        "manifest": "public_source_adx_dmi_bounded_bt_results_audit_manifest.json",
    },
    {
        "display_name": "CCI Correction",
        "strategy_id": "cci_correction_spy_bil_primary_v1",
        "family_id": "equity_index_cci_pullback_trend_bias",
        "evidence_path": "evidence/research_recovery/public_source_cci_correction_bounded_bt_results_audit/latest",
        "manifest": "public_source_cci_correction_bounded_bt_results_audit_manifest.json",
    },
    {
        "display_name": "Larry Connors RSI(2)",
        "strategy_id": "connors_rsi2_spy_bil_primary_v1",
        "family_id": "short_term_equity_mean_reversion",
        "evidence_path": "evidence/research_recovery/public_source_larry_connors_rsi2_final_state_reconciliation/latest",
        "manifest": "larry_connors_rsi2_final_state_reconciliation_manifest.json",
    },
    {
        "display_name": "Coppock Curve",
        "strategy_id": "coppock_spy_bil_monthly_zero_cross_primary_v1",
        "family_id": "long_term_equity_index_momentum_zero_cross",
        "evidence_path": "evidence/research_recovery/public_source_coppock_curve_final_state_reconciliation/latest",
        "manifest": "public_source_coppock_curve_final_state_reconciliation_manifest.json",
    },
    {
        "display_name": "Parabolic SAR",
        "strategy_id": "parabolic_sar_spy_bil_primary_v1",
        "family_id": "equity_index_parabolic_sar_trend_reversal",
        "evidence_path": "evidence/research_recovery/public_source_parabolic_sar_bounded_bt_run/latest",
        "manifest": "public_source_parabolic_sar_bounded_bt_run_manifest.json",
    },
    {
        "display_name": "MACD 12/26/9",
        "strategy_id": "fidelity_macd_12_26_9_signal_crossover_etf_bil_v1",
        "family_id": "macd_signal_line_trend_timing",
        "evidence_path": "evidence/fast_progress/fidelity_macd_12_26_9_signal_crossover_portability_v1/latest",
        "manifest": "family_outcome.json",
    },
    {
        "display_name": "Faber GTAA5",
        "strategy_id": "faber_gtaa5_10m_sma_equal_weight_etf_bil_v1",
        "family_id": "multi_asset_independent_trend_allocation",
        "evidence_path": "evidence/fast_progress/faber_gtaa5_10m_sma_equal_weight_etf_bil_v1/latest",
        "manifest": "family_outcome.json",
    },
    {
        "display_name": "Antonacci GEM",
        "strategy_id": "antonacci_gem_12m_global_equities_bond_v1",
        "family_id": "global_equity_dual_momentum_rotation",
        "evidence_path": "evidence/fast_progress/antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1/latest",
        "manifest": "family_outcome.json",
    },
    {
        "display_name": "VAA-G4",
        "strategy_id": "keller_keuning_vaa_g4_13612w_v1",
        "family_id": "breadth_gated_offensive_defensive_rotation",
        "evidence_path": "evidence/fast_progress/keller_keuning_vaa_g4_13612w_v1/latest",
        "manifest": "family_outcome.json",
    },
]


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def abs_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return ROOT / p


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def parse_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value))
    except (TypeError, ValueError):
        return None


def sha256_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def sha256_directory(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(rel(file_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_path(file_path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest().lower()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def row_count_for_source(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_dir():
        return len([p for p in path.iterdir() if p.is_file()])
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return len(read_csv_rows(path))
    if suffix == ".json":
        payload = read_json(path)
        if isinstance(payload, dict):
            return len(payload)
    if suffix in {".yaml", ".yml"}:
        payload = read_yaml(path)
        if isinstance(payload, dict):
            return len(payload)
    return 1


def source_digest(path: Path) -> str:
    if path.is_dir():
        return sha256_directory(path)
    return sha256_path(path)


def clean_output_dir() -> None:
    if EVIDENCE_DIR.exists():
        resolved = EVIDENCE_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1").resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected evidence path: {resolved}")
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def protected_hashes() -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in PROTECTED_STATE_PATHS}


def build_source_inventory() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []

    def add(
        source_id: str,
        path: str | Path,
        source_type: str,
        precedence: int,
        role: str,
        notes: str = "",
    ) -> None:
        p = abs_path(path)
        sources.append(
            {
                "source_id": source_id,
                "source_type": source_type,
                "path": rel(p),
                "exists": p.exists(),
                "precedence": precedence,
                "role": role,
                "record_count": row_count_for_source(p),
                "sha256": source_digest(p),
                "notes": notes,
            }
        )

    add("strategy_registry", "strategy_lab/strategy_registry.yaml", "registry", 4, "registry_state")
    add("research_roadmap", "strategy_lab/RESEARCH_ROADMAP.md", "roadmap", 5, "roadmap_state")
    add(
        "active_observations",
        "strategy_lab/research_os/operations/active_observations.yaml",
        "active_observation_state",
        2,
        "current_active_configuration",
        "Highest-precedence current active paper/demo source inspected by this report.",
    )
    add("research_queue", "strategy_lab/research_os/research/research_queue.yaml", "queue", 4, "queue_state")
    add(
        "family_ledger",
        "strategy_lab/research_os/family_lineage/family_ledger.yaml",
        "family_lineage",
        4,
        "lineage_state",
    )
    add(
        "current_research_checkpoint",
        "evidence/current_research_checkpoint/latest",
        "checkpoint_evidence",
        3,
        "current_checkpoint",
    )
    add(
        "strategy_evidence_library",
        "evidence/strategy_evidence_library/latest",
        "strategy_evidence_library",
        3,
        "provenance_inventory",
    )
    add(
        "paper_forward_vm_activation",
        "evidence/paper_forward_activations/vm_quality_lowvol_proxy_v1/latest",
        "paper_forward_activation",
        3,
        "eligibility_and_activation",
    )
    add(
        "paper_forward_dsr_activation",
        "evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1/latest",
        "paper_forward_activation",
        3,
        "eligibility_and_activation",
    )
    add(
        "paper_forward_usci_eligibility",
        "evidence/usci_paper_forward_eligibility_review_v1/latest",
        "paper_forward_eligibility_review",
        3,
        "eligibility_and_activation",
    )
    add(
        "paper_forward_combo_vm_dsr_usci_eligibility",
        "evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest",
        "paper_forward_eligibility_review",
        3,
        "eligibility_and_activation",
    )
    add(
        "current_paper_forward_update",
        "evidence/current_paper_forward_update_and_reconciliation_v1/latest",
        "paper_forward_monitoring",
        3,
        "operational_monitoring",
    )
    add(
        "historical_paper_forward_runs",
        "evidence/paper_forward_runs/latest",
        "historical_paper_forward_report",
        6,
        "historical_lower_precedence",
        "Historical paper-forward status was inspected but not used to override current active_observations.yaml.",
    )
    for lane in RECENT_FAST_LANES:
        add(
            f"recent_fast_lane_{lane['strategy_id']}",
            lane["evidence_path"],
            "recent_fast_lane_evidence",
            3,
            "recent_fast_lane_accounting",
        )
    return sorted(sources, key=lambda row: (int(row["precedence"]), str(row["source_id"])))


def classify_sel_stage(row: dict[str, str]) -> str:
    status = " ".join(
        [
            row.get("current_status", ""),
            row.get("status_detail", ""),
            row.get("rejection_failure_codes", ""),
            row.get("variant_id", ""),
        ]
    ).lower()
    if any(token in status for token in ["benchmark", "control", "cash_proxy", "watchlist_reference"]):
        return "benchmark_or_reference_only"
    if any(token in status for token in ["paper_forward_active", "active_paper_demo_observation"]):
        return "status_reconciliation_required"
    if "paper_forward_eligible" in status or "paper_demo_eligible" in status:
        return "paper_demo_eligible_not_active"
    if (
        "promotion_review_passed" in status
        or "create_promotion_review" in status
        or "candidate_exhaustive" in status
    ):
        return "status_reconciliation_required"
    if "promotion_review_candidate" in status or "validation_or_promotion_review_candidate" in status:
        return "validation_or_promotion_review_candidate"
    if "followup" in status or "follow-up" in status or "design_volatility_throttle" in status:
        return "exploratory_followup_candidate"
    if any(
        token in status
        for token in [
            "closed",
            "rejected",
            "duplicate",
            "do_not_retest",
            "control_weak",
            "no_advancement",
            "fragile",
            "cost_sensitive",
            "return_destroyed",
            "holdout_does_not_confirm",
        ]
    ):
        return "closed_no_advancement"
    if any(token in status for token in ["blocked", "data_unavailable", "incomplete", "pending", "paused"]):
        return "blocked_or_deferred"
    if parse_int(row.get("identifiable_backtest_runs")) > 0:
        return "exploration_completed_not_advanced"
    return "blocked_or_deferred"


def build_exact_inventory(
    active_config: dict[str, Any],
    current_best_rows: list[dict[str, str]],
    recent_fast_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    sel_path = ROOT / "evidence" / "strategy_evidence_library" / "latest" / "strategy_inventory.csv"
    for row in read_csv_rows(sel_path):
        strategy_id = row.get("variant_id", "")
        if not strategy_id:
            continue
        stage = classify_sel_stage(row)
        trial_count = parse_int(row.get("identifiable_backtest_runs"))
        inventory[strategy_id] = {
            "strategy_id": strategy_id,
            "family_id": row.get("family", "unknown") or "unknown",
            "display_name": strategy_id.replace("_", " "),
            "current_highest_verified_stage": stage,
            "active_or_inactive": "inactive",
            "paper_demo_eligible": stage in DEMO_READY_STAGES,
            "paper_demo_active": stage == "paper_demo_active_observation",
            "benchmark_reference_only": stage == "benchmark_or_reference_only",
            "real_money_authorized": False,
            "primary_instrument_universe": row.get("instruments_or_universe", "unknown"),
            "strategy_architecture": row.get("family", "unknown"),
            "long_cash_rotation_classification": "unknown",
            "source_or_research_lineage": row.get("source_type", "unknown"),
            "latest_evidence_outcome": row.get("status_detail", row.get("current_status", "")),
            "latest_direction_decision": row.get("current_status", ""),
            "reason_for_advancement_closure_or_deferral": row.get("rejection_failure_codes", ""),
            "latest_evidence_date": "",
            "evaluation_period": "",
            "trial_count": trial_count,
            "parameter_configuration_count": 1 if trial_count else 0,
            "primary_benchmark_control": "",
            "static_exposure_control_used": "unknown",
            "identity_overlay_equality_required_or_passed": "unknown",
            "latest_evidence_path": rel(sel_path),
            "current_registry_path": "strategy_lab/strategy_registry.yaml",
            "active_observation_path": "",
            "status_conflicts": "",
            "missing_artifacts": f"missing_metadata_count={row.get('missing_metadata_count', '')}",
            "implemented_evidence": trial_count > 0,
            "source_fingerprint": row.get("strategy_fingerprint", ""),
        }

    current_best_by_id = {row.get("strategy_id", ""): row for row in current_best_rows}
    for row in current_best_rows:
        strategy_id = row.get("strategy_id", "")
        if not strategy_id:
            continue
        role = row.get("role", "")
        status = row.get("status", "")
        lower = f"{role} {status} {strategy_id}".lower()
        if "active_paper_demo_observation" in lower:
            stage = "paper_demo_active_observation"
        elif any(token in lower for token in ["benchmark", "control", "cash", "reference", "watchlist"]):
            stage = "benchmark_or_reference_only"
        else:
            stage = "status_reconciliation_required"
        existing = inventory.get(strategy_id, {})
        family_id = existing.get("family_id", "unknown")
        if strategy_id == "active_combo_vm_dsr_equal_weight_v1":
            family_id = "active_combo_benchmark_reference"
        elif strategy_id == "SPY_200d_trend_model":
            family_id = "equity_index_trend_control"
        elif strategy_id == "BIL_cash_proxy":
            family_id = "cash_proxy_benchmark"
        elif strategy_id == "lvq_lowvol_quality_spy_regime_v1":
            family_id = "defensive_factor_rotation_watchlist"
        inventory[strategy_id] = {
            **existing,
            "strategy_id": strategy_id,
            "family_id": family_id,
            "display_name": existing.get("display_name", strategy_id.replace("_", " ")),
            "current_highest_verified_stage": stage,
            "active_or_inactive": "active" if stage == "paper_demo_active_observation" else "inactive",
            "paper_demo_eligible": stage in DEMO_READY_STAGES,
            "paper_demo_active": stage == "paper_demo_active_observation",
            "benchmark_reference_only": stage == "benchmark_or_reference_only",
            "real_money_authorized": False,
            "primary_instrument_universe": existing.get("primary_instrument_universe", "see_latest_evidence"),
            "strategy_architecture": role,
            "long_cash_rotation_classification": existing.get("long_cash_rotation_classification", "benchmark_or_watchlist"),
            "source_or_research_lineage": row.get("evidence_source", ""),
            "latest_evidence_outcome": status,
            "latest_direction_decision": row.get("recommended_action", ""),
            "reason_for_advancement_closure_or_deferral": row.get("caveat", ""),
            "latest_evidence_date": "",
            "evaluation_period": "180d diagnostic where present",
            "trial_count": existing.get("trial_count", 1),
            "parameter_configuration_count": existing.get("parameter_configuration_count", 1),
            "primary_benchmark_control": "current_research_checkpoint_controls",
            "static_exposure_control_used": "unknown",
            "identity_overlay_equality_required_or_passed": "unknown",
            "latest_evidence_path": "evidence/current_research_checkpoint/latest/current_best_strategy_set.csv",
            "current_registry_path": "strategy_lab/strategy_registry.yaml",
            "active_observation_path": "",
            "status_conflicts": existing.get("status_conflicts", ""),
            "missing_artifacts": "" if stage != "benchmark_or_reference_only" else "metrics unavailable where checkpoint marks missing_or_unavailable",
            "implemented_evidence": True,
            "source_fingerprint": existing.get("source_fingerprint", ""),
        }

    active_rows = active_config.get("active_observations", [])
    for active_row in active_rows:
        strategy_id = active_row.get("strategy_id", "")
        if not strategy_id or not parse_bool(active_row.get("paper_forward_active")):
            continue
        meta = ACTIVE_OBSERVATION_EVIDENCE.get(strategy_id, {})
        checkpoint_row = current_best_by_id.get(strategy_id, {})
        evidence_path = meta.get("evidence_path", "strategy_lab/research_os/operations/active_observations.yaml")
        activation_date = latest_evidence_date_for_active(meta)
        inventory[strategy_id] = {
            "strategy_id": strategy_id,
            "family_id": meta.get("family_id", "unknown"),
            "display_name": meta.get("display_name", strategy_id.replace("_", " ")),
            "current_highest_verified_stage": "paper_demo_active_observation",
            "active_or_inactive": "active",
            "paper_demo_eligible": True,
            "paper_demo_active": True,
            "benchmark_reference_only": False,
            "real_money_authorized": False,
            "primary_instrument_universe": meta.get("primary_instrument_universe", "unknown"),
            "strategy_architecture": meta.get("strategy_architecture", "active_paper_demo_observation"),
            "long_cash_rotation_classification": meta.get("classification", "unknown"),
            "source_or_research_lineage": evidence_path,
            "latest_evidence_outcome": active_row.get("state", "active_accepted_frozen_observation"),
            "latest_direction_decision": "observe_only",
            "reason_for_advancement_closure_or_deferral": checkpoint_row.get("caveat", "current active observation source-of-truth"),
            "latest_evidence_date": activation_date,
            "evaluation_period": checkpoint_row.get("evaluation_period", ""),
            "trial_count": 1,
            "parameter_configuration_count": 1,
            "primary_benchmark_control": meta.get("primary_benchmark_control", ""),
            "static_exposure_control_used": "unknown",
            "identity_overlay_equality_required_or_passed": "not_applicable_or_not_reported",
            "latest_evidence_path": evidence_path,
            "current_registry_path": "strategy_lab/strategy_registry.yaml",
            "active_observation_path": "strategy_lab/research_os/operations/active_observations.yaml",
            "status_conflicts": "",
            "missing_artifacts": "",
            "implemented_evidence": True,
            "source_fingerprint": "",
        }

    for lane_row in recent_fast_rows:
        strategy_id = lane_row.get("strategy_id", "")
        if not strategy_id:
            continue
        if strategy_id in inventory and inventory[strategy_id].get("current_highest_verified_stage") == "paper_demo_active_observation":
            continue
        family_outcome = str(lane_row.get("exact_family_outcome", ""))
        if "candidate" in family_outcome.lower():
            stage = "exploratory_followup_candidate"
        elif "blocked" in family_outcome.lower():
            stage = "blocked_or_deferred"
        elif any(token in family_outcome.lower() for token in ["weak", "fragile", "failed", "closed"]):
            stage = "closed_no_advancement"
        else:
            stage = "exploration_completed_not_advanced"
        existing = inventory.get(strategy_id, {})
        inventory[strategy_id] = {
            **existing,
            "strategy_id": strategy_id,
            "family_id": lane_row.get("family_id") or existing.get("family_id", "unknown"),
            "display_name": lane_row.get("display_name") or existing.get("display_name", strategy_id.replace("_", " ")),
            "current_highest_verified_stage": stage,
            "active_or_inactive": "inactive",
            "paper_demo_eligible": False,
            "paper_demo_active": False,
            "benchmark_reference_only": False,
            "real_money_authorized": False,
            "primary_instrument_universe": existing.get("primary_instrument_universe", "see_recent_fast_lane_evidence"),
            "strategy_architecture": lane_row.get("display_name", ""),
            "long_cash_rotation_classification": existing.get("long_cash_rotation_classification", "research_lane"),
            "source_or_research_lineage": lane_row.get("evidence_path", ""),
            "latest_evidence_outcome": lane_row.get("exact_family_outcome", ""),
            "latest_direction_decision": lane_row.get("advancement_decision", ""),
            "reason_for_advancement_closure_or_deferral": lane_row.get("family_outcome_reason", ""),
            "latest_evidence_date": lane_row.get("created_utc", ""),
            "evaluation_period": lane_row.get("evaluation_period", ""),
            "trial_count": parse_int(lane_row.get("trial_count"), 1),
            "parameter_configuration_count": 1,
            "primary_benchmark_control": lane_row.get("primary_benchmark_control", ""),
            "static_exposure_control_used": lane_row.get("passed_static_controls", "unknown"),
            "identity_overlay_equality_required_or_passed": "not_applicable",
            "latest_evidence_path": lane_row.get("evidence_path", ""),
            "current_registry_path": "strategy_lab/strategy_registry.yaml",
            "active_observation_path": "",
            "status_conflicts": "",
            "missing_artifacts": lane_row.get("missing_artifacts", ""),
            "implemented_evidence": True,
            "source_fingerprint": existing.get("source_fingerprint", ""),
        }

    return sorted(inventory.values(), key=lambda row: (str(row.get("family_id", "")), str(row.get("strategy_id", ""))))


def latest_evidence_date_for_active(meta: dict[str, str]) -> str:
    evidence_path = abs_path(meta.get("evidence_path", ""))
    manifest = evidence_path / meta.get("activation_manifest", "")
    if manifest.suffix == ".json":
        payload = read_json(manifest)
        return str(payload.get("created_utc", payload.get("decision_date", payload.get("activation_date", ""))))
    if manifest.suffix in {".yaml", ".yml"}:
        payload = read_yaml(manifest)
        return str(payload.get("created_utc", payload.get("activation_date", "")))
    return ""


def parse_recent_fast_lane(lane: dict[str, str]) -> dict[str, Any]:
    path = abs_path(lane["evidence_path"])
    manifest_path = path / lane["manifest"]
    manifest = read_json(manifest_path)
    family_outcome = (
        manifest.get("family_outcome")
        or manifest.get("audit_decision")
        or manifest.get("final_larry_connors_rsi2_status")
        or manifest.get("final_coppock_curve_status")
        or manifest.get("primary_row_numeric_criteria_pass")
        or manifest.get("latest_outcome")
        or "missing"
    )
    if lane["display_name"] == "Parabolic SAR":
        family_outcome = "primary_row_numeric_criteria_failed"
    passed_full_period = infer_full_period_control_pass(manifest, path)
    passed_static = infer_static_control_pass(manifest, path)
    timeframe_nonnegative = infer_timeframe_nonnegative(path)
    paper_eligible = parse_bool(manifest.get("paper_forward_eligibility")) or parse_bool(
        manifest.get("paper_demo_eligible")
    )
    promotion_eligible = parse_bool(manifest.get("promotion_eligibility"))
    candidate_exhaustive = parse_bool(manifest.get("candidate_exhaustive_eligibility")) or parse_bool(
        manifest.get("candidate_exhaustive_ready")
    )
    if paper_eligible:
        advancement = "paper_demo_eligible"
    elif promotion_eligible or candidate_exhaustive:
        advancement = "validation_or_promotion_review_candidate"
    else:
        advancement = "no_advancement_or_direction_owner_review_required"
    missing = "" if path.exists() and manifest_path.exists() else "missing_manifest_or_evidence_path"
    return {
        "display_name": lane["display_name"],
        "strategy_id": lane["strategy_id"],
        "family_id": lane["family_id"],
        "exact_family_outcome": family_outcome,
        "passed_full_period_controls": passed_full_period,
        "passed_static_controls": passed_static,
        "both_existing_timeframe_diagnostics_nonnegative": timeframe_nonnegative,
        "advancement_decision": advancement,
        "paper_demo_eligible": paper_eligible,
        "promotion_eligible": promotion_eligible,
        "candidate_exhaustive_eligible": candidate_exhaustive,
        "family_outcome_reason": manifest.get("family_outcome_reason", ""),
        "created_utc": manifest.get("created_utc", ""),
        "trial_count": manifest.get("portability_trial_count", manifest.get("variant_count_reviewed", 1)),
        "primary_benchmark_control": "see_latest_evidence",
        "evaluation_period": f"{manifest.get('effective_start_date', manifest.get('effective_start_date_after_alignment_and_warmup', ''))} to {manifest.get('effective_end_date', '')}".strip(),
        "evidence_path": rel(path),
        "missing_artifacts": missing,
    }


def infer_full_period_control_pass(manifest: dict[str, Any], path: Path) -> str:
    if "primary_numeric_criteria_pass" in manifest:
        return csv_value(manifest["primary_numeric_criteria_pass"])
    if "primary_row_numeric_criteria_pass" in manifest:
        return csv_value(manifest["primary_row_numeric_criteria_pass"])
    if "primary_base_pass" in manifest:
        return csv_value(manifest["primary_base_pass"])
    criteria_rows = read_csv_rows(path / "criteria_recomputation_report.csv")
    for row in criteria_rows:
        if row.get("variant_role") == "source_primary" and "numeric_criteria_pass_recomputed" in row:
            return csv_value(parse_bool(row.get("numeric_criteria_pass_recomputed")))
    baseline_rows = read_csv_rows(path / "baseline_vs_controls.csv")
    if not baseline_rows:
        return "unknown"
    row = baseline_rows[0]
    preferred_keys = [
        key
        for key in row
        if key.lower() in {"after_cost_beats_primary_control", "five_bps_beats_equal_weight"}
        or key.lower().startswith("source_10bps_beats_equal")
        or key.lower().startswith("project_5bps_beats_equal")
    ]
    if preferred_keys:
        return csv_value(all(parse_bool(row.get(key)) for key in preferred_keys))
    candidate_keys = [
        key
        for key in row
        if ("beats_equal_weight" in key.lower() or "beats_global_equity" in key.lower())
        and not key.lower().startswith("zero_cost")
    ]
    if candidate_keys:
        return csv_value(all(parse_bool(row.get(key)) for key in candidate_keys))
    return "unknown"


def infer_static_control_pass(manifest: dict[str, Any], path: Path) -> str:
    if "spy200d_control_dominates_primary" in manifest:
        return csv_value(not parse_bool(manifest.get("spy200d_control_dominates_primary")))
    if "control_weakness_detected" in manifest:
        return csv_value(not parse_bool(manifest.get("control_weakness_detected")))
    baseline_rows = read_csv_rows(path / "baseline_vs_controls.csv")
    if not baseline_rows:
        return "unknown"
    row = baseline_rows[0]
    preferred_keys = [
        key
        for key in row
        if key.lower() == "after_cost_beats_static_control"
        or key.lower().startswith("five_bps_beats_static_control")
        or key.lower().startswith("source_10bps_beats_static_control")
        or key.lower().startswith("project_5bps_beats_static_control")
    ]
    if preferred_keys:
        return csv_value(any(parse_bool(row.get(key)) for key in preferred_keys))
    keys = [key for key in row if "beats_static_control" in key.lower() and not key.lower().startswith("zero_cost")]
    if keys:
        return csv_value(any(parse_bool(row.get(key)) for key in keys))
    return "unknown"


def infer_timeframe_nonnegative(path: Path) -> str:
    rows = read_csv_rows(path / "timeframe_diagnostics.csv")
    if not rows:
        return "not_available"
    row = rows[0]
    keys = [key for key in row if "excess" in key.lower() and ("first" in key.lower() or "second" in key.lower())]
    if not keys:
        return "not_available"
    values = [parse_float(row.get(key)) for key in keys]
    if any(value is None for value in values):
        return "not_available"
    return csv_value(all(value >= 0 for value in values if value is not None))


def build_family_inventory(exact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exact_rows:
        grouped[str(row.get("family_id", "unknown") or "unknown")].append(row)
    family_rows: list[dict[str, Any]] = []
    for family_id, rows in grouped.items():
        stages = [str(row.get("current_highest_verified_stage", "")) for row in rows]
        highest = max(stages, key=lambda stage: STAGE_RANK.get(stage, 0)) if stages else "blocked_or_deferred"
        family_rows.append(
            {
                "family_id": family_id,
                "exact_configuration_count": len(rows),
                "implemented_configuration_count": sum(1 for row in rows if parse_bool(row.get("implemented_evidence"))),
                "exact_trial_count": sum(parse_int(row.get("trial_count")) for row in rows),
                "highest_verified_family_stage": highest,
                "paper_demo_eligible_exact_count": sum(parse_bool(row.get("paper_demo_eligible")) for row in rows),
                "paper_demo_active_exact_count": sum(parse_bool(row.get("paper_demo_active")) for row in rows),
                "benchmark_reference_exact_count": sum(parse_bool(row.get("benchmark_reference_only")) for row in rows),
                "closed_no_advancement_exact_count": sum(
                    1 for row in rows if row.get("current_highest_verified_stage") == "closed_no_advancement"
                ),
                "blocked_or_deferred_exact_count": sum(
                    1 for row in rows if row.get("current_highest_verified_stage") == "blocked_or_deferred"
                ),
                "unresolved_conflict_exact_count": sum(
                    1 for row in rows if row.get("current_highest_verified_stage") == "status_reconciliation_required"
                ),
                "representative_strategy_ids": "|".join(sorted(str(row.get("strategy_id", "")) for row in rows)[:12]),
            }
        )
    return sorted(family_rows, key=lambda row: str(row["family_id"]))


def build_status_reconciliation(
    active_config: dict[str, Any],
    current_best_rows: list[dict[str, str]],
    candidate_pipeline_rows: list[dict[str, str]],
    sel_funnel_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active_ids = sorted(
        row.get("strategy_id", "")
        for row in active_config.get("active_observations", [])
        if parse_bool(row.get("paper_forward_active"))
    )
    checkpoint_active_stage = next(
        (row for row in candidate_pipeline_rows if row.get("stage") == "paper_forward_active"), {}
    )
    checkpoint_active_ids = sorted(
        item for item in str(checkpoint_active_stage.get("rows", "")).split(";") if item
    )
    if active_ids != checkpoint_active_ids:
        rows.append(
            {
                "conflict_id": "active_observation_count_active_yaml_vs_checkpoint_pipeline",
                "strategy_id": "|".join(sorted(set(active_ids + checkpoint_active_ids))),
                "higher_precedence_source": "strategy_lab/research_os/operations/active_observations.yaml",
                "higher_precedence_value": f"{len(active_ids)} active: {'|'.join(active_ids)}",
                "lower_precedence_source": "evidence/current_research_checkpoint/latest/candidate_pipeline_status.csv",
                "lower_precedence_value": f"{len(checkpoint_active_ids)} active: {'|'.join(checkpoint_active_ids)}",
                "resolution_applied": "active_observations_yaml_used_for_current_active_count",
                "requires_direction_owner_audit": True,
            }
        )

    sel_counts = {row.get("evidence_level", row.get("metric", "")): row for row in sel_funnel_rows}
    e7_count = parse_int(sel_counts.get("E7", {}).get("count"))
    if e7_count != len(active_ids):
        rows.append(
            {
                "conflict_id": "strategy_evidence_library_e7_zero_vs_active_observations",
                "strategy_id": "|".join(active_ids),
                "higher_precedence_source": "strategy_lab/research_os/operations/active_observations.yaml",
                "higher_precedence_value": str(len(active_ids)),
                "lower_precedence_source": "evidence/strategy_evidence_library/latest/evidence_level_funnel.csv",
                "lower_precedence_value": str(e7_count),
                "resolution_applied": "active_state_count_reported_separately_from_sel_evidence_level_chain",
                "requires_direction_owner_audit": True,
            }
        )

    sel_inventory_rows = read_csv_rows(ROOT / "evidence" / "strategy_evidence_library" / "latest" / "strategy_inventory.csv")
    stale_active_ids = sorted(
        row.get("variant_id", "")
        for row in sel_inventory_rows
        if "active_paper_demo_observation" in row.get("status_detail", "").lower()
        and row.get("variant_id", "") not in active_ids
    )
    if stale_active_ids:
        rows.append(
            {
                "conflict_id": "strategy_evidence_library_active_rows_absent_from_current_active_config",
                "strategy_id": "|".join(stale_active_ids),
                "higher_precedence_source": "strategy_lab/research_os/operations/active_observations.yaml",
                "higher_precedence_value": f"current active ids: {'|'.join(active_ids)}",
                "lower_precedence_source": "evidence/strategy_evidence_library/latest/strategy_inventory.csv",
                "lower_precedence_value": f"stale active status ids: {'|'.join(stale_active_ids)}",
                "resolution_applied": "stale SEL active rows not counted as current active observations",
                "requires_direction_owner_audit": True,
            }
        )

    for row in current_best_rows:
        strategy_id = row.get("strategy_id", "")
        if strategy_id == "SPY_200d_trend_model" and row.get("status") == "active_observation":
            rows.append(
                {
                    "conflict_id": "spy200d_status_active_observation_but_role_frozen_control",
                    "strategy_id": strategy_id,
                    "higher_precedence_source": "evidence/current_research_checkpoint/latest/current_best_strategy_set.csv role",
                    "higher_precedence_value": row.get("role", ""),
                    "lower_precedence_source": "evidence/current_research_checkpoint/latest/current_best_strategy_set.csv status",
                    "lower_precedence_value": row.get("status", ""),
                    "resolution_applied": "classified_as_benchmark_or_reference_only",
                    "requires_direction_owner_audit": True,
                }
            )

    promotion_row = next((row for row in candidate_pipeline_rows if row.get("stage") == "promotion_review_candidates"), {})
    if parse_int(promotion_row.get("count")) == 0:
        rows.append(
            {
                "conflict_id": "stale_registry_promotion_like_metadata_not_current_candidate",
                "strategy_id": "A_ETF_sector_momentum|new_batch_approved_cache",
                "higher_precedence_source": "evidence/current_research_checkpoint/latest/candidate_pipeline_status.csv",
                "higher_precedence_value": "0 current promotion_review_candidates",
                "lower_precedence_source": "evidence/strategy_evidence_library/latest/strategy_inventory.csv",
                "lower_precedence_value": "promotion_review_passed/create_promotion_review metadata exists in older records",
                "resolution_applied": "not_counted_as_current_demo_ready_or_current_promotion_candidate",
                "requires_direction_owner_audit": True,
            }
        )
    return sorted(rows, key=lambda row: str(row["conflict_id"]))


def build_missing_or_conflicting_evidence(
    active_config: dict[str, Any],
    status_rows: list[dict[str, Any]],
    recent_fast_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for conflict in status_rows:
        rows.append(
            {
                "item_id": conflict["conflict_id"],
                "strategy_id": conflict["strategy_id"],
                "issue_type": "status_conflict",
                "severity": "audit_required",
                "evidence_path": conflict["higher_precedence_source"],
                "description": f"{conflict['higher_precedence_value']} conflicts with {conflict['lower_precedence_value']}",
                "resolution_or_next_needed": "direction_owner_audit_tournament_strategy_readiness_report_v1",
            }
        )
    for active_row in active_config.get("active_observations", []):
        strategy_id = active_row.get("strategy_id", "")
        if strategy_id:
            rows.append(
                {
                    "item_id": f"{strategy_id}_paper_account_operational_fields",
                    "strategy_id": strategy_id,
                    "issue_type": "missing_operational_account_results",
                    "severity": "informational",
                    "evidence_path": "strategy_lab/research_os/operations/active_observations.yaml",
                    "description": "Current active configuration is present, but broker/account order and fill fields are not populated in this report-only source set.",
                    "resolution_or_next_needed": "Continue manual or delegated observation logging; do not estimate missing account fields.",
                }
            )
    for lane in recent_fast_rows:
        if lane.get("missing_artifacts"):
            rows.append(
                {
                    "item_id": f"{lane['strategy_id']}_recent_fast_lane_missing_artifacts",
                    "strategy_id": lane["strategy_id"],
                    "issue_type": "missing_evidence_artifact",
                    "severity": "audit_required",
                    "evidence_path": lane.get("evidence_path", ""),
                    "description": lane.get("missing_artifacts", ""),
                    "resolution_or_next_needed": "Inspect source lane evidence before relying on the row.",
                }
            )
    return sorted(rows, key=lambda row: str(row["item_id"]))


def build_passed_strategy_results(
    exact_rows: list[dict[str, Any]], current_best_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    current_best_by_id = {row.get("strategy_id", ""): row for row in current_best_rows}
    rows: list[dict[str, Any]] = []
    for exact in exact_rows:
        if exact.get("current_highest_verified_stage") not in ADVANCED_RESULT_STAGES:
            continue
        strategy_id = str(exact["strategy_id"])
        metrics = current_best_by_id.get(strategy_id, {})
        rows.append(
            {
                "strategy_id": strategy_id,
                "family_id": exact.get("family_id", ""),
                "stage": exact.get("current_highest_verified_stage", ""),
                "evaluation_start": "",
                "evaluation_end": "",
                "initial_capital": "",
                "final_value": metrics.get("180d_median_equity", ""),
                "total_return": "",
                "cagr": "",
                "annualized_volatility": "",
                "sharpe_ratio": "",
                "maximum_drawdown": metrics.get("worst_drawdown", ""),
                "turnover": "",
                "transaction_cost_assumption": "",
                "average_gross_exposure": "",
                "trade_or_rebalance_count": "",
                "primary_control_return": "",
                "primary_control_cagr": "",
                "primary_control_maximum_drawdown": "",
                "static_exposure_control_results": "",
                "relative_result_vs_primary_control": metrics.get("target_300_rate", ""),
                "relative_result_vs_static_control": metrics.get("target_400_rate", ""),
                "first_period_diagnostics": "",
                "second_period_diagnostics": "",
                "promotion_or_eligibility_decision": exact.get("latest_evidence_outcome", ""),
                "main_risks_or_caveats": exact.get("reason_for_advancement_closure_or_deferral", ""),
                "current_next_review_or_observation_requirement": exact.get("latest_direction_decision", ""),
                "supporting_evidence_path": exact.get("latest_evidence_path", ""),
            }
        )
    return sorted(rows, key=lambda row: str(row["strategy_id"]))


def build_paper_demo_eligible(exact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in exact_rows:
        if not parse_bool(row.get("paper_demo_eligible")):
            continue
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "family_id": row.get("family_id", ""),
                "stage": row.get("current_highest_verified_stage", ""),
                "active": row.get("paper_demo_active", False),
                "explicit_eligibility_artifact": row.get("latest_evidence_path", ""),
                "eligibility_source_type": "active_configuration_or_paper_forward_eligibility_packet",
                "paper_demo_only": True,
                "real_money_authorized": False,
                "next_action": "observe_only",
            }
        )
    return sorted(rows, key=lambda row: str(row["strategy_id"]))


def build_active_observation_rows(
    active_config: dict[str, Any], current_best_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    current_best_by_id = {row.get("strategy_id", ""): row for row in current_best_rows}
    rows: list[dict[str, Any]] = []
    for active_row in active_config.get("active_observations", []):
        strategy_id = active_row.get("strategy_id", "")
        if not strategy_id or not parse_bool(active_row.get("paper_forward_active")):
            continue
        meta = ACTIVE_OBSERVATION_EVIDENCE.get(strategy_id, {})
        metrics = current_best_by_id.get(strategy_id, {})
        rows.append(
            {
                "strategy_id": strategy_id,
                "base_strategy_id": meta.get("base_strategy_id", ""),
                "family_id": meta.get("family_id", ""),
                "activation_date": latest_evidence_date_for_active(meta),
                "observation_status": active_row.get("state", ""),
                "broker_account_mode": "simulated_paper_demo_only_no_broker_orders",
                "instruments": meta.get("primary_instrument_universe", ""),
                "target_allocation_logic": meta.get("strategy_architecture", ""),
                "current_observation_period": "current_active_configuration",
                "starting_paper_equity": "",
                "current_paper_equity": metrics.get("180d_median_equity", ""),
                "realized_pnl": "",
                "unrealized_pnl": "",
                "submitted_orders": "missing_no_broker_order_log",
                "filled_orders": "missing_no_broker_order_log",
                "rejected_orders": "missing_no_broker_order_log",
                "cancelled_orders": "missing_no_broker_order_log",
                "open_orders": "missing_no_broker_order_log",
                "current_positions": "missing_or_not_applicable_in_report_sources",
                "expected_vs_actual_allocations": "missing_or_not_applicable_in_report_sources",
                "broker_api_errors": "none_recorded_in_current_active_configuration",
                "missing_fills_or_reconciliation_issues": "not_estimated",
                "logging_completeness": "active_configuration_present_operational_account_fields_missing",
                "latest_weekly_or_periodic_report_path": "evidence/current_paper_forward_update_and_reconciliation_v1/latest",
                "current_blockers": "",
                "observation_remains_valid": True,
                "supporting_evidence_path": meta.get("evidence_path", "strategy_lab/research_os/operations/active_observations.yaml"),
            }
        )
    return sorted(rows, key=lambda row: str(row["strategy_id"]))


def build_operational_status_rows(active_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot_rows = {
        row.get("observation_id", ""): row
        for row in read_csv_rows(
            ROOT
            / "evidence"
            / "current_paper_forward_update_and_reconciliation_v1"
            / "latest"
            / "observation_monitoring_snapshot.csv"
        )
    }
    rows: list[dict[str, Any]] = []
    for row in active_rows:
        strategy_id = row["strategy_id"]
        snapshot = snapshot_rows.get(strategy_id, {})
        rows.append(
            {
                "strategy_id": strategy_id,
                "operational_status_source": "current_paper_forward_update_and_reconciliation_v1" if snapshot else "active_observations_yaml_only",
                "as_of_date": snapshot.get("as_of_date", ""),
                "current_virtual_equity": snapshot.get("derived_total_virtual_equity", row.get("current_paper_equity", "")),
                "submitted_orders": row.get("submitted_orders", ""),
                "filled_orders": row.get("filled_orders", ""),
                "rejected_orders": row.get("rejected_orders", ""),
                "cancelled_orders": row.get("cancelled_orders", ""),
                "open_orders": row.get("open_orders", ""),
                "current_positions": row.get("current_positions", ""),
                "allocation_status": snapshot.get("missing_component_status", row.get("expected_vs_actual_allocations", "")),
                "broker_api_errors": row.get("broker_api_errors", ""),
                "reconciliation_status": snapshot.get("stale_date_status", row.get("missing_fills_or_reconciliation_issues", "")),
                "logging_completeness": row.get("logging_completeness", ""),
                "current_blockers": snapshot.get("missing_component_status", row.get("current_blockers", "")),
                "observation_remains_valid": row.get("observation_remains_valid", ""),
                "supporting_evidence_path": row.get("supporting_evidence_path", ""),
            }
        )
    return sorted(rows, key=lambda row: str(row["strategy_id"]))


def build_benchmark_inventory(
    active_config: dict[str, Any], exact_rows: list[dict[str, Any]], current_best_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for control in active_config.get("benchmark_controls", []):
        rows.append(
            {
                "strategy_id": control.get("strategy_id", ""),
                "family_id": "benchmark_control",
                "role": control.get("state", "benchmark_control_only"),
                "current_status": "benchmark_or_reference_only",
                "source_path": "strategy_lab/research_os/operations/active_observations.yaml",
                "counted_as_approved_strategy": False,
            }
        )
    for ref in active_config.get("references", []):
        rows.append(
            {
                "strategy_id": str(ref),
                "family_id": "reference_symbol_or_alias",
                "role": "reference",
                "current_status": "benchmark_or_reference_only",
                "source_path": "strategy_lab/research_os/operations/active_observations.yaml",
                "counted_as_approved_strategy": False,
            }
        )
    for row in current_best_rows:
        strategy_id = row.get("strategy_id", "")
        role = row.get("role", "")
        if any(token in f"{strategy_id} {role}".lower() for token in ["benchmark", "control", "cash", "combo", "watchlist"]):
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "family_id": next((r.get("family_id", "") for r in exact_rows if r.get("strategy_id") == strategy_id), ""),
                    "role": role,
                    "current_status": "benchmark_or_reference_only",
                    "source_path": "evidence/current_research_checkpoint/latest/current_best_strategy_set.csv",
                    "counted_as_approved_strategy": False,
                }
            )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        unique[(str(row.get("strategy_id", "")), str(row.get("source_path", "")))] = row
    return sorted(unique.values(), key=lambda row: (str(row["strategy_id"]), str(row["source_path"])))


def build_closed_and_deferred_inventory(exact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in exact_rows:
        if row.get("current_highest_verified_stage") not in {"closed_no_advancement", "blocked_or_deferred"}:
            continue
        rows.append(
            {
                "strategy_id": row.get("strategy_id", ""),
                "family_id": row.get("family_id", ""),
                "stage": row.get("current_highest_verified_stage", ""),
                "latest_outcome": row.get("latest_evidence_outcome", ""),
                "reason": row.get("reason_for_advancement_closure_or_deferral", ""),
                "retest_conditions_or_next_action": row.get("latest_direction_decision", ""),
                "supporting_evidence_path": row.get("latest_evidence_path", ""),
            }
        )
    return sorted(rows, key=lambda row: (str(row["stage"]), str(row["family_id"]), str(row["strategy_id"])))


def build_funnel_counts(exact_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def stage_count(rows: list[dict[str, Any]], stage: str) -> int:
        return sum(1 for row in rows if row.get("current_highest_verified_stage") == stage)

    exact_implemented = sum(1 for row in exact_rows if parse_bool(row.get("implemented_evidence")))
    exact_trials = sum(parse_int(row.get("trial_count")) for row in exact_rows)
    exact_exploration_completed = sum(
        1
        for row in exact_rows
        if row.get("current_highest_verified_stage")
        in {
            "exploration_completed_not_advanced",
            "exploratory_followup_candidate",
            "validation_or_promotion_review_candidate",
            "paper_demo_eligible_not_active",
            "paper_demo_active_observation",
            "closed_no_advancement",
        }
        and not parse_bool(row.get("benchmark_reference_only"))
    )
    exact_counts = {
        "distinct_strategy_families_discovered": len({row.get("family_id") for row in exact_rows if row.get("family_id")}),
        "exact_configurations_implemented": exact_implemented,
        "exact_trials_registered": exact_trials,
        "exploration_runs_completed": exact_exploration_completed,
        "exploratory_followup_candidates": stage_count(exact_rows, "exploratory_followup_candidate"),
        "validation_or_promotion_review_candidates": stage_count(exact_rows, "validation_or_promotion_review_candidate"),
        "paper_demo_eligible_strategies": sum(parse_bool(row.get("paper_demo_eligible")) for row in exact_rows),
        "paper_demo_active_observations": sum(parse_bool(row.get("paper_demo_active")) for row in exact_rows),
        "benchmark_reference_only_strategies": stage_count(exact_rows, "benchmark_or_reference_only"),
        "closed_no_advancement_configurations": stage_count(exact_rows, "closed_no_advancement"),
        "blocked_deferred_configurations": stage_count(exact_rows, "blocked_or_deferred"),
        "strategies_with_unresolved_status_conflicts": stage_count(exact_rows, "status_reconciliation_required"),
    }
    family_counts = {
        "distinct_strategy_families_discovered": len(family_rows),
        "families_with_implemented_configurations": sum(parse_int(row.get("implemented_configuration_count")) > 0 for row in family_rows),
        "family_trials_registered": sum(parse_int(row.get("exact_trial_count")) for row in family_rows),
        "families_with_exploration_runs_completed": sum(
            row.get("highest_verified_family_stage")
            in {
                "exploration_completed_not_advanced",
                "exploratory_followup_candidate",
                "validation_or_promotion_review_candidate",
                "paper_demo_eligible_not_active",
                "paper_demo_active_observation",
                "closed_no_advancement",
            }
            for row in family_rows
        ),
        "families_with_exploratory_followup_candidates": sum(
            row.get("highest_verified_family_stage") == "exploratory_followup_candidate" for row in family_rows
        ),
        "families_with_validation_or_promotion_review_candidates": sum(
            row.get("highest_verified_family_stage") == "validation_or_promotion_review_candidate"
            for row in family_rows
        ),
        "families_with_paper_demo_eligible_strategies": sum(
            parse_int(row.get("paper_demo_eligible_exact_count")) > 0 for row in family_rows
        ),
        "families_with_paper_demo_active_observations": sum(
            parse_int(row.get("paper_demo_active_exact_count")) > 0 for row in family_rows
        ),
        "families_with_benchmark_reference_only_strategies": sum(
            parse_int(row.get("benchmark_reference_exact_count")) > 0 for row in family_rows
        ),
        "families_with_closed_no_advancement_configurations": sum(
            parse_int(row.get("closed_no_advancement_exact_count")) > 0 for row in family_rows
        ),
        "families_with_blocked_deferred_configurations": sum(
            parse_int(row.get("blocked_or_deferred_exact_count")) > 0 for row in family_rows
        ),
        "families_with_unresolved_status_conflicts": sum(
            parse_int(row.get("unresolved_conflict_exact_count")) > 0 for row in family_rows
        ),
    }
    return {
        "task_id": TASK_ID,
        "exact_configuration_counts": exact_counts,
        "family_level_counts": family_counts,
    }


def conversion_rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "denominator_zero"
    return f"{numerator / denominator:.12g}"


def build_conversion_rates(funnel: dict[str, Any]) -> list[dict[str, Any]]:
    exact = funnel["exact_configuration_counts"]
    family = funnel["family_level_counts"]
    rows = [
        {
            "count_basis": "exact_configuration",
            "conversion": "implemented_to_exploratory_followup",
            "numerator": exact["exploratory_followup_candidates"],
            "denominator": exact["exact_configurations_implemented"],
            "rate": conversion_rate(exact["exploratory_followup_candidates"], exact["exact_configurations_implemented"]),
        },
        {
            "count_basis": "exact_configuration",
            "conversion": "exploratory_followup_to_validation_or_promotion_review",
            "numerator": exact["validation_or_promotion_review_candidates"],
            "denominator": exact["exploratory_followup_candidates"],
            "rate": conversion_rate(
                exact["validation_or_promotion_review_candidates"], exact["exploratory_followup_candidates"]
            ),
        },
        {
            "count_basis": "exact_configuration",
            "conversion": "validation_or_promotion_review_to_paper_demo_eligible",
            "numerator": exact["paper_demo_eligible_strategies"],
            "denominator": exact["validation_or_promotion_review_candidates"],
            "rate": conversion_rate(exact["paper_demo_eligible_strategies"], exact["validation_or_promotion_review_candidates"]),
        },
        {
            "count_basis": "exact_configuration",
            "conversion": "paper_demo_eligible_to_active_observation",
            "numerator": exact["paper_demo_active_observations"],
            "denominator": exact["paper_demo_eligible_strategies"],
            "rate": conversion_rate(exact["paper_demo_active_observations"], exact["paper_demo_eligible_strategies"]),
        },
        {
            "count_basis": "exact_configuration",
            "conversion": "implemented_to_paper_demo_eligible",
            "numerator": exact["paper_demo_eligible_strategies"],
            "denominator": exact["exact_configurations_implemented"],
            "rate": conversion_rate(exact["paper_demo_eligible_strategies"], exact["exact_configurations_implemented"]),
        },
        {
            "count_basis": "exact_configuration",
            "conversion": "implemented_to_active_observation",
            "numerator": exact["paper_demo_active_observations"],
            "denominator": exact["exact_configurations_implemented"],
            "rate": conversion_rate(exact["paper_demo_active_observations"], exact["exact_configurations_implemented"]),
        },
        {
            "count_basis": "family",
            "conversion": "implemented_to_exploratory_followup",
            "numerator": family["families_with_exploratory_followup_candidates"],
            "denominator": family["families_with_implemented_configurations"],
            "rate": conversion_rate(
                family["families_with_exploratory_followup_candidates"],
                family["families_with_implemented_configurations"],
            ),
        },
        {
            "count_basis": "family",
            "conversion": "exploratory_followup_to_validation_or_promotion_review",
            "numerator": family["families_with_validation_or_promotion_review_candidates"],
            "denominator": family["families_with_exploratory_followup_candidates"],
            "rate": conversion_rate(
                family["families_with_validation_or_promotion_review_candidates"],
                family["families_with_exploratory_followup_candidates"],
            ),
        },
        {
            "count_basis": "family",
            "conversion": "validation_or_promotion_review_to_paper_demo_eligible",
            "numerator": family["families_with_paper_demo_eligible_strategies"],
            "denominator": family["families_with_validation_or_promotion_review_candidates"],
            "rate": conversion_rate(
                family["families_with_paper_demo_eligible_strategies"],
                family["families_with_validation_or_promotion_review_candidates"],
            ),
        },
        {
            "count_basis": "family",
            "conversion": "paper_demo_eligible_to_active_observation",
            "numerator": family["families_with_paper_demo_active_observations"],
            "denominator": family["families_with_paper_demo_eligible_strategies"],
            "rate": conversion_rate(
                family["families_with_paper_demo_active_observations"],
                family["families_with_paper_demo_eligible_strategies"],
            ),
        },
        {
            "count_basis": "family",
            "conversion": "implemented_to_paper_demo_eligible",
            "numerator": family["families_with_paper_demo_eligible_strategies"],
            "denominator": family["families_with_implemented_configurations"],
            "rate": conversion_rate(
                family["families_with_paper_demo_eligible_strategies"],
                family["families_with_implemented_configurations"],
            ),
        },
        {
            "count_basis": "family",
            "conversion": "implemented_to_active_observation",
            "numerator": family["families_with_paper_demo_active_observations"],
            "denominator": family["families_with_implemented_configurations"],
            "rate": conversion_rate(
                family["families_with_paper_demo_active_observations"],
                family["families_with_implemented_configurations"],
            ),
        },
    ]
    return rows


def build_evidence_path_index(source_rows: list[dict[str, Any]], output_files: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        path = abs_path(str(source["path"]))
        rows.append(
            {
                "path": source["path"],
                "path_type": "source",
                "exists": path.exists(),
                "sha256": source_digest(path),
                "notes": source.get("role", ""),
            }
        )
    for name in output_files:
        path = EVIDENCE_DIR / name
        rows.append(
            {
                "path": rel(path),
                "path_type": "generated_report_artifact",
                "exists": path.exists(),
                "sha256": sha256_path(path),
                "notes": "generated_by_report_only_inventory",
            }
        )
    return sorted(rows, key=lambda row: (str(row["path_type"]), str(row["path"])))


def build_report_markdown(
    funnel: dict[str, Any],
    active_rows: list[dict[str, Any]],
    eligible_rows: list[dict[str, Any]],
    exact_rows: list[dict[str, Any]],
    recent_rows: list[dict[str, Any]],
    status_rows: list[dict[str, Any]],
    conversion_rows: list[dict[str, Any]],
) -> str:
    exact = funnel["exact_configuration_counts"]
    family = funnel["family_level_counts"]
    active_sections = "\n".join(
        f"### {row['strategy_id']}\n"
        f"- Family: {row.get('family_id', '')}\n"
        f"- Status: {row.get('observation_status', '')}\n"
        f"- Evidence: `{row.get('supporting_evidence_path', '')}`\n"
        f"- Operational status: {row.get('logging_completeness', '')}\n"
        f"- Account/order fields: {row.get('submitted_orders', '')}\n"
        for row in active_rows
    )
    demo_sections = "\n".join(
        f"### {row['strategy_id']}\n"
        f"- Stage: {row.get('stage', '')}\n"
        f"- Active: {row.get('active', '')}\n"
        f"- Eligibility artifact: `{row.get('explicit_eligibility_artifact', '')}`\n"
        for row in eligible_rows
    )
    not_ready_rows = [
        row
        for row in exact_rows
        if row.get("current_highest_verified_stage")
        in {"exploration_completed_not_advanced", "exploratory_followup_candidate", "validation_or_promotion_review_candidate"}
    ][:40]
    not_ready_lines = "\n".join(
        f"- `{row['strategy_id']}`: {row.get('current_highest_verified_stage')} ({row.get('latest_evidence_outcome', '')})"
        for row in not_ready_rows
    )
    fast_lines = "\n".join(
        f"- {row['display_name']}: outcome `{row.get('exact_family_outcome', '')}`, "
        f"full-period controls `{row.get('passed_full_period_controls', '')}`, "
        f"static controls `{row.get('passed_static_controls', '')}`, "
        f"timeframe diagnostics `{row.get('both_existing_timeframe_diagnostics_nonnegative', '')}`, "
        f"advancement `{row.get('advancement_decision', '')}`, evidence `{row.get('evidence_path', '')}`"
        for row in recent_rows
    )
    conversion_lines = "\n".join(
        f"- {row['count_basis']} {row['conversion']}: {row['numerator']}/{row['denominator']} = {row['rate']}"
        for row in conversion_rows
    )
    conflict_lines = "\n".join(
        f"- `{row['conflict_id']}`: {row['higher_precedence_value']} vs {row['lower_precedence_value']}"
        for row in status_rows
    )
    if not conflict_lines:
        conflict_lines = "- No unresolved source disagreement was detected by this report."

    return f"""# Tournament Strategy Readiness Report

## 1. Executive count

- Passed exploration: {exact['exploration_runs_completed']} exact configurations; {family['families_with_exploration_runs_completed']} families
- Validation/promotion candidates: {exact['validation_or_promotion_review_candidates']} exact configurations; {family['families_with_validation_or_promotion_review_candidates']} families
- Paper/demo eligible: {exact['paper_demo_eligible_strategies']} exact configurations; {family['families_with_paper_demo_eligible_strategies']} families
- Active paper/demo observations: {exact['paper_demo_active_observations']} exact configurations; {family['families_with_paper_demo_active_observations']} families
- Benchmark/reference only: {exact['benchmark_reference_only_strategies']} exact configurations; {family['families_with_benchmark_reference_only_strategies']} families
- Closed or deferred: {exact['closed_no_advancement_configurations'] + exact['blocked_deferred_configurations']} exact configurations; {family['families_with_closed_no_advancement_configurations'] + family['families_with_blocked_deferred_configurations']} families with at least one closed/deferred row
- Unresolved: {exact['strategies_with_unresolved_status_conflicts']} exact configurations plus {len(status_rows)} source-level conflicts

## 2. Demo-ready strategies

{demo_sections or 'No paper/demo eligible strategies were found beyond active observations.'}

## 3. Active paper/demo observations

{active_sections or 'No active paper/demo observations were found in current active configuration.'}

## 4. Strategies that passed exploration but are not demo-ready

The rows below are not counted as demo-ready because the report found no current explicit paper/demo eligibility artifact for them.

{not_ready_lines or '- None found.'}

## 5. Recent fast-lane results

{fast_lines}

## 6. Tournament funnel

Exact-configuration counts and family-level counts are kept separate in `tournament_funnel_counts.json`.

{conversion_lines}

## 7. Evidence conflicts and missing information

{conflict_lines}

## 8. Audit-ready factual observations

- The active-observation source-of-truth currently lists {exact['paper_demo_active_observations']} active paper/demo observations.
- Benchmark/reference rows are excluded from approved strategy counts.
- Exploratory follow-up and promotion-review-like rows are not counted as demo-ready without explicit paper/demo eligibility.
- Current account/order fields are missing for active observations in the inspected report-only sources and were not estimated.
- No strategy discovery, backtest, validation run, promotion review, paper/demo activation, broker order, registry cleanup or real-money recommendation was performed by this report generator.
- Exact next action: `{NEXT_ACTION}`.
"""


def write_report_scope() -> None:
    payload = {
        "task_id": TASK_ID,
        "mode": "report",
        "stage": "verification",
        "purpose": "audit-ready tournament status extraction",
        "research_status": "read-only reporting",
        "highest_verified_stages": STAGES,
        "demo_ready_rule": {
            "count_demo_ready_only_when": [
                "current evidence explicitly grants paper/demo eligibility",
                "current active configuration marks active paper/demo observation",
            ],
            "not_demo_ready_by_itself": [
                "positive total return",
                "high CAGR or Sharpe",
                "lower drawdown",
                "exploratory_followup_candidate",
                "promotion_review_candidate",
                "Codex recommendation",
                "old roadmap entry",
                "stale registry field",
                "broker-compatible instruments",
                "execution adapter availability",
            ],
        },
        "current_state_precedence": [
            "explicit_latest_direction_owner_decision_recorded_in_repository_evidence",
            "current_active_paper_demo_configuration",
            "latest_completed_review_or_eligibility_packet",
            "current_strategy_registry",
            "research_roadmap",
            "older_reports_and_historical_evidence",
        ],
        "prohibited_actions": [
            "strategy_discovery",
            "backtest",
            "validation_run",
            "promotion_review",
            "paper_demo_activation",
            "broker_order_placement",
            "registry_cleanup",
            "evidence_regeneration",
            "real_money_advice",
        ],
        "exact_next_action": NEXT_ACTION,
    }
    write_yaml(EVIDENCE_DIR / "report_scope_and_definitions.yaml", payload)


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    clean_output_dir()

    active_config = read_yaml(ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml")
    current_best_rows = read_csv_rows(ROOT / "evidence" / "current_research_checkpoint" / "latest" / "current_best_strategy_set.csv")
    candidate_pipeline_rows = read_csv_rows(
        ROOT / "evidence" / "current_research_checkpoint" / "latest" / "candidate_pipeline_status.csv"
    )
    sel_funnel_rows = read_csv_rows(ROOT / "evidence" / "strategy_evidence_library" / "latest" / "evidence_level_funnel.csv")
    recent_fast_rows = [parse_recent_fast_lane(lane) for lane in RECENT_FAST_LANES]

    source_rows = build_source_inventory()
    exact_rows = build_exact_inventory(active_config, current_best_rows, recent_fast_rows)
    family_rows = build_family_inventory(exact_rows)
    status_rows = build_status_reconciliation(active_config, current_best_rows, candidate_pipeline_rows, sel_funnel_rows)
    missing_rows = build_missing_or_conflicting_evidence(active_config, status_rows, recent_fast_rows)
    passed_rows = build_passed_strategy_results(exact_rows, current_best_rows)
    eligible_rows = build_paper_demo_eligible(exact_rows)
    active_rows = build_active_observation_rows(active_config, current_best_rows)
    operational_rows = build_operational_status_rows(active_rows)
    benchmark_rows = build_benchmark_inventory(active_config, exact_rows, current_best_rows)
    closed_rows = build_closed_and_deferred_inventory(exact_rows)
    funnel = build_funnel_counts(exact_rows, family_rows)
    conversion_rows = build_conversion_rates(funnel)

    task_outcome = TASK_OUTCOME_WITH_CONFLICTS if status_rows or missing_rows else TASK_OUTCOME_COMPLETE

    write_report_scope()
    write_csv(EVIDENCE_DIR / "source_inventory.csv", source_rows)
    write_csv(EVIDENCE_DIR / "exact_strategy_inventory.csv", exact_rows)
    write_csv(EVIDENCE_DIR / "family_inventory.csv", family_rows)
    write_csv(EVIDENCE_DIR / "status_reconciliation.csv", status_rows)
    write_csv(EVIDENCE_DIR / "passed_strategy_results.csv", passed_rows)
    write_csv(EVIDENCE_DIR / "paper_demo_eligible_strategies.csv", eligible_rows)
    write_csv(EVIDENCE_DIR / "active_paper_demo_observations.csv", active_rows)
    write_csv(EVIDENCE_DIR / "active_observation_operational_status.csv", operational_rows)
    write_csv(EVIDENCE_DIR / "benchmark_and_reference_inventory.csv", benchmark_rows)
    write_csv(EVIDENCE_DIR / "closed_and_deferred_inventory.csv", closed_rows)
    write_csv(EVIDENCE_DIR / "recent_fast_lane_results.csv", recent_fast_rows)
    write_json(EVIDENCE_DIR / "tournament_funnel_counts.json", funnel)
    write_csv(EVIDENCE_DIR / "tournament_conversion_rates.csv", conversion_rows)
    write_csv(EVIDENCE_DIR / "missing_or_conflicting_evidence.csv", missing_rows)
    write_text(
        EVIDENCE_DIR / "tournament_strategy_readiness_report.md",
        build_report_markdown(funnel, active_rows, eligible_rows, exact_rows, recent_fast_rows, status_rows, conversion_rows),
    )

    output_artifacts_for_index = [
        "report_scope_and_definitions.yaml",
        "source_inventory.csv",
        "exact_strategy_inventory.csv",
        "family_inventory.csv",
        "status_reconciliation.csv",
        "passed_strategy_results.csv",
        "paper_demo_eligible_strategies.csv",
        "active_paper_demo_observations.csv",
        "active_observation_operational_status.csv",
        "benchmark_and_reference_inventory.csv",
        "closed_and_deferred_inventory.csv",
        "recent_fast_lane_results.csv",
        "tournament_funnel_counts.json",
        "tournament_conversion_rates.csv",
        "missing_or_conflicting_evidence.csv",
        "tournament_strategy_readiness_report.md",
    ]
    evidence_path_rows = build_evidence_path_index(source_rows, output_artifacts_for_index)
    write_csv(EVIDENCE_DIR / "evidence_path_index.csv", evidence_path_rows)

    after_hashes = protected_hashes()
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "exact_next_action": NEXT_ACTION,
        "report_only": True,
        "strategy_discovery_run": False,
        "backtest_run": False,
        "validation_runner_called": False,
        "promotion_review_run": False,
        "paper_demo_activation": False,
        "broker_write_endpoint_called": False,
        "broker_orders_submitted": False,
        "registry_cleanup_run": False,
        "real_money_recommendation": False,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_unchanged": before_hashes == after_hashes,
        "known_active_expectations_verified_from_current_config": {
            "paper_forward_vm_quality_lowvol_proxy_v1": any(
                row.get("strategy_id") == "paper_forward_vm_quality_lowvol_proxy_v1"
                for row in active_config.get("active_observations", [])
            ),
            "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": any(
                row.get("strategy_id") == "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
                for row in active_config.get("active_observations", [])
            ),
            "active_combo_vm_dsr_equal_weight_v1_benchmark_reference_only": any(
                row.get("strategy_id") == "active_combo_vm_dsr_equal_weight_v1"
                and row.get("current_highest_verified_stage") == "benchmark_or_reference_only"
                for row in exact_rows
            ),
        },
        "exploratory_followup_candidates_counted_as_demo_ready": any(
            row.get("current_highest_verified_stage") == "exploratory_followup_candidate"
            and parse_bool(row.get("paper_demo_eligible"))
            for row in exact_rows
        ),
        "promotion_review_candidates_counted_as_demo_ready": any(
            row.get("current_highest_verified_stage") == "validation_or_promotion_review_candidate"
            and parse_bool(row.get("paper_demo_eligible"))
            for row in exact_rows
        ),
        "benchmark_references_counted_as_approved": any(
            row.get("current_highest_verified_stage") == "benchmark_or_reference_only"
            and parse_bool(row.get("paper_demo_eligible"))
            for row in exact_rows
        ),
        "active_observation_count": funnel["exact_configuration_counts"]["paper_demo_active_observations"],
        "paper_demo_eligible_count": funnel["exact_configuration_counts"]["paper_demo_eligible_strategies"],
        "benchmark_reference_only_count": funnel["exact_configuration_counts"]["benchmark_reference_only_strategies"],
        "status_conflict_count": len(status_rows),
        "missing_or_conflicting_evidence_count": len(missing_rows),
        "recent_fast_lane_count": len(recent_fast_rows),
        "all_required_recent_fast_lanes_present": len(recent_fast_rows) == len(RECENT_FAST_LANES)
        and all(not row.get("missing_artifacts") for row in recent_fast_rows),
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)

    # Add consistency and path index after consistency exists; keep index self-free for deterministic hashing.
    evidence_path_rows = build_evidence_path_index(
        source_rows, output_artifacts_for_index + ["evidence_path_index.csv", "consistency_check.json"]
    )
    write_csv(EVIDENCE_DIR / "evidence_path_index.csv", evidence_path_rows)

    return {
        "task_id": TASK_ID,
        "task_outcome": task_outcome,
        "evidence_path": rel(EVIDENCE_DIR),
        "exact_next_action": NEXT_ACTION,
        "funnel": funnel,
        "status_conflict_count": len(status_rows),
        "missing_or_conflicting_evidence_count": len(missing_rows),
        "protected_state_unchanged": before_hashes == after_hashes,
        "active_observation_count": funnel["exact_configuration_counts"]["paper_demo_active_observations"],
        "paper_demo_eligible_count": funnel["exact_configuration_counts"]["paper_demo_eligible_strategies"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
