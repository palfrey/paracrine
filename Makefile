build:
	python -m build

.PHONY: build

testpypi:
	twine upload -r testpypi dist/*

pypi:
	twine upload dist/*

docs:
	pdoc --html paracrine --force --output-dir docs
	mv docs/paracrine/* docs
	rmdir docs/paracrine

.PHONY: docs
