from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_phase_checkpoint import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "checkpoint_status": result["checkpoint_status"],
                "candidate_count": result["candidate_count"],
                "stale_next_action_pointer_count": result["stale_next_action_pointer_count"],
                "state_files_updated": result["state_files_updated"],
                "dirty_worktree_item_count": result["dirty_worktree_item_count"],
                "new_public_source_selected_by_codex": result["new_public_source_selected_by_codex"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
