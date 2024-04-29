import typing
from typing import (
    cast,
    overload,
    Literal,
    TypeAlias,
    NamedTuple,
    NewType,
)
import logging
from pathlib import Path
from dataclasses import dataclass
from uuid import UUID

import pandas as pd
from pandas import Series


# ** types
#ScopusExportIdentifier: TypeAlias = str | int
ScopusID = NewType('ScopusID', int)
DOI: TypeAlias = str
EID: TypeAlias = str

# **logging
logger = logging.getLogger('scopus_citpgraph.parsing')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)

@dataclass(frozen=True, kw_only=True, slots=True)
class PaperInfo():
    title: str
    authors: str
    year: int
    scopus_id: ScopusID
    doi: str | None
    eid: str
    scopus_url: str
    """
    def __key(self) -> tuple[ScopusID, EID]:
        return (self.scopus_id, self.eid)
    
    def __hash__(self) -> int:
        hash(self.__key())
    """

@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: Literal[True],
) -> tuple[DOI, ...]:
    ...

@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: Literal[False] = ...,
) -> tuple[EID, ...]:
    ...

@overload
def read_id_list_from_scopus(
    path_to_csv: str | Path,
    use_doi: bool = ...,
) -> tuple[DOI | EID, ...]:
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
        f"Entries after cleaning: {cleaned_num_entries}, "
        f"empty: {nan_entries}"
    )
    
    return ids

def authors_to_str(
    authors: list[NamedTuple],
) -> str:
    """Generate author string based on author namedtuple from
    Pybliometrics

    Parameters
    ----------
    authors : list[NamedTuple]
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