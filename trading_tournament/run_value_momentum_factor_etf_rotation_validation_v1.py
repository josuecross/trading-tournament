from __future__ import annotations

import json

from strategy_lab.research_os.research import value_momentum_factor_etf_rotation_validation_v1 as validation


if __name__ == "__main__":
    print(json.dumps(validation.run(), indent=2, sort_keys=True, default=validation.clean_value))
