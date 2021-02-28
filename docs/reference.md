# Reference

`mkelvis` allows you to easily create common types of options found in surfraw
elvi.  Most these types validate their values at runtime.  They each have a
"typename" which is used in some `mkelvis` options to disambiguate their target
(e.g., `--alias=`).

## Main elvis options

These options create variables corresponding to their name with the pattern
`SURFRAW_${yourelvisname}_${thevariable}`.  They can't conflict.

### Boolean options (typename: `bool`, synonyms: `yes-no`)

Created with: `--yes-no=VARNAME:DEFAULT`

This is one of the simplest option types, corresponding to the surfraw options
checked with `yesno` in elvi.

The valid arguments are (in elvi):

  - `yes`, `on`, `1`: True
  - `no`, `off`, `0`: False

For simplicity, `--yes-no` only accepts `yes` for true and `no` for false.
File an issue if you need the other values to be accepted.

### Enum options (typename: `enum`)

Created with: `--enum=VARNAME:DEFAULT:VAL1,VAL2,...`

This is a common option type where only a fixed set of values is valid.  This
set of values must be specified for every enum.

### "Anything" options (typename: `anything`)

Created with: `--anything=VARNAME:DEFAULT`

An unchecked option: the values of this type are *not* checked by elvi.  Useful
for websites whose search syntax is too complex or is really an option that
*could* contain anything, like target users.

### Special options (typename: `special`)

Created with: `--use-results-option` (1), `--use-language-option` (2)

Singleton options that implement behaviour common to many elvi:

  1. A `-results=NUM` option whose default value is taken from `SURFRAW_results`
  2. A `-language=ISOCODE` option whose default value is taken from `SURFRAW_lang`

### List options (typename: `list`)

Created with: `--list=VARNAME:TYPE:DEFAULT1,DEFAULT2,...[:VALID_VALUES_IF_ENUM]`

An option that specifies list-like behaviour for a variable whose elements are
of a single type.  Generates `-add-$optname=`, `-remove-$optname=`, and
`-clear-$optname` options for every list option.

* `-add-$optname=VALS`: Append `VALS` to list variable.
* `-remove-$optname=VALS`: Remove *all* instances of each value of `VALS` from list variable.
* `-clear-$optname`: Clear list variable.

The valid list types are:

  - `enum`
  - `anything`

## Auxiliary elvis options

These options help make the generated elvi quicker to use.  They don't create
variables.

### Flag options (typename: `flag`)

Created with: `--flag=`

An alias (with a value) to one of the above options--all of which create
variables in the generated elvis (hereafter "variable options").  This is
essentially a shorthand for specifying `-opt=commonval` as `-c`, for example.

### Alias options (typename: `alias`)

Created with: `--alias=`

An alias (without a value) to either a variable option or flag option.  This is
essentially a synonym for another option.  Aliases *cannot* target other
aliases.

Since aliases can target variable options *and* flag options, they take a
typename to disambiguate.

Examples:

  - `-s`: Alias for `-sort` (a flag)
  - `-l=`: Alias for `-language=`.  The user would still have to specify the
    value.

## Manipulating variables

`mkelvis` provides a `--collapse=VARNAME:VAL1,VAL2,RESULT:...` option which
corresponds to a shell case-statement.  Each argument after `VARNAME` is a list
where the *last* value (`RESULT` in this case) is a shell snippet that the
other values (`VAL1` and `VAL2` here) are converted to.  `RESULT` is not
escaped so it can include parameter expansions and command substitutions
(please stick to POSIX shell).

Within `RESULT`, you can access `$it`, which is an alias for the current
option's variable.  The variables for the other options are in an undefined
state at this point--don't reference them here.

This roughly corresponds to:

```sh
case "$varname" in
	VAL1|VAL2) varname="RESULT" ;;
esac
```

## Map variables to URL

Variables may each be "mapped" or "inlined" to a query parameter in the URL or
as a keyword in the search query respectively.

### Mapping

`--map=VAR:PARAM[:URL_ENCODE?]`

Map variable `VAR` to `PARAM` like so: `https://example.com/?PARAM=$VAR`.

If `URL_ENCODE` is `yes` (default), then the value of `VAR` is percent-encoded;
if `no` then `$VAR` is left as it is.

`--list-map=VAR:PARAM[:URL_ENCODE?]`

Similar to `--map=` but `VAR` is treated like a list and each value is mapped
to a separate `PARAM` query parameter.  If the list is empty, then `PARAM` will
have an empty value like so: `https://example.com/?PARAM=`.

### Inlining

`--inline=VAR:KEYWORD`

Inline variable `VAR` to `KEYWORD` in the search query like so:
`https://example.com/?q=search+arg+KEYWORD:$VAR`.  If `$VAR` has whitespace,
then it will be wrapped in double quotes.  If `$VAR` is empty, then `VAR` will
not be inlined.

`--list-inline=VAR:KEYWORD`

Similar to `--inline=` but `VAR` is treated like a list and each value is
mapped to a separate `KEYWORD` in the search query, double-quoting if needed
(see `--inline=`).  If the list is empty, then `VAR` will not be inlined at
all.

## Control over search URL

Where the mappings and search terms (which includes the inlinings) are exactly
placed in the URL can each be independently controlled using the
`--no-append-mappings` and `--no-append-args` options respectively.  

Like with `--collapse=`, parameter expansions and command substitutions are
available in the search URL string (and the base URL too).  The `$mappings` and
`$it` (search terms and inlinings) variables are available.  You have the
responsibility of ensuring that these go into the URL correctly.

## Miscellaneous options

Here are some other useful options.  See `mkelvis --help` for any others
missed.

* `--description=DESCRIPTION`: Set the elvis description, excluding its domain
  name.
* `--query-parameter=PARAM`: Define the query parameter to be appended to the
  URL (mandatory if `--map=` or `--list-map=` are used).
* `--metavar=VAR:METAVAR`: Set the metavar of the variable option `VAR` to
  `METAVAR` (in `-local-help`), which is capitalised automatically.
* `--describe=VAR:DESCRIPTION`: Set the description of the variable option
  `VAR` to `DESCRIPTION` (in `-local-help`).
