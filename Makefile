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

.PHONY: help install install-python install-frontend dev stop logs-backend logs-frontend backend frontend test eval eval-baseline eval-compare

help:
	@echo "Available targets:"
	@echo "  make install           Install Python and frontend dependencies"
	@echo "  make dev               Start backend and frontend dev servers"
	@echo "  make stop              Gracefully stop servers started by make dev"
	@echo "  make logs-backend      Follow the backend server log"
	@echo "  make logs-frontend     Follow the frontend server log"
	@echo "  make backend           Start only the FastAPI backend"
	@echo "  make frontend          Start only the Vite frontend"
	@echo "  make test              Run the Python test suite"
	@echo "  make eval              Run retrieval evals without answer generation"
	@echo "  make eval-baseline     Regenerate the FAISS hybrid+rerank baseline"
	@echo "  make eval-compare      Run evals and compare against the baseline"

install: install-python install-frontend

install-python:
	$(PYTHON) -m pip install -r requirements.txt

install-frontend:
	$(NPM) --prefix src/frontend install

dev:
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
	@echo "Use 'make stop' to stop both gracefully."

stop:
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

logs-backend:
	@touch $(BACKEND_LOG)
	tail -f $(BACKEND_LOG)

logs-frontend:
	@touch $(FRONTEND_LOG)
	tail -f $(FRONTEND_LOG)

backend:
	$(PYTHON) -m uvicorn src.backend.app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

frontend:
	$(NPM) --prefix src/frontend run dev -- --host $(FRONTEND_HOST) --port $(FRONTEND_PORT)

test:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_OUTPUT_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

eval-baseline:
	$(PYTHON) -m evals.run_retrieval_eval \
		--gold-path $(EVAL_GOLD_PATH) \
		--output-path $(EVAL_BASELINE_PATH) \
		--debug-log-path $(EVAL_DEBUG_LOG_PATH) \
		--modes hybrid_rerank \
		--skip-answer-generation \
		--require-source-hit-rate 1.0 \
		--require-mrr 1.0 \
		--require-top-1-accuracy 1.0

eval-compare:
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
