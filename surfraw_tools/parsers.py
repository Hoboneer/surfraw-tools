import argparse

from .options import (
    AliasOption,
    AnythingOption,
    BoolOption,
    CollapseOption,
    EnumOption,
    FlagOption,
    MappingOption,
)
from .parse import parse_args
from .validation import (
    list_of,
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
@parse_args([validate_name, validate_name, list_of(validate_name)])
def parse_enum_option(name, default, values):
    """Check an enum option, requiring three colon-delimited parts.

    The default value (part 2) *must* be a value in the third part.
    """
    # Ensure `default` is among `values`.
    if default not in values:
        raise argparse.ArgumentTypeError(
            f"default value '{default}' must be within '{values}'"
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


@parse_args([validate_name, list_of(no_validation)], last_is_unlimited=True)
def parse_collapse(variable, *collapses_list):
    return CollapseOption(variable, collapses_list)


@parse_args([validate_url_parameter])
def parse_query_parameter(param):
    return param
