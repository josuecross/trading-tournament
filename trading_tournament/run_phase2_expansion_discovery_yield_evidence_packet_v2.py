from __future__ import annotations

import json

from strategy_lab.research_os.research.phase2_expansion_discovery_yield_evidence_packet_v2 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
