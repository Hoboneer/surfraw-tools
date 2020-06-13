import argparse
import sys
from argparse import _VersionAction
from functools import partial, wraps
from itertools import chain
from os import EX_OK, EX_USAGE
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
)

from jinja2 import Environment, PackageLoader
from typing_extensions import Protocol

from ._package import __version__
from .options import (
    VALID_FLAG_TYPES_STR,
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
    Option,
    OptionResolutionError,
    SurfrawAnything,
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
    resolve_options,
)


class _HasType(Protocol):
    @property
    def type(self) -> Type[Any]:
        ...


T = TypeVar("T", bound=_HasType)


class _ChainContainer(argparse.Namespace, Generic[T]):
    # List of `SurfrawOption`-derived classes.
    types: List[Type[Any]] = []

    def __init__(self) -> None:
        self._items: Dict[Type[Any], List[T]] = {
            type_: [] for type_ in self.types
        }

    def __init_subclass__(cls, **kwargs) -> None:
        # Dynamically create getters.
        for type_ in cls.types:
            setattr(
                cls,
                type_.typename_plural,
                property(
                    # Account for late binding
                    partial(
                        lambda self_, saved_type: self_._items[  # type: ignore
                            saved_type
                        ].copy(),
                        saved_type=type_,
                    )
                ),
            )

    def append(self, item: T) -> None:
        try:
            self._items[item.type].append(item)
        except KeyError:
            raise TypeError(
                f"object '{item}' may not go into `{self.__class__.__name__}`s as it not a valid type"
            ) from None

    def __iter__(self):
        return chain.from_iterable(self._items.values())

    # `__bool__` automatically defined.  True if non-zero length.
    def __len__(self):
        return sum(len(types_) for types_ in self._items.values())


class _FlagContainer(_ChainContainer[SurfrawFlag]):
    types = SurfrawOption.variable_options


class _ListContainer(_ChainContainer[SurfrawList]):
    types = [SurfrawEnum, SurfrawAnything]


class _UnresolvedOptsContainer(_ChainContainer[Option]):
    types = list(Option.__subclasses__())


class _SurfrawOptionContainer(argparse.Namespace):
    def __init__(self) -> None:
        # Options that create variables.
        self.variable_options: List[SurfrawOption] = []
        self._seen_variable_names: Set[str] = set()
        self.nonvariable_options: List[SurfrawOption] = []
        self._seen_nonvariable_names: Set[str] = set()

        self.options: Dict[
            str, Union[_FlagContainer, _ListContainer, List[SurfrawOption]]
        ] = {
            type_.typename_plural: []
            for type_ in SurfrawOption.typenames.values()
        }
        # Flags and lists can be grouped by their target types.
        self.options[SurfrawFlag.typename_plural] = _FlagContainer()
        self.options[SurfrawList.typename_plural] = _ListContainer()

        # Dynamically create getters.
        for type_ in self.options.keys():
            setattr(
                self.__class__,
                type_,
                # Account for late binding
                property(
                    partial(
                        lambda self_, saved_type: self_.options[saved_type],  # type: ignore
                        saved_type=type_,
                    )
                ),
            )

    def append(self, option: SurfrawOption) -> None:
        try:
            bucket = self.options[option.typename_plural]
        except KeyError:
            raise TypeError(
                f"option '{option.name}' is not a surfraw option"
            ) from None
        bucket.append(option)  # type: ignore

        # Keep track of variable names.
        if option.creates_variable:
            if option.name in self._seen_variable_names:
                raise ValueError(
                    f"the variable name '{option.name}' is duplicated"
                )
            self._seen_variable_names.add(option.name)
            self.variable_options.append(option)
        else:
            if option.name in self._seen_nonvariable_names:
                raise ValueError(
                    f"the non-variable-creating option name '{option.name}' is duplicated"
                )
            self._seen_nonvariable_names.add(option.name)
            self.nonvariable_options.append(option)


class Context(argparse.Namespace):
    def __init__(self) -> None:
        self._surfraw_options = _SurfrawOptionContainer()
        self.unresolved = _UnresolvedOptsContainer()

    # I'd prefer properties but argparse's "append" action doesn't append in
    # the way I expected it to.  It requires the ability to assign values...
    def __getattr__(self, name):
        # Delegate to `_SurfrawOptionContainer`.
        try:
            ret = self._surfraw_options.options[name]
        except KeyError:
            raise AttributeError from None
        else:
            return ret

    @property
    def options(self):
        return self._surfraw_options

    # Again, needed for argparse's weirdness.
    @options.setter
    def options(self, val):
        self._surfraw_options = val

    @property
    def variable_options(self):
        return self.options.variable_options


F = TypeVar("F", bound=Callable[..., Any])


def _wrap_parser(func: F) -> F:
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
        except Exception as e:
            raise argparse.ArgumentTypeError(str(e)) from None
        return ret

    return cast(F, wrapper)


BASE_PARSER = argparse.ArgumentParser(add_help=False)
_VERSION_FORMAT_ACTION = cast(
    _VersionAction,
    BASE_PARSER.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (surfraw-tools) {__version__}",
    ),
)
VERSION_FORMAT_STRING = _VERSION_FORMAT_ACTION.version
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

# Include the 'or' for the last typename.
BASE_PARSER.add_argument(
    "--flag",
    "-F",
    action="append",
    type=_wrap_parser(FlagOption.from_arg),
    dest="unresolved",
    metavar="FLAG_NAME:FLAG_TARGET:VALUE",
    help=f"specify an alias to a value(s) of a defined {VALID_FLAG_TYPES_STR} option",
)
BASE_PARSER.add_argument(
    "--yes-no",
    "-Y",
    action="append",
    type=_wrap_parser(BoolOption.from_arg),
    dest="unresolved",
    metavar="VARIABLE_NAME:DEFAULT_YES_OR_NO",
    help="specify a boolean option for the elvis",
)
BASE_PARSER.add_argument(
    "--enum",
    "-E",
    action="append",
    type=_wrap_parser(EnumOption.from_arg),
    dest="unresolved",
    metavar="VARIABLE_NAME:DEFAULT_VALUE:VAL1,VAL2,...",
    help="specify an option with an argument from a range of values",
)
BASE_PARSER.add_argument(
    "--member",
    "-M",
    action="append",
    type=_wrap_parser(FlagOption.from_arg),
    dest="unresolved",
    metavar="OPTION_NAME:ENUM_VARIABLE_NAME:VALUE",
    help="specify an option that is an alias to a member of a defined --enum. DEPRECATED; now does the same thing as the more general --flag option",
)
BASE_PARSER.add_argument(
    "--anything",
    "-A",
    action="append",
    dest="unresolved",
    type=_wrap_parser(AnythingOption.from_arg),
    metavar="VARIABLE_NAME:DEFAULT_VALUE",
    help="specify an option that is not checked",
)
BASE_PARSER.add_argument(
    "--alias",
    action="append",
    type=_wrap_parser(AliasOption.from_arg),
    dest="unresolved",
    metavar="ALIAS_NAME:ALIAS_TARGET:ALIAS_TARGET_TYPE",
    help="make an alias to another defined option",
)
BASE_PARSER.add_argument(
    "--list",
    action="append",
    type=_wrap_parser(ListOption.from_arg),
    dest="unresolved",
    metavar="LIST_NAME:LIST_TYPE:DEFAULT1,DEFAULT2,...[:VALID_VALUES_IF_ENUM]",
    help="create a list of enum or 'anything' values as a repeatable (cumulative) option (e.g., `-add-foos=bar,baz,qux`)",
)
BASE_PARSER.add_argument(
    "--use-results-option",
    action="store_true",
    default=False,
    dest="use_results_option",
    help="define a 'results' variable and option",
)
BASE_PARSER.add_argument(
    "--use-language-option",
    action="store_true",
    default=False,
    dest="use_language_option",
    help="define a 'language' variable and option",
)
BASE_PARSER.add_argument(
    "--map",
    action="append",
    default=[],
    type=_wrap_parser(MappingOption.from_arg),
    dest="mappings",
    metavar="VARIABLE_NAME:PARAMETER[:URL_ENCODE?]",
    help="map a variable to a URL parameter; by default, `URL_ENCODE` is 'yes'",
)
BASE_PARSER.add_argument(
    "--list-map",
    action="append",
    default=[],
    # Same object, different target
    type=_wrap_parser(MappingOption.from_arg),
    dest="list_mappings",
    metavar="VARIABLE_NAME:PARAMETER[:URL_ENCODE?]",
    help="map the values of a list variable to multiple URL parameters; by default, `URL_ENCODE` is 'yes'",
)
BASE_PARSER.add_argument(
    "--inline",
    action="append",
    default=[],
    type=_wrap_parser(InlineOption.from_arg),
    dest="inlines",
    metavar="VARIABLE_NAME:KEYWORD",
    help="map a variable to a keyword in the search query (e.g., `filetype:pdf` or `site:example.com`)",
)
BASE_PARSER.add_argument(
    "--list-inline",
    action="append",
    default=[],
    type=_wrap_parser(InlineOption.from_arg),
    dest="list_inlines",
    metavar="VARIABLE_NAME:KEYWORD",
    help="map the values of a list variable to multiple keywords in the search query (e.g., `foo bar query filetype:pdf filetype:xml`)",
)
BASE_PARSER.add_argument(
    "--collapse",
    action="append",
    default=[],
    type=_wrap_parser(CollapseOption.from_arg),
    dest="collapses",
    metavar="VARIABLE_NAME:VAL1,VAL2,RESULT:VAL_A,VAL_B,VAL_C,RESULT_D:...",
    help="change groups of values of a variable to a single value",
)
BASE_PARSER.add_argument(
    "--metavar",
    action="append",
    default=[],
    type=_wrap_parser(MetavarOption.from_arg),
    dest="metavars",
    metavar="VARIABLE_NAME:METAVAR",
    help="define a metavar for an option; it will be UPPERCASE in the generated elvis",
)
BASE_PARSER.add_argument(
    "--describe",
    action="append",
    default=[],
    type=_wrap_parser(DescribeOption.from_arg),
    dest="descriptions",
    metavar="VARIABLE_NAME:DESCRIPTION",
    help="define a description for an option",
)
BASE_PARSER.add_argument(
    "--num-tabs",
    default=1,
    type=int,
    help="define the number of tabs after the elvis name in `sr -elvi` output for alignment",
)
_search_args_group = BASE_PARSER.add_mutually_exclusive_group()
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


def process_args(ctx):
    if ctx.description is None:
        ctx.description = f"Search {ctx.name} ({ctx.base_url})"
    else:
        ctx.description += f" ({ctx.base_url})"

    if ctx.insecure:
        # Is this the right term?
        url_scheme = "http"
    else:
        url_scheme = "https"

    ctx.base_url = f"{url_scheme}://{ctx.base_url}"
    ctx.search_url = f"{url_scheme}://{ctx.search_url}"

    if ctx.use_results_option:
        ctx.options.append(SurfrawSpecial("results"))
    if ctx.use_language_option:
        # If `SURFRAW_lang` is empty or unset, assume English.
        ctx.options.append(
            SurfrawSpecial("language", default="${SURFRAW_lang:=en}")
        )

    if ctx.num_tabs < 1:
        print(
            f"{ctx._program_name}: argument of `--num-tabs` must be at least '1'",
            file=sys.stderr,
        )
        return EX_USAGE

    try:
        resolve_options(ctx)
    except OptionResolutionError as e:
        print(f"{ctx._program_name}: {e}", file=sys.stderr)
        return EX_USAGE

    if (ctx.mappings or ctx.list_mappings) and ctx.query_parameter is None:
        print(
            f"{ctx._program_name}: mapping variables without a defined --query-parameter is forbidden",
            file=sys.stderr,
        )
        # TODO: Use proper exit code.
        return EX_USAGE

    return EX_OK


def _make_namespace(prefix):
    def prefixer(name):
        return f"{prefix}_{name}"

    return prefixer


def get_env(ctx):
    """Get a Jinja `Environment` and a dict of variables to base the code
    generator on.

    The calling code should add entries to the `template_variables` dict and
    simply render get a template and render it like so:
    `template.render(variables)` for simple uses.
    """
    env = Environment(
        loader=PackageLoader("surfraw_tools"),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Add functions to jinja template
    default_namespace = _make_namespace(f"SURFRAW_{ctx.name}")
    env.filters["namespace"] = default_namespace
    # Short-hand for `namespace`
    env.filters["ns"] = default_namespace
    ctx._namespacer = default_namespace

    for typename, opt_type in SurfrawOption.typenames.items():
        # Account for late-binding.
        env.tests[f"{typename}_option"] = partial(
            lambda x, type_: isinstance(x, type_), type_=opt_type
        )

    template_variables = {
        # Aliases and flags can only exist if any variable-creating options are defined.
        "any_options_defined": any(True for _ in ctx.variable_options),
        "name": ctx.name,
        "description": ctx.description,
        "base_url": ctx.base_url,
        "search_url": ctx.search_url,
        "num_tabs": ctx.num_tabs,
        # Options to generate
        "flags": ctx.flags,
        "bools": ctx.bools,
        "enums": ctx.enums,
        "anythings": ctx.anythings,
        "aliases": ctx.aliases,
        "specials": ctx.specials,
        "lists": ctx.lists,
        # URL parameters
        "mappings": ctx.mappings,
        "list_mappings": ctx.list_mappings,
        "inlines": ctx.inlines,
        "list_inlines": ctx.list_inlines,
        "collapses": ctx.collapses,
        "query_parameter": ctx.query_parameter,
        "append_search_args": ctx.append_search_args,
    }

    return (env, template_variables)
