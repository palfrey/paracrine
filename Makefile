build:
	python -m build

.PHONY: build

testpypi:
	twine upload -r testpypi dist/*

pypi:
	twine upload dist/*

docs:
	pdoc --html paracrine --force --output-dir docs

.PHONY: docs

type-check:
	python -m pyright paracrine integration_test tests

watch-type-check:
	python -m pyright --watch paracrine integration_test tests
