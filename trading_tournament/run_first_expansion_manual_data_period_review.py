from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import run_first_expansion_discovery_preregistration as prereg


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "data_availability" / "first_expansion_batch" / "manual_period_review" / "latest"
REFRESH_DIR = Path("evidence") / "data_availability" / "first_expansion_batch" / "latest"
PREREG_DIR = prereg.OUTPUT_DIR
EXPANSION_REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
EXPANSION_ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"

ALLOWED_RESOLUTIONS = [
    "run_first_expansion_discovery_batch_without_sector_rs",
    "pre_register_sector_rs_limited_history_batch",
    "revise_first_expansion_batch_period_gate_before_discovery",
    "manual_research_governance_review_required",
]
SELECTED_RESOLUTION = "run_first_expansion_discovery_batch_without_sector_rs"
NEXT_ACTION = "run_first_expansion_discovery_batch_without_sector_rs"
SEPARATE_LIMITED_HISTORY_NEXT_ACTION = "pre_register_sector_rs_limited_history_batch"
DEFERRED_CANDIDATE_IDS = ["sector_rs_weekly_cash_filter_v1"]
PERIOD_COMPATIBLE_CANDIDATE_IDS = [
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def date_min(values: list[str]) -> str:
    parsed = [parse_date(value) for value in values]
    valid = [value for value in parsed if value is not None]
    return str(min(valid)) if valid else ""


def date_max(values: list[str]) -> str:
    parsed = [parse_date(value) for value in values]
    valid = [value for value in parsed if value is not None]
    return str(max(valid)) if valid else ""


def years_between(start: str, end: str) -> float:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if start_date is None or end_date is None:
        return 0.0
    return round((end_date - start_date).days / 365.25, 2)


def load_batch(root: Path) -> dict[str, Any]:
    return load_yaml(root / PREREG_DIR / "first_expansion_discovery_batch.yaml")


def load_data_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / PREREG_DIR / "first_expansion_data_availability_manifest.json")


def candidate_projection(batch: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ["candidate_id", "universe", "entry_rule", "exit_rule", "sizing_rule", "benchmark_controls", "risk_controls"]
    return [{field: candidate.get(field) for field in fields} for candidate in batch.get("candidates", [])]


def existing_mixed_inception_convention(root: Path) -> dict[str, Any]:
    discovery_runner = root / "run_parallel_discovery_approved_cache_batch.py"
    runner_text = discovery_runner.read_text(encoding="utf-8") if discovery_runner.exists() else ""
    diagnostics_paths = [
        root / "evidence" / "parallel_research_discovery" / "breadth_state_regime" / "latest" / "breadth_state_regime_availability_diagnostics.csv",
        root / "evidence" / "parallel_research_discovery" / "breadth_state_regime" / "latest" / "breadth_state_regime_state_frequency.csv",
    ]
    return {
        "per_asset_availability_mode_found": 'DATA_HISTORY_MODE = "per_asset_availability"' in runner_text,
        "availability_diagnostics_found": any(path.exists() for path in diagnostics_paths),
        "conclusion": "project_has_some_per_asset_availability_convention_but_sector_rs_15y_gate_still_blocks_xlre_row",
    }


def compatibility_rows(root: Path) -> list[dict[str, Any]]:
    batch = load_batch(root)
    data_manifest = load_data_manifest(root)
    symbols = {row["symbol"]: row for row in data_manifest.get("symbol_details", [])}
    status_by_id = {row["candidate_id"]: row for row in data_manifest.get("candidate_status", [])}
    rows: list[dict[str, Any]] = []
    for candidate in batch.get("candidates", []):
        candidate_id = candidate["candidate_id"]
        universe = list(candidate.get("universe", []))
        first_dates = [str(symbols.get(symbol, {}).get("first_date", "")) for symbol in universe]
        last_dates = [str(symbols.get(symbol, {}).get("last_date", "")) for symbol in universe]
        earliest_start = date_min(first_dates)
        effective_start = date_max(first_dates)
        common_last = date_min(last_dates)
        history_years = years_between(effective_start, common_last)
        status = status_by_id.get(candidate_id, {})
        uses_xlre = "XLRE" in universe
        blocked_by_xlre = candidate_id in DEFERRED_CANDIDATE_IDS
        impacted_by_xlre = uses_xlre
        can_proceed = candidate_id in PERIOD_COMPATIBLE_CANDIDATE_IDS
        rows.append(
            {
                "candidate_id": candidate_id,
                "required_symbols": ";".join(universe),
                "earliest_required_symbol_start_date": earliest_start,
                "effective_all_symbols_start_date": effective_start,
                "common_last_date": common_last,
                "common_history_years": history_years,
                "full_2007_style_period_supported": effective_start <= "2007-05-30",
                "blocked_by_xlre": blocked_by_xlre,
                "xlre_in_universe": uses_xlre,
                "cache_missing": bool(status.get("missing_symbols")),
                "issue_classification": "period_inception_limitation" if impacted_by_xlre else "period_compatible",
                "can_proceed_without_changing_frozen_rules": can_proceed,
                "requires_separate_limited_history_batch": blocked_by_xlre,
                "comparability_vs_active_vm_affected": impacted_by_xlre,
                "comparability_vs_active_dsr_affected": impacted_by_xlre,
                "comparability_vs_active_combo_affected": impacted_by_xlre,
                "comparability_vs_spy_200d_affected": impacted_by_xlre,
                "recommended_handling": "defer_to_limited_history_preregistration" if blocked_by_xlre else "allow_in_first_batch_with_mixed_inception_diagnostics" if impacted_by_xlre else "allow_in_first_batch",
            }
        )
    return rows


def resolution_options_md(convention: dict[str, Any]) -> str:
    return f"""# First Expansion Resolution Options

Existing convention check:

- Per-asset availability mode found: `{convention['per_asset_availability_mode_found']}`
- Availability diagnostics found: `{convention['availability_diagnostics_found']}`
- Conclusion: `{convention['conclusion']}`

## Option A - Proceed With All Five Using Per-Symbol Availability

Allowed only if future discovery explicitly reports symbol availability, denominators, first eligible dates, and mixed-inception warnings. This is not selected because `sector_rs_weekly_cash_filter_v1` has a frozen 15-year period gate and `XLRE` starts in 2015.

## Option B - Proceed With Four Candidates And Defer Sector RS

Selected. Keep `sector_rs_weekly_cash_filter_v1` out of the first discovery batch and require a separate limited-history pre-registration. Allow the remaining four candidates to proceed only in a future authorized discovery step, with mixed-inception diagnostics for the two broad-universe rows that include `XLRE`.

## Option C - Split Limited-History Candidates Into Separate 2015+ Batch

Required for `sector_rs_weekly_cash_filter_v1` if it is tested later. This preserves comparability and prevents pretending the sector rotation sample length is the same as legacy sector ETFs.

## Option D - Revise The First Expansion Period Gate Before Discovery

Not selected. This would be allowable before backtests, but it would weaken the frozen 15-year skepticism gate for a sector-rotation row. A separate limited-history pre-registration is cleaner.
"""


def review_md(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# First Expansion Manual Data Period Review",
        "",
        "This is a methodology and comparability review only. No backtest, discovery run, performance metric, provider download, candidate exhaustive validation, paper-forward action, broker/live path, or real-money recommendation occurred.",
        "",
        f"Selected resolution: `{manifest['selected_resolution']}`",
        f"Next action: `{manifest['next_action']}`",
        f"Separate limited-history next action: `{manifest['separate_limited_history_next_action']}`",
        "",
        "## Core Decision",
        "",
        "`DIA` and `XLRE` are no longer missing-cache problems. `XLRE` remains an inception-period comparability issue because it starts in 2015. The first expansion batch should not pretend the sector-rotation candidate has the same 2007-style/15-year coverage as legacy sector ETFs.",
        "",
        "The selected resolution is to run a future first expansion discovery batch without `sector_rs_weekly_cash_filter_v1`, and to pre-register that sector row separately as a limited-history XLRE batch before any test.",
        "",
        "## Candidate Compatibility",
        "",
        "| Candidate | Effective start | Full 2007-style support | XLRE blocker | Can proceed without rule change | Handling |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['candidate_id']}` | {row['effective_all_symbols_start_date']} | {row['full_2007_style_period_supported']} | {row['blocked_by_xlre']} | {row['can_proceed_without_changing_frozen_rules']} | {row['recommended_handling']} |"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- No symbols were removed or substituted.",
            "- The frozen candidate definitions remain unchanged.",
            "- `sector_rs_weekly_cash_filter_v1` is deferred explicitly, not silently dropped.",
            "- Any future limited-history sector test needs its own pre-registration and must label the 2015+ sample clearly.",
        ]
    )
    return "\n".join(lines) + "\n"


def selected_resolution_md(manifest: dict[str, Any]) -> str:
    return f"""# First Expansion Selected Resolution

Selected resolution: `{manifest['selected_resolution']}`

Next action: `{manifest['next_action']}`

Deferred candidate: `sector_rs_weekly_cash_filter_v1`

Separate limited-history next action: `{manifest['separate_limited_history_next_action']}`

Rationale: `XLRE` is cache-present and schema-valid, but its 2015 inception conflicts with the frozen 15-year sector-rotation gate. Deferring the sector row preserves comparability while allowing the four non-blocked candidates to move to the future authorized discovery step.
"""


def update_metadata(root: Path, manifest: dict[str, Any]) -> None:
    registry_path = root / EXPANSION_REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("metadata", {})
    metadata.update(
        {
            "first_expansion_manual_period_review_path": str((root / OUTPUT_DIR).resolve()),
            "first_expansion_manual_period_selected_resolution": manifest["selected_resolution"],
            "first_expansion_manual_period_next_action": manifest["next_action"],
            "first_expansion_limited_history_next_action": manifest["separate_limited_history_next_action"],
            "manual_period_review_only": True,
            "backtests_run": False,
            "discovery_run": False,
            "provider_download": False,
            "candidate_exhaustive_run": False,
            "paper_forward_activation": False,
            "real_money_recommendation": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / EXPANSION_ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Strategy Expansion Roadmap\n"
    marker = "## First Expansion Manual Data Period Review"
    existing_without_old = existing.split(marker)[0].rstrip()
    section = f"""

{marker}

Created UTC: `{manifest['created_utc']}`

Selected resolution: `{manifest['selected_resolution']}`

Next action: `{manifest['next_action']}`

Deferred limited-history action: `{manifest['separate_limited_history_next_action']}`

Reason: `XLRE` is cache-present but starts in 2015, so `sector_rs_weekly_cash_filter_v1` should not be treated as 2007-style/15-year comparable inside the first expansion discovery batch.
"""
    roadmap_path.write_text(existing_without_old + section + "\n", encoding="utf-8")

    prereg_decision = root / PREREG_DIR / "first_expansion_manual_period_review_decision.md"
    prereg_decision.write_text(selected_resolution_md(manifest), encoding="utf-8")
    (root / PREREG_DIR / "first_expansion_next_action.md").write_text(
        f"# First Expansion Next Action\n\n`{manifest['next_action']}`\n\nDeferred limited-history action: `{manifest['separate_limited_history_next_action']}`\n",
        encoding="utf-8",
    )


def consistency_check(
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    before_batch: dict[str, Any],
    after_batch: dict[str, Any],
) -> dict[str, Any]:
    before_projection = candidate_projection(before_batch)
    after_projection = candidate_projection(after_batch)
    dia_row = next((row for row in rows if "DIA" in row["required_symbols"].split(";")), None)
    xlre_rows = [row for row in rows if row["xlre_in_universe"]]
    consistency = {
        "manual_period_review_only": manifest["manual_period_review_only"],
        "backtests_run": manifest["backtests_run"],
        "discovery_run": manifest["discovery_run"],
        "performance_metrics_computed": manifest["performance_metrics_computed"],
        "provider_download": manifest["provider_download"],
        "candidate_exhaustive_run": manifest["candidate_exhaustive_run"],
        "paper_forward_review": manifest["paper_forward_review"],
        "paper_forward_activation": manifest["paper_forward_activation"],
        "broker_path_touched": manifest["broker_path_touched"],
        "live_orders": manifest["live_orders"],
        "real_money_recommendation": manifest["real_money_recommendation"],
        "frozen_rules_changed": before_projection != after_projection,
        "candidate_universe_changed": any(before.get("universe") != after.get("universe") for before, after in zip(before_projection, after_projection)),
        "benchmarks_changed": any(before.get("benchmark_controls") != after.get("benchmark_controls") for before, after in zip(before_projection, after_projection)),
        "active_strategy_state_changed": manifest["active_strategy_state_changed"],
        "etf_wrapper_track_reopened": manifest["etf_wrapper_track_reopened"],
        "xlre_period_blocker_detected": manifest["xlre_period_blocker_detected"],
        "dia_not_marked_missing": bool(dia_row) and not dia_row["cache_missing"],
        "xlre_not_marked_missing": bool(xlre_rows) and all(not row["cache_missing"] for row in xlre_rows),
        "issue_is_period_not_missing_cache": bool(xlre_rows) and all(row["issue_classification"] == "period_inception_limitation" for row in xlre_rows),
        "selected_resolution_allowed": manifest["selected_resolution"] in ALLOWED_RESOLUTIONS,
        "next_action_not_blind_refresh": manifest["next_action"] != "authorize_data_availability_or_cache_refresh_for_first_expansion_batch",
        "no_symbols_removed_or_substituted": [row["candidate_id"] for row in after_projection] == prereg.AUTHORIZED_CANDIDATE_IDS,
        "mixed_inception_diagnostics_required_for_proceeding_xlre_rows": manifest["mixed_inception_diagnostics_required_for_future_discovery"],
        "limited_history_preregistration_required_for_deferred_candidates": bool(manifest["deferred_limited_history_candidate_ids"]) and manifest["separate_limited_history_next_action"] == SEPARATE_LIMITED_HISTORY_NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["manual_period_review_only"]
        and not consistency["backtests_run"]
        and not consistency["discovery_run"]
        and not consistency["performance_metrics_computed"]
        and not consistency["provider_download"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["paper_forward_review"]
        and not consistency["paper_forward_activation"]
        and not consistency["broker_path_touched"]
        and not consistency["live_orders"]
        and not consistency["real_money_recommendation"]
        and not consistency["frozen_rules_changed"]
        and not consistency["candidate_universe_changed"]
        and not consistency["benchmarks_changed"]
        and not consistency["active_strategy_state_changed"]
        and not consistency["etf_wrapper_track_reopened"]
        and consistency["xlre_period_blocker_detected"]
        and consistency["dia_not_marked_missing"]
        and consistency["xlre_not_marked_missing"]
        and consistency["issue_is_period_not_missing_cache"]
        and consistency["selected_resolution_allowed"]
        and consistency["next_action_not_blind_refresh"]
        and consistency["no_symbols_removed_or_substituted"]
        and consistency["mixed_inception_diagnostics_required_for_proceeding_xlre_rows"]
        and consistency["limited_history_preregistration_required_for_deferred_candidates"]
    )
    return consistency


def run_first_expansion_manual_data_period_review(root: Path = ROOT) -> dict[str, Any]:
    created_utc = now_utc()
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    before_batch = load_batch(root)
    before_hashes = {
        "strategy_expansion_registry": sha256_file(root / EXPANSION_REGISTRY_PATH),
        "strategy_expansion_roadmap": sha256_file(root / EXPANSION_ROADMAP_PATH),
    }
    rows = compatibility_rows(root)
    convention = existing_mixed_inception_convention(root)
    manifest = {
        "artifact": "first_expansion_manual_data_period_review",
        "created_utc": created_utc,
        "output_dir": str(output_dir.resolve()),
        "manual_period_review_only": True,
        "backtests_run": False,
        "discovery_run": False,
        "performance_metrics_computed": False,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "frozen_rules_changed": False,
        "candidate_universe_changed": False,
        "benchmarks_changed": False,
        "active_strategy_state_changed": False,
        "etf_wrapper_track_reopened": False,
        "xlre_period_blocker_detected": True,
        "dia_cache_present": True,
        "xlre_cache_present": True,
        "issue_classification": "period_inception_limitation_not_missing_cache",
        "selected_resolution": SELECTED_RESOLUTION,
        "next_action": NEXT_ACTION,
        "separate_limited_history_next_action": SEPARATE_LIMITED_HISTORY_NEXT_ACTION,
        "period_compatible_candidate_ids": PERIOD_COMPATIBLE_CANDIDATE_IDS,
        "deferred_limited_history_candidate_ids": DEFERRED_CANDIDATE_IDS,
        "mixed_inception_diagnostics_required_for_future_discovery": True,
        "existing_convention": convention,
    }

    write_csv(
        output_dir / "first_expansion_candidate_period_compatibility.csv",
        rows,
        [
            "candidate_id",
            "required_symbols",
            "earliest_required_symbol_start_date",
            "effective_all_symbols_start_date",
            "common_last_date",
            "common_history_years",
            "full_2007_style_period_supported",
            "blocked_by_xlre",
            "xlre_in_universe",
            "cache_missing",
            "issue_classification",
            "can_proceed_without_changing_frozen_rules",
            "requires_separate_limited_history_batch",
            "comparability_vs_active_vm_affected",
            "comparability_vs_active_dsr_affected",
            "comparability_vs_active_combo_affected",
            "comparability_vs_spy_200d_affected",
            "recommended_handling",
        ],
    )
    write_json(output_dir / "first_expansion_manual_period_review_manifest.json", manifest)
    (output_dir / "first_expansion_manual_period_review.md").write_text(review_md(rows, manifest), encoding="utf-8")
    (output_dir / "first_expansion_resolution_options.md").write_text(resolution_options_md(convention), encoding="utf-8")
    (output_dir / "first_expansion_selected_resolution.md").write_text(selected_resolution_md(manifest), encoding="utf-8")
    (output_dir / "first_expansion_next_action.md").write_text(f"# First Expansion Next Action\n\n`{NEXT_ACTION}`\n", encoding="utf-8")

    update_metadata(root, manifest)
    after_batch = load_batch(root)
    after_hashes = {
        "strategy_expansion_registry": sha256_file(root / EXPANSION_REGISTRY_PATH),
        "strategy_expansion_roadmap": sha256_file(root / EXPANSION_ROADMAP_PATH),
    }
    manifest["metadata_files_updated"] = before_hashes != after_hashes
    write_json(output_dir / "first_expansion_manual_period_review_manifest.json", manifest)
    consistency = consistency_check(manifest, rows, before_batch, after_batch)
    write_json(output_dir / "first_expansion_manual_period_consistency_check.json", consistency)
    return manifest


if __name__ == "__main__":
    result = run_first_expansion_manual_data_period_review(ROOT)
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_resolution": result["selected_resolution"],
                "next_action": result["next_action"],
                "separate_limited_history_next_action": result["separate_limited_history_next_action"],
                "deferred_limited_history_candidate_ids": result["deferred_limited_history_candidate_ids"],
            },
            indent=2,
        )
    )
