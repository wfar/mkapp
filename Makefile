SHFMT := uv run shfmt
SHELLCHECK := uv run shellcheck
RUFF := uv run ruff
PYTEST := uv run pytest
PIP_AUDIT := uv run pip-audit

GIT_LS := git ls-files --cached --others --exclude-standard
SH_FILES := $(wildcard $(shell $(GIT_LS) '*.sh'))
PY_FILES := $(wildcard $(shell $(GIT_LS) '*.py'))

# Extra flags for `make test`, e.g. make test ARGS=--quick
ARGS ?=

.PHONY: help install format lint audit clean test
.DEFAULT_GOAL := help

help:
	@printf 'Targets:\n'
	@printf '  install  install dev dependencies and the pre-commit hooks\n'
	@printf '  format   format shell and Python files\n'
	@printf '  lint     report linting problems\n'
	@printf '  audit    check locked dependencies for known vulnerabilities\n'
	@printf '  test     run the test suite (ARGS=--quick for the quick tests only)\n'
	@printf '  clean    remove caches and test build output\n'

install:
	uv sync
	uv run pre-commit install

format:
	$(if $(SH_FILES),$(SHFMT) -w $(SH_FILES),@printf 'no shell files to format\n')
	$(if $(PY_FILES),$(RUFF) format $(PY_FILES),@printf 'no Python files to format\n')

lint:
	$(if $(SH_FILES),$(SHELLCHECK) $(SH_FILES),@printf 'no shell files to lint\n')
	$(if $(PY_FILES),$(RUFF) check $(PY_FILES),@printf 'no Python files to lint\n')

audit:
	@reqs=$$(mktemp) && trap 'rm -f "$$reqs"' EXIT && \
		uv export --frozen --all-groups --no-emit-project --quiet -o "$$reqs" && \
		$(PIP_AUDIT) --require-hashes --disable-pip --progress-spinner off --requirement "$$reqs"

clean:
	@printf 'Cleaning up...\n'
	@find . \( -name .git -o -name .venv \) -prune -o -type d \
		\( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) \
		-prune -exec rm -rf {} +
	@find tests -type d \( -name dist -o -name build \) -prune -exec rm -rf {} +
	@find tests -type f -name '*.spec' -delete
	@printf 'Done cleaning up.\n'

test:
	$(PYTEST) tests/ $(ARGS)
