from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal, NamedTuple, NewType, NotRequired, TypeAlias, TypedDict, cast


class LoggingLevels(enum.IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


"""
LoggingLevels: TypeAlias = Literal[
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL',
]
"""

ScopusID = NewType('ScopusID', int)
DOI = NewType('DOI', str)
EID = NewType('EID', str)
DocIdentifier: TypeAlias = ScopusID | DOI | EID
PybliometricsIDTypes: TypeAlias = Literal[
    'eid',
    'pii',
    'scopus_id',
    'pubmed_id',
    'doi',
]
SourceTitle: TypeAlias = str  # title of publication source (e.g. journal)
ISSN: TypeAlias = str
RankingScore = NewType('RankingScore', float)
NestedIterable: TypeAlias = Iterable['Any | NestedIterable']
RankPropertiesSJR: TypeAlias = Literal[
    'SJR',
    'SJR Quartile',
    'H Index',
    'Total Docs. (3years)',
    'Total Refs.',
    'Total Cites (3years)',
    'Citable Docs. (3years)',
    'Cites / Doc. (2years)',
    'Ref. / Doc.',
]
FuzzyMatches: TypeAlias = list[tuple[SourceTitle, float]]


class PybliometricsAuthor(NamedTuple):
    auid: int
    indexed_name: str
    surname: str
    given_name: str
    affiliation: str


class PybliometricsReference(NamedTuple):
    position: str | None
    id: str | None
    doi: str | None
    title: str | None
    authors: str | None
    authors_auid: str | None
    authors_affiliationid: str | None
    sourcetitle: str | None
    publicationyear: str | None
    coverDate: str | None
    volume: str | None
    issue: str | None
    first: str | None
    last: str | None
    citedbycount: str | None
    type: str | None
    text: str | None
    fulltext: str | None


class PybliometricsISSN(NamedTuple):
    print: ISSN
    electronic: ISSN


@dataclass(frozen=True, kw_only=True, slots=True)
class Reference:
    scopus_id: ScopusID
    doi: str | None

    def __key(self) -> ScopusID:
        return self.scopus_id

    def __hash__(self) -> int:
        return hash(self.__key())


class PaperProperties(TypedDict):
    iter_depth: int
    title: str
    authors: str
    year: int
    scopus_id: ScopusID
    doi: DOI | Literal['']
    eid: EID
    scopus_url: str
    refs: NotRequired[frozenset[Reference] | Literal['']]
    pub_name: SourceTitle | Literal['']
    pub_issn_print: ISSN | Literal['']
    pub_issn_electronic: ISSN | Literal['']
    rank_score: NotRequired[RankingScore | Literal[0]]


@dataclass(frozen=True, kw_only=True, slots=True)
class PaperInfo:
    iter_depth: int
    title: str
    authors: str
    year: int
    scopus_id: ScopusID
    doi: DOI | None
    eid: EID
    scopus_url: str
    refs: frozenset[Reference] | None
    pub_name: SourceTitle | None
    pub_issn_print: ISSN | None
    pub_issn_electronic: ISSN | None

    def __key(self) -> tuple[ScopusID, EID]:
        return (self.scopus_id, self.eid)

    def __hash__(self) -> int:
        return hash(self.__key())

    def graph_properties_as_dict(self) -> PaperProperties:
        prop_dict = cast(PaperProperties, asdict(self))
        _ = prop_dict.pop('refs', None)

        for key, val in prop_dict.items():
            if val is None:
                prop_dict[key] = ''

        return prop_dict
