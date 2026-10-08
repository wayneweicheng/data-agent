# BigQuery data-agent demo

A small, repeatable ecommerce project for learning how a **BigQuery data agent** turns natural-language questions into SQL-backed analysis. It creates five related tables with realistic enough data to practice joins, metrics, time filters, segmentation, profitability, and returns.

The default project is already set to `ark-of-data-2000` in `.env.example`.

## What this demo creates

Dataset: `retail_agent_demo`

| Table | Purpose |
| --- | --- |
| `customers` | Customer, segment, and region |
| `products` | Product category, list price, and unit cost |
| `orders` | Order date, channel, status, and discount |
| `order_items` | Products and quantities per order |
| `returns` | Returned units and reason |

The important relationships are:

```text
customers 1 ──< orders 1 ──< order_items >── 1 products
                         └──< returns >───────┘
```

The seed is deterministic and safe to rerun: it replaces only the tables in this demo dataset.

## Prerequisites

1. A Google Cloud project with billing enabled. The configured project is `ark-of-data-2000`.
2. Python 3.10 or newer.
3. A user or service account with permission to create/load BigQuery tables and use Gemini Data Analytics.
4. `gcloud` installed and authenticated.

Enable the APIs once:

```bash
gcloud config set project ark-of-data-2000
gcloud services enable \
  bigquery.googleapis.com \
  geminidataanalytics.googleapis.com \
  cloudaicompanion.googleapis.com \
  dataplex.googleapis.com
```

For local development, Application Default Credentials are the simplest option:

```bash
gcloud auth application-default login
```

The account also needs, at minimum, BigQuery access to the demo data and these data-agent permissions:

- `roles/geminidataanalytics.dataAgentCreator` to create the agent
- `roles/geminidataanalytics.dataAgentUser` to chat with it
- `roles/bigquery.jobUser` on the billing project
- `roles/bigquery.dataEditor` while loading the demo tables
- `roles/bigquery.dataViewer` when querying the tables

Google Cloud IAM may be granted at the project level for this learning project. Use narrower dataset-level permissions in production.

## Run it

From this directory:

```bash
# macOS/Linux
cp .env.example .env
python -m venv .venv
source .venv/bin/activate

# Windows PowerShell equivalents:
# Copy-Item .env.example .env
# py -m venv .venv
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python scripts/seed_bigquery.py
python scripts/data_agent.py create-agent
```

If you use another project, edit `GOOGLE_CLOUD_PROJECT` in `.env`. Keep `BIGQUERY_LOCATION` and `DATA_AGENT_LOCATION` consistent with your data residency needs. The defaults use BigQuery `US` and the data-agent `us` multi-region.

The agent script supplies table/field descriptions, join rules, business definitions, and a 10 MiB maximum billed-bytes limit. The descriptions matter: they help the agent distinguish list price from cost, order headers from order lines, and cancelled orders from sales.

## Add OpenMetadata as the metadata layer

This demo now includes a local OpenMetadata deployment. OpenMetadata maintains the table and column descriptions; the final sync reads those descriptions back and publishes them into the BigQuery text-to-SQL agent.

Docker Desktop should have at least 6 GiB RAM and 4 vCPUs available. Start the official OpenMetadata Compose quickstart:

```bash
python scripts/openmetadata.py start
```

Open `http://localhost:8585` and sign in with the local quickstart credentials:

```text
admin@open-metadata.org / admin
```

Create a bot token in **Settings > Bots** and put it in `.env` as `OPENMETADATA_JWT_TOKEN`. Then install the OpenMetadata BigQuery ingestion package. Its version is intentionally aligned with the Docker release:

```bash
python -m pip install -r requirements-openmetadata.txt
python scripts/openmetadata.py ingest
```

The ingestion workflow imports the BigQuery project and `retail_agent_demo` dataset into OpenMetadata. The BigQuery hierarchy is represented as:

```text
retail_bigquery.ark-of-data-2000.retail_agent_demo.orders
```

Apply the curated descriptions in `metadata/catalog.yaml`:

```bash
python scripts/openmetadata.py apply
```

Now OpenMetadata is the metadata system that you can maintain. Edit table or column descriptions in the OpenMetadata UI, or update `metadata/catalog.yaml` and run `apply` again. Then update the data agent from the current OpenMetadata API values:

```bash
python scripts/data_agent.py create-agent
python scripts/openmetadata.py sync-agent
```

`sync-agent` retrieves each table from OpenMetadata, converts its current descriptions into the agent's structured BigQuery context, and updates the existing data agent. If the agent does not exist, it creates it. This gives you a repeatable flow:

```text
BigQuery schema/data -> OpenMetadata ingestion -> curated metadata -> data-agent context -> text-to-SQL answer
```

The initial YAML is only bootstrap metadata. After ingestion, OpenMetadata is the place to maintain descriptions, ownership, tags, glossary terms, quality information, and lineage. The current sync intentionally focuses on table and column descriptions because those are directly consumed by the data agent; it preserves the business definitions and join rules in the agent instructions.

Stop the local stack when finished:

```bash
python scripts/openmetadata.py stop
```

## Ask the agent

Try a simple question first:

```bash
python scripts/data_agent.py ask --question "What are the top five products by completed-order revenue?"
```

Then try questions that require several joins and explicit business logic:

```text
Which product categories generated the most gross profit, after applying order discounts, and what are their gross margins?

Compare repeat-purchase rate and average completed-order value by channel. Do not count order lines as orders.

Which customer segments have the highest net revenue per customer in each region, after excluding cancelled orders and returned units?

What are the monthly revenue and gross-profit trends, and which month had the biggest change in gross margin?

Which products have both an above-average return rate and below-average gross margin? Explain the likely business risk.

For the West region, identify loyalist customers with at least two completed orders, rank them by net revenue, and show their most-purchased category.
```

The CLI prints the answer and the generated SQL when the API returns it. Read the SQL, not just the prose: verify filters, join keys, `COUNT(DISTINCT order_id)`, and the discount/return calculations.

## Console workflow (no custom app)

You can also learn the BigQuery UI flow:

1. Open [BigQuery Agents](https://console.cloud.google.com/bigquery/agents_hub).
2. Choose **New agent**.
3. Name it `Retail analyst demo`.
4. Add all five tables from `ark-of-data-2000.retail_agent_demo` as knowledge sources.
5. Add these instructions:

   ```text
   Revenue means completed-order quantity * unit_price * (1 - discount_pct).
   Exclude cancelled orders from sales. Join order_items to orders on order_id and
   to products on product_id. Use COUNT(DISTINCT order_id) for order-level metrics.
   A repeat customer has at least two completed orders. State assumptions and show
   the SQL or calculation behind every answer.
   ```

6. Add a verified query for one important metric, such as category gross profit. Run it and confirm the result before saving.
7. Preview the agent with the questions above, refine descriptions/instructions, then publish only when the answers are trustworthy.

The UI and the Python script are two ways to use the same Conversational Analytics capabilities. The Python script is useful for learning how an application references a published agent:

```python
# The essential pattern used by scripts/data_agent.py
message.user_message.text = "Which category has the highest return rate?"
context.data_agent = (
    "projects/ark-of-data-2000/locations/us/dataAgents/retail-analyst-demo"
)
stream = data_chat_client.chat(
    request=geminidataanalytics.ChatRequest(
        parent="projects/ark-of-data-2000/locations/us",
        messages=[message],
        data_agent_context=context,
    ),
    timeout=300,
)
for response in stream:
    # Read system_message.text and system_message.data.generated_sql/result.
    ...
```

## Check the result independently

Use `sql/answer_key.sql` to inspect the intended SQL patterns. Replace `PROJECT_ID.DATASET` with `ark-of-data-2000.retail_agent_demo`, then run the queries in BigQuery. The answer key is not used by the agent; it is there to teach validation and prevent trusting a plausible but incorrect answer.

## Cleanup

The demo creates billable BigQuery resources and agent conversations. Delete the demo dataset when finished:

```bash
bq rm -r -f ark-of-data-2000:retail_agent_demo
```

Delete the data agent from **BigQuery > Agents**, or use the agent management API if you extend the script.

## Official references

- [Build a data agent with the Python SDK](https://cloud.google.com/gemini/docs/conversational-analytics-api/build-agent-sdk)
- [Create data agents in BigQuery](https://cloud.google.com/bigquery/docs/create-data-agents)
- [Conversational Analytics API overview](https://cloud.google.com/gemini/data-agents/conversational-analytics-api/overview)
- [OpenMetadata BigQuery connector](https://docs.open-metadata.org/latest/connectors/database/bigquery)
- [OpenMetadata local Docker quickstart](https://docs.open-metadata.org/latest/quick-start/local-docker-deployment)
- [OpenMetadata table update API](https://docs.open-metadata.org/latest/api-reference/data-assets/tables/update)
