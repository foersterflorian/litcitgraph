from __future__ import annotations
from typing import (
    cast, 
    Final,
)
import logging
from pathlib import Path

import pandas as pd
from pandas import DataFrame
from thefuzz import process

from litcitgraph.types import SourceTitle, ISSN, RankProperties, RankingScore
from litcitgraph.graphs import CitationGraph
from litcitgraph.errors import TooManyFuzzyMatchesError
from litcitgraph.ranking.common import flatten, extract_issn


# relative to >>test-notebooks<< at first
PATH_TO_RANKING_DATA: Final[Path] = Path('../ranking_data/SJR/')
SOURCE_TYPE: Final[str] = 'journal'
TARGET_SCORE: Final[str] = 'SJR'
SCORE_MULTIPLIER: Final[int] = 1000

logger = logging.getLogger('litcitgraph.ranking.ranks')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)


def read_ranking_data(
    path_folder: Path,
    target_score: RankProperties = 'SJR',
    source_type: str = 'journal',
    num_entries_per_file: int = 20,
) -> DataFrame:
    ranking_data = pd.DataFrame()
    
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
        
        if ranking_data.empty:
            ranking_data = df.copy()
        else:
            ranking_data = pd.concat([ranking_data, subset_data])

    ranking_data = ranking_data.drop_duplicates(subset=['Sourceid'])
    
    return ranking_data.copy()

def obtain_match_info(
    ranking_data: DataFrame,
) -> tuple[frozenset[ISSN], frozenset[SourceTitle]]:
    # ISSNs
    issns = cast(list[str | list[str]], 
                 ranking_data['Issn'].astype(str).apply(extract_issn).to_list())
    relevant_issns = cast(frozenset[ISSN],
                          frozenset(flatten(issns)))
    # source titles
    relevant_journals = cast(frozenset[SourceTitle],
                             frozenset(ranking_data['Title'].to_list()))
    
    return relevant_issns, relevant_journals


class GraphScorer:
    
    def __init__(
        self,
        path_ranking_data: Path,
        target_score: RankProperties = 'SJR',
        source_type: str = 'journal',
        num_entries_per_file: int = 20,
        fuzzy_threshold: float = 94.,
        fuzzy_match_limit: int = 2,
    ) -> None:
        
        self.ranking_data = read_ranking_data(path_folder=path_ranking_data,
                                              target_score=target_score,
                                              source_type=source_type,
                                              num_entries_per_file=num_entries_per_file)
        
        (self.relevant_issns, 
         self.relevant_journals) = obtain_match_info(self.ranking_data)
        self.fuzzy_threshold = fuzzy_threshold
        self.fuzzy_match_limit = fuzzy_match_limit
    
    def match_journal_title(
        self,
        journal_title: str,
    ) -> tuple[bool, SourceTitle | None]:
        journal_title = journal_title.lower()
        if journal_title in self.relevant_journals:
            return True, journal_title
        
        matches = process.extract(journal_title, self.relevant_journals, limit=self.fuzzy_match_limit)
        target_journals: list[SourceTitle] = []
        for title, score in matches:
            if score > self.fuzzy_threshold:
                target_journals.append(title)
        
        if len(target_journals) == 0:
            return False, None
        elif len(target_journals) == 1:
            return True, target_journals[0]
        else:
            raise TooManyFuzzyMatchesError("More than one journal matched")

    def match_rank(
        self,
        issn: ISSN | None,
        journal_title: SourceTitle | None,
    ) -> RankingScore | None:
        if not any((issn, journal_title)):
            raise ValueError("Either ISSN or journal title must be provided")
        
        is_match: bool
        # ** ISSN lookup has priority
        if issn is not None:
            is_match = issn in self.relevant_issns
        if is_match:
            rank_score = self.lookup_rank(issn=issn)
            return rank_score
        
        # ** journal title
        if journal_title is not None:
            is_match, journal_title = self.match_journal_title(journal_title)
        if is_match:
            rank_score = self.lookup_rank(journal_title=journal_title)
            return rank_score
        else:
            return None

    def lookup_rank(
        self,
        *,
        issn: ISSN | None = None,
        journal_title: SourceTitle | None = None,
        rank_property: RankProperties = 'SJR',
    ) -> RankingScore:
        # ISSN lookup has priority
        if issn is not None:
            rank_score = cast(int, 
                            self.ranking_data
                            .loc[self.ranking_data['Issn']==issn, rank_property]
                            .iat[0])
            # score was multiplied by SCORE_MULTIPLIER, reverse operation
            return RankingScore(rank_score / SCORE_MULTIPLIER)
        elif journal_title is not None:
            rank_score = cast(int, 
                            self.ranking_data
                            .loc[self.ranking_data['Title']==journal_title.lower(), rank_property]
                            .iat[0])
            # score was multiplied by SCORE_MULTIPLIER, reverse operation
            return RankingScore(rank_score / SCORE_MULTIPLIER)
        else:
            raise ValueError("Either ISSN or journal title must be provided")
    
    def score_graph(
        self,
        graph: CitationGraph,
    ) -> CitationGraph:
        # TODO check implementation
        for node in graph.nodes:
            node_props = graph.nodes[node]
            issn = node_props['pub_issn_print']
            journal_title = node_props['pub_name']
            rank_score = self.match_rank(issn=issn, journal_title=journal_title)
            if rank_score is not None:
                node_props['rank_score'] = rank_score
            else:
                logger.warning(f"No rank found for {node}")
        
        return graph