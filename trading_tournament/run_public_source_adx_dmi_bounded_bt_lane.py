from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "formula_contract_version": result["formula_contract_version"],
                "variant_count_planned": result["variant_count_planned"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "primary_row_numeric_criteria_pass": result["primary_row_numeric_criteria_pass"],
                "timing_sanity_context_only": result["timing_sanity_context_only"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
