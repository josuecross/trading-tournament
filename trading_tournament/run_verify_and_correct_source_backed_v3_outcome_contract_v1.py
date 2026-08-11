from __future__ import annotations

import json

from strategy_lab.research_os.research.verify_and_correct_source_backed_v3_outcome_contract_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
