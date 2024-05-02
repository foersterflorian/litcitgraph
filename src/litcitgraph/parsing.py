from typing import (
    cast,
    overload,
    Literal,
)
from collections.abc import Iterable
import logging
from pathlib import Path

import pandas as pd
from pandas import Series

from .types import (
    DOI,
    EID,
    ScopusExportIdentifier,
    PybliometricsAuthor,
)

# **logging
logger = logging.getLogger('scopus_citpgraph.parsing')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)


@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: Literal[True],
) -> tuple[tuple[DOI, ...], Literal[True]]:
    ...

@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: Literal[False] = ...,
) -> tuple[tuple[EID, ...], Literal[False]]:
    ...

@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: bool = ...,
) -> tuple[tuple[DOI | EID, ...], bool]:
    ...

def read_id_list_from_scopus(
    path_to_csv, 
    use_doi=False,
):
    data = pd.read_csv(path_to_csv, encoding='UTF-8')
    
    if use_doi:
        key = 'DOI'
    else:
        key = 'EID'
    
    ids = data[key]
    ids = cast(Series, ids.dropna(ignore_index=True)) # type: ignore
    ids = cast(tuple[ScopusExportIdentifier, ...], tuple(ids.to_list()))
    
    total_num_entries = len(data)
    cleaned_num_entries = len(ids)
    nan_entries = total_num_entries - cleaned_num_entries
    logger.info(
        f"Entries in dataset: {total_num_entries}, "
        f"Entries after cleansing: {cleaned_num_entries}, "
        f"empty: {nan_entries}"
    )
    
    return ids, use_doi

def authors_to_str(
    authors: Iterable[PybliometricsAuthor],
) -> str:
    """Generate author string based on author namedtuple from
    Pybliometrics

    Parameters
    ----------
    authors : list[Author]
        list of authors with properties  (AUID, indexed_name, 
        surname, given_name, affiliation)

    Returns
    -------
    str
        concatenation of all authors in the form (Author1; Author2; ...) with
        (Author = Surname, Given Name)
    """
    names: list[str] = list()
    # build list of indexed names
    for author in authors:
        name = ', '.join(author.indexed_name.split(' ')) # type: ignore
        names.append(name)
    
    return '; '.join(names)