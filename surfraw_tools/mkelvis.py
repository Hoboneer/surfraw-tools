# Copyright 2019 Gabriel Lisaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import re
import sys
from collections import namedtuple
from functools import wraps
from itertools import chain
from os import EX_OK, EX_OSERR, EX_SOFTWARE, EX_USAGE

from jinja2 import Environment, PackageLoader

from .options import (
    OptionResolutionError,
    resolve_aliases,
    resolve_flags,
    resolve_mappings,
)
from .parsers import (
    parse_alias_option,
    parse_anything_option,
    parse_bool_option,
    parse_enum_option,
    parse_flag_option,
    parse_mapping_option,
    parse_query_parameter,
)


def get_parser():
    parser = argparse.ArgumentParser(
        description="generate an elvis for surfraw"
    )
    parser.add_argument("name", help="name for the elvis")
    parser.add_argument(
        "base_url",
        help="the url to show in the description and is the url opened when no search terms are passed, with no protocol",
    )
    parser.add_argument(
        "search_url",
        help="the url to append arguments to, with the query parameters opened and no protocol (automatically set to 'https')",
    )
    parser.add_argument(
        "--description",
        help="description for the elvis, excluding the domain name in parentheses",
    )
    parser.add_argument(
        "--insecure", action="store_true", help="use 'http' instead of 'https'"
    )
    # Option generation
    parser.add_argument(
        "--flag",
        "-F",
        action="append",
        default=[],
        type=parse_flag_option,
        dest="flags",
        metavar="FLAG_NAME:FLAG_TARGET:YES_OR_NO",
        help="specify a flag for the elvis",
    )
    parser.add_argument(
        "--yes-no",
        "-Y",
        action="append",
        default=[],
        type=parse_bool_option,
        dest="bools",
        metavar="VARIABLE_NAME:DEFAULT_YES_OR_NO",
        help="specify a yes or no option for the elvis",
    )
    parser.add_argument(
        "--enum",
        "-E",
        action="append",
        default=[],
        type=parse_enum_option,
        dest="enums",
        metavar="VARIABLE_NAME:DEFAULT_VALUE:VAL1,VAL2,...",
        help="specify an option with an argument from a range of values",
    )
    parser.add_argument(
        "--anything",
        "-A",
        action="append",
        default=[],
        dest="anythings",
        type=parse_anything_option,
        metavar="VARIABLE_NAME:DEFAULT_VALUE",
        help="specify an option that is not checked",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        type=parse_alias_option,
        dest="aliases",
        metavar="ALIAS_NAME:ALIAS_TARGET",
        help="make an alias to another defined option",
    )
    parser.add_argument(
        "--map",
        "-M",
        action="append",
        default=[],
        type=parse_mapping_option,
        dest="mappings",
        metavar="VARIABLE_NAME:PARAMETER",
        help="map a variable to a URL parameter",
    )
    parser.add_argument(
        "--query-parameter",
        "-Q",
        type=parse_query_parameter,
        help="define the parameter for the query arguments; needed with --map",
    )
    return parser


# Taken from this stackoverflow answer:
#   https://stackoverflow.com/questions/12791997/how-do-you-do-a-simple-chmod-x-from-within-python/30463972#30463972
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


def make_namespace(prefix):
    def prefixer(name):
        return f"{prefix}_{name}"

    return prefixer


def generate_elvis(args):
    options = (args.flags, args.bools, args.enums, args.aliases)
    env = Environment(
        loader=PackageLoader("surfraw_tools"),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Add functions to jinja template
    env.globals["namespace"] = make_namespace(f"SURFRAW_{args.name}")
    env.globals["any_options_defined"] = lambda: any(
        len(option_container) for option_container in options
    )
    env.tests["flag_option"] = lambda x: isinstance(x, FlagOption)
    env.tests["bool_option"] = lambda x: isinstance(x, BoolOption)
    env.tests["enum_option"] = lambda x: isinstance(x, EnumOption)

    ELVIS_TEMPLATE = env.get_template("elvis.in")

    return ELVIS_TEMPLATE.render(
        name=args.name,
        description=args.description,
        base_url=args.base_url,
        search_url=args.search_url,
        options=options,
        # Options to generate
        flags=args.flags,
        bools=args.bools,
        enums=args.enums,
        anythings=args.anythings,
        aliases=args.aliases,
        # URL parameters
        mappings=args.mappings,
        query_parameter=args.query_parameter,
    )


def main(args=None):
    """Main program to generate surfraw elvi.

    Exit codes correspond to the distro's `sysexits.h` file, which are the
    exit codes prefixed "EX_".
    """
    if args is None:
        args = get_parser().parse_args()

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

    # Generate the elvis.
    elvis_program = generate_elvis(args)

    try:
        with open(args.name, "w") as f:
            f.write(elvis_program)
        make_executable(args.name)
    except OSError:
        # I'm not sure if this is the correct exit code, and if the two
        # actions above should be separated.
        return EX_OSERR
    return EX_OK
