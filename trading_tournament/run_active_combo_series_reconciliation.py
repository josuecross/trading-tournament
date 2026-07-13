from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.active_combo_series_reconciliation import json_safe, run_active_combo_series_reconciliation


ROOT = Path(__file__).resolve().parent


def main() -> None:
    print(json.dumps(json_safe(run_active_combo_series_reconciliation(ROOT)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
