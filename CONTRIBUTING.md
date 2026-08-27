# Contributing to agentreplay

## Development Setup

```bash
# Clone the repo
git clone https://github.com/aafre/agentreplay.git
cd agentreplay

# Install all dependencies (requires uv)
uv sync --all-extras
```

## Quality Gates

All of these must pass before merging:

```bash
uv run ruff check .          # Lint
uv run ruff format --check . # Format
uv run mypy .                # Type check (strict)
uv run pytest -v             # Tests
```

## Code Style

- Python 3.12+, type hints everywhere
- `mypy --strict` compliance required
- Ruff for linting and formatting
- Follow SOLID, DRY, YAGNI

## Testing

- Write tests first (TDD)
- Use PydanticAI's `TestModel` — never call real LLM APIs in tests
- Property tests with `hypothesis` where they add meaningful guarantees

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.
