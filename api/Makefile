PYTHON ?= 3.12
UV ?= uv
APP ?= mismapi.main:app

.PHONY: install lock run dev test lint format typecheck clean integration-up integration-test integration-down

install:
	$(UV) sync --python $(PYTHON) --all-groups

lock:
	$(UV) lock

run:
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port 8000

dev:
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port 8000 --reload

test:
	$(UV) run python -m pytest

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run python -m mypy src tests

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache

integration-up:
	docker compose -f ../docker-compose.test.yaml up -d --build --wait

integration-test: integration-up
	$(UV) run pytest tests/test_integration.py -m integration -v

integration-down:
	docker compose -f ../docker-compose.test.yaml down -v
