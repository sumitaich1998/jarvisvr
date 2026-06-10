.DEFAULT_GOAL := help

.PHONY: help install mock e2e test test-backend test-voice test-holo \
        test-protocol test-protocol-ts test-e2e lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the agent-backend + run the LLM API-key wizard
	$(MAKE) -C infra install

mock: ## Run the offline mock backend (no API key needed)
	$(MAKE) -C infra mock

e2e: ## Run the end-to-end protocol conformance harness
	$(MAKE) -C infra e2e

test: test-backend test-holo test-voice test-protocol test-protocol-ts test-e2e ## Run every component test suite

test-backend: ## agent-backend pytest
	cd agent-backend && python -m pip install -q -e ".[dev]" && pytest

test-holo: ## holo-tools pytest
	cd holo-tools && python -m pip install -q -e ".[test]" && pytest

test-voice: ## voice-service pytest
	cd voice-service && python -m pip install -q -e ".[dev]" && pytest

test-protocol: ## shared-protocol (Python) pytest
	cd shared-protocol/python && python -m pip install -q -e ".[dev]" && pytest

test-protocol-ts: ## shared-protocol (TypeScript) typecheck + build + vitest
	cd shared-protocol/typescript && npm install && npm run typecheck && npm run build && npm test

test-e2e: ## infra e2e conformance (against the mock backend)
	python -m pip install -q -e ./shared-protocol/python && \
	python -m pip install -q -r infra/e2e/requirements.txt && \
	pytest infra/e2e

lint: ## Byte-compile Python + typecheck TypeScript
	python -m compileall -q agent-backend/jarvis_backend voice-service/jarvis_voice holo-tools/holo_tools shared-protocol/python/src infra
	cd shared-protocol/typescript && npm install && npm run typecheck
