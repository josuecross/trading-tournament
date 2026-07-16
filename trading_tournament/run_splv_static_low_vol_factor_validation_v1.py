from __future__ import annotations

import json

from strategy_lab.research_os.research import splv_static_low_vol_factor_validation_v1 as validation


if __name__ == "__main__":
    print(json.dumps(validation.run(), indent=2, sort_keys=True))
