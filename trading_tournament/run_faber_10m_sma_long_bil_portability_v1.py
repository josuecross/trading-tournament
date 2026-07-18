from __future__ import annotations

import json

from strategy_lab.research_os.universe_expansion.faber_10m_sma_long_bil_portability_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
