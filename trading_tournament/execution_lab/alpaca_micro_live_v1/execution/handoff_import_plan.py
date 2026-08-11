from __future__ import annotations

import argparse
from pathlib import Path

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import (
    DEFAULT_AUDIT_ROOT,
    DEFAULT_HANDOFF_ROOT,
    IMPORT_EVIDENCE_ROOT,
    load_packages,
    plan_rows,
)
from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan Standard V1 handoff imports for the isolated Alpaca runtime.")
    parser.add_argument("--handoff-root", default=DEFAULT_HANDOFF_ROOT, type=Path)
    parser.add_argument("--audit-root", default=DEFAULT_AUDIT_ROOT, type=Path)
    parser.add_argument("--output-dir", default=IMPORT_EVIDENCE_ROOT / "plans" / "latest", type=Path)
    return parser


def run_plan(handoff_root: Path, audit_root: Path, output_dir: Path) -> dict[str, object]:
    calculators = CalculatorRegistry()
    providers = ProviderRegistry()
    packages = load_packages(handoff_root)
    rows = plan_rows(packages, calculators, providers)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "handoff_import_plan.csv", rows)
    write_csv(output_dir / "calculator_binding_plan.csv", [
        {"package_id": row["package_id"], "strategy_id": row["strategy_id"], "calculator_status": row["calculator_status"], "blocked_reasons": row["blocked_reasons"]}
        for row in rows
    ])
    write_csv(output_dir / "provider_adapter_plan.csv", [
        {"package_id": row["package_id"], "strategy_id": row["strategy_id"], "provider_status": row["provider_status"], "blocked_reasons": row["blocked_reasons"], "unsupported_reasons": row["unsupported_reasons"]}
        for row in rows
    ])
    write_csv(output_dir / "generated_spec_plan.csv", [
        {"package_id": row["package_id"], "strategy_id": row["strategy_id"], "will_generate_disabled_spec": "true", "enabled": "false", "runtime_ready": "false"}
        for row in rows
    ])
    blocked = sum(1 for row in rows if row["import_status"] == "blocked")
    unsupported = sum(1 for row in rows if row["import_status"] == "unsupported")
    summary = [
        "# Handoff Import Plan",
        "",
        f"- handoff_root: {handoff_root}",
        f"- audit_root: {audit_root}",
        f"- packages_planned: {len(rows)}",
        f"- blocked: {blocked}",
        f"- unsupported: {unsupported}",
        "- generated_specs_enabled: false",
        "- network_calls: false",
        "- paper_orders_submitted: false",
        "- live_orders_submitted: false",
    ]
    (output_dir / "handoff_import_plan.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return {"packages_planned": len(rows), "blocked": blocked, "unsupported": unsupported, "output_dir": str(output_dir)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_plan(args.handoff_root, args.audit_root, args.output_dir)
    print(f"packages_planned: {result['packages_planned']}")
    print(f"blocked: {result['blocked']}")
    print(f"unsupported: {result['unsupported']}")
    print(f"output_dir: {result['output_dir']}")
    print("network_calls: false")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
