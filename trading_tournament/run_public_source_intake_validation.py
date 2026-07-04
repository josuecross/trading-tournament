from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_intake_validation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "candidate_file_count": result["candidate_file_count"],
                "manual_source_supplied": result["manual_source_supplied"],
                "source_id": result["source_id"],
                "eligibility_decision": result["eligibility_decision"],
                "constraint_blockers": result["constraint_blockers"],
                "family_similarity_hit_count": result["family_similarity_hit_count"],
                "local_cache_checked": result["local_cache_checked"],
                "bounded_bt_design_created": result["bounded_bt_design_created"],
                "strategy_backtest_run": result["strategy_backtest_run"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
