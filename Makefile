# `SPEC_FILE` specifies the args to pass to `./mkelvis`, where newline is the
# record separator.
SPEC_FILE := elvi
OUTPUTS := $(shell cut -f 1 -d ' ' $(SPEC_FILE))

all: $(OUTPUTS)
$(OUTPUTS): $(SPEC_FILE)
	grep '^$@' $< | xargs ./mkelvis

clean:
	rm -- $(OUTPUTS)
