from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_comparative_screening_batch_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "batch_id": result["batch_id"],
                "included_lane_count": result["included_lane_count"],
                "lanes_evaluated_count": result["lanes_evaluated_count"],
                "lanes_comparable_count": result["lanes_comparable_count"],
                "benchmark_comparability_complete": result["benchmark_comparability_complete"],
                "comparative_evidence_positive_count": result["comparative_evidence_positive_count"],
                "invariant_failure_count": result["invariant_failure_count"],
                "provider_download": result["provider_download"],
                "paper_forward_activation": result["paper_forward_activation"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
