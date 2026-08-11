from __future__ import annotations

import json

from strategy_lab.research_os.research.accepted_47_targeted_internal_technical_batch_v2 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
