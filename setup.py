# noqa: D100
# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
from distutils import log

from jinja2 import FileSystemLoader

# I hate setuptools.  I hate distutils.  Why must this be so needlessly difficult?!
from setuptools import setup
from setuptools.command.build_py import build_py

from surfraw_tools.common import Context, get_env


def compile_templates(path):
    """Pre-compile Jinja2 templates for faster runtime execution."""
    ctx = Context("jinjac")
    env, *_ = get_env(ctx)
    templates_dir = "surfraw_tools/templates"
    env.loader = FileSystemLoader(templates_dir)
    env.compile_templates(path, zip=None)


class PrecompiledJinja(build_py):
    """Compile Jinja2 templates while building.

    Parsing templates on every call is too slow.
    """

    def run(self):  # noqa: D102
        super().run()
        templates_dir = os.path.join(
            self.build_lib, "surfraw_tools/templates/compiled/"
        )
        # *Nothing* uses `self.announce()` why?????
        log.info(f"compiling jinja templates into {templates_dir}")
        # --dry-run doesn't propagate to build_py if called on build.... WHYYYYYYYY?!
        if not self.dry_run:
            compile_templates(templates_dir)


setup(cmdclass={"build_py": PrecompiledJinja},)
