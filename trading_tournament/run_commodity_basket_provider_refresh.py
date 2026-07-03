from __future__ import annotations

import json

from strategy_lab.research_os.research.commodity_basket_provider_refresh import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "downloaded_symbols": result["downloaded_symbols"],
                "failed_symbols": result["failed_symbols"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
