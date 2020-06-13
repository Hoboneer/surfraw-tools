from __future__ import annotations

import re
import weakref
from collections import deque
from dataclasses import dataclass, field
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    List,
    NoReturn,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import Protocol

from .validation import (
    OptionParseError,
    list_of,
    no_validation,
    parse_bool,
    validate_bool,
    validate_enum_value,
    validate_name,
)

if TYPE_CHECKING:
    from .common import Context


# Options with non alphabetic characters are impossible
_FORBIDDEN_OPTION_NAMES = {
    "browser",
    "elvi",
    "g",
    "graphical",
    "h",
    "help",
    "lh",
    "p",
    "print",
    "o",
    "new",
    "ns",
    "newscreen",
    "t",
    "text",
    "q",
    "quote",
    "version",
    # Just in case options with hyphens are allowed in the future:
    "bookmark-search-elvis",
    "custom-search",
    "escape-url-args",
    "local-help",
}


_FlagValidator = Callable[[Any], Any]


class SurfrawOption:
    creates_variable: ClassVar[bool]
    flag_value_validator: _FlagValidator

    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}
    typename: ClassVar[str]
    typename_plural: ClassVar[str]
    variable_options: ClassVar[List[Type[SurfrawOption]]] = []

    name: str
    metavar: Optional[str]
    description: str

    def __init__(self, name: str, *args: Any, **kwargs: Any):
        if name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{name}' is global, which cannot be overriden by elvi"
            )
        self.name: str = name
        if not hasattr(self, "metavar"):
            if self.__class__.creates_variable:
                self.metavar = self.name.upper()
            else:
                self.metavar = None
        if not hasattr(self, "description"):
            self.description = f"A {self.typename} option for '{self.name}'"
        # Aliases and flags.
        self.aliases: weakref.WeakSet[SurfrawOption] = weakref.WeakSet()
        # Flags should be listed in the order that they were defined in the command line.
        self.flags: List[SurfrawFlag] = []

    def __init_subclass__(cls, **kwargs) -> None:
        subclass_re = r"Surfraw([A-Z][a-z]+)"
        try:
            cls.typename = re.match(subclass_re, cls.__name__).group(1).lower()  # type: ignore
        except IndexError:
            raise RuntimeError(
                f"subclasses of SurfrawOption must match the regex '{subclass_re}'"
            ) from None
        # Can't reference `SurfrawAlias` here since it's not defined yet, but this will do.
        if cls.typename == "alias":
            cls.typename_plural = "aliases"
        else:
            cls.typename_plural = cls.typename + "s"

        SurfrawOption.typenames[cls.typename] = cls
        if cls.creates_variable:
            SurfrawOption.variable_options.append(cls)

    def add_alias(self, alias: SurfrawOption) -> None:
        self.aliases.add(alias)

    def add_flag(self, flag: SurfrawFlag) -> None:
        self.flags.append(flag)

    def resolve_flags(self) -> None:
        try:
            for flag in self.flags:
                flag.value = self.__class__.flag_value_validator(flag.value)
        except OptionParseError as e:
            raise OptionResolutionError(str(e)) from None


_FlagValidatorsType = List[Union[List[_FlagValidator], _FlagValidator]]
_O = TypeVar("_O", bound=Type["Option"])


class Option:
    """Option to a command-line program with validated colon-delimited arguments.

    Configure subclasses with these class attributes:

        validators: A list of validator or parser functions from `.validation`, corresponding to its arguments in the command line.
        last_arg_is_unlimited: Whether the last arg may be repeated.  (default: `False`)
    """

    validators: _FlagValidatorsType = []
    last_arg_is_unlimited = False

    typename: ClassVar[str]
    typename_plural: ClassVar[str]

    def __init_subclass__(cls, **kwargs) -> None:
        subclass_re = r"([A-Z][a-z]+)Option"
        try:
            cls.typename = re.match(subclass_re, cls.__name__).group(1).lower()  # type: ignore
        except IndexError:
            raise RuntimeError(
                f"subclasses of Option must match the regex '{subclass_re}'"
            ) from None
        # Can't reference `AliasOption` here since it's not defined yet, but this will do.
        if cls.typename == "alias":
            cls.typename_plural = "aliases"
        else:
            cls.typename_plural = cls.typename + "s"

    @property
    def type(self) -> Type[Option]:
        return self.__class__

    @classmethod
    def from_arg(cls: _O, arg: str) -> _O:
        parsed_args = cls.parse_args(
            arg,
            validators=cls.validators,
            last_is_unlimited=cls.last_arg_is_unlimited,
        )
        if cls.last_arg_is_unlimited:
            normal_args = parsed_args[: len(cls.validators) - 1]
            # `last_arg` is the list of validated args from the last validator.
            last_arg = parsed_args[len(cls.validators) - 1 :]
            # Too many arguments, according to mypy.  I know better!
            return cast(_O, cls(*normal_args, last_arg))  # type: ignore
        else:
            return cast(_O, cls(*parsed_args))

    @staticmethod
    def parse_args(
        raw_arg: str,
        validators: _FlagValidatorsType,
        last_is_unlimited: bool = False,
    ) -> List[Any]:
        args = deque(raw_arg.split(":"))
        valid_args: List[Any] = []

        curr_validators = deque(validators)
        num_required = len(curr_validators)
        group_num = 0
        while curr_validators:
            new_group = False
            curr_validator = curr_validators.popleft()
            # Then we are in an optional group.
            if not callable(curr_validator):
                curr_validators = deque(curr_validator)
                num_required = len(curr_validators)
                try:
                    curr_validator = curr_validators.popleft()
                except IndexError:
                    raise ValueError(
                        "validator groups must not be empty"
                    ) from None
                if not callable(curr_validator):
                    raise TypeError(
                        "optional validator groups must start with at least one callable"
                    )
                group_num += 1
                new_group = True
            try:
                arg = args.popleft()
            except IndexError:
                if new_group:
                    # Not enough args but this is an optional group anyway.
                    break
                else:
                    raise OptionParseError(
                        f"current group {group_num} for '{raw_arg}' needs at least {num_required} colon-delimited parts"
                    )
            else:
                # Raise `OptionParseError` if invalid arg.
                valid_args.append(curr_validator(arg))
        # No more validators.

        # Continue until args exhausted.
        if last_is_unlimited:
            assert callable(curr_validator)
            # Raise `OptionParseError` if invalid arg.
            valid_args.extend(curr_validator(arg) for arg in args)
            # `args` is "empty" now.

        return valid_args


# Concrete option types follow


@dataclass(frozen=True)
class FlagOption(Option):
    validators = [validate_name, validate_name, no_validation]
    name: str
    target: str
    value: str

    def to_surfraw_opt(self, resolved_target: SurfrawOption) -> SurfrawFlag:
        return SurfrawFlag(self.name, resolved_target, self.value)


class SurfrawFlag(SurfrawOption):
    creates_variable = False

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError("flags cannot have flags")

    def __init__(self, name: str, target: SurfrawOption, value: Any):
        super().__init__(name)
        self.target = target
        self.value = value
        self.description = f"An alias for -{self.target.name}={self.value}"

    @property
    def type(self) -> Type[SurfrawOption]:
        return self.target.__class__


@dataclass(frozen=True)
class BoolOption(Option):
    validators = [validate_name, validate_bool]
    name: str
    default: str

    def to_surfraw_opt(self) -> SurfrawBool:
        return SurfrawBool(self.name, self.default)


class SurfrawBool(SurfrawOption):
    creates_variable = True
    flag_value_validator = validate_bool

    def __init__(self, name: str, default: str):
        super().__init__(name)
        self.default = default


@dataclass(frozen=True)
class EnumOption(Option):
    validators = [
        validate_name,
        validate_enum_value,
        list_of(validate_enum_value),
    ]
    name: str
    default: str
    values: List[str]

    def to_surfraw_opt(self) -> SurfrawEnum:
        return SurfrawEnum(self.name, self.default, self.values)


class SurfrawEnum(SurfrawOption):
    creates_variable = True
    flag_value_validator = validate_enum_value

    def __init__(self, name: str, default: str, values: List[str]):
        super().__init__(name)
        if default not in values:
            raise ValueError(
                f"enum default value '{default}' must be within '{values}'"
            )
        self.default = default
        self.values = values
        # "A enum" is incorrect.
        self.description = re.sub("^A ", "An ", self.description)

    def resolve_flags(self):
        for flag in self.flags:
            flag.value = self.__class__.flag_value_validator(flag.value)
            if flag.value not in self.values:
                raise OptionResolutionError(
                    f"enum flag option {flag.name}'s value ({flag.value}) is not contained in its target enum ({self.values})"
                )


@dataclass(frozen=True)
class AnythingOption(Option):
    validators = [validate_name, no_validation]
    name: str
    default: str

    def to_surfraw_opt(self) -> SurfrawAnything:
        return SurfrawAnything(self.name, self.default)


class SurfrawAnything(SurfrawOption):
    creates_variable = True
    flag_value_validator = no_validation

    def __init__(self, name: str, default: str):
        super().__init__(name)
        self.default = default
        self.description = f"An unchecked option for '{self.name}'"


# This class is not instantiated normally... maybe prepend name with underscore?
class SurfrawSpecial(SurfrawOption):
    creates_variable = True

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawSpecial` directly"
        )

    def __init__(self, name: str, default: Optional[str] = None):
        super().__init__(name)
        if default is None:
            self.default = "$SURFRAW_" + name
        else:
            self.default = default

        if self.name == "results":
            # Match the rest of the elvi's metavars for -results=
            self.metavar = "NUM"
            self.description = "Number of search results returned"
        elif self.name == "language":
            # Match the wikimedia elvi
            self.metavar = "ISOCODE"
            self.description = (
                "Two letter language code (resembles ISO country codes)"
            )
        else:
            raise ValueError(
                f"special options cannot have the name '{self.name}'"
            )
        # Use default metavar and description otherwise.

    def resolve_flags(self):
        for flag in self.flags:
            if flag.name == "results":
                try:
                    flag.value = int(flag.value)
                except ValueError:
                    raise OptionResolutionError(
                        "value for special 'results' option must be an integer"
                    ) from None
            # The language option needn't be checked here.  There are way too
            # many ISO language codes to match.


def parse_option_type(option_type):
    # For backward compatibility.
    if option_type == "member":
        option_type = "flag"
    try:
        type_ = SurfrawOption.typenames[option_type]
    except KeyError:
        valid_option_types = ", ".join(sorted(SurfrawOption.typenames))
        raise OptionParseError(
            f"option type '{option_type}' must be one of the following: {valid_option_types}"
        ) from None
    else:
        return type_


# Can't freeze this class, but it should be treated as immutable.
@dataclass
class ListOption(Option):
    validators = [
        validate_name,
        parse_option_type,
        list_of(no_validation),
        [list_of(no_validation)],
    ]

    name: str
    elem_type: Type[SurfrawOption]
    defaults: List[str]
    values: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # They are equivalent.
        if len(self.defaults) == 1 and self.defaults[0] == "":
            self.defaults = []
        if len(self.values) == 1 and self.values[0] == "":
            self.values = []

        if issubclass(self.elem_type, SurfrawEnum):
            if not self.values:
                raise OptionParseError(
                    "fourth argument to `--list` option must be provided for enum lists"
                )

            # Raise `OptionParseError` if invalid.
            self.values = [validate_enum_value(val) for val in self.values]

        elif issubclass(self.elem_type, SurfrawAnything):
            # Nothing to check for 'anythings'.
            pass

    def to_surfraw_opt(self) -> SurfrawList:
        return SurfrawList(
            self.name, self.elem_type, self.defaults, self.values
        )


# XXX: Should this store validators for the type it has?
class SurfrawList(SurfrawOption):
    creates_variable = True

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawList` directly"
        )

    def __init__(
        self,
        name: str,
        type: Type[SurfrawOption],
        defaults: List[str],
        values: List[str],
    ):
        super().__init__(name)
        self.type = type
        self.defaults = defaults
        self.values = values
        self.description = f"A repeatable (cumulative) '{self.type.typename}' list option for '{self.name}'"

        if not issubclass(self.type, (SurfrawEnum, SurfrawAnything)):
            raise TypeError(
                f"element type ('{self.type.__name__}') of list '{self.name}' is not a valid list type"
            )

        if issubclass(self.type, SurfrawEnum):
            if not set(self.defaults) <= set(self.values):
                raise ValueError(
                    f"enum list option {self.name}'s defaults ('{self.defaults}') must be a subset of its valid values ('{self.values}')"
                )

    def resolve_flags(self) -> None:
        for flag in self.flags:
            if issubclass(self.type, EnumOption):
                flag.value = list_of(validate_enum_value)(flag.value)
                if not set(flag.value) <= set(self.values):
                    raise OptionResolutionError(
                        f"enum list flag option {flag.name}'s value ('{flag.value}') must be a subset of its target's values ('{self.values}')"
                    )
            flag.description = f"An alias for the '{self.type.typename}' list option '{self.name}' with the values '{','.join(flag.value)}'"
            # Don't need to check `AnythingOption`.


@dataclass(frozen=True)
class AliasOption(Option):
    validators = [validate_name, validate_name, parse_option_type]
    name: str
    target: str
    ref_type: Type[SurfrawOption]

    def to_surfraw_opt(self, resolved_target: SurfrawOption) -> SurfrawAlias:
        # No longer need to store target type explicitly (it has a reference!).
        return SurfrawAlias(self.name, resolved_target)


class SurfrawAlias(SurfrawOption):
    creates_variable = False

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError("aliases cannot have flags")

    def __init__(self, name: str, target: SurfrawOption):
        super().__init__(name)
        if isinstance(target, self.__class__):
            raise TypeError("aliases cannot be aliases of other aliases")
        self.target = target


@dataclass(frozen=True)
class MappingOption(Option):
    validators = [validate_name, no_validation, [parse_bool]]
    target: str
    parameter: str
    should_url_encode: bool = True

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


@dataclass(frozen=True)
class InlineOption(Option):
    validators = [validate_name, validate_name]
    target: str
    keyword: str

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


@dataclass(frozen=True)
class CollapseOption(Option):
    validators = [validate_name, list_of(no_validation)]
    last_arg_is_unlimited = True

    target: str
    collapses: List[str]

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


_VALID_METAVAR_STR = "^[a-z]+$"
_VALID_METAVAR = re.compile(_VALID_METAVAR_STR)


def _validate_metavar(metavar: str) -> str:
    if not _VALID_METAVAR.fullmatch(metavar):
        raise OptionParseError(
            f"metavar '{metavar}' must match the regex '{_VALID_METAVAR_STR}'"
        )
    return metavar


# Treat this as immutable!
@dataclass
class MetavarOption(Option):
    validators = [validate_name, _validate_metavar]
    variable: str
    metavar: str

    def __post_init__(self):
        self.metavar = self.metavar.upper()


@dataclass(frozen=True)
class DescribeOption(Option):
    validators = [validate_name, no_validation]
    variable: str
    description: str


class OptionResolutionError(Exception):
    pass


VALID_FLAG_TYPES = [opt.typename for opt in SurfrawOption.variable_options]
VALID_FLAG_TYPES_STR = ", ".join(
    f"'{typename}'" if typename != VALID_FLAG_TYPES[-1] else f"or '{typename}'"
    for i, typename in enumerate(VALID_FLAG_TYPES)
)


def _cleanup_flag_alias_resolve(
    ctx: Context,
    flag_or_alias: Union[FlagOption, AliasOption],
    target: SurfrawOption,
) -> None:
    real_opt = flag_or_alias.to_surfraw_opt(target)
    if isinstance(real_opt, SurfrawFlag):
        target.add_flag(real_opt)
    else:
        target.add_alias(real_opt)
    ctx.options.append(real_opt)


class _HasTarget(Protocol):
    @property
    def target(self) -> str:
        ...


def resolve_options(ctx: Context) -> None:
    # Resolve variable options.
    unresolved_opt: Union[BoolOption, EnumOption, AnythingOption, ListOption]
    for unresolved_opt in chain(
        ctx.unresolved.bools,
        ctx.unresolved.enums,
        ctx.unresolved.anythings,
        ctx.unresolved.lists,
    ):
        # Register name with central container.
        ctx.options.append(unresolved_opt.to_surfraw_opt())

    # Symbol table.
    varopts: Dict[str, SurfrawOption] = {
        opt.name: opt for opt in ctx.options.variable_options
    }

    # Set `target` of flags to an instance of `SurfrawOption`.
    for flag in ctx.unresolved.flags:
        try:
            target: SurfrawOption = varopts[flag.target]
        except KeyError:
            raise OptionResolutionError(
                f"flag option '{flag.name}' does not target any existing {VALID_FLAG_TYPES_STR} option"
            ) from None
        _cleanup_flag_alias_resolve(ctx, flag, target)

    # Check if flag values are valid for their target type.
    try:
        for flag_target in varopts.values():
            flag_target.resolve_flags()
    except OptionParseError as e:
        raise OptionResolutionError(str(e)) from None

    # Set `target` of aliases to an instance of `SurfrawOption`.
    flag_names: Dict[str, SurfrawFlag] = {
        flag.name: flag for flag in ctx.flags
    }
    for alias in ctx.unresolved.aliases:
        # Check flags or aliases, depending on alias type.
        if issubclass(alias.ref_type, SurfrawAlias):
            raise OptionResolutionError(
                f"alias '{alias.name}' targets another alias, which is not allowed"
            )

        alias_target: Optional[Union[SurfrawFlag, SurfrawOption]]
        if issubclass(alias.ref_type, SurfrawFlag):
            alias_target = flag_names.get(alias.target)
        else:
            alias_target = varopts.get(alias.target)
        if alias_target is None or not isinstance(
            alias_target, alias.ref_type
        ):
            raise OptionResolutionError(
                f"alias '{alias.name}' does not target any options of matching type ('{alias.type.__name__}')"
            ) from None
        _cleanup_flag_alias_resolve(ctx, alias, alias_target)

    # Metavars + descriptions
    for metavar in ctx.metavars:
        try:
            opt = varopts[metavar.variable]
        except KeyError:
            raise OptionResolutionError(
                f"metavar for '{metavar.variable}' with the value '{metavar.metavar}' targets a non-existent variable"
            )
        else:
            opt.metavar = metavar.metavar
    for desc in ctx.descriptions:
        try:
            opt = varopts[desc.variable]
        except KeyError:
            raise OptionResolutionError(
                f"description for '{desc.variable}' targets a non-existent variable"
            )
        else:
            opt.description = desc.description

    # Check if options target variables that exist.
    var_checks: List[Tuple[Iterable[_HasTarget], str]] = [
        (ctx.mappings, "URL parameter"),
        (ctx.list_mappings, "URL parameter"),
        (ctx.inlines, "inlining"),
        (ctx.list_inlines, "inlining"),
        (ctx.collapses, "collapse"),
    ]
    for topts, subject_name in var_checks:
        for topt in topts:
            if topt.target not in varopts:
                raise OptionResolutionError(
                    f"{subject_name} '{topt.target}' does not target any existing variable"
                )
