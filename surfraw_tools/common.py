import argparse
import sys
from os import EX_USAGE

from ._package import __version__
from .options import (
    OptionResolutionError,
    resolve_aliases,
    resolve_collapses,
    resolve_flags,
    resolve_mappings,
)
from .parsers import (
    parse_alias_option,
    parse_anything_option,
    parse_bool_option,
    parse_collapse,
    parse_enum_option,
    parse_flag_option,
    parse_mapping_option,
    parse_query_parameter,
)

BASE_PARSER = argparse.ArgumentParser(add_help=False)
BASE_PARSER.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s (surfraw-tools) {__version__}",
)
BASE_PARSER.add_argument("name", help="name for the elvis")
BASE_PARSER.add_argument(
    "base_url",
    help="the url to show in the description and is the url opened when no search terms are passed, with no protocol",
)
BASE_PARSER.add_argument(
    "search_url",
    help="the url to append arguments to, with the query parameters opened and no protocol (automatically set to 'https')",
)
BASE_PARSER.add_argument(
    "--description",
    help="description for the elvis, excluding the domain name in parentheses",
)
BASE_PARSER.add_argument(
    "--insecure", action="store_true", help="use 'http' instead of 'https'"
)
# Option generation
BASE_PARSER.add_argument(
    "--flag",
    "-F",
    action="append",
    default=[],
    type=parse_flag_option,
    dest="flags",
    metavar="FLAG_NAME:FLAG_TARGET:YES_OR_NO",
    help="specify a flag for the elvis",
)
BASE_PARSER.add_argument(
    "--yes-no",
    "-Y",
    action="append",
    default=[],
    type=parse_bool_option,
    dest="bools",
    metavar="VARIABLE_NAME:DEFAULT_YES_OR_NO",
    help="specify a yes or no option for the elvis",
)
BASE_PARSER.add_argument(
    "--enum",
    "-E",
    action="append",
    default=[],
    type=parse_enum_option,
    dest="enums",
    metavar="VARIABLE_NAME:DEFAULT_VALUE:VAL1,VAL2,...",
    help="specify an option with an argument from a range of values",
)
BASE_PARSER.add_argument(
    "--anything",
    "-A",
    action="append",
    default=[],
    dest="anythings",
    type=parse_anything_option,
    metavar="VARIABLE_NAME:DEFAULT_VALUE",
    help="specify an option that is not checked",
)
BASE_PARSER.add_argument(
    "--alias",
    action="append",
    default=[],
    type=parse_alias_option,
    dest="aliases",
    metavar="ALIAS_NAME:ALIAS_TARGET",
    help="make an alias to another defined option",
)
BASE_PARSER.add_argument(
    "--map",
    "-M",
    action="append",
    default=[],
    type=parse_mapping_option,
    dest="mappings",
    metavar="VARIABLE_NAME:PARAMETER",
    help="map a variable to a URL parameter",
)
BASE_PARSER.add_argument(
    "--collapse",
    action="append",
    default=[],
    type=parse_collapse,
    dest="collapses",
    metavar="VARIABLE_NAME:VAL1,VAL2,RESULT:VAL_A,VAL_B,VAL_C,RESULT_D:...",
    help="change groups of values of a variable to a single value",
)
BASE_PARSER.add_argument(
    "--query-parameter",
    "-Q",
    type=parse_query_parameter,
    help="define the parameter for the query arguments; needed with --map",
)


def process_args(args):
    if args.description is None:
        args.description = f"Search {args.name} ({args.base_url})"
    else:
        args.description += f" ({args.base_url})"

    if args.insecure:
        # Is this the right term?
        url_scheme = "http"
    else:
        url_scheme = "https"

    args.base_url = f"{url_scheme}://{args.base_url}"
    args.search_url = f"{url_scheme}://{args.search_url}"

    try:
        resolve_aliases(args)
        resolve_flags(args)
        resolve_mappings(args)
        resolve_collapses(args)
    except OptionResolutionError as e:
        print(e, file=sys.stderr)
        return EX_USAGE

    if len(args.mappings) > 0 and args.query_parameter is None:
        print(
            "mapping variables without a defined --query-parameter is forbidden",
            file=sys.stderr,
        )
        # TODO: Use proper exit code.
        return EX_USAGE
