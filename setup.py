import os
from distutils import log

# I hate setuptools.  I hate distutils.  Why must this be so needlessly difficult?!
from setuptools import setup
from setuptools.command.build_py import build_py

import jinjac


class PrecompiledJinja(build_py):
    def run(self):
        super().run()
        templates_dir = os.path.join(
            self.build_lib, "surfraw_tools/templates/compiled/"
        )
        # *Nothing* uses `self.announce()` why?????
        log.info(f"compiling jinja templates into {templates_dir}")
        # --dry-run doesn't propagate to build_py if called on build.... WHYYYYYYYY?!
        if not self.dry_run:
            jinjac.generate(templates_dir)


setup(cmdclass={"build_py": PrecompiledJinja})
