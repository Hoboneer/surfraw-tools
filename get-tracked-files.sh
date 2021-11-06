#!/bin/sh

# SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

exec git ls-tree -r master --name-only
