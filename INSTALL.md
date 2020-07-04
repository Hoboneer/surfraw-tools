<!--
SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# surfraw-tools

See `README.md` for usage information.

## Basic installation

You may use `pip` to install, but [pipx](https://github.com/pipxproject/pipx)
is recommended.  It is available in the distro repositories.

```sh
pipx install surfraw-tools
# or
pip install --user surfraw-tools
```

## Installing with a specific version of Jinja2

This package depends on Jinja2 to pre-compile templates for faster runtime
execution (see `pyproject.toml`).  These are specific to each version of
Jinja2, so the build-time version and runtime version need to match.

`pipx` places all dependencies in a virtual environment and should build with
the same version of Jinja2 as at runtime--which is the latest (`<3.0`).  Use
`pip` to use a specific version.

By default, `pip` builds packages in a separate environment.  If a specific
version of Jinja2 is desired, ensure that all the packages in the `requires`
key of `pyproject.toml` are installed.  Then:

```sh
pip install --no-build-isolation surfraw-tools
```

## Local installation

```sh
pip install .
# or
python setup.py install
```

Note that the second method doesn't build a wheel.  This means that--at least
on my machine--`pkg_resources` was imported by the script for the `mkelvis`
entry point so import time was increased by over 100 ms.
