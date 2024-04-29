from typing import (
    cast,
    Callable,
    TypeVar, 
    ParamSpec,
)
import typing
import logging
from uuid import uuid4
import functools

from pybliometrics.scopus import AbstractRetrieval
from pybliometrics.scopus.exception import Scopus404Error

from .parsing import (
    ScopusID,
    PaperInfo,
    authors_to_str,
)

# ** typing
T = TypeVar('T')
P = ParamSpec('P')

# **logging
logger = logging.getLogger('scopus_citpgraph.requests')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)

"""
except Scopus404Error:
        logger.warning(f"Scopus404Error: {identifier=} not found.")
        return False, None
"""


def retry_scopus(
    num_retries: int = 3
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

@retry_scopus(num_retries=3)
def get_from_scopus(
    identifier: str,
    id_type: str,
    view: str = 'FULL',
) -> PaperInfo | None:
    
    try:
        retrieval = AbstractRetrieval(
            identifier=identifier, 
            view=view, 
            id_type=id_type
        )
    except Scopus404Error as error:
        raise error
    
    title = retrieval.title
    authors = retrieval.authors
    year = int(retrieval.coverDate.split('-')[0])
    scopus_id = ScopusID(retrieval.identifier)
    eid = retrieval.eid
    doi = retrieval.doi
    scopus_url = retrieval.scopus_link
    
    if title is None:
        logger.warning(f"{identifier=} not containing title.")
        return None
    
    if authors is None:
        authors = ''
    else:
        authors = authors_to_str(authors)
    
    #internal_id = uuid4()
    
    paper_info = PaperInfo(
        title=title,
        authors=authors,
        year=year,
        scopus_id=scopus_id,
        doi=doi,
        eid=eid,
        scopus_url=scopus_url,
    )
    
    return paper_info