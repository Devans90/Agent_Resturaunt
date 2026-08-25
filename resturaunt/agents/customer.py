import csv
from datetime import UTC, datetime
import random

from resturaunt.agents.core import TickAction, TickActionType, TickAgent, TickContext, TickResult

class CustomerAgent(TickAgent):
    """Customer proxy agent, that can be used to simulate customer interactions with the restaurant, including random orders based on a rng."""

    def __init__(self, name: str = "rando customer", order_chance: float = 0.01) -> None:
        self.name = name
        self.order_chance = order_chance

    def _random_order(self, order_id: int = 1) -> dict[str, str | int]:
        """Generate a random order in the same shape as orders.csv rows."""
        # Read recipes and choose one menu item.
        with open("./resturaunt_files/recipe_lists.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            recipes = [row for row in reader]
            base_choice = random.choice(recipes)

            # Parse "[cheese,mustard,ketchup]" into individual toppings.
            valid_toppings_raw = (base_choice.get("valid_optional_toppings") or "").strip()
            valid_toppings_raw = valid_toppings_raw.strip("[]")

            # Select random toppings with a 50% inclusion chance each.
            toppings = []
            for item in valid_toppings_raw.split(","):
                if random.random() < 0.5:  # 50% chance to include each topping
                    toppings.append(item.strip())

            order = {
                "order_id": order_id,
                "status": "active",
                "item": (base_choice.get("menu_item") or "").strip(),
                "qty": 1,
                "optional_toppings": ",".join([t for t in toppings if t]),
                "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "created_at_tick": ctx.tick,
            }

            # print(f"[{self.name}] generated order: {order}")

            return order

    def on_tick(self, ctx: TickContext) -> TickResult:
        """Per tick, randomly emit an ADD_ORDER action based on order_chance."""
        order_id = ctx.tick + 1

        if random.random() < self.order_chance:
            order_payload = self._random_order(order_id)
            return TickResult(
                actions=[
                    TickAction(
                        action_type=TickActionType.ADD_ORDER,
                        actor=self.name,
                        duration_ticks=20,
                        payload=order_payload,
                    )
                ],
                logs=[f"[{self.name}] new order created on tick {ctx.tick}"],
            )

        return TickResult(logs=[f"[{self.name}] no order on tick {ctx.tick}"])

