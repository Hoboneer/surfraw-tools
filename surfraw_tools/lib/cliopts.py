# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Represent options from cli as object."""
from __future__ import annotations

import re
from collections import deque
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    cast,
)

from .options import (
    SurfrawAlias,
    SurfrawAnything,
    SurfrawBool,
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawListType,
    SurfrawOption,
    SurfrawVarOption,
    _FlagValidator,
)
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
    from typing_extensions import Final

_FlagValidatorsType = Sequence[Union[Sequence[_FlagValidator], _FlagValidator]]
_O = TypeVar("_O", bound=Type["Option"])


class Option:
    """Option to a command-line program with validated colon-delimited arguments.

    Configure subclasses with these class attributes:

        validators: A list of validator or parser functions from `.validation`, corresponding to its arguments in the command line.
        last_arg_is_unlimited: Whether the last arg may be repeated.  (default: `False`)
    """

    __slots__ = ()

    validators: ClassVar[_FlagValidatorsType]
    last_arg_is_unlimited: ClassVar[bool] = False

    @classmethod
    def from_arg(cls: _O, arg: str) -> _O:
        """Construct an instance from a single string of arguments.

        `arg` is delimited by colon (':') characters.
        """
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
        """Validate `raw_arg` using `validators`.

        Despite the name, each validator may map values to different types,
        i.e., a parser.

        `validators` may contain nested sequences of validators to denote
        optional groups, e.g., `validators=[foo, bar, [baz]]`.

        If `last_is_unlimited` is `True`, then the args will be validated by
        the final validator until exhausted.
        """
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


class FlagOption(Option):
    """Alias (with value) to a variable-creating option."""

    __slots__ = ("name", "target", "value")

    validators = (validate_name, validate_name, no_validation)

    def __init__(self, name: str, target: str, value: str):
        self.name: Final = name
        self.target: Final = target
        self.value: Final = value

    def to_surfraw_opt(self, resolved_target: SurfrawVarOption) -> SurfrawFlag:
        """Resolve flag target to a concrete option."""
        return SurfrawFlag(self.name, resolved_target, self.value)


class BoolOption(Option):
    """Boolean option corresponding to 'yesno' in `surfraw`."""

    __slots__ = ("name", "default")

    validators = (validate_name, validate_bool)

    def __init__(self, name: str, default: str):
        self.name: Final = name
        self.default: Final = default

    def to_surfraw_opt(self) -> SurfrawBool:
        """Return model for surfraw bool options."""
        return SurfrawBool(self.name, self.default)


class EnumOption(Option):
    """Option with user-specified list of valid values."""

    __slots__ = ("name", "default", "values")

    validators = (
        validate_name,
        validate_enum_value,
        list_of(validate_enum_value),
    )

    def __init__(self, name: str, default: str, values: List[str]):
        self.name: Final = name
        self.default: Final = default
        self.values: Final = values

    def to_surfraw_opt(self) -> SurfrawEnum:
        """Return model for surfraw enum options."""
        return SurfrawEnum(self.name, self.default, self.values)


class AnythingOption(Option):
    """Unchecked option."""

    __slots__ = ("name", "default")

    validators = (validate_name, no_validation)

    def __init__(self, name: str, default: str):
        self.name: Final = name
        self.default: Final = default

    def to_surfraw_opt(self) -> SurfrawAnything:
        """Return model for surfraw 'anything' options."""
        return SurfrawAnything(self.name, self.default)


def _parse_list_type(list_type: str) -> Type[SurfrawListType]:
    try:
        type_ = SurfrawListType.typenames[list_type]
    except KeyError:
        raise OptionParseError(
            f"list type '{list_type}' must be one of the following: {', '.join(sorted(SurfrawListType.typenames))}"
        ) from None
    else:
        return cast(Type[SurfrawListType], type_)


class ListOption(Option):
    """List- or CSV-like option."""

    __slots__ = ("name", "type", "defaults", "values")

    validators = (
        validate_name,
        _parse_list_type,
        list_of(no_validation),
        (list_of(no_validation),),
    )

    def __init__(
        self,
        name: str,
        type: Type[SurfrawListType],
        defaults: List[str],
        values: Optional[List[str]] = None,
    ):
        if values is None:
            values = []

        self.name: Final = name
        self.type: Final = type
        self.defaults: Final = defaults
        self.values: Final = values

        # Validate `self.values` if needed, according to `self.type`.
        if issubclass(self.type, SurfrawEnum):
            if not self.values:
                raise OptionParseError(
                    "fourth argument to `--list` option must be provided for enum lists"
                )

            for val in self.values:
                # Raise `OptionParseError` if invalid.
                validate_enum_value(val)

        elif issubclass(self.type, SurfrawAnything):
            # Nothing to check for 'anythings'.
            pass

    def to_surfraw_opt(self) -> SurfrawList:
        """Return model for surfraw list options."""
        return SurfrawList(self.name, self.type, self.defaults, self.values)


def _parse_alias_type(
    alias_type: str,
) -> Union[Type[SurfrawVarOption], Type[SurfrawFlag]]:
    if alias_type == SurfrawAlias.typename:
        raise OptionParseError("aliases may not target other aliases")
    # For backward compatibility.
    if alias_type == "yes-no":
        alias_type = "bool"

    try:
        type_ = SurfrawOption.typenames[alias_type]
    except KeyError:
        valid_option_types = ", ".join(
            sorted(
                typename
                for typename, type_ in SurfrawOption.typenames.items()
                if not issubclass(type_, SurfrawAlias)
            )
        )
        raise OptionParseError(
            f"alias type '{alias_type}' must be one of the following: {valid_option_types}"
        )
    else:
        return cast(Union[Type[SurfrawVarOption], Type[SurfrawFlag]], type_)


class AliasOption(Option):
    """Alias (without value) to variable-creating option or flag option.

    This is essentially a shorthand for common options.
    """

    __slots__ = ("name", "target", "type")

    validators = (validate_name, validate_name, _parse_alias_type)

    def __init__(
        self,
        name: str,
        target: str,
        type: Union[Type[SurfrawVarOption], Type[SurfrawFlag]],
    ):
        self.name: Final = name
        self.target: Final = target
        self.type: Final = type

    def to_surfraw_opt(
        self, resolved_target: Union[SurfrawVarOption, SurfrawFlag]
    ) -> SurfrawAlias:
        """Resolve alias target to a concrete option.

        Note that the model of surfraw aliases doesn't need to store its type
        since it already contains a reference.
        """
        # No longer need to store target type explicitly (it has a reference!).
        return SurfrawAlias(self.name, resolved_target)


class MappingOption(Option):
    """Non-surfraw option to map surfraw variables to url parameters.

    `should_url_encode` specifies whether to percent-encode the values of
    target variables, which is useful for already-encoded values.
    """

    __slots__ = ("target", "parameter", "should_url_encode")

    validators = (validate_name, no_validation, (parse_bool,))

    def __init__(
        self, target: str, parameter: str, should_url_encode: bool = True
    ):
        self.target: Final = target
        self.parameter: Final = parameter
        self.should_url_encode: Final = should_url_encode

    @property
    def variable(self) -> str:
        """Return the surfraw variable this mapping targets."""
        # To allow other code to continue to use this class unchanged
        return self.target


class InlineOption(Option):
    """Non-surfraw option to map surfraw variables to search keywords.

    A common use would be to output "search string... filetype:pdf", without
    users having to memorise keywords or with special preprocessing.
    """

    __slots__ = ("target", "keyword")

    validators = (validate_name, validate_name)

    def __init__(self, target: str, keyword: str):
        self.target: Final = target
        self.keyword: Final = keyword

    @property
    def variable(self) -> str:
        """Return the surfraw variable this inlining targets."""
        # To allow other code to continue to use this class unchanged
        return self.target


class CollapseOption(Option):
    """Non-surfraw option to modify variables in-place using a shell case statement.

    This may specify unlimited cases in the output case statement.  The last
    list value in each case is what the variable is replaced with, which may
    contain command substitutions and is run within double quotes.
    """

    __slots__ = ("target", "collapses")

    validators = (validate_name, list_of(no_validation))
    last_arg_is_unlimited = True

    def __init__(self, target: str, collapses: List[str]):
        self.target: Final = target
        self.collapses: Final = collapses

    @property
    def variable(self) -> str:
        """Return the surfraw variable this collapse targets."""
        # To allow other code to continue to use this class unchanged
        return self.target


_VALID_METAVAR_STR: Final = "^[a-z]+$"
_VALID_METAVAR: Final = re.compile(_VALID_METAVAR_STR)


def _validate_metavar(metavar: str) -> str:
    if not _VALID_METAVAR.fullmatch(metavar):
        raise OptionParseError(
            f"metavar '{metavar}' must match the regex '{_VALID_METAVAR_STR}'"
        )
    return metavar


class MetavarOption(Option):
    """Option to set the metavar of surfraw options."""

    __slots__ = ("variable", "metavar")

    validators = (validate_name, _validate_metavar)

    def __init__(self, variable: str, metavar: str):
        self.variable: Final = variable
        self.metavar: Final = metavar.upper()


class DescribeOption(Option):
    """Option to set the description of surfraw options."""

    __slots__ = ("variable", "description")

    validators = (validate_name, no_validation)

    def __init__(self, variable: str, description: str):
        self.variable: Final = variable
        self.description: Final = description
