from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ID = "quantpedia_asset_class_trend_following_5asset_10m_v1"
OUTPUT_DIR = Path("evidence") / "public_source_strategy_implementation" / STRATEGY_ID / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"

BLOCKING_DECISION = "prohibited_nearby_variant"
SCREENING_OUTCOME = "duplicate_or_prohibited_variant"
PRIMARY_FAILURE_REASON = "prohibited_nearby_variant"
NEXT_ACTION = "direction_owner_review_required_for_prohibited_faber_taa_nearby_variant"

SOURCE_PACKET: dict[str, Any] = {
    "strategy_id": STRATEGY_ID,
    "source": {
        "secondary_page": {
            "title": "Asset Class Trend-Following",
            "publisher": "Quantpedia",
            "url": "https://quantpedia.com/strategies/asset-class-trend-following",
            "public_access": True,
        },
        "original_source": {
            "title": "A Quantitative Approach to Tactical Asset Allocation",
            "author": "Mebane T. Faber",
            "publication": "The Journal of Wealth Management",
            "original_working_paper_year": 2006,
            "published_year": 2007,
            "updated_through": 2013,
            "url": "https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf",
        },
    },
    "canonical_family": "global_tactical_asset_allocation_trend",
    "implementation_tier": "A_existing_engine",
    "duplicate_status": "prohibited_nearby_variant",
    "lifecycle": "rejected_duplicate_or_blocked",
    "economic_mechanism": {
        "value": "independently time each major asset-class sleeve using its own long-term monthly price trend; move weak sleeves into Treasury-bill cash",
        "provenance": "original_source_verified",
    },
    "universe": {
        "economic_asset_classes": {
            "value": ["us_equity", "foreign_developed_equity", "bonds", "real_estate", "commodities"],
            "provenance": "original_source_verified",
        },
        "quantpedia_etf_translation": {
            "value": ["SPY", "EFA", "BND", "VNQ", "GSG"],
            "provenance": "public_page_explicit",
        },
    },
    "cash_proxy": {
        "source_value": "90_day_treasury_bills",
        "source_provenance": "original_source_verified",
        "project_translation": "BIL",
        "project_translation_provenance": "mechanical_translation",
    },
    "rules": {
        "signal_frequency": {"value": "monthly", "provenance": "original_source_verified"},
        "signal": {
            "value": "compare each sleeve's month-end total-return price with its 10-month simple moving average",
            "provenance": "original_source_verified",
        },
        "parameter": {"value": "10_month_sma", "provenance": "original_source_verified"},
        "entry": {
            "value": "allocate the sleeve to its risky asset when monthly price is above the 10-month SMA",
            "provenance": "original_source_verified",
        },
        "exit": {
            "value": "move the sleeve to Treasury-bill cash when monthly price is below the 10-month SMA",
            "provenance": "original_source_verified",
        },
        "weighting": {"value": "five fixed 20_percent sleeves, each timed independently", "provenance": "original_source_verified"},
        "source_execution": {"value": "signal-day month-end close", "provenance": "original_source_verified"},
        "project_safe_execution": {"value": "next_common_session_close", "provenance": "project_execution_convention"},
        "equal_signal_behavior": {"value": "unresolved", "provenance": "unresolved"},
        "missing_data_behavior": {"value": "unresolved", "provenance": "unresolved"},
    },
    "constraints": {
        "long_only": True,
        "project_level_leverage": False,
        "shorting": False,
        "options": False,
        "futures_required": False,
    },
    "secondary_source_reported_performance": {
        "annual_return": "11.27_percent",
        "volatility": "6.87_percent",
        "maximum_drawdown": "-29.43_percent",
        "sharpe_ratio": 1.06,
        "may_influence_project_decisions": False,
    },
    "closest_project_trial": {
        "id": "faber_10m_sma_long_bil_portability_v1",
        "final_outcome": "holdout_does_not_confirm_portability",
    },
    "blocker": {
        "type": "prohibited_nearby_variant",
        "reason": "same Faber source, 10-month parameter, monthly long/cash mechanism and Treasury-bill defensive state; five-sleeve portfolio would be a nearby portfolio/instrument-subset rescue after the family-level holdout failed",
    },
    "frozen_first_test_design": {
        "status": "archived_not_authorized",
        "risky_universe": ["SPY", "EFA", "BND", "VNQ", "GSG"],
        "cash": "BIL",
        "target_weights": "20_percent_per_sleeve",
        "benchmark": "static_equal_weight_same_five_etfs",
        "prohibited_tuning": [
            "sma_length",
            "etf_mapping",
            "sleeve_weights",
            "cash_proxy",
            "execution_delay",
            "rebalance_frequency",
            "sleeve_selection",
        ],
    },
    "stop_conditions": [
        "exact_duplicate_found",
        "prohibited_nearby_variant_found",
        "source_rule_conflict",
        "unresolved_execution_or_data_rule",
    ],
}


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def evidence_exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def duplicate_review_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "review_item": "closest_project_trial",
            "project_id": "faber_10m_sma_long_bil_portability_v1",
            "evidence_path": "evidence/faber_10m_sma_long_bil_portability_holdout_v1/latest",
            "evidence_exists": evidence_exists(root, "evidence/faber_10m_sma_long_bil_portability_holdout_v1/latest"),
            "shared_source": "Mebane T. Faber tactical asset allocation",
            "shared_mechanism": "monthly 10-month SMA long/cash timing",
            "shared_cash_behavior": "Treasury-bill/BIL defensive state",
            "difference": "five fixed sleeves instead of the broader portability trial records",
            "classification": "prohibited_nearby_variant",
            "blocks_implementation": True,
        },
        {
            "review_item": "public_source_phase_checkpoint",
            "project_id": "faber_taa",
            "evidence_path": "evidence/research_recovery/public_source_phase_checkpoint/latest/candidate_status_ledger.csv",
            "evidence_exists": evidence_exists(root, "evidence/research_recovery/public_source_phase_checkpoint/latest/candidate_status_ledger.csv"),
            "shared_source": "Faber/TAA Asset Class Trend Following",
            "shared_mechanism": "global multi-asset trend/cash timing",
            "shared_cash_behavior": "cash defensive state",
            "difference": "checkpoint already marks the source duplicate/do-not-retest",
            "classification": "prohibited_nearby_variant",
            "blocks_implementation": True,
        },
        {
            "review_item": "registry_planning_row",
            "project_id": "gtaa_faber_style_benchmark_lane",
            "evidence_path": "strategy_lab/strategy_registry.yaml",
            "evidence_exists": evidence_exists(root, "strategy_lab/strategy_registry.yaml"),
            "shared_source": "Faber-style GTAA planning row",
            "shared_mechanism": "asset-class trend following planning context",
            "shared_cash_behavior": "not implementation-authorized",
            "difference": "registry row is planning-only/watchlist, not implementation approval",
            "classification": "requires_direction_owner_review",
            "blocks_implementation": False,
        },
    ]


def rule_provenance_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, payload in SOURCE_PACKET["rules"].items():
        rows.append(
            {
                "rule_field": field,
                "rule_value": payload["value"],
                "provenance": payload["provenance"],
                "material_rule": field
                in {
                    "signal_frequency",
                    "signal",
                    "parameter",
                    "entry",
                    "exit",
                    "weighting",
                    "source_execution",
                    "project_safe_execution",
                    "equal_signal_behavior",
                    "missing_data_behavior",
                },
                "blocking_if_unresolved": payload["provenance"] == "unresolved",
            }
        )
    rows.extend(
        [
            {
                "rule_field": "universe",
                "rule_value": SOURCE_PACKET["universe"]["quantpedia_etf_translation"]["value"],
                "provenance": SOURCE_PACKET["universe"]["quantpedia_etf_translation"]["provenance"],
                "material_rule": True,
                "blocking_if_unresolved": False,
            },
            {
                "rule_field": "cash_proxy",
                "rule_value": SOURCE_PACKET["cash_proxy"]["project_translation"],
                "provenance": SOURCE_PACKET["cash_proxy"]["project_translation_provenance"],
                "material_rule": True,
                "blocking_if_unresolved": False,
            },
        ]
    )
    return rows


def missing_requirement_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement": "prohibited_nearby_variant_review",
            "status": "blocking",
            "reason": SOURCE_PACKET["blocker"]["reason"],
            "smallest_revisit_condition": "direction-owner supplies materially distinct source-backed mechanism, not a Faber/TAA sleeve subset or parameter/instrument rescue",
        },
        {
            "requirement": "equal_signal_behavior",
            "status": "unresolved_secondary_blocker",
            "reason": "source packet leaves equality versus SMA unresolved",
            "smallest_revisit_condition": "source packet or original-source review freezes equality behavior without inference",
        },
        {
            "requirement": "missing_data_behavior",
            "status": "unresolved_secondary_blocker",
            "reason": "source packet leaves missing-data behavior unresolved",
            "smallest_revisit_condition": "source packet or project convention freezes behavior before any screen",
        },
    ]


def pre_implementation_gate(root: Path) -> dict[str, Any]:
    registry_before = sha256_path(root / REGISTRY_PATH)
    active_before = sha256_path(root / ACTIVE_OBSERVATIONS_PATH)
    duplicates = duplicate_review_rows(root)
    source_reported_performance = SOURCE_PACKET["secondary_source_reported_performance"]
    return {
        "strategy_id": STRATEGY_ID,
        "gate_ran_before_backtest": True,
        "gate_decision": BLOCKING_DECISION,
        "screening_outcome": SCREENING_OUTCOME,
        "primary_failure_reason": PRIMARY_FAILURE_REASON,
        "implementation_allowed": False,
        "backtest_allowed": False,
        "backtest_run": False,
        "candidate_metrics_created": False,
        "benchmark_metrics_created": False,
        "source_packet_duplicate_status": SOURCE_PACKET["duplicate_status"],
        "source_packet_lifecycle": SOURCE_PACKET["lifecycle"],
        "closest_project_trial": SOURCE_PACKET["closest_project_trial"],
        "blocking_repository_evidence": [
            row["evidence_path"] for row in duplicates if row["blocks_implementation"]
        ],
        "secondary_material_blockers": ["equal_signal_behavior", "missing_data_behavior"],
        "source_reported_performance_present": True,
        "source_reported_performance_used_for_selection": False,
        "source_reported_performance_used_for_pass_fail": False,
        "source_reported_performance": source_reported_performance,
        "public_page_copied_verbatim": False,
        "full_public_page_stored": False,
        "long_passages_stored": False,
        "strategy_logic_written": False,
        "unregistered_parameter_variants_run": False,
        "parameter_optimization_run": False,
        "instrument_substitution_performed": False,
        "missing_data_silently_shrank_universe": False,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_before,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_before,
        "paper_demo_activation": False,
        "broker_or_order_behavior": False,
        "real_money_recommendation": False,
        "family_status_after_gate": "broader_family_not_closed_by_this_task",
        "exact_variant_status_after_gate": "blocked_not_implemented",
        "next_action": NEXT_ACTION,
    }


def blocker_report(gate: dict[str, Any]) -> str:
    return f"""# Public Source Strategy Implementation Blocker

Strategy: `{STRATEGY_ID}`

Gate decision: `{gate['gate_decision']}`

Implementation stopped before strategy logic or backtesting because the supplied source packet and repository memory both classify this as a prohibited nearby Faber/TAA variant. The closest project trial is `{SOURCE_PACKET['closest_project_trial']['id']}`, whose holdout outcome is recorded as `{SOURCE_PACKET['closest_project_trial']['final_outcome']}`.

Supporting evidence:
- `evidence/faber_10m_sma_long_bil_portability_holdout_v1/latest`
- `evidence/research_recovery/public_source_phase_checkpoint/latest/candidate_status_ledger.csv`
- `strategy_lab/strategy_registry.yaml`

The broader family is not closed by this task. Only this exact supplied five-sleeve Faber/TAA implementation request is blocked. Revisit would require a direction-owner supplied, materially distinct, source-backed mechanism that is not an instrument-subset, parameter, execution, or sleeve-weight rescue of the prior Faber/TAA line.

No candidate metrics, benchmark metrics, paper/demo activation, broker path, or real-money recommendation was created.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    gate = pre_implementation_gate(root)
    duplicate_rows = duplicate_review_rows(root)
    missing_rows = missing_requirement_rows()

    write_yaml(output / "source_packet_used.yaml", SOURCE_PACKET)
    write_json(output / "pre_implementation_gate.json", gate)
    write_csv(
        output / "duplicate_and_closure_review.csv",
        duplicate_rows,
        [
            "review_item",
            "project_id",
            "evidence_path",
            "evidence_exists",
            "shared_source",
            "shared_mechanism",
            "shared_cash_behavior",
            "difference",
            "classification",
            "blocks_implementation",
        ],
    )
    write_csv(
        output / "missing_requirements.csv",
        missing_rows,
        ["requirement", "status", "reason", "smallest_revisit_condition"],
    )
    write_text(output / "blocker_report.md", blocker_report(gate))
    consistency = {
        "strategy_id": STRATEGY_ID,
        "blocked_outputs_only": sorted(path.name for path in output.iterdir() if path.is_file())
        == [
            "blocker_report.md",
            "duplicate_and_closure_review.csv",
            "missing_requirements.csv",
            "pre_implementation_gate.json",
            "source_packet_used.yaml",
        ],
        "gate_ran_before_backtest": gate["gate_ran_before_backtest"],
        "implementation_allowed": gate["implementation_allowed"],
        "backtest_run": gate["backtest_run"],
        "candidate_metrics_created": (output / "candidate_metrics.csv").exists(),
        "benchmark_metrics_created": (output / "benchmark_metrics.csv").exists(),
        "duplicate_or_prohibited_variant_blocked": gate["gate_decision"] == BLOCKING_DECISION,
        "source_rules_incomplete_recorded": any(row["status"].endswith("secondary_blocker") for row in missing_rows),
        "source_reported_performance_used": False,
        "public_page_copied_verbatim": False,
        "registry_unchanged": gate["registry_hash_before"] == sha256_path(root / REGISTRY_PATH),
        "active_observations_unchanged": gate["active_observations_hash_before"] == sha256_path(root / ACTIVE_OBSERVATIONS_PATH),
        "paper_demo_activation": False,
        "broker_or_order_behavior": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["gate_ran_before_backtest"]
        and not consistency["implementation_allowed"]
        and not consistency["backtest_run"]
        and not consistency["candidate_metrics_created"]
        and not consistency["benchmark_metrics_created"]
        and consistency["duplicate_or_prohibited_variant_blocked"]
        and consistency["registry_unchanged"]
        and consistency["active_observations_unchanged"]
        and not consistency["source_reported_performance_used"]
        and not consistency["paper_demo_activation"]
        and not consistency["broker_or_order_behavior"]
    )
    write_json(output / "consistency_check.json", consistency)
    return {
        "strategy_id": STRATEGY_ID,
        "evidence_dir": str(output),
        "gate_decision": gate["gate_decision"],
        "screening_outcome": gate["screening_outcome"],
        "implementation_allowed": gate["implementation_allowed"],
        "backtest_run": gate["backtest_run"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
