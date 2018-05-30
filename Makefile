clean:
	find . -name \*.pyc -delete
	find . -name \*.so -delete
	find . -name __pycache__ -delete
	rm -rf .coverage build dist *.egg-info .pytest_cache

build:
	python setup.py sdist bdist_wheel

upload:
	twine upload dist/*

install:
	pip install .

testing_install:
	pip install '.[test]'

test:
	flake8 tc_mailmanager tests
	PYTHONPATH=. pytest tests
