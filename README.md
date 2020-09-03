# reader-embedding-api

API to find similar wikidata-items (and their corresponding articles) in embedding space constructed from reading sessions.

## Usage

Possible arguments:
- qid: wikidata item ot query; example:qid=Q81068910 (required)
- n: number of related items to return (optional, default: 10, max: 100); example: n=10
- lang: return article-title in corresponding wikipedia if it exists (optional, default: None); example: lang=en|de to get article-titles for enwiki and dewiki
- threshold: threshold for similarity score, i.e. only return items that are above a certain similarity threshold (optional, default=0.0); similarity goes from 0.0 (not very similar) to 1.0 (identical); example: threshold=0.8
- showurl: whether to show the url of the wikidata-item and the articles for easier exploration (optional, default=False); example: showurl=True
- filter: filter items whose label contains the substrings (optional, default=None); example filter=covid|corona filters all wikidata items for which the lowercased English label contains the substrings 'covid' or 'corona'.

Example-query on the toolforge instance:
```
https://reader.toolforge.org/api/v1/reader/nn?qid=Q81068910

```


## Additional notes

```./code``` contains the scripts to generate the embedding. The actual trained model is hosted on cloud-vps due to memory-requirements. Thus, here we point to that endpoint.
