SPECS := $(wildcard *.in)
OUTPUTS := $(SPECS:.in=.elvis)

.PHONY: all
all: $(OUTPUTS)

# The elvi are all prefixed with .elvis because it is easier to generate them
# with makefiles this way.
%.elvis: %.in
	cat $< | xargs mkelvis
	mv $(basename $@) $@

.PHONY: clean
clean:
	rm -f -- $(OUTPUTS)
