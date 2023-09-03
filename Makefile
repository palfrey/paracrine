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
