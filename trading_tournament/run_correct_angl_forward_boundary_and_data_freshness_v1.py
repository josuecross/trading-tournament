from __future__ import annotations

import json

from strategy_lab.research_os.research.correct_angl_forward_boundary_and_data_freshness_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
