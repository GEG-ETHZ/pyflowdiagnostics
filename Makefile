help:
	@echo "Commands:"
	@echo ""
	@echo "  install        install in editable mode"
	@echo "  dev-install    install in editable mode with dev requirements"
#	@echo "  pytest         run the test suite and report coverage"
	@echo "  ruff           check with ruff"
	@echo "  html           build docs (update existing)"
	@echo "  html-clean     build docs (new, removing any existing)"
	@echo "  preview        renders docs in Browser"
#	@echo "  linkcheck      check all links in docs"
	@echo "  clean          clean up all generated files"
	@echo ""

install:
	python -m pip install -e .

dev-install:
	python -m pip install -e .[all]

pytest:
	rm -rf .coverage htmlcov/ .pytest_cache/ && pytest --cov=pyflowdiagnostics && coverage html

ruff:
	ruff check

html:
	cd docs && make html

html-clean:
	cd docs && rm -rf api/pyflowdiagnostics* && rm -rf _build/ && make html

preview:
	xdg-open docs/_build/html/index.html

linkcheck:
	cd docs && make linkcheck

clean:
	python -m pip uninstall pyflowdiagnostics -y
	rm -rf build/ dist/ .eggs/ pyflowdiagnostics.egg-info/ pyflowdiagnostics/version.py  # build
	rm -rf */__pycache__/ */*/__pycache__/      # python cache
	rm -rf .coverage htmlcov/ .pytest_cache/    # tests and coverage
	rm -rf docs/api/pyflowdiagnostics* docs/_build/ docs/savefig/ # docs
