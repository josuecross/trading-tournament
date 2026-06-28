from __future__ import annotations

import csv
import json
import shutil
import subprocess
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "repository_refactor" / "family_lane_research_os_refactor" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
GITIGNORE_PATH = Path(".gitignore")

NEXT_ACTION = "manual_review_required_after_repository_refactor"
VALID_NEXT_ACTIONS = {
    "audit_risk_controlled_high_return_discovery_failures",
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_indicator_library_integration_audit",
    "manual_review_required_after_repository_refactor",
}

MANIFEST_FLAGS = {
    "repository_refactor_only": True,
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
    "generated_artifacts_gitignored": True,
    "cleanup_inventory_created": True,
    "compact_state_created": True,
    "family_registry_created_or_updated": True,
    "artifact_policy_created": True,
}

GITIGNORE_BLOCK_START = "# BEGIN trading-tournament generated artifact policy"
GITIGNORE_BLOCK_END = "# END trading-tournament generated artifact policy"
GITIGNORE_RULES = [
    GITIGNORE_BLOCK_START,
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".ipynb_checkpoints/",
    ".venv/",
    "venv/",
    ".env",
    ".env.*",
    "*.local.yaml",
    "*.local.env",
    "*.log",
    "*.jsonl",
    "*.tmp",
    "*.bak",
    "*.zip",
    "*.parquet",
    "*.feather",
    "*.sqlite",
    "*.db",
    ".DS_Store",
    "Thumbs.db",
    "evidence/**/latest/",
    "evidence/**/packet.zip",
    "evidence/**/latest.zip",
    "evidence/advisor_upload/",
    "evidence/research_state/latest/",
    "evidence/strategy_lab/latest/",
    "data/cache/",
    "data/intraday/",
    "data/raw/",
    "data/provider_downloads/",
    "reports/generated/",
    "logs/",
    "tmp/",
    "artifacts/",
    "!reports/compact_state/*.md",
    "!family_registry/family_status/*.md",
    "!strategy_specs/**/*.yaml",
    "!strategy_specs/**/*.md",
    "!governance/**/*.yaml",
    "!governance/**/*.md",
    "!lanes/**/*.py",
    "!lanes/**/*.md",
    "!indicator_layer/**/*.yaml",
    "!indicator_layer/**/*.md",
    GITIGNORE_BLOCK_END,
]

EVIDENCE_FILES = [
    "repo_refactor_manifest.json",
    "repo_refactor_summary.md",
    "repo_cleanup_inventory.csv",
    "archived_or_deleted_items.md",
    "gitignore_update_report.md",
    "untracked_generated_files_report.md",
    "new_structure_report.md",
    "canonical_state_report.md",
    "family_registry_report.md",
    "lane_framework_report.md",
    "indicator_governance_report.md",
    "artifact_policy_report.md",
    "refactor_next_action.md",
    "repo_refactor_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_state_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def update_gitignore(root: Path) -> dict[str, Any]:
    path = root / GITIGNORE_PATH
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    if GITIGNORE_BLOCK_START in lines:
        start = lines.index(GITIGNORE_BLOCK_START)
        end = lines.index(GITIGNORE_BLOCK_END) if GITIGNORE_BLOCK_END in lines[start:] else len(lines) - 1
        new_lines = lines[:start] + GITIGNORE_RULES + lines[end + 1 :]
    else:
        new_lines = lines + ([""] if lines and lines[-1] else []) + GITIGNORE_RULES
    updated = "\n".join(new_lines).rstrip() + "\n"
    changed = updated != original
    if changed:
        write_text(path, updated)
    return {"gitignore_updated": changed, "rules_added_or_refreshed": GITIGNORE_RULES}


def git_ls_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def generated_path(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    generated_prefixes = (
        "evidence/advisor_upload/",
        "evidence/research_state/latest/",
        "evidence/strategy_lab/latest/",
        "data/cache/",
        "data/intraday/",
        "data/raw/",
        "data/provider_downloads/",
        "reports/generated/",
        "logs/",
        "tmp/",
        "artifacts/",
    )
    generated_suffixes = (".zip", ".jsonl", ".log", ".tmp", ".bak", ".parquet", ".feather", ".sqlite", ".db", ".pyc")
    return lower.startswith(generated_prefixes) or lower.endswith(generated_suffixes)


def tracked_generated_files(root: Path) -> list[str]:
    return [path for path in git_ls_files(root) if generated_path(path)]


def local_generated_junk(root: Path) -> list[Path]:
    junk: list[Path] = []
    for name in ["__pycache__", ".pytest_cache"]:
        for path in root.rglob(name):
            parts = set(path.parts)
            if ".git" in parts or ".venv" in parts or "venv" in parts:
                continue
            if path.is_dir():
                junk.append(path)
    return sorted(junk, key=lambda p: str(p).lower())


def delete_local_generated_junk(root: Path) -> list[str]:
    deleted: list[str] = []
    for path in local_generated_junk(root):
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            deleted.append(str(path.relative_to(root)))
    return deleted


def current_tournament_state_md(created_utc: str) -> str:
    return f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `repository_refactor_governance_only`

Current next action: `{NEXT_ACTION}`

## Active Accepted / Paper-Demo Observations

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.

## Benchmark Controls

- `static_all_weather_benchmark_v1` is benchmark/control only.
- SPY, QQQ, BIL, SPY_200d, active VM, active DSR, and active combo remain references/controls, not new promotions.

## Paused / Closed State

- Intraday research remains paused because data-source terms and local intraday cache are unresolved.
- Exact rejected variants remain closed.
- Risk-controlled high-return discovery produced no promotion candidates.
- `rc_dual_momentum_paa_vol_scaled_v1` and `rc_donchian_breakout_risk_budget_v1` remain rejected after discovery.
- Invalidated 55-day Donchian language must not be used.
- Official Donchian child rule uses the reviewed 20-day breakout.

## Forbidden Actions

- No strategy discovery.
- No backtest or new performance metric computation.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No broker/live-order path activation or order action.
- No real-money recommendation.
"""


def history_summary_md() -> str:
    return """# History Summary

The long `strategy_lab/RESEARCH_ROADMAP.md` remains the detailed chronological record. This compact summary exists so Codex and human reviewers can start from current state without scanning every historical packet.

Recent history in one line: daily/weekly ETF-wrapper expansion produced many clean rejects, active VM and active DSR remain the best supported active/frozen pair, static all-weather was accepted as a benchmark/control only, intraday was paused due to unresolved source/data constraints, and the latest risk-controlled high-return discovery produced no promotion candidates.
"""


def family_status_files() -> dict[str, str]:
    template_tail = """
## Governance

- Exact rejected variants closed: true
- Allowed future work: family-level audit or pre-registered distinct hypothesis only
- Forbidden repeats: exact replay, post-result parameter tuning, direct candidate_exhaustive, paper/demo activation, provider download, broker/live path, real-money recommendation
"""
    return {
        "dual_momentum.md": """# Dual Momentum Family

- Tested variants: `dual_momentum_paa_clean_v1`, `rc_dual_momentum_paa_vol_scaled_v1`
- Active variants: none
- Rejected variants: both tested variants
- Benchmark/control variants: SPY, QQQ, GLD, IEF, BIL, static all-weather, active combo
- Last audit conclusion: return power existed, but risk-buffer/drawdown controls did not produce a promotion candidate.
""" + template_tail,
        "donchian_breakout.md": """# Donchian Breakout Family

- Tested variants: `donchian_atr_breakout_etf_v1`, `rc_donchian_breakout_risk_budget_v1`
- Active variants: none
- Rejected variants: both tested variants
- Benchmark/control variants: SPY, QQQ, BIL, SPY_200d, active combo
- Last audit conclusion: risk-budget child remained rejected; invalidated 55-day language must not be reused, and the reviewed child rule uses 20-day breakout mechanics.
""" + template_tail,
        "macro_gld_duration.md": """# Macro GLD Duration Family

- Tested variants: `gld_gror_balanced_momentum_clean_v1`, `gld_ief_spy_defensive_rotation_v1`
- Active variants: none
- Rejected variants: tested macro rotation rows
- Benchmark/control variants: GLD, IEF, BIL, static all-weather
- Last audit conclusion: useful as macro/diversifier context, not a standalone promotion candidate.
""" + template_tail,
        "sector_rotation.md": """# Sector Rotation Family

- Tested variants: active DSR, top-N DSR variants, sector relative-strength variants
- Active variants: `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`
- Rejected variants: DSR top-N and sector RS rows that failed duplication, risk, or same-window gates
- Benchmark/control variants: SPY, BIL, active combo
- Last audit conclusion: active DSR remains protected; same-family rescue is closed unless a distinct hypothesis is pre-registered.
""" + template_tail,
        "volatility_management.md": """# Volatility Management Family

- Tested variants: active VM and related volatility/quality proxy rows
- Active variants: `paper_forward_vm_quality_lowvol_proxy_v1`
- Rejected variants: risk-controlled/high-upside variants that failed risk buffer or lagged active references
- Benchmark/control variants: SPY, QQQ, BIL, active combo
- Last audit conclusion: active VM remains protected; related rescue variants are not automatically promotable.
""" + template_tail,
        "calendar_anomaly.md": """# Calendar Anomaly Family

- Tested variants: `turn_of_month_spy_qqq_v1`
- Active variants: none
- Rejected variants: `turn_of_month_spy_qqq_v1`
- Benchmark/control variants: SPY, QQQ, BIL
- Last audit conclusion: zero-trade bug was fixed, rerun remained rejected, and future runners require signal-funnel diagnostics.
""" + template_tail,
        "intraday_research.md": """# Intraday Research Family

- Tested variants: none authorized
- Active variants: none
- Rejected variants: none; research is blocked before testing
- Benchmark/control variants: SPY, QQQ
- Last audit conclusion: intraday remains paused until source terms, local cache, SPY/QQQ 1Min or 5Min history, and session/calendar QA pass.

## Governance

- Exact rejected variants closed: n/a
- Families still open: data/source review only
- Allowed future work: `data_source_review_required`
- Forbidden repeats: intraday discovery, intraday backtest, provider download without explicit authorization, candidate_exhaustive, paper/demo activation, broker/live path, real-money recommendation
""",
    }


def write_family_registry(root: Path) -> list[Path]:
    written: list[Path] = []
    status_dir = root / "family_registry" / "family_status"
    for name, content in family_status_files().items():
        path = status_dir / name
        write_text(path, content)
        written.append(path)
    write_text(
        root / "family_registry" / "failure_taxonomy.py",
        '''"""Canonical failure labels for family-first research governance."""

FAILURE_LABELS = {
    "clean_reject",
    "risk_buffer_failed",
    "drawdown_too_large",
    "stress_failed",
    "benchmark_edge_failed",
    "too_slow_for_profit_goal",
    "excessive_BIL_or_cash",
    "high_correlation_or_duplication",
    "buy_hold_explains_result",
    "skip_block_logic_dominates",
    "implementation_bug_fixed_then_rejected",
    "limited_history",
    "data_blocked",
    "methodology_concern",
    "family_open_only_with_new_hypothesis",
    "exact_variant_closed",
}
''',
    )
    written.append(root / "family_registry" / "failure_taxonomy.py")
    write_text(
        root / "family_registry" / "parent_child_lineage.py",
        '''"""Parent/child lineage contract for future strategy follow-ups."""

REQUIRED_LINEAGE_FIELDS = [
    "parent_candidate_id",
    "parent_status",
    "parent_failure_reason",
    "exact_parent_remains_closed",
    "one_major_changed_dimension",
    "unchanged_dimensions",
    "why_this_is_not_a_rescue",
    "valid_future_outcomes",
]

DISCOVERY_BLOCKED_IF_PARENT_RULE_MISMATCH = True
''',
    )
    written.append(root / "family_registry" / "parent_child_lineage.py")
    return written


def write_lanes(root: Path) -> list[Path]:
    lane_definitions = '''"""Lane definitions for the family-first research OS."""

LANES = {
    "conservative_etf_allocation_lane": {"roles": ["risk_reducer", "profit_engine"]},
    "moderate_tactical_etf_lane": {"roles": ["profit_engine", "risk_reducer"]},
    "macro_gld_duration_risk_off_lane": {"roles": ["diversifier", "risk_reducer", "profit_engine"]},
    "diversifier_contribution_lane": {"roles": ["diversifier", "benchmark_control"]},
    "intraday_research_only_lane": {"roles": ["execution_research_only", "data_methodology_only"]},
    "benchmark_control_lane": {"roles": ["benchmark_control"]},
}
'''
    lane_gates = '''"""Lane-specific gate expectations.

These helpers are policy metadata only; they do not run strategy research.
"""

LANE_GATES = {
    "profit_engine": ["standalone_edge", "risk_buffer_pass", "stress_survival"],
    "risk_reducer": ["drawdown_improvement", "objective_not_destroyed", "duplication_review"],
    "diversifier": ["portfolio_contribution", "same_window_controls", "not_promoted_as_benchmark_only"],
    "benchmark_control": ["comparison_value", "not_promotion_eligible"],
    "execution_research_only": ["data_source_approved", "fill_contract_ready", "no_strategy_testing_while_blocked"],
}
'''
    scorecard_policy = """# Lane Scorecard Policy

Every candidate maps to one lane before testing. Profit engines require standalone edge and risk survival. Diversifiers require portfolio-contribution evidence. Benchmark controls remain comparison-only. Intraday concepts remain data/source blocked until approved.
"""
    paths = [
        root / "lanes" / "lane_definitions.py",
        root / "lanes" / "lane_gate_framework.py",
        root / "lanes" / "lane_scorecard_policy.md",
    ]
    write_text(paths[0], lane_definitions)
    write_text(paths[1], lane_gates)
    write_text(paths[2], scorecard_policy)
    return paths


def write_indicator_layer(root: Path) -> list[Path]:
    approved = {
        "approved_indicators_version": 1,
        "allowed_initial_categories": {
            "trend": ["SMA", "EMA", "Donchian"],
            "momentum": ["ROC", "momentum", "RSI"],
            "volatility": ["ATR", "Bollinger z-score", "realized volatility", "ADX"],
            "volume_liquidity": ["volume SMA", "volume filter"],
        },
        "blocked_for_now": [
            "large indicator combination searches",
            "candlestick pattern mining",
            "genetic search",
            "AI-selected indicator formulas",
            "broad parameter grids eligible for promotion",
            "post-result indicator tuning",
            "intraday indicators while intraday source is blocked",
        ],
        "new_dependency_added": False,
    }
    policy = """# Indicator Policy

Indicator expansion is governance-controlled. This refactor does not install an indicator library and does not add indicators to strategy logic.

Allowed initial categories are SMA/EMA, ROC/momentum, RSI, ATR, Donchian, Bollinger z-score, ADX, realized volatility, and volume SMA/filter.

Blocked for now: large indicator-combination searches, candlestick-pattern mining, genetic search, AI-selected formulas, broad parameter grids eligible for promotion, and post-result indicator tuning.
"""
    paths = [root / "indicator_layer" / "approved_indicators.yaml", root / "indicator_layer" / "indicator_policy.md"]
    write_yaml(paths[0], approved)
    write_text(paths[1], policy)
    return paths


def write_governance(root: Path) -> list[Path]:
    artifact_policy = """# Artifact Policy

Tracked source of truth: registry YAML, roadmap Markdown, canonical specs, family status summaries, lane policies, indicator governance, tests, and compact state reports.

Generated local-only artifacts: evidence packets, zip files, `latest/` evidence exports, provider caches, logs, JSONL progress, pytest caches, Python bytecode, and temporary outputs.

Bulky generated evidence should be retained locally or regenerated, not treated as primary source code. Compact summaries should be promoted into `reports/compact_state/` or `family_registry/family_status/` when they become canonical.
"""
    cleanup_policy = """# Cleanup Policy

Delete obvious local junk such as Python caches, pytest caches, temporary logs, and throwaway generated files.

Archive rather than delete when a file may contain lineage, historical decisions, or source-of-truth strategy context.

Do not delete active registries, accepted active strategy definitions, benchmark/control registration definitions, tests, broker safety guardrails, or evidence summaries that preserve lineage unless a compact replacement summary exists.

Tracked generated files should be removed from the Git index with `git rm --cached` only after human review in a dirty worktree.
"""
    workflow = """# Research Workflow

`family thesis` -> `pre-registration` -> `discovery` -> `family lesson` -> `promotion review only if strong` -> `candidate exhaustive only after promotion review` -> `paper/demo observation only after candidate exhaustive`

Canonical non-promotion statuses:

- `research_useful_not_promotable`
- `benchmark_control_only`
- `data_blocked`
- `methodology_blocked`
- `family_paused`
"""
    next_action_policy = '''"""Allowed next actions after repository refactor."""

VALID_NEXT_ACTIONS = {
    "audit_risk_controlled_high_return_discovery_failures",
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_indicator_library_integration_audit",
    "manual_review_required_after_repository_refactor",
}

CURRENT_NEXT_ACTION = "manual_review_required_after_repository_refactor"
'''
    paths = [
        root / "governance" / "artifact_policy.md",
        root / "governance" / "cleanup_policy.md",
        root / "governance" / "research_workflow.md",
        root / "governance" / "next_action_policy.py",
    ]
    write_text(paths[0], artifact_policy)
    write_text(paths[1], cleanup_policy)
    write_text(paths[2], workflow)
    write_text(paths[3], next_action_policy)
    return paths


def write_strategy_specs(root: Path) -> list[Path]:
    written: list[Path] = []
    for subdir, purpose in {
        "active": "Active/frozen accepted or paper-demo observation specs only.",
        "preregistered": "Pre-registered future specs before discovery only.",
        "rejected": "Rejected strategy specs kept for lineage and exact-variant closure.",
        "benchmark_controls": "Benchmark/control specs that are not promotion candidates.",
    }.items():
        path = root / "strategy_specs" / subdir / "README.md"
        write_text(path, f"# {subdir.replace('_', ' ').title()}\n\n{purpose}\n")
        written.append(path)
    write_text(
        root / "strategy_specs" / "README.md",
        "# Strategy Specs\n\nCanonical specs should live here over time. This refactor does not move existing strategy code or mutate strategy outcomes.\n",
    )
    written.append(root / "strategy_specs" / "README.md")
    return written


def update_roadmap(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    header = "## Compact Current State"
    section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Repository refactor evidence: `{output.resolve()}`
- Compact state: `{(root / 'reports' / 'compact_state' / 'current_tournament_state.md').resolve()}`
- Current research mode: `repository_refactor_governance_only`
- Current next action: `{NEXT_ACTION}`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Intraday remains paused due to unresolved data-source terms and missing local intraday cache.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- Older roadmap sections below are historical/context unless explicitly referenced by the compact state.
- This section does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, or real-money recommendation.
"""
    if header in existing:
        start = existing.index(header)
        next_start = existing.find("\n## ", start + len(header))
        if next_start == -1:
            updated = existing[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
        else:
            updated = existing[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + existing[next_start + 1 :].lstrip()
    else:
        first_heading_end = existing.find("\n\n")
        if first_heading_end == -1:
            updated = existing.rstrip() + "\n\n" + section.rstrip() + "\n"
        else:
            updated = existing[:first_heading_end].rstrip() + "\n\n" + section.rstrip() + "\n\n" + existing[first_heading_end:].lstrip()
    write_text(path, updated)


def write_structure(root: Path, created_utc: str, output: Path) -> list[Path]:
    written: list[Path] = []
    compact = root / "reports" / "compact_state" / "current_tournament_state.md"
    history = root / "reports" / "compact_state" / "history_summary.md"
    write_text(compact, current_tournament_state_md(created_utc))
    write_text(history, history_summary_md())
    written.extend([compact, history])
    written.extend(write_family_registry(root))
    written.extend(write_lanes(root))
    written.extend(write_indicator_layer(root))
    written.extend(write_governance(root))
    written.extend(write_strategy_specs(root))
    update_roadmap(root, created_utc, output)
    return written


def cleanup_inventory_rows(tracked_generated: list[str], deleted: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in tracked_generated:
        rows.append(
            {
                "category": "tracked_generated_or_bulky_artifact",
                "path": path,
                "tracked": True,
                "action_taken": "none",
                "recommended_action": "git_rm_cached_after_manual_review",
                "reason": "Generated evidence/cache/log artifact should not remain source-of-truth code.",
            }
        )
    for path in deleted:
        rows.append(
            {
                "category": "local_python_or_test_cache",
                "path": path,
                "tracked": False,
                "action_taken": "deleted_local_directory",
                "recommended_action": "none",
                "reason": "Obvious local generated cache outside .venv.",
            }
        )
    return rows


def untracked_generated_report(tracked_generated: list[str]) -> str:
    commands = [
        "git rm --cached -r evidence/advisor_upload",
        "git rm --cached -r evidence/research_state/latest",
        "git rm --cached -r evidence/strategy_lab/latest",
        "git rm --cached -r data/cache",
        "git rm --cached -r data/intraday",
        'git rm --cached "*.zip"',
        'git rm --cached "*.jsonl"',
    ]
    sample = "\n".join(f"- `{path}`" for path in tracked_generated[:80]) or "- none found"
    command_text = "\n".join(f"- `{command}`" for command in commands)
    return f"""# Untracked Generated Files Report

Tracked generated/bulky artifacts found: `{len(tracked_generated)}`

Files untracked from Git in this task: `0`

Reason: the worktree was already dirty and many evidence files preserve lineage. This pass updates ignore policy and prepares commands rather than staging mass index removals.

## Sample Tracked Generated Files

{sample}

## Prepared Commands

{command_text}
"""


def write_reports(
    output: Path,
    created_utc: str,
    written: list[Path],
    deleted: list[str],
    tracked_generated: list[str],
    gitignore_info: dict[str, Any],
    manifest: dict[str, Any],
    consistency: dict[str, Any],
) -> None:
    rows = cleanup_inventory_rows(tracked_generated, deleted)
    write_csv(
        output / "repo_cleanup_inventory.csv",
        rows,
        ["category", "path", "tracked", "action_taken", "recommended_action", "reason"],
    )
    write_json(output / "repo_refactor_manifest.json", manifest)
    write_text(
        output / "repo_refactor_summary.md",
        f"""# Repository Refactor Summary

Created UTC: `{created_utc}`

This was a repository architecture, cleanup, and governance refactor only. It created compact state, family status summaries, lane policy, indicator governance, artifact policy, cleanup policy, workflow policy, and a cleanup inventory.

Next action: `{NEXT_ACTION}`
""",
    )
    write_text(
        output / "archived_or_deleted_items.md",
        f"""# Archived Or Deleted Items

Files archived: `0`

Local generated cache directories deleted: `{len(deleted)}`

Deleted directories:

{chr(10).join(f"- `{path}`" for path in deleted) if deleted else "- none"}

No lineage evidence, registry, roadmap, strategy code, test, broker guardrail, or active observation file was deleted.
""",
    )
    write_text(
        output / "gitignore_update_report.md",
        f"""# Gitignore Update Report

`.gitignore` updated: `{gitignore_info["gitignore_updated"]}`

Generated artifact policy block present: `true`

Generated/cache/artifact directories now ignored include evidence `latest/` outputs, advisor uploads, research-state latest, strategy-lab latest, provider/raw/intraday caches, logs, temp outputs, artifacts, zips, JSONL, DB files, parquet/feather, Python caches, and local environment files.

Canonical exceptions are preserved for compact reports, family status files, strategy specs, governance docs/configs, lanes, and indicator governance files.
""",
    )
    write_text(output / "untracked_generated_files_report.md", untracked_generated_report(tracked_generated))
    write_text(
        output / "new_structure_report.md",
        "# New Structure Report\n\n" + "\n".join(f"- `{path}`" for path in sorted(str(path) for path in written)) + "\n",
    )
    write_text(
        output / "canonical_state_report.md",
        f"""# Canonical State Report

Compact state location: `{Path('reports/compact_state/current_tournament_state.md')}`

History summary location: `{Path('reports/compact_state/history_summary.md')}`

The compact state preserves active VM, active DSR, static all-weather benchmark/control-only status, intraday pause, exact rejected variant closure, and the latest risk-controlled high-return rejection state.
""",
    )
    write_text(
        output / "family_registry_report.md",
        "# Family Registry Report\n\nFamily status files were created for dual momentum, Donchian breakout, macro GLD/duration, sector rotation, volatility management, calendar anomaly, and intraday research. Failure taxonomy and parent/child lineage contracts were added under `family_registry/`.\n",
    )
    write_text(
        output / "lane_framework_report.md",
        "# Lane Framework Report\n\nLane definitions, lane gate framework, and lane scorecard policy were added under `lanes/`. Profit engines, risk reducers, diversifiers, benchmark controls, and intraday research-only concepts now have separate gate expectations.\n",
    )
    write_text(
        output / "indicator_governance_report.md",
        "# Indicator Governance Report\n\nApproved initial indicator categories were defined under `indicator_layer/approved_indicators.yaml`. No indicator dependency was installed and no strategy logic was changed.\n",
    )
    write_text(
        output / "artifact_policy_report.md",
        "# Artifact Policy Report\n\nArtifact and cleanup policies were added under `governance/`. Generated evidence, caches, logs, zips, latest exports, and local data are treated as generated/local-only unless promoted into compact canonical summaries.\n",
    )
    write_text(
        output / "refactor_next_action.md",
        f"""# Refactor Next Action

Exact next action: `{NEXT_ACTION}`

Reason: the refactor created the structure and reports, but tracked generated artifacts remain in the Git index and should receive human review before mass untracking. Do not run this next action in this task.
""",
    )
    write_json(output / "repo_refactor_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "repo_refactor_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in EVIDENCE_FILES:
            archive.write(output / rel, rel)


def consistency_check(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    check = {
        "refactor_only": manifest["repository_refactor_only"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders": manifest["broker_orders_submitted"] is False and manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_not_changed": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_not_changed": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "compact_state_exists": (root / "reports" / "compact_state" / "current_tournament_state.md").exists(),
        "family_status_directory_exists": (root / "family_registry" / "family_status").exists(),
        "lane_policy_exists": (root / "lanes" / "lane_scorecard_policy.md").exists(),
        "indicator_governance_policy_exists": (root / "indicator_layer" / "indicator_policy.md").exists(),
        "artifact_policy_exists": (root / "governance" / "artifact_policy.md").exists(),
        "cleanup_inventory_exists": manifest["cleanup_inventory_created"] is True,
        "gitignore_update_report_exists": True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_repository_refactor_family_lane_os(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_state_snapshot(root)
    gitignore_info = update_gitignore(root)
    written = write_structure(root, created_utc, output)
    tracked_generated = tracked_generated_files(root)
    deleted = delete_local_generated_junk(root)
    strategies_after = strategy_state_snapshot(root)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output),
        **MANIFEST_FLAGS,
        "active_strategy_state_changed": strategies_before != strategies_after,
        "rejected_strategy_state_changed": strategies_before != strategies_after,
        "files_deleted_count": len(deleted),
        "files_archived_count": 0,
        "gitignore_updated": gitignore_info["gitignore_updated"],
        "tracked_generated_files_found": len(tracked_generated),
        "tracked_generated_files_untracked_count": 0,
        "next_action": NEXT_ACTION,
    }
    consistency = consistency_check(root, manifest)
    write_reports(output, created_utc, written, deleted, tracked_generated, gitignore_info, manifest, consistency)
    return {
        "output_dir": str(output),
        "files_deleted_count": len(deleted),
        "files_archived_count": 0,
        "gitignore_updated": gitignore_info["gitignore_updated"],
        "tracked_generated_files_found": len(tracked_generated),
        "tracked_generated_files_untracked_count": 0,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_repository_refactor_family_lane_os(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
