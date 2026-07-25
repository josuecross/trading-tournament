from __future__ import annotations

import json

from strategy_lab.research_os.research.maio_dont_fight_fed_source_rule_completion_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
