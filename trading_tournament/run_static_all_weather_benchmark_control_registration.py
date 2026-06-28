from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "benchmark_controls" / "static_all_weather_benchmark_v1" / "latest"
THIRD_EXPANSION_DIR = Path("evidence") / "parallel_research_discovery" / "third_expansion_with_lane_framework" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

BENCHMARK_CONTROL_ID = "static_all_weather_benchmark_v1"
BENCHMARK_CONTROL_STATUS = "benchmark_control_accepted"
NEXT_ACTION = "audit_third_expansion_failures_before_more_expansion"
VALID_NEXT_ACTIONS = {
    "audit_third_expansion_failures_before_more_expansion",
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_fourth_expansion_discovery_batch_with_lane_framework",
}

THIRD_EXPANSION_REJECTED_IDS = [
    "dual_momentum_paa_clean_v1",
    "gld_ief_spy_defensive_rotation_v1",
    "volatility_regime_spy_qqq_bil_v1",
]

MANIFEST_FLAGS = {
    "benchmark_control_registration_only": True,
    "benchmark_control_id": BENCHMARK_CONTROL_ID,
    "benchmark_control_status": BENCHMARK_CONTROL_STATUS,
    "backtests_run": False,
    "discovery_run": False,
    "new_performance_metrics_computed": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "provider_download": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "third_expansion_rejected_rows_reopened": False,
    "paper_demo_eligible": False,
    "candidate_exhaustive_eligible": False,
    "promotion_review_eligible": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    manifest = read_json(root / THIRD_EXPANSION_DIR / "third_expansion_discovery_manifest.json")
    if manifest.get("next_action") != "register_static_all_weather_as_benchmark_control_only":
        mismatches.append("third expansion discovery does not authorize static all-weather benchmark-control registration")
    if BENCHMARK_CONTROL_ID not in manifest.get("benchmark_control_accepted_ids", []):
        mismatches.append("static all-weather is not recorded as benchmark_control_accepted")
    if manifest.get("promotion_candidates_count") != 0:
        mismatches.append("third expansion has promotion candidates; registration-only static control action is no longer the sole next action")
    if manifest.get("candidate_exhaustive_run") is not False:
        mismatches.append("third expansion manifest unexpectedly records candidate_exhaustive")
    if manifest.get("paper_forward_activation") is not False:
        mismatches.append("third expansion manifest unexpectedly records paper-forward activation")
    return mismatches


def update_metadata(root: Path, output: Path, created_utc: str) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "static_all_weather_benchmark_control_path": str(output),
                "static_all_weather_benchmark_control_status": BENCHMARK_CONTROL_STATUS,
                "static_all_weather_benchmark_control_id": BENCHMARK_CONTROL_ID,
                "static_all_weather_benchmark_control_lane": "diversifier_contribution_lane",
                "static_all_weather_benchmark_control_usage": "same_window_benchmark_control_only",
                "static_all_weather_paper_demo_eligible": False,
                "static_all_weather_candidate_exhaustive_eligible": False,
                "static_all_weather_promotion_review_eligible": False,
                "static_all_weather_next_action": NEXT_ACTION,
                "current_next_action": NEXT_ACTION,
                "next_action": NEXT_ACTION,
                "backtests_run": False,
                "discovery_run": False,
                "new_performance_metrics_computed": False,
                "provider_download": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_path_touched": False,
                "live_orders": False,
                "real_money_recommendation": False,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        lines.insert(1 if lines else 0, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    marker = "## Static All-Weather Benchmark Control Registration"
    section = f"""## Static All-Weather Benchmark Control Registration

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Benchmark/control ID: `{BENCHMARK_CONTROL_ID}`
- Status: `{BENCHMARK_CONTROL_STATUS}`
- Universe: `SPY, IEF, GLD, BIL`
- Frozen allocation: `30% SPY, 40% IEF, 20% GLD, 10% BIL`
- Usage: same-window benchmark/control only for macro, diversifier, conservative allocation, and portfolio-contribution reviews.
- Next action: `{NEXT_ACTION}`
- No backtest, discovery, new performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live path, third-expansion rejected-row reopening, or real-money recommendation is authorized by this registration.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def registration_payload(output: Path, created_utc: str) -> dict[str, Any]:
    return {
        "benchmark_control_id": BENCHMARK_CONTROL_ID,
        "status": BENCHMARK_CONTROL_STATUS,
        "created_utc": created_utc,
        "evidence_path": str(output),
        "lane": "diversifier_contribution_lane",
        "role": "same_window_benchmark_control",
        "universe": ["SPY", "IEF", "GLD", "BIL"],
        "timeframe": "monthly",
        "frozen_allocation": {"SPY": 0.30, "IEF": 0.40, "GLD": 0.20, "BIL": 0.10},
        "rule": {
            "rebalance": "monthly",
            "static_weights_only": True,
            "signal_ranking": False,
            "trend_filter": False,
            "volatility_filter": False,
            "tactical_override": False,
            "replacement_asset": False,
            "leverage": False,
            "margin": False,
            "shorting": False,
            "derivatives": False,
        },
        "eligibility": {
            "paper_demo_eligible": False,
            "candidate_exhaustive_eligible": False,
            "promotion_review_eligible": False,
            "live_ready": False,
            "broker_ready": False,
            "real_money_recommendation": False,
        },
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Static All-Weather Benchmark Control Registration

Created UTC: `{manifest['created_utc']}`

Benchmark/control ID: `{BENCHMARK_CONTROL_ID}`

Status: `{BENCHMARK_CONTROL_STATUS}`

This registration records the static all-weather row as a benchmark/control artifact only. It is not a profit candidate, not a promotion-review candidate, not candidate-exhaustive eligible, and not paper/demo eligible.

Frozen allocation: `30% SPY / 40% IEF / 20% GLD / 10% BIL`

Next action: `{manifest['next_action']}`
"""


def allowed_usage_md() -> str:
    return """# Static All-Weather Allowed Usage

- Same-window benchmark/control for macro lane reviews.
- Same-window benchmark/control for diversifier contribution reviews.
- Same-window benchmark/control for conservative ETF allocation reviews.
- Portfolio contribution reference with and without a proposed diversifier.
- Drawdown, allocation, and interpretation control in future research packets.
- Compare-only registry metadata and evidence packet reference.
"""


def forbidden_usage_md() -> str:
    return """# Static All-Weather Forbidden Usage

- Do not treat as standalone alpha.
- Do not treat as a promotion-review candidate.
- Do not run candidate_exhaustive because of this registration.
- Do not activate paper-forward.
- Do not mark demo_active, live_ready, broker_ready, or real-money ready.
- Do not use this registration to reopen rejected third-expansion strategy rows.
- Do not tune weights, filters, universe, or rebalance cadence without a new pre-registration.
- Do not add broker/live-order paths.
"""


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_files = [
        "static_all_weather_benchmark_control_manifest.json",
        "static_all_weather_benchmark_control_summary.md",
        "static_all_weather_benchmark_control_registration.yaml",
        "static_all_weather_allowed_usage.md",
        "static_all_weather_forbidden_usage.md",
        "static_all_weather_next_action.md",
    ]
    check = {
        "registered_only_as_benchmark_control": manifest["benchmark_control_registration_only"] and manifest["benchmark_control_status"] == BENCHMARK_CONTROL_STATUS,
        "not_marked_active_strategy": not manifest["paper_demo_eligible"],
        "not_marked_promotion_candidate": not manifest["promotion_review_eligible"],
        "not_marked_candidate_exhaustive": not manifest["candidate_exhaustive_eligible"] and not manifest["candidate_exhaustive_run"],
        "not_paper_forward_eligible": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "not_demo_active": not manifest["paper_demo_eligible"],
        "not_live_ready": not manifest["live_orders"],
        "no_broker_live_order_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "third_expansion_rejected_candidates_remain_rejected": not manifest["third_expansion_rejected_rows_reopened"],
        "no_new_backtest_or_discovery": not manifest["backtests_run"] and not manifest["discovery_run"],
        "no_provider_download": not manifest["provider_download"],
        "no_real_money_recommendation": not manifest["real_money_recommendation"],
        "strategy_rows_unchanged": strategies_before == strategies_after,
        "required_files_created": all((output / name).exists() for name in required_files),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def write_outputs(output: Path, manifest: dict[str, Any], registration: dict[str, Any]) -> None:
    write_json(output / "static_all_weather_benchmark_control_manifest.json", manifest)
    (output / "static_all_weather_benchmark_control_summary.md").write_text(summary_md(manifest), encoding="utf-8")
    (output / "static_all_weather_benchmark_control_registration.yaml").write_text(
        yaml.safe_dump(registration, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )
    (output / "static_all_weather_allowed_usage.md").write_text(allowed_usage_md(), encoding="utf-8")
    (output / "static_all_weather_forbidden_usage.md").write_text(forbidden_usage_md(), encoding="utf-8")
    (output / "static_all_weather_next_action.md").write_text(
        f"# Static All-Weather Next Action\n\n`{manifest['next_action']}`\n\nDo not run this next action from the benchmark-control registration task.\n",
        encoding="utf-8",
    )


def run_static_all_weather_benchmark_control_registration(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    created_utc = now_utc()
    strategies_before = strategy_snapshot(root)
    registry_updated, roadmap_updated = update_metadata(root, output, created_utc)
    manifest = {
        "artifact": "static_all_weather_benchmark_control_registration",
        "created_utc": created_utc,
        "output_dir": str(output),
        "next_action": NEXT_ACTION,
        "registry_metadata_updated": registry_updated,
        "roadmap_updated": roadmap_updated,
        **MANIFEST_FLAGS,
    }
    registration = registration_payload(output, created_utc)
    write_outputs(output, manifest, registration)
    strategies_after = strategy_snapshot(root)
    consistency = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "static_all_weather_benchmark_control_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "benchmark_control_id": BENCHMARK_CONTROL_ID,
        "benchmark_control_status": BENCHMARK_CONTROL_STATUS,
        "next_action": NEXT_ACTION,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_static_all_weather_benchmark_control_registration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
