# TODO List

- Allow options to be specified (flags, yes/no options, options with fixed set
  of valid args)
- Make installable via `pip`
	- Upload to PyPI
- Add more option types
	- `results`: An option implementing elvi-specific results as suggested
	  by `SURFRAW_results`. This may also need to have its own specific
`--map-*` option (with the regular mapping option preventing it to be done?).
	- More generally, a `nat`ural number option type to be the underlying
	  "type" of the `results` option.
- Put in comment in generated elvi: the example mappings in comments only work
  as-is if the `search_url` is not provided with the parameter for search
queries opened, but instead simply have the query string opened, with the
`--query-parameter` specified.
- Separate options into groups in help output for `mkelvis` and co.
- Either:
	1. Allow special chars to mkelvis to be escaped; or
	2. Allow changing the argument delimiter with an option like
`--delimiter` (short: `-d`)
- The first one would require a less fundamental change in the program's
  structure.
- Add `--list-collapse` option?  A backwards-incompatible change would have to
  made in order for symmetry with the other `--{list,}-*` options, however.
