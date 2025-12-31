# firm-ai

A simple wrapper CLI that discovers and runs tools published as separate Python packages via entry points.

## User Guide (install and use)

### What you need

- A terminal
- Python 3.9+
- `pipx` (recommended, installs apps cleanly)

If you do not have `pipx`, ask IT or run:

```bash
python -m pip install --user pipx
python -m pipx ensurepath
```

### Install firm-ai

Install from GitHub (recommended):

```bash
pipx install git+https://github.com/josephpugh/firm-ai@v0.0.4
```

If you omit the tag, pipx installs the default branch (usually `main`), not the latest tag.

### Install a tool

Tools are separate repos. Install them into the same environment as the wrapper:

```bash
firm-ai install git+https://github.com/josephpugh/firm-ai-hello@v0.0.2
```

### List tools

```bash
firm-ai list
```

### Run a tool

```bash
firm-ai run hello -- --name "Ada"
```

If a tool does not need `--`, you can omit it. Any remaining arguments are passed to the tool.

### Remove a tool

```bash
firm-ai uninstall hello
```

### Upgrade a tool

```bash
firm-ai upgrade git+https://github.com/josephpugh/firm-ai-hello@v0.0.2
```

### Upgrade the wrapper

```bash
firm-ai upgrade-self
```

If you see "command not found", open a new terminal so your PATH updates.

## Developer Guide (build and publish a plugin)

### 1) Create a plugin package

Your tool is a normal Python package that depends on `firm-ai` and exposes a `Tool` via the
`firm_ai.tools` entry point group.

Minimal structure:

```
firm-ai-hello/
  pyproject.toml
  src/
    firm_ai_hello/
      __init__.py
```

### 2) Implement a Tool

```python
# src/firm_ai_hello/__init__.py
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

### 3) Register the entry point

```toml
# pyproject.toml
[project]
name = "firm-ai-hello"
version = "0.0.1"
dependencies = ["firm-ai>=0.0.4"]

[project.entry-points."firm_ai.tools"]
hello = "firm_ai_hello:tool"
```

### 4) Test locally

Install your plugin into the same pipx environment:

```bash
pipx inject firm-ai -e /path/to/firm-ai-hello
firm-ai list
firm-ai run hello
```

### 5) Publish

Push your repo and tag a release:

```bash
git tag -a v0.0.1 -m "v0.0.1"
git push --tags
```

Then users can install it:

```bash
firm-ai install git+https://github.com/your-org/firm-ai-hello@v0.0.1
```

### Shared helpers (optional)

Plugins can reuse common helpers from the wrapper:

- `firm_ai.azure.get_bearer_token`
- `firm_ai.azure.get_azure_openai_client`

If your plugin needs Azure helpers, depend on the optional extra:

```toml
dependencies = ["firm-ai[azure]>=0.0.3"]
```

## Testing

Run the unit tests (uses stdlib `unittest`):

```bash
python -m unittest discover -s tests
```

Optional: add coverage to CI (example GitHub Actions steps):

```yaml
- name: Install coverage
  run: python -m pip install --upgrade coverage
- name: Run tests with coverage
  run: |
    coverage run -m unittest discover -s tests
    coverage report -m
```
