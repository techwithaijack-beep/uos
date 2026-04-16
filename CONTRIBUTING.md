# Contributing

μOS optimizes for a small, legible codebase with a strong model. Contributions
that strengthen the abstractions are welcome. Contributions that add features
without a home in the model will be closed with care.

## Before you open a PR

1. Read [`docs/design_principles.md`](docs/design_principles.md).
2. Run the tests:
   ```
   pip install -e ".[dev]"
   pytest
   ```
3. Run the linter:
   ```
   ruff check .
   ```
4. If your change affects behavior, add a test.
5. If your change affects the model (ISA, MMU, process, capabilities), include
   a paragraph in your PR about *why the abstraction should change*.

## What we accept fast

- Bugfixes with a failing test.
- Tighter abstractions (removing special cases).
- New drivers for new LLM backends.
- New benchmark adapters that let us measure fairly against prior frameworks.

## What we ask twice

- New abstractions.
- New dependencies (ruthless about this).
- New features without a place in the model.

## Code of conduct

Be kind. Be precise. Disagreements about the model are fine and encouraged;
disagreements about people are not.
