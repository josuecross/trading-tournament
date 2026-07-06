from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_coppock_intake_evidence_consistency import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "coppock_yaml_valid": result["coppock_yaml_valid"],
                "larry_connors_yaml_change_report": result["larry_connors_yaml_change_report"],
                "candidate_specific_evidence_valid": result["candidate_specific_evidence_valid"],
                "generic_bridge_blank_intake_expected": result["generic_bridge_blank_intake_expected"],
                "eligibility_decision": result["eligibility_decision"],
                "verification_decision": result["verification_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
