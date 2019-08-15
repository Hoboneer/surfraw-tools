# surfraw-tools

These are command line tools to generate
[surfraw](https://www.techrepublic.com/blog/linux-and-open-source/surfing-the-world-wide-web-raw-style/)
scripts easily.

The following are currently provided:

* `mkelvis`: Generate a single surfraw elvis per invocation.

## How to use (simple)

Specify your elvis to generate with the three positional arguments as shown:

```sh
mkelvis ELVIS_NAME www.domain.com www.domain.com/search?q=
```

Notice that the final argument has an open query string for the `q` parameter.
This is intentional; it is where your search terms will be placed.

The created elvis will be placed in the current directory with the name
`ELVIS_NAME`, and ready for installation (made executable, shebang added).

## Adding options

To add options to an elvis, you need to use one of the following to generate
option parsing code.

* `--flag`: Boolean (yes-no) option with no arguments (e.g., `-lucky`).
* `--yes-no`: Boolean option whose argument must be: yes, on, 1; or no, off, 0.
* `--enum`: Option whose argument must be a member of a fixed list.
* `--alias`: Alias to any other option above. Displayed together in help
  output (TODO).
* `--map`: Map a variable in the generated elvis to a URL parameter.
* `--query-parameter`: Define the query parameter to be appended to the URL
  (needed if `--map` is used).

The yes-no, and enum options create variables corresponding to their name,
named as such: `SURFRAW_yourelviname_thevariable`.

## Making many elvi at once

`mkelvis` does not require any specific way of creating multiple elvi-- it only
does one a time. This enables multiple options.

For many simple elvi, a single text file may be sufficient. It shall be called
`elvi` here.

First, specify the elvi you want by putting the arguments to `mkelvis` for each
elvis to generate on separate lines. The name should have no whitespace.

Example `elvi` file:

```
reddit www.reddit.com www.reddit.com/search?q=
subreddit www.reddit.com www.reddit.com/subreddits/search?q= --description='Visit a subreddit'
```

These may then be generated by `make`, in whichever way is desired.
