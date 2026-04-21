SHELL := /bin/bash

VENV_PYTHON := $(CURDIR)/.venv/bin/python
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)
NPM ?= npm
SCREEN ?= screen

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 5173
BACKEND_SESSION ?= acme-assistant-backend
FRONTEND_SESSION ?= acme-assistant-frontend
LOG_DIR ?= artifacts/dev
BACKEND_LOG ?= $(LOG_DIR)/backend.log
FRONTEND_LOG ?= $(LOG_DIR)/frontend.log
EVAL_GOLD_PATH ?= evals/retrieval_gold.yaml
EVAL_OUTPUT_PATH ?= artifacts/evals/retrieval_eval_results.json
EVAL_BASELINE_PATH ?= evals/baselines/faiss_hybrid_rerank.json
EVAL_DEBUG_LOG_PATH ?= artifacts/evals/rerank_debug.jsonl
GROUNDEDNESS_GOLD_PATH ?= evals/groundedness_gold.yaml
GROUNDEDNESS_OUTPUT_PATH ?= artifacts/evals/groundedness_eval_results.json
GROUNDEDNESS_DEBUG_LOG_PATH ?= artifacts/evals/groundedness_debug.jsonl
GROUNDEDNESS_JUDGE_MODE ?= heuristic
DOCKER_COMPOSE ?= docker compose
DOCKER_COMPOSE_PROD ?= docker compose -f docker-compose.yml -f docker-compose.prod.yml
DOCKER_API_RUN ?= $(DOCKER_COMPOSE) run --rm api
POSTGRES_DB ?= acme_assistant
POSTGRES_USER ?= acme

.PHONY: help install install-python install-frontend dev stop logs-backend logs-frontend logs-worker backend frontend test eval eval-baseline eval-compare eval-postgres eval-postgres-compare groundedness-eval docker-up docker-down docker-logs docker-test docker-migrate docker-db-shell docker-worker-logs docker-ingest docker-verify-corpus docker-eval docker-prod-up docker-prod-down docker-prod-logs docker-prod-test retriever-faiss retriever-postgres local-dev local-stop local-logs-backend local-logs-frontend local-backend local-frontend local-test local-eval local-eval-baseline local-eval-compare local-eval-postgres local-eval-postgres-compare local-groundedness-eval

help:
	@echo "Available targets:"
	@echo "  make install           Build Docker images"
	@echo "  make dev               Build and start the Docker dev stack"
	@echo "  make stop              Stop the Docker dev stack"
	@echo "  make logs-backend      Follow Docker backend logs"
	@echo "  make logs-frontend     Follow Docker frontend logs"
	@echo "  make logs-worker       Follow Docker worker logs"
	@echo "  make backend           Start only the Docker backend service"
	@echo "  make frontend          Start the Docker frontend service"
	@echo "  make test              Run pytest inside the backend Docker image"
	@echo "  make eval              Run retrieval evals inside the backend Docker image"
	@echo "  make eval-baseline     Regenerate the FAISS baseline inside Docker"
	@echo "  make eval-compare      Compare evals against the baseline inside Docker"
	@echo "  make eval-postgres     Run retrieval evals against the Postgres backend"
	@echo "  make eval-postgres-compare Compare Postgres evals against the FAISS baseline"
	@echo "  make groundedness-eval Run groundedness evals inside Docker"
	@echo "  make docker-migrate    Apply database migrations"
	@echo "  make docker-db-shell   Open a psql shell in the Postgres container"
	@echo "  make docker-worker-logs Follow Docker worker logs"
	@echo "  make docker-ingest     Run a full corpus ingest inside Docker"
	@echo "  make docker-verify-corpus Verify active corpus integrity inside Docker"
	@echo "  make docker-prod-up    Start the production-like Docker profile"
	@echo "  make docker-prod-down  Stop the production-like Docker profile"
	@echo "  make docker-prod-logs  Follow production-like Docker logs"
	@echo "  make docker-prod-test  Validate the production-like Docker config"
	@echo "  make retriever-faiss    Switch Docker to the FAISS retriever"
	@echo "  make retriever-postgres Switch Docker to the Postgres retriever"
	@echo "  make local-dev         Start local non-Docker dev servers"
	@echo "  make local-test        Run local non-Docker pytest"
	@echo "  make local-groundedness-eval Run groundedness evals locally"

install:
	$(DOCKER_COMPOSE) build

install-python:
	$(PYTHON) -m pip install -r requirements.txt

install-frontend:
	$(NPM) --prefix src/frontend install

dev: docker-up

stop: docker-down

logs-backend:
	$(DOCKER_COMPOSE) logs -f api

logs-frontend:
	$(DOCKER_COMPOSE) logs -f frontend

logs-worker:
	$(DOCKER_COMPOSE) logs -f worker

backend:
	$(DOCKER_COMPOSE) up --build api

frontend:
	$(DOCKER_COMPOSE) up --build frontend

test: docker-test

eval:
	$(DOCKER_API_RUN) python -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

eval-baseline:
	$(DOCKER_API_RUN) python -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_BASELINE_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

eval-compare:
	$(DOCKER_API_RUN) python -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0 \
		--compare-baseline $(EVAL_BASELINE_PATH)

eval-postgres:
	$(DOCKER_API_RUN) python -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--retriever-backend postgres \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

eval-postgres-compare:
	$(DOCKER_API_RUN) python -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--retriever-backend postgres \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0 \
		--compare-baseline $(EVAL_BASELINE_PATH)

local-dev:
	@echo "Starting FastAPI backend at http://$(BACKEND_HOST):$(BACKEND_PORT)"
	@echo "Starting Vite frontend at http://$(FRONTEND_HOST):$(FRONTEND_PORT)"
	@existing_sessions="$$( { $(SCREEN) -list || true; } | awk '/[.]($(BACKEND_SESSION)|$(FRONTEND_SESSION))[[:space:]]/ { print $$1 }')"; \
	if [[ -n "$$existing_sessions" ]]; then \
		echo "Existing dev server screen sessions found:"; \
		echo "$$existing_sessions"; \
		echo "Run 'make stop' first, then run 'make dev' again."; \
		exit 1; \
	fi
	@mkdir -p $(LOG_DIR)
	@: > $(BACKEND_LOG)
	@: > $(FRONTEND_LOG)
	@$(SCREEN) -dmS $(BACKEND_SESSION) bash -lc 'cd "$(CURDIR)" && $(PYTHON) -m uvicorn src.backend.app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT) >> "$(CURDIR)/$(BACKEND_LOG)" 2>&1'
	@$(SCREEN) -dmS $(FRONTEND_SESSION) bash -lc 'cd "$(CURDIR)" && $(NPM) --prefix src/frontend run dev -- --host $(FRONTEND_HOST) --port $(FRONTEND_PORT) >> "$(CURDIR)/$(FRONTEND_LOG)" 2>&1'
	@echo "Servers are running in screen sessions:"
	@echo "  $(BACKEND_SESSION)"
	@echo "  $(FRONTEND_SESSION)"
	@echo "Logs:"
	@echo "  $(BACKEND_LOG)"
	@echo "  $(FRONTEND_LOG)"
	@echo "Use 'make local-stop' to stop both gracefully."

local-stop:
	@frontend_sessions="$$( { $(SCREEN) -list || true; } | awk '/[.]$(FRONTEND_SESSION)[[:space:]]/ { print $$1 }')"; \
	if [[ -n "$$frontend_sessions" ]]; then \
		while read -r session; do \
			[[ -z "$$session" ]] && continue; \
			echo "Stopping Vite frontend ($$session) with q + Enter"; \
			$(SCREEN) -S "$$session" -X stuff $$'q\n'; \
			sleep 1; \
			$(SCREEN) -S "$$session" -X stuff $$'exit\n' 2>/dev/null || true; \
			sleep 1; \
			$(SCREEN) -S "$$session" -X quit 2>/dev/null || true; \
		done <<< "$$frontend_sessions"; \
	else \
		echo "Vite frontend session is not running"; \
	fi
	@backend_sessions="$$( { $(SCREEN) -list || true; } | awk '/[.]$(BACKEND_SESSION)[[:space:]]/ { print $$1 }')"; \
	if [[ -n "$$backend_sessions" ]]; then \
		while read -r session; do \
			[[ -z "$$session" ]] && continue; \
			echo "Stopping Uvicorn backend ($$session) with Ctrl-C"; \
			$(SCREEN) -S "$$session" -X stuff $$'\003'; \
			sleep 1; \
			$(SCREEN) -S "$$session" -X stuff $$'exit\n' 2>/dev/null || true; \
			sleep 1; \
			$(SCREEN) -S "$$session" -X quit 2>/dev/null || true; \
		done <<< "$$backend_sessions"; \
	else \
		echo "Uvicorn backend session is not running"; \
	fi

local-logs-backend:
	@touch $(BACKEND_LOG)
	tail -f $(BACKEND_LOG)

local-logs-frontend:
	@touch $(FRONTEND_LOG)
	tail -f $(FRONTEND_LOG)

local-backend:
	$(PYTHON) -m uvicorn src.backend.app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

local-frontend:
	$(NPM) --prefix src/frontend run dev -- --host $(FRONTEND_HOST) --port $(FRONTEND_PORT)

local-test:
	$(PYTHON) -m pytest

local-eval:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

local-eval-baseline:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_BASELINE_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

local-eval-compare:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0 \
		--compare-baseline $(EVAL_BASELINE_PATH)

local-eval-postgres:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--retriever-backend postgres \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

local-eval-postgres-compare:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--retriever-backend postgres \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0 \
		--compare-baseline $(EVAL_BASELINE_PATH)

groundedness-eval:
	$(DOCKER_API_RUN) python -m evals.run_groundedness_eval \
		--gold-path $(GROUNDEDNESS_GOLD_PATH) \
		--output-path $(GROUNDEDNESS_OUTPUT_PATH) \
		--debug-log-path $(GROUNDEDNESS_DEBUG_LOG_PATH) \
		--judge-mode $(GROUNDEDNESS_JUDGE_MODE) \
		--require-groundedness-score 0.80 \
		--require-critical-unsupported-rate 0.0 \
		--require-conflict-rate 0.0

local-groundedness-eval:
	$(PYTHON) -m evals.run_groundedness_eval \
		--gold-path $(GROUNDEDNESS_GOLD_PATH) \
		--output-path $(GROUNDEDNESS_OUTPUT_PATH) \
		--debug-log-path $(GROUNDEDNESS_DEBUG_LOG_PATH) \
		--retriever-backend faiss \
		--judge-mode $(GROUNDEDNESS_JUDGE_MODE) \
		--require-groundedness-score 0.80 \
		--require-critical-unsupported-rate 0.0 \
		--require-conflict-rate 0.0

docker-up:
	$(DOCKER_COMPOSE) up --build

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-test:
	$(DOCKER_COMPOSE) build api worker
	$(DOCKER_COMPOSE) up -d postgres redis worker
	$(DOCKER_COMPOSE) run --rm api python -m pytest

docker-migrate:
	$(DOCKER_COMPOSE) run --rm migrate

docker-db-shell:
	$(DOCKER_COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

docker-worker-logs: logs-worker

docker-ingest:
	$(DOCKER_API_RUN) python -m src.backend.app.scripts.run_document_ingest --wait --job-mode full --source-type mounted_data --requested-paths data

docker-verify-corpus:
	$(DOCKER_API_RUN) python -m src.backend.app.scripts.verify_corpus

docker-eval: eval-postgres-compare

docker-prod-up:
	$(DOCKER_COMPOSE_PROD) up --build -d

docker-prod-down:
	$(DOCKER_COMPOSE_PROD) down

docker-prod-logs:
	$(DOCKER_COMPOSE_PROD) logs -f api worker frontend

docker-prod-test:
	$(DOCKER_COMPOSE_PROD) config --quiet

define switch_retriever
	@grep -q '^RETRIEVER_BACKEND=' .env && \
		perl -0pi -e 's/^RETRIEVER_BACKEND=.*/RETRIEVER_BACKEND=$(1)/m' .env || \
		printf '\nRETRIEVER_BACKEND=$(1)\n' >> .env
	@$(DOCKER_COMPOSE) up -d --force-recreate api worker
	@echo "Retriever switched to $(1)"
endef

retriever-faiss:
	$(call switch_retriever,faiss)

retriever-postgres:
	$(call switch_retriever,postgres)
	@$(DOCKER_API_RUN) python -m src.backend.app.scripts.run_document_ingest \
		--wait \
		--job-mode full \
		--source-type mounted_data \
		--requested-paths data
