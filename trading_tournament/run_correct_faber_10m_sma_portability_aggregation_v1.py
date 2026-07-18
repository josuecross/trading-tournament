from __future__ import annotations

import json

from strategy_lab.research_os.universe_expansion.correct_faber_10m_sma_portability_aggregation_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
