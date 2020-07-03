# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Main module for `mkelvis` command-line program."""

from __future__ import annotations

import argparse
import os
import sys
from functools import wraps
from itertools import chain
from os import EX_OK, EX_OSERR, EX_USAGE
from tempfile import NamedTemporaryFile
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

from .cliopts import (
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
from .common import (
    _VALID_FLAG_TYPES_STR,
    BASE_PARSER,
    VERSION_FORMAT_STRING,
    Context,
    _ElvisName,
    get_env,
    process_args,
)
from .options import (
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
    SurfrawVarOption,
)

if TYPE_CHECKING:
    from typing_extensions import Final

PROGRAM_NAME: Final = "mkelvis"


def _get_optheader(
    opt: SurfrawOption, prefix: str = "", force_no_metavar: bool = False
) -> str:
    """Return representation of `opt` in `-local-help`.

    These are in sorted order.

    Example:
      -s=SORT, -sort=SORT
    """
    if opt.metavar is None or force_no_metavar:
        suffix = ""
    else:
        suffix = f"={opt.metavar}"
    optheader = "  " + ", ".join(
        f"-{prefix}{opt_.name}{suffix}"
        for opt_ in sorted(chain([opt], opt.aliases), key=lambda x: x.name)
    )
    return optheader


def _get_optlines(
    opt: SurfrawOption, target: Optional[SurfrawOption] = None
) -> List[str]:
    """Return representation of `opt` in `-local-help`, with special-casing for list options."""
    if target is None:
        target = opt
    if isinstance(target, SurfrawList):
        optlines = []
        optlines.append(_get_optheader(opt, prefix="add-"))
        if not isinstance(opt, SurfrawFlag):
            optlines.append(
                _get_optheader(opt, prefix="clear-", force_no_metavar=True)
            )
        optlines.append(_get_optheader(opt, prefix="remove-"))
    else:
        optlines = [_get_optheader(opt)]
    return optlines


# FIXME: This is very ugly, please... make it not so bad.
def _generate_local_help_output(
    ctx: Context, namespacer: Callable[[str], str]
) -> str:
    """Return the 'Local options' part of `sr $elvi -local-help`."""
    # The local options part starts indented by two spaces.
    entries: List[Tuple[SurfrawOption, List[str]]] = []

    # Options that take arguments
    # Depends on subclass definition order.
    types_to_sort_order = {
        type_: i for i, type_ in enumerate(SurfrawVarOption.typenames.values())
    }
    for opt in sorted(
        ctx.variable_options, key=lambda x: types_to_sort_order[x.__class__]
    ):
        lines = _get_optlines(opt)

        # Add values of enum aligned with last metavar.
        if isinstance(opt, SurfrawEnum) or (
            isinstance(opt, SurfrawList) and issubclass(opt.type, SurfrawEnum)
        ):
            optheader = lines[-1]
            # +1 to go past the '='
            offset = optheader.rindex("=") + 1
            prefix = " " * offset
            lines.extend(f"{prefix}{value}" for value in opt.values)

        entries.append((opt, lines))

    # Aliases to one of the above options, but with an argument
    entries.extend(
        (flag, _get_optlines(flag, target=flag.target))
        for flag in ctx.options.flags
    )

    # Include "  | "
    longest_length = max(
        len(line)
        for line in chain.from_iterable(lines for _, lines in entries)
    )
    for opt, lines in entries:
        for i, line in enumerate(lines):
            # Ensure alignment.
            padding = " " * (longest_length - len(line))
            if i == 0:
                gap = "    "
                suffix = opt.description
            else:
                gap = "  | "
                suffix = ""
            lines[i] = f"{line}{padding}{gap}{suffix}"
        if isinstance(opt, SurfrawVarOption):
            prefix = " " * longest_length + "    "
            ns_name = namespacer(opt.name)
            lines.append(prefix + f"Default: ${ns_name}")
            # TODO: Allow a generic way for options to depend on other variables.
            if isinstance(opt, SurfrawSpecial):
                if opt.name == "results":
                    lines.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_results"
                    )
                elif opt.name == "language":
                    lines.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_lang"
                    )
            else:
                lines.append(prefix + f"Environment: {ns_name}")
    return "\n".join(chain.from_iterable(lines for _, lines in entries))


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


def _parse_elvis_name(name: str) -> _ElvisName:
    dirs, _ = os.path.split(name)
    if dirs:
        raise argparse.ArgumentTypeError("elvis names may not be paths")
    return _ElvisName(name)


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate an elvis for surfraw",
        parents=[BASE_PARSER],
    )
    parser.add_argument(
        "name", type=_parse_elvis_name, help="name for the elvis"
    )
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
    _search_args_group = parser.add_mutually_exclusive_group()
    _search_args_group.add_argument(
        "--query-parameter",
        "-Q",
        help="define the parameter for the query arguments; needed with --map",
    )
    _search_args_group.add_argument(
        "--no-append-args",
        action="store_false",
        dest="append_search_args",
        help="don't automatically append search to url",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="outfile",
        metavar="FILE",
        help="write elvis code to FILE instead of elvis name",
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
        "--no-completions",
        "--disable-completions",
        action="store_false",
        dest="enable_completions",
        help="don't include completion code in output elvis",
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


def main(argv: Optional[List[str]] = None) -> int:
    """Generate a single surfraw elvis.

    Exit codes correspond to the distro's `sysexits.h` file, which are the
    exit codes prefixed "EX_".
    """
    parser = _get_parser()
    ctx = Context(PROGRAM_NAME)
    try:
        parser.parse_args(argv, namespace=ctx)
    except Exception as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    exit_code = process_args(ctx)
    if exit_code != EX_OK:
        return exit_code

    # Generate the elvis.
    env, template_vars, namespacer = get_env(ctx)
    assert (
        VERSION_FORMAT_STRING is not None
    ), "VERSION_FORMAT_STRING should be defined"
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
    if template_vars["any_options_defined"]:
        template_vars["local_help_output"] = _generate_local_help_output(
            ctx, namespacer
        )

    # Atomically write output file.
    try:
        template = env.get_template("elvis.in")
        if ctx.outfile == "-":
            # Don't want to close stdout so don't wrap in with-statement.
            template.stream(template_vars).dump(sys.stdout)
        else:
            with NamedTemporaryFile(
                mode="w",
                delete=False,
                prefix=f"{ctx.name}.",
                suffix=f".{ctx.program_name}.tmp",
                dir=os.getcwd(),
            ) as f:
                template.stream(template_vars).dump(f)
                f.flush()
                fd = f.fileno()
                os.fsync(fd)
                os.fchmod(fd, 0o755)
                os.rename(f.name, ctx.outfile)
    except OSError as e:
        # Don't delete tempfile to allow for inspection on write errors.
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_OSERR
    return EX_OK
