import weakref
from collections import defaultdict
from itertools import chain


class AliasTarget:
    def __init__(self):
        self.aliases = weakref.WeakSet()

    def add_alias(self, alias):
        self.aliases.add(alias)


class FlagOption(AliasTarget):
    def __init__(self, name, target, value):
        super().__init__()
        self.name = name
        self.target = target
        self.value = value


class BoolOption(AliasTarget):
    def __init__(self, name, default):
        super().__init__()
        self.name = name
        self.default = default


class EnumOption(AliasTarget):
    def __init__(self, name, default, values):
        super().__init__()
        self.name = name
        self.default = default
        self.values = values


class MemberOption(AliasTarget):
    def __init__(self, name, target, value):
        super().__init__()
        self.name = name
        self.target = target
        self.value = value


class AnythingOption(AliasTarget):
    def __init__(self, name, default):
        super().__init__()
        self.name = name
        self.default = default


class AliasOption:
    def __init__(self, name, target, target_type):
        self.name = name
        self.target = target
        self.target_type = target_type


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


def _resolver(func):
    RESOLVERS.append(func)


@_resolver
def _resolve_duplicate_variables(args):
    options = chain(args.bools, args.enums, args.anythings)
    name_counts = defaultdict(int)
    for option in options:
        name_counts[option.name] += 1
        if name_counts[option.name] > 1:
            raise OptionResolutionError(
                f"the variable name '{option.name}' is duplicated"
            )


# TODO: What to do about naming conflicts?
# Order is important! (Why?)
_inner_resolve_aliases = make_option_resolver(
    "aliases",
    ["flags", "bools", "members", "enums", "anythings"],
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
                args.flags,
                args.bools,
                args.members,
                args.enums,
                args.anythings,
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


# Resolve flags
# TODO: Allow flags to be shorthand for passing the value of any bool or enum
# option.
_resolver(
    make_option_resolver(
        "flags",
        ["bools"],
        error_msg="flag '{target.name}' does not target any existing option",
        assign_target=True,
    )
)


# Resolve mappings
_resolver(
    make_option_resolver(
        "mappings",
        ["bools", "enums", "anythings"],
        error_msg="URL parameter '{target.parameter}' does not target any existing variable",
        assign_target=False,
    )
)


# Resolve collapses
_resolver(
    make_option_resolver(
        "collapses",
        ["bools", "enums", "anythings"],
        error_msg="'{target.variable}' is a non-existent variable so it cannot be collapsed",
        assign_target=False,
    )
)


# Do extra checking
_inner_resolve_members = make_option_resolver(
    "members",
    ["enums"],
    error_msg="enum member option '{target.name}' does not target any existing enum",
    assign_target=True,
)


@_resolver
def _resolve_members(args):
    _inner_resolve_members(args)
    # At this point, all members should be pointing to an existing enum
    for member in args.members:
        if member.value not in member.target.values:
            raise OptionResolutionError(
                f"enum member option {member.name}'s value ({member.value}) is not contained in its target enum ({member.target.values})"
            )
