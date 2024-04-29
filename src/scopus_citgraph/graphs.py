import typing
from collections.abc import Iterable
import logging

import networkx as nx

from .parsing import ScopusExportIdentifier


logger = logging.getLogger('scopus_citpgraph.graphs')
LOGGING_LEVEL = 'INFO'
logger.setLevel(LOGGING_LEVEL)


def generate_init_graph(
    ids: list[ScopusExportIdentifier],
) -> tuple[nx.DiGraph, set, set, dict, dict]:
    # global identifier, simple integer
    global node_id_counter
    # build known corpus
    corpus: set[int] = set()
    id_tuples: set[tuple[int,int]] = set()
    iter_depth = 0
    # custom ID mapping: using entry tuple as key and map to custom ID
    map_scopus_to_node_id = dict()
    # whole corpus with custom ID
    map_node_id_to_scopus = dict()
    # graph
    cit_graph = nx.DiGraph()
    
    
    # check ID type
    test_id = ids[0]
    if '2-s2.0-' in test_id and '/' not in test_id:
        # EID
        id_type: str = 'eid'
    else:
        # DOI
        id_type: str = 'doi'

    for idx, ident in enumerate(ids):
        
        if (NUM_PAPER_BATCH is not None and 
            idx == NUM_PAPER_BATCH):
            break
        
        # obtain information from Scopus
        paper_info = AbstractRetrieval(identifier=ident, view='FULL', id_type=id_type)
        title = paper_info.title
        authors = build_author_str(paper_info.authors)
        year = paper_info.coverDate.split('-')[0]
        scopus_id = paper_info.identifier
        doi = paper_info.doi
        
        if not all((title, year)):
            logger.warning(f"{entry=} not containing title or year. Skipped.")
            continue
        
        entry_tuple = (iter_depth, title, authors, year, scopus_id, doi)
        id_tuple = (iter_depth, scopus_id)
        
        if scopus_id not in corpus:
            corpus.add(scopus_id)
        else:
            logger.info(f"{scopus_id=} already in known corpus set. Skipped")
            continue
        
        # add id tuple if not known with this iteration depth
        # other depths not relevant
        if id_tuple not in id_tuples:
            id_tuples.add(id_tuple)
        
        map_scopus_to_node_id[scopus_id] = node_id_counter
        map_node_id_to_scopus[node_id_counter] = scopus_id
        
        # NetworkX: (node ID, node_attribute_dict)
        node_props = transform_entry_tuple_to_dict(entry_tuple=entry_tuple)
        node = (node_id_counter, node_props)
        cit_graph.add_nodes_from([node])
        
        node_id_counter += 1
        
    return (cit_graph, corpus.copy(), id_tuples.copy(), 
            map_scopus_to_node_id.copy(), map_node_id_to_scopus.copy())