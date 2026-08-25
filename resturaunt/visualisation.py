from __future__ import annotations

import functools
import http.server
import json
import threading
import webbrowser
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _normalise_order(order: dict[str, Any], tick: int) -> dict[str, Any]:
    created_tick = order.get("created_at_tick")
    if created_tick is None:
        created_tick = order.get("created_at")
        if isinstance(created_tick, str):
            try:
                created_tick = int(created_tick)
            except ValueError:
                created_tick = tick
    try:
        created_tick = int(created_tick)
    except (TypeError, ValueError):
        created_tick = tick

    age_ticks = max(0, tick - created_tick)
    item_name = str(order.get("item") or "hotdog").strip() or "hotdog"
    image_name = str(order.get("image") or "").strip() or f"{item_name.lower().replace(' ', '')}.png"
    return {
        "order_id": order.get("order_id", f"order-{created_tick}"),
        "created_at_tick": created_tick,
        "age_ticks": age_ticks,
        "priority": age_ticks + 1,
        "item": item_name,
        "image": f"./media/{image_name}",
    }


def build_dashboard_snapshot(
    tick: int,
    cash_history: list[float | int] | None = None,
    revenue_history: list[float | int] | None = None,
    profit_history: list[float | int] | None = None,
    stock_rows: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cash_list = [float(x) for x in (cash_history or [])]
    revenue_list = [float(x) for x in (revenue_history or [])]
    profit_list = [float(x) for x in (profit_history or [])]

    current_cash = cash_list[-1] if cash_list else 0.0
    stock_entries: list[dict[str, Any]] = []
    for row in stock_rows or []:
        ingredient = str(row.get("ingredient", "")).strip()
        if not ingredient or ingredient.lower() == "cash":
            continue
        qty = _as_float(row.get("qty"), 0.0)
        target = _as_float(row.get("reorder_threshold"), 0.0)
        stock_entries.append(
            {
                "ingredient": ingredient,
                "qty": qty,
                "target": target,
                "gap": max(0.0, target - qty),
                "status": "low" if qty <= target else "healthy",
            }
        )
    stock_entries.sort(key=lambda item: (item["qty"] <= item["target"], item["qty"]))

    waiting_orders = [_normalise_order(order, tick) for order in (orders or [])]
    waiting_orders.sort(key=lambda item: item["age_ticks"], reverse=True)

    return {
        "tick": tick,
        "cash": {
            "current": current_cash,
            "history": cash_list,
            "revenue": revenue_list,
            "profit": profit_list,
        },
        "stock": stock_entries,
        "waiting_orders": waiting_orders,
    }


def _render_cash_figure(snapshot: dict[str, Any]) -> go.Figure:
    cash_trace = snapshot["cash"]["history"]
    revenue_trace = snapshot["cash"]["revenue"]
    profit_trace = snapshot["cash"]["profit"]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=list(range(len(cash_trace))), y=cash_trace, mode="lines+markers", name="cash", line=dict(color="#2ECC71", width=4)), secondary_y=False)
    if revenue_trace:
        fig.add_trace(go.Scatter(x=list(range(len(revenue_trace))), y=revenue_trace, mode="lines+markers", name="revenue", line=dict(color="#00A8E8", width=3), marker=dict(size=7)), secondary_y=True)
    if profit_trace:
        fig.add_trace(go.Scatter(x=list(range(len(profit_trace))), y=profit_trace, mode="lines+markers", name="profit", line=dict(color="#FF7F50", width=3), marker=dict(size=7)), secondary_y=True)

    fig.update_layout(
        title="Cash, revenue and profit",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#E2E8F0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color="#E2E8F0")),
        margin=dict(l=30, r=30, t=50, b=30),
        height=300,
    )
    fig.update_xaxes(title_text="tick", title_font=dict(color="#E2E8F0"), tickfont=dict(color="#E2E8F0"), gridcolor="#1f2937", zerolinecolor="#334155")
    fig.update_yaxes(title_text="cash", title_font=dict(color="#E2E8F0"), tickfont=dict(color="#E2E8F0"), gridcolor="#1f2937", zerolinecolor="#334155", secondary_y=False)
    fig.update_yaxes(title_text="cash flow", title_font=dict(color="#E2E8F0"), tickfont=dict(color="#E2E8F0"), gridcolor="#1f2937", zerolinecolor="#334155", secondary_y=True)
    return fig


def _render_stock_figure(snapshot: dict[str, Any]) -> go.Figure:
    stock_items = snapshot["stock"]
    if not stock_items:
        fig = go.Figure()
        fig.add_annotation(text="No stock lines yet", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    ingredients = [item["ingredient"] for item in stock_items]
    qty = [item["qty"] for item in stock_items]
    target = [item["target"] for item in stock_items]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=ingredients, y=qty, name="stock", marker_color="#7BD389"))
    fig.add_trace(go.Scatter(x=ingredients, y=target, mode="lines+markers", name="target", line=dict(color="#FFB703", width=3), marker=dict(size=10)))
    fig.update_layout(
        title="Stock vs target",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#E2E8F0"),
        barmode="group",
        height=300,
        margin=dict(l=20, r=20, t=50, b=80),
    )
    fig.update_yaxes(title_text="qty", title_font=dict(color="#E2E8F0"), tickfont=dict(color="#E2E8F0"), gridcolor="#1f2937", zerolinecolor="#334155")
    fig.update_xaxes(title_text="ingredient", title_font=dict(color="#E2E8F0"), tickfont=dict(color="#E2E8F0"), gridcolor="#1f2937", zerolinecolor="#334155")
    return fig


def _render_waiting_orders_figure(snapshot: dict[str, Any]) -> go.Figure:
    waiting = snapshot["waiting_orders"]
    if not waiting:
        fig = go.Figure()
        fig.add_annotation(text="No waiting orders", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    fig = go.Figure()
    y_positions = list(range(len(waiting), 0, -1))

    for idx, item in enumerate(waiting):
        age = int(item["age_ticks"])
        color = "#22c55e" if age <= 2 else "#f59e0b" if age <= 5 else "#ef4444"
        y = y_positions[idx]
        image_path = item.get("image") or "./media/hotdog.png"

        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=-0.8,
            x1=0.8,
            y0=y - 0.45,
            y1=y + 0.45,
            line=dict(color=color, width=4),
            fillcolor="rgba(0,0,0,0)",
            layer="below",
        )
        fig.add_layout_image(
            dict(
                source=image_path,
                xref="x",
                yref="y",
                x=0,
                y=y,
                sizex=0.75,
                sizey=0.75,
                xanchor="center",
                yanchor="middle",
                sizing="contain",
                opacity=1,
                layer="above",
            )
        )
        fig.add_annotation(
            text=f"{age} ticks",
            x=0,
            y=y + 0.55,
            xref="x",
            yref="y",
            showarrow=False,
            font=dict(color="#F8FAFC", size=11),
            xanchor="center",
            yanchor="bottom",
        )

    fig.update_layout(
        title="Waiting orders",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#E2E8F0"),
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(visible=False, range=[-1, 1], showgrid=False, zeroline=False, showline=False),
        yaxis=dict(visible=False, range=[0, len(waiting) + 1], showgrid=False, zeroline=False, showline=False),
    )
    return fig


def _render_kitchen_tasks_figure(snapshot: dict[str, Any]) -> go.Figure:
    fig = go.Figure(
        data=[go.Table(
            header=dict(values=["Kitchen tasks", "Status"], fill_color="#1f2937", line_color="#374151", font=dict(color="white")),
            cells=dict(values=[["None yet"], ["not implemented"]], fill_color="#111827", line_color="#374151", font=dict(color="#E5E7EB")),
        )]
    )
    fig.update_layout(
        title="Active kitchen tasks",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#E2E8F0"),
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def render_dashboard_html(snapshot: dict[str, Any]) -> str:
    snapshot_json = json.dumps(snapshot)
    fig_cash = _render_cash_figure(snapshot)
    fig_stock = _render_stock_figure(snapshot)
    fig_waiting = _render_waiting_orders_figure(snapshot)
    fig_tasks = _render_kitchen_tasks_figure(snapshot)

    cash_json = json.dumps(fig_cash.to_dict())
    stock_json = json.dumps(fig_stock.to_dict())
    waiting_json = json.dumps(fig_waiting.to_dict())
    tasks_json = json.dumps(fig_tasks.to_dict())

    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Restaurant Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
        <style>
          body {{
            background: #0b1020;
            color: #f5f7fb;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
          }}
          h1 {{
            margin-bottom: 8px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #7bd389;
          }}
          .subtitle {{
            color: #cbd5e1;
            margin-bottom: 20px;
          }}
          .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
          }}
          .panel {{
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 14px;
            padding: 12px;
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.5);
          }}
          .header {{
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 12px;
          }}
          .pill {{
            background: linear-gradient(135deg, #22c55e, #1d4ed8);
            color: white;
            border-radius: 999px;
            padding: 6px 12px;
            font-weight: bold;
          }}
        </style>
      </head>
      <body>
        <div class="header">
          <div>
            <h1>Restaurant Ops Dashboard</h1>
            <div class="subtitle">tick {snapshot['tick']} · cash: {snapshot['cash']['current']:.2f} DanBucks</div>
          </div>
          <div class="pill">live</div>
        </div>
        <div class="grid">
          <div class="panel"><div id="cash-plot"></div></div>
          <div class="panel"><div id="stock-plot"></div></div>
          <div class="panel"><div id="waiting-plot"></div></div>
          <div class="panel"><div id="tasks-plot"></div></div>
        </div>
        <script>
          const initialSnapshot = {snapshot_json};

          function buildCashFigure(snapshot) {{
            const x = snapshot.cash.history.map((_, index) => index);
            const data = [
              {{ type: 'scatter', x, y: snapshot.cash.history, mode: 'lines+markers', name: 'cash', line: {{ color: '#2ECC71', width: 4 }} }},
            ];
            if (snapshot.cash.revenue.length) {{
              data.push({{ type: 'scatter', x: snapshot.cash.revenue.map((_, index) => index), y: snapshot.cash.revenue, mode: 'lines+markers', name: 'revenue', yaxis: 'y2', line: {{ color: '#00A8E8', width: 3 }}, marker: {{ size: 7 }} }});
            }}
            if (snapshot.cash.profit.length) {{
              data.push({{ type: 'scatter', x: snapshot.cash.profit.map((_, index) => index), y: snapshot.cash.profit, mode: 'lines+markers', name: 'profit', yaxis: 'y2', line: {{ color: '#FF7F50', width: 3 }}, marker: {{ size: 7 }} }});
            }}
            return {{
              data,
              layout: {{
                title: 'Cash, revenue and profit',
                template: 'plotly_dark',
                paper_bgcolor: '#0f172a',
                plot_bgcolor: '#0f172a',
                font: {{ color: '#E2E8F0' }},
                height: 300,
                margin: {{ l: 30, r: 30, t: 50, b: 30 }},
                xaxis: {{ title: 'tick', gridcolor: '#1f2937', tickfont: {{ color: '#E2E8F0' }}, titlefont: {{ color: '#E2E8F0' }} }},
                yaxis: {{ title: 'cash', gridcolor: '#1f2937', tickfont: {{ color: '#E2E8F0' }}, titlefont: {{ color: '#E2E8F0' }} }},
                yaxis2: {{ title: 'cash flow', overlaying: 'y', side: 'right', gridcolor: '#1f2937', tickfont: {{ color: '#E2E8F0' }}, titlefont: {{ color: '#E2E8F0' }} }},
                legend: {{ orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'left', x: 0, font: {{ color: '#E2E8F0' }} }}
              }}
            }};
          }}

          function buildStockFigure(snapshot) {{
            const items = snapshot.stock || [];
            const data = [
              {{ type: 'bar', x: items.map(item => item.ingredient), y: items.map(item => item.qty), name: 'stock', marker: {{ color: '#7BD389' }} }},
              {{ type: 'scatter', x: items.map(item => item.ingredient), y: items.map(item => item.target), mode: 'lines+markers', name: 'target', line: {{ color: '#FFB703', width: 3 }}, marker: {{ size: 10 }} }}
            ];
            return {{
              data,
              layout: {{
                title: 'Stock vs target',
                template: 'plotly_dark',
                paper_bgcolor: '#0f172a',
                plot_bgcolor: '#0f172a',
                font: {{ color: '#E2E8F0' }},
                barmode: 'group',
                height: 300,
                margin: {{ l: 20, r: 20, t: 50, b: 80 }},
                xaxis: {{ title: 'ingredient', gridcolor: '#1f2937', tickfont: {{ color: '#E2E8F0' }}, titlefont: {{ color: '#E2E8F0' }} }},
                yaxis: {{ title: 'qty', gridcolor: '#1f2937', tickfont: {{ color: '#E2E8F0' }}, titlefont: {{ color: '#E2E8F0' }} }}
              }}
            }};
          }}

          function buildWaitingFigure(snapshot) {{
            const items = snapshot.waiting_orders || [];
            if (!items.length) {{
              return {{ data: [{{ type: 'scatter', x: [], y: [], mode: 'markers' }}], layout: {{ title: 'Waiting orders', template: 'plotly_dark', height: 300, margin: {{ l: 20, r: 20, t: 50, b: 80 }} }} }};
            }}
            const imageMap = {{
              hotdog: './media/hotdog.png',
              burger: './media/burger.png'
            }};
            const yPositions = items.map((_, index) => items.length - index);
            const images = items.map((item, index) => ({{
              source: (item.image || imageMap[(item.item || 'hotdog').toLowerCase().replace(/\s+/g, '')] || './media/hotdog.png'),
              xref: 'x',
              yref: 'y',
              x: 0,
              y: yPositions[index],
              sizex: 0.75,
              sizey: 0.75,
              xanchor: 'center',
              yanchor: 'middle',
              sizing: 'contain',
              opacity: 1,
              layer: 'above'
            }}));
            const shapes = items.map((item, index) => ({{
              type: 'rect',
              xref: 'x',
              yref: 'y',
              x0: -0.8,
              x1: 0.8,
              y0: yPositions[index] - 0.45,
              y1: yPositions[index] + 0.45,
              line: {{ color: item.age_ticks <= 2 ? '#22c55e' : item.age_ticks <= 5 ? '#f59e0b' : '#ef4444', width: 4 }},
              fillcolor: 'rgba(255,255,255,0)',
              layer: 'below'
            }}));
            const annotations = items.map((item, index) => ({{
              x: 0,
              y: yPositions[index] + 0.55,
              xref: 'x',
              yref: 'y',
              text: item.age_ticks + ' ticks',
              showarrow: false,
              font: {{ color: '#F8FAFC', size: 11 }},
              xanchor: 'center',
              yanchor: 'bottom'
            }}));
            return {{
              data: [{{ type: 'scatter', x: [0], y: [0], mode: 'markers', hoverinfo: 'skip', marker: {{ size: 0, opacity: 0 }}, showlegend: false }}],
              layout: {{
                title: 'Waiting orders',
                template: 'plotly_dark',
                paper_bgcolor: '#0f172a',
                plot_bgcolor: '#0f172a',
                font: {{ color: '#E2E8F0' }},
                height: 300,
                margin: {{ l: 20, r: 20, t: 50, b: 20 }},
                xaxis: {{ visible: false, range: [-1, 1], showgrid: false, zeroline: false, showline: false }},
                yaxis: {{ visible: false, range: [0, items.length + 1], showgrid: false, zeroline: false, showline: false }},
                images: images,
                annotations: annotations,
                shapes: shapes
              }}
            }};
          }}

          function buildTasksFigure() {{
            return {{
              data: [{{
                type: 'table',
                header: {{ values: ['Kitchen tasks', 'Status'], fill: {{ color: '#1f2937' }}, line: {{ color: '#374151' }}, font: {{ color: 'white' }} }},
                cells: {{ values: [['None yet'], ['not implemented']], fill: {{ color: '#111827' }}, line: {{ color: '#374151' }}, font: {{ color: '#E5E7EB' }} }}
              }}],
              layout: {{ title: 'Active kitchen tasks', template: 'plotly_dark', paper_bgcolor: '#0f172a', plot_bgcolor: '#0f172a', font: {{ color: '#E2E8F0' }}, height: 300, margin: {{ l: 20, r: 20, t: 50, b: 20 }} }}
            }};
          }}

          function applySnapshot(snapshot) {{
            const cashFigure = buildCashFigure(snapshot);
            const stockFigure = buildStockFigure(snapshot);
            const waitingFigure = buildWaitingFigure(snapshot);
            const tasksFigure = buildTasksFigure();

            Plotly.react('cash-plot', cashFigure.data, cashFigure.layout);
            Plotly.react('stock-plot', stockFigure.data, stockFigure.layout);
            Plotly.react('waiting-plot', waitingFigure.data, waitingFigure.layout);
            Plotly.react('tasks-plot', tasksFigure.data, tasksFigure.layout);

            const subtitle = document.querySelector('.subtitle');
            if (subtitle) {{
              subtitle.textContent = 'tick ' + snapshot.tick + ' · cash: ' + snapshot.cash.current.toFixed(2) + ' DanBucks';
            }}
          }}

          Plotly.newPlot('cash-plot', buildCashFigure(initialSnapshot).data, buildCashFigure(initialSnapshot).layout, {{ responsive: true }});
          Plotly.newPlot('stock-plot', buildStockFigure(initialSnapshot).data, buildStockFigure(initialSnapshot).layout, {{ responsive: true }});
          Plotly.newPlot('waiting-plot', buildWaitingFigure(initialSnapshot).data, buildWaitingFigure(initialSnapshot).layout, {{ responsive: true }});
          Plotly.newPlot('tasks-plot', buildTasksFigure().data, buildTasksFigure().layout, {{ responsive: true }});

          async function refreshDashboard() {{
            try {{
              const response = await fetch('restaurant_dashboard.json', {{ cache: 'no-store' }});
              if (!response.ok) {{
                return;
              }}
              const snapshot = await response.json();
              applySnapshot(snapshot);
            }} catch (error) {{
              console.warn('dashboard poll failed', error);
            }}
          }}

          setInterval(refreshDashboard, 1000);
          window.addEventListener('resize', () => {{
            Plotly.Plots.resize('cash-plot');
            Plotly.Plots.resize('stock-plot');
            Plotly.Plots.resize('waiting-plot');
            Plotly.Plots.resize('tasks-plot');
          }});
        </script>
      </body>
    </html>
    """


class RestaurantDashboard:
    def __init__(self, output_path: str | Path = "restaurant_dashboard.html", auto_open: bool = True):
        self.output_path = Path(output_path)
        self.json_path = self.output_path.with_suffix(".json")
        self.auto_open = auto_open
        self._opened = False
        self.url = None
        self._server = None
        self._start_server()

    def _start_server(self) -> None:
        if self._server is not None:
            return

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(Path.cwd()))
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{port}/{self.output_path.name}"

    def update(self, snapshot: dict[str, Any]) -> Path:
        html = render_dashboard_html(snapshot)
        self.output_path.write_text(html, encoding="utf-8")
        self.json_path.write_text(json.dumps(snapshot), encoding="utf-8")
        if self.auto_open and not self._opened:
            try:
                webbrowser.open(self.url)
                self._opened = True
            except Exception:
                pass
        return self.output_path

    def show(self, snapshot: dict[str, Any]) -> Path:
        return self.update(snapshot)
