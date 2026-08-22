# high level orchestration of the restaurant, including the kitchen, waiters, and customers. 
# This is where the main loop of the restaurant will be implemented.

#TODO initilse the files by copying the files from the resturaunt_files directory to the current working directory.

import csv
import os
import shutil
from pathlib import Path

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
            # TODO: Implement the logic to buy stock. For now, just print the action.
            print(f"tick={self.tick} buying stock: {action.payload}")
            return

        print(
            f"tick={self.tick} action={action.action_type} actor={action.actor} "
            f"duration={duration} payload={action.payload}"
        )

# iniitialise the loop
tick = 0
tick_cost = 1000 # minimum time cost for each tick in milliseconds


restaurant_orchestrator = RestaurantOrchestrator(agents=[CustomerAgent(), StockerAgent()])
restaurant_orchestrator.run(max_ticks=1000)