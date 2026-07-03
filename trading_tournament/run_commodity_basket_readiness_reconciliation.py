from __future__ import annotations

import json

from strategy_lab.research_os.research.commodity_basket_readiness_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "final_decision": result["final_decision"],
                "contradictions_found_count": result["contradictions_found_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
