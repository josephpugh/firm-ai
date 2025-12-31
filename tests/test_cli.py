from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import tests

from firm_ai import cli
from firm_ai.discovery import ToolInfo, ToolLoadError
from firm_ai.plugin import Tool


class TestCliBasics(unittest.TestCase):
    def test_normalize_name(self) -> None:
        self.assertEqual(cli._normalize_name("Firm_AI"), "firm-ai")

    def test_is_vcs_or_url(self) -> None:
        self.assertTrue(cli._is_vcs_or_url("git+https://example.com/repo.git"))
        self.assertTrue(cli._is_vcs_or_url("https://example.com/repo.git"))
        self.assertFalse(cli._is_vcs_or_url("firm-ai-hello"))

    def test_cmd_list_reports_no_tools(self) -> None:
        with patch("firm_ai.cli.load_tools_with_versions", return_value=({}, ())):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = cli._cmd_list()

        self.assertEqual(result, 0)
        self.assertIn("No tools installed.", stdout.getvalue())

    def test_cmd_list_prints_tools_and_errors(self) -> None:
        tool = Tool(name="hello", description="desc", run=lambda _: 0)
        tools = {"hello": ToolInfo(tool=tool, version="1.0.0")}
        errors = (ToolLoadError(name="bad", entry_point="bad", error="boom"),)
        with patch("firm_ai.cli.load_tools_with_versions", return_value=(tools, errors)):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = cli._cmd_list()

        self.assertEqual(result, 0)
        self.assertIn("hello\t1.0.0\tdesc", stdout.getvalue())
        self.assertIn("tool load error", stderr.getvalue())

    def test_cmd_run_passes_args_after_double_dash(self) -> None:
        captured = {}

        def run(args: list[str]) -> int:
            captured["args"] = args
            return 5

        tool = Tool(name="hello", description="desc", run=run)
        with patch("firm_ai.cli.load_tools", return_value=({"hello": tool}, ())):
            result = cli._cmd_run("hello", ["--", "a", "b"])

        self.assertEqual(result, 5)
        self.assertEqual(captured["args"], ["a", "b"])

    def test_cmd_run_reports_unknown_tool(self) -> None:
        with patch("firm_ai.cli.load_tools", return_value=({}, ())):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_run("missing", [])

        self.assertEqual(result, 2)
        self.assertIn("unknown tool", stderr.getvalue())

    def test_cmd_run_handles_tool_exception(self) -> None:
        def run(_: list[str]) -> int:
            raise RuntimeError("boom")

        tool = Tool(name="hello", description="desc", run=run)
        with patch("firm_ai.cli.load_tools", return_value=({"hello": tool}, ())):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_run("hello", [])

        self.assertEqual(result, 1)
        self.assertIn("failed", stderr.getvalue())


class TestCliInstallUninstallUpgrade(unittest.TestCase):
    def test_cmd_install_uses_pipx_inject(self) -> None:
        with patch("firm_ai.cli._pipx_cmd", return_value=["pipx"]), patch(
            "firm_ai.cli._run_pipx", return_value=0
        ) as run_pipx:
            result = cli._cmd_install("git+https://example.com/repo.git")

        self.assertEqual(result, 0)
        run_pipx.assert_called_once_with(
            ["pipx", "inject", "firm-ai", "git+https://example.com/repo.git"],
            action="inject",
        )

    def test_cmd_uninstall_refuses_wrapper(self) -> None:
        with patch(
            "firm_ai.cli.resolve_tool_distribution", return_value=("firm-ai", ())
        ), patch("firm_ai.cli._run_pipx") as run_pipx:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_uninstall("firm-ai")

        self.assertEqual(result, 2)
        self.assertIn("refusing to uninstall", stderr.getvalue())
        run_pipx.assert_not_called()

    def test_cmd_uninstall_runs_pipx_and_cleanup(self) -> None:
        with patch(
            "firm_ai.cli.resolve_tool_distribution", return_value=(None, ())
        ), patch("firm_ai.cli._run_pipx", return_value=0) as run_pipx, patch(
            "firm_ai.cli._cleanup_pipx_metadata"
        ) as cleanup:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_uninstall("firm-ai-hello")

        self.assertEqual(result, 0)
        run_pipx.assert_called_once()
        cleanup.assert_called_once_with("firm-ai-hello")
        self.assertIn("could not resolve tool", stderr.getvalue())

    def test_cmd_uninstall_skips_cleanup_on_failure(self) -> None:
        with patch(
            "firm_ai.cli.resolve_tool_distribution", return_value=(None, ())
        ), patch("firm_ai.cli._run_pipx", return_value=4), patch(
            "firm_ai.cli._cleanup_pipx_metadata"
        ) as cleanup:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_uninstall("firm-ai-hello")

        self.assertEqual(result, 4)
        cleanup.assert_not_called()

    def test_cmd_upgrade_refuses_wrapper(self) -> None:
        with patch(
            "firm_ai.cli.resolve_tool_distribution", return_value=("firm-ai", ())
        ), patch("firm_ai.cli._run_pipx") as run_pipx:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._cmd_upgrade("firm-ai")

        self.assertEqual(result, 2)
        run_pipx.assert_not_called()

    def test_cmd_upgrade_vcs_skips_resolve(self) -> None:
        with patch("firm_ai.cli._run_pipx", return_value=0) as run_pipx:
            result = cli._cmd_upgrade("git+https://example.com/repo.git")

        self.assertEqual(result, 0)
        run_pipx.assert_called_once()

    def test_cmd_upgrade_resolved_name(self) -> None:
        with patch(
            "firm_ai.cli.resolve_tool_distribution", return_value=("firm-ai-hello", ())
        ), patch("firm_ai.cli._run_pipx", return_value=0) as run_pipx:
            result = cli._cmd_upgrade("hello")

        self.assertEqual(result, 0)
        run_pipx.assert_called_once()

    def test_cmd_upgrade_self(self) -> None:
        with patch("firm_ai.cli._pipx_cmd", return_value=["pipx"]), patch(
            "firm_ai.cli._run_pipx", return_value=0
        ) as run_pipx:
            result = cli._cmd_upgrade_self()

        self.assertEqual(result, 0)
        run_pipx.assert_called_once_with(["pipx", "upgrade", "firm-ai"], action="upgrade")


class TestCliPipxHelpers(unittest.TestCase):
    def test_pipx_cmd_prefers_system_pipx(self) -> None:
        with patch("firm_ai.cli.shutil.which", return_value="/usr/bin/pipx"):
            self.assertEqual(cli._pipx_cmd(), ["/usr/bin/pipx"])

    def test_pipx_cmd_falls_back_to_python_module(self) -> None:
        with patch("firm_ai.cli.shutil.which", return_value=None):
            self.assertEqual(cli._pipx_cmd(), [sys.executable, "-m", "pipx"])

    def test_run_pipx_success(self) -> None:
        with patch("firm_ai.cli.subprocess.run") as run:
            result = cli._run_pipx(["pipx", "list"], action="list")

        self.assertEqual(result, 0)
        run.assert_called_once_with(["pipx", "list"], check=True)

    def test_run_pipx_missing_binary(self) -> None:
        with patch("firm_ai.cli.subprocess.run", side_effect=FileNotFoundError):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._run_pipx(["pipx", "list"], action="list")

        self.assertEqual(result, 1)
        self.assertIn("pipx is not available", stderr.getvalue())

    def test_run_pipx_command_failure(self) -> None:
        error = subprocess.CalledProcessError(returncode=5, cmd=["pipx"])
        with patch("firm_ai.cli.subprocess.run", side_effect=error):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli._run_pipx(["pipx", "list"], action="list")

        self.assertEqual(result, 5)
        self.assertIn("pipx list failed", stderr.getvalue())

    def test_pipx_list_json_parses_output(self) -> None:
        payload = {"venvs": {"firm-ai": {"venv_dir": "/tmp/venv"}}}
        run_result = SimpleNamespace(stdout=json.dumps(payload))
        with patch("firm_ai.cli._pipx_cmd", return_value=["pipx"]), patch(
            "firm_ai.cli.subprocess.run", return_value=run_result
        ):
            data = cli._pipx_list_json()

        self.assertEqual(data, payload)

    def test_pipx_list_json_handles_invalid_json(self) -> None:
        run_result = SimpleNamespace(stdout="not-json")
        with patch("firm_ai.cli._pipx_cmd", return_value=["pipx"]), patch(
            "firm_ai.cli.subprocess.run", return_value=run_result
        ):
            data = cli._pipx_list_json()

        self.assertIsNone(data)

    def test_pipx_list_json_handles_run_failure(self) -> None:
        with patch("firm_ai.cli._pipx_cmd", return_value=["pipx"]), patch(
            "firm_ai.cli.subprocess.run", side_effect=FileNotFoundError
        ):
            data = cli._pipx_list_json()

        self.assertIsNone(data)

    def test_pipx_venv_dir_uses_json_data(self) -> None:
        payload = {"venvs": {"firm-ai": {"venv_dir": "/tmp/venv"}}}
        with patch("firm_ai.cli._pipx_list_json", return_value=payload):
            venv = cli._pipx_venv_dir("firm-ai")

        self.assertEqual(venv, "/tmp/venv")

    def test_pipx_venv_dir_falls_back_to_home(self) -> None:
        with patch("firm_ai.cli._pipx_list_json", return_value=None), patch(
            "firm_ai.cli.os.path.isdir", return_value=True
        ), patch.dict(os.environ, {"PIPX_HOME": "/tmp/pipx"}):
            venv = cli._pipx_venv_dir("firm-ai")

        self.assertEqual(venv, "/tmp/pipx/venvs/firm-ai")

    def test_cleanup_pipx_metadata_removes_injected_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = os.path.join(temp_dir, "pipx_metadata.json")
            data = {
                "injected_packages": {"firm-ai-hello": {}},
                "main_package": {"injected_packages": {"firm-ai-hello": {}}},
            }
            with open(metadata_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)

            with patch("firm_ai.cli._pipx_venv_dir", return_value=temp_dir):
                cli._cleanup_pipx_metadata("firm-ai-hello")

            with open(metadata_path, "r", encoding="utf-8") as handle:
                updated = json.load(handle)

        self.assertNotIn("firm-ai-hello", updated.get("injected_packages", {}))
        self.assertNotIn(
            "firm-ai-hello", updated.get("main_package", {}).get("injected_packages", {})
        )

    def test_remove_injected_package(self) -> None:
        data = {
            "injected_packages": {"firm-ai-hello": {}, "other": {}},
            "main_package": {"injected_packages": {"firm-ai-hello": {}}},
        }
        removed = cli._remove_injected_package(data, "firm-ai-hello")

        self.assertTrue(removed)
        self.assertNotIn("firm-ai-hello", data["injected_packages"])
        self.assertNotIn("firm-ai-hello", data["main_package"]["injected_packages"])
