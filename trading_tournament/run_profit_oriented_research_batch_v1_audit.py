from strategy_lab.research_os.research.profit_oriented_research_batch_v1_audit import run


if __name__ == "__main__":
    result = run()
    print(f"profit_batch_v1_audit_output={result['output_dir']}")
    print(f"methodology_valid={result['methodology_valid']}")
    print(f"exposure_weighting_issue_found={result['exposure_weighting_issue_found']}")
    print(f"cash_bil_issue_found={result['cash_bil_issue_found']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
