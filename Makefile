clean:
	find . -name \*.pyc -delete
	find . -name \*.so -delete
	find . -name __pycache__ -delete
	rm -rf .coverage build dist *.egg-info

build:
	python setup.py sdist bdist_wheel

upload:
	twine upload dist/*

install:
	pip install .

testing_install:
	pip install '.[test]'

test:
	PYTHONPATH=. pytest tests
