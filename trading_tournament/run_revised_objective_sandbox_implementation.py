from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import (
    run_revised_objective_sandbox_implementation,
)


def main() -> None:
    print(json.dumps(run_revised_objective_sandbox_implementation(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
