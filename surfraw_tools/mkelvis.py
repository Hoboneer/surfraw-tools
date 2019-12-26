# Copyright 2019 Gabriel Lisaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sys
from itertools import chain
from os import EX_OK, EX_OSERR, EX_USAGE

from .common import (
    BASE_PARSER,
    VERSION_FORMAT_STRING,
    Context,
    get_env,
    process_args,
)
from .options import EnumOption, ListOption, SpecialOption, SurfrawOption

PROGRAM_NAME = "mkelvis"


# Taken from this stackoverflow answer:
#   https://stackoverflow.com/questions/12791997/how-do-you-do-a-simple-chmod-x-from-within-python/30463972#30463972
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


# FIXME: This is very ugly, please... make it not so bad.
def generate_local_help_output(ctx):
    """Return the 'Local options' part of `sr $elvi -local-help`."""
    # The local options part starts indented by two spaces.
    entries = []

    # Add aliases of options alongside main option, e.g.,
    #   -s=SORT, -sort=SORT
    def get_optheader(opt, prefix=""):
        if opt.metavar is None:
            suffix = ""
        else:
            suffix = f"={opt.metavar}"
        optheader = "  " + ", ".join(
            f"-{prefix}{opt_.name}{suffix}"
            for opt_ in sorted(chain([opt], opt.aliases), key=lambda x: x.name)
        )
        return optheader

    def get_optlines(opt):
        if isinstance(opt, ListOption):
            optlines = [
                get_optheader(opt, prefix="add-"),
                get_optheader(opt, prefix="remove-"),
                get_optheader(opt, prefix="clear-"),
            ]
        else:
            optlines = [get_optheader(opt)]
        return optlines

    # Options that take arguments
    # Depends on subclass definition order.
    types_to_sort_order = {
        type_: i for i, type_ in enumerate(SurfrawOption.variable_options)
    }
    for opt in sorted(
        ctx.variable_options, key=lambda x: types_to_sort_order[x.__class__]
    ):
        lines = get_optlines(opt)
        optheader = lines[-1]

        if isinstance(opt, EnumOption):
            valid_values = opt.values
        elif isinstance(opt, ListOption) and issubclass(opt.type, EnumOption):
            valid_values = opt.valid_enum_values
        else:
            # Won't add any lines because empty list.
            valid_values = []

        # +1 to go past the '='
        offset = optheader.rindex("=") + 1
        prefix = " " * offset
        # Add values of enum aligned with metavar.
        # Won't add any lines if not an enum or enum list.
        lines.extend(f"{prefix}{value}" for value in valid_values)

        entries.append((opt, lines))

    # Aliases to one of the above options, but with an argument
    entries.extend((flag, get_optlines(flag)) for flag in ctx.flags)

    # Nothing else to do.
    if not entries:
        return None

    # Include "  | "
    longest_length = max(
        len(line)
        for line in chain.from_iterable(lines for _, lines in entries)
    )
    for opt, lines in entries:
        for i, line in enumerate(lines):
            # Ensure alignment.
            padding = " " * (longest_length - len(line))
            if i == 0:
                gap = "    "
                suffix = opt.description
            else:
                gap = "  | "
                suffix = ""
            lines[i] = f"{line}{padding}{gap}{suffix}"
        if isinstance(opt, tuple(SurfrawOption.variable_options)):
            prefix = " " * longest_length + "    "
            ns_name = ctx._namespacer(opt.name)
            lines.append(prefix + f"Default: ${ns_name}")
            # TODO: Allow a generic way for options to depend on other variables.
            if isinstance(opt, SpecialOption):
                if opt.name == "results":
                    lines.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_results"
                    )
                elif opt.name == "language":
                    lines.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_lang"
                    )
            else:
                lines.append(prefix + f"Environment: {ns_name}")
    # Flatten entries into a list of strings
    return "\n".join(chain.from_iterable(lines for _, lines in entries))


def main(argv=None):
    """Main program to generate surfraw elvi.

    Exit codes correspond to the distro's `sysexits.h` file, which are the
    exit codes prefixed "EX_".
    """
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate an elvis for surfraw",
        parents=[BASE_PARSER],
    )
    ctx = Context()
    try:
        parser.parse_args(argv, namespace=ctx)
    except Exception as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    ctx._program_name = PROGRAM_NAME

    exit_code = process_args(ctx)
    if exit_code != EX_OK:
        return exit_code

    # Generate the elvis.
    env, template_vars = get_env(ctx)
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
    template_vars["local_help_output"] = generate_local_help_output(ctx)
    elvis_template = env.get_template("elvis.in")
    elvis_program = elvis_template.render(template_vars)

    try:
        with open(ctx.name, "w") as f:
            f.write(elvis_program)
        make_executable(ctx.name)
    except OSError:
        # I'm not sure if this is the correct exit code, and if the two
        # actions above should be separated.
        return EX_OSERR
    return EX_OK
