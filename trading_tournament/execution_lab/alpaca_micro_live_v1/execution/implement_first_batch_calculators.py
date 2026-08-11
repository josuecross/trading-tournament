from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.conformance import run_conformance
from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import DEFAULT_HANDOFF_ROOT, FIRST_BATCH, IMPORT_EVIDENCE_ROOT, load_packages
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv, write_json

EVIDENCE_DIR = IMPORT_EVIDENCE_ROOT / "calculators_first_batch" / "latest"
CONFORMANCE_DIR = IMPORT_EVIDENCE_ROOT / "conformance" / "latest"
GENERATED_SPEC_DIR = MODULE_ROOT / "runtime_strategies" / "generated"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Implement and gate first-batch Standard V1 handoff calculators.")
    parser.add_argument("--first-batch", action="store_true", required=True)
    parser.add_argument("--handoff-root", type=Path, default=DEFAULT_HANDOFF_ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=EVIDENCE_DIR)
    parser.add_argument("--conformance-dir", type=Path, default=CONFORMANCE_DIR)
    parser.add_argument("--generated-spec-dir", type=Path, default=GENERATED_SPEC_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not update generated specs.")
    parser.add_argument("--write-bindings", action="store_true", help="Write binding evidence and update generated specs from conformance results.")
    parser.add_argument("--run-conformance", action="store_true", help="Run first-batch conformance fixtures.")
    return parser


def _status_from_conformance(status: str) -> str:
    if status == "fixture_passed":
        return "calculator_binding_present_fixture_passed"
    if status == "fixture_failed":
        return "calculator_binding_present_fixture_failed"
    if status in {"fixture_missing", "manual_review_required"}:
        return "manual_review_required"
    return "calculator_binding_missing"


def _update_generated_spec(spec_dir: Path, package, conformance_status: str, blocked_reason: str) -> dict[str, Any]:
    path = spec_dir / f"{package.strategy_id}.yaml"
    before_exists = path.exists()
    payload: dict[str, Any] = {}
    if before_exists:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload.update(
        {
            "strategy_id": package.strategy_id,
            "handoff_package_id": package.package_id,
            "source": "standard_v1_handoff_import",
            "runtime_version": "alpaca_runtime_v1",
            "enabled": False,
            "runtime_ready": False,
            "paper_trading_allowed": False,
            "live_trading_allowed": False,
            "import_status": "conformance_passed_disabled" if conformance_status == "fixture_passed" else "blocked",
            "calculator_binding": _status_from_conformance(conformance_status),
            "conformance": {"status": conformance_status},
            "blocked_reason": blocked_reason if conformance_status != "fixture_passed" else "disabled_pending_runtime_enablement",
        }
    )
    spec_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return {
        "package_id": package.package_id,
        "strategy_id": package.strategy_id,
        "generated_spec_path": str(path),
        "spec_existed_before": str(before_exists).lower(),
        "import_status": payload["import_status"],
        "enabled": str(payload["enabled"]).lower(),
        "runtime_ready": str(payload["runtime_ready"]).lower(),
        "paper_trading_allowed": str(payload["paper_trading_allowed"]).lower(),
        "live_trading_allowed": str(payload["live_trading_allowed"]).lower(),
    }


def run_first_batch(
    *,
    handoff_root: Path,
    evidence_dir: Path,
    conformance_dir: Path,
    generated_spec_dir: Path,
    dry_run: bool,
    write_bindings: bool,
    run_conformance_gate: bool,
) -> dict[str, Any]:
    packages = [package for package in load_packages(handoff_root) if package.package_id in FIRST_BATCH]
    registry = CalculatorRegistry()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    conformance_dir.mkdir(parents=True, exist_ok=True)

    binding_rows: list[dict[str, Any]] = []
    conformance_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    spec_rows: list[dict[str, Any]] = []
    for package in sorted(packages, key=lambda item: item.package_id):
        binding = registry.resolve(package.calculator_type, package.strategy_id)
        binding_status = binding.status if binding else "calculator_binding_missing"
        conformance = run_conformance(package, registry, conformance_dir) if run_conformance_gate else {"status": "not_run", "report_path": ""}
        if run_conformance_gate and binding:
            binding_status = _status_from_conformance(conformance["status"])
        blocked_reason = ""
        if conformance["status"] != "fixture_passed":
            blocked_reason = conformance["status"]
            blocked_rows.append({"package_id": package.package_id, "strategy_id": package.strategy_id, "blocked_reason": blocked_reason})
        binding_rows.append(
            {
                "package_id": package.package_id,
                "strategy_id": package.strategy_id,
                "calculator_type": package.calculator_type,
                "calculator_binding": binding_status,
                "module_path": binding.module_path if binding else "",
            }
        )
        conformance_rows.append(
            {
                "package_id": package.package_id,
                "strategy_id": package.strategy_id,
                "calculator_type": package.calculator_type,
                "conformance_status": conformance["status"],
                "report_path": conformance.get("report_path", ""),
            }
        )
        if write_bindings and not dry_run:
            spec_rows.append(_update_generated_spec(generated_spec_dir, package, conformance["status"], blocked_reason))

    write_csv(evidence_dir / "first_batch_calculator_bindings.csv", binding_rows)
    write_json(evidence_dir / "first_batch_calculator_bindings.json", binding_rows)
    write_csv(evidence_dir / "first_batch_conformance_results.csv", conformance_rows)
    write_csv(evidence_dir / "blocked_first_batch_calculators.csv", blocked_rows, ["package_id", "strategy_id", "blocked_reason"])
    write_csv(evidence_dir / "generated_spec_update_report.csv", spec_rows, ["package_id", "strategy_id", "generated_spec_path", "spec_existed_before", "import_status", "enabled", "runtime_ready", "paper_trading_allowed", "live_trading_allowed"])

    write_csv(conformance_dir / "first_batch_conformance_results.csv", conformance_rows)
    write_json(conformance_dir / "first_batch_conformance_results.json", conformance_rows)
    write_csv(conformance_dir / "calculator_binding_report.csv", binding_rows)
    write_csv(conformance_dir / "blocked_calculator_imports.csv", blocked_rows, ["package_id", "strategy_id", "blocked_reason"])

    passed = sum(1 for row in conformance_rows if row["conformance_status"] == "fixture_passed")
    summary = [
        "# First Batch Conformance Summary",
        "",
        f"- evaluated: {len(conformance_rows)}",
        f"- fixture_passed: {passed}",
        f"- blocked: {len(blocked_rows)}",
        f"- generated_specs_updated: {len(spec_rows)}",
        "- generated_specs_enabled: false",
        "- active_runtime_strategies_changed: false",
        "- broker_network_calls: false",
        "- paper_orders_submitted: false",
        "- live_orders_submitted: false",
    ]
    (evidence_dir / "first_batch_conformance_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    (conformance_dir / "first_batch_conformance_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    safety = {
        "paper_orders_submitted": False,
        "live_orders_submitted": False,
        "broker_network_calls": False,
        "active_runtime_strategies_changed": False,
        "generated_specs_enabled": False,
        "research_handoffs_mutated": False,
        "trading_tournament_mutated": False,
    }
    write_json(evidence_dir / "safety_check.json", safety)
    consistency = {
        **safety,
        "first_batch_expected": len(FIRST_BATCH),
        "first_batch_evaluated": len(conformance_rows),
        "fixture_passed": passed,
        "blocked_calculators": len(blocked_rows),
        "generated_specs_updated": len(spec_rows),
        "generated_specs_runtime_ready": False,
        "generated_specs_paper_trading_allowed": False,
        "dry_run": dry_run,
        "write_bindings": write_bindings,
        "run_conformance": run_conformance_gate,
    }
    write_json(evidence_dir / "consistency_check.json", consistency)
    (evidence_dir / "calculator_implementation_manifest.yaml").write_text(
        "\n".join(
            [
                "task_id: implement_missing_calculators_first_batch_v1",
                f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
                f"first_batch_evaluated: {len(conformance_rows)}",
                f"fixture_passed: {passed}",
                f"blocked_calculators: {len(blocked_rows)}",
                "generated_specs_enabled: false",
                "active_runtime_strategies_changed: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "next_action.md").write_text("run_first_batch_conformance_review_v1\n", encoding="utf-8")
    return consistency


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = args.dry_run or not args.write_bindings
    result = run_first_batch(
        handoff_root=args.handoff_root,
        evidence_dir=args.evidence_dir,
        conformance_dir=args.conformance_dir,
        generated_spec_dir=args.generated_spec_dir,
        dry_run=dry_run,
        write_bindings=args.write_bindings,
        run_conformance_gate=args.run_conformance,
    )
    print(f"first_batch_evaluated: {result['first_batch_evaluated']}")
    print(f"fixture_passed: {result['fixture_passed']}")
    print(f"blocked_calculators: {result['blocked_calculators']}")
    print(f"generated_specs_updated: {result['generated_specs_updated']}")
    print("generated_specs_enabled: false")
    print("active_runtime_strategies_changed: false")
    print("broker_network_calls: false")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
