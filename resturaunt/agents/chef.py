

import asyncio
import csv
from typing import Any

from pydantic_ai import Agent

from resturaunt.agents.core import TickAction, TickActionType, TickContext, TickResult
from resturaunt.agents.stocker import _normalize_name


class ChefAgent:
    def __init__(
            self, 
            name: str,
            model_name: str = "llama3.1",
            ) -> None:
        self.name = name
		self.model = OllamaModel(model_name, provider=OllamaProvider(base_url=base_url)) #TODO could make this more generic as will break with others
        self.agent = Agent(
            self.model,
            system_prompt=(
                "You are a chef agent. You are a stand-in for the act of actually cooking, your job is to lookup outstanding orders, the recipes to acheive them and reduce the stock to simulate the ingredients being used." \
                "A typical flow for you will be:  Prompted with simply 'cook', Lookup outstanding orders, take the order that has been outstanding the longest, lookup the recipe/ingredients, check stock of those ingredients, reduce stock of those ingredients (indicating them being used), then moving the order from orders to completed orders, then increase the stock of cash to represent a sale  " \
                "Always call your tools first before answering any question."
            ),
        )
        self.register_tools()

        def _load_stock_rows(self) -> list[dict[str, str]]:
            with self.stock_csv.open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))

        def _load_order_rows(self) -> list[dict[str, str]]:
            with self.orders_csv.open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))             

        def _register_tools(self) -> None:
                @self.agent.tool_plain
                def list_stock() -> list[dict[str, str]]:
                    """Return all stock rows as dictionaries."""
                    return self._load_stock_rows()
        
                @self.agent.tool_plain
                def lookup_stock(item: str) -> dict[str, Any]:
                    """Return stock details for any ingredient in stock.csv."""
                    normalized_item = _normalize_name(item)
                    for row in self._load_stock_rows():
                        ingredient = (row.get("ingredient") or "").strip()
                        if _normalize_name(ingredient) == normalized_item:
                            qty_raw = (row.get("qty") or "0").strip()
                            reorder_raw = (row.get("reorder_threshold") or "0").strip()
                            return {
                                "ingredient": ingredient,
                                "qty": float(qty_raw),
                                "unit": (row.get("unit") or "").strip(),
                                "reorder_threshold": float(reorder_raw),
                            }
                    raise ValueError(f"Ingredient not found in stock.csv: {item}")
                @self.agent.tool_plain
                def lookup_orders(order_id: str) -> dict[str, str]:
                    """Return order details for a specific order_id in orders.csv."""
                    normalized_order_id = _normalize_name(order_id)
                    for row in self._load_order_rows():
                        current_order_id = (row.get("order_id") or "").strip()
                        if _normalize_name(current_order_id) == normalized_order_id:
                            return {
                                "order_id": current_order_id,
                                "item": (row.get("item") or "").strip(),
                                "qty": int((row.get("qty") or "0").strip()),
                                "optional_toppings": (row.get("optional_toppings") or "").strip(),
                                "created_at_tick": int((row.get("created_at_tick") or "0").strip()),
                            }
                    raise ValueError(f"Order not found in orders.csv: {order_id}")
                
        

        async def ask(self) -> str:
            """Ask the agent to cook the next order."""
            result = await self.agent.run("cook")
            return str(result.output)

        def on_tick(self, ctx: TickContext) -> TickResult:
            """Per tick, check for outstanding orders and cook them."""
            if ctx.orders:
                # If there are outstanding orders, ask the agent to cook the next one.
                cook_result = asyncio.run(self.ask())
                return TickResult(
                    actions=[
                        TickAction(
                            action_type=TickActionType.COOK_ORDER,
                            actor=self.name,
                            duration_ticks=5,
                            payload={"result": cook_result},
                        )
                    ],
                    logs=[f"[{self.name}] cooked an order on tick {ctx.tick}"],
                )
            else:
                return TickResult(logs=[f"[{self.name}] no orders to cook on tick {ctx.tick}"])