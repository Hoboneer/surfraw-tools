# mkelvis

This is a command line tool to generate
[surfraw](https://www.techrepublic.com/blog/linux-and-open-source/surfing-the-world-wide-web-raw-style/)
scripts easily.

## How to use

Specify your elvis to generate with the three positional arguments as shown:

```sh
./mkelvis ELVIS_NAME www.domain.com www.domain.com/search?q=
```

Notice that the final argument has an open query string for the `q` parameter.
This is intentional; it is where your search terms will be placed.

## Making many elvi at once

First, specify the elvi you want by putting the arguments to `mkelvis` for
each elvis to generate on separate lines. The name should have no whitespace.

Example `elvi` file:

```
reddit www.reddit.com www.reddit.com/search?q=
subreddit www.reddit.com www.reddit.com/subreddits/search?q= --description='Visit a subreddit'
```

Run:

- `make` to generate the elvi
- `make install` to install it to the specified location (`ELVI_DIR` variable)
- `make uninstall` to remove it from the specified location (`ELVI_DIR`
  variable)

The Makefile makes sure that any elvi *already* present will not be replaced
(via the `--no-clobber` option for `cp`) when running `make install`.
