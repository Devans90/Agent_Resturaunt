# high level orchestration of the restaurant, including the kitchen, waiters, and customers. 
# This is where the main loop of the restaurant will be implemented.

#TODO initilse the files by copying the files from the resturaunt_files directory to the current working directory.

import csv
import os
import shutil
from pathlib import Path
import pandas as pd

from resturaunt.agents.core import TickAction, TickActionType, TickAgent, TickContext
from resturaunt.agents.customer import CustomerAgent
from resturaunt.agents.stocker import StockerAgent

# delete any existing resturaunt_files directory and copy the resturaunt_files_intialisation directory from the root of the project to the current working directory.
if os.path.exists("resturaunt_files"):
    shutil.rmtree("resturaunt_files")
shutil.copytree("resturaunt_files_initialisation", "resturaunt_files")

class RestaurantOrchestrator:
    def __init__(self, agents: list[TickAgent]):
        self.agents = agents
        self.tick = 0
        self.tick_cost = 1000  # minimum time cost for each tick in milliseconds
        self.agents = agents
        self.busy_until_tick: dict[str, int] = {}
        self.orders_csv_path = Path("resturaunt_files") / "orders.csv"

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

            self.tick += 1

    def _is_actor_busy(self, actor: str) -> bool:
        return self.tick < self.busy_until_tick.get(actor, -1)

    def _append_order(self, payload: dict[str, object]) -> None:
        """Append a new active order row to orders.csv."""
        fieldnames = ["order_id", "status", "item", "qty", "optional_toppings", "created_at"]
        order_row = {
            "order_id": payload.get("order_id", ""),
            "status": payload.get("status", "active"),
            "item": payload.get("item", ""),
            "qty": payload.get("qty", 1),
            "optional_toppings": payload.get("optional_toppings", ""),
            "created_at": payload.get("created_at", ""),
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