from itertools import chain


class FlagOption:
    def __init__(self, name, target, value):
        self.name = name
        self.target = target
        self.value = value


class BoolOption:
    def __init__(self, name, default):
        self.name = name
        self.default = default


class EnumOption:
    def __init__(self, name, default, values):
        self.name = name
        self.default = default
        self.values = values


class MemberOption:
    def __init__(self, name, target, value):
        self.name = name
        self.target = target
        self.value = value


class AnythingOption:
    def __init__(self, name, default):
        self.name = name
        self.default = default


class AliasOption:
    def __init__(self, name, target):
        self.name = name
        self.target = target


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


# TODO: What to do about naming conflicts?
# Order is important! (Why?)
resolve_aliases = make_option_resolver(
    "aliases",
    ["flags", "bools", "enums", "anythings"],
    error_msg="alias '{target.name}' does not target any existing option",
    assign_target=True,
)


# TODO: Allow flags to be shorthand for passing the value of any bool or enum
# option.
resolve_flags = make_option_resolver(
    "flags",
    ["bools"],
    error_msg="flag '{target.name}' does not target any existing option",
    assign_target=True,
)


resolve_mappings = make_option_resolver(
    "mappings",
    ["bools", "enums", "anythings"],
    error_msg="URL parameter '{target.parameter}' does not target any existing variable",
    assign_target=False,
)


resolve_collapses = make_option_resolver(
    "collapses",
    ["bools", "enums", "anythings"],
    error_msg="'{target.variable}' is a non-existent variable so it cannot be collapsed",
    assign_target=False,
)


# Do extra checking
_inner_resolve_members = make_option_resolver(
    "members",
    ["enums"],
    error_msg="enum member option '{target.name}' does not target any existing enum",
    assign_target=True,
)


def resolve_members(args):
    _inner_resolve_members(args)
    # At this point, all members should be pointing to an existing enum
    for member in args.members:
        if member.value not in member.target.values:
            raise OptionResolutionError(
                f"enum member option {member.name}'s value ({member.value}) is not contained in its target enum ({member.target.values})"
            )
