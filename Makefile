REQUIREMENTS_DIR := requirements

PACKAGE_DIR := surfraw_tools
SOURCE_FILES := $(shell find "$(PACKAGE_DIR)" -type f -name '*.py')

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
