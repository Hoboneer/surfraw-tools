import os
import re

from setuptools import setup


# The package isn't installed yet, so need to get it by regex.
def get_package_attribute(attr, package):
    with open(os.path.join(package, "__init__.py")) as f:
        results = re.search(
            r"{}\s*=\s*[\"']([^\"']*)[\"']".format(attr), f.read()
        )
    if results is None:
        raise RuntimeError(
            f"Could not find property {attr} in package {package}'s `__init__.py` file."
        )
    return results.group(1)


with open("README.md", "r") as f:
    long_description = f.read()

PACKAGE_NAME = "surfraw_tools"
setup(
    name="surfraw-tools",
    version=get_package_attribute("__version__", PACKAGE_NAME),
    author="Gabriel Lisaca",
    author_email="gabriel.lisaca@gmail.com",
    description="Python tools to generate surfraw scripts",
    keywords="surfraw shell elvis script generate",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Hoboneer/surfraw-elvis-generator/",
    packages=["surfraw_tools"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: System :: Shells",
        "Topic :: Terminals",
    ],
    install_requires=["jinja2"],
    entry_points={"console_scripts": ["mkelvis=surfraw_tools.mkelvis:main"]},
    python_requires=">=3.6",
    include_package_data=True,
    zip_safe=False,
    license="Apache-2.0",
)
