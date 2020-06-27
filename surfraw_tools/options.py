from __future__ import annotations

import re
import weakref
from dataclasses import dataclass, field
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Match,
    NoReturn,
    Optional,
    Type,
    Union,
    cast,
)

from .validation import (
    OptionParseError,
    OptionResolutionError,
    list_of,
    no_validation,
    validate_bool,
    validate_enum_value,
)

if TYPE_CHECKING:
    from typing_extensions import TypedDict, Literal, Final

    class _SurfrawMetadata(TypedDict):
        metavar: Optional[str]
        description: str


# Options with non alphabetic characters are impossible
_FORBIDDEN_OPTION_NAMES: Final = {
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


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawOption:
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}
    typename: ClassVar[str]
    typename_plural: ClassVar[str]

    name: str

    # `_metadata` holds the true data.
    _metadata: _SurfrawMetadata = field(
        default_factory=cast(
            Type["_SurfrawMetadata"],
            partial(dict, metavar=None, description=None),
        ),
        init=False,
        compare=False,
    )

    aliases: weakref.WeakSet[SurfrawAlias] = field(
        default_factory=weakref.WeakSet, init=False, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{self.name}' is global, which cannot be overriden by elvi"
            )
        self.set_metadata(
            "description", f"A {self.typename} option for '{self.name}'"
        )

    @property
    def metavar(self) -> Optional[str]:
        return self._metadata["metavar"]

    @property
    def description(self) -> str:
        return self._metadata["description"]

    def set_metadata(
        self,
        key: Union[Literal["metavar"], Literal["description"]],
        val: Optional[str],
    ) -> None:
        self._metadata[key] = val

    def __init_subclass__(cls) -> None:
        if cls.__name__ in ("SurfrawVarOption", "SurfrawListType"):
            # This is just a superclass.  It won't be used.
            # FIXME: Special case.  Refactor?
            return
        subclass_re = r"Surfraw([A-Z][a-z]+)"
        try:
            cls.typename = (
                cast(Match[str], re.match(subclass_re, cls.__name__))
                .group(1)
                .lower()
            )
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

    def add_alias(self, alias: SurfrawAlias) -> None:
        self.aliases.add(alias)


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawVarOption(SurfrawOption):
    """Superclass for options that create variables in elvi."""

    # This should only contain subclasses of `SurfrawVarOption`.
    # mypy doesn't seem to like having values of `typenames` to subclasses of this class.
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}

    flag_value_validator: ClassVar[_FlagValidator]

    # Flags should be listed in the order that they were defined in the command line.
    flags: List[SurfrawFlag] = field(
        default_factory=list, init=False, compare=False, repr=False
    )
    _resolved_flag_values: List[SurfrawFlag] = field(
        default_factory=list, init=False, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        self.set_metadata("metavar", self.name.upper())

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls.__name__ != "SurfrawListType":
            SurfrawVarOption.typenames[cls.typename] = cls

    def add_flag(self, flag: SurfrawFlag) -> None:
        self.flags.append(flag)

    # Flags should be resolved *before* aliases so that aliases' targets aren't dangling.
    def resolve_flags(self) -> None:
        try:
            for flag in self.flags:
                self._resolved_flag_values.append(
                    self.__class__.flag_value_validator(flag.value)
                )
        except OptionParseError as e:
            raise OptionResolutionError(str(e)) from None
        self._post_resolve_flags()
        # They're useless now.
        self._resolved_flag_values.clear()

    def _post_resolve_flags(self) -> None:
        pass


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawListType(SurfrawVarOption):
    # This should only contain subclasses of `SurfrawListType`.
    # mypy doesn't seem to like having values of `typenames` to subclasses of this class.
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        SurfrawListType.typenames[cls.typename] = cls


# Concrete option types follow


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawFlag(SurfrawOption):
    target: SurfrawVarOption
    value: Any

    def __post_init__(self) -> None:
        super().__post_init__()
        self.set_metadata("metavar", None)
        self.set_metadata(
            "description", f"An alias for -{self.target.name}={self.value}"
        )

    @property
    def type(self) -> Type[SurfrawOption]:
        return self.target.__class__


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawBool(SurfrawVarOption):
    # Don't need to make new flag objects after resolving.
    flag_value_validator = validate_bool
    default: str


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawEnum(SurfrawListType):
    flag_value_validator = validate_enum_value
    default: str
    values: List[str] = field(hash=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.values:
            raise ValueError(
                f"enum '{self.name}' must specify its valid values"
            )
        if self.default not in self.values:
            raise ValueError(
                f"enum default value '{self.default}' must be within '{self.values}'"
            )
        # "A enum" is incorrect.
        self.set_metadata(
            "description", re.sub("^A ", "An ", self.description)
        )

    def _post_resolve_flags(self) -> None:
        vals = set(self.values)
        if (set(self._resolved_flag_values) | vals) > vals:
            raise OptionResolutionError(
                f"values of flags to enum '{self.name}' are a superset of the valid values ({self.values})'"
            )


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawAnything(SurfrawListType):
    # Don't need to make new flag objects after resolving.
    flag_value_validator = no_validation
    default: str

    def __post_init__(self) -> None:
        super().__post_init__()
        self.set_metadata(
            "description", f"An unchecked option for '{self.name}'"
        )


# This class is not instantiated normally... maybe prepend name with underscore?
@dataclass(frozen=True, unsafe_hash=True)
class SurfrawSpecial(SurfrawVarOption):
    default: str

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawSpecial` directly"
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.name == "results":
            # Match the rest of the elvi's metavars for -results=
            self.set_metadata("metavar", "NUM")
            self.set_metadata(
                "description", "Number of search results returned"
            )
        elif self.name == "language":
            # Match the wikimedia elvi
            self.set_metadata("metavar", "ISOCODE")
            self.set_metadata(
                "description",
                "Two letter language code (resembles ISO country codes)",
            )
        else:
            raise ValueError(
                f"special options cannot have the name '{self.name}'"
            )
        # Use default metavar and description otherwise.

    def resolve_flags(self) -> None:
        for i, flag in enumerate(self.flags):
            if flag.name == "results":
                try:
                    new_val = int(flag.value)
                except ValueError:
                    raise OptionResolutionError(
                        "value for special 'results' option must be an integer"
                    ) from None
                self.flags[i] = SurfrawFlag(flag.name, flag.target, new_val)
            # The language option needn't be checked here.  There are way too
            # many ISO language codes to match.


# XXX: Should this store validators for the type it has?
@dataclass(frozen=True, unsafe_hash=True)
class SurfrawList(SurfrawVarOption):
    type: Type[SurfrawListType]
    defaults: List[str] = field(hash=False)
    values: List[str] = field(hash=False)

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawList` directly"
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        self.set_metadata(
            "description",
            f"A repeatable (cumulative) '{self.type.typename}' list option for '{self.name}'",
        )

        if issubclass(self.type, SurfrawEnum):
            if not set(self.defaults) <= set(self.values):
                raise ValueError(
                    f"enum list option {self.name}'s defaults ('{self.defaults}') must be a subset of its valid values ('{self.values}')"
                )

    def resolve_flags(self) -> None:
        # Don't need to make new flag objects after resolving.
        for flag in self.flags:
            if issubclass(self.type, SurfrawEnum):
                try:
                    flag_values = list_of(validate_enum_value)(flag.value)
                except OptionParseError as e:
                    raise OptionResolutionError(str(e)) from None
                if not set(flag_values) <= set(self.values):
                    raise OptionResolutionError(
                        f"enum list flag option {flag.name}'s value ('{flag_values}') must be a subset of its target's values ('{self.values}')"
                    )
            flag.set_metadata(
                "description",
                f"An alias for the '{self.type.typename}' list option '{self.name}' with the values '{','.join(flag.value)}'",
            )
            # Don't need to check `AnythingOption`.


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawAlias(SurfrawOption):
    target: Union[SurfrawVarOption, SurfrawFlag]

    def __post_init__(self) -> None:
        super().__post_init__()
        self.set_metadata("metavar", None)
