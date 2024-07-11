import copy
import datetime
import pickle
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Self

from networkx import DiGraph

from litcitgraph.loggers import graphs as logger
from litcitgraph.requests import get_scopus_abstract_retrieval, get_scopus_refs
from litcitgraph.types import (
    DocIdentifier,
    PaperInfo,
    PaperProperties,
    PybliometricsIDTypes,
    ScopusID,
)


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
        backup: bool = True,
        backup_interval: int = 1000,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        if isinstance(path_interim, str):
            path_interim = Path(path_interim)
        self._path_interim = path_interim

        self._name: str = name
        self.iter_depth: int = 0
        self.papers_by_iter_depth: dict[int, frozenset[PaperInfo]] = {}
        self.retrievals_total: int = 0
        self.retrievals_failed: int = 0

        self.parent_papers_iter: set[PaperInfo] = set()
        self.child_papers_iter: set[PaperInfo] = set()
        self.iteration_completed: bool = True

        self.backup = backup
        self.backup_interval = backup_interval

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
        suffix: str = '.pkl',
    ) -> Path:
        if isinstance(path, str):
            path = Path(path)
        path = path.with_suffix(suffix)
        return path

    def save_pickle(
        self,
        path: str | Path,
        log: bool = True,
    ) -> None:
        path = self.prep_save(path)
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        if log:
            logger.info(f'Graph successfully saved to {path}.')

    @classmethod
    def load_pickle(
        cls,
        path: str | Path,
    ) -> Self:
        path = cls.prep_save(path)
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save_backup(self) -> None:
        timestamp = datetime.datetime.now(tz=datetime.UTC).strftime(r'%Y%m%d_%H%M%S-%Z')
        backup_name = f'{self._path_interim.stem}_backup_{timestamp}'
        backup_path = self._path_interim.with_name(backup_name)
        path = self.prep_save(backup_path)
        self.save_pickle(path, log=False)

    def transform_graphistry(self) -> Self:
        export_graph = self.deepcopy()
        for node in export_graph.nodes:
            # Graphistry does not properly handle large integers
            export_graph.nodes[node]['scopus_id'] = str(export_graph.nodes[node]['scopus_id'])
            # Graphistry drops attribute with key 'title', so rename to 'paper_title'
            export_graph.nodes[node]['paper_title'] = export_graph.nodes[node]['title']
            _ = export_graph.nodes[node].pop('title', None)

        return export_graph

    def _initialise(
        self,
        ids: Iterable[DocIdentifier],
        id_type: PybliometricsIDTypes,
    ) -> bool:
        """initialise citation graph with data from search query

        Parameters
        ----------
        ids : Iterable[DocIdentifier]
            IDs for lookup in Scopus database
        id_type : PybliometricsIDTypes
            used ID type supported by Pybliometrics and Scopus

        Returns
        -------
        bool
            indicator for successful operation

        Raises
        ------
        error
            any error occurring during retrieval processes
        """
        success: bool = False
        papers_init: set[PaperInfo] = set()

        # id_type: PybliometricsIDTypes = 'doi' if use_doi else 'eid'

        try:
            for identifier in ids:
                # obtain information from Scopus
                quota_exceeded, paper_info = get_scopus_abstract_retrieval(
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
        except KeyboardInterrupt:
            logger.warning('Process interrupted by user.')
            logger.info('Saving current state...')
            self.save_pickle(self.path_interim)
            sys.exit(130)
        except Exception as error:
            logger.error('Unknown exception raised.')
            logger.info('Saving current state...')
            self.save_pickle(self.path_interim)
            raise error
        else:
            success = True
            return success

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

        references = get_scopus_refs(target_papers, target_iter_depth)

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

            if (child not in self.child_papers_iter) and (child.scopus_id not in self.nodes):
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

            if self.backup and (count % self.backup_interval == 0):
                self.save_backup()

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
        """resume started build process of the citation graph

        Parameters
        ----------
        target_iter_depth : int
            iteration depth at which the scraping should be stopped

        Returns
        -------
        bool
            indicator for successful operation

        Raises
        ------
        error
            any error occurring during retrieval processes
        """
        success: bool = False
        try:
            for it in range(self.iter_depth, target_iter_depth):
                logger.info('Starting iteration %d...', (it + 1))
                if self.iteration_completed:
                    success = self._iterate_full()
                else:
                    logger.info(
                        'Iteration %d was partially completed before. Resume...', (it + 1)
                    )
                    success = self._iterate_partial()

                if not success:
                    logger.warning('Iteration %d failed. Aborted.', (it + 1))
                    break
                else:
                    logger.info('Iteration %d successfully completed.', (it + 1))
        except KeyboardInterrupt:
            logger.warning('Process interrupted by user.')
            logger.info('Saving current state...')
            self.save_pickle(self.path_interim)
            sys.exit(130)
        except Exception as error:
            logger.error('Unknown exception raised.')
            logger.info('Saving current state...')
            self.save_pickle(self.path_interim)
            raise error
        else:
            logger.info('Build process successful')
            logger.info('Saving current state...')
            self.save_pickle(self.path_interim)
            logger.info('Current state saved successfully.')
            return success

    def build_from_ids(
        self,
        ids: Iterable[DocIdentifier],
        id_type: PybliometricsIDTypes,
        target_iter_depth: int,
    ) -> None:
        if target_iter_depth < 0:
            raise ValueError('Target depth must be non-negative!')
        elif target_iter_depth == 0:
            logger.warning('Target depth is 0, only initialising with given document IDs.')

        success: bool
        logger.info('Building citation graph...')
        logger.info(
            '...target depth: %d, using ID type: >>%s<<...', target_iter_depth, id_type
        )

        logger.info('Initialising graph with given IDs...')
        success = self._initialise(ids=ids, id_type=id_type)
        if success:
            logger.info('Initialisation completed.')
        else:
            logger.warning('Initialisation failed.')
            return None

        # now build upon initialisation state and resume build process, saving done there
        success = self.resume_build_process(target_iter_depth)
