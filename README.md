<!--
SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# surfraw-tools

These are command line tools to generate
[surfraw](https://www.techrepublic.com/blog/linux-and-open-source/surfing-the-world-wide-web-raw-style/)
scripts easily.  Hosted on
[GitHub](https://github.com/Hoboneer/surfraw-elvis-generator).

The following are currently provided:

* `mkelvis`: Generate a single surfraw elvis per invocation.  Code for
  completions is also generated inside the output elvis.

## Copyright

This project is licensed under the Apache License 2.0 (sic) and follows the
[REUSE licencing guidelines](https://reuse.software).  Some auxiliary files
have a different licence.  Check their file headers or `.reuse/dep5` for
details.  Copies of the licences used in this project can be located in the
`LICENSES/` directory, per the REUSE guidelines.

## Installation

`surfraw-tools` is available on PyPI.
[pipx](https://github.com/pipxproject/pipx) is recommended to install.  It is
available in the distro repositories.

```sh
pipx install surfraw-tools
```

See `INSTALL.md` for more details.

## Quickstart

Specify your elvis to generate with the three positional arguments as shown:

```sh
mkelvis yourelvisname www.domain.com www.domain.com/search?q=
```

Notice that the final argument has an open query string for the `q` parameter.
This is intentional; it is where your search terms will be placed.

The created elvis will be placed in the current directory with the name
`yourelvisname`, and ready for installation (made executable, shebang added).

### Caveats

At the time of writing, this program generates completion code for surfraw elvi
for my work-in-progress system of elvi-specific completions.  Check the merge
requests in the [main surfraw repo](https://gitlab.com/surfraw/Surfraw).  If
you don't want to use the WIP completions, use the `--no-completions` option.

## Option types

`mkelvis` offers a selection of types that each option may have.  Each of these
types have special properties and interact with the other types in their own
ways.  They have a "typename" which is used to refer to types.  Unless
otherwise stated: their values are validated every time the generated elvis is
run, and each option creates a variable with the pattern
`SURFRAW_${yourelvisname}_${thevariable}`.

### Boolean options (typename: `bool`, synonyms: `yes-no`)

Created with: `--yes-no=`

This is one of the simplest option types, corresponding to the surfraw options
checked with `yesno` in elvi.

The valid arguments are (in elvi):

  - `yes`, `on`, `1`: True
  - `no`, `off`, `0`: False

For simplicity, `--yes-no` only accepts `yes` for true and `no` for false.
File an issue if you need the other values to be accepted.

### Enum options (typename: `enum`)

Created with: `--enum=`

This is a common option type where only a fixed set of values is valid.  This
set of values must be specified for every enum.

### "Anything" options (typename: `anything`)

Created with: `--anything=`

An unchecked option: the values of this type are *not* checked by elvi.  Useful
for websites whose search syntax is too complex or is really an option that
*could* contain anything, like target users.

### Special options (typename: `special`)

Created with: `--use-results-option` (1), `--use-language-option` (2)

Singleton options that implement behaviour common to many elvi:

  1. A `-results=NUM` option whose default value is taken from `SURFRAW_results`
  2. A `-language=ISOCODE` option whose default value is taken from `SURFRAW_lang`

### List options (typename: `list`)

Created with: `--list=`

An option that specifies list-like behaviour for a variable whose elements are
of a single type.  Generates `-add-$optname=`, `-remove-$optname=`, and
`-clear-$optname` options for every list option.

* `-add-$optname=VALS`: Append `VALS` to list variable.
* `-remove-$optname=VALS`: Remove *all* instances of `VALS` from list variable.
* `-clear-$optname`: Clear list variable.

The valid list types are:

  - `enum`
  - `anything`

### Flag options (typename: `flag`)

Created with: `--flag=`

An alias (with a value) to one of the above options--all of which create
variables in the generated elvis (hereafter "variable options").  This is
essentially a shorthand for specifying `-opt=commonval` as `-c`, for example.
Creates no variable.

### Alias options (typename: `alias`)

Created with: `--alias=`

An alias (without a value) to either a variable option or flag option.  This is
essentially a synonym for another option.  Aliases *cannot* target other
aliases.  Creates no variable.

Examples:

  - `-s`: Alias for `-sort` (a flag)
  - `-l=`: Alias for `-language=`.  The user would still have to specify the
    value.

## Manipulating variables

`mkelvis` provides a `--collapse=VARNAME:VAL1,VAL2,RESULT:...` option which
corresponds to a shell case-statement.  Each argument after `VARNAME` is a list
where the *last* value (`RESULT` in this case) is a shell snippet that the
other values (`VAL1` and `VAL2` here) are converted to.  `RESULT` is not
escaped so it may include command substitutions (please stick to POSIX shell).

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

## Making many elvi at once

`mkelvis` only generates one elvis per invocation, deferring the method to
create multiple elvi to the user.  An example follows.

For many simple elvi, a single text file may be sufficient. It shall be called
`elvi` here.

First, specify the elvi you want by putting the arguments to `mkelvis` for each
elvis to generate on separate lines. The name should have no whitespace.

Example `elvi` file:

```
reddit www.reddit.com www.reddit.com/search?q=
subreddit www.reddit.com www.reddit.com/subreddits/search?q= --description='Visit a subreddit'
```

These may then be generated by `make`, in whichever way is desired.

See [my elvi repo](https://github.com/Hoboneer/surfraw-elvis) for more examples.
