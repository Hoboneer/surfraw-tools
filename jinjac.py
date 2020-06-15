"""Pre-compile Jinja2 templates for faster runtime execution."""
import os

from jinja2 import FileSystemLoader

from surfraw_tools.common import Context, get_env


def generate(path):
    ctx = Context("jinjac")
    env, *_ = get_env(ctx)
    templates_dir = "surfraw_tools/templates"
    env.loader = FileSystemLoader(templates_dir)
    env.compile_templates(path, zip=None)
