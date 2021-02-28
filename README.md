<!--
SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# surfraw-tools

`surfraw-tools` is a suite of command-line tools to generate
[surfraw](https://www.techrepublic.com/blog/linux-and-open-source/surfing-the-world-wide-web-raw-style/)
elvi easily.

Hosted on [GitHub](https://github.com/Hoboneer/surfraw-elvis-generator).

Documentation is at TODO.

The following are currently provided:

* `mkelvis`: generate an elvis
* `opensearch2elvis`: generate an elvis for an OpenSearch-enabled website

## Installation

`surfraw-tools` is available on
[PyPI](https://pypi.org/project/surfraw-tools/).  Use
[pipx](https://github.com/pipxproject/pipx).  It's available in many distro
repositories.

```sh
pipx install surfraw-tools
```

See `INSTALL.md` for more details.

## Quickstart

### Generate a simple elvis
```sh
# these two are equivalent: https is the default url scheme
mkelvis yourelvisname example.com 'example.com/search?q='
mkelvis yourelvisname https://example.com 'https://example.com/search?q='

# use http for insecure websites
mkelvis yourelvisname --insecure example.com 'example.com/search?q='
mkelvis yourelvisname http://example.com 'http://example.com/search?q='

# with a description
mkelvis yourelvisname --description='Search Example for bliks' https://example.com 'https://example.com/search?q='

# to align in `sr-elvi`
mkelvis yourelvisname --num-tabs=NUM https://example.com 'https://example.com/search?q='
```

Leave the `q` URL parameter with an empty value because the search terms will
be appended to it when `yourelvisname` runs.  The first URL is where the elvis
takes you when no search terms have been passed.

### Create an elvis for an [OpenSearch](https://github.com/dewitt/opensearch)-enabled website
```sh
# find and download the OpenSearch description file, and then generate
opensearch2elvis yourelvisname https://example.com  # any HTML page under the domain should work

# download an OpenSearch description file and then generate
opensearch2elvis yourelvisname https://example.com/opensearch.xml

# generate from a local OpenSearch description file
opensearch2elvis yourelvisname opensearch.xml
```

The created elvis will be placed in the current directory with the name
`yourelvisname`, and ready for installation (made executable, shebang added).

See the advanced usage docs for more.

### Caveats

The generated elvi include tab-completion code using my *work-in-progress*
system of elvi-specific completions.  Check the merge requests in the [main
surfraw repo](https://gitlab.com/surfraw/Surfraw).

If you don't want to use the WIP completions, use the `--no-completions`
option.  This isn't needed though: the elvi still work but there might be a few
error messages.

Also, `opensearch2elvis` only has minimal support for websites that specify
POST method searches.  Currently, it just treats them as if they specified GET
and hopes for the best.  [I plan to support
this](https://github.com/Hoboneer/surfraw-elvis-generator/issues/27).

## Features (`mkelvis`)

* allows `*` characters in queries without spewing out contents of directories from globbing
* usable, automatically-generated `--local-help` and `-elvi` output
    - with control over some aspects of formatting
* readable output elvi with explanatory comments and templates
* elvi-specific tab-completions (**NOTE: uses WIP surfraw features from my merge request on the main surfraw repo**)
* easy-to-generate options, with *types* for different uses
* shortcuts to generate common surfraw options: `-result=NUM` and `-language=ISOCODE`
* declarative option syntax with access to the shell for some options
    - the topic variable (`$it`) is available for some options
    - map surfraw-option values to url parameters
    - "inline" surfraw-option values to search query keywords
    - mutate variables in shell case-statements

See the reference and advanced usage docs for more.

## Contributing

### Set up a development environment
```sh
python3 -m venv env
. env/bin/activate
pip install -r requirements/dev.txt
pip install -e .
```

Also ensure that you have GNU Make and (Universal) Ctags.  On Debian, Ubuntu, and their derivatives:
```sh
sudo apt install make universal-ctags
```

### Before submitting a pull request
```sh
make -k format check-dev
```

Make sure that no new errors were introduced after your changes.

## Copyright

This project is licensed under the Apache License 2.0 (sic) and follows the
[REUSE licencing guidelines](https://reuse.software).  Some auxiliary files
have a different licence.  Check their file headers or `.reuse/dep5` for
details.  Copies of the licences used in this project can be located in the
`LICENSES/` directory, per the REUSE guidelines.

Written by Gabriel Lisaca -- gabriel.lisaca (replace me with at) gmail dot com

