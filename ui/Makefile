PORT ?= 3000

IMAGE_REPO ?= mismplatform
IMAGE_NAME ?= ui
TAG ?= v0.1.0
IMAGE_TAG ?= $(IMAGE_REPO)/$(IMAGE_NAME):$(TAG)
IMAGE_RUN_ARGS ?=

.DEFAULT_GOAL := help

.PHONY: help install dev build start run test lint lint-fix format format-check typecheck check ci clean image-build image-run image-push

## Show available targets (default)
help:
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'By default, IMAGE_TAG=$$(IMAGE_REPO)/$$(IMAGE_NAME):$$(TAG)'
	@echo 'You can provide variables to targets, like this:'
	@echo '  make dev'
	@echo '  make run PORT=3000'
	@echo '  make image-build TAG=v0.1.1'
	@echo ''
	@echo 'Available variables:'
	@echo '  NPM, PORT, IMAGE_REPO, IMAGE_NAME, TAG, IMAGE_TAG, IMAGE_RUN_ARGS'
	@echo ''
	@echo 'Targets:'
	@awk '/^[[:space:]]*$$/ { next } /^##/ { desc = $$0; sub(/^##[[:space:]]*/, "", desc); next } /^[a-zA-Z0-9_-]+[[:space:]]*:/ { if (desc != "") { t = $$0; sub(/:.*/, "", t); printf "  %-16s %s\n", t, desc } desc = ""; next } { desc = "" }' $(MAKEFILE_LIST)

## Install dependencies from package-lock.json
install:
	npm ci

## Start the React Router development server with HMR (example: make dev DEV_PORT=4173)
dev:
	npm run dev -- --port $(PORT)

## Create a production build
build:
	npm run build

## Run the production server from the existing build output
start:
	PORT=$(PORT) npm run start

## Build and run the production server
run: build
	PORT=$(PORT) npm run start

## Run the currently configured frontend verification suite (currently the static quality checks)
test: check

## Run ESLint
lint:
	npm run lint

## Run ESLint with auto-fix
lint-fix:
	npm run lint:fix

## Format the codebase with Prettier
format:
	npm run format

## Check formatting without writing files
format-check:
	npm exec -- prettier --check .

## Generate route types and run the TypeScript checker
typecheck:
	npm run typecheck

## Run the main frontend quality checks (except lint, since that currently takes forever)
check: format-check typecheck build

## CI-friendly alias for the frontend quality checks
ci: check

## Remove build output and common local caches
clean:
	rm -rf build .react-router node_modules/.vite

## Build the Docker image (linux/amd64)
image-build:
	docker build -t $(IMAGE_TAG) --platform linux/amd64 -f Dockerfile .

## Run the built Docker image
image-run:
	docker run --rm -p $(PORT):$(PORT) -e PORT=$(PORT) $(IMAGE_RUN_ARGS) $(IMAGE_TAG)

## Push the image to the registry
image-push:
	docker push $(IMAGE_TAG)
