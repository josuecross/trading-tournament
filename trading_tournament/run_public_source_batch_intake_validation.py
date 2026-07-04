from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_batch_intake_validation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "candidate_count": result["candidate_count"],
                "eligible_candidate_count": result["eligible_candidate_count"],
                "needs_direction_review_candidate_count": result["needs_direction_review_candidate_count"],
                "duplicate_or_do_not_retest_candidate_count": result["duplicate_or_do_not_retest_candidate_count"],
                "blocked_candidate_count": result["blocked_candidate_count"],
                "incomplete_candidate_count": result["incomplete_candidate_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
