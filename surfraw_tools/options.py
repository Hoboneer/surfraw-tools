from collections import namedtuple
from itertools import chain


class FlagOption:
    def __init__(self, name, target, value):
        self.name = name
        self.target = target
        self.value = value


BoolOption = namedtuple("BoolOption", ["name", "default"])
EnumOption = namedtuple("EnumOption", ["name", "default", "values"])
AnythingOption = namedtuple("AnythingOption", ["name", "default"])


class AliasOption:
    def __init__(self, name, target):
        self.name = name
        self.target = target


MappingOption = namedtuple("MappingOption", ["variable", "parameter"])
CollapseOption = namedtuple("CollapseOption", ["variable", "collapses"])


class OptionResolutionError(Exception):
    pass


def resolve_aliases(args):
    # TODO: What to do about naming conflicts?
    # Order is important! (Why?)
    options = [*chain(args.flags, args.bools, args.enums, args.anythings)]
    for alias in args.aliases:
        for option in options:
            if alias.target == option.name:
                alias.target = option
                break
        else:
            raise OptionResolutionError(
                f"alias '{alias.name}' does not target any existing option"
            )


def resolve_flags(args):
    # TODO: Allow flags to be shorthand for passing the value of any bool or
    # enum option.
    options = args.bools
    for flag in args.flags:
        for option in options:
            if flag.target == option.name:
                flag.target = option
                break
        else:
            raise OptionResolutionError(
                f"flag '{flag.name}' does not target any existing option"
            )


def resolve_mappings(args):
    options = list(chain(args.bools, args.enums, args.anythings))
    for mapping in args.mappings:
        for option in options:
            if mapping.variable == option.name:
                # Mappings don't get modified.
                break
        else:
            raise OptionResolutionError(
                f"URL parameter '{mapping.parameter}' does not target any existing variable"
            )


def resolve_collapses(args):
    options = list(chain(args.bools, args.enums, args.anythings))
    for collapse in args.collapses:
        for option in options:
            if collapse.variable == option.name:
                break
        else:
            raise OptionResolutionError(
                f"'{collapse.variable}' is a non-existent variable so it cannot be collapsed"
            )
