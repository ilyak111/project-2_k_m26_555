install:
	uv sync --locked

run:
	uv run database

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run python -m unittest discover -s tests -v

build:
	uv build

check: lint test build

.PHONY: install run lint test build check
