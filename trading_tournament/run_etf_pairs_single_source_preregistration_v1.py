from __future__ import annotations

import json

from strategy_lab.research_os.research import etf_pairs_single_source_preregistration_v1 as prereg


if __name__ == "__main__":
    print(json.dumps(prereg.run(), indent=2, sort_keys=True))
