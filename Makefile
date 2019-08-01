# `SPEC_FILE` specifies the args to pass to `./mkelvis`, where newline is the
# record separator.
SPEC_FILE := elvi
# This relies on elvi having no whitespace in their name (which seems to be
# the case for all of them anyway).
OUTPUTS := $(shell cut -f 1 -d ' ' $(SPEC_FILE))
ELVI_DIR := /usr/lib/surfraw/

all: $(OUTPUTS)
$(OUTPUTS): $(SPEC_FILE)
	grep '^$@' $< | xargs ./mkelvis

.PHONY: clean
clean:
	rm -- $(OUTPUTS)

.PHONY: install
install:
	echo $(OUTPUTS) | xargs cp --no-clobber --target=$(ELVI_DIR) --

.PHONY: uninstall
uninstall:
	cd $(ELVI_DIR) && rm -- $(OUTPUTS)
