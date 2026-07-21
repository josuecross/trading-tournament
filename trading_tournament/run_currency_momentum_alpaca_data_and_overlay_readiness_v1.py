from __future__ import annotations

import json

from strategy_lab.research_os.research.currency_momentum_alpaca_data_and_overlay_readiness_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
