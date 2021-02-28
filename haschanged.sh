#!/bin/sh
prevtag="$(git tag -l | grep '^[0-9]' | sort -r | head -n 1)" || { echo 'getting the previous tag failed' >&2; exit 1; }
for file in "$@"; do
	num_commits="$(git log --oneline "$prevtag".. "$file" | wc -l)"
	printf '%s:%d\n' "$file" "$num_commits"
done
