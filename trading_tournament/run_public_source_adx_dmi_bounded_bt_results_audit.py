from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_results_audit import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
