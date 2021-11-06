<!--
SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Advanced usage

## Elvi with search options

`mkelvis` allows you to create elvi with options like `-sort=` and
`-results=NUM` seen in many existing elvi.

We'll create an elvis for Reddit--starting simple and building up
functionality.  The end-result is based on [commit
`a8ec5a7833e44df9cc3d9f56dc6cf7aa69d13e8c` from my elvi
repo](https://github.com/Hoboneer/surfraw-elvis/blob/a8ec5a7833e44df9cc3d9f56dc6cf7aa69d13e8c/src/reddit.in).

Name your file `reddit.in` and create a `Makefile` with these contents:

```mk
reddit: reddit.in
	grep -v '^[[:space:]]*\#' < $< | xargs mkelvis $@
```

Including the elvis name in the command means that we don't have to include
them in the file.  This makes expanding this to more elvi easier.  The `grep`
call also allows line comments with `#`.

### Bookmark-like elvis

```
www.reddit.com
www.reddit.com/search?q=
--description='Search Reddit'
```

This doesn't give us much more than the bookmarks that surfraw allows: a line
of

```
reddit	https://www.reddit.com/search?q=%s
```

in your bookmarks file would be enough to reimplement this.

The `--description=` isn't strictly needed since it defaults to `Search
$elvisname`.

### Sorting and date-restricting

```
www.reddit.com
www.reddit.com/search?
--description='Search Reddit'

--enum=sort:relevance:relevance,hot,top,new,comments
--map=sort:sort

--enum=time:all-time:hour,day,week,year,all-time
--collapse=time:all-time,all
--map=time:t

--query-parameter=q
```

This provides `-sort=` and `-time=` options to define how the search is sorted
and how far back you want your results to be.  Run `./reddit -lh` and you'll
see it nicely formatted for you with your options:

```
Usage: reddit [options] [search words]...
Description:
  Search Reddit (www.reddit.com)
Local options:
  -sort=SORT         An enum option for 'sort'
        relevance  | 
        hot        | 
        top        | 
        new        | 
        comments   | 
                     Default: relevance
                     Environment: SURFRAW_reddit_sort
  -time=TIME         An enum option for 'time'
        hour       | 
        day        | 
        week       | 
        year       | 
        all-time   | 
                     Default: all-time
                     Environment: SURFRAW_reddit_time
```

We can override the descriptions and metavars of options with `--describe=` and
`--metavar=` respectively.  We'll do that later.

#### `-sort=`

**`--enum=sort:relevance:relevance,hot,top,new,comments`**: this defines the
`-sort=` option, says the default value is `relevance`, and then defines all of
the valid values: `relevance`, `hot`, `top`, `new`, and `comments`.  The
default (`relevance`) must be included in that list of valid values.  `mkelvis`
will exit with an error otherwise.

**`--map=sort:sort`**: this says that it's mapping the `sort` variable (defined
above, but order doesn't matter) to the `sort` URL query string parameter.  In
the URL, it will appear like `sort=$SURFRAW_reddit_sort`.

#### `-time=`

**`--enum=time:all-time:hour,day,week,year,all-time`**: this defines the
date-restricting option you can see on Reddit.  Like with `sort`, we can see
that it defaults to `all-time`--out of `hour`, `day`, `week`, `year`,
`all-time`.

**`--map=time:t`**: it's mapped to the `t` parameter.

**`--collapse=time:all-time,all`**: this says that if the `time` variable has
the exact value of `all-time`, it should be replaced with `all`.  This allows
us to define a nicer interface for our elvis--not being bound to what the
search engine's parameter values actually are.

In fact, each colon-delimited (`:`) argument *after* the first one can be
comma-delimited (`,`) lists of patterns describing these changes.  See [the
reference](reference.md) for more.

Now, a problem with our previous version is that it would be hard for `mkelvis`
to decide what order to append the mappings and the search terms in.  The
`--query-parameter/-Q` option solves this for us.  The `q=` suffix can now be
removed from the search URL because this will be appended to it later.

### Keyword search

```
www.reddit.com
www.reddit.com/search?
--description='Search Reddit'

--enum=sort:relevance:relevance,hot,top,new,comments
--map=sort:sort

--enum=time:all-time:hour,day,week,year,all-time
--collapse=time:all-time,all
--map=time:t

--yes-no=nsfw:no
--inline=nsfw:nsfw
--describe=nsfw:'Whether to include NSFW posts'

--anything=flair:
--inline=flair:flair

--enum=self:any:any,only,none
--collapse=self:any,:only,yes:none,no
--inline=self:self
--describe=self:'Whether to include text posts'

--query-parameter=q
```

This gives us an elvis that unifies the syntax of searches with URL query
parameters and searches with keywords such as `site:github.com` to limit
results to `github.com`.

#### `-nsfw=`

**`--yes-no=nsfw:no`**: this defines a *boolean* option, corresponding to the
values that have the surfraw functions `ok`, `yesno`, `ifyes`, and `ifno`,
called on it.  It's called `nsfw`, and has a default value of `no`.  In the
elvis, you'd be able to use `-nsfw=yes`, `-nsfw=no`, `-nsfw=on`, `-nsfw=off`,
`-nsfw=1`, `-nsfw=0`.  They're treated the same.

**`--inline=nsfw:nsfw`**: this places the value of `nsfw` *inside* the search
terms in the form `nsfw:$SURFRAW_reddit_nsfw`.  This is common search syntax.

**`--describe=nsfw:'Whether to include NSFW posts'`**: this overrides the
description for the `-nsfw=` option.  Run `./reddit -lh` to see it.

#### `-flair=`

**`--anything=flair:`**: this defines an option that has a value that the elvis
doesn't check.  This is a useful catch-all option type that works very well for
this elvis because Reddit flairs can *really be anything*.

**`--inline=flair:flair`**: like `-nsfw=`, this inlines the value of `flair`
into the search terms.  If `flair` has an empty value, it doesn't get inlined.

#### `-self=`

**`--collapse=self:any,:only,yes:none,no`**: expanding on what was said
[above](#sorting-and-date-restricting), `--collapse=` can have an unlimited
number of comma-delimited arguments after the first argument (which defines the
variable it applies to).

**`--inline=self:self`**: like the others, this is also inlined.

**`--describe=self:'Whether to include text posts'`**: this overrides the
description for the `-self=` option.  Run `./reddit -lh` to see it.

### Subreddit search

```
www.reddit.com/r/${SURFRAW_reddit_subreddit:-all}
www.reddit.com/r/${SURFRAW_reddit_subreddit:-all}/search?restrict_sr=1&
--description='Search posts in a subreddit'

--anything=subreddit:all
--alias=search:subreddit:anything
--describe=subreddit:'Set subreddit to search in; "all" is a global search'

--flag=global:subreddit:all

--enum=sort:relevance:relevance,hot,top,new,comments
--map=sort:sort

--enum=time:all-time:hour,day,week,year,all-time
--collapse=time:all-time,all
--map=time:t

--yes-no=nsfw:no
--inline=nsfw:nsfw
--describe=nsfw:'Whether to include NSFW posts'

--anything=flair:
--inline=flair:flair

--enum=self:any:any,only,none
--collapse=self:any,:only,yes:none,no
--inline=self:self
--describe=self:'Whether to include text posts'

--query-parameter=q
```

This expands our elvis from *only* searching globally to searching globally
*or* in one subreddit, defaulting to `all` (i.e., `r/all`)--using a
`-subreddit=` option.

#### `--alias=search:subreddit:anything`

This defines an alias, `-search=` (a common option for elvi), to the
`-subreddit=` option.  The `anything` as the third argument is needed because
aliases can target options like `-foo=` and `-foo`, which `mkelvis`
distinguishes--one takes a value, and the other is an alias to an option that
*does* take a value.  This `anything` argument is called a "typename".  See
[the reference](reference.md) for the details.  These value- and
non-value-taking versions can co-exist with the same names.

#### `--flag=global:subreddit:all`

This defines an alias to `-subreddit=all` for quick access to `r/all` (if it's
needed for some reason).  You could replace this with your favourite subreddit
and you won't have to type the `-subreddit=` prefix all the time.

#### `www.reddit.com/r/${SURFRAW_reddit_subreddit:-all}` (base url)

At this point, any variables defined by the elvis will have their final values
after validating and collapsing.  The base URL text is placed in the elvis
inside double quotes, so parameter expansions and command substitutions are
available.  It's placed like so (without escaping or validating--so be
careful!):

```sh
w3_browse_url "YOUR_BASE_URL"
```

Note that this parameter expansion is visible in the `surfraw -elvi` output.

*(For your elvi, please stick to POSIX shell since `surfraw` is a POSIX shell
program.  We want elvi to be usable everywhere.)*

#### `www.reddit.com/r/${SURFRAW_reddit_subreddit:-all}/search?restrict_sr=1&` (search url)

Like in the base URL, any variables will have their final values at this point
and the search URL text is available for interaction by the shell:

```sh
w3_browse_url "YOUR_SEARCH_URL"
```

By the time `w3_browse_url` is called, the search URL will have any mappings
and inlines, and the search terms placed within it.

Note that this search URL has an `&` at the end.  This is because every search
is restricted to the subreddit using the `restrict_sr` query parameter.
`mkelvis` doesn't care if there are already query parameters in the search
URL--it just places its own mappings after it.

### Swappable domain

```
# you can place these in quotes if you want
# it's only needed if the urls contain whitespace--since we use `xargs`
${SURFRAW_reddit_site}/r/${SURFRAW_reddit_subreddit:-all}
${SURFRAW_reddit_site}/r/${SURFRAW_reddit_subreddit:-all}/search?restrict_sr=1&
--description='Search posts in a subreddit'

--enum=site:reddit:reddit,oldreddit
--collapse=site:reddit,www.reddit.com:oldreddit,old.reddit.com

--anything=subreddit:all
--alias=search:subreddit:anything
--describe=subreddit:'Set subreddit to search in; "all" is a global search'

--flag=global:subreddit:all

--enum=sort:relevance:relevance,hot,top,new,comments
--map=sort:sort

--enum=time:all-time:hour,day,week,year,all-time
--collapse=time:all-time,all
--map=time:t

--yes-no=nsfw:no
--inline=nsfw:nsfw
--describe=nsfw:'Whether to include NSFW posts'

--anything=flair:
--inline=flair:flair

--enum=self:any:any,only,none
--collapse=self:any,:only,yes:none,no
--inline=self:self
--describe=self:'Whether to include text posts'

--num-tabs=2

--query-parameter=q
```

Finally, this allows us to switch between the default Reddit interface at
`www.reddit.com` and the classic interface at `old.reddit.com`--using a
`-site=` option.

Both URLs now replace their `www.reddit.com` prefix with a parameter expansion.

We also use `--num-tabs=2` to align the description of the elvis with that of
other elvi in `surfraw -elvi`.

Done!  You can play around with it and its options, and read the elvis code
(it has lots of nice comments).  Now run `./reddit -lh` and see the output of a
nice elvis:

```
Usage: reddit [options] [search words]...
Description:
  Search posts in a subreddit (${SURFRAW_reddit_site}/r/${SURFRAW_reddit_subreddit:-all})
Local options:
  -nsfw=NSFW                                 Whether to include NSFW posts
                                             Default: no
                                             Environment: SURFRAW_reddit_nsfw
  -site=SITE                                 An enum option for 'site'
        reddit                             | 
        oldreddit                          | 
                                             Default: reddit
                                             Environment: SURFRAW_reddit_site
  -sort=SORT                                 An enum option for 'sort'
        relevance                          | 
        hot                                | 
        top                                | 
        new                                | 
        comments                           | 
                                             Default: relevance
                                             Environment: SURFRAW_reddit_sort
  -time=TIME                                 An enum option for 'time'
        hour                               | 
        day                                | 
        week                               | 
        year                               | 
        all-time                           | 
                                             Default: all-time
                                             Environment: SURFRAW_reddit_time
  -self=SELF                                 Whether to include text posts
        any                                | 
        only                               | 
        none                               | 
                                             Default: any
                                             Environment: SURFRAW_reddit_self
  -search=SUBREDDIT, -subreddit=SUBREDDIT    Set subreddit to search in; "all" is a global search
                                             Default: all
                                             Environment: SURFRAW_reddit_subreddit
  -flair=FLAIR                               An unchecked option for 'flair'
                                             Default: 
                                             Environment: SURFRAW_reddit_flair
  -global                                    An alias for -subreddit=all
```

See [the reference](reference.md) for the details on individual options to
`mkelvis`.

## Making many elvi at once

`mkelvis` only generates one elvis per invocation (KISS!), leaving the user
free to decide how they want to create many of them.  An example follows.

If there are lots of simple elvi, a single text file is enough.  It will be
called `elvi.in` here.

First, specify the elvi you want by putting the arguments to `mkelvis` for each
elvis on separate lines.  The name should have no whitespace.

Example `elvi.in` file:

```
reddit www.reddit.com www.reddit.com/search?q=
subreddit www.reddit.com www.reddit.com/subreddits/search?q= --description='Visit a subreddit'
```

A possible `Makefile`:

```mk
.PHONY: all elvi
all: elvi
elvi: elvi.in
	xargs -L 1 mkelvis < $<
```

Note that after running `make`, the current directory will be filled with elvi.
You could modify this so that each elvis has a suffix like `.elvis` to manage
them easier.

See [my elvi repo](https://github.com/Hoboneer/surfraw-elvis) for more examples.
