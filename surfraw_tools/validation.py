import re


class OptionParseError(Exception):
    def __init__(self, msg, subject, subject_type):
        super().__init__(msg)
        self.subject = subject
        self.subject_type = subject_type


# NAME

# This is purposely not in the full range of shell variable names because I am
# trying to encourage a particular naming convention. That is,
# `SURFRAW_elvisname_onewordvar` is what the script would generate.
_VALID_SURFRAW_VAR_NAME = re.compile("^[a-z]+$")


def validate_name(name):
    if not _VALID_SURFRAW_VAR_NAME.fullmatch(name):
        raise OptionParseError(
            f"name '{name}' is an invalid variable name for an elvis",
            subject=name,
            subject_type="variable name",
        )
    return name


# YES-NO

# TODO: Should the yes-no option take the other forms?
# TRUE_WORDS = {"yes", "on", "1"}
# FALSE_WORDS = {"no", "off", "0"}
_TRUE_WORDS = {"yes"}
_FALSE_WORDS = {"no"}
_BOOL_WORDS = _TRUE_WORDS | _FALSE_WORDS


def validate_bool(bool_):
    if bool_ not in _BOOL_WORDS:
        valid_bools = ", ".join(sorted(_BOOL_WORDS))
        raise OptionParseError(
            f"bool '{bool_}' must be one of the following: {valid_bools}",
            subject=bool_,
            subject_type="bool",
        )
    return bool_


# OPTION TYPES is defined elsewhere to avoid circular imports.

# ENUM VALUES

_VALID_ENUM_VALUE_STR = "^[a-z0-9][a-z0-9_+-]*$"
_VALID_ENUM_VALUE = re.compile(_VALID_ENUM_VALUE_STR)


def validate_enum_value(value):
    if not _VALID_ENUM_VALUE.fullmatch(value):
        raise OptionParseError(
            f"enum value '{value}' must match the regex '{_VALID_ENUM_VALUE_STR}'",
            subject=value,
            subject_type="enum value",
        )
    return value


# MISC.


def no_validation(arg):
    return arg


def list_of(validator):
    def list_validator(arg):
        values = arg.split(",")
        # In case the validators return a different object from its input.
        new_values = []
        for value in values:
            new_values.append(validator(value))
        return new_values

    return list_validator
