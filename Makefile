PYTHON ?= .venv/bin/python
export PYTHONPATH := .

.PHONY: data truth test

data:
	$(PYTHON) -m src.data.fetch_gisco
	$(PYTHON) -m src.data.fetch_ons
	$(PYTHON) -m src.data.fetch_overture

truth:
	$(PYTHON) -m src.truth.build

test:
	$(PYTHON) -m pytest
