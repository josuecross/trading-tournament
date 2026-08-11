from __future__ import annotations

import json

from strategy_lab.research_os.research.phase2_new_group_discovery_batch_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "overall_pass": result["overall_pass"],
                "task_outcome": result["task_outcome"],
                "winner_trial_id": result["winner_trial_id"],
                "followup_count": result["followup_count"],
                "exact_next_action": result["exact_next_action"],
                "deterministic_core_hash": result["deterministic_core_hash"],
            },
            indent=2,
            sort_keys=True,
        )
    )
