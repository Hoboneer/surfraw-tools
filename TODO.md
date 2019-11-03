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
- Evaluate user-provided search url as late as possible:
	- To allow the results of option checking, variable collapsing, and
	  enum checks to be used in the resultant search url.
	- Useful to allow the options to manipulate parts of the search url
	  *other* than the query parameters. Potentially allows for *any*
snippet of shell code to be executed, so it can be as complex as users need it
to be.
	- Do option checking even with no args? This is to allow any variable
	  mutations to propagate to the base url.
