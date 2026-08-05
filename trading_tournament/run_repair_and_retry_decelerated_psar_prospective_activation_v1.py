from __future__ import annotations

import json
import os

from strategy_lab.research_os.research.repair_and_retry_decelerated_psar_prospective_activation_v1 import (
    finalize_after_local_error,
    run,
)


if __name__ == "__main__":
    result = (
        finalize_after_local_error()
        if os.environ.get("PSAR_REPAIR_FINALIZE_ONLY") == "1"
        else run()
    )
    print(json.dumps(result, indent=2, sort_keys=True))
