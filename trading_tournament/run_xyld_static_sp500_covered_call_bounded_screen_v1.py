from __future__ import annotations

import json

from strategy_lab.research_os.research.xyld_static_sp500_covered_call_bounded_screen_v1 import clean_value, run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
