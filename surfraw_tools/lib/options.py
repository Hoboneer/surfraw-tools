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

from surfraw_tools.lib.validation import (
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

    def __init__(
        self,
        name: str,
        *,
        metavar: Optional[str] = None,
        description: Optional[str] = None,
    ):
        if name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{name}' is global, which cannot be overriden by elvi"
            )
        self.name: Final = name
        self.aliases: Final[weakref.WeakSet[SurfrawAlias]] = weakref.WeakSet()

        self.metavar: Optional[str] = metavar
        self.description: str = description or (
            f"A {self.__class__.typename} option for '{self.name}'"
        )

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

    __slots__ = ("flags",)

    # This should only contain subclasses of `SurfrawVarOption`.
    # mypy doesn't seem to like having values of `typenames` to subclasses of this class.
    typenames: ClassVar[Dict[str, Type[SurfrawOption]]] = {}

    flag_value_validator: ClassVar[_FlagValidator]

    def __init__(self, name: str, **kwargs: Any):
        super().__init__(name, **kwargs)

        # Flags should be listed in the order that they were defined in the command line.
        self.flags: Final[List[SurfrawFlag]] = []

        self.metavar = self.metavar or self.name.upper()

    def __init_subclass__(cls) -> None:
        """Add relevant subclasses to `SurfrawVarOption.typenames`."""
        super().__init_subclass__()
        if cls.__name__ != "SurfrawListType":
            SurfrawVarOption.typenames[cls.typename] = cls

    def add_flag(self, flag: SurfrawFlag) -> None:
        """Add surfraw flag for this option."""
        if flag.target is not self:
            raise OptionResolutionError(
                f"tried to add flag '{flag.name}' to an option it doesn't target"
            )
        self.resolve_flag(flag)
        self.flags.append(flag)

    def resolve_flag(self, flag: SurfrawFlag) -> None:
        """Check that the value of `flag` is valid for the type of its target."""
        try:
            self.__class__.flag_value_validator(flag.value)
        except OptionParseError as e:
            raise OptionResolutionError(str(e)) from None


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

    def __init__(
        self, name: str, target: SurfrawVarOption, value: Any, **kwargs: Any
    ):
        super().__init__(name, **kwargs)
        self.target: Final = target
        self.value = value
        # Flags don't take arguments so a metavar would be useless.
        # For clarity, their description also can't be changed.
        if "metavar" in kwargs:
            raise ValueError("flags can't have metavars")
        elif "description" in kwargs:
            # At least not yet.  I want flags to clearly show what they're aliases for.
            raise ValueError("flags can't have custom descriptions")
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

    def __init__(self, name: str, default: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.default: Final = default


class SurfrawEnum(SurfrawListType):
    """Option with user-specified list of valid values."""

    __slots__ = ("default", "values")

    typename = "enum"
    typename_plural = "enums"

    flag_value_validator = validate_enum_value

    def __init__(
        self, name: str, default: str, values: List[str], **kwargs: Any
    ):
        super().__init__(name, **kwargs)
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

        # Can't risk messing up a custom description.
        if "description" not in kwargs:
            # "A enum" is incorrect.
            self.description = re.sub("^A ", "An ", self.description)

    def resolve_flag(self, flag: SurfrawFlag) -> None:
        """Check that the value of `flag` is valid for an enum.

        In addition the default implementation, this checks that the value is
        in `self.values`.
        """
        super().resolve_flag(flag)
        if flag.value not in set(self.values):
            raise OptionResolutionError(
                f"value of flag '{flag.name}' to enum '{self.name}' is not a valid value"
            )


class SurfrawAnything(SurfrawListType):
    """Unchecked option."""

    __slots__ = ("default",)

    typename = "anything"
    typename_plural = "anythings"

    flag_value_validator = no_validation

    def __init__(self, name: str, default: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.default: Final = default
        # Calling these 'anything' options in the help output is unclear.
        if "description" not in kwargs:
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

        This shouldn't be called directly since `resolve_flag` is overridden.
        """
        raise RuntimeError(
            "don't call `flag_value_validator` of `SurfrawSpecial` directly"
        )

    def __init__(self, name: str, default: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.default: Final = default
        if self.name not in ("results", "language"):
            raise ValueError(f"'{self.name}' is an unsupported special option")

    def resolve_flag(self, flag: SurfrawFlag) -> None:
        """Resolve flags for each special option kind."""
        if flag.name == "results":
            try:
                new_val = int(flag.value)
            except ValueError:
                raise OptionResolutionError(
                    "value for special 'results' option must be an integer"
                ) from None
            flag.value = new_val
        # The language option needn't be checked here.  There are way too
        # many ISO language codes to match.


class SurfrawList(SurfrawVarOption):
    """List- or CSV-like option."""

    __slots__ = ("type", "defaults", "values")

    typename = "list"
    typename_plural = "lists"

    # This is only determinable at runtime.
    @staticmethod
    def flag_value_validator(_: Any) -> NoReturn:
        """Fail every time.

        This shouldn't be called directly since `resolve_flag` is overridden.
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
        **kwargs: Any,
    ):
        super().__init__(name, **kwargs)
        self.type: Final = type
        self.defaults: Final = defaults
        self.values: Final = values

        if "description" not in kwargs:
            self.description = f"A repeatable (cumulative) '{self.type.typename}' list option for '{self.name}'"

        # Ensure list is consistent.
        if issubclass(self.type, SurfrawEnum):
            if not set(self.defaults) <= set(self.values):
                raise ValueError(
                    f"enum list option {self.name}'s defaults ('{self.defaults}') must be a subset of its valid values ('{self.values}')"
                )

    def resolve_flag(self, flag: SurfrawFlag) -> None:
        """Check that `flag` is valid for its type.

        This also ensures that `flag.value` is a list.
        """
        try:
            flag_values = list_of(self.type.flag_value_validator)(flag.value)
        except OptionParseError as e:
            raise OptionResolutionError(str(e)) from None

        if issubclass(self.type, SurfrawEnum) and set(flag_values) > set(
            self.values
        ):
            raise OptionResolutionError(
                f"enum list flag option {flag.name}'s value ('{flag_values}') must be a subset of its target's values ('{self.values}')"
            )

        flag.value = flag_values
        flag.description = f"An alias for the '{self.type.typename}' list option '{self.name}' with the values '{','.join(flag.value)}'"


class SurfrawAlias(SurfrawOption):
    """Alias (without value) to variable-creating option or flag option.

    This is essentially a shorthand for common options.
    """

    __slots__ = ("target", "__weakref__")

    typename = "alias"
    typename_plural = "aliases"

    def __init__(
        self,
        name: str,
        target: Union[SurfrawVarOption, SurfrawFlag],
        **kwargs: Any,
    ):
        super().__init__(name, **kwargs)
        self.target: Final = target
        if "metavar" in kwargs:
            raise ValueError("aliases can't have metavars")
        elif "description" in kwargs:
            # It doesn't make sense for aliases: each appears alongside its parent option.
            raise ValueError("aliases can't have custom descriptions")
