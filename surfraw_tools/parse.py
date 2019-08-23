import argparse
from functools import wraps


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

            return func(*valid_args)

        return validate_args_wrapper

    return wrapper
