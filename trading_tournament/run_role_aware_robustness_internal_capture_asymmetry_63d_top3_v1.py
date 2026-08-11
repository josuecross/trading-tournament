from __future__ import annotations

import json

from strategy_lab.research_os.research.role_aware_robustness_internal_capture_asymmetry_63d_top3_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
