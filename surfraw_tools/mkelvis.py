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
from .options import (
    VARIABLE_OPTIONS,
    EnumOption,
    ListOption,
    SpecialOption,
)

PROGRAM_NAME = "mkelvis"


# Taken from this stackoverflow answer:
#   https://stackoverflow.com/questions/12791997/how-do-you-do-a-simple-chmod-x-from-within-python/30463972#30463972
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


# FIXME: This is very ugly, please... make it not so bad.
def generate_local_help_output(args):
    """Return the 'Local options' part of `sr $elvi -local-help`."""
    # The local options part starts indented by two spaces.
    entries = []
    longest_length = 0

    def set_longest_length(entry):
        nonlocal longest_length
        longest_entry_line = max(len(line) for line in entry[1:])
        if longest_entry_line > longest_length:
            longest_length = longest_entry_line

    # Add aliases of options alongside main option, e.g.,
    #   -s=SORT, -sort=SORT
    def get_optheader(opt, prefix=""):
        optnames = [opt.name, *(alias.name for alias in opt.aliases)]
        optnames.sort()
        metavar = opt.metavar
        if metavar is None:
            suffix = ""
        else:
            suffix = f"={metavar}"
        optheader = "  " + ", ".join(
            f"-{prefix}{name}{suffix}" for name in optnames
        )
        return optheader

    # Options that take arguments
    for opt in VARIABLE_OPTIONS["iterable_func"](args):
        entry = []
        entry.append(opt)

        if isinstance(opt, ListOption):
            entry.append(get_optheader(opt, prefix="add-"))
            entry.append(get_optheader(opt, prefix="remove-"))
            entry.append(get_optheader(opt, prefix="clear-"))
        else:
            entry.append(get_optheader(opt))
        optheader = entry[-1]

        # +1 to go past the '='
        offset = optheader.rindex("=") + 1
        if isinstance(opt, EnumOption):
            # Add values of enum aligned with metavar
            for value in opt.values:
                entry.append(" " * offset + value)
        elif isinstance(opt, ListOption) and issubclass(opt.type, EnumOption):
            # Add values of enum aligned with metavar
            for value in opt.valid_enum_values:
                entry.append(" " * offset + value)
        set_longest_length(entry)
        entries.append(entry)

    # Aliases to one of the above options, but with an argument
    for opt in args.flags:
        entry = []
        entry.append(opt)

        if isinstance(opt, ListOption):
            entry.append(get_optheader(opt, prefix="add-"))
            entry.append(get_optheader(opt, prefix="remove-"))
            entry.append(get_optheader(opt, prefix="clear-"))
        else:
            entry.append(get_optheader(opt))

        set_longest_length(entry)
        entries.append(entry)

    # Include "  | "
    for entry in entries:
        opt = entry[0]
        for i, record in enumerate(entry):
            # The first element is the option object itself.
            if i == 0:
                continue
            # Ensure alignment.
            gap = " " * (longest_length - len(record))
            if i == 1:
                postgap = "    "
                suffix = opt.description
            else:
                postgap = "  | "
                suffix = ""
            entry[i] = f"{record}{gap}{postgap}{suffix}"
        prefix = " " * longest_length + "    "
        if isinstance(opt, VARIABLE_OPTIONS["types"]):
            ns_name = args._namespacer(opt.name)
            entry.append(prefix + f"Default: ${ns_name}")
            # TODO: Allow a generic way for options to depend on other variables.
            if isinstance(opt, SpecialOption):
                if opt.name == "results":
                    entry.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_results"
                    )
                elif opt.name == "language":
                    entry.append(
                        prefix + f"Environment: {ns_name}, SURFRAW_lang"
                    )
            else:
                entry.append(prefix + f"Environment: {ns_name}")
    # Flatten entries into a list of strings
    return "\n".join(
        line for line in chain.from_iterable(entries) if isinstance(line, str)
    )


def main(args=None):
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
        args = parser.parse_args(args, namespace=ctx)
    except Exception as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    args._program_name = PROGRAM_NAME

    exit_code = process_args(args)
    if exit_code != EX_OK:
        return exit_code

    # Generate the elvis.
    env, template_vars = get_env(args)
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
    template_vars["local_help_output"] = generate_local_help_output(args)
    elvis_template = env.get_template("elvis.in")
    elvis_program = elvis_template.render(template_vars)

    try:
        with open(args.name, "w") as f:
            f.write(elvis_program)
        make_executable(args.name)
    except OSError:
        # I'm not sure if this is the correct exit code, and if the two
        # actions above should be separated.
        return EX_OSERR
    return EX_OK
