# ***CURRENTLY NOT WORKING***

[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org) 

# LitCitGraph

This library automatically builds literature citation graphs based on a given batch obtained from a search query in scientific databases. The iteration depth is customisable.

## Supported Databases

Current only **Scopus** supported.

## Important Notice

This library uses API requests. Therefore it is required to provide a valid API key, which has to acquired from the corresponding database provider, in this case Scopus. In order to successfully build a citation graph the references of each paper have to be obtained. This references are then used to gather their references in an iterative procedure.

To obtain these references in **Scopus** you have to use the *FULL view* according to the API documentation. The availability of this view depends on the subscription model with which you applied for your API key. So if your your underlying subscription does not allow to use the *FULL view* there is unfortunately no way to build up the citation graph and use this library.