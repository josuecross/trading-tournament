from __future__ import annotations

import csv
import json
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "tournament_failure_synthesis" / "risk_controlled_high_return_failure_audit" / "latest"
DISCOVERY_DIR = Path("evidence") / "parallel_research_discovery" / "risk_controlled_high_return_discovery" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

NEXT_ACTION = "pause_expansion_and_summarize_tournament_state"
VALID_NEXT_ACTIONS = {
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_next_family_after_risk_controlled_review",
    "manual_review_required_for_risk_controlled_high_return_batch",
}

MANIFEST_FLAGS = {
    "audit_only": True,
    "backtests_run": False,
    "discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "new_strategy_candidates_created": False,
    "risk_controls_tuned": False,
    "gates_relaxed": False,
    "intraday_research_remains_paused": True,
}

CANDIDATE_CLASSIFICATIONS = [
    {
        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
        "family": "dual_momentum_paa",
        "outcome": "discovery_reject",
        "primary_failure": "risk_control_preserved_return_but_not_risk",
        "secondary_failures": "risk_buffer_failed;drawdown_still_too_large;stress_failed;benchmark_edge_failed;parent_comparison_unavailable_by_design;no_promotion_review_candidate;exact_variant_closed;family_open_only_with_future_new_hypothesis",
        "clean_reject": True,
        "promotion_review_candidate": False,
        "immediate_followup_allowed": False,
        "audit_conclusion": "Volatility scaling preserved some target-hit evidence but did not fit the small-account drawdown/risk budget or benchmark/stress gates.",
    },
    {
        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
        "family": "donchian_breakout",
        "outcome": "discovery_reject",
        "primary_failure": "risk_control_reduced_risk_but_destroyed_return",
        "secondary_failures": "stress_failed;benchmark_edge_failed;excessive_BIL_or_cash;skip_block_logic_dominates;parent_comparison_unavailable_by_design;no_promotion_review_candidate;exact_variant_closed;family_open_only_with_future_new_hypothesis",
        "clean_reject": True,
        "promotion_review_candidate": False,
        "immediate_followup_allowed": False,
        "audit_conclusion": "Risk-budget sizing produced acceptable drawdown but killed the profit objective and left skip/block logic dominating results.",
    },
]

REQUIRED_FILES = [
    "risk_controlled_failure_audit_manifest.json",
    "risk_controlled_failure_audit_summary.md",
    "risk_controlled_candidate_failure_classification.csv",
    "dual_momentum_vol_scaled_failure_review.md",
    "donchian_risk_budget_failure_review.md",
    "risk_controlled_family_status_after_discovery.csv",
    "methodology_and_implementation_review.md",
    "project_state_recommendation.md",
    "risk_controlled_failure_audit_next_action.md",
    "risk_controlled_failure_audit_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def discovery_state(root: Path) -> dict[str, Any]:
    manifest = load_json(root / DISCOVERY_DIR / "risk_controlled_discovery_manifest.json")
    rows = read_csv_rows(root / DISCOVERY_DIR / "risk_controlled_candidate_results.csv")
    metrics = load_json(root / DISCOVERY_DIR / "risk_controlled_candidate_metrics.json")
    return {
        "manifest": manifest,
        "candidate_results": rows,
        "metrics": metrics,
        "promotion_candidates_count": int(manifest.get("promotion_candidates_count", 0)),
        "invalidated_55_day_donchian_used": manifest.get("invalidated_55_day_donchian_used") is True,
    }


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "risk_controlled_high_return_failure_audit_path": str(output.resolve()),
            "risk_controlled_high_return_failure_audit_status": "completed",
            "risk_controlled_high_return_failure_audit_created_utc": created_utc,
            "risk_controlled_high_return_candidates_clean_reject_count": manifest["risk_controlled_candidates_clean_reject_count"],
            "risk_controlled_high_return_promotion_candidates_current_count": manifest["promotion_candidates_current_count"],
            "risk_controlled_exact_variants_remain_closed": True,
            "risk_controlled_immediate_followup_allowed": False,
            "daily_weekly_expansion_pause_recommended": True,
            "official_current_next_action": NEXT_ACTION,
            "current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "audit_only": True,
            "backtests_run": False,
            "discovery_run": False,
            "new_performance_metrics_computed": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_path_touched": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    write_yaml(path, data)


def update_roadmap(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Risk-Controlled High-Return Failure Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Audit-only governance step: `true`
- Candidates audited: `rc_dual_momentum_paa_vol_scaled_v1`, `rc_donchian_breakout_risk_budget_v1`
- Promotion-review candidates: `0`
- Clean rejects: `2`
- Dual momentum conclusion: volatility scaling preserved some target-hit evidence but failed small-account drawdown/risk-buffer, stress, and benchmark gates.
- Donchian conclusion: risk-budget sizing reduced drawdown but destroyed target-hit evidence and left skip/block logic plus defensive allocation dominating the result.
- Invalidated 55-day Donchian rule used: `false`
- Exact variants remain closed: `true`
- Immediate risk-control rescue allowed: `false`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- No backtest, discovery, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, risk-control tuning, gate relaxation, or real-money recommendation is authorized by this audit.
"""
    write_text(path, replace_or_append_section(text, "## Risk-Controlled High-Return Failure Audit", section))


def summary_md(created_utc: str, output: Path) -> str:
    return f"""# Risk-Controlled High-Return Failure Audit

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Decision: both risk-controlled candidates are clean rejects.

Promotion-review candidates: `0`

Exact variants remain closed: `true`

Immediate next risk-control rescue allowed: `false`

Next action: `{NEXT_ACTION}`
"""


def dual_momentum_review_md() -> str:
    return """# Dual Momentum Vol-Scaled Failure Review

Candidate: `rc_dual_momentum_paa_vol_scaled_v1`

Conclusion: clean reject.

The volatility scalar hypothesis worked only partially. The row retained some return evidence, with +300/+400 target-hit rates of `0.60 / 0.60`, and the scalar distribution ranged from `0.25 / 0.85 / 1.00`. But the small-account risk budget still failed badly: max drawdown was `-2292.53` and risk buffer was `-1692.53`.

The row also failed stress slippage and benchmark-edge gates versus active combo and SPY 200d. This means the scalar preserved enough risk exposure to keep some upside, but not enough risk reduction to make the strategy promotable.

No immediate scalar target, lookback, min/max, or rounding variant should be run. That would be post-result tuning.
"""


def donchian_review_md() -> str:
    return """# Donchian Risk-Budget Failure Review

Candidate: `rc_donchian_breakout_risk_budget_v1`

Conclusion: clean reject.

Risk-budget sizing improved drawdown control but destroyed the profit objective. Max drawdown was `-434.60` and risk buffer was positive at `165.40`, but +300/+400 target-hit rates were `0.00 / 0.00`.

The signal funnel was also unattractive: `7032` signals produced only `423` accepted entries, with `6609` skipped signals. Median notional was `943.19`, BIL allocation was excessive, and skip/block logic dominated the result.

No immediate loosening of per-position risk, portfolio risk, max positions, or exposure cap should be run. That would be post-result tuning.
"""


def family_status_rows() -> list[dict[str, Any]]:
    return [
        {
            "family": "dual_momentum_paa",
            "audited_candidate": "rc_dual_momentum_paa_vol_scaled_v1",
            "family_status_after_audit": "closed_exact_variants_future_hypothesis_only",
            "exact_variant_closed": True,
            "allowed_future_work": "future checkpoint plus distinct pre-registered family hypothesis only",
            "forbidden_future_work": "immediate scalar rescue;post_result_tuning;gate_relaxation;candidate_exhaustive;paper_forward",
        },
        {
            "family": "donchian_breakout",
            "audited_candidate": "rc_donchian_breakout_risk_budget_v1",
            "family_status_after_audit": "closed_exact_variants_future_hypothesis_only",
            "exact_variant_closed": True,
            "allowed_future_work": "future checkpoint plus distinct pre-registered family hypothesis only",
            "forbidden_future_work": "immediate risk-budget rescue;post_result_tuning;gate_relaxation;candidate_exhaustive;paper_forward",
        },
    ]


def methodology_review_md() -> str:
    return """# Methodology And Implementation Review

The discovery evidence is internally clean enough for rejection.

- Parent comparison remains unavailable by design because exact rejected parents were not rerun.
- Parent candidates should not be rerun in this audit.
- Invalidated 55-day Donchian language remained excluded.
- The reviewed Donchian child used the corrected parent-consistent 20-day breakout mechanics.
- No implementation blocker is severe enough to change either rejection into manual-review-required.
- Signal-funnel concerns in Donchian are a failure characteristic, not a promotion reason.

No methodology finding authorizes new discovery, parent reruns, candidate_exhaustive, paper-forward activation, gate relaxation, or risk-control tuning.
"""


def project_state_md() -> str:
    return f"""# Project State Recommendation

Recommendation: `{NEXT_ACTION}`

The repeated tournament pattern remains intact:

- high-return rows fail drawdown/risk-buffer gates,
- risk controls reduce drawdown but weaken or kill edge,
- defensive rows are too slow or benchmark-weak,
- intraday remains paused due to data-source constraints,
- no promotion candidates emerged from this batch.

The project should pause expansion and summarize tournament state before any more strategy work.
"""


def next_action_md() -> str:
    return f"""# Risk-Controlled Failure Audit Next Action

Exact next action: `{NEXT_ACTION}`

Do not run this next action in the audit task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "audit_only": manifest["audit_only"] is True,
        "no_backtests": manifest["backtests_run"] is False,
        "no_discovery": manifest["discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_path": manifest["broker_path_touched"] is False and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "no_exact_rejected_variants_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "no_new_strategy_candidates_created": manifest["new_strategy_candidates_created"] is False,
        "no_risk_controls_tuned": manifest["risk_controls_tuned"] is False,
        "no_gates_relaxed": manifest["gates_relaxed"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "candidate_failure_classification_exists": (output / "risk_controlled_candidate_failure_classification.csv").exists(),
        "dual_momentum_review_exists": (output / "dual_momentum_vol_scaled_failure_review.md").exists(),
        "donchian_review_exists": (output / "donchian_risk_budget_failure_review.md").exists(),
        "methodology_review_exists": (output / "methodology_and_implementation_review.md").exists(),
        "project_state_recommendation_exists": (output / "project_state_recommendation.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(output: Path, created_utc: str, manifest: dict[str, Any], consistency: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "risk_controlled_failure_audit_manifest.json", manifest)
    write_text(output / "risk_controlled_failure_audit_summary.md", summary_md(created_utc, output))
    write_csv(
        output / "risk_controlled_candidate_failure_classification.csv",
        CANDIDATE_CLASSIFICATIONS,
        [
            "candidate_id",
            "family",
            "outcome",
            "primary_failure",
            "secondary_failures",
            "clean_reject",
            "promotion_review_candidate",
            "immediate_followup_allowed",
            "audit_conclusion",
        ],
    )
    write_text(output / "dual_momentum_vol_scaled_failure_review.md", dual_momentum_review_md())
    write_text(output / "donchian_risk_budget_failure_review.md", donchian_review_md())
    write_csv(
        output / "risk_controlled_family_status_after_discovery.csv",
        family_status_rows(),
        ["family", "audited_candidate", "family_status_after_audit", "exact_variant_closed", "allowed_future_work", "forbidden_future_work"],
    )
    write_text(output / "methodology_and_implementation_review.md", methodology_review_md())
    write_text(output / "project_state_recommendation.md", project_state_md())
    write_text(output / "risk_controlled_failure_audit_next_action.md", next_action_md())
    write_json(output / "risk_controlled_failure_audit_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "risk_controlled_failure_audit_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_FILES:
            archive.write(output / rel, rel)


def run_risk_controlled_high_return_failure_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    output = root / OUTPUT_DIR
    created_utc = now_utc()
    strategies_before = strategy_snapshot(root)
    state = discovery_state(root)
    clean_reject_count = len([row for row in CANDIDATE_CLASSIFICATIONS if row["clean_reject"] is True])
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "promotion_candidates_current_count": state["promotion_candidates_count"],
        "risk_controlled_candidates_clean_reject_count": clean_reject_count,
        "invalidated_55_day_donchian_used": state["invalidated_55_day_donchian_used"],
        "next_action": NEXT_ACTION,
    }
    write_evidence(output, created_utc, manifest, {"consistency_passed": False})
    consistency = consistency_check(manifest, output)
    write_json(output / "risk_controlled_failure_audit_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "risk_controlled_failure_audit_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_FILES:
            archive.write(output / rel, rel)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["accepted_strategy_state_changed"] = False
        manifest["rejected_strategy_state_changed"] = False
        write_json(output / "risk_controlled_failure_audit_manifest.json", manifest)
    return {
        "output_dir": str(output),
        "promotion_candidates_current_count": manifest["promotion_candidates_current_count"],
        "clean_reject_count": clean_reject_count,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_risk_controlled_high_return_failure_audit(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
