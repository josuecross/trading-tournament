from __future__ import annotations

import json

from strategy_lab.research_os.research.antonacci_gem_12m_global_equities_bond_v1 import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
