from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT, PACKAGE_ROOT


OUTPUT_ROOT = MODULE_ROOT / "evidence" / "runtime_onboarding"
DEFAULT_JSON = OUTPUT_ROOT / "runtime_strategy_inventory.json"
DEFAULT_MD = OUTPUT_ROOT / "runtime_strategy_inventory.md"
REGISTRY_PATH = MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml"

REQUIRED_RULE_FIELDS = [
    "universe",
    "indicators",
    "eligibility",
    "ranking",
    "portfolio",
    "rebalance",
    "constraints",
]


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def runtime_registry() -> dict[str, Any]:
    return read_yaml(REGISTRY_PATH)


def source_exists(path_text: str) -> bool:
    return (MODULE_ROOT / path_text).exists() or (PACKAGE_ROOT / path_text).exists()


def copied_runtime_candidates() -> list[dict[str, Any]]:
    registry = runtime_registry()
    rows: list[dict[str, Any]] = []
    for strategy_id, row in (registry.get("strategies") or {}).items():
        spec_path = MODULE_ROOT / str(row.get("runtime_spec", "")).replace("runtime_strategies/", "runtime_strategies/")
        module_path = MODULE_ROOT / str(row.get("runtime_module", "")).replace("runtime_strategies/", "runtime_strategies/")
        if row.get("runtime_ready") is True and spec_path.exists() and module_path.exists():
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "status_classification": "runtime_ready",
                    "evidence_files_inspected": [str(REGISTRY_PATH.relative_to(PACKAGE_ROOT)), str(spec_path.relative_to(PACKAGE_ROOT))],
                    "exact_reason": "Already copied into Alpaca runtime registry with runtime_ready true and local spec/module present.",
                    "source_rule_files": [str(spec_path.relative_to(PACKAGE_ROOT)), str(module_path.relative_to(PACKAGE_ROOT))],
                    "missing_rule_fields": [],
                    "alpaca_paper_compatible": True,
                    "already_copied_into_alpaca_runtime": True,
                    "allowed_symbols": row.get("allowed_symbols", []),
                }
            )
    return rows


def dsr_candidate() -> dict[str, Any]:
    observation = PACKAGE_ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml"
    activation = PACKAGE_ROOT / "evidence" / "paper_forward_activations" / "dsr_sector_equal_weight_defensive_filter_v1" / "latest" / "frozen_rule.md"
    payload = read_yaml(observation)
    missing = []
    if not payload.get("universe"):
        missing.append("universe")
    if not payload.get("rule_summary"):
        missing.extend(["eligibility", "portfolio", "rebalance"])
    if payload.get("paper_forward_active") is True and not missing:
        classification = "ready_to_freeze"
        reason = "Recovered active/frozen paper-demo observation has complete enough fixed ETF rules for direct Alpaca runtime copy."
    else:
        classification = "onboarding_blocked"
        reason = "DSR recovered observation is missing required rule fields."
    return {
        "strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
        "status_classification": classification,
        "evidence_files_inspected": [str(observation.relative_to(PACKAGE_ROOT)), str(activation.relative_to(PACKAGE_ROOT))],
        "exact_reason": reason,
        "source_rule_files": [str(observation.relative_to(PACKAGE_ROOT)), str(activation.relative_to(PACKAGE_ROOT))],
        "missing_rule_fields": missing,
        "alpaca_paper_compatible": True,
        "already_copied_into_alpaca_runtime": (MODULE_ROOT / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.yaml").exists(),
        "allowed_symbols": payload.get("universe", ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"]),
    }


def future_only_candidates() -> list[dict[str, Any]]:
    review = PACKAGE_ROOT / "evidence" / "lane_reviews" / "volatility_managed_equity_etf" / "latest" / "volatility_managed_equity_etf_candidate_variants.csv"
    return [
        {
            "strategy_id": "vm_spy_realized_vol_target_v1",
            "status_classification": "not_successful_enough",
            "evidence_files_inspected": [str(review.relative_to(PACKAGE_ROOT))],
            "exact_reason": "Local evidence marks this as future research-sample review only, not successful or approved for runtime.",
            "source_rule_files": [],
            "missing_rule_fields": REQUIRED_RULE_FIELDS,
            "alpaca_paper_compatible": True,
            "already_copied_into_alpaca_runtime": False,
            "allowed_symbols": ["SPY", "BIL"],
        }
    ]


def blocked_candidates() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": "gror_balanced_momentum_60_40_v1",
            "status_classification": "onboarding_blocked",
            "evidence_files_inspected": ["strategy_lab/strategy_registry.yaml"],
            "exact_reason": "Promotion candidate is queued, but candidate_exhaustive was not run and full runtime rule source is not locally copied.",
            "source_rule_files": [],
            "missing_rule_fields": ["source_rule_file", "exact_runtime_module"],
            "alpaca_paper_compatible": True,
            "already_copied_into_alpaca_runtime": False,
            "allowed_symbols": [],
        },
        {
            "strategy_id": "crypto_spot",
            "status_classification": "unsupported_asset_class",
            "evidence_files_inspected": ["strategy_lab/strategy_registry.yaml"],
            "exact_reason": "Crypto is outside current Alpaca stock/ETF paper runtime scope.",
            "source_rule_files": [],
            "missing_rule_fields": [],
            "alpaca_paper_compatible": False,
            "already_copied_into_alpaca_runtime": False,
            "allowed_symbols": [],
        },
    ]


def build_inventory() -> dict[str, Any]:
    candidates = copied_runtime_candidates()
    seen = {row["strategy_id"] for row in candidates}
    dsr = dsr_candidate()
    if dsr["strategy_id"] not in seen:
        candidates.append(dsr)
    candidates.extend(future_only_candidates())
    candidates.extend(blocked_candidates())
    counts: dict[str, int] = {}
    for row in candidates:
        counts[row["status_classification"]] = counts.get(row["status_classification"], 0) + 1
    return {
        "phase": "Phase 6A: Successful Strategy Runtime Onboarding + Weekly Paper Demo Runner",
        "module_root": str(MODULE_ROOT),
        "no_tournament_runtime_dependency": True,
        "live_orders_supported": False,
        "paper_demo_only": True,
        "classification_counts": counts,
        "candidates": candidates,
    }


def write_inventory(inventory: dict[str, Any], json_path: Path = DEFAULT_JSON, md_path: Path = DEFAULT_MD) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Runtime Strategy Inventory", "", f"Phase: {inventory['phase']}", ""]
    for row in inventory["candidates"]:
        lines.extend(
            [
                f"## {row['strategy_id']}",
                "",
                f"- classification: `{row['status_classification']}`",
                f"- reason: {row['exact_reason']}",
                f"- alpaca_paper_compatible: `{str(row['alpaca_paper_compatible']).lower()}`",
                f"- already_copied_into_alpaca_runtime: `{str(row['already_copied_into_alpaca_runtime']).lower()}`",
                f"- evidence: {', '.join(row['evidence_files_inspected']) if row['evidence_files_inspected'] else 'none'}",
                f"- missing_rule_fields: {', '.join(row['missing_rule_fields']) if row['missing_rule_fields'] else 'none'}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory successful strategies for Alpaca runtime onboarding.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inventory = build_inventory()
    write_inventory(inventory, args.output_json, args.output_md)
    print(f"runtime_strategy_inventory_json={args.output_json}")
    print(f"runtime_strategy_inventory_md={args.output_md}")
    print(f"classification_counts={inventory['classification_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
