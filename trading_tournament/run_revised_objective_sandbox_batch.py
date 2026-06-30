from __future__ import annotations

import argparse
import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import BATCH_ID, MAX_TOTAL_VARIANTS
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import (
    run_revised_objective_sandbox_batch,
    run_revised_objective_sandbox_dry_run,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_v3_rerun import (
    run_revised_objective_sandbox_batch_v3_rerun,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or dry-run the revised-objective sandbox batch.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate the non-executing batch 002 implementation plan.")
    mode.add_argument("--run-batch", action="store_true", help="Run sandbox-only exploratory batch 002 calculations.")
    parser.add_argument("--batch-id", default=BATCH_ID)
    parser.add_argument("--max-variants", type=int, default=MAX_TOTAL_VARIANTS)
    parser.add_argument("--scoring-version", choices=("v3",), default=None)
    parser.add_argument("--rerun-label", default=None)
    args = parser.parse_args()
    if args.run_batch:
        if args.scoring_version == "v3" and args.rerun_label == "fixed_scoring_v3":
            payload = run_revised_objective_sandbox_batch_v3_rerun(
                ROOT,
                batch_id=args.batch_id,
                max_variants=args.max_variants,
                rerun_label=args.rerun_label,
                update_project_metadata=True,
            )
        else:
            payload = run_revised_objective_sandbox_batch(
                ROOT,
                batch_id=args.batch_id,
                max_variants=args.max_variants,
                update_project_metadata=True,
            )
    else:
        payload = run_revised_objective_sandbox_dry_run(
            ROOT,
            batch_id=args.batch_id,
            max_variants=args.max_variants,
            update_project_metadata=False,
        )
    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
