"""Plugin interfaces for Firm AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


ToolRunner = Callable[[Sequence[str]], int]


@dataclass(frozen=True)
class Tool:
    """Defines a callable tool exposed via entry points."""

    name: str
    description: str
    run: ToolRunner

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Tool.name must be non-empty")
        if not self.description:
            raise ValueError("Tool.description must be non-empty")
        if not callable(self.run):
            raise TypeError("Tool.run must be callable")
