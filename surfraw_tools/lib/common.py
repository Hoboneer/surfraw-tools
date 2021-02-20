# SPDX-FileCopyrightText: 2020 Gabriel Lisaca <gabriel.lisaca@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Common functions and classes to generate elvi.

Also includes a parser from `argparse` to base command-line programs on.
"""
from __future__ import annotations

import argparse
import logging
import os
from argparse import _VersionAction
from itertools import chain
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    NewType,
    Sequence,
    Set,
    Type,
    TypeVar,
    ValuesView,
    cast,
)

from surfraw_tools._package import __version__
from surfraw_tools.lib.options import (
    SurfrawAlias,
    SurfrawAnything,
    SurfrawBool,
    SurfrawEnum,
    SurfrawFlag,
    SurfrawList,
    SurfrawOption,
    SurfrawSpecial,
    SurfrawVarOption,
)

if TYPE_CHECKING:
    from typing_extensions import Final

T = TypeVar("T", SurfrawFlag, SurfrawList)


# TODO: Name this better!
class _ChainContainer(Generic[T]):
    types: ClassVar[Sequence[Type[SurfrawOption]]] = []

    def __init__(self) -> None:
        self._items: Dict[str, List[T]] = {
            type_.typename_plural: [] for type_ in self.__class__.types
        }

    def append(self, item: T) -> None:
        try:
            self._items[item.type.typename_plural].append(item)
        except KeyError:
            raise TypeError(
                f"object '{item}' may not go into `{self.__class__.__name__}`s as it not a valid type"
            ) from None

    def __getitem__(self, type_: str) -> List[T]:
        return self._items[type_]

    def __repr__(self) -> str:
        pairs = (
            f"{typename}={elems}" for typename, elems in self._items.items()
        )
        return f"_ChainContainer({', '.join(pairs)})"

    def __iter__(self) -> Iterator[T]:
        return chain.from_iterable(self._items.values())

    # `__bool__` automatically defined.  True if non-zero length.
    def __len__(self) -> int:
        return sum(len(types_) for types_ in self._items.values())


class _FlagContainer(_ChainContainer[SurfrawFlag]):
    types = tuple(SurfrawVarOption.typenames.values())


class _ListContainer(_ChainContainer[SurfrawList]):
    types = [SurfrawEnum, SurfrawAnything]


class _SurfrawOptionContainer(argparse.Namespace):
    def __init__(self) -> None:
        self._seen_variable_names: Set[str] = set()
        self._seen_nonvariable_names: Set[str] = set()

        # Options that create variables.
        self.bools: List[SurfrawBool] = []
        self.enums: List[SurfrawEnum] = []
        self.anythings: List[SurfrawAnything] = []
        self.specials: List[SurfrawSpecial] = []
        self.lists = _ListContainer()
        self._varopts = {
            "bools": self.bools,
            "enums": self.enums,
            "anythings": self.anythings,
            "specials": self.specials,
            "lists": self.lists,
        }

        self.aliases: List[SurfrawAlias] = []
        self.flags = _FlagContainer()
        self._nonvaropts = {
            "aliases": self.aliases,
            "flags": self.flags,
        }

    def append(self, option: SurfrawOption) -> None:
        # Keep track of variable names.
        if isinstance(option, SurfrawVarOption):
            if option.name in self._seen_variable_names:
                raise ValueError(
                    f"the variable name '{option.name}' is duplicated"
                )
            self._seen_variable_names.add(option.name)
            self._varopts[option.typename_plural].append(option)  # type: ignore
        else:
            if option.name in self._seen_nonvariable_names:
                raise ValueError(
                    f"the non-variable-creating option name '{option.name}' is duplicated"
                )
            self._seen_nonvariable_names.add(option.name)
            self._nonvaropts[option.typename_plural].append(option)  # type: ignore

    @property
    def variable_options(self) -> Iterable[SurfrawVarOption]:
        return chain.from_iterable(
            cast(
                ValuesView[Iterable[SurfrawVarOption]], self._varopts.values()
            )
        )

    @property
    def nonvariable_options(self) -> Iterable[SurfrawOption]:
        return chain.from_iterable(
            cast(
                ValuesView[Iterable[SurfrawOption]], self._nonvaropts.values()
            )
        )


_ElvisName = NewType("_ElvisName", str)


def parse_elvis_name(name: str) -> _ElvisName:
    dirs, _ = os.path.split(name)
    if dirs:
        raise argparse.ArgumentTypeError("elvis names may not be paths")
    return _ElvisName(name)


# Make sure that the resultant string is a grammatically-correct list.
_VALID_FLAG_TYPES_STR: Final = ", ".join(
    f"'{typename}'"
    if i != len(SurfrawVarOption.typenames) - 1
    else f"or '{typename}'"
    for i, typename in enumerate(SurfrawVarOption.typenames)
)


BASE_PARSER: Final = argparse.ArgumentParser(add_help=False)
_VERSION_FORMAT_ACTION: Final = cast(
    _VersionAction,
    BASE_PARSER.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (surfraw-tools) {__version__}",
    ),
)
VERSION_FORMAT_STRING: Final = _VERSION_FORMAT_ACTION.version


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("{name}: {message}", style="{"))

    logger.addHandler(handler)
    return logger
