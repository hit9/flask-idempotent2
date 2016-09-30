lint:
	flake8 tests ./*.py

unittest: lint
	py.test tests

.PHONY: lint unittest
