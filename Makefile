PYTHON ?= .venv/bin/python
export PYTHONPATH := .

.PHONY: data truth tasks explore check test

data:
	$(PYTHON) -m src.data.fetch_gisco
	$(PYTHON) -m src.data.fetch_ons
	$(PYTHON) -m src.data.fetch_overture

truth:
	$(PYTHON) -m src.truth.build

tasks:
	$(PYTHON) -m src.tasks.generate

explore:
	$(PYTHON) explore/build.py

check:
	$(PYTHON) explore/check.py

test:
	$(PYTHON) -m pytest
