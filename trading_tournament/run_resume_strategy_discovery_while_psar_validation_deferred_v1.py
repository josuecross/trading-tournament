from __future__ import annotations

import json

from strategy_lab.research_os.research import (
    resume_strategy_discovery_while_psar_validation_deferred_v1 as task,
)


if __name__ == "__main__":
    print(json.dumps(task.run(), indent=2, sort_keys=True))
