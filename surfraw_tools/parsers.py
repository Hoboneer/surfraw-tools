import argparse

from .options import (
    AliasOption,
    AnythingOption,
    BoolOption,
    EnumOption,
    FlagOption,
    MappingOption,
)
from .parse import insufficient_spec_parts, parse_args
from .validation import (
    invalid_name,
    is_valid_name,
    no_validation,
    validate_bool,
    validate_name,
    validate_url_parameter,
)


@parse_args([validate_name, validate_name, validate_bool])
def parse_flag_option(name, target, value):
    """Check a flag option, requiring three colon-delimited parts."""
    return FlagOption(name, target, value)


@parse_args([validate_name, validate_bool])
def parse_bool_option(name, default):
    """Check a yes-no option, requiring two colon-delimited parts."""
    return BoolOption(name, default)


# Third argument is validated inside the function since it needs access to
# other arguments.
@parse_args([validate_name, validate_name, no_validation])
def parse_enum_option(name, default, orig_values):
    """Check an enum option, requiring three colon-delimited parts.

    The default value (part 2) *must* be a value in the third part.
    """
    # Check validity of values.
    values = orig_values.split(",")
    for val in values:
        if not is_valid_name(val):
            invalid_name(val)

    # Ensure `default` is among `values`.
    if default not in values:
        raise argparse.ArgumentTypeError(
            f"default value '{default}' must be within '{orig_values}'"
        )

    return EnumOption(name, default, values)


@parse_args([validate_name, no_validation])
def parse_anything_option(name, default):
    return AnythingOption(name, default)


# NOTE: Aliases are useful since they would result in the target and its
# aliases to be displayed together in the help output.
@parse_args([validate_name, validate_name])
def parse_alias_option(name, target):
    """Make an alias to another option.

    NOTE: This function does *not* check whether the alias points to a valid
    option. It needs to be checked elsewhere since this does not have access to
    the parser.
    """
    return AliasOption(name, target)


@parse_args([validate_name, validate_url_parameter])
def parse_mapping_option(variable, parameter):
    return MappingOption(variable, parameter)


@parse_args([validate_url_parameter])
def parse_query_parameter(param):
    return param
