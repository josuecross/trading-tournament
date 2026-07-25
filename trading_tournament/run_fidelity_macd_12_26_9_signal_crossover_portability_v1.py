from __future__ import annotations

import json

from strategy_lab.research_os.research.fidelity_macd_12_26_9_signal_crossover_portability_v1 import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
