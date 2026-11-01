PYTHON ?= /usr/bin/python3

test:
	uv run pytest -q

test-system:
	$(PYTHON) -m pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

fmt:
	uv run ruff format .

bench:
	uv run python bench.py --python $(PYTHON)

.PHONY: test test-system lint fmt bench
