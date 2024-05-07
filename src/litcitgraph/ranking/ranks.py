from __future__ import annotations
from typing import (
    cast, 
    Final,
)
from collections.abc import Iterable, Iterator
from pathlib import Path

import pandas as pd
from pandas import DataFrame
from thefuzz import process

from litcitgraph.types import SourceTitle, ISSN
from litcitgraph.ranking.common import flatten, extract_issn


# relative to >>test-notebooks<< at first
PATH_TO_RANKING_DATA: Final[Path] = Path('../ranking_data/SJR/')
SOURCE_TYPE: Final[str] = 'journal'
TARGET_SCORE: Final[str] = 'SJR'


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
        # transform score to integer
        df[target_score] = df[target_score]\
            .apply(lambda x: x.replace(',', '.'))\
            .astype(float)
        df[target_score] = (df[target_score] * 1000).astype(int)
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