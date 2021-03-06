"""Provides a class that allows treating Surfraw elvi as objects."""
from __future__ import annotations

import argparse
import os
import sys
from itertools import chain
from tempfile import NamedTemporaryFile
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

if TYPE_CHECKING:
    from typing_extensions import Final

from functools import partial

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    ModuleLoader,
    contextfilter,
)
from jinja2.runtime import Context as JContext

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
    VERSION_FORMAT_STRING,
    _ElvisName,
    _SurfrawOptionContainer,
)
from surfraw_tools.lib.options import (
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
    SurfrawVarOption,
)
from surfraw_tools.lib.validation import OptionResolutionError

_HasTarget = Union[MappingOption, InlineOption, CollapseOption]


@contextfilter
def _jinja_namespacer(ctx: JContext, basename: str) -> str:
    return f"SURFRAW_{ctx['name']}_{basename}"


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


class Elvis(argparse.Namespace):
    """Object representation for a Surfraw elvis.

    It has two main functions:

    1. Resolving options: make sure that user-provided Surfraw options are
    consistent with each other.
    2. Writing elvi to disk.

    Options can be resolved by calling `resolve_options(...)`.

    To write the elvis to disk, call `get_template_vars(...)` to get a dict of
    Jinja2 template variables, make any modifications to the dict, and then
    pass it to `write(...)`.

    Both `base_url` and `search_url` are placed in the elvis source code within
    double quotes, so command substitutions and parameter expansions are
    available.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        search_url: str,
        *,
        generator: str,
        description: Optional[str] = None,
        query_parameter: Optional[str] = None,
        num_tabs: int = 1,
        scheme: str = "https",
        append_search_args: bool = True,
        append_mappings: bool = True,
        enable_completions: bool = True,
    ) -> None:
        self.generator: Final = generator
        # FIXME: remove when no longer a false positive.
        # Mypy flags this as an error.  This should be fixed in future versions.
        # See https://github.com/python/mypy/issues/3004
        self.name = name  # type: ignore
        self.base_url = base_url
        self.search_url = search_url
        self.description = description
        self.query_parameter = query_parameter
        self.append_search_args = append_search_args
        self.append_mappings = append_mappings
        self.enable_completions = enable_completions

        self.scheme = scheme
        self.num_tabs = num_tabs

        # Option containers
        self.options: _SurfrawOptionContainer = _SurfrawOptionContainer()

        self.mappings: List[MappingOption] = []
        self.list_mappings: List[MappingOption] = []

        self.inlines: List[InlineOption] = []
        self.list_inlines: List[InlineOption] = []

        self.collapses: List[CollapseOption] = []

        self.metavars: List[MetavarOption] = []
        self.descriptions: List[DescribeOption] = []

        self._have_results_option: bool = False
        self._have_language_option: bool = False

        self.env = self._init_get_env()

    def namespacer(self, name: str) -> str:
        """Return a namespaced variable name for the elvis."""
        return f"SURFRAW_{self.name}_{name}"

    @staticmethod
    def _init_get_env() -> Environment:
        # This package should not run from an archive--it's too slow to decompress every time.
        # Thus, `__file__` is guaranteed to be defined.
        package_dir = os.path.dirname(os.path.dirname(__file__))
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
            # Only one template to load.
            cache_size=1,
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

        return env

    def resolve_options(
        self,
        varopts: Iterable[
            Union[BoolOption, EnumOption, AnythingOption, ListOption]
        ],
        flags: Iterable[FlagOption],
        aliases: Iterable[AliasOption],
    ) -> None:
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
            for unresolved_opt in varopts:
                real_opt = unresolved_opt.to_surfraw_opt()
                # Register name with central container.
                self.options.append(real_opt)
        except Exception as e:
            raise OptionResolutionError(str(e)) from None

        # Symbol table.
        symtable = {opt.name: opt for opt in self.options.variable_options}

        self._resolve_flags(flags, symtable)
        self._resolve_aliases(aliases, symtable)
        self._resolve_metavars_and_descs(symtable)
        self._resolve_var_targets(symtable)

    def _resolve_flags(
        self,
        flags: Iterable[FlagOption],
        variable_options: Dict[str, SurfrawVarOption],
    ) -> None:
        for flag in flags:
            try:
                target = variable_options[flag.target]
            except KeyError:
                raise OptionResolutionError(
                    f"flag option '{flag.name}' does not target any existing {_VALID_FLAG_TYPES_STR} option"
                ) from None
            real_flag = flag.to_surfraw_opt(target)
            target.add_flag(real_flag)
            self.options.append(real_flag)

    def _resolve_aliases(
        self,
        aliases: Iterable[AliasOption],
        variable_options: Dict[str, SurfrawVarOption],
    ) -> None:
        # Set `target` of aliases to an instance of `SurfrawOption`.
        flag_names: Dict[str, SurfrawFlag] = {
            flag.name: flag for flag in self.options.flags
        }
        for alias in aliases:
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
            self.options.append(real_alias)

    def _resolve_metavars_and_descs(
        self, variable_options: Dict[str, SurfrawVarOption]
    ) -> None:
        # Metavars + descriptions
        for metavar in self.metavars:
            try:
                opt = variable_options[metavar.variable]
            except KeyError:
                raise OptionResolutionError(
                    f"metavar for '{metavar.variable}' with the value '{metavar.metavar}' targets a non-existent variable"
                )
            else:
                opt.metavar = metavar.metavar
        for desc in self.descriptions:
            try:
                opt = variable_options[desc.variable]
            except KeyError:
                raise OptionResolutionError(
                    f"description for '{desc.variable}' targets a non-existent variable"
                )
            else:
                opt.description = desc.description

    def _resolve_var_targets(
        self, variable_options: Dict[str, SurfrawVarOption]
    ) -> None:
        # Check if options target variables that exist.
        var_checks: List[Tuple[Iterable[_HasTarget], str]] = [
            (self.mappings, "URL parameter"),
            (self.list_mappings, "URL parameter"),
            (self.inlines, "inlining"),
            (self.list_inlines, "inlining"),
            (self.collapses, "collapse"),
        ]
        for opts, subject_name in var_checks:
            for opt in opts:
                if opt.target not in variable_options:
                    raise OptionResolutionError(
                        f"{subject_name} '{opt.target}' does not target any existing variable"
                    )

    @property
    def name(self) -> _ElvisName:
        """Name of elvis.

        It cannot contain "/" characters.
        """
        return self._name

    @name.setter
    def name(self, name: Union[str, _ElvisName]) -> None:
        dirs, _ = os.path.split(name)
        if dirs:
            raise ValueError("elvis names may not be paths")
        self._name = _ElvisName(name)

    @property
    def base_url(self) -> str:
        """URL when no search terms are entered.

        Getting the value includes the URL scheme, but setting it requires that
        the input URL has *no* scheme.
        """
        return f"{self.scheme}://{self._base_url}"

    @base_url.setter
    def base_url(self, url: str) -> None:
        self._base_url = url

    @property
    def search_url(self) -> str:
        """Return the URL which search terms are placed in.

        Getting the value includes the URL scheme, but setting it requires that
        the input URL has *no* scheme.
        """
        return f"{self.scheme}://{self._search_url}"

    @search_url.setter
    def search_url(self, url: str) -> None:
        self._search_url = url

    @property
    def num_tabs(self) -> int:
        """Return the number of tabs after elvis name.

        This is just for nicer output from `sr -elvi`.
        """
        return self._num_tabs

    @num_tabs.setter
    def num_tabs(self, val: int) -> None:
        if val < 1:
            raise ValueError("there must be at least one tab after elvis name")
        self._num_tabs = val

    def add_results_option(self) -> None:
        """Add a `--results=NUM` option to the elvis."""
        if self._have_results_option:
            # TODO: what error?
            raise NotImplementedError("cannot have two -results=NUM options")
        self.options.append(
            SurfrawSpecial(
                "results",
                default="$SURFRAW_results",
                metavar="NUM",
                description="Number of search results returned",
            )
        )
        self._have_results_option = True

    def add_language_option(self) -> None:
        """Add a `--results=ISOCODE` option to the elvis."""
        if self._have_results_option:
            # TODO: what error?
            raise NotImplementedError(
                "cannot have two -language=ISOCODE options"
            )
        # If `SURFRAW_lang` is empty or unset, assume English.
        self.options.append(
            SurfrawSpecial(
                "language",
                default="${SURFRAW_lang:=en}",
                metavar="ISOCODE",
                description="Two letter language code (resembles ISO country codes)",
            )
        )
        self._have_results_option = True

    def get_template_vars(self) -> Dict[str, Any]:
        """Get a dict of variables to be used in the Jinja2 template.

        This can be modified, if needed, before passing it to a call to
        `write(...)`.
        """
        assert (
            VERSION_FORMAT_STRING is not None
        ), "VERSION_FORMAT_STRING should be defined"
        any_options_defined = any(True for _ in self.options.variable_options)
        return {
            "GENERATOR_PROGRAM": VERSION_FORMAT_STRING
            % {"prog": self.generator},
            # Aliases and flags can only exist if any variable-creating options are defined.
            "any_options_defined": any_options_defined,
            "local_help_output": self._generate_local_help_output(
                self.namespacer
            )
            if any_options_defined
            else "",
            "name": self.name,
            "description": f"{self.description or f'Search {self.name}'} ({self._base_url})",
            "base_url": self.base_url,
            "search_url": self.search_url,
            "num_tabs": self.num_tabs,
            "enable_completions": self.enable_completions,
            # Options to generate
            "flags": self.options.flags,
            "bools": self.options.bools,
            "enums": self.options.enums,
            "anythings": self.options.anythings,
            "aliases": self.options.aliases,
            "specials": self.options.specials,
            "lists": self.options.lists,
            # URL parameters
            "mappings": self.mappings,
            "list_mappings": self.list_mappings,
            "inlines": self.inlines,
            "list_inlines": self.list_inlines,
            "collapses": self.collapses,
            "query_parameter": self.query_parameter,
            "append_search_args": self.append_search_args,
            "append_mappings": self.append_mappings,
        }

    # FIXME: This is very ugly, please... make it not so bad.
    def _generate_local_help_output(
        self, namespacer: Callable[[str], str]
    ) -> str:
        """Return the 'Local options' part of `sr $elvi -local-help`."""
        # The local options part starts indented by two spaces.
        entries: List[Tuple[SurfrawOption, List[str]]] = []

        # Options that take arguments
        # Depends on subclass definition order.
        types_to_sort_order = {
            type_: i
            for i, type_ in enumerate(SurfrawVarOption.typenames.values())
        }
        for opt in sorted(
            self.options.variable_options,
            key=lambda x: types_to_sort_order[x.__class__],
        ):
            lines = _get_optlines(opt)

            # Add values of enum aligned with last metavar.
            if isinstance(opt, SurfrawEnum) or (
                isinstance(opt, SurfrawList)
                and issubclass(opt.type, SurfrawEnum)
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
            for flag in self.options.flags
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

    # TODO: should `outfile` be `os.PathLike`?
    def write(
        self, template_vars: Mapping[str, Any], outfile: Optional[str] = None
    ) -> None:
        """Write the elvis to disk.

        `template_vars` should not have had any keys removed after being
        returned from `get_template_vars(...)`.  If `outfile` is `None`, the
        `name` attribute is used.

        `outfile` may be `"-"`, which causes the write to go to `sys.stdout`.
        Otherwise, it does an atomic write to the given file (using a temporary
        file).  If this atomic write fails, a file with the pattern
        `"ELVISNAME.RANDOMSTRING.GENERATORNAME.tmp"` should remain, available
        for inspection.
        """
        if outfile is None:
            outfile = self.name

        template = self.env.get_template("elvis.in")
        if outfile == "-":
            # Don't want to close stdout so don't wrap in with-statement.
            template.stream(template_vars).dump(sys.stdout)
        else:
            with NamedTemporaryFile(
                mode="w",
                delete=False,
                prefix=f"{self.name}.",
                suffix=f".{self.generator}.tmp",
                dir=os.getcwd(),
            ) as f:
                template.stream(template_vars).dump(f)
                f.flush()
                fd = f.fileno()
                os.fsync(fd)
                os.fchmod(fd, 0o755)
                os.rename(f.name, outfile)
