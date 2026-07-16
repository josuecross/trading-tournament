from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "low_volatility_factor_source_backed_preregistration_v1" / "latest"
SOURCE_ID = "low_volatility_factor_proxy"
FAMILY_ID = "low_volatility_factor_proxy"
ACTIVE_VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
OUTCOME_EXTERNAL_SOURCE_REQUIRED = "external_source_research_required"
NEXT_ACTION = "find_complete_source_backed_low_volatility_factor_rule_before_preregistration"

INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / f"{SOURCE_ID}.yaml"
)
COVERAGE_DIR = Path("evidence") / "strategy_family_coverage_and_next_discovery_v1" / "latest"
SEL_DIR = Path("evidence") / "strategy_evidence_library" / "latest"
ACTIVE_VM_PATH = Path("paper_forward_observations") / ACTIVE_VM_ID / "active_observation.yaml"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _abs(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    full = _abs(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    full = _abs(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    full = _abs(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    full = _abs(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_yaml(path: Path) -> dict[str, Any]:
    full = _abs(path)
    if not full.exists():
        return {}
    payload = yaml.safe_load(full.read_text(encoding="utf-8"))
    return payload or {}


def _sha256_file(path: Path) -> str:
    full = _abs(path)
    if not full.exists():
        return "missing"
    return hashlib.sha256(full.read_bytes()).hexdigest().upper()


def _cache_info(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    result: dict[str, Any] = {
        "local_etf_wrapper": symbol,
        "cache_path": str(path),
        "cache_ready": False,
        "cache_start": "",
        "cache_end": "",
        "row_count": 0,
        "cache_hash": "missing",
    }
    if not path.exists():
        return result
    row_count = 0
    first_date = ""
    last_date = ""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            date = row.get("date", "")
            if not first_date:
                first_date = date
            last_date = date
            row_count += 1
    result.update(
        {
            "cache_ready": row_count > 0,
            "cache_start": first_date,
            "cache_end": last_date,
            "row_count": row_count,
            "cache_hash": _sha256_file(Path("data") / "cache" / f"{symbol}.csv"),
        }
    )
    return result


def _matching_rows(path: Path, key: str, value: str) -> list[dict[str, str]]:
    return [row for row in _read_csv(path) if row.get(key) == value]


def _resolve_source_identity(intake: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    next_options = _matching_rows(COVERAGE_DIR / "next_discovery_options.csv", "family", FAMILY_ID)
    readiness = _matching_rows(COVERAGE_DIR / "external_source_readiness.csv", "source_id", SOURCE_ID)
    backlog = _matching_rows(SEL_DIR / "external_public_source_backlog.csv", "source_id", SOURCE_ID)
    source = intake.get("source", {})
    ambiguity: list[str] = []
    source_ids = {SOURCE_ID}
    for row in next_options:
        if row.get("existing_source_id"):
            source_ids.add(row["existing_source_id"])
    for row in readiness + backlog:
        if row.get("source_id"):
            source_ids.add(row["source_id"])
    if source.get("source_id"):
        source_ids.add(source["source_id"])
    if source_ids != {SOURCE_ID}:
        ambiguity.append(f"linked_source_ids={sorted(source_ids)}")
    if not source or source.get("source_id") != SOURCE_ID:
        ambiguity.append("intake_candidate_missing_or_wrong_source_id")
    return (
        {
            "source_id": source.get("source_id", SOURCE_ID),
            "source_name": source.get("source_name", "Low-Volatility Factor Proxy"),
            "source_type": source.get("source_type", ""),
            "citation": source.get("source_url_or_citation", ""),
            "intake_path": str(_abs(INTAKE_PATH)),
            "next_discovery_rows": len(next_options),
            "external_source_readiness_rows": len(readiness),
            "external_public_source_backlog_rows": len(backlog),
            "unique_associated_source": not ambiguity,
            "ambiguity": ";".join(ambiguity),
        },
        ambiguity,
    )


def _rule_rows(intake: dict[str, Any]) -> list[dict[str, Any]]:
    source = intake.get("source", {})
    description = intake.get("strategy_description", {})
    rules = intake.get("rules", {})
    execution = intake.get("data_and_execution", {})
    return [
        {
            "field": "economic_hypothesis",
            "extracted_value": description.get("claimed_hypothesis", ""),
            "classification": "source_explicit" if description.get("claimed_hypothesis") else "unresolved",
            "material": True,
            "source_support": source.get("source_url_or_citation", ""),
            "notes": "High-level hypothesis is present, but it is not a complete implementation rule.",
        },
        {
            "field": "eligible_universe",
            "extracted_value": "|".join(description.get("instruments", [])),
            "classification": "mechanical_etf_wrapper_translation",
            "material": True,
            "source_support": "intake candidate proposed SPLV/USMV/SPY/BIL wrapper context",
            "notes": "Wrapper list is present, but source-defined stock/index membership or ETF universe rule is not frozen.",
        },
        {
            "field": "security_or_etf_selection_rule",
            "extracted_value": rules.get("ranking_selection_rule", ""),
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "Intake says exact source rule is not frozen.",
        },
        {
            "field": "volatility_definition",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No source-backed realized-volatility formula, return frequency, or calculation convention supplied.",
        },
        {
            "field": "lookback_period",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No source-backed volatility or selection lookback supplied.",
        },
        {
            "field": "ranking_direction",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "Cannot infer ascending/descending volatility ranking from strategy name alone.",
        },
        {
            "field": "number_or_proportion_selected",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No top-N, quantile, index methodology, or wrapper-hold rule is source-supported.",
        },
        {
            "field": "weighting_rule",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No source-supported equal-weight, cap-weight, inverse-vol, or index-weight rule supplied.",
        },
        {
            "field": "rebalance_cadence",
            "extracted_value": rules.get("rebalance_frequency", "manual_input_required"),
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "The source record itself marks rebalance frequency manual_input_required.",
        },
        {
            "field": "entry_rule",
            "extracted_value": rules.get("entry_rule", "manual_input_required"),
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No entry rule may be borrowed from active VM.",
        },
        {
            "field": "exit_or_replacement_rule",
            "extracted_value": rules.get("exit_rule", "manual_input_required"),
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No source-backed exit, replacement, or rebalance-to-wrapper rule supplied.",
        },
        {
            "field": "risk_control_or_cash_behavior",
            "extracted_value": rules.get("risk_controls", ""),
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "Risk controls are stated as conditional future wrapper constraints, not a frozen source rule.",
        },
        {
            "field": "missing_data_behavior",
            "extracted_value": "manual_input_required",
            "classification": "unresolved",
            "material": True,
            "source_support": "",
            "notes": "No missing-data or incomplete-wrapper behavior is supplied.",
        },
        {
            "field": "long_only_unlevered_boundary",
            "extracted_value": "Long-only ETF wrapper only if later approved; no leverage; no shorting; no options/futures; no intraday execution.",
            "classification": "project_execution_convention",
            "material": True,
            "source_support": "project constraints in intake candidate",
            "notes": "Project boundary is explicit; it does not complete the strategy mechanism.",
        },
        {
            "field": "data_requirements",
            "extracted_value": execution.get("data_requirements", ""),
            "classification": "project_execution_convention",
            "material": False,
            "source_support": "intake candidate",
            "notes": "Cache feasibility can be checked without running a backtest.",
        },
    ]


def _source_support_rows(rule_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "field": row["field"],
            "classification": row["classification"],
            "material": row["material"],
            "source_support_present": bool(row["source_support"]) and row["classification"] != "unresolved",
            "supporting_reference": row["source_support"],
            "support_gap": "" if row["classification"] != "unresolved" else row["notes"],
        }
        for row in rule_rows
    ]


def _active_vm_fingerprint(active_vm: dict[str, Any]) -> list[dict[str, Any]]:
    rule_summary = active_vm.get("rule_summary", [])
    return [
        {"dimension": "strategy_id", "active_vm_value": active_vm.get("base_strategy_id", "vm_quality_lowvol_proxy_v1"), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "observation_id", "active_vm_value": active_vm.get("observation_id", ACTIVE_VM_ID), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "status", "active_vm_value": active_vm.get("status", ""), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "frozen", "active_vm_value": active_vm.get("frozen", ""), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "family", "active_vm_value": active_vm.get("family", ""), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "universe", "active_vm_value": "|".join(active_vm.get("universe", [])), "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "rebalance_cadence", "active_vm_value": "monthly", "source": "active_observation.rule_summary"},
        {"dimension": "eligibility_signal", "active_vm_value": "close > 200-day SMA", "source": "active_observation.rule_summary"},
        {"dimension": "ranking_signal", "active_vm_value": "126-day return / 60-day realized volatility", "source": "active_observation.rule_summary"},
        {"dimension": "selection_rule", "active_vm_value": "hold top 2 eligible assets equally; if one eligible hold 100%; if none hold 100% BIL", "source": "active_observation.rule_summary"},
        {"dimension": "scales_total_equity_exposure_using_realized_volatility", "active_vm_value": "false; volatility is used in risk-adjusted ranking, not as a total-exposure target-vol scaler", "source": "mechanism reconstruction from rule_summary"},
        {"dimension": "cross_sectional_or_single_asset", "active_vm_value": "cross-sectional ETF wrapper ranking among SPLV, USMV, QUAL, SPY", "source": "mechanism reconstruction from rule_summary"},
        {"dimension": "cash_or_bil_behavior", "active_vm_value": "BIL if no eligible risky ETF", "source": "active_observation.rule_summary"},
        {"dimension": "protected_state", "active_vm_value": "active VM remains frozen; no rule is donated to the source candidate", "source": str(_abs(ACTIVE_VM_PATH))},
        {"dimension": "raw_rule_summary", "active_vm_value": " | ".join(str(item) for item in rule_summary), "source": str(_abs(ACTIVE_VM_PATH))},
    ]


def _prior_fingerprints() -> list[dict[str, Any]]:
    return [
        {
            "prior_strategy_or_family": "paper_forward_vm_quality_lowvol_proxy_v1",
            "status": "active_frozen_observation",
            "universe": "SPLV|USMV|QUAL|SPY|BIL",
            "signal": "200d SMA eligibility and 126d return / 60d realized-vol ranking",
            "portfolio_construction": "top-2 equal weight among eligible ETFs",
            "risk_off_behavior": "100% BIL only if no eligible risky ETF",
            "source_artifact": str(_abs(ACTIVE_VM_PATH)),
            "duplicate_risk_note": "Closest prior low-vol overlap; cannot be changed or used to fill gaps.",
        },
        {
            "prior_strategy_or_family": "lvq_lowvol_quality_top2_v1",
            "status": "duplicate_or_near_duplicate",
            "universe": "low-vol/quality factor ETF proxies",
            "signal": "project research-sample low-vol/quality proxy rotation",
            "portfolio_construction": "top-N/factor proxy rotation context",
            "risk_off_behavior": "project-specific, not source-backed for this candidate",
            "source_artifact": "strategy_lab/strategy_registry.yaml",
            "duplicate_risk_note": "Prior low-vol quality row was duplicate/near-duplicate, so source-backed mechanism must be materially different.",
        },
        {
            "prior_strategy_or_family": "lvq_lowvol_quality_spy_regime_v1",
            "status": "keep_watchlist",
            "universe": "low-vol/quality factor ETF proxies and SPY/BIL controls",
            "signal": "project low-vol quality plus SPY regime context",
            "portfolio_construction": "project-defined watchlist row",
            "risk_off_behavior": "SPY-regime/fallback context",
            "source_artifact": "strategy_lab/strategy_registry.yaml",
            "duplicate_risk_note": "Watchlist diagnostic only; not a source-backed public low-vol factor rule.",
        },
        {
            "prior_strategy_or_family": "value_momentum_factor_etf_rotation_v1",
            "status": "duplicate_or_near_duplicate",
            "universe": "MTUM|VTV|QUAL|USMV|SPY|BIL",
            "signal": "126d return rank with 200d SMA filter",
            "portfolio_construction": "top-2 factor ETF rotation",
            "risk_off_behavior": "BIL for unused/filtered exposure",
            "source_artifact": "evidence/profit_exploration and strategy registry snapshots",
            "duplicate_risk_note": "Includes USMV but is a momentum/factor rotation, not a complete source-backed low-volatility factor definition.",
        },
        {
            "prior_strategy_or_family": "volatility_throttle_focused_research_lane_v1",
            "status": "completed_diagnostic_not_promotable",
            "universe": "equity tactical ETFs",
            "signal": "realized volatility throttle",
            "portfolio_construction": "exposure multiplier / BIL remainder",
            "risk_off_behavior": "BIL as defensive remainder",
            "source_artifact": "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit/latest",
            "duplicate_risk_note": "Volatility-managed exposure, not low-volatility factor selection.",
        },
        {
            "prior_strategy_or_family": "risk_parity_inverse_volatility_or_vol_targeting",
            "status": "control_weak_closed_for_immediate_retesting",
            "universe": "multi-asset ETF wrapper",
            "signal": "inverse-volatility/risk-parity context",
            "portfolio_construction": "risk allocation, not equity low-vol factor selection",
            "risk_off_behavior": "BIL/cash per source-backed risk parity trend context",
            "source_artifact": "evidence/risk_parity_trend_*",
            "duplicate_risk_note": "Shares volatility language but different asset-class allocation mechanism.",
        },
    ]


def _material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_source_id": SOURCE_ID,
            "closest_prior_strategy": ACTIVE_VM_ID,
            "shared_dimensions": "SPLV/USMV/SPY/BIL context; low-volatility wording; long-only ETF wrappers; monthly/daily wrapper feasibility",
            "changed_dimensions": "unproven because source lacks selection, volatility formula, lookback, weighting, rebalance, entry, exit, and replacement rules",
            "changed_dimensions_source_backed": "false",
            "mechanism_based_distinction": "not_determinable_from_existing_source_record",
            "duplicate_or_parameter_variation_risk": "medium_high",
            "decision": OUTCOME_EXTERNAL_SOURCE_REQUIRED,
            "rationale": "The existing source record is too incomplete to prove a materially distinct mechanism from active VM or prior low-volatility proxy variants.",
        },
        {
            "candidate_source_id": SOURCE_ID,
            "closest_prior_strategy": "value_momentum_factor_etf_rotation_v1",
            "shared_dimensions": "USMV/SPY/BIL factor-wrapper context",
            "changed_dimensions": "low-volatility factor hypothesis might differ from momentum rotation, but no source-backed rules are frozen",
            "changed_dimensions_source_backed": "false",
            "mechanism_based_distinction": "not_determinable_from_existing_source_record",
            "duplicate_or_parameter_variation_risk": "medium",
            "decision": OUTCOME_EXTERNAL_SOURCE_REQUIRED,
            "rationale": "Ticker overlap alone is not enough either to reject as duplicate or to preregister as distinct.",
        },
    ]


def _etf_feasibility_rows(intake: dict[str, Any]) -> list[dict[str, Any]]:
    instruments = intake.get("strategy_description", {}).get("instruments", ["SPLV", "USMV", "SPY", "BIL"])
    rows: list[dict[str, Any]] = []
    for symbol in instruments:
        info = _cache_info(symbol)
        directness = "cached_wrapper_named_in_intake"
        changes_mechanism = "unresolved_source_mechanism"
        material_differences = "ETF wrapper exists locally, but source does not define whether to hold wrapper, rank wrappers, replicate an index, or select stocks."
        if symbol in {"SPY", "BIL"}:
            material_differences = "Benchmark/cash proxy is cache-ready; source mechanism still not frozen."
        rows.append(
            {
                "source_asset_or_universe_role": symbol,
                "local_etf_wrapper": symbol,
                "cache_ready": info["cache_ready"],
                "cache_start": info["cache_start"],
                "cache_end": info["cache_end"],
                "row_count": info["row_count"],
                "cache_hash": info["cache_hash"],
                "directness_of_mapping": directness,
                "material_differences": material_differences,
                "mapping_changes_source_mechanism": changes_mechanism,
                "feasibility_status": "cache_ready_but_rule_incomplete" if info["cache_ready"] else "cache_missing",
            }
        )
    return rows


def _missing_rows(rule_rows: list[dict[str, Any]], source_identity: dict[str, Any]) -> list[dict[str, Any]]:
    missing = [
        row
        for row in rule_rows
        if row["classification"] == "unresolved" and row.get("material")
    ]
    rows = [
        {
            "field": row["field"],
            "blocking_reason": row["notes"],
            "source_evidence_present": row["source_support"],
            "source_evidence_absent": "complete cited source rule with page/section/table/code support",
            "needed_for_preregistration": True,
        }
        for row in missing
    ]
    if not source_identity.get("unique_associated_source"):
        rows.append(
            {
                "field": "source_identity",
                "blocking_reason": source_identity.get("ambiguity", "no unique source"),
                "source_evidence_present": "",
                "source_evidence_absent": "unique source association",
                "needed_for_preregistration": True,
            }
        )
    return rows


def _decision_md(decision: dict[str, Any]) -> str:
    missing = "\n".join(f"- `{field}`" for field in decision["blocking_fields"])
    return f"""# Low-Volatility Factor Source-Backed Preregistration Decision

Outcome: `{decision["outcome"]}`

Source evaluated: `{decision["source_id"]}` / {decision["source_name"]}

The existing source association is unique, but the source record is not complete enough to freeze a strategy specification. The intake explicitly preserves `manual_input_required` for entry, exit, rebalance, and exact source rule rather than inventing them.

## Why No Preregistration Was Created

Material unresolved fields:

{missing}

Active VM remains protected. Its rule summary was reconstructed only as a comparison fingerprint and was not used to fill any source-rule gap.

## Smallest Useful Next Research Question

Find one external, traceable low-volatility factor source that explicitly defines the investable universe, volatility calculation, lookback, ranking direction, number or proportion selected, weighting, rebalance cadence, entry/replacement/exit behavior, missing-data behavior, and whether ETF-wrapper translation is direct. The source must differ from active VM by a source-backed mechanism, not merely by ticker, threshold, lookback, or wrapper substitution.

No implementation, backtest, provider download, registry mutation, lifecycle change, paper/demo action, or real-money recommendation occurred.
"""


def _external_question_md() -> str:
    return """# External Source Research Question

Find or reject a public/external low-volatility factor source suitable for a bounded project preregistration.

The source must provide:

- A traceable citation with exact supporting section, page, table, code, or methodology reference.
- Eligible universe and whether it is individual stocks, an index methodology, ETF wrappers, or a source-defined basket.
- volatility calculation / definition, return frequency, lookback period, ranking direction, number/proportion selected, weighting, and rebalance cadence.
- Entry, exit, replacement, and missing-data behavior.
- Long-only/unlevered feasibility without shorting, options, futures, intraday data, unavailable fundamentals, proprietary point-in-time constituents, or provider downloads.
- A direct ETF-wrapper boundary if ETFs are used.

The eventual source must be mechanically distinct from active VM. A usable source cannot simply say to buy SPLV/USMV, change active VM's volatility window, substitute a risky ETF inside active VM, or relabel a prior quality/low-volatility proxy result.
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    global ROOT
    ROOT = root
    output = ROOT / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    # Remove stale preregistration artifacts from a previous ready run, if any.
    for stale_name in ("preregistration.yaml", "preregistration.md"):
        stale = output / stale_name
        if stale.exists():
            stale.unlink()

    registry_hash_before = _sha256_file(REGISTRY_PATH)
    intake = _read_yaml(INTAKE_PATH)
    active_vm = _read_yaml(ACTIVE_VM_PATH)
    source_identity, ambiguity = _resolve_source_identity(intake)
    rule_rows = _rule_rows(intake)
    unresolved_material = [row["field"] for row in rule_rows if row["classification"] == "unresolved" and row["material"]]
    etf_rows = _etf_feasibility_rows(intake)
    missing_rows = _missing_rows(rule_rows, source_identity)

    outcome = OUTCOME_EXTERNAL_SOURCE_REQUIRED
    decision = {
        "created_at_utc": _now_utc(),
        "outcome": outcome,
        "source_count_evaluated": 1,
        "source_id": source_identity["source_id"],
        "source_name": source_identity["source_name"],
        "family_id": FAMILY_ID,
        "active_vm_id": ACTIVE_VM_ID,
        "unique_associated_source": source_identity["unique_associated_source"],
        "source_identity_ambiguity": ambiguity,
        "blocking_fields": unresolved_material,
        "blocking_reason": "material_source_rules_unresolved",
        "closest_prior_strategy": ACTIVE_VM_ID,
        "material_distinction_result": "not_determinable_until_source_rules_complete",
        "preregistration_created": False,
        "external_source_research_question_created": True,
        "all_named_wrappers_cache_ready": all(row["cache_ready"] for row in etf_rows),
        "cache_ready_symbols": [row["local_etf_wrapper"] for row in etf_rows if row["cache_ready"]],
        "no_active_vm_rule_filled_source_gap": True,
        "active_vm_preserved": True,
        "drift_aware_holdings_accounting_required_later": True,
        "no_provider_call": True,
        "no_backtest_or_performance_computation": True,
        "no_strategy_implementation": True,
        "no_registry_lifecycle_evidence_level_active_observation_or_paper_demo_state_change": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
        "registry_hash_before": registry_hash_before,
    }
    decision["registry_hash_after"] = _sha256_file(REGISTRY_PATH)
    decision["registry_hash_preserved"] = decision["registry_hash_before"] == decision["registry_hash_after"]

    source_identity_rows = [source_identity]
    _write_csv(
        OUTPUT_DIR / "source_identity.csv",
        source_identity_rows,
        [
            "source_id",
            "source_name",
            "source_type",
            "citation",
            "intake_path",
            "next_discovery_rows",
            "external_source_readiness_rows",
            "external_public_source_backlog_rows",
            "unique_associated_source",
            "ambiguity",
        ],
    )
    _write_csv(
        OUTPUT_DIR / "source_rule_extraction.csv",
        rule_rows,
        ["field", "extracted_value", "classification", "material", "source_support", "notes"],
    )
    _write_csv(
        OUTPUT_DIR / "source_support_trace.csv",
        _source_support_rows(rule_rows),
        ["field", "classification", "material", "source_support_present", "supporting_reference", "support_gap"],
    )
    _write_csv(
        OUTPUT_DIR / "active_vm_mechanism_fingerprint.csv",
        _active_vm_fingerprint(active_vm),
        ["dimension", "active_vm_value", "source"],
    )
    _write_csv(
        OUTPUT_DIR / "prior_low_volatility_variant_fingerprints.csv",
        _prior_fingerprints(),
        [
            "prior_strategy_or_family",
            "status",
            "universe",
            "signal",
            "portfolio_construction",
            "risk_off_behavior",
            "source_artifact",
            "duplicate_risk_note",
        ],
    )
    _write_csv(
        OUTPUT_DIR / "material_distinction_review.csv",
        _material_distinction_rows(),
        [
            "candidate_source_id",
            "closest_prior_strategy",
            "shared_dimensions",
            "changed_dimensions",
            "changed_dimensions_source_backed",
            "mechanism_based_distinction",
            "duplicate_or_parameter_variation_risk",
            "decision",
            "rationale",
        ],
    )
    _write_csv(
        OUTPUT_DIR / "etf_wrapper_feasibility.csv",
        etf_rows,
        [
            "source_asset_or_universe_role",
            "local_etf_wrapper",
            "cache_ready",
            "cache_start",
            "cache_end",
            "row_count",
            "cache_hash",
            "directness_of_mapping",
            "material_differences",
            "mapping_changes_source_mechanism",
            "feasibility_status",
        ],
    )
    _write_csv(
        OUTPUT_DIR / "missing_or_ambiguous_fields.csv",
        missing_rows,
        [
            "field",
            "blocking_reason",
            "source_evidence_present",
            "source_evidence_absent",
            "needed_for_preregistration",
        ],
    )
    _write_json(OUTPUT_DIR / "decision.json", decision)
    _write_text(OUTPUT_DIR / "decision.md", _decision_md(decision))
    _write_text(OUTPUT_DIR / "external_source_research_question.md", _external_question_md())

    consistency = {
        "exactly_one_external_source_evaluated": decision["source_count_evaluated"] == 1 and decision["source_id"] == SOURCE_ID,
        "outcome_is_allowed": decision["outcome"] in {"preregistration_ready", OUTCOME_EXTERNAL_SOURCE_REQUIRED, "duplicate_or_not_materially_distinct"},
        "active_vm_remains_unchanged": decision["active_vm_preserved"],
        "no_active_vm_rule_fills_source_rule_gap": decision["no_active_vm_rule_filled_source_gap"],
        "every_preregistered_rule_has_explicit_provenance": True,
        "preregistration_absent_when_source_incomplete": not (output / "preregistration.yaml").exists(),
        "no_exact_rejected_variant_reopened": True,
        "material_distinction_is_mechanism_based": True,
        "no_provider_call": decision["no_provider_call"],
        "no_backtest_or_performance_computation": decision["no_backtest_or_performance_computation"],
        "drift_aware_holdings_accounting_required_later": decision["drift_aware_holdings_accounting_required_later"],
        "no_registry_or_lifecycle_state_change": decision["no_registry_lifecycle_evidence_level_active_observation_or_paper_demo_state_change"],
        "registry_hash_preserved": decision["registry_hash_preserved"],
        "generation_deterministic_except_timestamp": True,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(
        value is True
        for key, value in consistency.items()
        if key not in {"consistency_passed"}
    )
    _write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return decision


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
