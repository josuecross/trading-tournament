from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "active_observation_evidence_reconciliation" / "latest"

VM_ACTIVE_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
VM_PARENT_ID = "vm_quality_lowvol_proxy_v1"
VM_FAMILY_ID = "volatility_managed_equity_etf"

DSR_ACTIVE_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
DSR_PARENT_ID = "dsr_sector_equal_weight_defensive_filter_v1"
DSR_FAMILY_ID = "defensive_sector_rotation_etf"

TARGETS = {
    VM_ACTIVE_ID: {
        "parent_strategy_id": VM_PARENT_ID,
        "family_id": VM_FAMILY_ID,
        "activation_dir": Path("evidence") / "paper_forward_activations" / VM_PARENT_ID / "latest",
        "active_detail": Path("paper_forward_observations") / VM_ACTIVE_ID / "active_observation.yaml",
        "activation_detail": Path("evidence")
        / "paper_forward_activations"
        / VM_PARENT_ID
        / "latest"
        / f"{VM_ACTIVE_ID}_active_observation.yaml",
        "chain_csv": "vm_quality_lowvol_proxy_v1_evidence_chain.csv",
    },
    DSR_ACTIVE_ID: {
        "parent_strategy_id": DSR_PARENT_ID,
        "family_id": DSR_FAMILY_ID,
        "activation_dir": Path("evidence") / "paper_forward_activations" / DSR_PARENT_ID / "latest",
        "active_detail": Path("paper_forward_observations") / DSR_ACTIVE_ID / "active_observation.yaml",
        "activation_detail": Path("evidence")
        / "paper_forward_activations"
        / DSR_PARENT_ID
        / "latest"
        / f"{DSR_ACTIVE_ID}_active_observation.yaml",
        "chain_csv": "dsr_sector_equal_weight_defensive_filter_v1_evidence_chain.csv",
    },
}

CANONICAL_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
    TARGETS[VM_ACTIVE_ID]["active_detail"],
    TARGETS[DSR_ACTIVE_ID]["active_detail"],
]

RECOMPUTE_DIR = Path("evidence") / "active_strategy_evidence_recompute" / "latest"
RECOMPUTE_MANIFEST = RECOMPUTE_DIR / "active_strategy_recompute_manifest.json"
RECOMPUTE_CONSISTENCY = RECOMPUTE_DIR / "active_strategy_recompute_consistency_check.json"
RECOMPUTE_SUMMARY = RECOMPUTE_DIR / "active_strategy_evidence_recompute_summary.md"
RECOMPUTE_RECOVERED_VS_RECOMPUTED = RECOMPUTE_DIR / "active_strategy_recompute_recovered_vs_recomputed.csv"
RECOMPUTE_SCORECARD = RECOMPUTE_DIR / "active_strategy_recompute_scorecard.csv"
RECOMPUTE_RULE_FIDELITY = RECOMPUTE_DIR / "active_strategy_recompute_rule_fidelity.csv"
RECOMPUTE_MISSING = RECOMPUTE_DIR / "active_strategy_recompute_missing_evidence.md"

VM_LANE_REVIEW_DIR = Path("evidence") / "lane_reviews" / VM_FAMILY_ID / "latest"

CHAIN_FIELDS = [
    "active_observation_id",
    "parent_strategy_id",
    "family_id",
    "evidence_stage",
    "classification",
    "source_path",
    "source_record_or_field",
    "run_batch_id",
    "code_hash",
    "configuration_hash",
    "data_identity",
    "decision_value",
    "decision_date",
    "reviewer",
    "artifact_predates_qualifying_run",
    "artifact_superseded",
    "confidence",
    "exact_missing_requirements",
    "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_paths(root: Path, paths: list[Path]) -> dict[str, str]:
    return {str(path).replace("\\", "/"): file_hash(root / path) for path in paths}


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def relative(path: Path) -> str:
    return str(path).replace("\\", "/")


def registry_rows(root: Path) -> dict[str, dict[str, Any]]:
    registry = read_yaml(root / "strategy_lab" / "strategy_registry.yaml")
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def recovered_vs_recomputed_rows(root: Path) -> list[dict[str, str]]:
    path = root / RECOMPUTE_RECOVERED_VS_RECOMPUTED
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def scorecard_rows(root: Path) -> list[dict[str, str]]:
    path = root / RECOMPUTE_SCORECARD
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def config_match(root: Path, active_id: str) -> dict[str, Any]:
    target = TARGETS[active_id]
    active_detail_path = root / target["active_detail"]
    activation_detail_path = root / target["activation_detail"]
    active_detail = read_yaml(active_detail_path)
    activation_detail = read_yaml(activation_detail_path)
    compared_fields = [
        "observation_id",
        "base_strategy_id",
        "family",
        "status",
        "frozen",
        "rules_frozen",
        "paper_forward_active",
        "strategy_rule_summary",
        "universe",
        "forbidden",
    ]
    mismatches = [
        field
        for field in compared_fields
        if active_detail.get(field) != activation_detail.get(field)
    ]
    return {
        "active_detail_path": relative(target["active_detail"]),
        "activation_detail_path": relative(target["activation_detail"]),
        "active_detail_hash": file_hash(active_detail_path),
        "activation_detail_hash": file_hash(activation_detail_path),
        "compared_fields": compared_fields,
        "mismatched_fields": mismatches,
        "matches_recovered_activation_detail": not mismatches and bool(active_detail) and bool(activation_detail),
    }


def stage_row(
    active_id: str,
    stage: str,
    classification: str,
    source_path: str,
    source_field: str,
    decision_value: str,
    confidence: str,
    missing: list[str],
    notes: str,
    *,
    run_batch_id: str = "not_applicable",
    code_hash: str = "unknown",
    configuration_hash: str = "unknown",
    data_identity: str = "unknown",
    decision_date: str = "unknown",
    reviewer: str = "unknown",
    predates: str = "unknown",
    superseded: str = "false",
) -> dict[str, Any]:
    target = TARGETS[active_id]
    return {
        "active_observation_id": active_id,
        "parent_strategy_id": target["parent_strategy_id"],
        "family_id": target["family_id"],
        "evidence_stage": stage,
        "classification": classification,
        "source_path": source_path,
        "source_record_or_field": source_field,
        "run_batch_id": run_batch_id,
        "code_hash": code_hash,
        "configuration_hash": configuration_hash,
        "data_identity": data_identity,
        "decision_value": decision_value,
        "decision_date": decision_date,
        "reviewer": reviewer,
        "artifact_predates_qualifying_run": predates,
        "artifact_superseded": superseded,
        "confidence": confidence,
        "exact_missing_requirements": "; ".join(missing),
        "notes": notes,
    }


def build_chain(root: Path, active_id: str, recompute_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    target = TARGETS[active_id]
    activation_dir = target["activation_dir"]
    activation_manifest_path = activation_dir / "manifest.json"
    activation_manifest = read_json(root / activation_manifest_path)
    activation_summary_path = activation_dir / "activation_summary.md"
    frozen_rule_path = activation_dir / "frozen_rule.md"
    benchmark_plan_path = activation_dir / "benchmark_plan.md"
    risk_plan_path = activation_dir / "risk_plan.md"
    active_detail_path = target["active_detail"]
    active_hash = file_hash(root / active_detail_path)
    recompute_created = str(recompute_manifest.get("created_at_utc", "unknown"))
    recompute_decision = str(recompute_manifest.get("decisions", {}).get(active_id, "unknown"))
    recompute_manual = str(recompute_manifest.get("manual_review_required", {}).get(active_id, "unknown"))
    data_identity = (
        "cache_used=true; data_history_mode="
        + str(recompute_manifest.get("data_history_mode", "unknown"))
        + "; data_label="
        + str(recompute_manifest.get("data_label", "unknown"))
    )
    source_status = activation_manifest.get("evidence_source", "unknown")
    created = activation_manifest.get("created_utc", "unknown")
    run_id = activation_manifest.get("run_id", "unknown")
    code_hash = file_hash(root / "run_active_strategy_evidence_recompute.py")
    test_hash = file_hash(root / "tests" / "test_active_strategy_evidence_recompute.py")
    e3_code_hash = f"{code_hash}; test={test_hash}"

    e4_classification = "partial_existing_evidence"
    e4_notes = "Cached-data active evidence recompute exists, but it is a reconciliation/audit packet, not the original qualifying backtest."
    if active_id == DSR_ACTIVE_ID:
        e4_classification = "conflicting_existing_evidence"
        e4_notes = "Cached-data active evidence recompute exists, but DSR had a material recovered-vs-recomputed mismatch requiring manual review."

    rows = [
        stage_row(
            active_id,
            "E2",
            "partial_existing_evidence",
            "; ".join(
                [
                    relative(active_detail_path),
                    relative(frozen_rule_path),
                    relative(benchmark_plan_path),
                    relative(risk_plan_path),
                ]
            ),
            "active_observation fields; frozen_rule.md; benchmark_plan.md; risk_plan.md",
            "rules_frozen_recovered_active_observation",
            "medium",
            [
                "complete data requirements",
                "signal timestamp",
                "execution timestamp or price assumption",
                "success criteria",
                "failure criteria",
                "pre-qualifying preregistration timestamp",
                "immutable frozen specification hash predating qualifying run",
            ],
            "Rules, universe, sizing, rebalance, BIL fallback, benchmark plan, and stop context are present, but the artifact is recovered active-state documentation rather than a complete pre-run preregistration.",
            run_batch_id=run_id,
            configuration_hash=active_hash,
            decision_date=str(created),
            predates="unknown",
        ),
        stage_row(
            active_id,
            "E3",
            "partial_existing_evidence",
            "run_active_strategy_evidence_recompute.py; tests/test_active_strategy_evidence_recompute.py",
            "current recompute implementation and focused tests",
            "current_recompute_implementation_exists",
            "medium_low",
            [
                "exact original implementation path used for qualification",
                "exact configuration path used for qualification",
                "code commit/hash at historical qualifying run",
                "configuration hash at historical qualifying run",
                "implementation review linked to E2",
            ],
            "A tested recompute implementation exists for diagnostic verification, but it does not prove the historical implementation used for activation.",
            run_batch_id="active_strategy_evidence_recompute",
            code_hash=e3_code_hash,
            configuration_hash=active_hash,
            decision_date=recompute_created,
            predates="no",
        ),
        stage_row(
            active_id,
            "E4",
            e4_classification,
            "; ".join(
                [
                    relative(RECOMPUTE_MANIFEST),
                    relative(RECOMPUTE_SUMMARY),
                    relative(RECOMPUTE_RECOVERED_VS_RECOMPUTED),
                    relative(RECOMPUTE_RULE_FIDELITY),
                    relative(RECOMPUTE_SCORECARD),
                ]
            ),
            "active_strategy_recompute_manifest.decisions; recovered_vs_recomputed; scorecard; rule_fidelity",
            f"{recompute_decision}; manual_review_required={recompute_manual}",
            "medium" if active_id == VM_ACTIVE_ID else "medium_low",
            [
                "exact qualifying run or batch ID",
                "implementation/configuration identity for original qualifying run",
                "dataset snapshot hash and full date range",
                "accepted E4 local-backtest decision independent of reconciliation",
                "evidence that no later methodology defect invalidated the qualifying result",
            ],
            e4_notes,
            run_batch_id="active_strategy_evidence_recompute",
            code_hash=e3_code_hash,
            configuration_hash=active_hash,
            data_identity=data_identity,
            decision_date=recompute_created,
            predates="no",
        ),
        stage_row(
            active_id,
            "E5",
            "missing_existing_evidence",
            "; ".join([relative(RECOMPUTE_MISSING), relative(activation_manifest_path)]),
            "active_strategy_recompute_missing_evidence; activation manifest recovered stress fields",
            "no_explicit_robustness_qualification",
            "low",
            [
                "candidate-exhaustive or robustness protocol",
                "stress test protocol with cost/slippage assumptions",
                "parameter-neighborhood or variant checks",
                "out-of-sample or comparable validation",
                "explicit E5 pass decision",
            ],
            "Recovered activation metrics contain stress-like summary values, but the recompute packet says stress-cost-specific recompute was unavailable; no explicit robustness qualification was found.",
            run_batch_id=run_id,
            configuration_hash=active_hash,
            data_identity=data_identity,
            decision_date=str(created),
            predates="unknown",
        ),
        stage_row(
            active_id,
            "E6",
            "conversation_recovered_only",
            "; ".join(
                [
                    relative(activation_manifest_path),
                    relative(activation_summary_path),
                    "strategy_lab/research_os/operations/active_observations.yaml",
                    "strategy_lab/strategy_registry.yaml",
                ]
            ),
            "activation manifest paper_forward_active/frozen; registry promotion_decision",
            f"paper_forward_activation_recovered; evidence_source={source_status}",
            "medium_low",
            [
                "explicit paper/demo eligibility approval independent of recovered state",
                "reviewer or governance artifact",
                "frozen paper/demo configuration hash",
                "approval conditions and restrictions linked to complete E2-E5 chain",
                "proof approved configuration predates active observation",
            ],
            "Active/frozen paper-demo state is canonical and preserved, but the approval evidence is explicitly conversation-recovered and cannot independently establish E6.",
            run_batch_id=run_id,
            configuration_hash=active_hash,
            decision_date=str(created),
            predates="unknown",
        ),
    ]
    return rows


def artifact_row(root: Path, active_id: str, role: str, path: Path, source_type: str, notes: str) -> dict[str, Any]:
    return {
        "active_observation_id": active_id,
        "parent_strategy_id": TARGETS[active_id]["parent_strategy_id"],
        "family_id": TARGETS[active_id]["family_id"],
        "artifact_role": role,
        "source_path": relative(path),
        "exists": (root / path).exists(),
        "sha256": file_hash(root / path),
        "source_type": source_type,
        "notes": notes,
    }


def build_artifact_lineage(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for active_id, target in TARGETS.items():
        activation_dir = target["activation_dir"]
        for role, path, source_type, notes in [
            ("canonical_active_detail", target["active_detail"], "canonical_state", "Protected active observation detail."),
            ("recovered_activation_detail", target["activation_detail"], "conversation_recovered", "Recovered activation copy of active detail."),
            ("activation_manifest", activation_dir / "manifest.json", "conversation_recovered", "Recovered activation manifest."),
            ("activation_summary", activation_dir / "activation_summary.md", "conversation_recovered", "Recovered activation summary."),
            ("frozen_rule", activation_dir / "frozen_rule.md", "conversation_recovered", "Recovered frozen rule text."),
            ("benchmark_plan", activation_dir / "benchmark_plan.md", "conversation_recovered", "Recovered benchmark plan."),
            ("risk_plan", activation_dir / "risk_plan.md", "conversation_recovered", "Recovered risk plan."),
            ("active_recompute_manifest", RECOMPUTE_MANIFEST, "cached_data_recompute", "Later cached-data diagnostic recompute."),
            ("active_recompute_recovered_vs_recomputed", RECOMPUTE_RECOVERED_VS_RECOMPUTED, "cached_data_recompute", "Recovered-vs-recomputed metric comparison."),
            ("active_recompute_rule_fidelity", RECOMPUTE_RULE_FIDELITY, "cached_data_recompute", "Rule fidelity comparison."),
            ("active_recompute_scorecard", RECOMPUTE_SCORECARD, "cached_data_recompute", "Recompute scorecard."),
            ("active_recompute_consistency", RECOMPUTE_CONSISTENCY, "cached_data_recompute", "Non-mutation/guardrail consistency check."),
        ]:
            rows.append(artifact_row(root, active_id, role, path, source_type, notes))
    rows.append(
        {
            "active_observation_id": VM_ACTIVE_ID,
            "parent_strategy_id": VM_PARENT_ID,
            "family_id": VM_FAMILY_ID,
            "artifact_role": "family_lineage_context",
            "source_path": relative(VM_LANE_REVIEW_DIR / "volatility_managed_equity_etf_fixed_rules.md"),
            "exists": (root / VM_LANE_REVIEW_DIR / "volatility_managed_equity_etf_fixed_rules.md").exists(),
            "sha256": file_hash(root / VM_LANE_REVIEW_DIR / "volatility_managed_equity_etf_fixed_rules.md"),
            "source_type": "future_research_sample_review",
            "notes": "Contains vm_quality_lowvol_proxy_v1 as a future research-sample variant, not an E4/E6 qualifying run.",
        }
    )
    return rows


def build_missing_or_conflicting(root: Path, chain_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in chain_rows:
        if row["classification"] == "verified_existing_evidence":
            continue
        rows.append(
            {
                "active_observation_id": row["active_observation_id"],
                "parent_strategy_id": row["parent_strategy_id"],
                "family_id": row["family_id"],
                "evidence_stage": row["evidence_stage"],
                "issue_type": row["classification"],
                "source_path": row["source_path"],
                "requirements_or_conflict": row["exact_missing_requirements"],
                "notes": row["notes"],
            }
        )
    for source_row in recovered_vs_recomputed_rows(root):
        if source_row.get("verdict") == "material_mismatch_requires_review":
            rows.append(
                {
                    "active_observation_id": source_row.get("strategy_id", "unknown"),
                    "parent_strategy_id": TARGETS.get(source_row.get("strategy_id", ""), {}).get("parent_strategy_id", "unknown"),
                    "family_id": TARGETS.get(source_row.get("strategy_id", ""), {}).get("family_id", "unknown"),
                    "evidence_stage": "E4",
                    "issue_type": "conflicting_existing_evidence",
                    "source_path": relative(RECOMPUTE_RECOVERED_VS_RECOMPUTED),
                    "requirements_or_conflict": (
                        f"{source_row.get('metric')} historical_recovered_claim={source_row.get('recovered_value')} "
                        f"current_sampled_window_diagnostic={source_row.get('recomputed_value')}; comparability=non_comparable"
                    ),
                    "notes": (
                        "Historical recovered metric is unverified_non_comparable; current recompute is "
                        "reproducible_diagnostic_only/current_diagnostic_only; both are not_qualifying_e4."
                    ),
                }
            )
    return rows


def build_superseded(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    verdicts_by_strategy: dict[str, list[str]] = {}
    for row in recovered_vs_recomputed_rows(root):
        verdicts_by_strategy.setdefault(row.get("strategy_id", "unknown"), []).append(row.get("verdict", "unknown"))
    for active_id in TARGETS:
        verdicts = verdicts_by_strategy.get(active_id, [])
        if active_id == DSR_ACTIVE_ID:
            supersession_status = "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference"
            notes = (
                f"Recovered quantitative metrics are preserved as historical claims and compared against cached diagnostics; "
                f"verdicts={sorted(set(verdicts))}. The DSR historical best_final_equity is unverified_non_comparable, "
                "the current recompute is current_diagnostic_only, and neither changes rule text or active state."
            )
        else:
            supersession_status = "historical_recovered_metrics_compared_to_cached_recompute"
            notes = (
                f"Recovered metrics compared against cached recompute; verdicts={sorted(set(verdicts))}. "
                "Rule text and active state are not superseded by this row."
            )
        rows.append(
            {
                "active_observation_id": active_id,
                "parent_strategy_id": TARGETS[active_id]["parent_strategy_id"],
                "family_id": TARGETS[active_id]["family_id"],
                "superseded_artifact": relative(TARGETS[active_id]["activation_dir"] / "manifest.json"),
                "superseded_scope": "conversation_recovered_quantitative_metrics_only",
                "superseded_by": relative(RECOMPUTE_RECOVERED_VS_RECOMPUTED),
                "supersession_status": supersession_status,
                "decision_effect": "does_not_change_canonical_active_state",
                "notes": notes,
            }
        )
    return rows


def markdown_summary(summary: dict[str, Any], chain_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Active Observation Evidence Reconciliation",
        "",
        f"Created UTC: `{summary['created_at_utc']}`",
        "",
        "This packet traces only the two canonical active/frozen paper-demo observations. It does not run a backtest, recompute metrics, promote, reject, deactivate, or change observation state.",
        "",
        "## Stage Conclusions",
        "",
    ]
    for active_id in [VM_ACTIVE_ID, DSR_ACTIVE_ID]:
        lines.append(f"### `{active_id}`")
        for row in [item for item in chain_rows if item["active_observation_id"] == active_id]:
            lines.append(
                f"- `{row['evidence_stage']}`: `{row['classification']}` from `{row['source_path']}`. Decision/value: `{row['decision_value']}`."
            )
        lines.append(
            f"- Highest independently verified SEL evidence level: `{summary['observations'][active_id]['highest_independently_verified_sel_level']}`."
        )
        lines.append(
            f"- Active config matches recovered activation detail: `{str(summary['observations'][active_id]['config_match']['matches_recovered_activation_detail']).lower()}`."
        )
        lines.append("")
    lines.extend(
        [
            "## SEL Integration Decision",
            "",
            "- No SEL parser or mapping patch was made.",
            "- No E2-E6 stage was fully verified as qualifying existing evidence.",
            "- The current conservative SEL behavior that keeps these active observations at E1 is consistent with this reconciliation.",
            "",
            "## Guardrails",
            "",
            "- Canonical registry and active-observation hashes were checked before and after evidence generation.",
            "- No lifecycle, strategy rule, metric, paper/demo, broker/live, or real-money state was changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_active_observation_evidence_reconciliation(root: Path = ROOT) -> dict[str, Any]:
    canonical_hashes_before = hash_paths(root, CANONICAL_PATHS)
    recompute_manifest = read_json(root / RECOMPUTE_MANIFEST)
    recompute_consistency = read_json(root / RECOMPUTE_CONSISTENCY)
    registry = registry_rows(root)
    active_index = read_yaml(root / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml")

    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    chain_rows: list[dict[str, Any]] = []
    for active_id in TARGETS:
        chain_rows.extend(build_chain(root, active_id, recompute_manifest))

    artifact_rows = build_artifact_lineage(root)
    missing_rows = build_missing_or_conflicting(root, chain_rows)
    superseded_rows = build_superseded(root)

    observations: dict[str, Any] = {}
    for active_id in TARGETS:
        row = registry.get(active_id, {})
        stage_classes = {
            chain["evidence_stage"]: chain["classification"]
            for chain in chain_rows
            if chain["active_observation_id"] == active_id
        }
        observations[active_id] = {
            "parent_strategy_id": TARGETS[active_id]["parent_strategy_id"],
            "family_id": TARGETS[active_id]["family_id"],
            "canonical_registry_status": row.get("status", "unknown"),
            "canonical_registry_paper_forward_active": row.get("paper_forward_active", "unknown"),
            "canonical_registry_rules_frozen": row.get("rules_frozen", "unknown"),
            "reconstructed_stages": stage_classes,
            "highest_independently_verified_sel_level": "E1",
            "highest_independently_verified_sel_level_reason": "No complete E2 prerequisite chain was found; active lifecycle state remains separate from reconstructed evidence level.",
            "config_match": config_match(root, active_id),
        }

    active_ids = [item.get("strategy_id") for item in active_index.get("active_observations", [])]
    canonical_hashes_after = hash_paths(root, CANONICAL_PATHS)
    consistency = {
        "reconciliation_completed": True,
        "target_active_observation_ids": [VM_ACTIVE_ID, DSR_ACTIVE_ID],
        "active_observation_ids_unchanged": set(active_ids) == {VM_ACTIVE_ID, DSR_ACTIVE_ID},
        "canonical_hashes_before": canonical_hashes_before,
        "canonical_hashes_after": canonical_hashes_after,
        "canonical_hashes_unchanged": canonical_hashes_before == canonical_hashes_after,
        "canonical_statuses_unchanged": True,
        "no_strategy_metrics_recomputed": True,
        "no_backtest_run": True,
        "no_strategy_discovery_run": True,
        "no_source_artifact_rewritten": True,
        "no_lifecycle_state_changed": True,
        "no_strategy_rules_changed": True,
        "no_paper_demo_state_changed": True,
        "no_promotion_or_rejection_decision": True,
        "sel_parser_changed": False,
        "recompute_guardrails_reference_passed": bool(recompute_consistency.get("consistency_passed")),
        "missing_or_conflicting_row_count": len(missing_rows),
        "superseded_row_count": len(superseded_rows),
    }
    consistency["consistency_passed"] = all(
        bool(consistency[key])
        for key in [
            "reconciliation_completed",
            "active_observation_ids_unchanged",
            "canonical_hashes_unchanged",
            "canonical_statuses_unchanged",
            "no_strategy_metrics_recomputed",
            "no_backtest_run",
            "no_strategy_discovery_run",
            "no_source_artifact_rewritten",
            "no_lifecycle_state_changed",
            "no_strategy_rules_changed",
            "no_paper_demo_state_changed",
            "no_promotion_or_rejection_decision",
            "recompute_guardrails_reference_passed",
        ]
    )

    summary = {
        "created_at_utc": utc_now(),
        "git_head": git_head(root),
        "reconciliation_only": True,
        "target_active_observation_ids": [VM_ACTIVE_ID, DSR_ACTIVE_ID],
        "canonical_state_unchanged": consistency["canonical_hashes_unchanged"],
        "sel_parser_changed": False,
        "sel_parser_change_reason": "No fully verified E2-E6 source shape was found; no parser exception or promotion mapping was justified.",
        "observations": observations,
        "supporting_artifact_count": len(artifact_rows),
        "missing_or_conflicting_evidence_count": len(missing_rows),
        "superseded_evidence_count": len(superseded_rows),
        "guardrails": {
            "no_strategy_metrics_recomputed": True,
            "no_backtest_run": True,
            "no_strategy_discovery_run": True,
            "no_source_artifact_rewritten": True,
            "no_lifecycle_state_changed": True,
            "no_paper_demo_state_changed": True,
            "no_promotion_or_rejection_decision": True,
        },
        "sel_deterministic_mappings_required": [],
        "next_action": "none_reconciliation_complete_no_state_change",
    }

    write_csv(output / TARGETS[VM_ACTIVE_ID]["chain_csv"], [row for row in chain_rows if row["active_observation_id"] == VM_ACTIVE_ID], CHAIN_FIELDS)
    write_csv(output / TARGETS[DSR_ACTIVE_ID]["chain_csv"], [row for row in chain_rows if row["active_observation_id"] == DSR_ACTIVE_ID], CHAIN_FIELDS)
    write_csv(
        output / "artifact_lineage.csv",
        artifact_rows,
        ["active_observation_id", "parent_strategy_id", "family_id", "artifact_role", "source_path", "exists", "sha256", "source_type", "notes"],
    )
    write_csv(
        output / "missing_or_conflicting_evidence.csv",
        missing_rows,
        ["active_observation_id", "parent_strategy_id", "family_id", "evidence_stage", "issue_type", "source_path", "requirements_or_conflict", "notes"],
    )
    write_csv(
        output / "superseded_evidence.csv",
        superseded_rows,
        ["active_observation_id", "parent_strategy_id", "family_id", "superseded_artifact", "superseded_scope", "superseded_by", "supersession_status", "decision_effect", "notes"],
    )
    write_json(output / "active_observation_evidence_reconciliation.json", summary)
    write_json(output / "reconciliation_consistency_check.json", consistency)
    (output / "active_observation_evidence_reconciliation.md").write_text(markdown_summary(summary, chain_rows), encoding="utf-8")

    return {
        "output_dir": str(output),
        "target_active_observation_ids": [VM_ACTIVE_ID, DSR_ACTIVE_ID],
        "canonical_state_unchanged": consistency["canonical_hashes_unchanged"],
        "consistency_passed": consistency["consistency_passed"],
        "highest_independently_verified_sel_level": {
            active_id: observations[active_id]["highest_independently_verified_sel_level"] for active_id in TARGETS
        },
        "sel_parser_changed": False,
        "next_action": summary["next_action"],
    }


def main() -> None:
    result = run_active_observation_evidence_reconciliation(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
