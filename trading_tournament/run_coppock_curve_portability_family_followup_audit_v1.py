from __future__ import annotations

import json

from strategy_lab.research_os.research.coppock_curve_portability_family_followup_audit_v1 import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))

