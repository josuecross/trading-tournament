from __future__ import annotations

import json

from strategy_lab.research_os.research.rerun_fast_source_library_blocked_candidates_v3 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
