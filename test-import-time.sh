#!/bin/sh
# Print cumulative import time.
env PYTHONPROFILEIMPORTTIME=1 mkelvis -h 2>&1 >/dev/null |
	tail -n +2 |
	cut -d: -f2- |
	awk '{print $1}' |
	numsum
