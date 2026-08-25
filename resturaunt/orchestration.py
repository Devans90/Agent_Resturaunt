# high level orchestration of the restaurant, including the kitchen, waiters, and customers. 
# This is where the main loop of the restaurant will be implemented.

#TODO initilse the files by copying the files from the resturaunt_files directory to the current working directory.

import csv
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from resturaunt.agents.core import TickAction, TickActionType, TickAgent, TickContext
from resturaunt.agents.customer import CustomerAgent
from resturaunt.agents.stocker import StockerAgent
from resturaunt.visualisation import RestaurantDashboard, build_dashboard_snapshot

# delete any existing resturaunt_files directory and copy the resturaunt_files_intialisation directory from the root of the project to the current working directory.
if os.path.exists("resturaunt_files"):
    shutil.rmtree("resturaunt_files")
shutil.copytree("resturaunt_files_initialisation", "resturaunt_files")

class RestaurantOrchestrator:
    def __init__(self, agents: list[TickAgent], show_dashboard: bool = True):
        self.agents = agents
        self.tick = 0
        self.tick_cost = 1000  # minimum time cost for each tick in milliseconds
        self.agents = agents
        self.busy_until_tick: dict[str, int] = {}
        self.orders_csv_path = Path("resturaunt_files") / "orders.csv"
        self.cash_history: list[float] = []
        self.revenue_history: list[float] = []
        self.profit_history: list[float] = []
        self.dashboard = RestaurantDashboard(output_path="restaurant_dashboard.html", auto_open=show_dashboard) if show_dashboard else None
        self._record_cash_tick()

    def _read_stock_rows(self) -> list[dict[str, str]]:
        stock_path = Path("resturaunt_files") / "stock.csv"
        if not stock_path.exists():
            return []
        with stock_path.open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _read_orders_rows(self) -> list[dict[str, object]]:
        if not self.orders_csv_path.exists():
            return []
        with self.orders_csv_path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        records: list[dict[str, object]] = []
        for row in rows:
            order_id = row.get("order_id")
            item_name = (row.get("item") or "").strip()
            image_name = (row.get("image") or "").strip()
            if not image_name and item_name:
                recipe_path = Path("resturaunt_files") / "recipe_lists.csv"
                if recipe_path.exists():
                    with recipe_path.open("r", newline="", encoding="utf-8") as recipe_handle:
                        for recipe_row in csv.DictReader(recipe_handle):
                            if (recipe_row.get("menu_item") or "").strip().lower() == item_name.lower():
                                image_name = (recipe_row.get("image") or "").strip()
                                break
            created_tick_value = row.get("created_at_tick")
            created_tick = None
            if created_tick_value is not None and str(created_tick_value).strip():
                try:
                    created_tick = int(float(str(created_tick_value).strip()))
                except ValueError:
                    created_tick = None
            if created_tick is None:
                created_at = row.get("created_at")
                if isinstance(created_at, str):
                    created_at = created_at.strip()
                    if created_at.endswith("Z"):
                        created_at = created_at[:-1] + "+00:00"
                    try:
                        created_at_dt = datetime.fromisoformat(created_at)
                        if created_at_dt.tzinfo is None:
                            created_at_dt = created_at_dt.replace(tzinfo=UTC)
                        age_seconds = max(0, int((datetime.now(UTC) - created_at_dt).total_seconds()))
                        created_tick = max(0, self.tick - age_seconds)
                    except ValueError:
                        created_tick = 0
            if created_tick is None:
                created_tick = 0
            record = {"order_id": order_id, "created_at_tick": int(created_tick), "item": item_name, "image": image_name}
            records.append(record)
        return records

    def _record_cash_tick(self) -> None:
        stock_rows = self._read_stock_rows()
        cash_row = next(
            (row for row in stock_rows if (row.get("ingredient") or "").strip().lower() == "cash"),
            {"qty": "0"},
        )
        cash_value = float((cash_row.get("qty") or 0.0))
        self.cash_history.append(cash_value)
        if len(self.cash_history) > 1:
            delta = self.cash_history[-1] - self.cash_history[-2]
            self.revenue_history.append(max(0.0, delta))
            self.profit_history.append(max(0.0, delta * 0.5))
        else:
            self.revenue_history.append(0.0)
            self.profit_history.append(0.0)

    def _update_dashboard(self) -> None:
        if self.dashboard is None:
            return
        snapshot = build_dashboard_snapshot(
            tick=self.tick,
            cash_history=self.cash_history,
            revenue_history=self.revenue_history,
            profit_history=self.profit_history,
            stock_rows=self._read_stock_rows(),
            orders=self._read_orders_rows(),
        )
        self.dashboard.update(snapshot)

    def run(self, max_ticks: int = 1000):
        """Run the restaurant simulation for a given number of ticks."""
        while self.tick < max_ticks:
            ctx = TickContext(tick=self.tick, state={"busy_until_tick": dict(self.busy_until_tick)})

            # Let each agent decide what to do for this tick.
            for agent in self.agents:
                busy_until = self.busy_until_tick.get(agent.name, -1)
                if self.tick < busy_until:
                    continue

                result = agent.on_tick(ctx)
                for action in result.actions:
                    if self._is_actor_busy(action.actor):
                        continue
                    self.execute_action(action)

            self._record_cash_tick()
            self._update_dashboard()
            self.tick += 1

    def _is_actor_busy(self, actor: str) -> bool:
        return self.tick < self.busy_until_tick.get(actor, -1)

    def _append_order(self, payload: dict[str, object]) -> None:
        """Append a new active order row to orders.csv."""
        fieldnames = ["order_id", "status", "item", "qty", "optional_toppings", "image", "created_at", "created_at_tick"]
        image_name = str(payload.get("image") or "").strip()
        if not image_name:
            item_name = str(payload.get("item") or "").strip()
            if item_name:
                recipe_path = Path("resturaunt_files") / "recipe_lists.csv"
                if recipe_path.exists():
                    with recipe_path.open("r", newline="", encoding="utf-8") as recipe_handle:
                        for recipe_row in csv.DictReader(recipe_handle):
                            if (recipe_row.get("menu_item") or "").strip().lower() == item_name.lower():
                                image_name = (recipe_row.get("image") or "").strip()
                                break
        order_row = {
            "order_id": payload.get("order_id", ""),
            "status": payload.get("status", "active"),
            "item": payload.get("item", ""),
            "qty": payload.get("qty", 1),
            "optional_toppings": payload.get("optional_toppings", ""),
            "image": image_name,
            "created_at": payload.get("created_at", ""),
            "created_at_tick": payload.get("created_at_tick", self.tick),
        }

        file_exists = self.orders_csv_path.exists()
        with self.orders_csv_path.open("a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(order_row)

    def execute_action(self, action: TickAction):
        """Execute the given action and reserve the actor for the action duration."""
        duration = max(0, action.duration_ticks)
        self.busy_until_tick[action.actor] = self.tick + duration

        if action.action_type == TickActionType.NOOP:
            return  # No operation, just reserve the actor for the duration.

        if action.action_type == TickActionType.ADD_ORDER:
            self._append_order(action.payload)
            print(f"tick={self.tick} added order: {action.payload}")
            return

        if action.action_type == TickActionType.BUY_STOCK:
            low_stock = action.payload.get("low_stock", [])

            if not low_stock:
                print(f"tick={self.tick} no low stock items to buy.")
                return

            stock_items = ", ".join([f"{item['ingredient']} (qty: {item['qty']})" for item in low_stock])
            print(f"tick={self.tick} buying stock for low stock items: {stock_items}")

            stock_path = Path("resturaunt_files") / "stock.csv"
            prices_path = Path("resturaunt_files") / "price_quantity_list.csv"

            with stock_path.open("r", newline="", encoding="utf-8") as f:
                stock_rows = list(csv.DictReader(f))

            with prices_path.open("r", newline="", encoding="utf-8") as f:
                price_rows = list(csv.DictReader(f))

            price_map = {
                    (row.get("sku") or "").strip().lower(): row
                    for row in price_rows
                    if (row.get("sku") or "").strip()
                }

            stock_map = {
                (row.get("ingredient") or "").strip().lower(): row
                for row in stock_rows
                if (row.get("ingredient") or "").strip()
            }

            cash_row = next(
                (
                    row
                    for row in stock_rows
                    if (row.get("ingredient") or "").strip().lower() == "cash"
                ),
                None,
            )

            # INITIALISE CASH ROW IF NOT PRESENT
            if cash_row is None:
                cash_row = {"ingredient": "cash", "qty": "0", "unit": "DanBucks", "reorder_threshold": "0"}
                stock_rows.append(cash_row)

            # actual stock buying logic
            for item in low_stock:
                ingredient = str(item.get("ingredient", "")).strip()
                if not ingredient:
                    continue

                key = ingredient.lower()
                price_row = price_map.get(key)
                if price_row is None:
                    print(f"tick={self.tick} cannot buy stock for {ingredient}, not in price list.")
                    continue

                stock_row = stock_map.get(key)
                if stock_row is None:
                    stock_row = {
                        "ingredient": ingredient,
                        "qty": "0",
                        "unit": item.get("unit", ""),
                        "reorder_threshold": str(item.get("reorder_threshold", 0)),
                    }
                    stock_rows.append(stock_row)
                    stock_map[key] = stock_row

                pack_qty = float((price_row.get("pack_qty") or 0))
                pack_price = float((price_row.get("pack_price") or 0))
                current_qty = float((stock_row.get("qty") or 0))
                current_cash = float((cash_row.get("qty") or 0))

                if current_cash < pack_price:
                    # just going to go into debt for now
                    print("The debt cometh....")

                # buy one pack to restock
                stock_row["qty"] = str(current_qty + pack_qty)
                cash_row["qty"] = str(current_cash - pack_price)
                print(f"tick={self.tick} bought {pack_qty} {ingredient} for {pack_price} DanBucks")

            with stock_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["ingredient", "qty", "unit", "reorder_threshold"])
                writer.writeheader()
                writer.writerows(stock_rows)

            for agent in self.agents:
                if isinstance(agent, StockerAgent):
                    agent.need_stock = False
                    agent.low_stock_snapshot = []
            return
            


# iniitialise the loop
tick = 0
tick_cost = 1000 # minimum time cost for each tick in milliseconds


restaurant_orchestrator = RestaurantOrchestrator(agents=[CustomerAgent(), StockerAgent()])
restaurant_orchestrator.run(max_ticks=1000)