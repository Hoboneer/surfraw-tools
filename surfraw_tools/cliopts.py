"""Represent options from cli as object."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    List,
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

    validators: ClassVar[_FlagValidatorsType]
    last_arg_is_unlimited: ClassVar[bool] = False

    typename: ClassVar[str]
    typename_plural: ClassVar[str]

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


@dataclass(frozen=True)
class FlagOption(Option):
    validators = (validate_name, validate_name, no_validation)
    name: str
    target: str
    value: str

    def to_surfraw_opt(self, resolved_target: SurfrawVarOption) -> SurfrawFlag:
        return SurfrawFlag(self.name, resolved_target, self.value)


@dataclass(frozen=True)
class BoolOption(Option):
    validators = (validate_name, validate_bool)
    name: str
    default: str

    def to_surfraw_opt(self) -> SurfrawBool:
        return SurfrawBool(self.name, self.default)


@dataclass(frozen=True)
class EnumOption(Option):
    validators = (
        validate_name,
        validate_enum_value,
        list_of(validate_enum_value),
    )
    name: str
    default: str
    values: List[str] = field(hash=False)

    def to_surfraw_opt(self) -> SurfrawEnum:
        return SurfrawEnum(self.name, self.default, self.values)


@dataclass(frozen=True)
class AnythingOption(Option):
    validators = (validate_name, no_validation)
    name: str
    default: str

    def to_surfraw_opt(self) -> SurfrawAnything:
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


@dataclass(frozen=True)
class ListOption(Option):
    validators = (
        validate_name,
        _parse_list_type,
        list_of(no_validation),
        (list_of(no_validation),),
    )

    name: str
    type: Type[SurfrawListType]
    defaults: List[str] = field(hash=False)
    values: List[str] = field(default_factory=list, hash=False)

    def __post_init__(self) -> None:
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


@dataclass(frozen=True)
class AliasOption(Option):
    validators = (validate_name, validate_name, _parse_alias_type)
    name: str
    target: str
    type: Union[Type[SurfrawVarOption], Type[SurfrawFlag]]

    def to_surfraw_opt(
        self, resolved_target: Union[SurfrawVarOption, SurfrawFlag]
    ) -> SurfrawAlias:
        # No longer need to store target type explicitly (it has a reference!).
        return SurfrawAlias(self.name, resolved_target)


@dataclass(frozen=True)
class MappingOption(Option):
    validators = (validate_name, no_validation, (parse_bool,))
    target: str
    parameter: str
    should_url_encode: bool = True

    @property
    def variable(self) -> str:
        # To allow other code to continue to use this class unchanged
        return self.target


@dataclass(frozen=True)
class InlineOption(Option):
    validators = (validate_name, validate_name)
    target: str
    keyword: str

    @property
    def variable(self) -> str:
        # To allow other code to continue to use this class unchanged
        return self.target


@dataclass(frozen=True)
class CollapseOption(Option):
    validators = (validate_name, list_of(no_validation))
    last_arg_is_unlimited = True

    target: str
    collapses: List[str] = field(hash=False)

    @property
    def variable(self) -> str:
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


# Treat this as immutable!
@dataclass
class MetavarOption(Option):
    validators = (validate_name, _validate_metavar)
    variable: str
    metavar: str

    def __post_init__(self) -> None:
        self.metavar = self.metavar.upper()


@dataclass(frozen=True)
class DescribeOption(Option):
    validators = (validate_name, no_validation)
    variable: str
    description: str
