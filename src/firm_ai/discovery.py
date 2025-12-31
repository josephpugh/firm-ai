"""Entry point discovery for Firm AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points, distributions
from typing import Dict, Iterable, Optional, Tuple

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


def _iter_entry_points_with_dist() -> Iterable[Tuple[EntryPoint, object]]:
    for dist in distributions():
        for ep in dist.entry_points:
            if ep.group == ENTRYPOINT_GROUP:
                yield ep, dist


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


def resolve_tool_distribution(tool_name: str) -> Tuple[Optional[str], Tuple[ToolLoadError, ...]]:
    errors = []
    for ep, dist in _iter_entry_points_with_dist():
        try:
            tool = _resolve_tool(ep)
            if tool.name != tool_name:
                continue
            dist_name = getattr(dist, "name", None)
            if not dist_name:
                dist_name = dist.metadata.get("Name")
            return dist_name, tuple(errors)
        except Exception as exc:
            errors.append(
                ToolLoadError(
                    name=ep.name,
                    entry_point=str(ep),
                    error=str(exc),
                )
            )
    return None, tuple(errors)
