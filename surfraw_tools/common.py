import argparse
import sys
from abc import ABCMeta, abstractmethod
from functools import partial, wraps
from itertools import chain
from os import EX_OK, EX_USAGE

from jinja2 import Environment, PackageLoader

from ._package import __version__
from .options import (
    RESOLVERS,
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
    OptionResolutionError,
    SpecialOption,
    SurfrawOption,
)


class _ChainContainer(argparse.Namespace, metaclass=ABCMeta):
    types = []

    def __init__(self):
        self._items = {type_: [] for type_ in self.types}
        self._unresolved_items = []
        self._resolved = False
        # Dynamically create getters.
        for type_ in self.types:
            setattr(
                self.__class__,
                type_,
                # Account for late binding
                property(
                    partial(
                        lambda self_, saved_type: self_._items[
                            saved_type
                        ].copy(),
                        saved_type=type_,
                    )
                ),
            )

    # For use with argparse's "append" action.
    def append(self, item):
        self._unresolved_items.append(item)

    @abstractmethod
    def resolve(self):
        """Place items into their corresponding buckets.

        Remember to set `_resolved` to `True` afterward."""
        raise NotImplementedError

    def __iter__(self):
        if not self._resolved:
            return iter(self._unresolved_items)
        return chain.from_iterable(self._items.values())

    # `__bool__` automatically defined.  True if non-zero length.
    def __len__(self):
        return sum(len(types_) for types_ in self._items.values())


class _FlagContainer(_ChainContainer):
    types = ["bools", "enums", "anythings", "specials", "lists"]

    def resolve(self):
        # XXX: Should this just check for an instance of `FlagTarget`?
        #      How to determine which "bucket" to place into then?
        if not self._unresolved_items:
            return
        for flag in self._unresolved_items:
            if isinstance(flag.target, BoolOption):
                self._items["bools"].append(flag)
            elif isinstance(flag.target, EnumOption):
                self._items["enums"].append(flag)
            elif isinstance(flag.target, AnythingOption):
                self._items["anythings"].append(flag)
            elif isinstance(flag.target, SpecialOption):
                self._items["specials"].append(flag)
            elif isinstance(flag.target, ListOption):
                self._items["lists"].append(flag)
            else:
                raise RuntimeError(
                    "Invalid flag target type.  This should never be raised; the code is out of sync with itself."
                )
            flag.target.add_flag(flag)
        self._unresolved_items.clear()
        self._resolved = True


class _ListContainer(_ChainContainer):
    types = ["enums", "anythings"]

    def resolve(self):
        if not self._unresolved_items:
            return
        for list_ in self._unresolved_items:
            if issubclass(list_.type, EnumOption):
                self._items["enums"].append(list_)
            elif issubclass(list_.type, AnythingOption):
                self._items["anythings"].append(list_)
            else:
                raise RuntimeError(
                    "Invalid list target type.  This should never be raised; the code is out of sync with itself."
                )
        self._unresolved_items.clear()
        self._resolved = True


class _SurfrawOptionContainer(argparse.Namespace):
    def __init__(self):
        # Options that create variables (corresponds to `creates_variable`)
        # attribute on `SurfrawOption`).
        self.variable_options = []
        self._seen_variable_names = set()
        self.nonvariable_options = []
        self._seen_nonvariable_names = set()

        self.types_to_buckets = {
            FlagOption: "flags",
            BoolOption: "bools",
            EnumOption: "enums",
            AnythingOption: "anythings",
            AliasOption: "aliases",
            SpecialOption: "specials",
            ListOption: "lists",
        }
        self.options = {
            "flags": _FlagContainer(),
            "bools": [],
            "enums": [],
            "anythings": [],
            "aliases": [],
            "specials": [],
            "lists": _ListContainer(),
        }
        # Dynamically create getters.
        for type_ in self.options.keys():
            setattr(
                self.__class__,
                type_,
                # Account for late binding
                property(
                    partial(
                        lambda self_, saved_type: self_.options[saved_type],
                        saved_type=type_,
                    )
                ),
            )

    def append(self, option):
        if not isinstance(option, SurfrawOption):
            raise TypeError(f"option '{option.name}' is not a surfraw option")

        try:
            bucket = self.types_to_buckets[option.__class__]
        except KeyError:
            raise RuntimeError(
                f"could not route option '{option.name}' to a bucket; the code is out of sync with itself"
            )
        else:
            self.options[bucket].append(option)

        self._notify_append(option)

    def _notify_append(self, option):
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
    def __init__(self):
        self._surfraw_options = _SurfrawOptionContainer()

    # I'd prefer properties but argparse's "append" action doesn't append in
    # the way I expected it to.  It requires the ability to assign values...
    def __getattr__(self, name):
        # For backward compatibility.
        if name == "members":
            name = "flags"
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


def _wrap_parser(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
        except Exception as e:
            raise argparse.ArgumentTypeError(str(e)) from None
        return ret

    return wrapper


BASE_PARSER = argparse.ArgumentParser(add_help=False)
_VERSION_FORMAT_ACTION = BASE_PARSER.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s (surfraw-tools) {__version__}",
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
    default=argparse.SUPPRESS,
    type=_wrap_parser(FlagOption.from_arg),
    dest="options",
    metavar="FLAG_NAME:FLAG_TARGET:VALUE",
    help=f"specify an alias to a value(s) of a defined {VALID_FLAG_TYPES_STR} option",
)
BASE_PARSER.add_argument(
    "--yes-no",
    "-Y",
    action="append",
    default=argparse.SUPPRESS,
    type=_wrap_parser(BoolOption.from_arg),
    dest="options",
    metavar="VARIABLE_NAME:DEFAULT_YES_OR_NO",
    help="specify a boolean option for the elvis",
)
BASE_PARSER.add_argument(
    "--enum",
    "-E",
    action="append",
    default=argparse.SUPPRESS,
    type=_wrap_parser(EnumOption.from_arg),
    dest="options",
    metavar="VARIABLE_NAME:DEFAULT_VALUE:VAL1,VAL2,...",
    help="specify an option with an argument from a range of values",
)
BASE_PARSER.add_argument(
    "--member",
    "-M",
    action="append",
    default=argparse.SUPPRESS,
    type=_wrap_parser(FlagOption.from_arg),
    dest="options",
    metavar="OPTION_NAME:ENUM_VARIABLE_NAME:VALUE",
    help="specify an option that is an alias to a member of a defined --enum. DEPRECATED; now does the same thing as the more general --flag option",
)
BASE_PARSER.add_argument(
    "--anything",
    "-A",
    action="append",
    default=argparse.SUPPRESS,
    dest="options",
    type=_wrap_parser(AnythingOption.from_arg),
    metavar="VARIABLE_NAME:DEFAULT_VALUE",
    help="specify an option that is not checked",
)
BASE_PARSER.add_argument(
    "--alias",
    action="append",
    default=argparse.SUPPRESS,
    type=_wrap_parser(AliasOption.from_arg),
    dest="options",
    metavar="ALIAS_NAME:ALIAS_TARGET:ALIAS_TARGET_TYPE",
    help="make an alias to another defined option",
)
BASE_PARSER.add_argument(
    "--list",
    action="append",
    type=_wrap_parser(ListOption.from_arg),
    dest="options",
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
    "--query-parameter",
    "-Q",
    help="define the parameter for the query arguments; needed with --map",
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
        ctx.options.append(SpecialOption("results"))
    if ctx.use_language_option:
        # If `SURFRAW_lang` is empty or unset, assume English.
        ctx.options.append(
            SpecialOption("language", default="${SURFRAW_lang:=en}")
        )

    try:
        for resolver in RESOLVERS:
            resolver(ctx)
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

    env.tests["flag_option"] = lambda x: isinstance(x, FlagOption)
    env.tests["bool_option"] = lambda x: isinstance(x, BoolOption)
    env.tests["enum_option"] = lambda x: isinstance(x, EnumOption)
    env.tests["anything_option"] = lambda x: isinstance(x, AnythingOption)
    env.tests["special_option"] = lambda x: isinstance(x, SpecialOption)
    env.tests["alias_option"] = lambda x: isinstance(x, AliasOption)
    env.tests["list_option"] = lambda x: isinstance(x, ListOption)

    template_variables = {
        # Aliases and flags can only exist if any variable-creating options are defined.
        "any_options_defined": any(True for _ in ctx.variable_options),
        "name": ctx.name,
        "description": ctx.description,
        "base_url": ctx.base_url,
        "search_url": ctx.search_url,
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
    }

    return (env, template_variables)
