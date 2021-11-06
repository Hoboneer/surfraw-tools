<!--
SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2021-11-07

### Added
- `opensearch2elvis`: a program to generate elvi for OpenSearch-enabled
  websites.
- Dependency on `lxml` because of `opensearch2elvis`.
- Repeatable `--verbose` and `--quiet` options for `mkelvis` and
  `opensearch2elvis`.
- `--no-append-mappings` option for `mkelvis`: take control of how the search
  URL gets its query string params.

### Changed
- URLs *with* or *without* a scheme are now allowed for `mkelvis`.  Both URLs
  must have the *same* scheme or both have *no* scheme.
- Some checks for "impossible" option combinations for `mkelvis` were removed.
  The defaults are safe and the advanced user should know what they're doing.
- Use `$it` instead of `$_` for implicit variables.  Bash and other shells do
  special things with `$_`, so this is the next best name.
- The repo now uses the name `surfraw-tools`:
  https://github.com/Hoboneer/surfraw-tools
- Documentation now available at https://hoboneer.github.io/surfraw-tools/

### Fixed
- Disabled globbing when working with "list" variables in generated elvi.  This
  caused directory contents to be exposed if a `*` character appeared in
  `-add-LIST=`.

## [0.1.0] - 2020-07-03

Initial release.

