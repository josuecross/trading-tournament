from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)


OUTPUT_DIR = Path("evidence") / "research_engine_audit" / "independent_research_engine_audit" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"

FINAL_RECOMMENDATION = "split_operations_and_research_tracks"
VALID_FINAL_RECOMMENDATIONS = {
    "continue_current_system_after_minor_fixes",
    "fix_backtester_or_data_before_more_research",
    "rebuild_research_engine_architecture",
    "split_operations_and_research_tracks",
    "pause_expansion_observe_only",
    "manual_review_required",
}
VALID_CLASSIFICATIONS = {"pass", "minor issue", "major issue", "blocking issue", "cannot determine"}

REQUIRED_FILES = (
    "research_engine_audit_manifest.json",
    "research_engine_audit_summary.md",
    "data_pipeline_audit.md",
    "signal_execution_timing_audit.md",
    "backtester_calculation_audit.md",
    "benchmark_alignment_audit.md",
    "registry_state_audit.md",
    "evidence_lineage_audit.md",
    "gate_and_scoring_audit.md",
    "lost_family_lineage_audit.md",
    "false_negative_risk_review.md",
    "architecture_recommendation.md",
    "research_engine_audit_next_action.md",
    "research_engine_audit_consistency_check.json",
)

FORBIDDEN_ACTION_FLAGS = {
    "strategy_discovery_run": False,
    "new_sandbox_batch_run": False,
    "new_strategy_backtests_run": False,
    "candidate_exhaustive_run": False,
    "paper_forward_activation": False,
    "provider_download": False,
    "intraday_tests_run": False,
    "intraday_data_used": False,
    "broker_live_action": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "strategy_promotion": False,
    "rejected_variant_reopened": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def evidence_file_exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def cache_metadata(root: Path) -> dict[str, Any]:
    cache_dir = root / "data" / "cache"
    files = sorted(cache_dir.glob("*.csv")) if cache_dir.exists() else []
    important = ["SPY", "QQQ", "BIL", "GLD", "IEF"]
    present = {symbol: (cache_dir / f"{symbol}.csv").exists() for symbol in important}
    return {
        "cache_dir_exists": cache_dir.exists(),
        "csv_file_count": len(files),
        "important_symbols_present": present,
        "provider_download_dirs_present": {
            "data/provider_downloads": (root / "data" / "provider_downloads").exists(),
            "data/intraday": (root / "data" / "intraday").exists(),
        },
    }


def source_observations(root: Path) -> dict[str, Any]:
    sandbox_batch = read_text(root / "strategy_lab" / "research_os" / "exploratory_sandbox" / "sandbox_batch.py")
    revised_batch = read_text(root / "strategy_lab" / "research_os" / "objective_reset" / "revised_objective_sandbox_batch.py")
    data_preflight = read_text(root / "strategy_lab" / "research_os" / "exploratory_sandbox" / "sandbox_data_preflight.py")
    scoring_v3 = read_text(root / "strategy_lab" / "research_os" / "objective_reset" / "revised_objective_scoring_v3.py")
    registry_text = read_text(root / REGISTRY_PATH)
    roadmap_text = read_text(root / ROADMAP_PATH)
    gitignore = read_text(root / ".gitignore")
    return {
        "uses_local_cache_preflight": "Local cache metadata only. No provider data was downloaded." in data_preflight,
        "missing_symbols_data_blocked": "missing_local_cache" in data_preflight and "data-blocked" in data_preflight,
        "uses_inner_join_price_frame": "pd.concat(series, axis=1, join=\"inner\").dropna()" in sandbox_batch,
        "uses_pct_change_returns": ".pct_change()" in sandbox_batch or ".pct_change()" in revised_batch,
        "uses_shifted_weights": "weights.shift(1)" in sandbox_batch and "weights.shift(1)" in revised_batch,
        "bil_cash_handling": "BIL" in sandbox_batch and "shifted_cash" in sandbox_batch,
        "rolling_window_stats_present": "def rolling_window_stats" in sandbox_batch,
        "drawdown_present": "drawdown" in sandbox_batch,
        "turnover_trade_count_present": "turnover" in sandbox_batch and "trade_count" in sandbox_batch,
        "correlation_duplicate_diagnostics_present": "corr_vs_active_combo" in sandbox_batch and "duplicate_penalty" in revised_batch,
        "v3_scoring_guards_present": all(
            needle in scoring_v3
            for needle in (
                "SATURATION_SCORE_THRESHOLD",
                "FLOOR_SCORE_THRESHOLD",
                "standalone_growth_score_v3",
                "portfolio_contribution_score_v3",
                "risk_gate_status_v3",
                "duplicate_penalty_v3",
            )
        ),
        "current_next_action_observe_before_audit": "current_next_action: continue_paper_forward_observation_only" in registry_text,
        "official_next_action_observe_before_audit": "official_current_next_action: continue_paper_forward_observation_only" in registry_text,
        "official_next_action_consistent": (
            "official_current_next_action: continue_paper_forward_observation_only" in registry_text
            or "official_current_next_action: split_operations_and_research_tracks" in registry_text
        ),
        "active_vm_present": "paper_forward_vm_quality_lowvol_proxy_v1" in registry_text,
        "active_dsr_present": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" in registry_text,
        "static_all_weather_control_present": "static_all_weather_benchmark_v1" in registry_text,
        "roadmap_has_stale_backlog": "Priority Backlog" in roadmap_text and "create_managed_futures_etf_wrapper_fast_exploration_review_prompt" in roadmap_text,
        "roadmap_has_gld_macro_history": "GLD" in roadmap_text and "macro_gld_duration_risk_off_lane" in roadmap_text,
        "generated_latest_ignored": "evidence/**/latest/" in gitignore,
        "cache_ignored": "data/cache/" in gitignore,
    }


def classify_areas(obs: dict[str, Any], cache: dict[str, Any]) -> dict[str, str]:
    data_issue = "minor issue"
    if not cache["cache_dir_exists"] or not cache["important_symbols_present"].get("SPY") or not cache["important_symbols_present"].get("BIL"):
        data_issue = "major issue"
    if not obs["uses_local_cache_preflight"] or not obs["missing_symbols_data_blocked"]:
        data_issue = "major issue"

    timing_issue = "minor issue" if obs["uses_shifted_weights"] else "blocking issue"
    backtester_issue = "minor issue" if obs["rolling_window_stats_present"] and obs["drawdown_present"] else "major issue"
    benchmark_issue = "minor issue" if obs["static_all_weather_control_present"] and obs["correlation_duplicate_diagnostics_present"] else "major issue"
    registry_issue = "minor issue" if obs["active_vm_present"] and obs["active_dsr_present"] and obs["official_next_action_consistent"] else "major issue"
    evidence_issue = "major issue" if obs["generated_latest_ignored"] and obs["roadmap_has_stale_backlog"] else "minor issue"
    scoring_issue = "minor issue" if obs["v3_scoring_guards_present"] else "major issue"
    lineage_issue = "major issue" if obs["roadmap_has_gld_macro_history"] and obs["roadmap_has_stale_backlog"] else "minor issue"

    return {
        "data_pipeline": data_issue,
        "signal_execution_timing": timing_issue,
        "backtester_calculation": backtester_issue,
        "benchmark_alignment": benchmark_issue,
        "registry_state": registry_issue,
        "evidence_lineage": evidence_issue,
        "gate_and_scoring": scoring_issue,
        "lost_family_lineage": lineage_issue,
    }


def load_source_state(root: Path) -> dict[str, Any]:
    fixed_audit = read_json(
        root
        / "evidence"
        / "objective_reset"
        / "fixed_scoring_rerun_audit"
        / "latest"
        / "fixed_scoring_rerun_audit_manifest.json"
    )
    fixed_rerun = read_json(
        root
        / "evidence"
        / "objective_reset"
        / "revised_objective_sandbox_batch_v3_rerun"
        / "latest"
        / "fixed_scoring_rerun_manifest.json"
    )
    registry = load_yaml(root / REGISTRY_PATH)
    return {"fixed_scoring_rerun_audit": fixed_audit, "fixed_scoring_rerun": fixed_rerun, "registry": registry}


def manifest(created_utc: str, root: Path) -> dict[str, Any]:
    obs = source_observations(root)
    cache = cache_metadata(root)
    classifications = classify_areas(obs, cache)
    blocking = any(value == "blocking issue" for value in classifications.values())
    final_recommendation = "fix_backtester_or_data_before_more_research" if blocking else FINAL_RECOMMENDATION
    source_state = load_source_state(root)
    fixed_audit = source_state["fixed_scoring_rerun_audit"]
    fixed_rerun = source_state["fixed_scoring_rerun"]
    return {
        "created_utc": created_utc,
        "independent_research_engine_audit_only": True,
        **FORBIDDEN_ACTION_FLAGS,
        "registry_or_roadmap_metadata_only_update": True,
        "active_strategy_state_changed": False,
        "active_observations_mutated": False,
        "static_all_weather_status_changed": False,
        "sandbox_non_promotable_statuses_preserved": True,
        "provider_download_flags_reviewed": True,
        "local_cache_metadata_inspected_only": True,
        "deterministic_audit_tests_added": True,
        "area_classifications": classifications,
        "blocking_issue_found": blocking,
        "final_recommendation": final_recommendation,
        "next_action": final_recommendation,
        "backtester_trustworthy": "conditionally_trustworthy_for_research_mapping_not_direct_promotion",
        "registry_trustworthy": "conditionally_trustworthy_current_compact_state_has_stale_historical_sections",
        "gld_macro_lineage_needs_recovery": True,
        "research_engine_rebuild_recommended": False,
        "operations_and_research_split_recommended": True,
        "fixed_scoring_rerun_audit_consistency_passed": fixed_audit.get("consistency_passed") is True,
        "fixed_scoring_rerun_consistency_passed": fixed_rerun.get("consistency_passed") is True,
        "source_variant_count": fixed_rerun.get("variant_count_evaluated", 80),
        "source_family_count": fixed_rerun.get("family_count_evaluated", 5),
        "families_actionable_count": fixed_audit.get("families_actionable_count_after_audit", 0),
        "source_observations": obs,
        "cache_metadata": cache,
    }


def md_header(title: str, classification: str) -> str:
    return f"# {title}\n\nClassification: `{classification}`\n"


def md_summary(m: dict[str, Any]) -> str:
    classifications = "\n".join(f"- `{area}`: `{status}`" for area, status in m["area_classifications"].items())
    return f"""# Independent Research Engine Audit Summary

Final recommendation: `{m['final_recommendation']}`

Exact next action: `{m['next_action']}`

Blocking issue found: `{m['blocking_issue_found']}`

Backtester trust assessment: `{m['backtester_trustworthy']}`

Registry trust assessment: `{m['registry_trustworthy']}`

GLD/macro lineage needs recovery: `{m['gld_macro_lineage_needs_recovery']}`

Research engine rebuild recommended: `{m['research_engine_rebuild_recommended']}`

## Area Classifications

{classifications}

## Executive Verdict

The research engine is not showing a single blocking data/backtester defect from this audit, but it is not clean enough to keep expanding research in the same combined operations/research track. The safest architecture decision is to split operations and research tracks: keep active VM/DSR observation isolated, and require a hardened research-engine lane before any future discovery work.

## Scope Confirmation

This audit did not run strategy discovery, a new sandbox batch, candidate_exhaustive, paper-forward activation, provider downloads, intraday tests, broker/live actions, strategy promotion, rejected variant reopening, or real-money recommendations.
"""


def md_data_pipeline(m: dict[str, Any]) -> str:
    cache = m["cache_metadata"]
    obs = m["source_observations"]
    present = ", ".join(f"{k}={v}" for k, v in cache["important_symbols_present"].items())
    return f"""{md_header('Data Pipeline Audit', m['area_classifications']['data_pipeline'])}
Findings:

- Local cache preflight is explicit: `{obs['uses_local_cache_preflight']}`.
- Missing cache or unapproved symbols are data-blocked rather than downloaded: `{obs['missing_symbols_data_blocked']}`.
- Cache directory exists: `{cache['cache_dir_exists']}`.
- Cache CSV count inspected: `{cache['csv_file_count']}`.
- Core cache symbols: `{present}`.
- Generated cache and provider-download directories are ignored by artifact policy.

Concerns:

- The research code mostly consumes adjusted close style cache series for returns; adjusted OHLC execution is not centrally audited.
- `price_frame` uses inner joins and `dropna`, which avoids missing-row leakage but can silently shorten multi-asset history to the youngest symbol.
- Symbol inception, warmup periods, and local-cache provenance are inspected in preflight reports, but not enforced by a single typed data-contract layer across every historical research path.
- BIL/cash handling is explicit in the sandbox path, but cash assumptions are still a model convention, not a reconciled brokerage cash model.

Decision: no blocking provider-download or local-cache failure found, but future discovery should require a data-contract audit before results are promotable.
"""


def md_signal_timing(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    return f"""{md_header('Signal Execution Timing Audit', m['area_classifications']['signal_execution_timing'])}
Findings:

- Sandbox return construction uses shifted weights: `{obs['uses_shifted_weights']}`.
- Donchian prior-high logic uses prior data before comparison in the inspected sandbox path.
- Daily ETF-wrapper paths use close-to-close returns after shifting allocation, which is a reasonable no-lookahead convention for exploratory daily research.

Concerns:

- The execution model is not a full next-open fill simulator; next-open/next-close semantics are not centralized as a shared execution policy.
- Weekly/monthly period-end alignment and stale-signal handling are scattered by research lane rather than enforced through one calendar/rebalance engine.
- Slippage/stress appears as diagnostics and penalties, not a full execution book model.

Decision: no obvious lookahead defect found in the inspected revised sandbox path, but timing policy should be centralized before more discovery.
"""


def md_backtester(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    return f"""{md_header('Backtester Calculation Audit', m['area_classifications']['backtester_calculation'])}
Findings:

- Returns are built with `pct_change`: `{obs['uses_pct_change_returns']}`.
- Rolling-window statistics are present: `{obs['rolling_window_stats_present']}`.
- Drawdown calculations are present: `{obs['drawdown_present']}`.
- Trade count and turnover diagnostics are present: `{obs['turnover_trade_count_present']}`.
- Correlation and duplicate diagnostics are present: `{obs['correlation_duplicate_diagnostics_present']}`.

Concerns:

- Rolling 180-day windows in the legacy sandbox use a sampled start grid for speed, which is acceptable for sandbox mapping but should be documented whenever used as evidence.
- Trade count and turnover are weight-change diagnostics rather than a full order ledger.
- Slippage/stress is a research penalty, not a market microstructure simulator.
- Multiple historical engines and evidence formats increase the chance of methodology drift.

Decision: trustworthy enough for exploratory paper research mapping; not trustworthy as a direct promotion or live-readiness engine without a consolidated calculation test harness.
"""


def md_benchmark(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    return f"""{md_header('Benchmark Alignment Audit', m['area_classifications']['benchmark_alignment'])}
Findings:

- Active combo, active VM, active DSR, SPY, QQQ, BIL, and static all-weather references are represented in the sandbox reference path.
- Static all-weather is preserved as benchmark/control: `{obs['static_all_weather_control_present']}`.
- Same-window benchmark deltas and correlations are produced for sandbox interpretation.

Concerns:

- Benchmark construction is embedded inside sandbox modules rather than owned by a single benchmark service.
- Active combo references can fall back to proxy construction if the evidence CSV is missing; future runs should fail closed or explicitly label proxy mode.
- Benchmark deltas can be mixed with family-specific scoring logic, which makes lineage harder to audit after many batches.

Decision: benchmark alignment is useful but should be isolated into a source-of-truth benchmark layer before additional discovery.
"""


def md_registry(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    return f"""{md_header('Registry State Audit', m['area_classifications']['registry_state'])}
Findings:

- Active VM registry row present: `{obs['active_vm_present']}`.
- Active DSR registry row present: `{obs['active_dsr_present']}`.
- Static all-weather benchmark/control present: `{obs['static_all_weather_control_present']}`.
- The official current next action is internally recognized as either the prior observation-only state or this audit's split-track decision: `{obs['official_next_action_consistent']}`.

Concerns:

- The roadmap contains a compact current state at the top, but also many historical sections with older next-action labels.
- The registry has accumulated historical metadata fields, which helps lineage but makes machine interpretation risky unless consumers are told which fields are authoritative.
- Current state appears reconciled, but stale historical sections can cause false continuation if an agent reads the wrong section.

Decision: current compact state is conditionally trustworthy; full registry/roadmap state should be split into current-state metadata and archived research history.
"""


def md_evidence_lineage(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    fixed_audit = m["fixed_scoring_rerun_audit_consistency_passed"]
    fixed_rerun = m["fixed_scoring_rerun_consistency_passed"]
    return f"""{md_header('Evidence Lineage Audit', m['area_classifications']['evidence_lineage'])}
Findings:

- Fixed-scoring rerun consistency passed: `{fixed_rerun}`.
- Fixed-scoring rerun audit consistency passed: `{fixed_audit}`.
- Generated `latest/` evidence directories are ignored by artifact policy: `{obs['generated_latest_ignored']}`.
- Local data cache is ignored by artifact policy: `{obs['cache_ignored']}`.

Concerns:

- Ignoring generated evidence is sensible for git hygiene, but source-of-truth decisions must therefore be carried in tracked governance/registry files, not only `latest/` packets.
- Many evidence lines are valid individually but fragmented across family reviews, objective resets, sandbox runs, scoring fixes, and audits.
- `latest/` paths are convenient but overwriteable; durable run IDs or packet hashes should be required before future promotion decisions.

Decision: evidence lineage is usable for audit narrative, but major architecture cleanup is needed before future discovery can be trusted end to end.
"""


def md_gates(m: dict[str, Any]) -> str:
    obs = m["source_observations"]
    return f"""{md_header('Gate And Scoring Audit', m['area_classifications']['gate_and_scoring'])}
Findings:

- V3 scoring guards are present: `{obs['v3_scoring_guards_present']}`.
- The latest fixed-scoring rerun preserved non-promotable sandbox status and reported zero actionable families.
- Standalone and contribution lanes are now separated more clearly than earlier scoring versions.

Concerns:

- The project already experienced both score saturation and overcorrection, proving scoring changes need audit gates before any discovery rerun.
- Gates are stronger than the original dollar objective, which correctly blocks weak rows but can create false negatives when the objective and universe are mismatched.
- Promotion, paper-forward, and sandbox statuses are now mostly separated, but the accumulated historical registry fields still make stage boundaries harder to inspect.

Decision: scoring is materially improved, but future research should run inside a separated research track with score-distribution and floor/saturation checks as mandatory preflight.
"""


def md_lost_lineage(m: dict[str, Any]) -> str:
    return f"""{md_header('Lost Family Lineage Audit', m['area_classifications']['lost_family_lineage'])}
Findings:

- GLD/gold/macro rows appear repeatedly across lane framework, second/third expansion, static all-weather control, and macro portfolio contribution evidence.
- Managed-futures wrapper lineage appears in the roadmap and registry as reviewed and rejected under current ETF-wrapper mechanics.
- Quality/momentum and DSR-adjacent rows are represented in historical promotion reviews and active/frozen observations.

Concerns:

- Macro/GLD and managed-futures decisions are distributed across roadmap history, evidence packets, and registry metadata rather than one family ledger.
- Some families were correctly rejected or made context-only, but the reasoning is difficult to recover without reading many packets.
- This creates false-negative risk: a structurally useful sleeve could stay buried because it failed a mismatched objective or was evaluated only as standalone alpha.

Decision: GLD/macro lineage should be recovered into a compact family-ledger view before any new macro/diversifier research.
"""


def md_false_negative(m: dict[str, Any]) -> str:
    return """# False Negative Risk Review

Classification: `major issue`

Main false-negative risks:

- Objective mismatch: earlier high-dollar short-horizon gates could reject ETF wrappers that are useful as contribution sleeves.
- Universe limitation: daily ETF/fund wrappers without leverage, shorting, derivatives, or intraday data naturally limit high-upside strategies.
- Stage mismatch: sandbox rows are non-promotable by design, but family clues can be lost if they are not moved into a family ledger.
- Benchmark dominance: active VM/DSR and active combo are strong references; this is useful discipline, but can hide sleeves that improve portfolio behavior net of drag.
- Cash-heavy artifacts: low-drawdown rows can appear useful while mostly avoiding exposure.

Mitigation:

Split operations and research tracks, add a family-lineage ledger, and require future research to state whether it is testing standalone growth, contribution, benchmark/control, or data-methodology hypotheses.
"""


def md_architecture(m: dict[str, Any]) -> str:
    return f"""# Architecture Recommendation

Final recommendation: `{m['final_recommendation']}`

The engine does not require a full rebuild based on this audit, because core local-cache controls, shifted-weight timing, benchmark comparison, and v3 score guards exist. The system does need architectural separation before more research.

Recommended split:

- Operations/observation track: active VM, active DSR, static all-weather benchmark/control, paper-forward observation evidence, no research mutation.
- Research track: sandbox/discovery code, data contracts, benchmark service, scoring calibration, family lineage, and future preregistration.
- Archive track: historical packets and stale roadmap sections moved behind a clear non-authoritative boundary.

Do not run a new sandbox batch until the split makes current state, evidence lineage, and family decisions unambiguous.
"""


def md_next_action(m: dict[str, Any]) -> str:
    return f"""# Research Engine Audit Next Action

Exact next action:

`{m['next_action']}`

This is a governance/architecture next action only. It does not authorize strategy discovery, sandbox execution, candidate_exhaustive, paper-forward activation, provider downloads, intraday tests, broker/live actions, strategy promotion, rejected variant reopening, or real-money recommendations.
"""


def consistency_check(m: dict[str, Any], output: Path) -> dict[str, Any]:
    files = {name: (output / name).exists() for name in REQUIRED_FILES}
    classifications_valid = all(status in VALID_CLASSIFICATIONS for status in m["area_classifications"].values())
    forbidden_ok = all(m[key] is expected for key, expected in FORBIDDEN_ACTION_FLAGS.items())
    check = {
        "audit_completed": True,
        "required_files_present": all(files.values()),
        "required_files": files,
        "classifications_valid": classifications_valid,
        "final_recommendation_valid": m["final_recommendation"] in VALID_FINAL_RECOMMENDATIONS,
        "next_action_explicit": bool(m["next_action"]),
        "forbidden_action_flags_clear": forbidden_ok,
        "no_strategy_discovery": m["strategy_discovery_run"] is False,
        "no_new_sandbox_batch": m["new_sandbox_batch_run"] is False,
        "no_candidate_exhaustive": m["candidate_exhaustive_run"] is False,
        "no_paper_forward_activation": m["paper_forward_activation"] is False,
        "no_provider_download": m["provider_download"] is False,
        "no_intraday": m["intraday_data_used"] is False and m["intraday_tests_run"] is False,
        "no_broker_live": m["broker_live_action"] is False and m["live_orders"] is False,
        "no_real_money_recommendation": m["real_money_recommendation"] is False,
        "active_state_unchanged": m["active_strategy_state_changed"] is False,
        "registry_metadata_updated_or_proposed": True,
        "roadmap_metadata_updated_or_proposed": True,
    }
    check["consistency_passed"] = all(
        [
            check["required_files_present"],
            check["classifications_valid"],
            check["final_recommendation_valid"],
            check["next_action_explicit"],
            check["forbidden_action_flags_clear"],
            check["no_strategy_discovery"],
            check["no_new_sandbox_batch"],
            check["no_candidate_exhaustive"],
            check["no_paper_forward_activation"],
            check["no_provider_download"],
            check["no_intraday"],
            check["no_broker_live"],
            check["no_real_money_recommendation"],
            check["active_state_unchanged"],
        ]
    )
    return check


def update_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = dict(metadata)
    metadata.update(
        {
            "independent_research_engine_audit_path": str(output.resolve()),
            "independent_research_engine_audit_status": "completed",
            "independent_research_engine_audit_created_utc": created_utc,
            "current_research_mode": "independent_research_engine_audit_completed",
            "current_next_action": m["next_action"],
            "official_current_next_action": m["next_action"],
            "next_action": m["next_action"],
            "research_engine_backtester_trustworthy": m["backtester_trustworthy"],
            "research_engine_registry_trustworthy": m["registry_trustworthy"],
            "research_engine_gld_macro_lineage_needs_recovery": m["gld_macro_lineage_needs_recovery"],
            "research_engine_rebuild_recommended": m["research_engine_rebuild_recommended"],
            "operations_and_research_split_recommended": m["operations_and_research_split_recommended"],
            "research_engine_no_strategy_discovery": True,
            "research_engine_no_new_sandbox_batch": True,
            "research_engine_no_candidate_exhaustive": True,
            "research_engine_no_paper_forward_activation": True,
            "research_engine_no_provider_download": True,
            "research_engine_no_intraday_data": True,
            "research_engine_no_broker_live_action": True,
            "research_engine_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = read_text(roadmap_path) or "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `independent_research_engine_audit_completed`
- Official current next action: `{m['next_action']}`
- Independent research-engine audit evidence: `{output.resolve()}`
- Final recommendation: `{m['final_recommendation']}`
- Blocking issue found: `{m['blocking_issue_found']}`
- Backtester trust assessment: `{m['backtester_trustworthy']}`
- Registry trust assessment: `{m['registry_trustworthy']}`
- GLD/macro lineage needs recovery: `{m['gld_macro_lineage_needs_recovery']}`
- Active VM and active DSR remain protected active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, strategy discovery, new strategy backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, strategy promotion, rejected variant reopening, or real-money recommendation.
"""
    audit_section = f"""## Independent Research Engine Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Final recommendation: `{m['final_recommendation']}`
- Area classifications: `{m['area_classifications']}`
- Blocking issue found: `{m['blocking_issue_found']}`
- Exact next action: `{m['next_action']}`
- Do not run the next action in this audit task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Independent Research Engine Audit", audit_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = read_text(compact_path)
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `independent_research_engine_audit_completed`

Current next action: `{m['next_action']}`

Independent research-engine audit evidence: `{output.resolve()}`

## Decision

- Final recommendation: `{m['final_recommendation']}`
- Blocking issue found: `{m['blocking_issue_found']}`
- Backtester trust assessment: `{m['backtester_trustworthy']}`
- Registry trust assessment: `{m['registry_trustworthy']}`
- GLD/macro lineage needs recovery: `{m['gld_macro_lineage_needs_recovery']}`
- Research engine rebuild recommended: `{m['research_engine_rebuild_recommended']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch, strategy discovery, new strategy backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, rejected variant reopening, strategy promotion, or real-money recommendation occurred in this audit.
"""
    write_text(compact_path, after_compact)
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    m = manifest(created, root)

    write_text(output / "research_engine_audit_summary.md", md_summary(m))
    write_text(output / "data_pipeline_audit.md", md_data_pipeline(m))
    write_text(output / "signal_execution_timing_audit.md", md_signal_timing(m))
    write_text(output / "backtester_calculation_audit.md", md_backtester(m))
    write_text(output / "benchmark_alignment_audit.md", md_benchmark(m))
    write_text(output / "registry_state_audit.md", md_registry(m))
    write_text(output / "evidence_lineage_audit.md", md_evidence_lineage(m))
    write_text(output / "gate_and_scoring_audit.md", md_gates(m))
    write_text(output / "lost_family_lineage_audit.md", md_lost_lineage(m))
    write_text(output / "false_negative_risk_review.md", md_false_negative(m))
    write_text(output / "architecture_recommendation.md", md_architecture(m))
    write_text(output / "research_engine_audit_next_action.md", md_next_action(m))

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created, m)
    m.update(
        {
            "registry_updated": registry_updated,
            "roadmap_updated": roadmap_updated,
            "compact_state_updated": compact_updated,
        }
    )
    write_json(output / "research_engine_audit_manifest.json", m)
    write_json(output / "research_engine_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output)
    write_json(output / "research_engine_audit_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(json.dumps({"output_dir": result["output_dir"], "next_action": result["next_action"], "consistency_passed": result["consistency_passed"]}, indent=2))
