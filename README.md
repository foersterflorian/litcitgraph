[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

# LitCitGraph

This library automatically builds literature citation graphs based on a given batch obtained from a search query in scientific databases. The iteration depth is customisable.

## Supported Databases

Current only **Scopus** supported.

## Important Notice

This library uses API requests. Therefore it is required to provide a valid API key, which has to acquired from the corresponding database provider, in this case Scopus. In order to successfully build a citation graph the references of each paper have to be obtained. This references are then used to gather their references in an iterative procedure.

To obtain these references in **Scopus** you have to use the *FULL view* according to the API documentation. The availability of this view depends on the subscription model with which you applied for your API key. So if your underlying subscription does not allow to use the *FULL view* there is unfortunately no way to build up the citation graph and use this library.

## Getting Started

### Pybliometrics

This package uses [pybliometrics](https://github.com/pybliometrics-dev/pybliometrics) as dependency for the interaction with the Scopus API. When you use `pybliometrics` for the first time you are prompted to provide a valid API key, which is then stored in a user configuration file. More on this can be found in the [corresponding section of the documentation](https://pybliometrics.readthedocs.io/en/stable/configuration.html).

### Text-based Search

The text-based search utilises a search query exported directly from Scopus. Therefore you can simply build your desired search query string and search through Scopus as you would normally do. To export the found results mark them all via the drop-drown menu `All` next to the check box and choose `Select all`. Then, click on `Export` and choose `CSV` as file format. A pop-up windows will appear, in which you can select the properties to be exported. We only need `EID` and `DOI` as unique identifiers. The other properties could be obtained through the corresponding request at a later stage. Save the exported CSV file in a location you have access to without problems. A path relative to your script is recommended.

Now we are able to build our first citation graph.

```python
# base class, always needed
from litcitgraph.graphs import CitationGraph
# helper function to read exported CSV data
from litcitgraph.parsing import read_scopus_ids_from_csv
```

We always need an additional saving path, where our citation graph can be saved to in case of any known potential error, e.g., the quota of your API key is exceeded. All paths can be either a `string` or a `Path` object from Python's standard library `pathlib`. In this example we use a standard `Path` objects.

Additionally, the path to the exported Scopus data must be provided.

```python
from pathlib import Path

path_to_data = Path('./scopus_data.csv')
saving_path = Path('./inter_save.pkl')
```

> [!CAUTION]
> The citation graph object is saved as `Pickle` file for convenience. Please be advised that pickled objects are not safe and can contain malicious code. Please only load pickled files which were created by your own. [See the official documentation for more information](https://docs.python.org/3.11//library/pickle.html).

Now we can start the build process by providing the necessary data input. We also need to provide information how many iteration levels we want to gather and whether we want to use the `DOI` or not. It is recommended not to use `DOI` and opt for `EID` as identifier. `EID` often provides more robust search experience since `DOI` information is sometimes outdated or not available on Scopus.

```python
id_data = read_scopus_ids_from_csv(path_to_data, use_doi=False, batch_size=None)
cit_graph = CitationGraph(saving_path)
cit_graph.build_from_ids(ids=id_data, use_doi=False, target_iter_depth=1)
```

You can decide to only process a given batch size of the exported data with the `batch_size` parameter of the `read_scopus_from_csv` function. If this parameter is `None` all entries are processed.

Now the citation graph is initialised with the given entries of the exported data. After that the build process for the first iteration starts since the `target_iter_depth` was set to `1`. You can also directly set a larger iteration depth. Depending on the size of the initial dataset and the reference count in each document you might run into quota limits.

### Query-based Search

Based on `pybliometrics` it is also possible to retrieve search results by providing a query string equivalent to the standard Scopus web search. It is planned to leverage this feature to seamlessly interact with Scopus without the need of manual data exports and file parsing. This feature is not yet implemented.

## Quota

Depending of the API key and the underlying licensing model there are different quota limits for certain retrieval actions regarding the Scopus API. If the quota is exceeded and the build process not successfully finished it is automatically interrupted and a copy of the current graph is saved to the path with which the citation graph instance was initialised. The build process can be resumed if the quota limit was reset for the given API keys.

## Resume Build Process after Error

If an expectable error occurred during the build process you are able to load the previous state and continue this process where it stopped. Assuming we ran into quota limits while performing this tutorial and our quota was reset, we can resume as follows:

```python
from pathlib import Path

from litcitgraph.graphs import CitationGraph

saving_path = Path('./inter_save.pkl')
cit_graph = CitationGraph.load_pickle(saving_path)
cit_graph.resume_build_process(target_iter_depth=2)
```

We can directly load the citation graph as it was saved to our previously defined saving path. After loading we resume the build process with a target iteration depth of `2` by calling the `resume_build_process` method with the corresponding parameter.

## No Guarantee for Completeness

Retrieval errors can always occur. Sometimes necessary information could not be obtained from Scopus to perform deeper analysis and dig further. If documents or references derived from them could not be retrieved they will be skipped. The `CitationGraph` class implements internal counters for failed retrievals, but keeps not track of the exact identifiers. Therefore the derived citation graphs are seldom complete. If you wish to build the complete citation graph with all necessary references you will need to check each paper and its references manually.

The retrieval counters can be accessed as attributes `retrievals_total` and `retrievals_failed` of the `CitationGraph` class.

## Dependencies

LitCitGraph needs the following dependencies:

| Dependency | Usage
| --- | ---
| [pybliometrics](https://github.com/pybliometrics-dev/pybliometrics) | retrieval from Scopus API
| [NetworkX](https://github.com/networkx/networkx) | graph-based features (`CitationGraph` is essentially a directed graph)
| [tqdm](https://github.com/tqdm/tqdm) | used to display progress bars during retrieval processes

---

## Graphistry

*Info provided later.*

## Ranking

*Info provided later.*