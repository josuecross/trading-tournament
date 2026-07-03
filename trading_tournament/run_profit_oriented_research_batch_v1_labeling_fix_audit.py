from strategy_lab.research_os.research.profit_oriented_research_batch_v1_labeling_fix_audit import run


if __name__ == "__main__":
    result = run()
    print(f"labeling_fix_audit_output={result['output_dir']}")
    print(f"batch_id_audited={result['batch_id_audited']}")
    print(f"label_fix_accepted={result['label_fix_accepted']}")
    print(f"label_overcorrection_found={result['label_overcorrection_found']}")
    print(f"high_return_tactical_broad_return_evidence={result['high_return_tactical_broad_return_evidence']}")
    print(f"high_return_tactical_requires_risk_control={result['high_return_tactical_requires_risk_control']}")
    print(f"high_return_tactical_direction_supported={result['high_return_tactical_direction_supported']}")
    print(f"macro_gld_lineage_recovery_supported={result['macro_gld_lineage_recovery_supported']}")
    print(f"deeper_research_family_count_accepted_after_audit={result['deeper_research_family_count_accepted_after_audit']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
