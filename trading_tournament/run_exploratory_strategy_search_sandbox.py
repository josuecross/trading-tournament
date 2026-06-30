from __future__ import annotations

import argparse
import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import MAX_TOTAL_FUTURE_VARIANTS, ROOT
from strategy_lab.research_os.exploratory_sandbox.sandbox_batch import run_sandbox_batch
from strategy_lab.research_os.exploratory_sandbox.sandbox_evidence import run_sandbox_implementation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a non-promotable exploratory sandbox dry-run plan.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate specifications only.")
    mode.add_argument("--run-batch", action="store_true", help="Run the authorized non-promotable sandbox batch.")
    parser.add_argument("--batch-id", default="batch_001")
    parser.add_argument("--max-variants", type=int, default=MAX_TOTAL_FUTURE_VARIANTS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        result = run_sandbox_implementation(ROOT, max_variants=args.max_variants, update_metadata=True)
    elif args.run_batch:
        result = run_sandbox_batch(ROOT, batch_id=args.batch_id, max_variants=args.max_variants, update_registry=True)
    else:
        raise SystemExit("Choose --dry-run or --run-batch.")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
