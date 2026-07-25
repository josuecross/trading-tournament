from __future__ import annotations

import json

from strategy_lab.research_os.research.fast_source_library_remaining_candidates_batch_v4 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
