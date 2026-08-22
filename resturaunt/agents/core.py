from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class TickActionType(str, Enum):
	"""Action categories that agents can emit per tick."""

	NOOP = "noop"
	READ_STOCK = "read_stock"
	COOK = "cook"
	BUY_STOCK = "buy"
	ADD_ORDER = "add_order"


@dataclass(slots=True)
class TickContext:
	"""Immutable-ish snapshot inputs available to an agent on a given tick."""

	tick: int
	now_ms: int | None = None
	state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TickAction:
	"""Planned work emitted by an agent for orchestration/scheduling."""

	action_type: TickActionType
	actor: str
	duration_ticks: int = 1
	payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TickResult:
	"""Per-tick output contract for all agents."""

	actions: list[TickAction] = field(default_factory=list)
	logs: list[str] = field(default_factory=list)


class TickAgent(Protocol):
	"""Backbone contract for all restaurant agents."""

	name: str

	def on_tick(self, ctx: TickContext) -> TickResult:
		"""Return proposed actions for this tick without mutating global state."""

