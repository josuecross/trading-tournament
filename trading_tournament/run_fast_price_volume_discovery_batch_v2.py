from __future__ import annotations

import json

from strategy_lab.research_os.research.fast_price_volume_discovery_batch_v2 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
