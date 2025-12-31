from __future__ import annotations

import types
import unittest
from unittest.mock import patch

import tests

from firm_ai import discovery
from firm_ai.plugin import Tool


class DummyEntryPoint:
    def __init__(self, name: str, loaded: object):
        self.name = name
        self._loaded = loaded
        self.group = discovery.ENTRYPOINT_GROUP

    def load(self) -> object:
        if isinstance(self._loaded, Exception):
            raise self._loaded
        return self._loaded

    def __str__(self) -> str:
        return f"DummyEntryPoint({self.name})"


class DummyDist:
    def __init__(self, name: str | None = None, version: str | None = None):
        self.name = name
        self.version = version
        self.metadata = {"Name": name or "", "Version": version or ""}
        self.entry_points = []


class TestResolveTool(unittest.TestCase):
    def test_resolve_tool_accepts_tool_instance(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)
        ep = DummyEntryPoint("hello", tool)
        self.assertIs(discovery._resolve_tool(ep), tool)

    def test_resolve_tool_accepts_callable_factory(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)

        def factory() -> Tool:
            return tool

        ep = DummyEntryPoint("hello", factory)
        self.assertIs(discovery._resolve_tool(ep), tool)

    def test_resolve_tool_rejects_invalid_entry(self) -> None:
        ep = DummyEntryPoint("bad", object())
        with self.assertRaises(TypeError):
            discovery._resolve_tool(ep)


class TestDiscoveryLoading(unittest.TestCase):
    def test_load_tools_reports_duplicate_names(self) -> None:
        tool1 = Tool(name="dup", description="one", run=lambda _: 0)
        tool2 = Tool(name="dup", description="two", run=lambda _: 0)
        eps = [DummyEntryPoint("one", tool1), DummyEntryPoint("two", tool2)]

        with patch("firm_ai.discovery._select_entry_points", return_value=eps):
            tools, errors = discovery.load_tools()

        self.assertEqual(list(tools.keys()), ["dup"])
        self.assertEqual(len(errors), 1)
        self.assertIn("Duplicate tool name", errors[0].error)

    def test_load_tools_collects_load_errors(self) -> None:
        eps = [DummyEntryPoint("bad", RuntimeError("boom"))]
        with patch("firm_ai.discovery._select_entry_points", return_value=eps):
            tools, errors = discovery.load_tools()

        self.assertEqual(tools, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("boom", errors[0].error)

    def test_load_tools_with_versions_uses_dist_version(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)
        ep = DummyEntryPoint("hello", tool)
        dist = DummyDist(name="firm-ai-hello", version="1.2.3")

        with patch(
            "firm_ai.discovery._iter_entry_points_with_dist",
            return_value=[(ep, dist)],
        ):
            tools, errors = discovery.load_tools_with_versions()

        self.assertEqual(errors, ())
        self.assertEqual(tools["hello"].version, "1.2.3")

    def test_load_tools_with_versions_uses_metadata_version(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)
        ep = DummyEntryPoint("hello", tool)
        dist = types.SimpleNamespace(version=None, metadata={"Version": "9.9.9"})

        with patch(
            "firm_ai.discovery._iter_entry_points_with_dist",
            return_value=[(ep, dist)],
        ):
            tools, errors = discovery.load_tools_with_versions()

        self.assertEqual(errors, ())
        self.assertEqual(tools["hello"].version, "9.9.9")

    def test_iter_entry_points_forwards_select(self) -> None:
        with patch("firm_ai.discovery._select_entry_points", return_value=["x"]):
            self.assertEqual(list(discovery.iter_entry_points()), ["x"])

    def test_resolve_tool_distribution_finds_dist_name(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)
        ep = DummyEntryPoint("hello", tool)
        dist = DummyDist(name="firm-ai-hello", version="1.0.0")

        with patch(
            "firm_ai.discovery._iter_entry_points_with_dist",
            return_value=[(ep, dist)],
        ):
            dist_name, errors = discovery.resolve_tool_distribution("hello")

        self.assertEqual(dist_name, "firm-ai-hello")
        self.assertEqual(errors, ())

    def test_resolve_tool_distribution_collects_errors(self) -> None:
        bad_ep = DummyEntryPoint("bad", RuntimeError("boom"))
        good_tool = Tool(name="hello", description="desc", run=lambda _: 0)
        good_ep = DummyEntryPoint("hello", good_tool)
        dist = DummyDist(name="firm-ai-hello", version="1.0.0")

        with patch(
            "firm_ai.discovery._iter_entry_points_with_dist",
            return_value=[(bad_ep, dist), (good_ep, dist)],
        ):
            dist_name, errors = discovery.resolve_tool_distribution("hello")

        self.assertEqual(dist_name, "firm-ai-hello")
        self.assertEqual(len(errors), 1)
