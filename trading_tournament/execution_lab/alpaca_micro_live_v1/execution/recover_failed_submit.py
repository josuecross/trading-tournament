from __future__ import annotations


def recovery_instructions(client_order_id: str) -> dict[str, str]:
    return {
        "client_order_id": client_order_id,
        "action": "manual_review_required",
        "note": "Order submission failed or was ambiguous. Check Alpaca orders before any manual retry.",
    }

