from __future__ import annotations

import json

from strategy_lab.research_os.universe_expansion.gatev_distance_etf_economic_groups_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
