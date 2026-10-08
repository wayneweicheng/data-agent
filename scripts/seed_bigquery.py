"""Create and load the small retail dataset used by the data-agent demo."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
DATASET_ID = os.getenv("BIGQUERY_DATASET", "retail_agent_demo")
LOCATION = os.getenv("BIGQUERY_LOCATION", "US")

if not PROJECT_ID:
    raise SystemExit("Set GOOGLE_CLOUD_PROJECT in .env before running this script.")


PRODUCTS = [
    {"product_id": "P001", "name": "Trail Shoes", "category": "outdoor", "unit_price": 120.0, "cost": 62.0},
    {"product_id": "P002", "name": "Insulated Bottle", "category": "outdoor", "unit_price": 28.0, "cost": 10.0},
    {"product_id": "P003", "name": "Yoga Mat", "category": "fitness", "unit_price": 45.0, "cost": 18.0},
    {"product_id": "P004", "name": "Resistance Bands", "category": "fitness", "unit_price": 24.0, "cost": 8.0},
    {"product_id": "P005", "name": "Wireless Headphones", "category": "electronics", "unit_price": 89.0, "cost": 48.0},
    {"product_id": "P006", "name": "Portable Speaker", "category": "electronics", "unit_price": 65.0, "cost": 31.0},
    {"product_id": "P007", "name": "Everyday Backpack", "category": "lifestyle", "unit_price": 74.0, "cost": 29.0},
    {"product_id": "P008", "name": "Travel Journal", "category": "lifestyle", "unit_price": 18.0, "cost": 5.0},
]

CUSTOMERS = [
    {"customer_id": "C001", "customer_name": "Avery Chen", "signup_date": "2024-10-03", "segment": "loyalist", "region": "West"},
    {"customer_id": "C002", "customer_name": "Sam Rivera", "signup_date": "2024-11-17", "segment": "new", "region": "South"},
    {"customer_id": "C003", "customer_name": "Jordan Patel", "signup_date": "2024-08-22", "segment": "loyalist", "region": "West"},
    {"customer_id": "C004", "customer_name": "Morgan Smith", "signup_date": "2025-01-05", "segment": "new", "region": "Northeast"},
    {"customer_id": "C005", "customer_name": "Taylor Kim", "signup_date": "2024-09-12", "segment": "regular", "region": "Midwest"},
    {"customer_id": "C006", "customer_name": "Casey Brown", "signup_date": "2024-12-29", "segment": "new", "region": "South"},
    {"customer_id": "C007", "customer_name": "Riley Jones", "signup_date": "2024-07-14", "segment": "loyalist", "region": "Northeast"},
    {"customer_id": "C008", "customer_name": "Drew Wilson", "signup_date": "2024-11-02", "segment": "regular", "region": "West"},
    {"customer_id": "C009", "customer_name": "Jamie Garcia", "signup_date": "2024-06-19", "segment": "loyalist", "region": "Midwest"},
    {"customer_id": "C010", "customer_name": "Alex Martin", "signup_date": "2025-02-02", "segment": "new", "region": "Northeast"},
    {"customer_id": "C011", "customer_name": "Quinn Davis", "signup_date": "2024-09-30", "segment": "regular", "region": "South"},
    {"customer_id": "C012", "customer_name": "Lee Thompson", "signup_date": "2024-05-11", "segment": "loyalist", "region": "West"},
]


def make_orders_and_items() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    orders: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    channels = ["web", "mobile", "store", "partner"]
    start = date(2025, 1, 6)

    for number in range(1, 49):
        order_id = f"O{number:04d}"
        customer = CUSTOMERS[(number * 3) % len(CUSTOMERS)]
        status = "cancelled" if number in (17, 34, 46) else "completed"
        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "order_date": (start + timedelta(days=(number - 1) * 2)).isoformat(),
                "channel": channels[number % len(channels)],
                "status": status,
                "discount_pct": [0.0, 0.05, 0.10, 0.15, 0.20][number % 5],
            }
        )

        product_count = 1 + (number % 3)
        product_indexes = [(number + offset * 3) % len(PRODUCTS) for offset in range(product_count)]
        for line_number, product_index in enumerate(product_indexes, start=1):
            items.append(
                {
                    "order_id": order_id,
                    "line_number": line_number,
                    "product_id": PRODUCTS[product_index]["product_id"],
                    "quantity": 1 + ((number + line_number) % 4),
                }
            )
    return orders, items


def make_returns(items: list[dict[str, Any]], orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order_by_id = {order["order_id"]: order for order in orders}
    returns: list[dict[str, Any]] = []
    return_number = 1
    # Deliberately deterministic: enough returns to make return-rate analysis interesting.
    for item in items:
        order = order_by_id[item["order_id"]]
        order_number = int(item["order_id"][1:])
        if order["status"] == "completed" and (order_number + item["line_number"]) % 9 == 0:
            returns.append(
                {
                    "return_id": f"R{return_number:04d}",
                    "order_id": item["order_id"],
                    "product_id": item["product_id"],
                    "return_date": (
                        date.fromisoformat(order["order_date"]) + timedelta(days=7)
                    ).isoformat(),
                    "quantity": 1,
                    "reason": ["size", "changed_mind", "damaged"][return_number % 3],
                }
            )
            return_number += 1
    return returns


SCHEMAS = {
    "customers": [
        bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED", description="Stable customer identifier used to join to orders."),
        bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED", description="Customer display name."),
        bigquery.SchemaField("signup_date", "DATE", mode="REQUIRED", description="Date the customer created an account."),
        bigquery.SchemaField("segment", "STRING", mode="REQUIRED", description="Marketing segment: new, regular, or loyalist."),
        bigquery.SchemaField("region", "STRING", mode="REQUIRED", description="Sales region of the customer."),
    ],
    "products": [
        bigquery.SchemaField("product_id", "STRING", mode="REQUIRED", description="Stable product identifier used to join to order_items."),
        bigquery.SchemaField("name", "STRING", mode="REQUIRED", description="Product name."),
        bigquery.SchemaField("category", "STRING", mode="REQUIRED", description="Merchandising category."),
        bigquery.SchemaField("unit_price", "FLOAT64", mode="REQUIRED", description="List price per unit in USD before an order discount."),
        bigquery.SchemaField("cost", "FLOAT64", mode="REQUIRED", description="Product cost per unit in USD; use for gross profit."),
    ],
    "orders": [
        bigquery.SchemaField("order_id", "STRING", mode="REQUIRED", description="Stable order identifier used to join to order_items and returns."),
        bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED", description="Customer who placed the order; joins to customers.customer_id."),
        bigquery.SchemaField("order_date", "DATE", mode="REQUIRED", description="Date the order was placed."),
        bigquery.SchemaField("channel", "STRING", mode="REQUIRED", description="Order channel: web, mobile, store, or partner."),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="Order status. Only completed orders count as sales; cancelled orders count as zero revenue."),
        bigquery.SchemaField("discount_pct", "FLOAT64", mode="REQUIRED", description="Fractional order-level discount, such as 0.10 for 10 percent. Apply to item revenue."),
    ],
    "order_items": [
        bigquery.SchemaField("order_id", "STRING", mode="REQUIRED", description="Order identifier; joins to orders.order_id."),
        bigquery.SchemaField("line_number", "INT64", mode="REQUIRED", description="Line number within an order."),
        bigquery.SchemaField("product_id", "STRING", mode="REQUIRED", description="Product identifier; joins to products.product_id."),
        bigquery.SchemaField("quantity", "INT64", mode="REQUIRED", description="Number of units sold on the line."),
    ],
    "returns": [
        bigquery.SchemaField("return_id", "STRING", mode="REQUIRED", description="Stable return identifier."),
        bigquery.SchemaField("order_id", "STRING", mode="REQUIRED", description="Original order identifier; joins to orders.order_id."),
        bigquery.SchemaField("product_id", "STRING", mode="REQUIRED", description="Returned product; joins to products.product_id and order_items.product_id."),
        bigquery.SchemaField("return_date", "DATE", mode="REQUIRED", description="Date the return was recorded."),
        bigquery.SchemaField("quantity", "INT64", mode="REQUIRED", description="Number of units returned."),
        bigquery.SchemaField("reason", "STRING", mode="REQUIRED", description="Return reason."),
    ],
}


def load_table(client: bigquery.Client, table_name: str, rows: list[dict[str, Any]]) -> None:
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
    table = bigquery.Table(table_id, schema=SCHEMAS[table_name])
    table.description = {
        "customers": "One row per retail customer.",
        "products": "Product catalog with list price and unit cost.",
        "orders": "Order header. Join to order_items for products and quantities.",
        "order_items": "One row per product line in an order.",
        "returns": "Returned units by original order and product.",
    }[table_name]
    client.delete_table(table_id, not_found_ok=True)
    client.create_table(table)
    job = client.load_table_from_json(
        rows,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=SCHEMAS[table_name],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    )
    job.result()
    print(f"  {table_name:12} {len(rows):>3} rows -> {table_id}")


def main() -> None:
    client = bigquery.Client(project=PROJECT_ID)
    dataset_id = f"{PROJECT_ID}.{DATASET_ID}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = LOCATION
    dataset.description = "Small ecommerce dataset for learning BigQuery data agents."
    client.create_dataset(dataset, exists_ok=True)

    orders, items = make_orders_and_items()
    returns = make_returns(items, orders)
    rows_by_table = {
        "customers": CUSTOMERS,
        "products": PRODUCTS,
        "orders": orders,
        "order_items": items,
        "returns": returns,
    }

    print(f"Loading retail demo into {dataset_id} (location={LOCATION})")
    for table_name, rows in rows_by_table.items():
        load_table(client, table_name, rows)
    print("Done. The dataset is ready for a data agent.")


if __name__ == "__main__":
    main()
