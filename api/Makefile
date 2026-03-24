PYTHON ?= 3.12
UV ?= uv
APP ?= mismapi.main:app

IMAGE_REPO ?= mismplatform
IMAGE_NAME ?= model-discovery
IMAGE_TAG ?= v0.1.0
IMAGE ?= $(IMAGE_REPO)/$(IMAGE_NAME):$(IMAGE_TAG)
IMAGE_RUN_ARGS ?=

.PHONY: install lock run dev test lint format typecheck clean image-build image-run image-push

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

image-build:
	docker build -t $(IMAGE) --platform linux/amd64 -f Dockerfile .

image-run:
	docker run --rm -p 8000:8000 $(IMAGE_RUN_ARGS) $(IMAGE)

image-push:
	docker push $(IMAGE)
