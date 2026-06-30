from __future__ import annotations

import json

from strategy_lab.research_os.exploratory_sandbox.sandbox_batch_audit import ROOT, run_sandbox_batch_audit


def main() -> None:
    print(json.dumps(run_sandbox_batch_audit(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
