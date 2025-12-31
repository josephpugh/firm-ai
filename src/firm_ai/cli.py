"""Command-line interface for Firm AI wrapper."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import List, Sequence

from firm_ai.discovery import load_tools


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="firm-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List installed tools")

    run_parser = subparsers.add_parser("run", help="Run a tool")
    run_parser.add_argument("tool", help="Tool name")
    run_parser.add_argument("tool_args", nargs=argparse.REMAINDER)

    install_parser = subparsers.add_parser(
        "install", help="Install a tool repo into the wrapper environment"
    )
    install_parser.add_argument("repo", help="Git URL or package spec")

    return parser


def _print_errors(errors: Sequence[object]) -> None:
    for error in errors:
        sys.stderr.write(f"[firm-ai] tool load error: {error}\n")


def _cmd_list() -> int:
    tools, errors = load_tools()
    _print_errors(errors)

    if not tools:
        print("No tools installed.")
        return 0

    for name in sorted(tools.keys()):
        tool = tools[name]
        print(f"{tool.name}\t{tool.description}")

    return 0


def _cmd_run(tool_name: str, tool_args: List[str]) -> int:
    tools, errors = load_tools()
    _print_errors(errors)

    if tool_args and tool_args[0] == "--":
        tool_args = tool_args[1:]

    tool = tools.get(tool_name)
    if tool is None:
        available = ", ".join(sorted(tools.keys())) or "<none>"
        sys.stderr.write(f"[firm-ai] unknown tool '{tool_name}'. Available: {available}\n")
        return 2

    try:
        return int(tool.run(tool_args))
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"[firm-ai] tool '{tool_name}' failed: {exc}\n")
        return 1


def _cmd_install(repo: str) -> int:
    pipx_path = shutil.which("pipx")
    if pipx_path:
        cmd = [pipx_path, "inject", "firm-ai", repo]
    else:
        cmd = [sys.executable, "-m", "pipx", "inject", "firm-ai", repo]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        sys.stderr.write(
            "[firm-ai] pipx is not available. Install pipx or use a venv and pip.\n"
        )
        return 1
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"[firm-ai] pipx inject failed: {exc}\n")
        return exc.returncode

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return _cmd_list()
    if args.command == "run":
        return _cmd_run(args.tool, list(args.tool_args))
    if args.command == "install":
        return _cmd_install(args.repo)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
