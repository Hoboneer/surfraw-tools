# TODO List

- Allow options to be specified (flags, yes/no options, options with fixed set
  of valid args)
	- Generate bash completions
		- Prevent a space being added when completing option names with
		  arguments
	- As part of this, perhaps ask surfraw devs to add completion support
	  to all of the elvi (maybe get `mkelvis` used?)
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
- Add `--disable-auto-args` (TODO: get a better name)?  This would allow for
  greater control in the `search_url`.
- Add a "topic" variable akin to perl?  Should `$_` be its name?  It would
  follow perl's case, but I'm not sure if this means what I think it means.
This would allow the user to easily refer to the current "thing" being operated
on (e.g., in each branch of --collapse, ...other examples?)
