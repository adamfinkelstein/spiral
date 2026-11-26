# Common tasks. `make` alone lists them.

PY := .venv/bin/python
PORT ?= 8000
JSC := /System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc
JS := $(wildcard *.js)

.DEFAULT_GOAL := help
.PHONY: help setup open serve card rerun check-js deploy deploy-status

help:  ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

setup:  ## make the Python environment (.venv) and install requirements.txt
	python3 -m venv .venv && $(PY) -m pip install -r requirements.txt

open:  ## open index.html in the browser, straight from disk
	open index.html

serve:  ## serve this folder at http://localhost:8000 (PORT=... to change; not needed to view the pages)
	$(PY) -m http.server $(PORT)

card:  ## rebuild card.html and card/img from the cached results (~1 min)
	$(PY) build_card.py

rerun:  ## rerun every simulated card, then rebuild card.html (several minutes)
	$(PY) build_card.py --rerun

check-js:  ## syntax-check the page scripts with JavaScriptCore
	$(JSC) -e "$(foreach f,$(JS),checkSyntax('$(f)');) print('ok: $(words $(JS)) files')"

deploy:  ## deploy what is on GitHub's main to GitHub Pages (a push alone doesn't)
	@git fetch -q origin main
	@if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse origin/main)" ]; then \
	  echo "Note: local HEAD differs from origin/main; Pages gets origin/main ($$(git rev-parse --short origin/main))."; fi
	gh workflow run pages.yml --ref main
	@echo "Started. Follow it with: make deploy-status"

deploy-status:  ## the last few Pages deployments
	gh run list --workflow pages.yml --limit 5
