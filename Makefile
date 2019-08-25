REQUIREMENTS_DIR := requirements

PACKAGE_DIR := surfraw_tools
SOURCE_FILES := $(shell find "$(PACKAGE_DIR)" -type f -name '*.py')

BLACK_FLAGS := --line-length=79 --target-version=py36
# Prevent `black` from unnecessarily reformatting `isort` output.
ISORT_FLAGS := --trailing-comma --use-parentheses --atomic --line-width=79 --multi-line=3

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
.formatted: $(SOURCE_FILES) setup.py
	isort $(ISORT_FLAGS) $(SOURCE_FILES) setup.py
	black $(BLACK_FLAGS) $(SOURCE_FILES) setup.py
	$(MAKE) tags
	touch .formatted

.PHONY: format
format: .formatted

.PHONY: lint
lint:
	flake8 $(SOURCE_FILES)
