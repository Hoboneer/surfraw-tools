# Generating requirements files with pip-tools.
REQUIREMENTS_FILES := $(wildcard *.in)
FROZEN_REQUIREMENTS_FILES := $(REQUIREMENTS_FILES:.in=.txt)
PIP_COMPILE_FLAGS := --generate-hashes --verbose

.PHONY: all
all: $(FROZEN_REQUIREMENTS_FILES)

.PHONY: clean
clean:
	rm -- $(FROZEN_REQUIREMENTS_FILES)

%.txt: %.in
	pip-compile $(PIP_COMPILE_FLAGS) --output-file $@ $<

# Dependency ordering
dev.txt: base.txt
