from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_parabolic_sar_bounded_bt_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "formula_contract_version": result["formula_contract_version"],
                "variant_count_planned": result["variant_count_planned"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "primary_row_numeric_criteria_pass": result["primary_row_numeric_criteria_pass"],
                "timing_sanity_context_only": result["timing_sanity_context_only"],
                "first_valid_sar_date": result["first_valid_sar_date"],
                "first_reversal_date": result["first_reversal_date"],
                "first_tradable_signal_date": result["first_tradable_signal_date"],
                "primary_entry_count": result["primary_entry_count"],
                "primary_exit_count": result["primary_exit_count"],
                "primary_completed_round_trip_count": result["primary_completed_round_trip_count"],
                "max_daily_exposure": result["max_daily_exposure"],
                "max_daily_weight_sum": result["max_daily_weight_sum"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "results_interpretable": result["results_interpretable"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "outputs_non_promotable": result["outputs_non_promotable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
