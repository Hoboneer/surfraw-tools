# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Object representations for surfraw options."""
from __future__ import annotations

import re
import weakref
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    NoReturn,
    Optional,
    Type,
    Union,
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
    from typing_extensions import Final

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


class SurfrawOption:
    """Model for options in surfraw elvi."""

    __slots__ = ("name", "aliases", "metavar", "description")

    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}
    typename: ClassVar[str]
    typename_plural: ClassVar[str]

    def __init__(self, name: str):
        if name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{name}' is global, which cannot be overriden by elvi"
            )
        self.name: Final = name
        self.aliases: Final[weakref.WeakSet[SurfrawAlias]] = weakref.WeakSet()

        self.metavar: Optional[str] = None
        self.description: str = f"A {self.__class__.typename} option for '{self.name}'"

    def __init_subclass__(cls) -> None:
        """Add relevant subclasses to `SurfrawOption.typenames` and give them typenames.

        "Relevant" subclasses are those classes that are actually instantiated
        in the code.
        """
        if cls.__name__ in ("SurfrawVarOption", "SurfrawListType"):
            # This is just a superclass.  It won't be used.
            # FIXME: Special case.  Refactor?
            return
        SurfrawOption.typenames[cls.typename] = cls

    def add_alias(self, alias: SurfrawAlias) -> None:
        """Add surfraw alias to this option."""
        self.aliases.add(alias)


class SurfrawVarOption(SurfrawOption):
    """Superclass for options that create variables in elvi."""

    __slots__ = ("flags", "_resolved_flag_values")

    # This should only contain subclasses of `SurfrawVarOption`.
    # mypy doesn't seem to like having values of `typenames` to subclasses of this class.
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}

    flag_value_validator: ClassVar[_FlagValidator]

    def __init__(self, name: str):
        super().__init__(name)

        # Flags should be listed in the order that they were defined in the command line.
        self.flags: Final[List[SurfrawFlag]] = []
        self._resolved_flag_values: Final[List[SurfrawFlag]] = []

        self.metavar = self.name.upper()

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


class SurfrawFlag(SurfrawOption):
    """Alias (with value) to a variable-creating option."""

    __slots__ = ("target", "value")

    typename = "flag"
    typename_plural = "flags"

    def __init__(self, name: str, target: SurfrawVarOption, value: Any):
        super().__init__(name)
        self.target: Final = target
        self.value: Final = value
        # Flags don't take arguments so a metavar would be useless.
        # For clarity, their description also can't be changed.
        self.metavar = None
        self.description = f"An alias for -{self.target.name}={self.value}"

    @property
    def type(self) -> Type[SurfrawOption]:
        """Return flag target type."""
        return self.target.__class__


class SurfrawBool(SurfrawVarOption):
    """Boolean option corresponding to 'yesno' in `surfraw`."""

    __slots__ = ("default",)

    typename = "bool"
    typename_plural = "bools"

    # Don't need to make new flag objects after resolving.
    flag_value_validator = validate_bool

    def __init__(self, name: str, default: str):
        super().__init__(name)
        self.default: Final = default


class SurfrawEnum(SurfrawListType):
    """Option with user-specified list of valid values."""

    __slots__ = ("default", "values")

    typename = "enum"
    typename_plural = "enums"

    flag_value_validator = validate_enum_value

    def __init__(self, name: str, default: str, values: List[str]):
        super().__init__(name)
        # Ensure enum is consistent.
        if not values:
            raise ValueError(
                f"enum '{self.name}' must specify its valid values"
            )
        if default not in values:
            raise ValueError(
                f"enum default value '{default}' must be within '{values}'"
            )
        self.default: Final = default
        self.values: Final = values

        # "A enum" is incorrect.
        self.description = re.sub("^A ", "An ", self.description)

    def _post_resolve_flags(self) -> None:
        vals = set(self.values)
        if (set(self._resolved_flag_values) | vals) > vals:
            raise OptionResolutionError(
                f"values of flags to enum '{self.name}' are a superset of the valid values ({self.values})'"
            )


class SurfrawAnything(SurfrawListType):
    """Unchecked option."""

    __slots__ = ("default",)

    typename = "anything"
    typename_plural = "anythings"

    # Don't need to make new flag objects after resolving.
    flag_value_validator = no_validation

    def __init__(self, name: str, default: str):
        super().__init__(name)
        self.default: Final = default
        # Calling these 'anything' options in the help output is unclear.
        self.description = f"An unchecked option for '{self.name}'"


# This class is not instantiated normally... maybe prepend name with underscore?
class SurfrawSpecial(SurfrawVarOption):
    """Option with hardcoded values.

    This isn't created normally.  Users opt in.
    Good for common patterns in surfraw elvi.
    """

    __slots__ = ("default",)

    typename = "special"
    typename_plural = "specials"

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        """Fail every time.

        This shouldn't be called directly since `resolve_flags` is overridden.
        """
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawSpecial` directly"
        )

    def __init__(self, name: str, default: str):
        super().__init__(name)
        self.default: Final = default

        # Set metadata specific to each kind of special option.
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
class SurfrawList(SurfrawVarOption):
    """List- or CSV-like option."""

    __slots__ = ("type", "defaults", "values")

    typename = "list"
    typename_plural = "lists"

    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        """Fail every time.

        This shouldn't be called directly since `resolve_flags` is overridden.
        """
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawList` directly"
        )

    def __init__(
        self,
        name: str,
        type: Type[SurfrawListType],
        defaults: List[str],
        values: List[str],
    ):
        super().__init__(name)
        self.type: Final = type
        self.defaults: Final = defaults
        self.values: Final = values

        self.description = f"A repeatable (cumulative) '{self.type.typename}' list option for '{self.name}'"

        # Ensure list is consistent.
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
            flag.description = f"An alias for the '{self.type.typename}' list option '{self.name}' with the values '{','.join(flag.value)}'"
            # Don't need to check `AnythingOption`.


class SurfrawAlias(SurfrawOption):
    """Alias (without value) to variable-creating option or flag option.

    This is essentially a shorthand for common options.
    """

    __slots__ = ("target", "__weakref__")

    typename = "alias"
    typename_plural = "aliases"

    def __init__(
        self, name: str, target: Union[SurfrawVarOption, SurfrawFlag]
    ):
        super().__init__(name)
        self.target: Final = target
