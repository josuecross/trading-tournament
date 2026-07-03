from strategy_lab.research_os.research.profit_oriented_research_batch_v1_after_methodology_fix_audit import run


if __name__ == "__main__":
    result = run()
    print(f"corrected_batch_audit_output={result['output_dir']}")
    print(f"batch_id_audited={result['batch_id_audited']}")
    print(f"methodology_fix_accepted={result['methodology_fix_accepted']}")
    print(f"exposure_weighting_issue_resolved={result['exposure_weighting_issue_resolved']}")
    print(f"cash_bil_issue_resolved={result['cash_bil_issue_resolved']}")
    print(f"return_benchmark_interpretation_valid={result['return_benchmark_interpretation_valid']}")
    print(f"scoring_labeling_valid={result['scoring_labeling_valid']}")
    print(f"deeper_research_family_count_accepted={result['deeper_research_family_count_accepted']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
