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
from os import EX_OK, EX_OSERR

from .common import BASE_PARSER, VERSION_FORMAT_STRING, get_env, process_args

PROGRAM_NAME = "mkelvis"


# Taken from this stackoverflow answer:
#   https://stackoverflow.com/questions/12791997/how-do-you-do-a-simple-chmod-x-from-within-python/30463972#30463972
def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


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

    exit_code = process_args(args)
    if exit_code != EX_OK:
        return exit_code

    # Generate the elvis.
    env, template_vars = get_env(args)
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
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
