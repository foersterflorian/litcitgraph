from typing import Any
from collections.abc import Iterable, Iterator

from litcitgraph.types import NestedIterable

def flatten(
    x: NestedIterable,
) -> Iterator[Any]:
    for entry in x:
        if isinstance(entry, Iterable) and not isinstance(entry, (str, bytes)):
            yield from flatten(entry)
        else:
            yield entry
