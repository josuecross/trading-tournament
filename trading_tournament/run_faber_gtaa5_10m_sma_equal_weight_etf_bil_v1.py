from __future__ import annotations

import json

from strategy_lab.research_os.research.faber_gtaa5_10m_sma_equal_weight_etf_bil_v1 import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
