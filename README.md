[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org) 

# LitCitGraph

This library automatically builds literature citation graphs based on a given batch obtained from a search query in scientific databases. The iteration depth is customisable.

## Supported Databases

Current only **Scopus** supported.

## Important Notice

This library uses API requests. Therefore it is required to provide a valid API key, which has to acquired from the corresponding database provider, in this case Scopus. In order to successfully build a citation graph the references of each paper have to be obtained. This references are then used to gather their references in an iterative procedure.

To obtain these references in **Scopus** you have to use the *FULL view* according to the API documentation. The availability of this view depends on the subscription model with which you applied for your API key. So if your underlying subscription does not allow to use the *FULL view* there is unfortunately no way to build up the citation graph and use this library.

## Getting Started

### Text-based search

The text-based search utilises an search query exported directly from Scopus. Therefore you can simply build your desired search query string and search through Scopus as you would normally do. To export the found results mark them all via the drop-drown menu `All` next to the check box and choose `Select all`. Then, click on `Export` and choose `CSV` as file format. A pop-up windows will appear, in which you can select the properties to be exported. We only need `EID` and `DOI` as unique identifiers. The other properties could be obtained through the corresponding request at a later stage. Save the exported CSV file in a location you have access to without problems. A path relative to your script is recommended.

Now we are able to build our first citation graph.

```python
# base class, always needed
from litcitgraph.graphs import CitationGraph
# helper function to read exported CSV data
from litcitgraph.parsing import read_scopus_ids_from_csv
```

We always need an additional saving path, where our citation graph can be saved to in case of any known potential error, e.g., the quota of your API key is exceeded. All paths can be either a `string` or a `Path` object from Python's standard library `pathlib`. In this example we use a standard `Path` object. 

Additionally, the path to the exported Scopus data must be provided.

```python
from pathlib import Path

path_to_data = Path('./scopus_data.csv')
saving_path = Path('./inter_save.pkl')
```

> [!CAUTION]
> The citation graph object is saved as `Pickle` file for convenience. Please be advised that pickled objects are not safe and can contain malicious code. Please only load pickled files which were created by your own.

Now we can start the build process by providing the necessary data input. We also need to provide information how many iteration levels we want to gather and whether we want to use the `DOI` or not. It is recommended not to use `DOI` and opt for `EID` as identifier. `EID` often provides more robust search experience since `DOI` information is sometimes outdated or not available on Scopus.

```python
id_data = read_scopus_ids_from_csv(path_to_data, use_doi=False, batch_size=None)
cit_graph = CitationGraph(saving_path)
```