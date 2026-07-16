from __future__ import annotations

import json

from strategy_lab.research_os.research.max_diversification_cross_asset_etf_screen_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
