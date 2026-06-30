from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.exploratory_sandbox.sandbox_manual_review import run_manual_review


def main() -> None:
    print(json.dumps(run_manual_review(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
