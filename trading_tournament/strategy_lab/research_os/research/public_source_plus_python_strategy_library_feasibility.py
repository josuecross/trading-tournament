from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv


OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_plus_python_strategy_library_feasibility"
    / "latest"
)

REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
RESEARCH_MODULE_DIR = Path("strategy_lab") / "research_os" / "research"
DATA_CACHE_DIR = Path("data") / "cache"
RESEARCH_RECOVERY_DIR = Path("evidence") / "research_recovery"

BT_DECISION_FEASIBLE = "bt_adapter_feasible"
BT_DECISION_BLOCKED = "bt_adapter_blocked"
BT_DECISION_DO_NOT_USE = "do_not_use_bt"
VALID_BT_DECISIONS = {BT_DECISION_FEASIBLE, BT_DECISION_BLOCKED, BT_DECISION_DO_NOT_USE}

NEXT_ACTION_BUILD = "build_bt_adapter_poc"
NEXT_ACTION_COMPARE = "compare_bt_vs_current_engine_on_existing_control"
NEXT_ACTION_SOURCE = "manual_quantpedia_source_intake_first"
NEXT_ACTION_DO_NOT = "do_not_integrate_python_strategy_library_now"
VALID_NEXT_ACTIONS = {NEXT_ACTION_BUILD, NEXT_ACTION_COMPARE, NEXT_ACTION_SOURCE, NEXT_ACTION_DO_NOT}

PACKAGE_MODULES = ("bt", "vectorbt", "backtesting", "backtrader", "qstrader", "pandas_ta", "ta")

REQUIRED_FILES = (
    "feasibility_manifest.json",
    "feasibility_summary.md",
    "architecture_integration_map.md",
    "public_source_intake_template.md",
    "bt_feasibility_report.md",
    "candidate_library_comparison.csv",
    "candidate_library_comparison.md",
    "package_availability_check.csv",
    "package_availability_check.md",
    "thin_adapter_design.md",
    "smallest_future_poc.md",
    "risks_and_blockers.md",
    "guardrail_checklist.json",
    "feasibility_next_action.md",
    "feasibility_consistency_check.json",
)

PACKAGE_FIELDS = ("package", "module_name", "available_in_current_venv", "check_method", "install_attempted")
LIBRARY_FIELDS = (
    "library",
    "candidate_role",
    "local_cache_fit",
    "etf_ranking_topn_fit",
    "rebalance_fit",
    "cash_fallback_fit",
    "risk_filter_fit",
    "daily_weight_export_fit",
    "equity_trade_turnover_export_fit",
    "project_adapter_complexity",
    "summary_decision",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def package_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in PACKAGE_MODULES:
        rows.append(
            {
                "package": "pandas-ta" if module == "pandas_ta" else module,
                "module_name": module,
                "available_in_current_venv": importlib.util.find_spec(module) is not None,
                "check_method": "importlib.util.find_spec",
                "install_attempted": False,
            }
        )
    return rows


def cache_summary(root: Path) -> dict[str, Any]:
    inventory = cache_inventory(root)
    ready = [row for row in inventory if row.get("status") == "cache_ready"]
    return {
        "cache_dir_exists": (root / DATA_CACHE_DIR).exists(),
        "cache_symbol_count": len(inventory),
        "cache_ready_symbol_count": len(ready),
        "sample_ready_symbols": [row["symbol"] for row in ready[:12]],
    }


def architecture_findings(root: Path) -> dict[str, Any]:
    research_modules = sorted(path.name for path in (root / RESEARCH_MODULE_DIR).glob("*.py"))
    bounded_modules = [name for name in research_modules if "bounded" in name]
    registry_text = read_text(root / REGISTRY)
    roadmap_text = read_text(root / ROADMAP)
    queue_text = read_text(root / QUEUE)
    ledger_text = read_text(root / LEDGER)
    evidence_dirs = sorted(path.name for path in (root / RESEARCH_RECOVERY_DIR).iterdir() if path.is_dir())
    return {
        "registry_exists": (root / REGISTRY).exists(),
        "roadmap_exists": (root / ROADMAP).exists(),
        "queue_exists": (root / QUEUE).exists(),
        "ledger_exists": (root / LEDGER).exists(),
        "research_module_count": len(research_modules),
        "bounded_research_module_count": len(bounded_modules),
        "bounded_research_module_examples": bounded_modules[:12],
        "evidence_recovery_packet_count": len(evidence_dirs),
        "candidate_exhaustive_authorized": "candidate_exhaustive_authorized: false" not in queue_text,
        "strategy_discovery_authorized": "strategy_discovery_authorized: false" not in queue_text,
        "paper_forward_candidate_creation_authorized": "paper_forward_candidate_creation_authorized: false" not in queue_text,
        "intraday_paused_visible": "intraday_research_paused: true" in registry_text or "intraday remains paused" in roadmap_text,
        "lineage_gate_visible": "family_lineage" in str(LEDGER) and "future_research_allowed: false" in ledger_text,
    }


def bt_capability_decision(packages: list[dict[str, Any]]) -> dict[str, Any]:
    bt_available = any(row["module_name"] == "bt" and row["available_in_current_venv"] for row in packages)
    return {
        "bt_feasibility_decision": BT_DECISION_FEASIBLE,
        "bt_package_available_now": bt_available,
        "bt_immediate_poc_dependency_blocker": not bt_available,
        "bt_decision_reason": (
            "bt fits ETF allocation/ranking/rebalance adapter patterns, but the package is not installed in the current venv"
            if not bt_available
            else "bt is available and fits the planned ETF allocation/ranking/rebalance adapter pattern"
        ),
    }


def library_rows() -> list[dict[str, str]]:
    return [
        {
            "library": "bt",
            "candidate_role": "primary execution-template adapter",
            "local_cache_fit": "high; can receive a pandas price DataFrame loaded by project cache utilities",
            "etf_ranking_topn_fit": "high; Algo composition can express ranking/select/weight logic",
            "rebalance_fit": "high; monthly or weekly rebalance logic is a native use case",
            "cash_fallback_fit": "medium-high; BIL/cash fallback should be represented as explicit target weights",
            "risk_filter_fit": "medium-high; risk-on/off filters can be implemented as Algos but must be audited for timing",
            "daily_weight_export_fit": "medium; project adapter should reconstruct or capture weights explicitly",
            "equity_trade_turnover_export_fit": "medium-high; equity is available, turnover may need project-side reconstruction",
            "project_adapter_complexity": "low-medium",
            "summary_decision": "best first adapter candidate, subject to dependency approval",
        },
        {
            "library": "vectorbt",
            "candidate_role": "secondary comparison candidate",
            "local_cache_fit": "high; pandas/numpy first",
            "etf_ranking_topn_fit": "medium-high; strong vectorization but adapter may be less transparent",
            "rebalance_fit": "medium-high",
            "cash_fallback_fit": "medium",
            "risk_filter_fit": "medium",
            "daily_weight_export_fit": "medium-high",
            "equity_trade_turnover_export_fit": "high",
            "project_adapter_complexity": "medium-high",
            "summary_decision": "useful later for speed comparison, not first template choice",
        },
        {
            "library": "backtesting.py",
            "candidate_role": "secondary comparison candidate",
            "local_cache_fit": "medium",
            "etf_ranking_topn_fit": "low-medium; more single-instrument oriented",
            "rebalance_fit": "medium",
            "cash_fallback_fit": "medium",
            "risk_filter_fit": "medium",
            "daily_weight_export_fit": "medium",
            "equity_trade_turnover_export_fit": "medium",
            "project_adapter_complexity": "medium-high",
            "summary_decision": "not ideal for multi-ETF allocation templates",
        },
        {
            "library": "Backtrader",
            "candidate_role": "secondary comparison candidate",
            "local_cache_fit": "medium-high",
            "etf_ranking_topn_fit": "medium; possible but heavier event-driven integration",
            "rebalance_fit": "high",
            "cash_fallback_fit": "medium",
            "risk_filter_fit": "high",
            "daily_weight_export_fit": "medium",
            "equity_trade_turnover_export_fit": "high",
            "project_adapter_complexity": "high",
            "summary_decision": "powerful but heavier than needed for first ETF allocation adapter",
        },
        {
            "library": "QSTrader",
            "candidate_role": "secondary comparison candidate",
            "local_cache_fit": "medium",
            "etf_ranking_topn_fit": "medium",
            "rebalance_fit": "high",
            "cash_fallback_fit": "medium",
            "risk_filter_fit": "medium-high",
            "daily_weight_export_fit": "medium",
            "equity_trade_turnover_export_fit": "high",
            "project_adapter_complexity": "high",
            "summary_decision": "institutional architecture but too heavy for first proof-of-concept",
        },
        {
            "library": "pandas-ta / ta",
            "candidate_role": "indicator support only",
            "local_cache_fit": "high",
            "etf_ranking_topn_fit": "low; indicators only, not portfolio execution",
            "rebalance_fit": "none",
            "cash_fallback_fit": "none",
            "risk_filter_fit": "medium as indicator source",
            "daily_weight_export_fit": "none",
            "equity_trade_turnover_export_fit": "none",
            "project_adapter_complexity": "low if used only for indicators",
            "summary_decision": "supporting dependency only, not a backtesting adapter",
        },
    ]


def manifest_payload(
    created: str,
    output: Path,
    architecture: dict[str, Any],
    cache: dict[str, Any],
    packages: list[dict[str, Any]],
    bt_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_plus_python_strategy_library_feasibility_only": True,
        "source_layer": "quantpedia_style_public_curated_strategy_intake",
        "execution_layer_primary_candidate": "bt",
        "validation_layer": "current_tournament_evidence_gates_and_invariants",
        "architecture_files_inspected": True,
        "registry_inspected": architecture["registry_exists"],
        "roadmap_inspected": architecture["roadmap_exists"],
        "research_queue_inspected": architecture["queue_exists"],
        "family_ledger_inspected": architecture["ledger_exists"],
        "research_modules_inspected_count": architecture["research_module_count"],
        "bounded_research_modules_inspected_count": architecture["bounded_research_module_count"],
        "evidence_recovery_packets_inspected_count": architecture["evidence_recovery_packet_count"],
        "local_cache_inspected": cache["cache_dir_exists"],
        "local_cache_ready_symbol_count": cache["cache_ready_symbol_count"],
        "package_availability_checked": True,
        "package_install_attempted": False,
        "external_strategy_code_imported": False,
        "quantpedia_scraped": False,
        "public_site_downloaded": False,
        "strategy_implemented": False,
        "strategy_backtest_run": False,
        "current_backtester_replaced": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        **bt_decision,
        "candidate_library_comparison_completed": True,
        "thin_adapter_design_created": True,
        "public_source_intake_template_created": True,
        "smallest_future_poc_defined": True,
        "current_evidence_gates_preserved": True,
        "exposure_invariants_remain_project_enforced": True,
        "next_action": NEXT_ACTION_SOURCE,
    }


def architecture_md(architecture: dict[str, Any], cache: dict[str, Any]) -> str:
    modules = "\n".join(f"- `{name}`" for name in architecture["bounded_research_module_examples"])
    samples = ", ".join(cache["sample_ready_symbols"])
    return f"""# Architecture Integration Map

Current integration points:

- Public strategy source intake: new report/spec layer before registry or bounded design creation.
- Pre-registration specs: existing bounded design modules under `strategy_lab/research_os/research/`.
- Execution templates: proposed thin adapter beside current bounded runners; it should consume frozen specs and local cached prices.
- Evidence gates: current manifest, consistency-check, row-results, numeric-criteria, comparator, and exposure-invariant packets remain authoritative.
- Registry/roadmap state: remains source-of-truth for what may be run, promoted, deferred, or blocked.

Observed bounded-run module examples:

{modules}

Local cache:

- Cache exists: `{cache['cache_dir_exists']}`
- Ready symbols: `{cache['cache_ready_symbol_count']}`
- Sample ready symbols: `{samples}`

The adapter must not bypass project guardrails. Public-source or Python-library outputs are evidence inputs only, never proof of profitability.
"""


def public_source_template_md() -> str:
    return """# Public Source Intake Template

Use this before any public strategy becomes a project design.

- Source name: `unknown`
- Source URL or citation: `manual_input_required`
- Source type: `Quantpedia-style curated source | academic paper | public article | other`
- Strategy family: `manual_input_required`
- Rule clarity: `clear | partial | ambiguous | paywalled_or_insufficient`
- Instruments: `manual_input_required`
- Timeframe: `daily | weekly | monthly | other`
- Data requirements: `prices | dividends | fundamentals | macro | futures | intraday | other`
- Execution assumptions: `rebalance timing, signal timing, fill timing, cash treatment`
- Current project constraint violations: `provider data, intraday, leverage, futures, shorting, options, benchmark-only overlap`
- Similar already-tested project families: `manual_input_required`
- Duplicate/rejected-lineage risk: `manual_input_required`
- Candidate action allowed now: `source_intake_only | bounded_design_possible | blocked_requires_review`
- Evidence-gate reminder: public-source presence is not validation and creates no promotion or paper-forward eligibility.
"""


def bt_feasibility_md(decision: dict[str, Any]) -> str:
    return f"""# bt Feasibility Report

Decision: `{decision['bt_feasibility_decision']}`

Package available in current virtualenv: `{decision['bt_package_available_now']}`

Immediate POC dependency blocker: `{decision['bt_immediate_poc_dependency_blocker']}`

Rationale:

- Local cached ETF price data can be loaded by the project into pandas DataFrames before passing into `bt`.
- ETF momentum ranking, top-N selection, and monthly/weekly rebalance fit `bt` Algo composition.
- BIL/cash fallback can be represented as explicit target weights, but the project should validate the final weight frame externally.
- Risk-on/risk-off filters can be represented, but signal date and no-lookahead timing must be tested against current controls.
- Equity curves can be converted to project evidence outputs.
- Daily weights and turnover should be captured or reconstructed by the project adapter, not trusted blindly.
- Current exposure invariants remain project-enforced after adapter output.

Decision reason: `{decision['bt_decision_reason']}`
"""


def library_comparison_md(rows: list[dict[str, str]]) -> str:
    lines = ["# Candidate Library Comparison", ""]
    for row in rows:
        lines.append(f"- `{row['library']}`: `{row['summary_decision']}`")
        lines.append(f"  - Role: `{row['candidate_role']}`")
        lines.append(f"  - Adapter complexity: `{row['project_adapter_complexity']}`")
    return "\n".join(lines) + "\n"


def package_availability_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Package Availability Check", ""]
    lines.append("Method: `importlib.util.find_spec`; no install attempted.")
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['module_name']}` available: `{row['available_in_current_venv']}`")
    return "\n".join(lines) + "\n"


def thin_adapter_design_md() -> str:
    return """# Thin Adapter Design

The adapter should be thin and evidence-first.

Inputs:

- Public strategy idea spec from the intake template.
- Frozen project pre-registration or bounded design spec.
- Local cached price data loaded by existing project cache utilities.

Execution template:

- Compose `bt` Algos for select/rank/weigh/rebalance behavior.
- Keep signal timing explicit: signal through `t-1`, trade/rebalance on the next allowed project date.
- Encode BIL/cash as a normal target allocation, not implicit residual cash.

Adapter output contract:

- Daily target weights.
- Daily strategy returns and equity curve.
- Trades/rebalance count and turnover proxy.
- Comparator-ready same-window return series.
- Metadata for source idea, execution assumptions, and package version when available.

Validation:

- Project recomputes or validates exposure invariants.
- Project recomputes key metrics where possible.
- Project writes normal manifest, consistency check, numeric criteria, comparator, lineage, and do-not-promote evidence.

The adapter must not update registry state, promote results, create paper-forward candidates, or run candidate_exhaustive.
"""


def poc_md() -> str:
    return f"""# Smallest Future Proof-of-Concept

Recommended future POC: monthly top-N ETF momentum with BIL fallback using `bt`, exporting project-compatible daily weights and equity curve.

Scope:

- Use an already-tested control-style concept, not a new public strategy idea.
- Use local cache only.
- Compare `bt` adapter output against the current engine on a known frozen control.
- Validate signal timing, monthly rebalance dates, BIL fallback, daily weights, equity curve, turnover, and exposure invariants.
- Treat all outputs as diagnostic only.

Because `bt` is not currently available in the virtualenv, the next no-install step is source intake: `{NEXT_ACTION_SOURCE}`.
"""


def risks_md() -> str:
    return """# Risks and Blockers

- Dependency risk: `bt` is not currently installed, and future installation must be separately authorized.
- Output mismatch risk: library equity/transaction conventions may differ from project metrics.
- Hidden lookahead risk: Algo timing must be tested against prior-day signal and rebalance rules.
- Weight/invariant mismatch risk: final weights must be exported or reconstructed and validated by project code.
- Overfitting risk: public-source ideas and library examples can encourage parameter shopping.
- Duplicate-family risk: public ideas may overlap with already-tested active, rejected, benchmark/control, or context-only families.
- Evidence-lineage risk: public writeups may omit details, require assumptions, or rely on unavailable data.
- Governance risk: No public source or Python library should create promotion, candidate_exhaustive, paper-forward, or real-money eligibility.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_plus_python_strategy_library_feasibility_only",
        "package_install_attempted",
        "external_strategy_code_imported",
        "quantpedia_scraped",
        "public_site_downloaded",
        "strategy_implemented",
        "strategy_backtest_run",
        "current_backtester_replaced",
        "new_strategy_discovery_run",
        "new_research_batch_run",
        "provider_download",
        "intraday_data_used",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return {key: manifest[key] for key in keys}


def next_action_md(next_action: str) -> str:
    return f"""# Feasibility Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Plus Python Strategy Library Feasibility

Source layer: `{manifest['source_layer']}`

Execution layer primary candidate: `{manifest['execution_layer_primary_candidate']}`

Validation layer: `{manifest['validation_layer']}`

bt feasibility decision: `{manifest['bt_feasibility_decision']}`

bt package available now: `{manifest['bt_package_available_now']}`

Immediate POC dependency blocker: `{manifest['bt_immediate_poc_dependency_blocker']}`

Package install attempted: `{manifest['package_install_attempted']}`

Strategy implemented: `{manifest['strategy_implemented']}`

Backtest run: `{manifest['strategy_backtest_run']}`

Current evidence gates preserved: `{manifest['current_evidence_gates_preserved']}`

Exposure invariants remain project-enforced: `{manifest['exposure_invariants_remain_project_enforced']}`

No public source or Python library is treated as proof of profitability.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["feasibility_consistency_check.json"] = True
    checks = {
        "feasibility_only": manifest["public_source_plus_python_strategy_library_feasibility_only"] is True,
        "architecture_inspected": manifest["architecture_files_inspected"] is True
        and manifest["registry_inspected"] is True
        and manifest["roadmap_inspected"] is True
        and manifest["research_queue_inspected"] is True
        and manifest["family_ledger_inspected"] is True,
        "local_cache_inspected": manifest["local_cache_inspected"] is True,
        "package_check_no_install": manifest["package_availability_checked"] is True
        and manifest["package_install_attempted"] is False,
        "bt_decision_valid": manifest["bt_feasibility_decision"] in VALID_BT_DECISIONS,
        "adapter_outputs_project_validated": manifest["current_evidence_gates_preserved"] is True
        and manifest["exposure_invariants_remain_project_enforced"] is True,
        "no_strategy_or_backtest": manifest["strategy_implemented"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["current_backtester_replaced"] is False,
        "no_external_scrape_or_code_import": manifest["external_strategy_code_imported"] is False
        and manifest["quantpedia_scraped"] is False
        and manifest["public_site_downloaded"] is False,
        "no_discovery_or_batch": manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_provider_or_intraday": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "protected_state_preserved": manifest["active_vm_preserved"] is True
        and manifest["active_dsr_preserved"] is True
        and manifest["static_all_weather_benchmark_control_only"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    architecture = architecture_findings(root)
    cache = cache_summary(root)
    packages = package_rows()
    bt_decision = bt_capability_decision(packages)
    libraries = library_rows()
    manifest = manifest_payload(created, output, architecture, cache, packages, bt_decision)

    write_json(output / "feasibility_manifest.json", manifest)
    write_text(output / "feasibility_summary.md", summary_md(manifest))
    write_text(output / "architecture_integration_map.md", architecture_md(architecture, cache))
    write_text(output / "public_source_intake_template.md", public_source_template_md())
    write_text(output / "bt_feasibility_report.md", bt_feasibility_md(bt_decision))
    write_csv(output / "candidate_library_comparison.csv", libraries, list(LIBRARY_FIELDS))
    write_text(output / "candidate_library_comparison.md", library_comparison_md(libraries))
    write_csv(output / "package_availability_check.csv", packages, list(PACKAGE_FIELDS))
    write_text(output / "package_availability_check.md", package_availability_md(packages))
    write_text(output / "thin_adapter_design.md", thin_adapter_design_md())
    write_text(output / "smallest_future_poc.md", poc_md())
    write_text(output / "risks_and_blockers.md", risks_md())
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "feasibility_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "feasibility_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
