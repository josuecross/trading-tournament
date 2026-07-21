from __future__ import annotations

import json

from strategy_lab.research_os.research.fx_carry_data_and_engine_feasibility_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "strategy_id": result["strategy_id"],
                "family_id": result["family_id"],
                "feasibility_outcome": result["feasibility_outcome"],
                "evidence_dir": result["evidence_dir"],
                "strategy_implemented": result["strategy_implemented"],
                "backtest_run": result["backtest_run"],
                "provider_download": result["provider_download"],
                "exact_next_action": result["exact_next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
