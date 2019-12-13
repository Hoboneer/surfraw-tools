import argparse
import weakref
from collections import defaultdict
from itertools import chain

from .validation import no_validation, validate_bool, validate_enum_value


class AliasTarget:
    def __init__(self):
        super().__init__()
        self.aliases = weakref.WeakSet()

    def add_alias(self, alias):
        self.aliases.add(alias)


class FlagTarget:
    def __init__(self):
        super().__init__()
        # Preferably, flags should be listed in the order that they were
        # defined in the command line.
        self.flags = []

    def add_flag(self, flag):
        self.flags.append(flag)


class FlagOption(AliasTarget):
    def __init__(self, name, target, value):
        super().__init__()
        self.name = name
        self.target = target
        self.value = value


class BoolOption(AliasTarget, FlagTarget):
    def __init__(self, name, default):
        super().__init__()
        self.name = name
        self.default = default


class EnumOption(AliasTarget, FlagTarget):
    def __init__(self, name, default, values):
        super().__init__()
        self.name = name
        self.default = default
        self.values = values


class AnythingOption(AliasTarget, FlagTarget):
    def __init__(self, name, default):
        super().__init__()
        self.name = name
        self.default = default


class AliasOption:
    def __init__(self, name, target, target_type):
        self.name = name
        self.target = target
        self.target_type = target_type


class SpecialOption(AliasTarget, FlagTarget):
    """An option that depends on values of environment variables."""

    def __init__(self, name, default=None):
        super().__init__()
        self.name = name
        if default is None:
            self.default = "$SURFRAW_" + name
        else:
            self.default = default


class MappingOption:
    def __init__(self, variable, parameter):
        self.target = variable
        self.parameter = parameter

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


class CollapseOption:
    def __init__(self, variable, collapses):
        self.target = variable
        self.collapses = collapses

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


class OptionResolutionError(Exception):
    pass


def make_option_resolver(target_type, option_types, error_msg, assign_target):
    def resolve_option(args):
        # `args` is the parsed arguments
        targets = getattr(args, target_type)
        options = list(
            chain.from_iterable(getattr(args, type_) for type_ in option_types)
        )
        for target in targets:
            for option in options:
                if target.target == option.name:
                    if assign_target:
                        target.target = option
                    break
            else:
                raise OptionResolutionError(error_msg.format(target=target))

    return resolve_option


RESOLVERS = []

_VARIABLE_OPTION_TYPES = ("bools", "enums", "anythings", "specials")
VARIABLE_OPTIONS = {
    "iterable_func": lambda args: chain.from_iterable(
        getattr(args, type_) for type_ in _VARIABLE_OPTION_TYPES
    ),
    "strings": _VARIABLE_OPTION_TYPES,
    "types": (BoolOption, EnumOption, AnythingOption, SpecialOption),
}


def _resolver(func):
    RESOLVERS.append(func)


@_resolver
def _resolve_duplicate_variables(args):
    name_counts = defaultdict(int)
    for option in VARIABLE_OPTIONS["iterable_func"](args):
        name_counts[option.name] += 1
        if name_counts[option.name] > 1:
            raise OptionResolutionError(
                f"the variable name '{option.name}' is duplicated"
            )


@_resolver
def _resolve_duplicate_nonvariable_options(args):
    name_counts = defaultdict(int)
    for option in chain(args.flags, args.aliases):
        name_counts[option.name] += 1
        if name_counts[option.name] > 1:
            raise OptionResolutionError(
                f"the non-variable-creating option name '{option.name}' is duplicated"
            )


# Options with non alphabetic characters are impossible
_FORBIDDEN_OPTION_NAMES = {
    "browser",
    "elvi",
    "g",
    "graphical",
    "h",
    "help",
    "lh",
    "p",
    "print",
    "o",
    "new",
    "ns",
    "newscreen",
    "t",
    "text",
    "q",
    "quote",
    "version",
    # Just in case options with hyphens are allowed in the future:
    "bookmark-search-elvis",
    "custom-search",
    "escape-url-args",
    "local-help",
}


@_resolver
def _resolve_forbidden_option_names(args):
    options = chain(
        VARIABLE_OPTIONS["iterable_func"](args), args.flags, args.aliases,
    )
    for option in options:
        if option.name in _FORBIDDEN_OPTION_NAMES:
            raise OptionResolutionError(
                f"option name '{option.name}' is global, which cannot be overriden by elvi"
            )


_inner_resolve_aliases = make_option_resolver(
    "aliases",
    ("flags", *VARIABLE_OPTIONS["strings"]),
    error_msg="alias '{target.name}' does not target any existing option",
    assign_target=True,
)


@_resolver
def _resolve_aliases(args):
    _inner_resolve_aliases(args)
    for alias in args.aliases:
        if not isinstance(alias.target, alias.target_type):
            # Find a matching target
            target_name = alias.target.name
            for opt in chain(
                args.flags, VARIABLE_OPTIONS["iterable_func"](args)
            ):
                if (
                    isinstance(opt, alias.target_type)
                    and opt.name == target_name
                ):
                    alias.target = opt
                    break
            else:
                raise OptionResolutionError(
                    f"alias {alias.name}'s target type does not match the alias target's type: {type(alias.target)}"
                )
        elif alias.target_type == AliasOption:
            raise OptionResolutionError(
                f"alias '{alias.name}' targets another alias, which is forbidden"
            )
        alias.target.add_alias(alias)


# Resolve mappings
_resolver(
    make_option_resolver(
        "mappings",
        VARIABLE_OPTIONS["strings"],
        error_msg="URL parameter '{target.parameter}' does not target any existing variable",
        assign_target=False,
    )
)


# Resolve collapses
_resolver(
    make_option_resolver(
        "collapses",
        VARIABLE_OPTIONS["strings"],
        error_msg="'{target.variable}' is a non-existent variable so it cannot be collapsed",
        assign_target=False,
    )
)


_inner_resolve_flags = make_option_resolver(
    "flags",
    VARIABLE_OPTIONS["strings"],
    error_msg="flag option '{target.name}' does not target any existing yes-no, enum, 'anything', or special option",
    assign_target=True,
)


@_resolver
def _resolve_flags(args):
    _inner_resolve_flags(args)
    flags = args.flags
    try:
        flags.resolve()
    except Exception as e:
        raise OptionResolutionError(str(e)) from None

    def validate_values(opts, validator):
        for flag in opts:
            flag.value = validator(flag.value)

    def validate_specials(specials):
        # Other special types will be handled as they have support added into
        # mkelvis.
        for flag in specials:
            if flag.name == "results":
                try:
                    flag.value = int(flag.value)
                except ValueError:
                    raise argparse.ArgumentTypeError(
                        "value for special 'results' option must be an integer"
                    ) from None
            # The language option needn't be checked here.  There are way too
            # many ISO language codes to match.

    try:
        validate_values(flags.bools, validate_bool)
        validate_values(flags.enums, validate_enum_value)
        validate_values(flags.anythings, no_validation)
        validate_specials(flags.specials)
    except argparse.ArgumentTypeError as e:
        raise OptionResolutionError(str(e)) from None

    # Extra validation
    for enum_flag in flags.enums:
        if enum_flag.value not in enum_flag.target.values:
            raise OptionResolutionError(
                f"enum flag option {enum_flag.name}'s value ({enum_flag.value}) is not contained in its target enum ({enum_flag.target.values})"
            )
