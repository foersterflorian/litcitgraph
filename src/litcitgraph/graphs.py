from collections.abc import Iterable
import logging

from networkx import DiGraph
import networkx as nx
from tqdm import tqdm

from .types import (
    ScopusID,
    ScopusExportIdentifier, 
    PaperProperties,
    PaperInfo,
)
from .requests import get_from_scopus, get_refs_from_scopus

logger = logging.getLogger('scopus_citpgraph.graphs')
LOGGING_LEVEL = 'INFO'
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
    else:
        if edge_weight is not None:
            # update edge weight
            graph[parent_node][child_node]['weight'] += edge_weight

def generate_init_graph(
    ids: Iterable[ScopusExportIdentifier],
    use_doi: bool,
) -> tuple[DiGraph, dict[int, frozenset[PaperInfo]]]:
    """initialise citation graph with data from search query to retain
    papers which do not have any reference data

    Parameters
    ----------
    ids : Iterable[ScopusExportIdentifier]
        IDs for lookup in Scopus database
    use_doi : bool
        indicator for ID type, if True DOI is used, if False EID is used

    Returns
    -------
    tuple[DiGraph, dict[IterDepth, frozenset[PaperInfo]]]
        initialised citation graph and dictionary with paper 
        information by iteration depth
    """
    
    graph = nx.DiGraph()
    paper_infos: set[PaperInfo] = set()
    papers_by_iter_depth: dict[int, frozenset[PaperInfo]] = {}
    
    id_type : str = 'doi' if use_doi else 'eid'
    iter_depth = int(0)
    
    for identifier in tqdm(ids):
        # obtain information from Scopus
        paper_info = get_from_scopus(
            identifier=identifier, 
            id_type=id_type,
            iter_depth=iter_depth,
        )
        
        if paper_info is None:
            continue
        
        node_id = paper_info.scopus_id # ScopusID as node identifier
        node_props = paper_info.graph_properties_as_dict()
        
        add_cit_graph_node(graph, node_id, node_props)
        if paper_info not in paper_infos:
            paper_infos.add(paper_info)
    
    papers_by_iter_depth[iter_depth] = frozenset(paper_infos)
    
    return graph, papers_by_iter_depth


def build_cit_graph(
    graph: DiGraph,
    papers_by_iter_depth: dict[int, frozenset[PaperInfo]],
    iter_depth: int,
) -> tuple[DiGraph, dict[int, frozenset[PaperInfo]]]:
    
    papers = papers_by_iter_depth[iter_depth-1]
    
    papers_iteration: set[PaperInfo] = set()
    references = get_refs_from_scopus(papers, iter_depth)
    
    for parent, child in references:
        if child is None:
            continue
        papers_iteration.add(child)
        add_cit_graph_edge(
            graph=graph, 
            parent_node=parent.scopus_id,
            parent_node_props=parent.graph_properties_as_dict(),
            child_node=child.scopus_id,
            child_node_props=child.graph_properties_as_dict(),
        )
    
    papers_by_iter_depth[iter_depth] = frozenset(papers_iteration)
    
    return graph, papers_by_iter_depth


# ------------------------------------------------------------

def add_refs_by_depth(
    cit_graph: nx.DiGraph,
    corpus: set,
    id_tuples: set,
    map_scopus_to_node_id: dict,
    map_node_id_to_scopus: dict,
    target_iter_depth: int,
) -> tuple[nx.DiGraph, set, dict, dict]:
    
    # global identifier, simple integer
    global node_id_counter
    
    target_corpus = corpus.copy()
    target_id_tuples = id_tuples.copy()
    if target_iter_depth == 0:
        filter_depth = 0
    elif target_iter_depth > 0:
        filter_depth = target_iter_depth - 1
    else:
        raise ValueError(f"Target depth must be non-negative!")
    
    iter_corpus = filter_iter_depth(id_tuples=target_id_tuples, 
                                    target_iter_depth=filter_depth)
    
    for scopus_id in iter_corpus:
        # try using ScopusID
        """
        scopus_id = paper[-2]
        if scopus_id is not None:
            request_id = scopus_id
            id_type = 'scopus_id'
        else:
            #use doi instead; is last entry of tuple
            doi = paper[-1]
            request_id = doi
            id_type = 'doi'
        """
        
        #request_id = scopus_id
        id_type = 'scopus_id'
        
        # REWORK: should not be necessary anymore
        # skip if doi is not provided
        if scopus_id is None or scopus_id == '':
            logger.info("Skipped paper because of missing identifier")
            continue
        
        # node ID
        node_id_parent = map_scopus_to_node_id[scopus_id]
        #print(f'{node_id_parent=} \n ---------------')
        logger.debug(f"-------------- \n {scopus_id=}")
        logger.debug(f"{node_id_parent=}")
        
        
        # obtain references
        try:
            refs = AbstractRetrieval(identifier=scopus_id, view='FULL', id_type=id_type).references
        except Scopus404Error:
            # inforamtion could not be obtained from Scopus
            # continue with next entry
            logger.warning(f'Could not obtain reference information for ScopusID: {scopus_id}')
            continue
        
        # skip empty references
        if refs is None:
            logger.info(f"No references for ID type: {id_type}, ID: {scopus_id}")
            continue
        
        for ref in refs:
            title = ref.title
            #authors = build_author_tuple_for_ref(ref.authors)
            authors = ref.authors
            year = ref.publicationyear
            scopus_id = int(ref.id)
            doi = ref.doi
            logger.debug(f"ScopusID of ref: {scopus_id}, DOI of ref: {doi}")
            # ignore empty ScopusIDs
            if scopus_id is None:
                logger.warning(f"Reference with title: {title}, year: {year} does not contain ScopusID.")
                continue
            #if doi is None:
                #doi = ''
            """
            if not all((title, year)):
                # ignore references which do not contain title or year
                logger.warning(f"Reference with ScopusID {scopus_id} does not contain title or year.")
                #continue
            """
            
            
            entry_tuple = (target_iter_depth, title, authors, year, scopus_id, doi)
            id_tuple = (target_iter_depth, scopus_id)
            
            # check if tuple is already in corpus
            if scopus_id not in target_corpus:
                # not known paper, add to corpus
                target_corpus.add(scopus_id)
                map_scopus_to_node_id[scopus_id] = node_id_counter
                map_node_id_to_scopus[node_id_counter] = scopus_id
                node_id_child = node_id_counter
            else:
                # already known: get node ID for this tuple
                node_id_child = map_scopus_to_node_id[scopus_id]
            
            # add id tuple if not known with this iteration depth
            # other depths not relevant
            if id_tuple not in target_id_tuples:
                target_id_tuples.add(id_tuple)
            
            # add child to graph as node
            # NetworkX: (node ID, node_attribute_dict)
            node_props = transform_entry_tuple_to_dict(entry_tuple=entry_tuple)
            node = (node_id_child, node_props)
            cit_graph.add_nodes_from([node])
            # add edge
            cit_graph.add_edge(node_id_parent, node_id_child)
            
            # set up ID counter
            node_id_counter += 1
            
    return (cit_graph, target_corpus.copy(), target_id_tuples.copy(), 
            map_scopus_to_node_id.copy(), map_node_id_to_scopus.copy())

# function to build graphs with customizable iteration depth
def generate_iter_graph(
    ids: list['Identifier'],
    target_iter_depth: int,
) -> tuple[nx.DiGraph, set, dict, dict]:
    
    # generate init graph with library
    (cit_graph, corpus, id_tuples,
     map_scopus_to_node_id, map_node_id_to_scopus) = generate_init_graph(ids=ids)
    
    # if iteration depth greater than 0
    # sequentially build graph
    if target_iter_depth > 0:
        for iter_depth in range(1, target_iter_depth+1):
            
            (cit_graph, corpus, id_tuples,
             map_scopus_to_node_id, map_node_id_to_scopus) = add_refs_by_depth(
                cit_graph=cit_graph,
                corpus=corpus,
                id_tuples=id_tuples,
                map_scopus_to_node_id=map_scopus_to_node_id,
                map_node_id_to_scopus=map_node_id_to_scopus,
                target_iter_depth=iter_depth,
            )
    elif target_iter_depth < 0:
        raise ValueError(f"Target depth must be non-negative!")
    
    return (cit_graph, corpus.copy(), id_tuples.copy(), 
            map_scopus_to_node_id.copy(), map_node_id_to_scopus.copy())