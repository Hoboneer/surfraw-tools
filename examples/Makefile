SPECS := $(wildcard *.in)

ELVI := $(SPECS:.in=.elvis)
COMPLETIONS := $(SPECS:.in=.completion)

OUTPUTS := $(ELVI) $(COMPLETIONS)

.PHONY: all
all: $(OUTPUTS)

# The elvi are all prefixed with .elvis because it is easier to generate them
# with makefiles this way.
%.elvis: %.in
	cat $< | xargs mkelvis
	mv $(basename $@) $@

%.completion: %.in
	cat $< | xargs mkelviscomps

.PHONY: clean
clean:
	rm -f -- $(OUTPUTS)
