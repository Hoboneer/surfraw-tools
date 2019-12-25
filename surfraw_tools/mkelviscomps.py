import argparse
from os import EX_OK, EX_OSERR

from .common import BASE_PARSER, VERSION_FORMAT_STRING, get_env, process_args

PROGRAM_NAME = "mkelviscomps"

# TODO: Allow completions with commands of the form `surfraw elvisname`.
#       This is likely to need support in the main surfraw completion script.


def main(argv=None):
    parser = argparse.ArgumentParser(
        PROGRAM_NAME,
        description="generate bash completions for a surfraw elvis",
        parents=[BASE_PARSER],
    )
    args = parser.parse_args(argv)
    args._program_name = PROGRAM_NAME

    exit_code = process_args(args)
    if exit_code != EX_OK:
        return exit_code

    # Generate the bash completion script.
    env, template_vars = get_env(args)
    template_vars["GENERATOR_PROGRAM"] = VERSION_FORMAT_STRING % {
        "prog": PROGRAM_NAME
    }
    comp_template = env.get_template("completion.in")
    completion = comp_template.render(template_vars)

    try:
        with open(f"{args.name}.completion", "w") as f:
            f.write(completion)
    except OSError:
        # I'm not sure if this is the correct exit code, and if the two
        # actions above should be separated.
        return EX_OSERR
    return EX_OK
