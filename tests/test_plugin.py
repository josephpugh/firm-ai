from __future__ import annotations

import unittest

import tests

from firm_ai.plugin import Tool


class TestTool(unittest.TestCase):
    def test_tool_requires_name(self) -> None:
        with self.assertRaises(ValueError):
            Tool(name="", description="desc", run=lambda _: 0)

    def test_tool_requires_description(self) -> None:
        with self.assertRaises(ValueError):
            Tool(name="tool", description="", run=lambda _: 0)

    def test_tool_requires_callable_run(self) -> None:
        with self.assertRaises(TypeError):
            Tool(name="tool", description="desc", run=None)  # type: ignore[arg-type]

    def test_tool_accepts_valid_runner(self) -> None:
        tool = Tool(name="tool", description="desc", run=lambda _: 0)
        self.assertEqual(tool.name, "tool")
        self.assertEqual(tool.description, "desc")
