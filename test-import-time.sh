#!/bin/sh

# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

# Print cumulative import time.
env PYTHONPROFILEIMPORTTIME=1 mkelvis -h 2>&1 >/dev/null |
	tail -n +2 |
	cut -d: -f2- |
	awk '{print $1}' |
	numsum
