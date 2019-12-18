import weakref
from collections import deque
from itertools import chain

from .validation import (
    OptionParseError,
    list_of,
    no_validation,
    validate_bool,
    validate_enum_value,
    validate_name,
)


class ListType:
    pass


class AliasTarget:
    def __init__(self):
        super().__init__()
        self.aliases = weakref.WeakSet()

    def add_alias(self, alias):
        self.aliases.add(alias)


class FlagTarget:
    @staticmethod
    def flag_value_validator(_):
        raise NotImplementedError

    def __init__(self):
        super().__init__()
        # Preferably, flags should be listed in the order that they were
        # defined in the command line.
        self.flags = []

    def add_flag(self, flag):
        self.flags.append(flag)

    def resolve_flags(self):
        try:
            for flag in self.flags:
                flag.value = self.__class__.flag_value_validator(flag.value)
        except OptionParseError as e:
            raise OptionResolutionError(str(e)) from None


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


class SurfrawOption:
    creates_variable = False
    typenames = {}

    def __init__(self):
        super().__init__()
        # Depends on `self.name` being defined by a subclass
        if not hasattr(self, "name"):
            raise RuntimeError(
                f"tried to run __init__ method of `{self.__class__.__name__}` but `self.name` was not defined"
            )
        if self.name in _FORBIDDEN_OPTION_NAMES:
            raise ValueError(
                f"option name '{self.name}' is global, which cannot be overriden by elvi"
            )

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        SurfrawOption.typenames[cls.typename] = cls


class Option:
    validators = []
    last_arg_is_unlimited = False

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{name}={var!r}' for name, var in vars(self).items())})"

    @classmethod
    def from_arg(cls, arg):
        parsed_args = cls.parse_args(
            arg,
            validators=cls.validators,
            last_is_unlimited=cls.last_arg_is_unlimited,
        )
        if cls.last_arg_is_unlimited:
            # `rest_args` is the positional arguments of `cls` and corresponds to the validators *before* the last one.
            rest_args = parsed_args[: len(cls.validators) - 1]
            # `normal_arg` is the list of validated args from the last validator.
            normal_arg = parsed_args[len(cls.validators) - 1 :]
            return cls(*rest_args, normal_arg)
        else:
            return cls(*parsed_args)

    @staticmethod
    def parse_args(raw_arg, validators, last_is_unlimited=False):
        args = deque(raw_arg.split(":"))
        valid_args = []

        curr_validators = deque(validators)
        num_required = len(curr_validators)
        group_num = 0
        while curr_validators:
            new_group = False
            curr_validator = curr_validators.popleft()
            # Then we are in an optional group.
            if not callable(curr_validator):
                curr_validators = deque(curr_validator)
                num_required = len(curr_validators)
                try:
                    curr_validator = curr_validators.popleft()
                except IndexError:
                    raise ValueError(
                        "validator groups must not be empty"
                    ) from None
                if not callable(curr_validator):
                    raise TypeError(
                        "optional validator groups must start with at least one callable"
                    )
                group_num += 1
                new_group = True
            try:
                arg = args.popleft()
            except IndexError:
                if new_group:
                    # Not enough args but this is an optional group anyway.
                    break
                else:
                    raise OptionParseError(
                        f"current group {group_num} for '{raw_arg}' needs at least {num_required} colon-delimited parts",
                        subject=raw_arg,
                        subject_type="option argument",
                    )
            else:
                # Raise `OptionParseError` if invalid arg.
                valid_args.append(curr_validator(arg))
        # No more validators.

        # Continue until args exhausted.
        if last_is_unlimited:
            while args:
                # Raise `OptionParseError` if invalid arg.
                valid_args.append(curr_validator(args.popleft()))

        return valid_args


# Concrete option types follow


class FlagOption(Option, AliasTarget, SurfrawOption):
    validators = [validate_name, validate_name, no_validation]

    creates_variable = False
    # This will break backwards-compatibility if 'member' isn't an alias
    typename = "flag"

    def __init__(self, name, target, value):
        self.name = name
        self.target = target
        self.value = value
        super().__init__()


class BoolOption(Option, AliasTarget, FlagTarget, SurfrawOption):
    flag_value_validator = validate_bool
    validators = [validate_name, flag_value_validator]

    creates_variable = True
    typename = "yes-no"

    def __init__(self, name, default):
        self.name = name
        self.default = default
        super().__init__()


class EnumOption(Option, AliasTarget, FlagTarget, SurfrawOption, ListType):
    flag_value_validator = validate_enum_value
    validators = [
        validate_name,
        flag_value_validator,
        list_of(validate_enum_value),
    ]

    creates_variable = True
    typename = "enum"

    def __init__(self, name, default, values):
        self.name = name
        if default not in values:
            raise ValueError(
                f"enum default value '{default}' must be within '{values}'",
                subject=default,
                subject_type="enum default value",
            )
        self.default = default
        self.values = values
        super().__init__()

    def resolve_flags(self):
        for flag in self.flags:
            flag.value = self.__class__.flag_value_validator(flag.value)
            if flag.value not in self.values:
                raise OptionResolutionError(
                    f"enum flag option {flag.name}'s value ({flag.value}) is not contained in its target enum ({self.values})"
                )


class AnythingOption(Option, AliasTarget, FlagTarget, SurfrawOption, ListType):
    flag_value_validator = no_validation
    validators = [validate_name, flag_value_validator]

    creates_variable = True
    typename = "anything"

    def __init__(self, name, default):
        self.name = name
        self.default = default
        super().__init__()


class SpecialOption(Option, AliasTarget, FlagTarget, SurfrawOption):
    """An option that depends on values of environment variables."""

    @staticmethod
    def flag_value_validator(_):
        raise RuntimeError(
            "This method should not have been called directly.  Use `resolve_flags` instead."
        )

    creates_variable = True
    typename = "special"

    # This class is not instantiated normally... maybe prepend name with underscore?
    def __init__(self, name, default=None):
        self.name = name
        if default is None:
            self.default = "$SURFRAW_" + name
        else:
            self.default = default
        super().__init__()

    def resolve_flags(self):
        for flag in self.flags:
            if flag.name == "results":
                try:
                    flag.value = int(flag.value)
                except ValueError:
                    raise OptionResolutionError(
                        "value for special 'results' option must be an integer"
                    ) from None
            # The language option needn't be checked here.  There are way too
            # many ISO language codes to match.


def validate_option_type(option_type):
    # For backward compatibility.
    if option_type == "member":
        option_type = "flag"
    try:
        type_ = SurfrawOption.typenames[option_type]
    except KeyError:
        valid_option_types = ", ".join(sorted(SurfrawOption.typenames))
        raise OptionParseError(
            f"option type '{option_type}' must be one of the following: {valid_option_types}",
            subject=option_type,
            subject_type="option type",
        ) from None
    else:
        return type_


class ListOption(Option, AliasTarget, FlagTarget, SurfrawOption):
    # XXX: I'm not sure if this is needed?
    flag_value_validator = no_validation

    validators = [
        validate_name,
        validate_option_type,
        list_of(no_validation),
        no_validation,
    ]
    last_arg_is_unlimited = True

    typename = "list"

    def __init__(self, name, type_, defaults, spec):
        self.name = name
        self.type = type_
        # They are equivalent.
        if len(defaults) == 1 and defaults[0] == "":
            defaults = []
        self.defaults = defaults
        if not issubclass(self.type, ListType):
            raise TypeError(
                f"element type ('{self.type.__name__}') of list '{self.name}' is not a valid list type"
            )

        self.flag_value_validator = list_of(self.type.flag_value_validator)
        if issubclass(self.type, EnumOption):
            # Ignore unused later values in `spec`.
            unparsed_enum_values, *_ = spec

            try:
                # Don't unnecessarily validate.  Defaults may be empty.
                if len(self.defaults) > 0:
                    self.defaults = self.flag_value_validator(
                        ",".join(self.defaults)
                    )
                self.valid_enum_values = self.flag_value_validator(
                    unparsed_enum_values
                )
            except OptionParseError as e:
                raise ValueError(str(e)) from None

            if not set(self.defaults) <= set(self.valid_enum_values):
                raise ValueError(
                    f"enum list option {self.name}'s defaults ('{self.defaults}') must be a subset of its valid values ('{self.valid_enum_values}')"
                )
        elif issubclass(self.type, AnythingOption):
            # Nothing to check for 'anythings'.
            pass
        super().__init__()

    def resolve_flags(self):
        for flag in self.flags:
            flag.value = self.flag_value_validator(flag.value)
            if issubclass(self.type, EnumOption):
                if not set(flag.value) <= set(self.valid_enum_values):
                    raise OptionResolutionError(
                        f"enum list flag option {flag.name}'s value ('{flag.value}') must be a subset of its target's values ('{self.valid_enum_values}')"
                    )
            # Don't need to check `AnythingOption`.


class AliasOption(Option, SurfrawOption):
    """An alias to another option.

    NOTE: This does *not* check whether the alias points to a valid
    option. It needs to be checked elsewhere since this does not have access to
    the parser.
    """

    validators = [validate_name, validate_name, validate_option_type]

    creates_variable = False
    typename = "alias"

    def __init__(self, name, target, target_type):
        self.name = name
        self.target = target
        if not issubclass(target_type, AliasTarget):
            raise TypeError(
                f"target type ('{target_type.__name__}') of alias '{self.name}' is not a valid alias target"
            )
        else:
            self.target_type = target_type
        super().__init__()


class MappingOption(Option):
    validators = [validate_name, no_validation, [validate_bool]]

    def __init__(self, variable, parameter, url_encode=True):
        self.target = variable
        self.parameter = parameter
        # Already a good value.
        if isinstance(url_encode, bool):
            pass
        elif url_encode == "yes":
            url_encode = True
        else:
            url_encode = False
        self.should_url_encode = url_encode

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


class CollapseOption(Option):
    validators = [validate_name, list_of(no_validation)]
    last_arg_is_unlimited = True

    def __init__(self, variable, collapses):
        self.target = variable
        self.collapses = collapses

    @property
    def variable(self):
        # To allow other code to continue to use this class unchanged
        return self.target


class OptionResolutionError(Exception):
    pass


_VARIABLE_OPTION_TYPES = ("bools", "enums", "anythings", "specials", "lists")
VARIABLE_OPTIONS = {
    "iterable_func": lambda args: chain.from_iterable(
        getattr(args, type_) for type_ in _VARIABLE_OPTION_TYPES
    ),
    "strings": _VARIABLE_OPTION_TYPES,
    "types": (
        BoolOption,
        EnumOption,
        AnythingOption,
        SpecialOption,
        ListOption,
    ),
}


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


VALID_FLAG_TYPES = [
    name
    for name in SurfrawOption.typenames
    if issubclass(SurfrawOption.typenames[name], FlagTarget)
]
VALID_FLAG_TYPES_STR = ", ".join(
    f"'{typename}'" if typename != VALID_FLAG_TYPES[-1] else f"or '{typename}'"
    for i, typename in enumerate(VALID_FLAG_TYPES)
)
RESOLVERS = []


def _resolver(func):
    RESOLVERS.append(func)


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
                    f"alias {alias.name}'s target type does not match the alias target's type: {alias.target.typename}"
                )
        elif alias.target_type == AliasOption:
            # This should be unreachable.
            raise OptionResolutionError(
                f"alias '{alias.name}' targets another alias, which is forbidden; this should never be reached; this is a bug!"
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
# Resolve list mappings
_resolver(
    make_option_resolver(
        "list_mappings",
        ("lists",),
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
    error_msg="flag option '{target.name}' does not target any existing "
    f"{VALID_FLAG_TYPES_STR} option",
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

    try:
        for flag_target in VARIABLE_OPTIONS["iterable_func"](args):
            flag_target.resolve_flags()
    except OptionParseError as e:
        raise OptionResolutionError(str(e)) from None


@_resolver
def _resolve_lists(args):
    lists = args.lists
    try:
        lists.resolve()
    except Exception as e:
        raise OptionResolutionError(str(e)) from None
