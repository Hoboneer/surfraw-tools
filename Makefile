REQUIREMENTS_DIR := requirements

PACKAGE_DIR := surfraw_tools
SOURCE_FILES := $(wildcard $(PACKAGE_DIR)/*.py)
CHECK_FILES := $(SOURCE_FILES) setup.py jinjac.py

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
