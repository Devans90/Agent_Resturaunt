from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import inflect
from pydantic_ai import Agent
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

from .core import TickAction, TickActionType, TickAgent, TickContext, TickResult

_PLURAL_ENGINE = inflect.engine()


def _default_stock_csv_path() -> Path:
	return Path(__file__).resolve().parents[2] / "resturaunt_files" / "stock.csv"


def _normalize_name(name: str) -> str:
	"""Normalize case/spacing and singularize for consistent stock matching."""
	normalized = re.sub(r"[\s_-]+", "-", (name or "").strip().lower())
	if not normalized:
		return normalized
	*head, last = normalized.split("-")
	singular = _PLURAL_ENGINE.singular_noun(last) or last
	return "-".join([*head, singular])


class StockerAgent(TickAgent):
	"""Stock lookup agent with tool wiring and tick-compatible backbone."""

	def __init__(
		self,
		model_name: str = "llama3.1",
		base_url: str = "http://localhost:11434/v1",
		stock_csv: Path | None = None,
	) -> None:
		self.name = "stocker"
		self.stock_csv = stock_csv or _default_stock_csv_path()
		self.model = OllamaModel(model_name, provider=OllamaProvider(base_url=base_url))
		self.agent = Agent(
			self.model,
			system_prompt=(
				"You are a stock assistant. For any stock or inventory question, always call "
				"lookup_stock or list_stock first, including non-food items like cash. "
				"Answer only from tool results."
			),
		)
		self._register_tools()

	def _load_stock_rows(self) -> list[dict[str, str]]:
		with self.stock_csv.open(newline="", encoding="utf-8") as handle:
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

	async def ask(self, question: str) -> str:
		"""Run a stock question through the pydantic-ai agent."""
		result = await self.agent.run(question)
		return str(result.output)

	def on_tick(self, ctx: TickContext) -> TickResult:
		"""Tick backbone placeholder; behavior can be extended with scheduling rules."""
		return TickResult(
			actions=[
				TickAction(
					action_type=TickActionType.NOOP,
					actor=self.name,
					tick_cost=0,
					payload={"reason": "stocker_backbone_ready", "tick": ctx.tick},
				)
			],
			logs=[f"[{self.name}] tick={ctx.tick} idle"],
		)

