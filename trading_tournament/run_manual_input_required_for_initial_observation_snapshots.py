from strategy_lab.research_os.operations.manual_input_snapshot_validation import run


if __name__ == "__main__":
    result = run()
    print(f"manual_input_snapshot_output={result['output_dir']}")
    print(f"manual_values_supplied={result['manual_values_supplied']}")
    print(f"vm_snapshot_status={result['vm_snapshot_status']}")
    print(f"dsr_snapshot_status={result['dsr_snapshot_status']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
