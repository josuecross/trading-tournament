from __future__ import annotations

import json

from strategy_lab.research_os.research.materialize_and_resume_accepted_47_source_backed_batch_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
