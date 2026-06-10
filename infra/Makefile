# JarvisVR infra — common dev tasks. Run `make` (or `make help`) for the list.
.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash

S := scripts

.PHONY: help install up down mock e2e test lint fmt config clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install the agent-backend + run setup (asks for your LLM API key)
	@$(S)/install.sh $(ARGS)

up: ## Start the real stack (agent-backend + voice-service) via Docker
	@$(S)/dev_up.sh

down: ## Stop the stack (real or mock)
	@$(S)/dev_down.sh

mock: ## Start the mock brain via Docker (no sibling images needed)
	@$(S)/mock.sh

e2e: ## Start the mock locally and run the conformance harness
	@$(S)/e2e.sh

test: ## Run the shared-protocol test suites (Python + TypeScript)
	@$(S)/test.sh

lint: ## Lint / typecheck the owned dirs (best-effort)
	@$(S)/lint.sh

fmt: ## Autoformat the owned dirs (best-effort)
	@$(S)/fmt.sh

config: ## Validate the docker-compose files (syntax)
	@( cd "$(CURDIR)" && [ -f .env ] || cp .env.example .env ); \
	if docker compose version >/dev/null 2>&1; then \
	  docker compose -f docker-compose.yml config >/dev/null && echo "base compose OK"; \
	  docker compose -f docker-compose.yml -f docker-compose.mock.yml config >/dev/null && echo "mock override OK"; \
	  docker compose -f docker-compose.yml -f docker-compose.gpu.yml config >/dev/null && echo "gpu override OK"; \
	elif command -v docker-compose >/dev/null 2>&1; then \
	  docker-compose -f docker-compose.yml config >/dev/null && echo "base compose OK (v1)"; \
	else \
	  echo "docker compose not installed; skipping (see README troubleshooting)"; \
	fi

clean: ## Remove the venv and TS build artifacts
	@rm -rf .venv ../shared-protocol/typescript/dist ../shared-protocol/typescript/node_modules
	@echo "cleaned"
