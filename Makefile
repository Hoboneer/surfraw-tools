# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

REQUIREMENTS_DIR := requirements

PACKAGE_DIRS := surfraw_tools surfraw_tools/lib
SOURCE_FILES := $(foreach dir, $(PACKAGE_DIRS), $(wildcard $(dir)/*.py))
CHECK_FILES := $(SOURCE_FILES) setup.py

# Do nothing.
.PHONY: all
all:

.PHONY: init
init:
	pip install -r $(REQUIREMENTS_DIR)/base.txt

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

.PHONY: lint
lint:
	flake8 $(CHECK_FILES)

.PHONY: typecheck
typecheck:
	mypy -p surfraw_tools

.PHONY: clean
clean:
	-rm -fr *.egg-info/
	-rm -fr build/
	-rm -fr dist/

.PHONY: dist
dist: format lint typecheck
	@# No wheel because jinja2 versions at build- and runtime need to match.
	python setup.py sdist
	twine check dist/*

.PHONY: upload
upload:
	twine upload dist/*
