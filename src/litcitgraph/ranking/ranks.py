from __future__ import annotations
from typing import (
    cast, 
    Final,
)
from pathlib import Path

import pandas as pd
from pandas import DataFrame
from thefuzz import process

from litcitgraph.types import SourceTitle, ISSN, RankProperties, RankingScore
from litcitgraph.errors import TooManyFuzzyMatchesError
from litcitgraph.ranking.common import flatten, extract_issn


# relative to >>test-notebooks<< at first
PATH_TO_RANKING_DATA: Final[Path] = Path('../ranking_data/SJR/')
SOURCE_TYPE: Final[str] = 'journal'
TARGET_SCORE: Final[str] = 'SJR'
SCORE_MULTIPLIER: Final[int] = 1000


def read_sjr_data(
    path_folder: Path,
    target_score: str = TARGET_SCORE,
    source_type: str | None = SOURCE_TYPE,
    num_entries_per_file: int = 20,
) -> DataFrame:
    whitelist_data = pd.DataFrame()
    
    for file in path_folder.glob(r'*.csv'):
        df = pd.read_csv(file, sep=';', encoding='utf_8')
        df = df.loc[df['Type']==source_type]
        df = df.dropna(subset=[target_score])
        # transform title all to lowercase
        df['Title'] = df['Title'].apply(lambda x: x.lower())
        # transform score to integer
        df[target_score] = df[target_score]\
            .apply(lambda x: x.replace(',', '.'))\
            .astype(float)
        df[target_score] = (df[target_score] * SCORE_MULTIPLIER).astype(int)
        df = df.sort_values(target_score, ascending=False)
        subset_data = df.iloc[:num_entries_per_file]
        
        if whitelist_data.empty:
            whitelist_data = df.copy()
        else:
            whitelist_data = pd.concat([whitelist_data, subset_data])

    whitelist_data = whitelist_data.drop_duplicates(subset=['Sourceid'])
    
    return whitelist_data.copy()

def obtain_match_info(
    whitelist_data: DataFrame,
) -> tuple[frozenset[SourceTitle], frozenset[ISSN]]:
    
    # source titles
    relevant_journals = cast(frozenset[SourceTitle],
                             frozenset(whitelist_data['Title'].to_list()))
    # ISSNs
    issns = cast(list[str | list[str]], 
                 whitelist_data['Issn'].astype(str).apply(extract_issn).to_list())
    relevant_issns = cast(frozenset[ISSN],
                          frozenset(flatten(issns)))
    
    return relevant_journals, relevant_issns

def match_ISSN(
    issn: ISSN,
    relevant_issns: frozenset[ISSN],
) -> bool:
    if issn in relevant_issns:
        return True
    else:
        return False

def match_journal_title(
    journal_title: str,
    relevant_journals: frozenset[SourceTitle],
    fuzzy_threshold: float = 94.,
    fuzzy_match_limit: int = 2,
) -> tuple[bool, SourceTitle | None]:
    journal_title = journal_title.lower()
    if journal_title in relevant_journals:
        return True, journal_title
    
    matches = process.extract(journal_title, relevant_journals, limit=fuzzy_match_limit)
    target_journals: list[SourceTitle] = []
    for title, score in matches:
        if score > fuzzy_threshold:
            target_journals.append(title)
    
    if len(target_journals) == 0:
        return False, None
    elif len(target_journals) == 1:
        return True, target_journals[0]
    else:
        raise TooManyFuzzyMatchesError("More than one journal matched")

def match_rank(
    whitelist_data: DataFrame,
    issn: ISSN | None,
    relevant_issns: frozenset[ISSN],
    journal_title: SourceTitle | None,
    relevant_journals: frozenset[SourceTitle],
) -> RankingScore | None:
    if not any((issn, journal_title)):
        raise ValueError("Either ISSN or journal title must be provided")
    
    is_match: bool
    # ** ISSN lookup has priority
    if issn is not None:
        is_match = match_ISSN(issn, relevant_issns)
    if is_match:
        rank_score = lookup_rank(whitelist_data, issn=issn)
        return rank_score
    
    # ** journal title
    if journal_title is not None:
        is_match, journal_title = match_journal_title(journal_title, relevant_journals)
    if is_match:
        rank_score = lookup_rank(whitelist_data, journal_title=journal_title)
        return rank_score
    else:
        return None

def lookup_rank(
    whitelist_data: DataFrame,
    *,
    issn: ISSN | None = None,
    journal_title: SourceTitle | None = None,
    rank_property: RankProperties = 'SJR',
) -> RankingScore:
    # ISSN lookup has priority
    if issn is not None:
        rank_score = cast(int, 
                          whitelist_data.loc[whitelist_data['Issn']==issn, rank_property].iat[0])
        # score was multiplied by SCORE_MULTIPLIER, reverse operation
        return RankingScore(rank_score / SCORE_MULTIPLIER)
    elif journal_title is not None:
        rank_score = cast(int, 
                          whitelist_data.loc[whitelist_data['Title']==journal_title.lower(), rank_property].iat[0])
        # score was multiplied by SCORE_MULTIPLIER, reverse operation
        return RankingScore(rank_score / SCORE_MULTIPLIER)
    else:
        raise ValueError("Either ISSN or journal title must be provided")
