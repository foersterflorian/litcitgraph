import functools
from collections.abc import Iterable, Iterator
from typing import (
    Callable,
    ParamSpec,
    TypeVar,
    cast,
)

from pybliometrics.scopus import AbstractRetrieval
from pybliometrics.scopus.exception import Scopus404Error, Scopus429Error
from requests.exceptions import ChunkedEncodingError
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from urllib3.exceptions import ProtocolError

from litcitgraph.loggers import requests as logger
from litcitgraph.parsing import authors_to_str
from litcitgraph.types import (
    DOI,
    EID,
    DocIdentifier,
    PaperInfo,
    PybliometricsAuthor,
    PybliometricsIDTypes,
    PybliometricsISSN,
    PybliometricsReference,
    Reference,
    ScopusID,
    SourceTitle,
)

T = TypeVar('T')
P = ParamSpec('P')

# logger = logging.getLogger('litcitgraph.requests')
# LOGGING_LEVEL: Final[LoggingLevels] = 'WARNING'
# logger.setLevel(LOGGING_LEVEL)


def retry_scopus(
    num_retries: int = 3,
) -> Callable[[Callable[P, T]], Callable[P, T | tuple[bool, PaperInfo | None]]]:
    def wrapper(func: Callable[P, T]) -> Callable[P, T | tuple[bool, PaperInfo | None]]:
        @functools.wraps(func)
        def wrapper_func(
            *args: P.args, **kwargs: P.kwargs
        ) -> T | tuple[bool, PaperInfo | None]:
            for attempt in range(1, (num_retries + 1)):
                try:
                    return func(*args, **kwargs)
                except Scopus404Error:
                    logger.info(
                        (f'Document not found. Attempt {attempt} of ' f'{num_retries}.')
                    )
            return False, None

        return wrapper_func

    return wrapper


@retry_scopus(num_retries=2)
def get_from_scopus(
    identifier: str | DocIdentifier,
    id_type: PybliometricsIDTypes,
    iter_depth: int,
    view: str = 'FULL',
) -> tuple[bool, PaperInfo | None]:
    quota_exceeded: bool = False
    try:
        retrieval = AbstractRetrieval(
            identifier=identifier,
            view=view,
            id_type=id_type,
        )
    except Scopus404Error as e:
        # logger.error(f"Error {e}: Document not found for {identifier=}.")
        raise e
    except Scopus429Error:
        logger.error('Quota exceeded.')
        quota_exceeded = True
        return quota_exceeded, None
    except (ChunkedEncodingError, ProtocolError) as error:
        logger.error('Error during request. Continue. Error was: %s', error)
        return quota_exceeded, None

    title = retrieval.title
    authors = retrieval.authors
    year = int(retrieval.coverDate.split('-')[0])
    scopus_id = ScopusID(retrieval.identifier)
    eid = retrieval.eid
    if eid is not None:
        eid = EID(eid)
    doi = retrieval.doi
    if doi is not None:
        doi = DOI(doi)
    scopus_url = retrieval.scopus_link
    references = retrieval.references
    pub_name = retrieval.publicationName
    try:
        pub_issns = retrieval.issn
    except KeyError:
        pub_issns = None
        logger.error(f'An error occurred for {identifier=} while retrieving ISSNs.')

    if title is None:
        logger.warning(f'{identifier=} not containing title.')
        return quota_exceeded, None

    if authors is None:
        authors = ''
    else:
        authors = cast(list[PybliometricsAuthor], authors)
        authors = authors_to_str(authors)

    if references is not None:
        # obtain references in standardised format
        references = cast(list[PybliometricsReference], references)
        obtained_refs = obtain_ref_info(references)
    else:
        obtained_refs = None

    if pub_name is not None:
        pub_name = cast(SourceTitle, pub_name)

    if pub_issns is not None:
        pub_issns = cast(PybliometricsISSN, pub_issns)
        pub_issn_print = pub_issns.print
        pub_issn_electronic = pub_issns.electronic
    else:
        pub_issn_print = None
        pub_issn_electronic = None

    paper_info = PaperInfo(
        iter_depth=iter_depth,
        title=title,
        authors=authors,
        year=year,
        scopus_id=scopus_id,
        doi=doi,
        eid=eid,
        scopus_url=scopus_url,
        refs=obtained_refs,
        pub_name=pub_name,
        pub_issn_print=pub_issn_print,
        pub_issn_electronic=pub_issn_electronic,
    )

    return quota_exceeded, paper_info


def obtain_ref_info(
    references: Iterable[PybliometricsReference],
) -> frozenset[Reference] | None:
    obtained_refs: set[Reference] = set()
    for ref in references:
        if ref.id is not None:
            scopus_id = ScopusID(int(ref.id))
            doi = ref.doi
            obtained_ref = Reference(scopus_id=scopus_id, doi=doi)
            obtained_refs.add(obtained_ref)

    if obtained_refs:
        return frozenset(obtained_refs)
    else:
        return None


def get_refs_from_scopus(
    papers: frozenset[PaperInfo],
    iter_depth: int,
) -> Iterator[tuple[bool, PaperInfo, PaperInfo | None]]:
    with logging_redirect_tqdm():
        for parent in tqdm(papers, position=0, leave=True):
            if parent.refs is None:
                continue

            for ref in tqdm(parent.refs, position=1, leave=False):
                quota_exceeded, child = get_from_scopus(
                    identifier=ref.scopus_id,
                    id_type='scopus_id',
                    iter_depth=iter_depth,
                )

                yield quota_exceeded, parent, child
