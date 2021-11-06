# SPDX-FileCopyrightText: 2020, 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

REQUIREMENTS_DIR := requirements

PACKAGE_DIRS := surfraw_tools surfraw_tools/lib
SOURCE_FILES := $(foreach dir, $(PACKAGE_DIRS), $(wildcard $(dir)/*.py)) $(wildcard tests/*.py)
CHECK_FILES := $(SOURCE_FILES) setup.py

# Do nothing.
.PHONY: all
all:

.PHONY: requirements
requirements:
	cd $(REQUIREMENTS_DIR) && $(MAKE)

tags: $(SOURCE_FILES)
	ctags $(SOURCE_FILES)

# Ensure that `isort` and `black` are not run unnecessarily.
.formatted: $(CHECK_FILES)
	isort $?
	black $?
	$(MAKE) tags
	touch .formatted

.PHONY: format
format: .formatted

.PHONY: check-dev
check-dev: typecheck lint test

.PHONY: typecheck
typecheck:
	mypy -p surfraw_tools

.PHONY: lint
lint:
	flake8 $(CHECK_FILES)

.PHONY: test
test:
	pytest

.PHONY: clean
clean:
	-rm -fr *.egg-info/
	-rm -fr build/
	-rm -fr dist/

.PHONY: check-copyright
check-copyright:
	reuse lint

.PHONY: dist
dist: format check-dev check-copyright
	@# No wheel because jinja2 versions at build- and runtime need to match.
	python setup.py sdist
	twine check dist/*

.PHONY: upload
upload:
	twine upload dist/*
