from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.revised_etf_wrapper_objective import (
    run_revised_etf_wrapper_objective,
)


def main() -> None:
    print(json.dumps(run_revised_etf_wrapper_objective(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
