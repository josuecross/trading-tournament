from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import run_objective_reset_review


def main() -> None:
    print(json.dumps(run_objective_reset_review(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
