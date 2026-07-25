from __future__ import annotations

import json

from strategy_lab.research_os.research.driesprong_oil_signal_control_strength_audit_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
