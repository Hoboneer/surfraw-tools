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

from __future__ import annotations

import argparse
import os
import sys
from itertools import chain
from os import EX_OK, EX_OSERR, EX_USAGE
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from .common import (
    BASE_PARSER,
    VERSION_FORMAT_STRING,
    Context,
    get_env,
    process_args,
)
from .options import (
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
)

if TYPE_CHECKING:
    from typing_extensions import Final

PROGRAM_NAME: Final = "mkelvis"


def get_optheader(
    opt: SurfrawOption, prefix: str = "", force_no_metavar: bool = False
) -> str:
    """Return representation of `opt` in `-local-help`.

    These are in sorted order.

    Example:
      -s=SORT, -sort=SORT"""

    if opt.metavar is None or force_no_metavar:
        suffix = ""
    else:
        suffix = f"={opt.metavar}"
    optheader = "  " + ", ".join(
        f"-{prefix}{opt_.name}{suffix}"
        for opt_ in sorted(chain([opt], opt.aliases), key=lambda x: x.name)
    )
    return optheader


def get_optlines(
    opt: SurfrawOption, target: Optional[SurfrawOption] = None
) -> List[str]:
    if target is None:
        target = opt
    if isinstance(target, SurfrawList):
        optlines = []
        optlines.append(get_optheader(opt, prefix="add-"))
        if not isinstance(opt, SurfrawFlag):
            optlines.append(
                get_optheader(opt, prefix="clear-", force_no_metavar=True)
            )
        optlines.append(get_optheader(opt, prefix="remove-"))
    else:
        optlines = [get_optheader(opt)]
    return optlines


# FIXME: This is very ugly, please... make it not so bad.
def generate_local_help_output(
    ctx: Context, namespacer: Callable[[str], str]
) -> str:
    """Return the 'Local options' part of `sr $elvi -local-help`."""
    # The local options part starts indented by two spaces.
    entries: List[Tuple[SurfrawOption, List[str]]] = []

    # Options that take arguments
    # Depends on subclass definition order.
    types_to_sort_order = {
        type_: i for i, type_ in enumerate(SurfrawOption.variable_options)
    }
    for opt in sorted(
        ctx.variable_options, key=lambda x: types_to_sort_order[x.__class__]
    ):
        lines = get_optlines(opt)

        # Add values of enum aligned with last metavar.
        if isinstance(opt, SurfrawEnum) or (
            isinstance(opt, SurfrawList) and issubclass(opt.type, SurfrawEnum)
        ):
            optheader = lines[-1]
            # +1 to go past the '='
            offset = optheader.rindex("=") + 1
            prefix = " " * offset
            lines.extend(f"{prefix}{value}" for value in opt.values)

        entries.append((opt, lines))

    # Aliases to one of the above options, but with an argument
    entries.extend(
        (flag, get_optlines(flag, target=flag.target))
        for flag in ctx.options.flags
    )

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
            ns_name = namespacer(opt.name)
            lines.append(prefix + f"Default: ${ns_name}")
            # TODO: Allow a generic way for options to depend on other variables.
            if isinstance(opt, SurfrawSpecial):
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
    return "\n".join(chain.from_iterable(lines for _, lines in entries))


def main(argv: Optional[List[str]] = None) -> int:
    """Main program to generate surfraw elvi.

    Exit codes correspond to the distro's `sysexits.h` file, which are the
    exit codes prefixed "EX_".
    """
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate an elvis for surfraw",
        parents=[BASE_PARSER],
    )
    ctx = Context(PROGRAM_NAME)
    try:
        parser.parse_args(argv, namespace=ctx)
    except Exception as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_USAGE

    exit_code = process_args(ctx)
    if exit_code != EX_OK:
        return exit_code

    # Generate the elvis.
    env, template_vars, namespacer = get_env(ctx)
    assert (
        VERSION_FORMAT_STRING is not None
    ), "VERSION_FORMAT_STRING should be defined"
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
    if template_vars["any_options_defined"]:
        template_vars["local_help_output"] = generate_local_help_output(
            ctx, namespacer
        )

    # Atomically write output file.
    try:
        with NamedTemporaryFile(mode="w", delete=False, dir=os.getcwd()) as f:
            env.get_template("elvis.in").stream(template_vars).dump(f)
            f.flush()
            fd = f.fileno()
            os.fsync(fd)
            os.fchmod(fd, 0o755)
            os.rename(f.name, ctx.name)
    except OSError as e:
        print(f"{PROGRAM_NAME}: {e}", file=sys.stderr)
        return EX_OSERR
    return EX_OK
