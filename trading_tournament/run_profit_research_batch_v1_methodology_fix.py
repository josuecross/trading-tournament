from strategy_lab.research_os.research.profit_research_batch_v1_methodology_fix import run


if __name__ == "__main__":
    result = run()
    print(f"methodology_fix_output={result['output_dir']}")
    print(f"batch_id_fixed={result['batch_id_fixed']}")
    print(f"corrected_variant_count={result['corrected_variant_count']}")
    print(f"corrected_family_count={result['corrected_family_count']}")
    print(f"max_daily_exposure_after_fix={result['max_daily_exposure_after_fix']}")
    print(f"average_exposure_gt_1_count_after_fix={result['average_exposure_gt_1_count_after_fix']}")
    print(f"average_exposure_gt_2_count_after_fix={result['average_exposure_gt_2_count_after_fix']}")
    print(f"families_marked_for_deeper_research_after_fix={result['families_marked_for_deeper_research_after_fix']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
