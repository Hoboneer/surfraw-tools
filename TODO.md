# TODO List

- Add comment to generated scripts that it was the result of running `mkelvis`?
- Allow options to be specified (flags, yes/no options, options with fixed set
  of valid args)
	- Generate bash completions
		- Prevent a space being added when completing option names with
		  arguments
	- As part of this, perhaps ask surfraw devs to add completion support
	  to all of the elvi (maybe get `mkelvis` used?)
- Make installable via `pip`
	- Create `setup.py` file
	- Make the program a Python package
	- Upload to PyPI
- Add more option types
	- `results`: An option implementing elvi-specific results as suggested
	  by `SURFRAW_results`. This may also need to have its own specific
`--map-*` option (with the regular mapping option preventing it to be done?).
	- More generally, a `nat`ural number option type to be the underlying
	  "type" of the `results` option.
- Make help messages and metavariables more helpful and clear
- Allow aliases to target enum member options
- Put in comment in generated elvi: the example mappings in comments only work
  as-is if the `search_url` is not provided with the parameter for search
queries opened, but instead simply have the query string opened, with the
`--query-parameter` specified.
- Separate options into groups in help output for `mkelvis` and co.
