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
	python -m pyright --pythonversion 3.9 paracrine integration_test tests

watch-type-check:
	python -m pyright --pythonversion 3.9 --watch paracrine integration_test tests

unittests-watch:
	ptw -- -vvv tests/
