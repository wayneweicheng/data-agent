# What is OpenMetadata?

**OpenMetadata is an open-source metadata platform and context layer for data and AI.** It catalogs data assets and connects their technical structure with business meaning, ownership, lineage, quality, governance, and usage context. Its goal is to help people and AI systems discover data, understand it, and judge whether it is trustworthy before using it.

This is distinct from a data warehouse: OpenMetadata stores information *about* data assets rather than replacing BigQuery as the place where the data is queried.

## What it manages

OpenMetadata models metadata for assets such as:

- databases, schemas, tables, and columns
- dashboards, charts, pipelines, topics, APIs, and ML models
- owners, teams, domains, and data products
- glossary terms, metrics, classifications, policies, and tags
- data quality tests, profiling results, freshness, and incidents
- table-level and column-level lineage
- usage information and collaboration context

The official repository describes this as a unified metadata knowledge graph containing technical metadata, quality, lineage, ownership, usage, policies, glossaries, classifications, metrics, domains, contracts, and data products. [OpenMetadata README](https://github.com/open-metadata/OpenMetadata/blob/main/README.md)

## How it is built

The main platform pieces are:

1. **REST API** — the central interface for creating, reading, updating, and querying metadata entities.
2. **Web UI** — a discovery and collaboration interface for users.
3. **Ingestion framework** — connectors that extract metadata from external systems and send it through the API.
4. **Entity store** — MySQL stores entity state and relationships.
5. **Search engine** — Elasticsearch indexes metadata to support discovery and search.

OpenMetadata uses a schema-first design. JSON Schemas provide the shared definition for metadata entities; Java models are used by the API, Python models by ingestion, and TypeScript types by the UI. [High-level design](https://docs.open-metadata.org/latest/api-reference/main-concepts/high-level-design)

Relationships are modeled separately from an entity's core JSON attributes. For example, a table can be related to its database, owner, tags, and upstream/downstream assets. The platform also records entity changes and versions, which supports history and auditing. [High-level design](https://docs.open-metadata.org/latest/api-reference/main-concepts/high-level-design)

## Why teams use it

OpenMetadata is useful when a data environment has many systems and people need answers such as:

- Which dataset should I use for customer revenue?
- What does this metric mean?
- Who owns this table?
- Is this table fresh, tested, and certified?
- Which dashboards or pipelines will be affected if this column changes?
- Which columns contain sensitive information?
- What are the upstream sources for this report?

Its main capabilities are therefore catalog/discovery, semantic business context, governance, lineage/impact analysis, data quality, observability, and collaboration. [OpenMetadata features](https://docs.open-metadata.org/latest/features)

## BigQuery connection

OpenMetadata has a BigQuery connector. The documented workflows include:

- metadata ingestion
- query usage
- data profiling
- data quality
- lineage
- dbt integration

The connector requires a service account or equivalent credentials and permissions such as `bigquery.datasets.get`, `bigquery.tables.get`, `bigquery.tables.getData`, `bigquery.tables.list`, and `bigquery.jobs.create`. BigQuery usage and lineage workflows additionally require Storage Read API permissions including `bigquery.readsessions.create` and `bigquery.readsessions.getData`. [BigQuery connector documentation](https://docs.open-metadata.org/latest/connectors/database/bigquery)

## Relationship to the BigQuery data-agent demo

The two tools solve different but complementary problems:

| Tool | Primary job |
| --- | --- |
| **BigQuery data agent** | Answers natural-language questions by generating and executing queries against selected BigQuery tables. |
| **OpenMetadata** | Provides catalog, definitions, owners, lineage, quality signals, classifications, and governance context about those tables. |

For the current retail demo, the BigQuery data agent can answer questions such as “Which category generated the most gross profit?” OpenMetadata could add context that improves trust and usability:

- document that `orders.status = 'completed'` defines a sale
- define “revenue,” “gross profit,” and “repeat customer” in a glossary
- assign an owner to the dataset
- identify sensitive customer columns
- show lineage from source tables to derived tables or dashboards
- attach quality tests and freshness information

OpenMetadata can expose metadata through APIs, SDKs, semantic search, and an MCP server, allowing an AI assistant or agent to retrieve governed metadata context. [OpenMetadata README](https://github.com/open-metadata/OpenMetadata/blob/main/README.md)

A practical architecture would be:

```text
BigQuery tables
      │
      ├── queried by ──> BigQuery data agent ──> analytical answer
      │
      └── cataloged by ──> OpenMetadata ──> definitions, ownership,
                             quality, lineage, and governance context
```

OpenMetadata would not automatically make a BigQuery data agent correct. The agent still needs appropriate table access, instructions, verified queries, and answer validation. OpenMetadata can supply additional context and governance, but the query execution and cost controls remain concerns for the BigQuery side.

## Getting started

The official project points to:

- [OpenMetadata Sandbox](https://sandbox.open-metadata.org) for trying the product
- [Quickstart documentation](https://docs.open-metadata.org/latest/quick-start) for installation
- [MCP server documentation](https://docs.open-metadata.org/latest/how-to-guides/mcp) for AI-agent integration
- [OpenMetadata GitHub repository](https://github.com/open-metadata/OpenMetadata)

## Bottom line

OpenMetadata is best understood as a **shared metadata and semantic context system** for a data estate. It helps humans and AI find the right data, understand its meaning, trace its origin and impact, and evaluate its trustworthiness. In this project, it would complement the BigQuery data agent rather than replace BigQuery or the data agent.

## Sources

All sources below are first-party OpenMetadata documentation or the official repository:

1. [OpenMetadata official site](https://open-metadata.org/)
2. [OpenMetadata GitHub README](https://github.com/open-metadata/OpenMetadata/blob/main/README.md)
3. [High-level design](https://docs.open-metadata.org/latest/api-reference/main-concepts/high-level-design)
4. [OpenMetadata features](https://docs.open-metadata.org/latest/features)
5. [BigQuery connector](https://docs.open-metadata.org/latest/connectors/database/bigquery)
