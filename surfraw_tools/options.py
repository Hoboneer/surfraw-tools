"""Object representations for surfraw options."""
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
    """Model for options in surfraw elvi."""

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
        """Ensure option name does not override global surfraw options.

        A good default for its description is also set.
        """
        if self.name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{self.name}' is global, which cannot be overriden by elvi"
            )
        self.set_metadata(
            "description", f"A {self.typename} option for '{self.name}'"
        )

    @property
    def metavar(self) -> Optional[str]:
        """Return the metavar of this option.

        It should be fully uppercase.
        """
        return self._metadata["metavar"]

    @property
    def description(self) -> str:
        """Return the description of this option."""
        return self._metadata["description"]

    def set_metadata(
        self,
        key: Union[Literal["metavar"], Literal["description"]],
        val: Optional[str],
    ) -> None:
        """Set metadata for this option."""
        self._metadata[key] = val

    def __init_subclass__(cls) -> None:
        """Add relevant subclasses to `SurfrawOption.typenames` and give them typenames.

        "Relevant" subclasses are those classes that are actually instantiated
        in the code.
        """
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
        """Add surfraw alias to this option."""
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
        """Set default metavar as this option's name."""
        super().__post_init__()
        self.set_metadata("metavar", self.name.upper())

    def __init_subclass__(cls) -> None:
        """Add relevant subclasses to `SurfrawVarOption.typenames`."""
        super().__init_subclass__()
        if cls.__name__ != "SurfrawListType":
            SurfrawVarOption.typenames[cls.typename] = cls

    def add_flag(self, flag: SurfrawFlag) -> None:
        """Add surfraw flag for this option."""
        self.flags.append(flag)

    # Flags should be resolved *before* aliases so that aliases' targets aren't dangling.
    def resolve_flags(self) -> None:
        """Validate/parse flag values for this option.

        Since `SurfrawOption` objects (and subtypes) are immutable, the old
        flag objects are thrown away and new flags are made.
        """
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
        """Analyse flags after resolving them."""
        pass


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawListType(SurfrawVarOption):
    """Valid types for surfraw list options."""

    # This should only contain subclasses of `SurfrawListType`.
    # mypy doesn't seem to like having values of `typenames` to subclasses of this class.
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}

    def __init_subclass__(cls) -> None:
        """Add subclasses to `SurfrawListType.typenames`."""
        super().__init_subclass__()
        SurfrawListType.typenames[cls.typename] = cls


# Concrete option types follow


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawFlag(SurfrawOption):
    """Alias (with value) to a variable-creating option."""

    target: SurfrawVarOption
    value: Any

    def __post_init__(self) -> None:
        """Set metavar to `None` and set flag description.

        Flags don't take arguments so a metavar would be useless.
        For clarity, their description also can't be changed.
        """
        super().__post_init__()
        self.set_metadata("metavar", None)
        self.set_metadata(
            "description", f"An alias for -{self.target.name}={self.value}"
        )

    @property
    def type(self) -> Type[SurfrawOption]:
        """Return flag target type."""
        return self.target.__class__


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawBool(SurfrawVarOption):
    """Boolean option corresponding to 'yesno' in `surfraw`."""

    # Don't need to make new flag objects after resolving.
    flag_value_validator = validate_bool
    default: str


@dataclass(frozen=True, unsafe_hash=True)
class SurfrawEnum(SurfrawListType):
    """Option with user-specified list of valid values."""

    flag_value_validator = validate_enum_value
    default: str
    values: List[str] = field(hash=False)

    def __post_init__(self) -> None:
        """Ensure enum is consistent.

        This means it must specify its valid values (it's useless otherwise)
        and its default must be a valid value (duh).
        """
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
    """Unchecked option."""

    # Don't need to make new flag objects after resolving.
    flag_value_validator = no_validation
    default: str

    def __post_init__(self) -> None:
        """Set default description.

        Calling these 'anything' options in the help output is unclear--
        "unchecked" clarifies what it does.
        """
        super().__post_init__()
        self.set_metadata(
            "description", f"An unchecked option for '{self.name}'"
        )


# This class is not instantiated normally... maybe prepend name with underscore?
@dataclass(frozen=True, unsafe_hash=True)
class SurfrawSpecial(SurfrawVarOption):
    """Option with hardcoded values.

    This isn't created normally.  Users opt in.
    Good for common patterns in surfraw elvi.
    """

    default: str

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        """Fail every time.

        This shouldn't be called directly since `resolve_flags` is overridden.
        """
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawSpecial` directly"
        )

    def __post_init__(self) -> None:
        """Set metadata specific to each kind of special option."""
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
        """Resolve flags for each special option kind."""
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
    """List- or CSV-like option."""

    type: Type[SurfrawListType]
    defaults: List[str] = field(hash=False)
    values: List[str] = field(hash=False)

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        """Fail every time.

        This shouldn't be called directly since `resolve_flags` is overridden.
        """
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawList` directly"
        )

    def __post_init__(self) -> None:
        """Ensure list is consistent.

        Enum-list defaults must be a subset of its valid values.
        """
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
        """Resolve flags for each list option type."""
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
    """Alias (without value) to variable-creating option or flag option.

    This is essentially a shorthand for common options.
    """

    target: Union[SurfrawVarOption, SurfrawFlag]

    def __post_init__(self) -> None:
        """Set metavar to `None`."""
        super().__post_init__()
        self.set_metadata("metavar", None)
