from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="surfraw-tools",
    version="0.1.0",
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
