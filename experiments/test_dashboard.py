from resturaunt.visualisation import build_dashboard_snapshot, render_dashboard_html


def test_build_dashboard_snapshot_tracks_order_age_and_cash():
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

    assert snapshot["tick"] == 7
    assert snapshot["cash"]["current"] == 42
    assert snapshot["cash"]["revenue"][-1] == 9
    assert snapshot["cash"]["profit"][-1] == 4
    assert snapshot["stock"][0]["ingredient"] == "burger"
    assert snapshot["stock"][0]["target"] == 5
    assert snapshot["waiting_orders"][0]["age_ticks"] == 6
    assert snapshot["waiting_orders"][0]["priority"] > 0


def test_dashboard_html_uses_js_polling_instead_of_page_refresh():
    snapshot = build_dashboard_snapshot(
        tick=3,
        cash_history=[10, 15, 18],
        revenue_history=[0, 5, 3],
        profit_history=[0, 2, 1],
        stock_rows=[
            {"ingredient": "hotdog", "qty": "2", "unit": "each", "reorder_threshold": "5"},
            {"ingredient": "burger", "qty": "10", "unit": "each", "reorder_threshold": "5"},
        ],
        orders=[{"order_id": "o1", "created_at_tick": 1}],
    )
    html = render_dashboard_html(snapshot)
    assert "fetch(\"restaurant_dashboard.json" in html
    assert "setInterval" in html
    assert "meta http-equiv=\"refresh\"" not in html.lower()
