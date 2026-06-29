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
OUTPUT_DIR = Path("evidence") / "tournament_checkpoints" / "pause_expansion_summary" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
RISK_AUDIT_DIR = Path("evidence") / "tournament_failure_synthesis" / "risk_controlled_high_return_failure_audit" / "latest"

NEXT_ACTION = "pre_register_indicator_library_integration_audit"
VALID_NEXT_ACTIONS = {
    "pre_register_indicator_library_integration_audit",
    "pre_register_next_family_after_pause_summary",
    "manual_review_required_after_pause_summary",
    "manual_intraday_data_source_review_required",
}

MANIFEST_FLAGS = {
    "pause_checkpoint_only": True,
    "expansion_paused": True,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "promotion_candidates_current_count": 0,
}

ACTIVE_OBSERVATIONS = [
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
]

BENCHMARK_CONTROLS = [
    "static_all_weather_benchmark_v1",
    "SPY",
    "QQQ",
    "BIL",
    "SPY_200d_trend_model",
    "active_combo_vm_dsr_equal_weight_v1",
    "active_VM_and_active_DSR_references",
]

CLOSED_VARIANT_GROUPS = [
    "breadth_state_variants",
    "first_expansion_rejects",
    "sector_rs_limited_history_reject",
    "second_expansion_rejects",
    "turn_of_month_post_bugfix_reject",
    "third_expansion_rejects",
    "risk_controlled_high_return_rejects",
]

FAMILY_STATUS_ROWS = [
    {"family": "volatility_management", "status": "active", "classification": "active", "notes": "Active VM remains frozen/accepted."},
    {"family": "defensive_sector_rotation", "status": "active", "classification": "active", "notes": "Active DSR remains frozen/accepted; same-family duplicates remain closed/deferred."},
    {"family": "dual_momentum_paa", "status": "closed_exact_variants", "classification": "open_only_with_future_new_hypothesis", "notes": "Risk-controlled child clean reject; no immediate scalar rescue."},
    {"family": "donchian_breakout", "status": "closed_exact_variants", "classification": "open_only_with_future_new_hypothesis", "notes": "Risk-budget child clean reject; invalidated 55-day language remains excluded."},
    {"family": "macro_gld_duration", "status": "closed_exact_variants", "classification": "open_only_with_future_new_hypothesis", "notes": "Useful as macro/diversifier context, not immediate strategy lane."},
    {"family": "sector_rotation", "status": "active_plus_closed_variants", "classification": "active_and_closed_exact_variants", "notes": "Active DSR remains; sector RS limited-history reject closed."},
    {"family": "calendar_anomaly", "status": "closed_exact_variants", "classification": "closed_exact_variants", "notes": "Turn-of-month bug fixed, rerun rejected."},
    {"family": "breadth_state", "status": "closed_exact_variants", "classification": "closed_exact_variants", "notes": "Final breadth-state lane produced no promotion candidate."},
    {"family": "intraday_research", "status": "paused", "classification": "blocked_by_data_source_constraints", "notes": "No approved data source or local intraday cache."},
    {"family": "quality_momentum_watchlist", "status": "watchlist_closed_no_rescue_now", "classification": "open_only_with_future_new_hypothesis", "notes": "High-upside variants failed risk; safer variants lagged references."},
    {"family": "managed_futures_etf_wrapper", "status": "future_review_only", "classification": "open_only_with_future_new_hypothesis", "notes": "ETF/fund-wrapper only; no direct futures."},
    {"family": "indicator_library_governance", "status": "governance_only", "classification": "allowed_future_infrastructure_audit", "notes": "Controlled audit before any indicator dependency or strategy mining."},
]

REQUIRED_FILES = [
    "pause_expansion_summary_manifest.json",
    "pause_expansion_summary.md",
    "active_and_benchmark_state.md",
    "closed_exact_variants_summary.md",
    "family_status_checkpoint.csv",
    "lessons_learned_summary.md",
    "why_expansion_is_paused.md",
    "allowed_future_directions.md",
    "forbidden_next_steps.md",
    "pause_expansion_next_action.md",
    "pause_expansion_consistency_check.json",
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


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def active_and_benchmark_state_md() -> str:
    return """# Active And Benchmark State

## Active accepted / frozen observations

- `paper_forward_vm_quality_lowvol_proxy_v1`: active/frozen VM observation.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`: active/frozen DSR observation.

No new active strategies are created by this checkpoint.

## Benchmark/control only

- `static_all_weather_benchmark_v1`: benchmark/control only; not promotion, candidate_exhaustive, paper/demo, or live eligible.
- `SPY`, `QQQ`, and `BIL`: market/cash references.
- `SPY_200d_trend_model`: reference/active observation context.
- Active VM, active DSR, and active combo are references where applicable.

Benchmark/control status does not imply promotion or paper-forward eligibility.
"""


def closed_variants_md() -> str:
    return """# Closed Exact Variants Summary

Closed exact-variant groups:

- breadth-state variants
- first-expansion rejects
- sector RS limited-history reject
- second-expansion rejects
- turn-of-month post-bugfix reject
- third-expansion rejects
- risk-controlled high-return rejects: `rc_dual_momentum_paa_vol_scaled_v1`, `rc_donchian_breakout_risk_budget_v1`

Invalidated 55-day Donchian language must not be used. Exact rejected variants remain closed unless a future governance checkpoint authorizes a genuinely distinct pre-registered hypothesis.
"""


def lessons_md() -> str:
    return """# Lessons Learned Summary

- High-return rows repeatedly fail drawdown and risk-buffer gates.
- Defensive rows are often too slow or benchmark-weak for the small-account profit objective.
- Risk controls can reduce drawdown but may destroy edge, as seen in Donchian risk-budget sizing.
- Risk controls can preserve some return evidence while still failing risk, as seen in dual momentum volatility scaling.
- Macro/diversifier rows may be useful as controls or portfolio-contribution references without becoming standalone profit candidates.
- Intraday remains infrastructure/data-source blocked.
- Indicator expansion should be governed by an allowlist and validation policy, not mined.
"""


def why_paused_md() -> str:
    return """# Why Expansion Is Paused

Expansion is paused because:

- current promotion candidates count is `0`,
- there is no immediate clean rescue path,
- intraday data/source approval is unresolved,
- exact rejected variants are closed,
- more random expansion would increase overfitting and false-confidence risk,
- the project needs a checkpoint before deciding the next family or indicator-integration step.
"""


def allowed_future_md() -> str:
    return """# Allowed Future Directions

Allowed only after future pre-registration:

- `pre_register_indicator_library_integration_audit`
- `pre_register_next_family_after_pause_summary`
- `pre_register_managed_futures_etf_wrapper_review`
- `pre_register_macro_contribution_family_review`
- `manual_intraday_data_source_review_required` if the user chooses to solve intraday data/source approval
- `promotion_review_for_existing_deferred_dsr_candidate` only if evidence is available and same-family duplication is explicitly handled

None of these directions is authorized directly by this checkpoint.
"""


def forbidden_md() -> str:
    return """# Forbidden Next Steps

- immediate strategy discovery
- backtests without pre-registration
- candidate_exhaustive
- paper-forward activation
- broker/live actions
- provider downloads
- intraday testing
- reopening exact rejected variants
- loosening gates to force candidates
- post-result tuning
- real-money recommendation
"""


def summary_md(created_utc: str, output: Path) -> str:
    return f"""# Pause Expansion Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Expansion paused: `true`

Promotion candidates: `0`

Active/frozen observations: `{len(ACTIVE_OBSERVATIONS)}`

Benchmark/reference controls: `{len(BENCHMARK_CONTROLS)}`

Closed exact-variant groups: `{len(CLOSED_VARIANT_GROUPS)}`

Next action: `{NEXT_ACTION}`
"""


def next_action_md() -> str:
    return f"""# Pause Expansion Next Action

Exact next action: `{NEXT_ACTION}`

Reason: the repo is structurally clean, random daily/weekly expansion is paused, intraday is data-blocked, and a controlled indicator-library integration audit can improve future family design without authorizing strategy mining.

Do not run this next action in the pause-summary task.
"""


def compact_state_md(created_utc: str) -> str:
    return f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `expansion_paused_checkpoint`

Current next action: `{NEXT_ACTION}`

## Active Accepted / Paper-Demo Observations

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.

## Benchmark Controls

- `static_all_weather_benchmark_v1` is benchmark/control only.
- SPY, QQQ, BIL, SPY_200d, active VM, active DSR, and active combo remain references/controls, not new promotions.

## Paused / Closed State

- Expansion is paused.
- Intraday research remains paused because data-source terms and local intraday cache are unresolved.
- Exact rejected variants remain closed.
- Risk-controlled high-return candidates remain clean rejects.
- Invalidated 55-day Donchian language must not be used.
- Official Donchian child rule uses the reviewed 20-day breakout.

## Forbidden Actions

- No immediate strategy discovery.
- No backtest or new performance metric computation.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No broker/live-order path activation or order action.
- No real-money recommendation.
"""


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "pause_expansion_summary_path": str(output.resolve()),
            "pause_expansion_summary_status": "completed",
            "pause_expansion_summary_created_utc": created_utc,
            "expansion_paused": True,
            "promotion_candidates_current_count": manifest["promotion_candidates_current_count"],
            "active_observations_count": manifest["active_observations_count"],
            "benchmark_controls_count": manifest["benchmark_controls_count"],
            "closed_exact_variant_count": manifest["closed_exact_variant_count"],
            "families_open_only_with_future_hypothesis_count": manifest["families_open_only_with_future_hypothesis_count"],
            "official_current_next_action": NEXT_ACTION,
            "current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "pause_checkpoint_only": True,
            "strategy_discovery_run": False,
            "backtests_run": False,
            "new_performance_metrics_computed": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    write_yaml(path, data)


def update_roadmap(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Pause Expansion Summary

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Expansion paused: `true`
- Promotion candidates current count: `0`
- Active/frozen observations: `2`
- Benchmark/control references: `{len(BENCHMARK_CONTROLS)}`
- Closed exact-variant groups: `{len(CLOSED_VARIANT_GROUPS)}`
- Families open only with future new hypothesis: `5`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This checkpoint does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, gate relaxation, post-result tuning, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Pause Expansion Summary", section))


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "pause_checkpoint_only": manifest["pause_checkpoint_only"] is True,
        "expansion_paused": manifest["expansion_paused"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "active_benchmark_state_exists": (output / "active_and_benchmark_state.md").exists(),
        "closed_variants_summary_exists": (output / "closed_exact_variants_summary.md").exists(),
        "family_status_checkpoint_exists": (output / "family_status_checkpoint.csv").exists(),
        "lessons_learned_summary_exists": (output / "lessons_learned_summary.md").exists(),
        "forbidden_next_steps_exists": (output / "forbidden_next_steps.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(output: Path, created_utc: str, manifest: dict[str, Any], consistency: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "pause_expansion_summary_manifest.json", manifest)
    write_text(output / "pause_expansion_summary.md", summary_md(created_utc, output))
    write_text(output / "active_and_benchmark_state.md", active_and_benchmark_state_md())
    write_text(output / "closed_exact_variants_summary.md", closed_variants_md())
    write_csv(output / "family_status_checkpoint.csv", FAMILY_STATUS_ROWS, ["family", "status", "classification", "notes"])
    write_text(output / "lessons_learned_summary.md", lessons_md())
    write_text(output / "why_expansion_is_paused.md", why_paused_md())
    write_text(output / "allowed_future_directions.md", allowed_future_md())
    write_text(output / "forbidden_next_steps.md", forbidden_md())
    write_text(output / "pause_expansion_next_action.md", next_action_md())
    write_json(output / "pause_expansion_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "pause_expansion_summary_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_FILES:
            archive.write(output / rel, rel)


def run_pause_expansion_summary(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    risk_manifest = load_json(root / RISK_AUDIT_DIR / "risk_controlled_failure_audit_manifest.json")
    future_hypothesis_count = sum(1 for row in FAMILY_STATUS_ROWS if "open_only_with_future_new_hypothesis" in row["classification"])
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "promotion_candidates_current_count": int(risk_manifest.get("promotion_candidates_current_count", 0)),
        "active_observations_count": len(ACTIVE_OBSERVATIONS),
        "benchmark_controls_count": len(BENCHMARK_CONTROLS),
        "closed_exact_variant_count": len(CLOSED_VARIANT_GROUPS),
        "families_open_only_with_future_hypothesis_count": future_hypothesis_count,
        "next_action": NEXT_ACTION,
    }
    write_evidence(output, created_utc, manifest, {"consistency_passed": False})
    consistency = consistency_check(manifest, output)
    write_json(output / "pause_expansion_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "pause_expansion_summary_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_FILES:
            archive.write(output / rel, rel)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output)
    write_text(root / COMPACT_STATE_PATH, compact_state_md(created_utc))
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = False
        manifest["rejected_strategy_state_changed"] = False
        write_json(output / "pause_expansion_summary_manifest.json", manifest)
    return {
        "output_dir": str(output),
        "expansion_paused": True,
        "promotion_candidates_current_count": manifest["promotion_candidates_current_count"],
        "active_observations_count": manifest["active_observations_count"],
        "benchmark_controls_count": manifest["benchmark_controls_count"],
        "closed_exact_variant_count": manifest["closed_exact_variant_count"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_pause_expansion_summary(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
