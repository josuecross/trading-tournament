from __future__ import annotations

import json

from strategy_lab.research_os.research.risk_parity_trend_single_source_preregistration_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
