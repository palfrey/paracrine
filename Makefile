.PHONY: build
build: sync
	.venv/bin/python -m build

testpypi: sync
	.venv/bin/twine upload -r testpypi dist/*

pypi: sync
	.venv/bin/twine upload dist/*

.PHONY: docs
docs: sync
	.venv/bin/pdoc --html paracrine --force --output-dir docs

type-check: sync
	.venv/bin/pyright --pythonversion 3.9 --pythonpath $(PWD)/.venv/bin/python paracrine integration_test tests

watch-type-check: sync
	.venv/bin/pyright --pythonversion 3.9 --pythonpath $(PWD)/.venv/bin/python --watch paracrine integration_test tests

unittests-watch: sync
	.venv/bin/ptw -- -vvv tests/

requirements.txt: requirements.in pyproject.toml
	uv pip compile --no-strip-extras requirements.in -o requirements.txt

.venv/bin/python:
	uv venv

sync: requirements.txt .venv/bin/python
	uv pip sync requirements.txt

pre-commit: sync
	./.venv/bin/pre-commit run -a
