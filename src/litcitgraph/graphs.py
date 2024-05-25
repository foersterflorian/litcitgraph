import copy
import logging
import pickle
from collections.abc import Iterator
from pathlib import Path
from typing import Final, Self

from networkx import DiGraph

from litcitgraph.requests import get_from_scopus, get_refs_from_scopus
from litcitgraph.types import (
    DOI,
    EID,
    LoggingLevels,
    PaperInfo,
    PaperProperties,
    PybliometricsIDTypes,
    ScopusID,
)

logger = logging.getLogger('litcitgraph.graphs')
LOGGING_LEVEL: Final[LoggingLevels] = 'INFO'
logger.setLevel(LOGGING_LEVEL)


def add_cit_graph_node(
    graph: DiGraph,
    node: ScopusID,
    node_props: PaperProperties,
) -> None:
    # inplace
    if node not in graph.nodes:
        graph.add_node(node, **node_props)


def add_cit_graph_edge(
    graph: DiGraph,
    parent_node: ScopusID,
    parent_node_props: PaperProperties,
    child_node: ScopusID,
    child_node_props: PaperProperties,
    edge_weight: int | None = None,
) -> None:
    # inplace
    if parent_node not in graph.nodes:
        graph.add_node(parent_node, **parent_node_props)
    if child_node not in graph.nodes:
        graph.add_node(child_node, **child_node_props)

    if not graph.has_edge(parent_node, child_node):
        graph.add_edge(parent_node, child_node)

    if edge_weight is not None:
        # add edge weight
        graph[parent_node][child_node]['weight'] = edge_weight


class CitationGraph(DiGraph):
    def __init__(
        self,
        path_interim: str | Path,
        name: str = 'CitationGraph',
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if isinstance(path_interim, str):
            path_interim = Path(path_interim)
        self._path_interim = path_interim

        self._name: str = name
        self.use_doi: bool
        self.iter_depth: int = 0
        self.papers_by_iter_depth: dict[int, frozenset[PaperInfo]] = {}
        self.retrievals_total: int = 0
        self.retrievals_failed: int = 0

        self.parent_papers_iter: set[PaperInfo] = set()
        self.child_papers_iter: set[PaperInfo] = set()
        self.iteration_completed: bool = True

    def __repr__(self) -> str:
        return (
            f'CitationGraph(name={self.name}, '
            f'iter_depth={self.iter_depth}, '
            f'number of nodes: {len(self.nodes)}, '
            f'number of edges: {len(self.edges)})'
        )

    @property
    def path_interim(self) -> Path:
        return self._path_interim

    @property
    def name(self) -> str:
        return self._name

    def deepcopy(self) -> Self:
        return copy.deepcopy(self)

    def _quota_exceeded(self) -> None:
        logger.warning(
            ('Quota exceeded. Stopping build process. ' 'Save current state to resume later.')
        )
        self.save_pickle(self.path_interim)

    @staticmethod
    def prep_save(
        path: str | Path,
        suffix: str = '.pickle',
    ) -> Path:
        if isinstance(path, str):
            path = Path(path)
        path = path.with_suffix(suffix)
        return path

    def save_pickle(
        self,
        path: str | Path,
    ) -> None:
        path = self.prep_save(path)
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        logger.info(f'Graph successfully saved to {path}.')

    @classmethod
    def load_pickle(
        cls,
        path: str | Path,
    ) -> Self:
        path = cls.prep_save(path)
        with open(path, 'rb') as f:
            return pickle.load(f)

    def transform_graphistry(self) -> Self:
        export_graph = self.deepcopy()
        for node in export_graph.nodes:
            # Graphistry does not properly
            # handle large integer
            export_graph.nodes[node]['scopus_id'] = str(export_graph.nodes[node]['scopus_id'])
            # Graphistry drops attribute with key 'title'
            # so rename to 'paper_title'
            export_graph.nodes[node]['paper_title'] = export_graph.nodes[node]['title']
            _ = export_graph.nodes[node].pop('title', None)

        return export_graph

    def _initialise(
        self,
        ids: Iterator[DOI | EID],
        use_doi: bool,
    ) -> bool:
        """initialise citation graph with data from search query to retain
        papers which do not have any reference data

        Parameters
        ----------
        ids : Iterator[DOI | EID]
            IDs for lookup in Scopus database
        use_doi : bool
            indicator for ID type, if True DOI is used, if False EID is used

        Returns
        -------
        tuple[DiGraph, dict[IterDepth, frozenset[PaperInfo]]]
            initialised citation graph and dictionary with paper
            information by iteration depth
        """
        self.use_doi = use_doi
        papers_init: set[PaperInfo] = set()

        id_type: PybliometricsIDTypes = 'doi' if use_doi else 'eid'

        for identifier in ids:
            # obtain information from Scopus
            quota_exceeded, paper_info = get_from_scopus(
                identifier=identifier,
                id_type=id_type,
                iter_depth=self.iter_depth,
            )
            if quota_exceeded:
                self._quota_exceeded()
                return False

            self.retrievals_total += 1
            if paper_info is None:
                self.retrievals_failed += 1
                continue

            node_id = paper_info.scopus_id  # ScopusID as node identifier
            node_props = paper_info.graph_properties_as_dict()
            add_cit_graph_node(self, node_id, node_props)

            if paper_info not in papers_init:
                # verbose because duplicates should not occur as each
                # paper is unique in the database output
                # only kept to be consistent with the other methods
                papers_init.add(paper_info)

        self.papers_by_iter_depth[self.iter_depth] = frozenset(papers_init)

        return True

    def _iterate_full(self) -> bool:
        target_papers = self.papers_by_iter_depth[self.iter_depth]
        self.parent_papers_iter = set(self.papers_by_iter_depth[self.iter_depth])
        self.child_papers_iter.clear()
        return self._iterate(target_papers)

    def _iterate_partial(self) -> bool:
        target_papers = frozenset(self.parent_papers_iter)
        # parent and child papers saved from previous iteration as property
        return self._iterate(target_papers)

    def _iterate(
        self,
        target_papers: frozenset[PaperInfo],
    ) -> bool:
        self.iteration_completed = False
        target_iter_depth = self.iter_depth + 1
        parent_paper_current: PaperInfo | None = None

        references = get_refs_from_scopus(target_papers, target_iter_depth)

        for count, (quota_exceeded, parent, child) in enumerate(references):
            if quota_exceeded:
                self._quota_exceeded()
                return False

            self.retrievals_total += 1
            if parent_paper_current is None:
                parent_paper_current = parent
            elif parent_paper_current != parent:
                self.parent_papers_iter.remove(parent_paper_current)
                parent_paper_current = parent
            if child is None:
                self.retrievals_failed += 1
                continue

            if child not in self.child_papers_iter and child.scopus_id not in self.nodes:
                # check if paper already in current iteration
                # or prior ones (already added to graph)
                self.child_papers_iter.add(child)

            add_cit_graph_edge(
                graph=self,
                parent_node=parent.scopus_id,
                parent_node_props=parent.graph_properties_as_dict(),
                child_node=child.scopus_id,
                child_node_props=child.graph_properties_as_dict(),
            )
        # in case of interruption would not get called
        self.parent_papers_iter.remove(parent)
        self.iter_depth = target_iter_depth
        self.iteration_completed = True
        self.papers_by_iter_depth[self.iter_depth] = frozenset(self.child_papers_iter)

        return True

    def resume_build_process(
        self,
        target_iter_depth: int,
    ) -> bool:
        for it in range(self.iter_depth, target_iter_depth):
            logger.info(f'Starting iteration {it+1}...')
            if self.iteration_completed:
                success = self._iterate_full()
            else:
                logger.info(
                    (f'Iteration {it+1} was partially ' 'completed before. Resume...')
                )
                success = self._iterate_partial()

            if not success:
                logger.warning(f'Iteration {it+1} failed. Aborted.')
                break
            else:
                logger.info(f'Iteration {it+1} successfully completed.')

        return success

    def build_from_ids(
        self,
        ids: Iterator[DOI | EID],
        use_doi: bool,
        target_iter_depth: int,
    ) -> None:
        if target_iter_depth < 0:
            raise ValueError('Target depth must be non-negative!')
        elif target_iter_depth == 0:
            logger.warning(
                ('Target depth is 0, only initialising with ' 'given document IDs.')
            )

        success: bool
        logger.info('Building citation graph...')
        logger.info((f'...target depth: {target_iter_depth}, ' f'using DOI: {use_doi}...'))

        logger.info('Initialising graph with given IDs...')
        success = self._initialise(ids=ids, use_doi=use_doi)
        if success:
            logger.info('Initialisation completed.')
        else:
            logger.warning('Initialisation failed.')
            return None

        success = self.resume_build_process(target_iter_depth)
        if success:
            logger.info('Building of citation graph completed.')
        else:
            logger.warning('Building of citation graph failed.')
