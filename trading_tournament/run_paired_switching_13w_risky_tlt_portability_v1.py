from __future__ import annotations

from strategy_lab.research_os.universe_expansion.paired_switching_13w_risky_tlt_portability_v1 import run


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2, sort_keys=True))
