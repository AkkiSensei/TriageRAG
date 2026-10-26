.PHONY: all verify lint format test eval ui validate-data clean

PYTHON ?= python

all: verify

verify:
	$(PYTHON) tools/tasks.py verify

lint:
	$(PYTHON) tools/tasks.py lint

test:
	$(PYTHON) tools/tasks.py test

eval:
	$(PYTHON) tools/tasks.py eval

ui:
	$(PYTHON) tools/tasks.py ui

validate-data:
	$(PYTHON) tools/tasks.py validate-data

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
