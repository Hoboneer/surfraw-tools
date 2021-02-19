# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Validators and parsers for option arguments.

All functions should raise `OptionParseError` on invalid input.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, List, TypeVar, cast

if TYPE_CHECKING:
    from typing_extensions import Final


class OptionParseError(Exception):
    """Exception when options are given incorrect arguments."""


class OptionResolutionError(Exception):
    """Exception when resolving options' targets to concrete objects fails."""


# NAME

# This is purposely not in the full range of shell variable names because I am
# trying to encourage a particular naming convention. That is,
# `SURFRAW_elvisname_onewordvar` is what the script would generate.
_VALID_SURFRAW_VAR_NAME: Final = re.compile("^[a-z]+$")


def validate_name(name: str) -> str:
    """Return `name` unchanged if it is valid for inclusion in elvi.

    Raises `OptionParseError` on invalid input.
    """
    if not _VALID_SURFRAW_VAR_NAME.fullmatch(name):
        raise OptionParseError(
            f"name '{name}' is an invalid variable name for an elvis"
        )
    return name


# YES-NO

# TODO: Should the yes-no option take the other forms?
# TRUE_WORDS = {"yes", "on", "1"}
# FALSE_WORDS = {"no", "off", "0"}
_TRUE_WORDS: Final = {"yes"}
_FALSE_WORDS: Final = {"no"}
_BOOL_WORDS: Final = _TRUE_WORDS | _FALSE_WORDS


def validate_bool(bool_: str) -> str:
    """Return `bool_` unchanged if it is a word representing a boolean.

    Raises `OptionParseError` on invalid input.
    """
    if bool_ not in _BOOL_WORDS:
        valid_bools = ", ".join(sorted(_BOOL_WORDS))
        raise OptionParseError(
            f"bool '{bool_}' must be one of the following: {valid_bools}"
        )
    return bool_


def parse_bool(bool_: str) -> bool:
    """Map boolean words to `True` or `False`.

    Raises `OptionParseError` on invalid input.
    """
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

_VALID_ENUM_VALUE_STR: Final = "^[a-z0-9][a-z0-9_+-]*$"
_VALID_ENUM_VALUE: Final = re.compile(_VALID_ENUM_VALUE_STR)


def validate_enum_value(value: str) -> str:
    """Return `value` unchanged if it is valid for surfraw enums.

    Technically, anything is valid for surfraw enums, but *our* enums are
    restricted since it makes life a bit easier.

    Raises `OptionParseError` on invalid input.
    """
    if not _VALID_ENUM_VALUE.fullmatch(value):
        raise OptionParseError(
            f"enum value '{value}' must match the regex '{_VALID_ENUM_VALUE_STR}'"
        )
    return value


# MISC.


def no_validation(arg: str) -> str:
    """Return `arg` unchanged.

    This is an identity function and raises no exceptions.
    """
    return arg


T = TypeVar("T")


def list_of(validator: Callable[[str], T]) -> Callable[[str], List[T]]:
    """Run `validator` on a comma-delimited list of arguments."""

    def list_validator(arg: str) -> List[T]:
        if arg == "":
            return []
        values = arg.split(",")
        # In case the validators return a different object from its input (i.e., parsers).
        for i, value in enumerate(values):
            # Mutating it is fine here.
            values[i] = validator(value)  # type: ignore
        return cast(List[T], values)

    return list_validator
