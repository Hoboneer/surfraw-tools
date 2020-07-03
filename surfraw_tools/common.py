# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Common functions and classes to generate elvi.

Also includes a parser from `argparse` to base command-line programs on.
"""
from __future__ import annotations

import argparse
import os
import sys
from argparse import _VersionAction
from functools import partial
from itertools import chain
from os import EX_OK, EX_USAGE
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    NewType,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    ValuesView,
    cast,
)

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    ModuleLoader,
    contextfilter,
)
from jinja2.runtime import Context as JContext

from ._package import __version__
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
from .options import (
    SurfrawAlias,
    SurfrawAnything,
    SurfrawBool,
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
    SurfrawVarOption,
)
from .validation import OptionParseError, OptionResolutionError

if TYPE_CHECKING:
    from typing_extensions import Final

T = TypeVar("T", SurfrawFlag, SurfrawList)


# TODO: Name this better!
class _ChainContainer(Generic[T]):
    types: ClassVar[Sequence[Type[SurfrawOption]]] = []

    def __init__(self) -> None:
        self._items: Dict[str, List[T]] = {
            type_.typename_plural: [] for type_ in self.__class__.types
        }

    def append(self, item: T) -> None:
        try:
            self._items[item.type.typename_plural].append(item)
        except KeyError:
            raise TypeError(
                f"object '{item}' may not go into `{self.__class__.__name__}`s as it not a valid type"
            ) from None

    def __getitem__(self, type_: str) -> List[T]:
        return self._items[type_]

    def __repr__(self) -> str:
        pairs = (
            f"{typename}={elems}" for typename, elems in self._items.items()
        )
        return f"_ChainContainer({', '.join(pairs)})"

    def __iter__(self) -> Iterator[T]:
        return chain.from_iterable(self._items.values())

    # `__bool__` automatically defined.  True if non-zero length.
    def __len__(self) -> int:
        return sum(len(types_) for types_ in self._items.values())


class _FlagContainer(_ChainContainer[SurfrawFlag]):
    types = tuple(SurfrawVarOption.typenames.values())


class _ListContainer(_ChainContainer[SurfrawList]):
    types = [SurfrawEnum, SurfrawAnything]


class _SurfrawOptionContainer(argparse.Namespace):
    def __init__(self) -> None:
        self._seen_variable_names: Set[str] = set()
        self._seen_nonvariable_names: Set[str] = set()

        # Options that create variables.
        self.bools: List[SurfrawBool] = []
        self.enums: List[SurfrawEnum] = []
        self.anythings: List[SurfrawAnything] = []
        self.specials: List[SurfrawSpecial] = []
        self.lists = _ListContainer()
        self._varopts = {
            "bools": self.bools,
            "enums": self.enums,
            "anythings": self.anythings,
            "specials": self.specials,
            "lists": self.lists,
        }

        self.aliases: List[SurfrawAlias] = []
        self.flags = _FlagContainer()
        self._nonvaropts = {
            "aliases": self.aliases,
            "flags": self.flags,
        }

    def append(self, option: SurfrawOption) -> None:
        # Keep track of variable names.
        if isinstance(option, SurfrawVarOption):
            if option.name in self._seen_variable_names:
                raise ValueError(
                    f"the variable name '{option.name}' is duplicated"
                )
            self._seen_variable_names.add(option.name)
            self._varopts[option.typename_plural].append(option)  # type: ignore
        else:
            if option.name in self._seen_nonvariable_names:
                raise ValueError(
                    f"the non-variable-creating option name '{option.name}' is duplicated"
                )
            self._seen_nonvariable_names.add(option.name)
            self._nonvaropts[option.typename_plural].append(option)  # type: ignore

    @property
    def variable_options(self) -> Iterable[SurfrawVarOption]:
        return chain.from_iterable(
            cast(
                ValuesView[Iterable[SurfrawVarOption]], self._varopts.values()
            )
        )

    @property
    def nonvariable_options(self) -> Iterable[SurfrawOption]:
        return chain.from_iterable(
            cast(
                ValuesView[Iterable[SurfrawOption]], self._nonvaropts.values()
            )
        )


_ElvisName = NewType("_ElvisName", str)


class Context(argparse.Namespace):
    """Data holder for elvis currently being generated."""

    def __init__(self, program_name: str):
        self.program_name: Final = program_name

        self.name: _ElvisName = _ElvisName("DEFAULT")
        self.base_url: str = ""
        self.search_url: str = ""
        self.description: Optional[str] = None
        self.query_parameter: Optional[str] = None
        self.append_search_args: bool = True
        self.enable_completions: bool = True

        self.insecure: bool = False
        self.num_tabs: int = 1
        self.outfile: str = ""

        # Option containers
        self.options: _SurfrawOptionContainer = _SurfrawOptionContainer()
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

    @property
    def variable_options(self) -> Iterable[SurfrawVarOption]:
        """Return variable-creating options."""
        return self.options.variable_options


# Make sure that the resultant string is a grammatically-correct list.
_VALID_FLAG_TYPES_STR: Final = ", ".join(
    f"'{typename}'"
    if i != len(SurfrawVarOption.typenames) - 1
    else f"or '{typename}'"
    for i, typename in enumerate(SurfrawVarOption.typenames)
)


BASE_PARSER: Final = argparse.ArgumentParser(add_help=False)
_VERSION_FORMAT_ACTION: Final = cast(
    _VersionAction,
    BASE_PARSER.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (surfraw-tools) {__version__}",
    ),
)
VERSION_FORMAT_STRING: Final = _VERSION_FORMAT_ACTION.version


def _resolve_flags(
    ctx: Context, variable_options: Dict[str, SurfrawVarOption]
) -> None:
    # Set `target` of flags to an instance of `SurfrawOption`.
    for flag in ctx.unresolved_flags:
        try:
            target = variable_options[flag.target]
        except KeyError:
            raise OptionResolutionError(
                f"flag option '{flag.name}' does not target any existing {_VALID_FLAG_TYPES_STR} option"
            ) from None
        real_flag = flag.to_surfraw_opt(target)
        target.add_flag(real_flag)
        ctx.options.append(real_flag)
    ctx.unresolved_flags.clear()

    # Check if flag values are valid for their target type.
    try:
        for flag_target in variable_options.values():
            flag_target.resolve_flags()
    except OptionParseError as e:
        raise OptionResolutionError(str(e)) from None


def _resolve_aliases(
    ctx: Context, variable_options: Dict[str, SurfrawVarOption]
) -> None:
    # Set `target` of aliases to an instance of `SurfrawOption`.
    flag_names: Dict[str, SurfrawFlag] = {
        flag.name: flag for flag in ctx.options.flags
    }
    for alias in ctx.unresolved_aliases:
        # Check flags or aliases, depending on alias type.
        target: Optional[Union[SurfrawFlag, SurfrawVarOption]]
        if issubclass(alias.type, SurfrawFlag):
            target = flag_names.get(alias.target)
        else:
            target = variable_options.get(alias.target)
        if target is None or not isinstance(target, alias.type):
            raise OptionResolutionError(
                f"alias '{alias.name}' does not target any option of matching type ('{alias.type.typename}')"
            ) from None
        real_alias = alias.to_surfraw_opt(target)
        target.add_alias(real_alias)
        ctx.options.append(real_alias)
    ctx.unresolved_aliases.clear()


def _resolve_metavars_and_descs(
    ctx: Context, variable_options: Dict[str, SurfrawVarOption]
) -> None:
    # Metavars + descriptions
    for metavar in ctx.metavars:
        try:
            opt = variable_options[metavar.variable]
        except KeyError:
            raise OptionResolutionError(
                f"metavar for '{metavar.variable}' with the value '{metavar.metavar}' targets a non-existent variable"
            )
        else:
            opt.metavar = metavar.metavar
    for desc in ctx.descriptions:
        try:
            opt = variable_options[desc.variable]
        except KeyError:
            raise OptionResolutionError(
                f"description for '{desc.variable}' targets a non-existent variable"
            )
        else:
            opt.description = desc.description


_HasTarget = Union[MappingOption, InlineOption, CollapseOption]


def _resolve_var_targets(
    ctx: Context, variable_options: Dict[str, SurfrawVarOption]
) -> None:
    # Check if options target variables that exist.
    var_checks: List[Tuple[Iterable[_HasTarget], str]] = [
        (ctx.mappings, "URL parameter"),
        (ctx.list_mappings, "URL parameter"),
        (ctx.inlines, "inlining"),
        (ctx.list_inlines, "inlining"),
        (ctx.collapses, "collapse"),
    ]
    for opts, subject_name in var_checks:
        for opt in opts:
            if opt.target not in variable_options:
                raise OptionResolutionError(
                    f"{subject_name} '{opt.target}' does not target any existing variable"
                )


def resolve_options(ctx: Context) -> None:
    """Resolve parsed options.

    "Resolving" can mean different things depending on the option.

    For flags and aliases, it means to get a concrete option to set as its
    `target`.  After that, flags also check if their values are valid for their
    target.

    For metavars and describe options, it sets the respective metavar or
    description of its target.

    For mappings, inlines, and collapses (incl. list-ones), it checks if their
    targets exist.
    """
    # Resolve variable options.
    try:
        for unresolved_opt in ctx.unresolved_varopts:
            real_opt = unresolved_opt.to_surfraw_opt()
            # Register name with central container.
            ctx.options.append(real_opt)
    except Exception as e:
        raise OptionResolutionError(str(e)) from None
    ctx.unresolved_varopts.clear()

    # Symbol table.
    varopts = {opt.name: opt for opt in ctx.options.variable_options}

    _resolve_flags(ctx, varopts)
    _resolve_aliases(ctx, varopts)
    _resolve_metavars_and_descs(ctx, varopts)
    _resolve_var_targets(ctx, varopts)


def process_args(ctx: Context) -> int:
    """Do extra processing on parsed options."""
    if ctx.description is None:
        ctx.description = f"Search {ctx.name} ({ctx.base_url})"
    else:
        ctx.description += f" ({ctx.base_url})"

    if not ctx.outfile:
        ctx.outfile = ctx.name

    if ctx.insecure:
        # Is this the right term?
        url_scheme = "http"
    else:
        url_scheme = "https"

    ctx.base_url = f"{url_scheme}://{ctx.base_url}"
    ctx.search_url = f"{url_scheme}://{ctx.search_url}"

    if ctx.use_results_option:
        ctx.options.append(
            SurfrawSpecial("results", default="$SURFRAW_results")
        )
    if ctx.use_language_option:
        # If `SURFRAW_lang` is empty or unset, assume English.
        ctx.options.append(
            SurfrawSpecial("language", default="${SURFRAW_lang:=en}")
        )

    if ctx.num_tabs < 1:
        print(
            f"{ctx.program_name}: argument of `--num-tabs` must be at least '1'",
            file=sys.stderr,
        )
        return EX_USAGE

    try:
        resolve_options(ctx)
    except OptionResolutionError as e:
        print(f"{ctx.program_name}: {e}", file=sys.stderr)
        return EX_USAGE

    if (ctx.mappings or ctx.list_mappings) and ctx.query_parameter is None:
        print(
            f"{ctx.program_name}: mapping variables without a defined --query-parameter is forbidden",
            file=sys.stderr,
        )
        # TODO: Use proper exit code.
        return EX_USAGE

    return EX_OK


def _make_namespace(prefix: str) -> Callable[[str], str]:
    def prefixer(name: str) -> str:
        return f"{prefix}_{name}"

    return prefixer


@contextfilter
def _jinja_namespacer(ctx: JContext, basename: str) -> str:
    return f"SURFRAW_{ctx['name']}_{basename}"


def get_env(
    ctx: Context,
) -> Tuple[Environment, Dict[str, Any], Callable[[str], str]]:
    """Return relevant objects for template generation.

    That is, get a Jinja `Environment`, a dict of variables to base the code
    generator on, and a function to namespace variables (from Python code).
    The namespacer is needed because the template gets a `contextfilter` to do
    the same thing.

    The calling code should add entries to the `template_variables` dict and
    simply get a template and render it like so: `template.render(variables)`
    for simple uses.
    """
    # This package should not run from an archive--it's too slow to decompress every time.
    # Thus, `__file__` is guaranteed to be defined.
    package_dir = os.path.dirname(__file__)
    raw_templates_dir = os.path.join(package_dir, "templates")
    precompiled_templates_dir = os.path.join(raw_templates_dir, "compiled")
    env = Environment(
        loader=ChoiceLoader(
            [
                ModuleLoader(precompiled_templates_dir),
                # Don't use `PackageLoader` because it imports `pkg_resources` internally, which is a slow operation.
                FileSystemLoader(raw_templates_dir),
            ]
        ),
        # Only need to get a template once.
        cache_size=0,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Add functions to jinja template
    env.filters["namespace"] = _jinja_namespacer
    # Short-hand for `namespace`
    env.filters["ns"] = _jinja_namespacer

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
        "enable_completions": ctx.enable_completions,
        # Options to generate
        "flags": ctx.options.flags,
        "bools": ctx.options.bools,
        "enums": ctx.options.enums,
        "anythings": ctx.options.anythings,
        "aliases": ctx.options.aliases,
        "specials": ctx.options.specials,
        "lists": ctx.options.lists,
        # URL parameters
        "mappings": ctx.mappings,
        "list_mappings": ctx.list_mappings,
        "inlines": ctx.inlines,
        "list_inlines": ctx.list_inlines,
        "collapses": ctx.collapses,
        "query_parameter": ctx.query_parameter,
        "append_search_args": ctx.append_search_args,
    }

    return (env, template_variables, _make_namespace(f"SURFRAW_{ctx.name}"))
