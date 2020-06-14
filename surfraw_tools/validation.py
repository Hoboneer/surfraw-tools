from __future__ import annotations

import re
from typing import Any, Callable, List, TypeVar


class OptionParseError(Exception):
    pass


# NAME

# This is purposely not in the full range of shell variable names because I am
# trying to encourage a particular naming convention. That is,
# `SURFRAW_elvisname_onewordvar` is what the script would generate.
_VALID_SURFRAW_VAR_NAME = re.compile("^[a-z]+$")


def validate_name(name: str) -> str:
    if not _VALID_SURFRAW_VAR_NAME.fullmatch(name):
        raise OptionParseError(
            f"name '{name}' is an invalid variable name for an elvis"
        )
    return name


# YES-NO

# TODO: Should the yes-no option take the other forms?
# TRUE_WORDS = {"yes", "on", "1"}
# FALSE_WORDS = {"no", "off", "0"}
_TRUE_WORDS = {"yes"}
_FALSE_WORDS = {"no"}
_BOOL_WORDS = _TRUE_WORDS | _FALSE_WORDS


def validate_bool(bool_: str) -> str:
    if bool_ not in _BOOL_WORDS:
        valid_bools = ", ".join(sorted(_BOOL_WORDS))
        raise OptionParseError(
            f"bool '{bool_}' must be one of the following: {valid_bools}"
        )
    return bool_


def parse_bool(bool_: str) -> bool:
    if bool_ in _TRUE_WORDS:
        return True
    elif bool_ in _FALSE_WORDS:
        return False
    else:
        valid_bools = ", ".join(sorted(_BOOL_WORDS))
        raise OptionParseError(
            f"bool '{bool_}' must be one of the following: {valid_bools}"
        )


# OPTION TYPES is defined elsewhere to avoid circular imports.

# ENUM VALUES

_VALID_ENUM_VALUE_STR = "^[a-z0-9][a-z0-9_+-]*$"
_VALID_ENUM_VALUE = re.compile(_VALID_ENUM_VALUE_STR)


def validate_enum_value(value: str) -> str:
    if not _VALID_ENUM_VALUE.fullmatch(value):
        raise OptionParseError(
            f"enum value '{value}' must match the regex '{_VALID_ENUM_VALUE_STR}'"
        )
    return value


# MISC.

T = TypeVar("T")


def no_validation(arg: T) -> T:
    return arg


def list_of(validator: Callable[..., Any]) -> Callable[..., List[Any]]:
    def list_validator(arg):
        values = arg.split(",")
        # In case the validators return a different object from its input.
        new_values = []
        for value in values:
            new_values.append(validator(value))
        return new_values

    return list_validator
