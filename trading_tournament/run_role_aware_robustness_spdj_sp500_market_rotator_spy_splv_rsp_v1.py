from __future__ import annotations

import json

from strategy_lab.research_os.research.role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "overall_pass": result["overall_pass"],
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "exact_next_action": result["exact_next_action"],
                "deterministic_core_hash": result["deterministic_core_hash"],
            },
            indent=2,
            sort_keys=True,
        )
    )
