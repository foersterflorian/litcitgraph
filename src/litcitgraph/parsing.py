import configparser
import csv
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal, overload

from litcitgraph.loggers import parsing as logger
from litcitgraph.types import (
    DOI,
    EID,
    PybliometricsAuthor,
)


def pybliometrics_add_API_keys(
    new_keys: str | Iterable[str],
    cfg_path: str | Path | None = None,
) -> None:
    if isinstance(cfg_path, str):
        cfg_path = Path(cfg_path)

    add_keys: str
    if isinstance(new_keys, Iterable) and not isinstance(new_keys, str):
        add_keys = ', '.join(new_keys)
    elif isinstance(new_keys, str):
        add_keys = new_keys

    # try to find in standard location
    if cfg_path is None:
        cfg_path = Path.home() / '.config/pybliometrics.cfg'

    if not cfg_path.exists():
        raise FileNotFoundError(
            (
                f'Provided config path for Pybliometrics does not exist. '
                f'Path provided: >>{cfg_path}<<'
            )
        )

    config = configparser.ConfigParser()
    config.optionxform = str  # type: ignore
    config.read(cfg_path)
    if 'Authentication' not in config.sections():
        raise KeyError('Authentification section in config file not found')

    api_keys = config['Authentication']['APIKey']
    api_keys = ', '.join((api_keys, add_keys))
    config['Authentication']['APIKey'] = api_keys

    with open(cfg_path, 'w') as file:
        config.write(file)

    logger.info('New API keys successfully added.')


@overload
def read_scopus_ids_from_csv(
    path_to_csv: str | Path,
    use_doi: Literal[True],
    encoding: str = ...,
    batch_size: int | None = ...,
) -> Iterator[DOI]: ...


@overload
def read_scopus_ids_from_csv(
    path_to_csv: str | Path,
    use_doi: Literal[False],
    encoding: str = ...,
    batch_size: int | None = ...,
) -> Iterator[EID]: ...


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
        raise ValueError('Batch size must be greater than 0.')

    with open(path_to_csv, 'r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f)
        for count, row in enumerate(reader):
            yield row[key]

            if batch_size is not None and (count + 1) >= batch_size:
                break

    logger.info(('Reading completed. ' f'Entries in dataset: {count+1}'))


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
    names: list[str] = []
    # build list of indexed names
    for author in authors:
        name = ', '.join(author.indexed_name.split(' '))  # type: ignore
        names.append(name)

    return '; '.join(names)
