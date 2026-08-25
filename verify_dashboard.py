from resturaunt.visualisation import build_dashboard_snapshot

snapshot = build_dashboard_snapshot(
    tick=7,
    cash_history=[50, 45, 42],
    revenue_history=[0, 4, 9],
    profit_history=[0, 2, 4],
    stock_rows=[
        {"ingredient": "cash", "qty": "42", "unit": "DanBucks", "reorder_threshold": "0"},
        {"ingredient": "hotdog", "qty": "2", "unit": "each", "reorder_threshold": "5"},
        {"ingredient": "burger", "qty": "10", "unit": "each", "reorder_threshold": "5"},
    ],
    orders=[
        {"order_id": "o1", "created_at_tick": 1},
        {"order_id": "o2", "created_at_tick": 5},
        {"order_id": "o3", "created_at_tick": 6},
    ],
)
print(snapshot["tick"])
print(snapshot["cash"]["current"])
print(snapshot["stock"][0]["ingredient"], snapshot["stock"][0]["target"])
print(snapshot["waiting_orders"][0]["age_ticks"], snapshot["waiting_orders"][0]["priority"])
