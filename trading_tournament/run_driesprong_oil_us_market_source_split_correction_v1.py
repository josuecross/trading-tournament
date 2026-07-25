from __future__ import annotations

import json

from strategy_lab.research_os.research.driesprong_oil_us_market_source_split_correction_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "task_id": result["task_id"],
                "outcome": result["outcome"],
                "valid_regression_pair_count": result.get("valid_regression_pair_count", 0),
                "estimation_count": result.get("estimation_count", 0),
                "evaluation_count": result.get("evaluation_count", 0),
                "market_state_count": result.get("market_state_count", 0),
                "risk_free_state_count": result.get("risk_free_state_count", 0),
                "switch_count": result.get("switch_count", 0),
                "trade_management_onboarding_state": result.get("trade_management_onboarding_state", ""),
                "existing_variant_artifacts_preserved": result["existing_variant_artifacts_preserved"],
                "consistency_passed": result["consistency_passed"],
                "next_action": result["next_action"],
            },
            indent=2,
            sort_keys=True,
        )
    )
