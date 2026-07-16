from __future__ import annotations

import json

from strategy_lab.research_os.research import advance_near_ready_research_queue_v1 as task
from strategy_lab.research_os.research import resume_existing_ready_research_batch_v1 as ready


if __name__ == "__main__":
    print(json.dumps(task.run(), indent=2, sort_keys=True, default=ready.clean_value))
