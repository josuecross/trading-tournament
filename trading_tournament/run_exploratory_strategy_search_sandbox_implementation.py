from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import MAX_TOTAL_FUTURE_VARIANTS, ROOT
from strategy_lab.research_os.exploratory_sandbox.sandbox_evidence import run_sandbox_implementation


def main() -> None:
    result = run_sandbox_implementation(ROOT, max_variants=MAX_TOTAL_FUTURE_VARIANTS, update_metadata=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
