PYTHON ?= /usr/bin/python3
VERSION ?= 0.1.0
PLIST_FLAGS ?=

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

build:
	uv run python scripts/build.py $(VERSION) $(PLIST_FLAGS)

check: build
	uv run python scripts/smoke.py

.PHONY: test test-system lint fmt bench build check
