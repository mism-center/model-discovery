PYTHON ?= 3.12
UV ?= uv
APP ?= mismapi.main:app

IMAGE_REPO ?= mismplatform
IMAGE_NAME ?= model-discovery
TAG ?= v0.1.0
IMAGE_TAG ?= $(IMAGE_REPO)/$(IMAGE_NAME):$(TAG)
IMAGE_RUN_ARGS ?=

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
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port 8000

## Run the API with uvicorn and --reload
dev:
	$(UV) run uvicorn --app-dir src $(APP) --host 0.0.0.0 --port 8000 --reload

## Run the test suite (pytest)
test:
	$(UV) run python -m pytest

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

## Remove pytest, Ruff, and mypy caches
clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache

## Build the Docker image (linux/amd64).
image-build:
	docker build -t $(IMAGE_TAG) --platform linux/amd64 -f Dockerfile .

## Run the built image on port 8000.
image-run:
	docker run --rm -p 8000:8000 $(IMAGE_RUN_ARGS) $(IMAGE_TAG)

## Push the image to the registry.
image-push:
	docker push $(IMAGE_TAG)
