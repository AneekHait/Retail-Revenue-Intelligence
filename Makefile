.PHONY: setup data analyze dashboard test clean all

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
STREAMLIT := .venv/bin/streamlit

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

data:
	$(PYTHON) -c "from src.generate_data import run; run()"

analyze:
	$(PYTHON) scripts/run_analysis.py --skip-generate

all:
	$(PYTHON) scripts/run_analysis.py

dashboard:
	$(STREAMLIT) run dashboard/app.py

test:
	$(PYTHON) -m pytest

clean:
	rm -f data/raw/*.csv data/processed/*.csv
	rm -f reports/figures/*.png reports/insights.md reports/executive_summary.json
