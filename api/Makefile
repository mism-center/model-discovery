PYTHON ?= 3.12
UV ?= uv
APP ?= mismapi.main:app

IMAGE_REPO ?= mismplatform
IMAGE_NAME ?= model-discovery
TAG ?= v0.1.0
IMAGE_TAG ?= $(IMAGE_REPO)/$(IMAGE_NAME):$(TAG)
IMAGE_RUN_ARGS ?=
PORT ?= 8000

COMPOSE_TEST ?= docker compose -f ../docker-compose.test.yaml

.PHONY: help install lock run dev test lint format format-check typecheck clean image-build image-run image-push

## Show available targets (default)
help:
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'By default, IMAGE_TAG=$$(IMAGE_REPO)/$$(IMAGE_NAME):$$(TAG)'
	@echo 'You can provide any of the above variables as arguments to the targets, like this:'
	@echo '  make image-build IMAGE_TAG=mismplatform/model-discovery:v0.1.0'
	@echo '  make image-build TAG=v0.1.1'
	@echo '  make image-push IMAGE_TAG=mismplatform/model-discovery:v0.1.1'
	@echo ''
	@echo 'Available variables:'
	@echo '  PORT, IMAGE_REPO, IMAGE_NAME, TAG, IMAGE_TAG, IMAGE_RUN_ARGS'
	@echo ''
	@echo 'Targets:'
	@awk '/^[[:space:]]*$$/ { next } /^##/ { desc = $$0; sub(/^##[[:space:]]*/, "", desc); next } /^[a-zA-Z0-9_-]+[[:space:]]*:/ { if (desc != "") { t = $$0; sub(/:.*/, "", t); printf "  %-16s %s\n", t, desc } desc = ""; next } { desc = "" }' $(MAKEFILE_LIST)

## Sync Python dependencies (uv sync --all-groups)
install:
	$(UV) sync --python $(PYTHON) --all-groups

## Regenerate the dependency lockfile (uv lock)
lock:
	$(UV) lock

## Run the API with uvicorn (no reload)
run:
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port $(PORT)

## Run the API with uvicorn and --reload
dev:
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port $(PORT) --reload

## Run the unit tests (pytest)
test-unit:
	$(UV) run pytest tests/unit/*.py -v

## Run the integration tests (pytest)
test-integration:
	$(UV) run pytest tests/integration/*.py -v

functional-up:
	$(COMPOSE_TEST) up -d --build --wait

functional-down:
	$(COMPOSE_TEST) down -v

## Run the functional tests (checking if the services are already running)
test-functional:
	@if [ -z "$$($(COMPOSE_TEST) ps --status running -q api 2>/dev/null)" ]; then \
		$(MAKE) functional-up; \
	fi
	$(UV) run pytest tests/functional/*.py -m integration -v
	$(MAKE) functional-down

## Run the test suite (including functional tests)
test: test-unit test-integration test-functional

## Run the test suite for CI
test-ci: test-unit test-integration

## Run Ruff linter
lint:
	$(UV) run ruff check .

## Apply Ruff formatting
format:
	$(UV) run ruff format .

## Check formatting without writing files
format-check:
	$(UV) run ruff format --check .

## Run mypy on src and tests
typecheck:
	$(UV) run python -m mypy src tests

## Run all CI steps. This is helpful for running all checks locally before committing.
ci: lint format-check typecheck test-ci

## Remove pytest, Ruff, and mypy caches
clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache



integration-test: integration-up


integration-down:
	docker compose -f ../docker-compose.test.yaml down -v

## Build the Docker image (linux/amd64).
image-build:
	docker build -t $(IMAGE_TAG) --platform linux/amd64 -f Dockerfile --build-arg PORT=$(PORT) .

## Run the built image.
image-run:
	docker run --rm -p $(PORT):$(PORT) -e PORT=$(PORT) $(IMAGE_RUN_ARGS) $(IMAGE_TAG)

## Push the image to the registry.
image-push:
	docker push $(IMAGE_TAG)
