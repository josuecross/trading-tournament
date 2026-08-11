from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import (
    DEFAULT_HANDOFF_ROOT,
    IMPORT_EVIDENCE_ROOT,
    run_import_pipeline,
)
from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import Standard V1 handoffs into disabled Alpaca runtime specs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-found", action="store_true")
    group.add_argument("--package-id")
    group.add_argument("--first-batch", action="store_true")
    parser.add_argument("--handoff-root", default=DEFAULT_HANDOFF_ROOT, type=Path)
    parser.add_argument("--output-dir", default=IMPORT_EVIDENCE_ROOT / "imports" / "latest", type=Path)
    parser.add_argument("--dry-run", action="store_true", default=False, help="Write reports only. This is the default unless --write-disabled-specs is used.")
    parser.add_argument("--write-disabled-specs", action="store_true", help="Write disabled generated specs and immutable package cache records.")
    return parser


def write_import_reports(results, output_dir: Path, *, dry_run: bool, write_disabled_specs: bool) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    imported = []
    blocked = []
    unsupported = []
    manual = []
    conformance = []
    for result in results:
        row = {
            "package_id": result.package.package_id,
            "strategy_id": result.package.strategy_id,
            "import_status": result.compatibility.import_status,
            "calculator_status": result.compatibility.calculator_status,
            "provider_status": result.compatibility.provider_status,
            "conformance_status": result.compatibility.conformance_status,
            "generated_spec_path": str(result.generated_spec_path or ""),
            "enabled": "false",
            "runtime_ready": "false",
        }
        imported.append(row)
        conformance.append({"package_id": row["package_id"], "strategy_id": row["strategy_id"], "conformance_status": row["conformance_status"], "report_path": str(result.conformance_report_path or "")})
        if result.compatibility.blocked_reasons:
            blocked.append({"package_id": row["package_id"], "strategy_id": row["strategy_id"], "blocked_reasons": ";".join(result.compatibility.blocked_reasons)})
        if result.compatibility.unsupported_reasons:
            unsupported.append({"package_id": row["package_id"], "strategy_id": row["strategy_id"], "unsupported_reasons": ";".join(result.compatibility.unsupported_reasons)})
        if result.compatibility.manual_review_reasons:
            manual.append({"package_id": row["package_id"], "strategy_id": row["strategy_id"], "manual_review_reasons": ";".join(result.compatibility.manual_review_reasons)})

    calculators = CalculatorRegistry()
    providers = ProviderRegistry()
    write_csv(output_dir / "imported_packages.csv", imported)
    write_csv(output_dir / "blocked_imports.csv", blocked, ["package_id", "strategy_id", "blocked_reasons"])
    write_csv(output_dir / "unsupported_imports.csv", unsupported, ["package_id", "strategy_id", "unsupported_reasons"])
    write_csv(output_dir / "manual_review_required.csv", manual, ["package_id", "strategy_id", "manual_review_reasons"])
    write_csv(output_dir / "conformance_results.csv", conformance)
    write_csv(output_dir / "calculator_registry_report.csv", calculators.rows())
    write_csv(output_dir / "provider_registry_report.csv", providers.rows())
    manifest = [
        "source: standard_v1_handoff_import",
        f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"dry_run: {str(dry_run).lower()}",
        f"write_disabled_specs: {str(write_disabled_specs).lower()}",
        "enabled_any_strategy: false",
        "paper_orders_submitted: false",
        "live_orders_submitted: false",
        "network_calls: false",
    ]
    (output_dir / "import_manifest.yaml").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    summary = [
        "# Standard Handoff Import Summary",
        "",
        f"- packages_seen: {len(imported)}",
        f"- disabled_specs_written: {sum(1 for row in imported if row['generated_spec_path'])}",
        f"- blocked_imports: {len(blocked)}",
        f"- unsupported_imports: {len(unsupported)}",
        f"- manual_review_required: {len(manual)}",
        "- strategies_enabled: false",
        "- runtime_ready_set_true: false",
        "- paper_orders_submitted: false",
        "- live_orders_submitted: false",
        "- network_calls: false",
    ]
    (output_dir / "handoff_import_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    consistency = {
        "dry_run": dry_run,
        "write_disabled_specs": write_disabled_specs,
        "packages_seen": len(imported),
        "disabled_specs_written": sum(1 for row in imported if row["generated_spec_path"]),
        "strategies_enabled": False,
        "runtime_ready_set_true": False,
        "paper_orders_submitted": False,
        "live_orders_submitted": False,
        "network_calls": False,
        "active_runtime_registry_modified": False,
    }
    (output_dir / "consistency_check.json").write_text(json.dumps(consistency, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return consistency


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = not args.write_disabled_specs or args.dry_run
    results = run_import_pipeline(
        handoff_root=args.handoff_root,
        output_dir=args.output_dir,
        all_found=args.all_found,
        package_id=args.package_id,
        first_batch=args.first_batch,
        write_disabled_specs=args.write_disabled_specs,
        dry_run=dry_run,
    )
    consistency = write_import_reports(results, args.output_dir, dry_run=dry_run, write_disabled_specs=args.write_disabled_specs)
    print(f"packages_seen: {consistency['packages_seen']}")
    print(f"disabled_specs_written: {consistency['disabled_specs_written']}")
    print(f"output_dir: {args.output_dir}")
    print("strategies_enabled: false")
    print("network_calls: false")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
