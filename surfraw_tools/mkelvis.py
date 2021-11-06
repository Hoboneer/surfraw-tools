# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
# SPDX-FileCopyrightText: 2021 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Generate a surfraw elvis.

Exit codes are taken from the `sysexits.h` file.
"""

from __future__ import annotations

import argparse
from functools import wraps
from os import EX_OK, EX_OSERR, EX_USAGE
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)
from urllib.parse import urlparse, urlunparse

from surfraw_tools.lib.cliopts import (
    AliasOption,
    AnythingOption,
    BoolOption,
    CollapseOption,
    DescribeOption,
    EnumOption,
    FlagOption,
    InlineOption,
    ListOption,
    MappingOption,
    MetavarOption,
)
from surfraw_tools.lib.common import (
    _VALID_FLAG_TYPES_STR,
    BASE_PARSER,
    ExecContext,
    setup_cli,
)
from surfraw_tools.lib.elvis import Elvis
from surfraw_tools.lib.validation import OptionResolutionError

if TYPE_CHECKING:
    from typing_extensions import Final

PROGRAM_NAME: Final = "mkelvis"


F = TypeVar("F", bound=Callable[..., Any])


def _wrap_parser(func: F) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            ret = func(*args, **kwargs)
        except Exception as e:
            raise argparse.ArgumentTypeError(str(e)) from None
        return ret

    return cast(F, wrapper)


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[BASE_PARSER],
    )
    parser.add_argument(
        "name",
        help="name for the elvis",
    )
    parser.add_argument(
        "base_url",
        help="the url opened when no search terms are passed, and is shown in the description",
    )
    parser.add_argument(
        "search_url",
        help="the url to append arguments to, with the query parameters opened",
    )
    parser.add_argument(
        "--description",
        help="description for the elvis, excluding the domain name in parentheses",
    )

    parser.add_argument(
        "--query-parameter",
        "-Q",
        help="define the parameter for the query arguments (needed with --map)",
    )
    parser.add_argument(
        "--no-append-args",
        action="store_false",
        dest="append_search_args",
        help="don't automatically append search to url",
    )
    parser.add_argument(
        "--no-append-mappings",
        action="store_false",
        dest="append_mappings",
        help="don't automatically append --map and --list-map values to query string",
    )

    parser.add_argument(
        "--insecure", action="store_true", help="use 'http' instead of 'https'"
    )
    parser.add_argument(
        "--num-tabs",
        type=int,
        help="define the number of tabs after the elvis name in `sr -elvi` output for alignment",
    )

    parser.add_argument(
        "--metavar",
        action="append",
        type=_wrap_parser(MetavarOption.from_arg),
        dest="metavars",
        metavar="VARIABLE_NAME:METAVAR",
        help="define a metavar for an option; it will be UPPERCASE in the generated elvis",
    )
    parser.add_argument(
        "--describe",
        action="append",
        type=_wrap_parser(DescribeOption.from_arg),
        dest="descriptions",
        metavar="VARIABLE_NAME:DESCRIPTION",
        help="define a description for an option",
    )

    option_group = parser.add_argument_group("elvi option types")
    option_group.add_argument(
        "--flag",
        "-F",
        action="append",
        type=_wrap_parser(FlagOption.from_arg),
        dest="unresolved_flags",
        metavar="FLAG_NAME:FLAG_TARGET:VALUE",
        help=f"specify an alias to a value(s) of a defined {_VALID_FLAG_TYPES_STR} option",
    )
    option_group.add_argument(
        "--yes-no",
        "-Y",
        action="append",
        type=_wrap_parser(BoolOption.from_arg),
        dest="unresolved_varopts",
        metavar="VARIABLE_NAME:DEFAULT_YES_OR_NO",
        help="specify a boolean option for the elvis",
    )
    option_group.add_argument(
        "--enum",
        "-E",
        action="append",
        type=_wrap_parser(EnumOption.from_arg),
        dest="unresolved_varopts",
        metavar="VARIABLE_NAME:DEFAULT_VALUE:VAL1,VAL2,...",
        help="specify an option with an argument from a range of values",
    )
    option_group.add_argument(
        "--anything",
        "-A",
        action="append",
        dest="unresolved_varopts",
        type=_wrap_parser(AnythingOption.from_arg),
        metavar="VARIABLE_NAME:DEFAULT_VALUE",
        help="specify an option that is not checked",
    )
    option_group.add_argument(
        "--alias",
        action="append",
        type=_wrap_parser(AliasOption.from_arg),
        dest="unresolved_aliases",
        metavar="ALIAS_NAME:ALIAS_TARGET:ALIAS_TARGET_TYPE",
        help="make an alias to another defined option",
    )
    option_group.add_argument(
        "--list",
        action="append",
        type=_wrap_parser(ListOption.from_arg),
        dest="unresolved_varopts",
        metavar="LIST_NAME:LIST_TYPE:DEFAULT1,DEFAULT2,...[:VALID_VALUES_IF_ENUM]",
        help="create a list of enum or 'anything' values as a repeatable (cumulative) option (e.g., `-add-foos=bar,baz,qux`)",
    )
    option_group.add_argument(
        "--use-results-option",
        action="store_true",
        dest="use_results_option",
        help="define a '-results=NUM' option",
    )
    option_group.add_argument(
        "--use-language-option",
        action="store_true",
        dest="use_language_option",
        help="define a '-language=ISOCODE' option",
    )

    modify_vars_group = parser.add_argument_group(
        "variable manipulation options",
        description="map, inline, or modify elvi variables",
    )
    modify_vars_group.add_argument(
        "--map",
        action="append",
        type=_wrap_parser(MappingOption.from_arg),
        dest="mappings",
        metavar="VARIABLE_NAME:PARAMETER[:URL_ENCODE?]",
        help="map a variable to a URL parameter; by default, `URL_ENCODE` is 'yes'",
    )
    modify_vars_group.add_argument(
        "--list-map",
        action="append",
        # Same object, different target
        type=_wrap_parser(MappingOption.from_arg),
        dest="list_mappings",
        metavar="VARIABLE_NAME:PARAMETER[:URL_ENCODE?]",
        help="map the values of a list variable to multiple URL parameters; by default, `URL_ENCODE` is 'yes'",
    )
    modify_vars_group.add_argument(
        "--inline",
        action="append",
        type=_wrap_parser(InlineOption.from_arg),
        dest="inlines",
        metavar="VARIABLE_NAME:KEYWORD",
        help="map a variable to a keyword in the search query (e.g., `filetype:pdf` or `site:example.com`)",
    )
    modify_vars_group.add_argument(
        "--list-inline",
        action="append",
        type=_wrap_parser(InlineOption.from_arg),
        dest="list_inlines",
        metavar="VARIABLE_NAME:KEYWORD",
        help="map the values of a list variable to multiple keywords in the search query (e.g., `foo bar query filetype:pdf filetype:xml`)",
    )
    modify_vars_group.add_argument(
        "--collapse",
        action="append",
        type=_wrap_parser(CollapseOption.from_arg),
        dest="collapses",
        metavar="VARIABLE_NAME:VAL1,VAL2,RESULT:VAL_A,VAL_B,VAL_C,RESULT_D:...",
        help="change groups of values of a variable to a single value",
    )

    return parser


class _Context(ExecContext):
    """Data holder for elvis currently being generated."""

    def __init__(self) -> None:
        super().__init__()
        self.name: str = "DEFAULT"
        self.base_url: str = ""
        self.search_url: str = ""
        self.description: Optional[str] = None
        self.query_parameter: Optional[str] = None
        self.append_search_args: bool = True
        self.append_mappings: bool = True

        self.insecure: bool = False
        self.num_tabs: int = 1

        # Option containers
        self.unresolved_varopts: List[
            Union[BoolOption, EnumOption, AnythingOption, ListOption]
        ] = []
        self.unresolved_flags: List[FlagOption] = []
        self.unresolved_aliases: List[AliasOption] = []

        self.mappings: List[MappingOption] = []
        self.list_mappings: List[MappingOption] = []

        self.inlines: List[InlineOption] = []
        self.list_inlines: List[InlineOption] = []

        self.collapses: List[CollapseOption] = []

        self.metavars: List[MetavarOption] = []
        self.descriptions: List[DescribeOption] = []

        self.use_results_option: bool = False
        self.use_language_option: bool = False


def main(argv: Optional[List[str]] = None) -> int:  # noqa: D103
    # Docstring is copied from the module.
    ctx, log = setup_cli(PROGRAM_NAME, argv, _get_parser(), _Context())

    # Accept URLs *with* or *without* schemes, but the schemes must match.
    base_parts = urlparse(ctx.base_url)
    search_parts = urlparse(ctx.search_url)
    if base_parts.scheme != search_parts.scheme:
        log.critical("the schemes of both URLs must be the same")
        return EX_USAGE
    elif base_parts.scheme == "":
        scheme = "http" if ctx.insecure else "https"
        new_base = ctx.base_url
        new_search = ctx.search_url
    else:
        # Allow search URLs that end with "?"
        if search_parts.query == "" and ctx.search_url.endswith("?"):
            search_suffix = "?"
        else:
            search_suffix = ""
        scheme = base_parts.scheme
        # `urlunparse` is a bit dumb, so just strip the leading "//".
        new_base = urlunparse(("", *base_parts[1:])).lstrip("/")
        new_search = (
            urlunparse(("", *search_parts[1:])).lstrip("/") + search_suffix
        )

    # TODO: handle exceptions PROPERLY
    # TODO: handle `--num-tabs` error (with nice error message): EX_USAGE
    try:
        elvis = Elvis(
            ctx.name,
            new_base,
            new_search,
            scheme=scheme,
            description=ctx.description,
            query_parameter=ctx.query_parameter,
            append_search_args=ctx.append_search_args,
            append_mappings=ctx.append_mappings,
            enable_completions=ctx.enable_completions,
            num_tabs=ctx.num_tabs,
            generator=PROGRAM_NAME,
        )
    except Exception as e:
        log.critical(f"{e}")
        return EX_USAGE

    # Transfer relevant data to `Elvis` object.
    # TODO: create a nice API for this?
    elvis.mappings = ctx.mappings
    elvis.list_mappings = ctx.list_mappings
    elvis.inlines = ctx.inlines
    elvis.list_inlines = ctx.list_inlines
    elvis.collapses = ctx.collapses
    elvis.metavars = ctx.metavars
    elvis.descriptions = ctx.descriptions
    if ctx.use_results_option:
        elvis.add_results_option()
    if ctx.use_language_option:
        elvis.add_language_option()

    try:
        elvis.resolve_options(
            ctx.unresolved_varopts,
            ctx.unresolved_flags,
            ctx.unresolved_aliases,
        )
    except OptionResolutionError as e:
        log.critical(f"{e}")
        return EX_USAGE

    # Generate the elvis.
    template_vars = elvis.get_template_vars()

    # Atomically write output file.
    try:
        elvis.write(template_vars, ctx.outfile)
    except OSError as e:
        # Don't delete tempfile to allow for inspection on write errors.
        log.critical(f"{e}")
        return EX_OSERR
    return EX_OK


main.__doc__ = __doc__
