.DEFAULT_GOAL := all
black = poetry run black tc_mailmanager tests
isort = poetry run isort tc_mailmanager tests

.PHONY: install
install:
	poetry install
	poetry run pre-commit install

.PHONY: format
format:
	poetry run pre-commit run --all-files

.PHONY: lint
lint:
	poetry run flake8 tc_mailmanager tests
	$(black) --diff --check
	$(isort) --check-only

.PHONY: mypy
mypy:
	poetry run mypy .

.PHONY: test
test:
	poetry run pytest --cov=tc_mailmanager --cov-report xml --cov-report term-missing

.PHONY: all
all: lint mypy test

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -rf .coverage coverage.xml build dist *.egg-info .pytest_cache .mypy_cache

.PHONY: build
build:
	poetry build

.PHONY: upload
upload:
	poetry publish
