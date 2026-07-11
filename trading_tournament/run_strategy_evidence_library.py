from __future__ import annotations

from pathlib import Path

from strategy_lab.research_os.strategy_evidence_library.builder import (
    OUTPUT_DIR,
    write_strategy_evidence_library,
)


def main() -> None:
    root = Path(__file__).resolve().parent
    library = write_strategy_evidence_library(root, cleanup_generated=True)
    output = root / OUTPUT_DIR
    print(f"Strategy Evidence Library generated: {output}")
    print(f"Sources: {library['manifest']['source_records']}")
    print(f"Ideas: {library['manifest']['idea_records']}")
    print(f"Experiments: {library['manifest']['experiment_records']}")
    print(f"Generated cache directories removed: {library['manifest']['generated_cache_directories_removed']}")


if __name__ == "__main__":
    main()
