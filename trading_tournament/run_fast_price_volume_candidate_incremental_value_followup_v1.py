from __future__ import annotations

import json

from strategy_lab.research_os.research.fast_price_volume_candidate_incremental_value_followup_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
