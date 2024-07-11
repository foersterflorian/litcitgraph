from __future__ import annotations

from pathlib import Path
from typing import (
    Final,
    cast,
)

import pandas as pd
from pandas import DataFrame
from thefuzz import process
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from litcitgraph.errors import TooManyFuzzyMatchesError
from litcitgraph.graphs import CitationGraph
from litcitgraph.loggers import ranks as logger
from litcitgraph.ranking.common import flatten
from litcitgraph.types import (
    ISSN,
    FuzzyMatches,
    PaperProperties,
    RankingScore,
    RankPropertiesSJR,
    SourceTitle,
)

# relative to >>test-notebooks<< at first
PATH_TO_RANKING_DATA: Final[Path] = Path('../ranking_data/SJR/')
SOURCE_TYPE: Final[str] = 'journal'
TARGET_SCORE: Final[str] = 'SJR'
SCORE_MULTIPLIER: Final[int] = 1000

# logger = logging.getLogger('litcitgraph.ranking.ranks')
# LOGGING_LEVEL: Final[LoggingLevels] = 'INFO'
# logger.setLevel(LOGGING_LEVEL)


def read_SJR_ranking_data(
    path_folder: Path,
    *,
    target_score: RankPropertiesSJR = 'SJR',
    source_type: str = 'journal',
    num_entries_per_file: int = 20,
) -> DataFrame:
    ranking_data = pd.DataFrame()

    for file in path_folder.glob(r'*.csv'):
        df = pd.read_csv(file, sep=';', encoding='utf_8')
        df = df.loc[df['Type'] == source_type]
        df = df.dropna(subset=[target_score])
        # transform title all to lowercase
        df['Title'] = df['Title'].apply(lambda x: x.lower())
        # transform score to integer
        df[target_score] = df[target_score].apply(lambda x: x.replace(',', '.')).astype(float)
        df[target_score] = (df[target_score] * SCORE_MULTIPLIER).astype(int)
        df = df.sort_values(target_score, ascending=False)
        subset_data = df.iloc[:num_entries_per_file]

        if ranking_data.empty:
            ranking_data = df.copy()
        else:
            ranking_data = pd.concat([ranking_data, subset_data])

    ranking_data = ranking_data.drop_duplicates(subset=['Sourceid']).reset_index(drop=True)

    return ranking_data.copy()


def extract_issn(
    entry: str,
) -> list[ISSN]:
    if ',' in entry:
        return [x.strip() for x in entry.split(',')]
    else:
        return [entry]


def multi_issns_as_columns(
    issns: list[list[ISSN]],
) -> list[tuple[ISSN, ISSN | None, ISSN | None]]:
    issns1: list[ISSN] = []
    issns2: list[ISSN | None] = []
    issns3: list[ISSN | None] = []

    val_issn1: ISSN
    val_issn2: ISSN | None = None
    val_issn3: ISSN | None = None

    for issn_list in issns:
        if len(issn_list) == 1:
            val_issn1 = issn_list[0]
        elif len(issn_list) == 2:
            val_issn1 = issn_list[0]
            val_issn2 = issn_list[1]
        elif len(issn_list) == 3:
            val_issn1 = issn_list[0]
            val_issn2 = issn_list[1]
            val_issn3 = issn_list[2]
        else:
            raise NotImplementedError('More than 3 ISSNs not implemented')

        issns1.append(val_issn1)
        issns2.append(val_issn2)
        issns3.append(val_issn3)

    issns_as_columns = list(zip(issns1, issns2, issns3))

    return issns_as_columns


def obtain_match_info(
    ranking_data: DataFrame,
) -> tuple[DataFrame, frozenset[ISSN], frozenset[SourceTitle]]:
    ranking_data = ranking_data.copy()
    # ISSNs
    issns = cast(
        list[list[ISSN]], ranking_data['Issn'].astype(str).apply(extract_issn).to_list()
    )
    relevant_issns = cast(frozenset[ISSN], frozenset(flatten(issns)))
    # transform ISSNs to columns (to allow lookup for multiple ISSNs)
    issns_as_columns = multi_issns_as_columns(issns)
    issn_df = pd.DataFrame(issns_as_columns, columns=['Issn1', 'Issn2', 'Issn3'])
    ranking_data = pd.concat([ranking_data, issn_df], axis=1)
    # source titles
    relevant_journals = cast(
        frozenset[SourceTitle], frozenset(ranking_data['Title'].to_list())
    )

    return ranking_data, relevant_issns, relevant_journals


class SJRGraphScorer:
    def __init__(
        self,
        folder_ranking_data: Path,
        *,
        target_score: RankPropertiesSJR = 'SJR',
        source_type: str = 'journal',
        num_entries_per_file: int = 20,
        fuzzy_threshold: float = 94.0,
        fuzzy_match_limit: int = 2,
    ) -> None:
        raw_ranking_data = read_SJR_ranking_data(
            path_folder=folder_ranking_data,
            target_score=target_score,
            source_type=source_type,
            num_entries_per_file=num_entries_per_file,
        )

        (self.ranking_data, self.relevant_issns, self.relevant_journals) = obtain_match_info(
            raw_ranking_data
        )
        self.fuzzy_threshold = fuzzy_threshold
        self.fuzzy_match_limit = fuzzy_match_limit

        self.num_matches: int = 0
        self.num_issn_matches: int = 0
        self.num_title_matches: int = 0
        self.num_title_fuzzy_matches: int = 0

        self.scoring_rate: float | None = None

    def match_journal_title(
        self,
        journal_title: SourceTitle,
    ) -> tuple[bool, SourceTitle | None]:
        if journal_title in self.relevant_journals:
            return True, journal_title

        matches = cast(
            FuzzyMatches,
            process.extract(
                journal_title, self.relevant_journals, limit=self.fuzzy_match_limit
            ),
        )
        target_journals: list[SourceTitle] = []
        for title, score in matches:
            if score > self.fuzzy_threshold:
                target_journals.append(title)

        if len(target_journals) == 0:
            return False, None
        elif len(target_journals) == 1:
            self.num_title_fuzzy_matches += 1
            logger.info(f'Fuzzy match found for {journal_title=}: {target_journals[0]}')
            return True, target_journals[0]
        else:
            raise TooManyFuzzyMatchesError('More than one journal matched')

    def match_rank(
        self,
        issn: ISSN | None,
        journal_title: SourceTitle | None = None,
    ) -> RankingScore | None:
        if not any((issn, journal_title)):
            raise ValueError('Either ISSN or journal title must be provided')

        is_match: bool = False
        # ** ISSN lookup has priority
        logger.debug(f'Matching {issn=} {journal_title=}')
        if issn is not None:
            is_match = issn in self.relevant_issns
        if is_match:
            rank_score = self.lookup_rank(issn=issn)
            if rank_score is not None:
                self.num_matches += 1
                self.num_issn_matches += 1
                return rank_score
            else:
                raise RuntimeError(f'{issn=} found in relevant ISSNs, but no rank found.')
        # ** journal title
        if journal_title is not None:
            is_match, journal_title = self.match_journal_title(journal_title)
        if is_match:
            self.num_matches += 1
            self.num_title_matches += 1
            rank_score = self.lookup_rank(journal_title=journal_title)
            return rank_score
        # explicitly None
        return None

    def lookup_rank(
        self,
        *,
        issn: ISSN | None = None,
        journal_title: SourceTitle | None = None,
        rank_property: RankPropertiesSJR = 'SJR',
    ) -> RankingScore | None:
        # ISSN lookup has priority
        if issn is not None:
            rank_score = self.lookup_rank_multi_issn(
                issn=issn,
                rank_property=rank_property,
            )
            if rank_score is not None:
                # score was multiplied by SCORE_MULTIPLIER, reverse operation
                logger.debug(f'Rank score for {issn=} found: {rank_score}')
                return RankingScore(rank_score / SCORE_MULTIPLIER)
            else:
                return None
        elif journal_title is not None:
            rank_score = cast(
                int,
                (
                    self.ranking_data.loc[
                        self.ranking_data['Title'] == journal_title.lower(), rank_property
                    ].iat[0]
                ),
            )
            # score was multiplied by SCORE_MULTIPLIER, reverse operation
            logger.debug(f'Rank score for {journal_title=} found: {rank_score}')
            return RankingScore(rank_score / SCORE_MULTIPLIER)
        else:
            raise ValueError('Either ISSN or journal title must be provided')

    def lookup_rank_multi_issn(
        self,
        issn: ISSN,
        max_num_issns: int = 3,
        rank_property: RankPropertiesSJR = 'SJR',
    ) -> int | None:
        lookup_col: str
        rank_score: int | None = None
        for trial in range(1, max_num_issns + 1):
            lookup_col = f'Issn{trial}'
            try:
                rank_score = cast(
                    int,
                    (
                        self.ranking_data.loc[
                            self.ranking_data[lookup_col] == issn, rank_property
                        ].iat[0]
                    ),
                )
            except IndexError:
                continue
            else:
                break

        return rank_score

    def score_graph(
        self,
        graph: CitationGraph,
    ) -> CitationGraph:
        self.num_title_matches = 0
        self.num_issn_matches = 0
        self.num_title_matches = 0
        self.num_title_fuzzy_matches = 0

        with logging_redirect_tqdm():
            for node in tqdm(graph.nodes):
                node_props = cast(PaperProperties, graph.nodes[node])
                issn_print = node_props['pub_issn_print']
                issn_electronic = node_props['pub_issn_electronic']
                journal_title = node_props['pub_name']
                rank_score = self.match_rank(issn=issn_print, journal_title=journal_title)
                # try electronic ISSN if no match found
                if issn_electronic and rank_score is None:
                    rank_score = self.match_rank(issn=issn_electronic)

                if rank_score is not None:
                    node_props['rank_score'] = rank_score
                else:
                    node_props['rank_score'] = 0
                    logger.info(
                        (
                            f'No rank found for {node=}, {issn_print=}, '
                            f'{issn_electronic=}, {journal_title=}'
                        )
                    )

        num_papers = len(graph.nodes)
        self.scoring_rate = self.num_matches / num_papers

        logger.info('Scoring completed.')
        logger.info(f'Number of matches: {self.num_matches}')
        logger.info(f'Scoring rate: {self.scoring_rate:.2%}')

        return graph
