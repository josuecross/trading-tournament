from __future__ import annotations

import json

from strategy_lab.research_os.universe_expansion.phase2_bounded_multi_asset_research_universe_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
