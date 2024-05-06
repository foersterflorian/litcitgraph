from typing import (
    cast,
    TypeAlias,
    NamedTuple,
    NewType,
    TypedDict,
    NotRequired,
    Literal,
)
from dataclasses import dataclass, asdict

# ** types
ScopusID = NewType('ScopusID', int)
#DOI: TypeAlias = str
#EID: TypeAlias = str
DOI = NewType('DOI', str)
EID = NewType('EID', str)
DocIdentifier: TypeAlias = ScopusID | DOI | EID
PybliometricsIDTypes = Literal[
    'eid',
    'pii',
    'scopus_id',
    'pubmed_id',
    'doi',
]

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
    scopus_id: NotRequired[ScopusID]
    doi: DOI | Literal['']
    eid: EID
    scopus_url: str
    refs: NotRequired[frozenset[Reference] | Literal['']]
    pub_name: str | Literal['']

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
    pub_name: str | None
    pub_issn: 
    
    def __key(self) -> tuple[ScopusID, EID]:
        return (self.scopus_id, self.eid)
    
    def __hash__(self) -> int:
        return hash(self.__key())
    
    def graph_properties_as_dict(self) -> PaperProperties:
        prop_dict = cast(PaperProperties, asdict(self))
        #_ = prop_dict.pop('scopus_id', None)
        _ = prop_dict.pop('refs', None)
        
        for key, val in prop_dict.items():
            if val is None:
                prop_dict[key] = ''
        
        return prop_dict