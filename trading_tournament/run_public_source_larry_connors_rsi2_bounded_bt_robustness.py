from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_robustness import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
