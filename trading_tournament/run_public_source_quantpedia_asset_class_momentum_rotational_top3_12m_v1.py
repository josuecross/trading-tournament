from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_quantpedia_asset_class_momentum_rotational_top3_12m_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
