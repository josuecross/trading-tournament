from __future__ import annotations

import json

from strategy_lab.research_os.research import etf_pairs_short_accounting_resolution_v1 as resolution


if __name__ == "__main__":
    print(json.dumps(resolution.run(), indent=2, sort_keys=True))
