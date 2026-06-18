from __future__ import annotations


def reconcile_order_statuses(client, order_ids: list[str]) -> list[dict]:
    return [client.get_order_by_id(order_id) for order_id in order_ids]
