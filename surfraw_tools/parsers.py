import argparse
from functools import wraps

from .options import (
    AliasOption,
    AnythingOption,
    BoolOption,
    CollapseOption,
    EnumOption,
    FlagOption,
    MappingOption,
    MemberOption,
    QueryParameterOption,
)
from .validation import (
    list_of,
    no_validation,
    validate_bool,
    validate_name,
    validate_url_parameter,
)


def insufficient_spec_parts(arg, num_required):
    raise argparse.ArgumentTypeError(
        f"option arg '{arg}' needs at least {num_required} colon-delimited parts"
    )


def parse_args(validators, last_is_unlimited=False):
    """Decorator to validate args of argument spec for generated elvis.

    Raises `argparse.ArgumentTypeError` when invalid, otherwise calls decorated
    function with validated arguments, returning its value.
    """

    def wrapper(func):
        @wraps(func)
        def validate_args_wrapper(raw_arg):
            args = raw_arg.split(":")
            valid_args = []
            for i, valid_or_fail_func in enumerate(validators):
                try:
                    arg = args[i]
                except IndexError:
                    # Raise `argparse.ArgumentTypeError`
                    insufficient_spec_parts(
                        raw_arg, num_required=len(validators)
                    )
                else:
                    # Raise `argparse.ArgumentTypeError` if invalid arg.
                    result = valid_or_fail_func(arg)
                    valid_args.append(result)

            # Continue until args exhausted.
            if last_is_unlimited:
                i += 1
                while i < len(args):
                    # Raise `argparse.ArgumentTypeError` if invalid arg.
                    result = valid_or_fail_func(args[i])
                    valid_args.append(result)
                    i += 1

            option = func(*valid_args)
            option._raw_arg = raw_arg
            return option

        return validate_args_wrapper

    return wrapper


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


@parse_args([validate_name, validate_name, validate_name])
def parse_member_option(name, enum_name, value):
    return MemberOption(name, enum_name, value)


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
    return QueryParameterOption(param)
