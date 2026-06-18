from __future__ import annotations


def status_label(value: bool) -> str:
    return "present" if value else "missing"

