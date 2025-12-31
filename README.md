# firm-ai

A stable wrapper CLI that discovers and runs tools published as separate Python packages via entry points.

## Install (recommended with pipx)

```bash
pipx install -e .
```

To include Azure OpenAI helpers:

```bash
pipx install -e ".[azure]"
```

## Usage

```bash
firm-ai list
firm-ai run <tool> -- <tool-args>
```

If a tool does not need `--`, you can omit it. Any remaining arguments are passed to the tool.

## Install tools from Enterprise GitHub

Tools are separate repos/packages. Install them into the same environment as the wrapper.

```bash
pipx inject firm-ai git+https://github.example.com/org/firm-ai-hello
```

You can also use a venv and `pip install git+...`.

## Plugin authoring (tool repo)

Create a normal Python package and expose a `Tool` instance via the `firm_ai.tools` entry point group.

```python
# firm_ai_hello/__init__.py
from firm_ai.plugin import Tool


def run(argv: list[str]) -> int:
    print("hello from plugin", argv)
    return 0


tool = Tool(
    name="hello",
    description="Example hello tool",
    run=run,
)
```

```toml
# pyproject.toml
[project.entry-points."firm_ai.tools"]
hello = "firm_ai_hello:tool"
```

## Common utilities for plugins

The wrapper exposes shared utilities under `firm_ai` that plugins can import, such as:

- `firm_ai.azure.get_bearer_token`
- `firm_ai.azure.get_azure_openai_client`

These helpers are intentionally lightweight and optional, so plugins only pay for dependencies they use.
