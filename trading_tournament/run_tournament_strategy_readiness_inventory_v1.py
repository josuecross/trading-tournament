from __future__ import annotations

import json

from strategy_lab.research_os.research import tournament_strategy_readiness_inventory_v1


if __name__ == "__main__":
    print(json.dumps(tournament_strategy_readiness_inventory_v1.run(), indent=2, sort_keys=True))
