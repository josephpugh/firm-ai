"""Entry point discovery for Firm AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Dict, Iterable, Tuple

from firm_ai.plugin import Tool

ENTRYPOINT_GROUP = "firm_ai.tools"


@dataclass(frozen=True)
class ToolLoadError:
    name: str
    entry_point: str
    error: str

    def __str__(self) -> str:
        return f"{self.name} ({self.entry_point}): {self.error}"


def _resolve_tool(ep: EntryPoint) -> Tool:
    loaded = ep.load()
    if isinstance(loaded, Tool):
        return loaded
    if callable(loaded):
        tool = loaded()
        if isinstance(tool, Tool):
            return tool
    raise TypeError(
        f"Entry point '{ep.name}' must resolve to a Tool or a callable returning Tool"
    )


def _select_entry_points() -> Iterable[EntryPoint]:
    eps = entry_points()
    if hasattr(eps, "select"):
        return eps.select(group=ENTRYPOINT_GROUP)
    return eps.get(ENTRYPOINT_GROUP, [])


def load_tools() -> Tuple[Dict[str, Tool], Tuple[ToolLoadError, ...]]:
    tools: Dict[str, Tool] = {}
    errors = []
    for ep in _select_entry_points():
        try:
            tool = _resolve_tool(ep)
            if tool.name in tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            tools[tool.name] = tool
        except Exception as exc:  # pragma: no cover - CLI shows errors
            errors.append(
                ToolLoadError(
                    name=ep.name,
                    entry_point=str(ep),
                    error=str(exc),
                )
            )
    return tools, tuple(errors)


def iter_entry_points() -> Iterable[EntryPoint]:
    return _select_entry_points()
