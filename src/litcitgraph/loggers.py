import logging

from litcitgraph.constants import (
    LOGGING_LEVEL_GRAPH,
    LOGGING_LEVEL_PARSING,
    LOGGING_LEVEL_RANKS,
    LOGGING_LEVEL_REQUESTS,
)

requests = logging.getLogger('litcitgraph.requests')
requests.setLevel(LOGGING_LEVEL_REQUESTS)
parsing = logging.getLogger('litcitgraph.parsing')
parsing.setLevel(LOGGING_LEVEL_PARSING)
graphs = logging.getLogger('litcitgraph.graphs')
graphs.setLevel(LOGGING_LEVEL_GRAPH)
ranks = logging.getLogger('litcitgraph.ranks')
ranks.setLevel(LOGGING_LEVEL_RANKS)
