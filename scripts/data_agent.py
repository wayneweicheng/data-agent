"""Create and query a BigQuery data agent for the retail demo."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from dotenv import load_dotenv
from google.api_core import client_options
from google.api_core.exceptions import AlreadyExists
from google.cloud import geminidataanalytics

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
DATASET_ID = os.getenv("BIGQUERY_DATASET", "retail_agent_demo")
LOCATION = os.getenv("DATA_AGENT_LOCATION", "us").lower()
AGENT_ID = os.getenv("DATA_AGENT_ID", "retail-analyst-demo")
MAX_BILLED_BYTES = 10 * 1024 * 1024  # BigQuery's documented minimum: 10 MiB.


def require_project() -> str:
    if not PROJECT_ID:
        raise SystemExit("Set GOOGLE_CLOUD_PROJECT in .env before running this script.")
    return PROJECT_ID


SYSTEM_INSTRUCTION = """
You are a careful retail business analyst for the demo ecommerce dataset.
Use only the supplied BigQuery tables. Explain the calculation briefly and show
units, percentages, and currency clearly. If the question is ambiguous, state
your assumption before answering. Never invent facts that are not in the data.

Business definitions:
- Revenue means completed-order item quantity * products.unit_price * (1 - orders.discount_pct).
- Cancelled orders are not sales and must be excluded from revenue, profit, and order counts.
- Gross profit means revenue minus item quantity * products.cost.
- Net revenue subtracts the value of returned units from completed-order revenue.
- A repeat customer has at least two completed orders in the requested period.
- Join orders to order_items on order_id, products to order_items on product_id,
  and customers to orders on customer_id. Join returns to both order_id and product_id.
- When calculating an order-level metric from order_items, use COUNT(DISTINCT order_id)
  to avoid counting an order once per line.
- discount_pct is a fraction: 0.10 means a 10% discount, not 0.10 dollars.
""".strip()

TABLE_CONTEXT: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "customers": (
        "One row per customer. Use for customer segments and geographic analysis.",
        [
            ("customer_id", "Stable customer key; joins to orders.customer_id."),
            ("customer_name", "Customer display name."),
            ("signup_date", "Account creation date."),
            ("segment", "new, regular, or loyalist marketing segment."),
            ("region", "Customer sales region."),
        ],
    ),
    "products": (
        "Product catalog. unit_price is list price and cost is unit cost, both in USD.",
        [
            ("product_id", "Stable product key; joins to order_items.product_id."),
            ("name", "Product name."),
            ("category", "Merchandising category."),
            ("unit_price", "List price per unit before the order discount, USD."),
            ("cost", "Product cost per unit, USD."),
        ],
    ),
    "orders": (
        "Order header. There is one row per order; join to order_items for quantities.",
        [
            ("order_id", "Stable order key; joins to order_items.order_id and returns.order_id."),
            ("customer_id", "Buyer key; joins to customers.customer_id."),
            ("order_date", "Date the order was placed."),
            ("channel", "web, mobile, store, or partner."),
            ("status", "completed or cancelled; only completed orders are sales."),
            ("discount_pct", "Fractional order discount, for example 0.10 = 10%."),
        ],
    ),
    "order_items": (
        "One row per product line in an order. Quantity is the number of units.",
        [
            ("order_id", "Joins to orders.order_id."),
            ("line_number", "Line number within the order."),
            ("product_id", "Joins to products.product_id."),
            ("quantity", "Units sold on this line."),
        ],
    ),
    "returns": (
        "Returned units by original order and product; use for return-rate and net-revenue analysis.",
        [
            ("return_id", "Stable return key."),
            ("order_id", "Original order key; joins to orders.order_id."),
            ("product_id", "Returned product key; joins to products.product_id."),
            ("return_date", "Date the return was recorded."),
            ("quantity", "Units returned."),
            ("reason", "size, changed_mind, or damaged."),
        ],
    ),
}


def endpoint_for(location: str) -> str:
    if not location or location == "global":
        return "geminidataanalytics.googleapis.com"
    if "-" in location:
        return f"geminidataanalytics-{location}.googleapis.com"
    return f"geminidataanalytics.{location}.rep.googleapis.com"


def clients() -> tuple[geminidataanalytics.DataAgentServiceClient, geminidataanalytics.DataChatServiceClient]:
    require_project()
    opts = client_options.ClientOptions(api_endpoint=endpoint_for(LOCATION))
    return (
        geminidataanalytics.DataAgentServiceClient(client_options=opts),
        geminidataanalytics.DataChatServiceClient(client_options=opts),
    )


def agent_name() -> str:
    return f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{AGENT_ID}"


def make_table_reference(
    table_name: str,
    table_context: dict[str, tuple[str, list[tuple[str, str]]]] | None = None,
) -> geminidataanalytics.BigQueryTableReference:
    context = table_context or TABLE_CONTEXT
    description, fields = context[table_name]
    reference = geminidataanalytics.BigQueryTableReference(
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        table_id=table_name,
    )
    reference.schema = geminidataanalytics.Schema()
    reference.schema.description = description
    reference.schema.fields = [
        geminidataanalytics.Field(name=name, description=field_description)
        for name, field_description in fields
    ]
    return reference


def make_agent(
    table_context: dict[str, tuple[str, list[tuple[str, str]]]] | None = None,
) -> geminidataanalytics.DataAgent:
    context = table_context or TABLE_CONTEXT
    sources = geminidataanalytics.DatasourceReferences()
    sources.bq.table_references = [
        make_table_reference(name, context) for name in context
    ]

    context = geminidataanalytics.Context()
    context.system_instruction = SYSTEM_INSTRUCTION
    context.datasource_references = sources
    # This field is an Int64Value wrapper; proto-plus accepts a plain integer.
    context.options.datasource.big_query_max_billed_bytes = MAX_BILLED_BYTES

    agent = geminidataanalytics.DataAgent()
    agent.data_analytics_agent.published_context = context
    return agent


def create_agent(
    table_context: dict[str, tuple[str, list[tuple[str, str]]]] | None = None,
) -> None:
    agent_client, _ = clients()
    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        data_agent_id=AGENT_ID,
        data_agent=make_agent(table_context),
    )
    try:
        response = agent_client.create_data_agent_sync(request=request)
        print(f"Created data agent: {response.name}")
    except AlreadyExists:
        print(f"Data agent already exists: {agent_name()}")
        print("Use it with: python scripts/data_agent.py ask --question \"...\"")


def value_to_json(value: Any) -> Any:
    """Make proto-plus values printable without depending on SDK internals."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): value_to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [value_to_json(item) for item in value]
    return str(value)


def print_result_data(data: Any) -> None:
    result = getattr(data, "result", None)
    if not result:
        return
    schema = getattr(result, "schema", None)
    fields = [getattr(field, "name", str(field)) for field in getattr(schema, "fields", [])]
    rows = list(getattr(result, "data", []))
    if fields:
        print("\nResult:")
        for row in rows:
            if isinstance(row, dict):
                rendered = {field: value_to_json(row.get(field)) for field in fields}
            else:
                rendered = value_to_json(row)
            print(json.dumps(rendered, default=str))


def show_response(response: Any) -> None:
    system_message = getattr(response, "system_message", None)
    if not system_message:
        return

    text_message = getattr(system_message, "text", None)
    parts = getattr(text_message, "parts", []) if text_message else []
    if parts:
        print("".join(str(part) for part in parts), end="", flush=True)

    data = getattr(system_message, "data", None)
    if data:
        generated_sql = getattr(data, "generated_sql", None)
        if generated_sql:
            print(f"\n\nGenerated SQL:\n{generated_sql}")
        print_result_data(data)


def ask(question: str) -> None:
    _, chat_client = clients()
    message = geminidataanalytics.Message()
    message.user_message.text = question
    context = geminidataanalytics.DataAgentContext()
    context.data_agent = agent_name()
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{PROJECT_ID}/locations/{LOCATION}",
        messages=[message],
        data_agent_context=context,
    )

    print(f"Question: {question}\n\nAnswer:\n")
    stream = chat_client.chat(request=request, timeout=300)
    for response in stream:
        show_response(response)
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create-agent", help="Create the configured BigQuery data agent.")
    ask_parser = subparsers.add_parser("ask", help="Ask one natural-language question.")
    ask_parser.add_argument("--question", help="Question to send; prompts if omitted.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "create-agent":
        create_agent()
    elif args.command == "ask":
        question = args.question or input("Ask your retail data agent: ").strip()
        if not question:
            raise SystemExit("A question is required.")
        ask(question)


if __name__ == "__main__":
    main()
