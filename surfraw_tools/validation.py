import argparse
import re

from .options import (
    AliasOption,
    AnythingOption,
    BoolOption,
    EnumOption,
    FlagOption,
    MemberOption,
)

# NAME

# This is purposely not in the full range of shell variable names because I am
# trying to encourage a particular naming convention. That is,
# `SURFRAW_elvisname_onewordvar` is what the script would generate.
VALID_SURFRAW_VAR_NAME = re.compile("^[a-z]+$")


def is_valid_name(name):
    return VALID_SURFRAW_VAR_NAME.fullmatch(name)


def invalid_name(name):
    raise argparse.ArgumentTypeError(
        f"name '{name}' is an invalid variable name for an elvis"
    )


def validate_name(name):
    if not is_valid_name(name):
        invalid_name(name)
    return name


# URL PARAMETER

VALID_URL_PARAM = re.compile("^[A-Za-z0-9_]+$")


def is_valid_url_parameter(url_param):
    return VALID_URL_PARAM.fullmatch(url_param)


def invalid_url_parameter(url_param):
    raise argparse.ArgumentTypeError(
        f"'{url_param}' is an invalid URL parameter"
    )


def validate_url_parameter(url_param):
    if not is_valid_url_parameter(url_param):
        invalid_url_parameter(url_param)
    return url_param


# YES-NO

# TODO: Should the yes-no option take the other forms?
# TRUE_WORDS = {"yes", "on", "1"}
# FALSE_WORDS = {"no", "off", "0"}
TRUE_WORDS = {"yes"}
FALSE_WORDS = {"no"}
BOOL_WORDS = TRUE_WORDS | FALSE_WORDS


def is_valid_bool(bool_arg):
    return bool_arg in BOOL_WORDS


def invalid_bool(bool_arg):
    valid_bools = ", ".join(sorted(BOOL_WORDS))
    raise argparse.ArgumentTypeError(
        f"bool '{bool_arg}' must be one of the following: {valid_bools}"
    )


def validate_bool(bool_):
    if not is_valid_bool(bool_):
        invalid_bool(bool_)
    return bool_


# OPTION TYPE
OPTION_TYPES = {
    "yes-no": BoolOption,
    "flag": FlagOption,
    "enum": EnumOption,
    "member": MemberOption,
    "anything": AnythingOption,
    "alias": AliasOption,
}


def invalid_option_type(option_type):
    valid_option_types = ", ".join(sorted(OPTION_TYPES))
    raise argparse.ArgumentTypeError(
        f"option type '{option_type}' must be one of the following: {valid_option_types}"
    ) from None


def validate_option_type(option_type):
    try:
        type_ = OPTION_TYPES[option_type]
    except KeyError:
        invalid_option_type(option_type)
    else:
        return type_


# MISC.


def no_validation(_):
    pass


def list_of(validator):
    def list_validator(arg):
        values = arg.split(",")
        for value in values:
            validator(value)
        return values

    return list_validator
