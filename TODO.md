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
- Add special-cased options:
	- language/lang: Uses the value in `SURFRAW_lang` as a default value
	- results: Uses the value in `SURFRAW_results` as a default value
- Make help messages and metavariables more helpful and clear:
	- Generate -local-help output for local options
- Put in comment in generated elvi: the example mappings in comments only work
  as-is if the `search_url` is not provided with the parameter for search
queries opened, but instead simply have the query string opened, with the
`--query-parameter` specified.
- Separate options into groups in help output for `mkelvis` and co.
- Add "inline" options maybe?  This would be similar to `--map` but would
  instead place the values _inside_ the search query in an undefined location
(it *may* be before or after the search terms).
- Add "cumulative" or "list" options (choose one or both names)?  This would
  allow the user to specify an option like `-filter=` multiple times and not
override their options.  Should it require the user to specify the type?
Perhaps the option would be shown to the user as:
	- `-add-foo=`: Add a valid value of `foo` to the list.  This would also
	  allow passing multiple values in the form `-add-foo=bar,baz`.
	- `-remove-foo=`: Remove a value of `foo` from the list.  This would
	  also allow passing of multiple values in the form
`-remove-foo=bar,baz`.  Should the error checking for this one be less strict?
i.e., should it ignore invalid values?
	- `-clear-foo`: Clear the list.
- Add an "ESCAPE?" argument to `--map` (bool).  This would specify any options
  whose argument is *already* url encoded, so don't double encode.  By default,
url encode everything that is mapped into a url.  For backwards compatibility,
the new argument should be optional.
- Either:
	1. Allow special chars to mkelvis to be escaped; or
	2. Allow changing the argument delimiter with an option like
`--delimiter` (short: `-d`)
- The first one would require a less fundamental change in the program's
  structure.
- Rearrange `-local-help` output for enum list options.  Where should the valid
  values be shown?  Maybe 'clear' could be moved to be the middle option?
