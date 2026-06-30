from __future__ import annotations

import json

from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_v3_audit import (
    run_revised_objective_sandbox_scoring_fix_v3_audit,
)


def main() -> None:
    print(json.dumps(run_revised_objective_sandbox_scoring_fix_v3_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
