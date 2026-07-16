from __future__ import annotations

import json

from strategy_lab.research_os.research import resume_existing_ready_research_batch_v1 as batch


if __name__ == "__main__":
    print(json.dumps(batch.run(), indent=2, sort_keys=True))
