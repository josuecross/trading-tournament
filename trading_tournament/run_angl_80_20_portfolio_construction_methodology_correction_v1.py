from __future__ import annotations

import json

from strategy_lab.research_os.research.angl_80_20_portfolio_construction_methodology_correction_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
