from __future__ import annotations

import json

from strategy_lab.research_os.research.gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
