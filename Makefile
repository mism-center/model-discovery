PYTHON ?= 3.12
UV ?= uv
APP ?= mism_api.main:app

.PHONY: install lock run dev test lint format typecheck clean

install:
	$(UV) sync --python $(PYTHON) --all-groups

lock:
	$(UV) lock

run:
	$(UV) run uvicorn $(APP) --host 0.0.0.0 --port 8000

dev:
	$(UV) run uvicorn $(APP) --host 0.0.0.0 --port 8000 --reload

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy src tests

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
