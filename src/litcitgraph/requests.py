import functools
from collections.abc import Iterable, Iterator
from typing import (
    Callable,
    ParamSpec,
    TypeVar,
    cast,
)

from pybliometrics.scopus import AbstractRetrieval, ScopusSearch
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
    ScopusAbstractRetrievalViews,
    ScopusID,
    ScopusSearchIntegrityProperties,
    ScopusSearchViews,
    SourceTitle,
)

T = TypeVar('T')
P = ParamSpec('P')


def query_search_scopus(
    query: str,
    view: ScopusSearchViews = 'COMPLETE',
    integrity_check: bool = True,
) -> tuple[EID, ...]:
    """using advanced Scopus search query to retrieve a tuple of all associated
    EIDs of the given query
    By default the integrity check is enabled which verifies that each retrieved
    document contains an EID to ensure that all entries can be used for further
    processing. This check can be disabled. In this case, please verify the
    consistency of the data on your own if you want to do any postprocessing.

    Parameters
    ----------
    query : str
        Scopus search query which could also be used via the web interface
    view : ScopusSearchViews, optional
        view supported by Scopus, corresponding to the Scopus API documentation,
        by default 'COMPLETE'
    integrity_check : bool, optional
        whether an integrity check regarding the EIDs should be performed or not,
        by default True

    Returns
    -------
    tuple[EID, ...]
        collection of all EIDs which were found in the search query
    """
    integrity_properties: tuple[ScopusSearchIntegrityProperties, ...] = tuple()
    if integrity_check:
        integrity_properties = ('eid',)

    search_result = ScopusSearch(
        query,
        view=view,
        subscriber=True,
        integrity_fields=integrity_properties,
        integrity_action='raise',
    )
    collection_eids = cast(list[EID], search_result.get_eids())

    logger.info('Retrieval successful. Total documents found: %d', len(collection_eids))

    return tuple(collection_eids)


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
                    logger.debug('Document not found. Attempt %d of %d', attempt, num_retries)
            return False, None

        return wrapper_func

    return wrapper


@retry_scopus(num_retries=2)
def get_scopus_abstract_retrieval(
    identifier: str | DocIdentifier,
    id_type: PybliometricsIDTypes,
    iter_depth: int,
    view: ScopusAbstractRetrievalViews = 'FULL',
) -> tuple[bool, PaperInfo | None]:
    """default function to use Scopus' Abstract Retrieval API using Pybliometrics,
    parses data in data structures utilised by litcitgraph for further processing

    Parameters
    ----------
    identifier : str | DocIdentifier
        ID for lookup in Scopus database, can be strings or integers depending on the ID type
    id_type : PybliometricsIDTypes
        used ID type supported by Pybliometrics and Scopus
    iter_depth : int
        current iteration depth during build process of the citation graph
    view : ScopusAbstractRetrievalViews, optional
        view supported by Scopus, corresponding to the Scopus API documentation,
        by default 'FULL'

    Returns
    -------
    tuple[bool, PaperInfo | None]
        indicator for successful operation AND
        `PaperInfo` dataclass if retrieval was successful, `None` otherwise

    Raises
    ------
    e
        _description_
    """
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
        logger.error('An error occurred for %s while retrieving ISSNs.', identifier)

    if title is None:
        logger.warning('%s not containing title.', identifier)
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


def get_scopus_refs(
    papers: frozenset[PaperInfo],
    iter_depth: int,
) -> Iterator[tuple[bool, PaperInfo, PaperInfo | None]]:
    with logging_redirect_tqdm():
        for parent in tqdm(papers, position=0, leave=True):
            if parent.refs is None:
                continue

            for ref in tqdm(parent.refs, position=1, leave=False):
                quota_exceeded, child = get_scopus_abstract_retrieval(
                    identifier=ref.scopus_id,
                    id_type='scopus_id',
                    iter_depth=iter_depth,
                )

                yield quota_exceeded, parent, child
