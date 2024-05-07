from typing import (
    cast,
    Callable,
    TypeVar, 
    ParamSpec,
)
from collections.abc import Iterable, Iterator
import logging
import functools

from pybliometrics.scopus import AbstractRetrieval
from pybliometrics.scopus.exception import Scopus404Error
from tqdm.auto import tqdm

from litcitgraph.types import (
    DocIdentifier,
    PybliometricsIDTypes,
    ScopusID,
    EID,
    DOI,
    PaperInfo,
    Reference,
    PybliometricsReference,
    PybliometricsAuthor,
    PybliometricsISSN,
)
from litcitgraph.parsing import authors_to_str

T = TypeVar('T')
P = ParamSpec('P')

logger = logging.getLogger('litcitgraph.requests')
LOGGING_LEVEL = 'WARNING'
logger.setLevel(LOGGING_LEVEL)

def retry_scopus(
    num_retries: int = 3,
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    def wrapper(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper_func(*args: P.args, **kwargs: P.kwargs) -> T | None:
            for attempt in range(1, (num_retries+1)):
                try:
                    return func(*args, **kwargs)
                except Scopus404Error:
                    logger.info((f"Document not found. Attempt {attempt} of "
                                 f"{num_retries}."))
                    if attempt == num_retries:
                        return None
        return wrapper_func
    return wrapper

@retry_scopus(num_retries=2)
def get_from_scopus(
    identifier: str | DocIdentifier,
    id_type: PybliometricsIDTypes,
    iter_depth: int,
    view: str = 'FULL',
) -> PaperInfo | None:
    
    try:
        retrieval = AbstractRetrieval(
            identifier=identifier, 
            view=view, 
            id_type=id_type,
        )
    except Scopus404Error as error:
        raise error
    
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
    pub_issns = retrieval.issn
    
    if title is None:
        logger.warning(f"{identifier=} not containing title.")
        return None
    
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
    
    return paper_info


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
        else:
            continue
    
    if obtained_refs:
        return frozenset(obtained_refs)
    else:
        return None


def get_refs_from_scopus(
    papers: frozenset[PaperInfo],
    iter_depth: int,
) -> Iterator[tuple[PaperInfo, PaperInfo | None]]:
    
    for parent in tqdm(papers, position=0, leave=True):
        if parent.refs is None:
            continue
        
        for ref in tqdm(parent.refs, position=1, leave=False):
            child = get_from_scopus(
                identifier=ref.scopus_id,
                id_type='scopus_id',
                iter_depth=iter_depth,
            )
            yield parent, child