from typing import overload, Literal
from collections.abc import Iterable, Iterator
import logging
from pathlib import Path
import csv

from .types import (
    DOI,
    EID,
    PybliometricsAuthor,
)

# **logging
logger = logging.getLogger('litcitgraph.parsing')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)

@overload
def read_scopus_ids_from_csv(
    path_to_csv: str | Path,
    use_doi: Literal[True],
) -> Iterator[DOI]:
    ...

@overload
def read_scopus_ids_from_csv(
    path_to_csv: str | Path,
    use_doi: Literal[False],
) -> Iterator[EID]:
    ...

def read_scopus_ids_from_csv(
    path_to_csv: str | Path, 
    use_doi: bool,
    encoding: str = 'utf_8_sig',
    batch_size: int | None = None,
) -> Iterator[DOI | EID]:
    key: Literal['DOI', 'EID']
    if use_doi:
        key = 'DOI'
    else:
        key = 'EID'
    
    if batch_size is not None and batch_size < 1:
        raise ValueError("Batch size must be greater than 0.")
    
    with open(path_to_csv, 'r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f)
        for count, row in enumerate(reader):
            if use_doi:
                yield DOI(row[key])
            else:
                yield EID(row[key])
            
            if batch_size is not None and (count+1) >= batch_size:
                break
    
    logger.info(("Reading completed. "
                 f"Entries in dataset: {count+1}"))


"""
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
"""

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