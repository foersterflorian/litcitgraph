from typing import Any
from collections.abc import Iterable, Iterator

from litcitgraph.types import NestedIterable, ISSN

def flatten(
    x: NestedIterable,
) -> Iterator[Any]:
    for entry in x:
        if isinstance(entry, Iterable) and not isinstance(entry, (str, bytes)):
            yield from flatten(entry)
        else:
            yield entry

def extract_issn(
    entry: str,
) -> ISSN | list[ISSN]:
    if ',' in entry:
        return [x.strip() for x in entry.split(',')]
    else:
        return entry