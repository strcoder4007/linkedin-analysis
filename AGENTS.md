# Repository Guidelines

## Project Structure & Module Organization
- `src/` — application code. Prefer `src/linkedin_analysis/` with a `cli.py` entry.
- `tests/` — unit/integration tests mirroring `src/` packages.
- `notebooks/` — exploratory analysis; keep outputs cleared before commit.
- `data/` — local data only (not committed): `raw/`, `interim/`, `processed/`.
- `configs/` — YAML/TOML for credentials-free settings.
- `scripts/` — one-off utilities (idempotent, small, documented).

## Build, Test, and Development Commands
Environment: Python 3.10; dependencies via `requirements.txt` with `pip`.
Use these if present; otherwise run the underlying Python equivalents.
- `make setup` — create venv and install deps (`python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`).
- `make test` — run the test suite (`pytest -q`).
- `make fmt` — auto-format (`black .` and `ruff --fix .`).
- `make lint` — static checks (`ruff .`).
- `make run` — run the CLI (`python -m linkedin_analysis` or `python src/linkedin_analysis/cli.py`).

## Coding Style & Naming Conventions
- Python 3.10, 4-space indentation, type hints required for public functions.
- Format with `black`; lint with `ruff`; sort imports with ruff import rules (`ruff --select I --fix`).
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Files: notebooks `YYYY-MM-DD-topic.ipynb`; scripts `verb_noun.py`.

## Testing Guidelines
- Framework: `pytest`; place tests under `tests/` with names `test_*.py`.
- Aim for ≥80% statement coverage on new/changed code (`pytest --cov=src`).
- Use fixtures for I/O; avoid hitting live APIs—mock with `responses` or `unittest.mock`.

## Commit & Pull Request Guidelines
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Keep subject ≤72 chars.
- PRs include: clear description, linked issue (e.g., `Closes #123`), test evidence, and, for notebooks, an HTML/PNG snapshot of key outputs.
- Keep PRs focused and small; update docs when behavior changes.

## Security & Configuration Tips
- Never commit secrets or data. Use `.env` (ignored) and provide `.env.example`.
- Parameterize credentials via env vars; load with `python-dotenv` in dev only.
- Large files/data live outside the repo; if needed, use DVC or object storage.

## Agent-Specific Instructions
- Prefer `rg` for search and read files in ≤250-line chunks.
- Do not install new deps without a rationale; favor standard library first.
