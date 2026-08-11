from __future__ import annotations

import argparse
from pathlib import Path

from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import (
    DEFAULT_AUDIT_ROOT,
    DEFAULT_HANDOFF_ROOT,
    IMPORT_EVIDENCE_ROOT,
    inventory_rows,
    load_packages,
)
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory Standard V1 handoff packages for the isolated Alpaca runtime.")
    parser.add_argument("--handoff-root", default=DEFAULT_HANDOFF_ROOT, type=Path)
    parser.add_argument("--audit-root", default=DEFAULT_AUDIT_ROOT, type=Path)
    parser.add_argument("--output-dir", default=IMPORT_EVIDENCE_ROOT / "inventory" / "latest", type=Path)
    return parser


def run_inventory(handoff_root: Path, audit_root: Path, output_dir: Path) -> dict[str, object]:
    packages = load_packages(handoff_root)
    rows = inventory_rows(packages)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "handoff_package_inventory.csv", rows)
    write_json(output_dir / "handoff_package_inventory.json", rows)
    summary = [
        "# Handoff Package Inventory",
        "",
        f"- handoff_root: {handoff_root}",
        f"- audit_root: {audit_root}",
        f"- packages_found: {len(rows)}",
        f"- packages_with_missing_fields: {sum(1 for row in rows if row['classifications'])}",
        "- network_calls: false",
        "- paper_orders_submitted: false",
        "- live_orders_submitted: false",
    ]
    (output_dir / "handoff_inventory_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return {"packages_found": len(rows), "output_dir": str(output_dir)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_inventory(args.handoff_root, args.audit_root, args.output_dir)
    print(f"packages_found: {result['packages_found']}")
    print(f"output_dir: {result['output_dir']}")
    print("network_calls: false")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
