from __future__ import annotations

import json

from strategy_lab.research_os.objective_reset.fixed_scoring_rerun_audit import run_fixed_scoring_rerun_audit


def main() -> None:
    print(json.dumps(run_fixed_scoring_rerun_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
