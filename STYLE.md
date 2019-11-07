# Style Guide

## Python code

Follow the `black` code style, enforced by the formatter of the same name. Just
run `make format` to do it automatically.

## Templates

Names should only contain ASCII digits and letters, as well as single
underscores between words.

Variables should follow these rules:

- Constants for the program (not things derived from the arguments!) should be
  in SCREAMING\_SNAKE\_CASE (e.g., `GENERATOR_PROGRAM`)
- Metadata about the program arguments should be in \_\_prefixed\_snake\_case
  (e.g., `__passed_opts`)
- Otherwise, all variables should be in snake\_case

Tests:

- Tests for option types should be in the form `optiontype_option` (e.g.,
  `flag_option`)
- Otherwise, all tests should be in snake\_case

Filters:

- A short name should be provided *in addition to* a long-form name for commonly-used filters
- Filters should be in snake\_case
