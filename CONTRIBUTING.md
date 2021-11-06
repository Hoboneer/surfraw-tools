<!--
SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Contributing

## Set up a development environment
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

## Before submitting a pull request
```sh
make -k format check-dev
```

Make sure that no new errors were introduced after your changes.

## While editing documentation
In a separate terminal window:
```sh
mkdocs serve
```

Open `http://127.0.0.1:8000/` in your browser to view your changes as you write
(it auto-reloads).

## Make a new release
1. Rename the `[Unreleased]` section in `CHANGELOG.md` to `[NEW_VERSION] - CURRENT_DATE_ISO`.
2. Create a new empty `[Unreleased]` section above the one renamed in step (1).
3. Change the version number in `surfraw_tools/_package.py` (`__version__`) to
   `NEW_VERSION`.
4. If the release is in a separate year from the previous one, change the copyright
   years in the licence headers for each file and in `.reuse/dep5`.
     - Only do this for the files that were changed since the last release (or
       new ones):
        - `git log PREV_VERSION.. FILE` (no entries means no changes); or
        - `haschanged.sh FILES` (shows number of commits with that file since).
            - For ease of use: `get-tracked-files.sh` gives you all git-tracked files
     - For `.md`, `.sh`, `.py`, `.toml`, `.yml`, `.cfg` files, you can run:
        - `reuse addheader --copyright="HOLDER <EMAIL>" --license=Apache-2.0 FILES`
     - For other files, update the header manually.
5. Run `make check-copyright` to see if some files don't have a licence
   header--go back to step (4) if some don't.
6. Run `mkdocs serve` and open `http://127.0.0.1:8000/` in your browser to
   check the docs for errors.
7. Commit these changes.
8. Run `make clean` to remove any build artifacts from previous builds.
9. Run `make dist`.  This has the `format`, `check-dev`, and `check-copyright`
   rules as prerequisites, and will fail if any of them do.
10. Check that the resulting sdist has all that you need.
11. Run `make upload`.
12. Add a tag with the new version number: `git tag NEW_VERSION`.
13. Push your changes: `git push --tags`.
14. Run `mkdocs gh-deploy` to deploy docs to Github Pages.

We don't build wheels because we pre-compile Jinja templates during
installation for faster runtime execution.  The build-time and runtime version
need to match.

