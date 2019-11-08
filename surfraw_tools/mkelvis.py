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
from itertools import chain
from os import EX_OK, EX_OSERR

from .common import BASE_PARSER, VERSION_FORMAT_STRING, get_env, process_args
from .options import (
    AliasOption,
    AnythingOption,
    BoolOption,
    EnumOption,
    FlagOption,
    MemberOption,
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
    base_offset = 2
    entries = []
    longest_length = 0

    def set_longest_length(entry):
        nonlocal longest_length
        longest_entry_line = max(len(line) for line in entry[1:])
        if longest_entry_line > longest_length:
            longest_length = longest_entry_line

    # Options that take arguments
    for opt in chain(args.bools, args.enums, args.anythings):
        # +2 to include the equal
        offset = base_offset + len(opt.name) + 2
        entry = []
        entry.append(opt)
        entry.append(f"  -{opt.name}={opt.name.upper()}")
        if isinstance(opt, EnumOption):
            for value in opt.values:
                entry.append(" " * offset + value)
        set_longest_length(entry)
        entries.append(entry)

    # Aliases to one of the above options, but with an argument
    for opt in chain(args.flags, args.members):
        entry = []
        entry.append(opt)
        entry.append(f"  -{opt.name}")
        set_longest_length(entry)
        entries.append(entry)

    # Aliases to any other non-alias option, which can include an argument
    for alias in args.aliases:
        entry = []
        entry.append(alias)
        if isinstance(alias.target, (BoolOption, EnumOption, AnythingOption)):
            entry.append(f"  -{alias.name}={alias.target.name.upper()}")
        elif isinstance(alias.target, (FlagOption, MemberOption)):
            entry.append(f"  -{alias.name}")
        else:
            raise RuntimeError(
                f"Unhandled alias target: {alias.target} for alias {alias}"
            )
        set_longest_length(entry)
        entries.append(entry)

    # Include "  | "
    base_offset = longest_length + 4
    for entry in entries:
        opt = entry[0]
        for i, record in enumerate(entry):
            # The first element is the option object itself.
            if i == 0:
                continue
            # Ensure alignment.
            if i == 1:
                entry[i] = (
                    record + " " * (longest_length - len(record)) + "    "
                )
                if isinstance(opt, BoolOption):
                    entry[i] += f"A yes-no option for '{opt.name}'"
                elif isinstance(opt, EnumOption):
                    entry[i] += f"An enum option for '{opt.name}'"
                elif isinstance(opt, AnythingOption):
                    entry[i] += f"An unchecked option for '{opt.name}'"
                elif isinstance(opt, (FlagOption, MemberOption)):
                    entry[i] += f"An alias for -{opt.target.name}={opt.value}"
                elif isinstance(opt, AliasOption):
                    if isinstance(
                        opt.target, (BoolOption, EnumOption, AnythingOption)
                    ):
                        entry[
                            i
                        ] += f"An alias for -{opt.target.name}={opt.target.name.upper()}"
                    elif isinstance(opt.target, (FlagOption, MemberOption)):
                        entry[
                            i
                        ] += f"An alias for -{opt.target.target.name}={opt.target.value}"
                    else:
                        entry[i] += "TODO alias option help"
                else:
                    entry[i] += "TODO option help"
            else:
                entry[i] = (
                    record + " " * (longest_length - len(record)) + "  | "
                )
        prefix = " " * longest_length + "    "
        if isinstance(opt, (BoolOption, EnumOption, AnythingOption)):
            ns_name = args._namespacer(opt.name)
            entry.append(prefix + f"Default: ${ns_name}")
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
    args = parser.parse_args(args)
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
