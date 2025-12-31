"""Command-line interface for Firm AI wrapper."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Sequence

from firm_ai.discovery import load_tools, resolve_tool_distribution

WRAPPER_PACKAGE = "firm-ai"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="firm-ai",
        description="Firm AI wrapper CLI for tool plugins.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  firm-ai list\n"
            "  firm-ai run hello -- --name \"Ada\"\n"
            "  firm-ai install git+https://github.com/org/firm-ai-hello@v0.0.1\n"
            "  firm-ai uninstall firm-ai-hello\n"
            "  firm-ai upgrade git+https://github.com/org/firm-ai-hello@v0.0.2\n"
            "  firm-ai upgrade-self\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List installed tools")

    run_parser = subparsers.add_parser("run", help="Run a tool")
    run_parser.add_argument("tool", help="Tool name")
    run_parser.add_argument("tool_args", nargs=argparse.REMAINDER)

    install_parser = subparsers.add_parser(
        "install", help="Install a tool repo into the wrapper environment"
    )
    install_parser.add_argument("repo", help="Git URL or package spec")

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall a tool package from the wrapper environment"
    )
    uninstall_parser.add_argument("name", help="Tool name or package name")

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Upgrade an installed tool package"
    )
    upgrade_parser.add_argument("spec", help="Tool name, package name, or repo URL")

    subparsers.add_parser("upgrade-self", help="Upgrade the firm-ai wrapper package")

    subparsers.add_parser("help", help="Show help and usage examples")

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
    cmd = _pipx_cmd() + ["inject", "firm-ai", repo]
    return _run_pipx(cmd, action="inject")


def _cmd_uninstall(name: str) -> int:
    resolved, errors = resolve_tool_distribution(name)
    _print_errors(errors)
    package_name = resolved or name
    if _normalize_name(package_name) == _normalize_name(WRAPPER_PACKAGE):
        sys.stderr.write(
            "[firm-ai] refusing to uninstall the wrapper package. "
            "Provide a tool package name (e.g. firm-ai-hello).\n"
        )
        return 2
    if resolved is None:
        sys.stderr.write(
            f"[firm-ai] could not resolve tool '{name}' to a package name. "
            "Trying the provided name.\n"
        )
    cmd = _pipx_cmd() + ["runpip", "firm-ai", "uninstall", "-y", package_name]
    result = _run_pipx(cmd, action="runpip uninstall")
    if result != 0:
        return result
    _cleanup_pipx_metadata(package_name)
    return 0


def _cmd_upgrade(spec: str) -> int:
    resolved_name = None
    if not _is_vcs_or_url(spec):
        resolved_name, errors = resolve_tool_distribution(spec)
        _print_errors(errors)
        if resolved_name:
            spec = resolved_name
    if _normalize_name(spec) == _normalize_name(WRAPPER_PACKAGE):
        sys.stderr.write(
            "[firm-ai] refusing to upgrade the wrapper via tool upgrade. "
            "Use 'firm-ai upgrade-self'.\n"
        )
        return 2
    cmd = _pipx_cmd() + ["runpip", "firm-ai", "install", "--upgrade", spec]
    return _run_pipx(cmd, action="runpip install --upgrade")


def _cmd_upgrade_self() -> int:
    cmd = _pipx_cmd() + ["upgrade", WRAPPER_PACKAGE]
    return _run_pipx(cmd, action="upgrade")


def _pipx_cmd() -> List[str]:
    pipx_path = shutil.which("pipx")
    if pipx_path:
        return [pipx_path]
    return [sys.executable, "-m", "pipx"]


def _run_pipx(cmd: List[str], *, action: str) -> int:
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        sys.stderr.write(
            "[firm-ai] pipx is not available. Install pipx or use a venv and pip.\n"
        )
        return 1
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"[firm-ai] pipx {action} failed: {exc}\n")
        return exc.returncode
    return 0


def _normalize_name(name: str) -> str:
    return name.replace("_", "-").lower()


def _is_vcs_or_url(spec: str) -> bool:
    return spec.startswith(("git+", "http://", "https://"))


def _pipx_list_json() -> Optional[Dict[str, object]]:
    cmd = _pipx_cmd() + ["list", "--json"]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _pipx_venv_dir(package_name: str) -> Optional[str]:
    data = _pipx_list_json()
    if isinstance(data, dict):
        venvs = data.get("venvs", {})
        if isinstance(venvs, dict):
            info = venvs.get(package_name)
            if isinstance(info, dict):
                venv_dir = info.get("venv_dir")
                if venv_dir:
                    return venv_dir
    pipx_home = os.getenv("PIPX_HOME", os.path.expanduser("~/.local/pipx"))
    venv_dir = os.path.join(pipx_home, "venvs", package_name)
    if os.path.isdir(venv_dir):
        return venv_dir
    return None


def _cleanup_pipx_metadata(package_name: str) -> None:
    venv_dir = _pipx_venv_dir(WRAPPER_PACKAGE)
    if not venv_dir:
        return
    metadata_path = os.path.join(venv_dir, "pipx_metadata.json")
    if not os.path.exists(metadata_path):
        return
    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return
    removed = _remove_injected_package(data, package_name)
    if not removed:
        return
    try:
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError:
        return


def _remove_injected_package(data: dict, package_name: str) -> bool:
    normalized = _normalize_name(package_name)
    removed = False

    def drop(mapping: dict) -> None:
        nonlocal removed
        for key in list(mapping.keys()):
            if _normalize_name(key) == normalized:
                mapping.pop(key)
                removed = True

    injected = data.get("injected_packages")
    if isinstance(injected, dict):
        drop(injected)
    main = data.get("main_package")
    if isinstance(main, dict):
        injected = main.get("injected_packages")
        if isinstance(injected, dict):
            drop(injected)
    return removed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return _cmd_list()
    if args.command == "run":
        return _cmd_run(args.tool, list(args.tool_args))
    if args.command == "install":
        return _cmd_install(args.repo)
    if args.command == "uninstall":
        return _cmd_uninstall(args.name)
    if args.command == "upgrade":
        return _cmd_upgrade(args.spec)
    if args.command == "upgrade-self":
        return _cmd_upgrade_self()
    if args.command == "help":
        parser.print_help()
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
