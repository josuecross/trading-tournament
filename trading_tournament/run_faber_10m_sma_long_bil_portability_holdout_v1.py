from __future__ import annotations

from strategy_lab.research_os.universe_expansion.faber_10m_sma_long_bil_portability_holdout_v1 import run


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2, sort_keys=True))
