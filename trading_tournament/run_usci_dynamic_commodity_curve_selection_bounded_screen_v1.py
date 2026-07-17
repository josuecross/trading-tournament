from __future__ import annotations

import json

from strategy_lab.research_os.research.usci_dynamic_commodity_curve_selection_bounded_screen_v1 import (
    clean_value,
    run,
)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
