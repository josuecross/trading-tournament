from __future__ import annotations

import json

from strategy_lab.research_os.research.commodity_basket_local_cache_revalidation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "family_id": result["family_id"],
                "lane_id": result["lane_id"],
                "missing_symbols": result["missing_symbols"],
                "restored_symbols": result["restored_symbols"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
