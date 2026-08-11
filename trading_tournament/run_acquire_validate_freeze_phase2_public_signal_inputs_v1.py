from __future__ import annotations

import json

from strategy_lab.research_os.research.acquire_validate_freeze_phase2_public_signal_inputs_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
