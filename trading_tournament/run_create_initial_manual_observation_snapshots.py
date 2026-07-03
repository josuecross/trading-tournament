from strategy_lab.research_os.operations.initial_manual_snapshots import run


if __name__ == "__main__":
    result = run()
    print(f"initial_manual_snapshots_output={result['output_dir']}")
    print(f"vm_initial_snapshot_created={result['vm_initial_snapshot_created']}")
    print(f"dsr_initial_snapshot_created={result['dsr_initial_snapshot_created']}")
    print(f"manual_input_required={result['manual_input_required']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")
