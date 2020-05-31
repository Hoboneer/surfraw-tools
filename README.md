# surfraw-tools

These are command line tools to generate
[surfraw](https://www.techrepublic.com/blog/linux-and-open-source/surfing-the-world-wide-web-raw-style/)
scripts easily.

The following are currently provided:

* `mkelvis`: Generate a single surfraw elvis per invocation.  Code for
  completions is also generated inside the output elvis.

## Quickstart

Specify your elvis to generate with the three positional arguments as shown:

```sh
	$ mkelvis yourelvisname www.domain.com www.domain.com/search?q=
```

Notice that the final argument has an open query string for the `q` parameter.
This is intentional; it is where your search terms will be placed.

The created elvis will be placed in the current directory with the name
`yourelvisname`, and ready for installation (made executable, shebang added).

## Adding options

To add options to an elvis, you need to use one of the following to generate
option parsing code.

* `--yes-no`: Boolean option whose argument must be one of: yes, on, 1; or no,
  off, 0.
* `--enum`: Option whose argument must be a member of a fixed list.
* `--anything`: Option whose argument is not checked.
* `--flag`: Alias to any variable-creating options (e.g., `-lucky` being an
  alias to `-lucky=yes`).
* `--alias`: Alias to any other option above. Displayed together in help
  output.
* `--use-results-option`: Create a `-results=NUM` option whose default value is
  taken from `$SURFRAW_results` (type: 'special').
* `--collapse`: Perform modification of a variable in a shell case-statement.
* `--map`: Map a variable in the generated elvis to a URL parameter.
* `--query-parameter`: Define the query parameter to be appended to the URL
  (needed if `--map` is used).

The yes-no, enum, anything, and special options create variables corresponding
to their name, named as such: `SURFRAW_yourelviname_thevariable`.

## Aliases

Aliases to flags or any variable-creating option can be made with the `--alias`
option.  Since flags and variable-creating options can have conflicting names
(but not between each other), this option needs the type of option it targets
to be specified.  Valid types follow:

* yes-no
* enum
* anything
* flag
* special

Another type is 'alias', but is forbidden to have aliases target other aliases.

## Making many elvi at once

`mkelvis` only generates one elvis per invocation, deferring the method to
create multiple elvi to the user.  An example follows.

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

See [my elvi repo](https://github.com/Hoboneer/surfraw-elvis) for more examples.
