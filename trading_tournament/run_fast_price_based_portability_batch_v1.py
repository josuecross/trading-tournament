from __future__ import annotations

import json

from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))

