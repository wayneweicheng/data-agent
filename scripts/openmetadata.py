"""Run the local OpenMetadata demo and sync its metadata into the data agent."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlretrieve

import requests
import yaml
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import geminidataanalytics
from google.protobuf.field_mask_pb2 import FieldMask

try:
    from scripts import data_agent
except ModuleNotFoundError:  # Running this file directly from the scripts directory.
    import data_agent

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
OPENMETADATA_DIR = ROOT / "openmetadata"
COMPOSE_FILE = OPENMETADATA_DIR / "docker-compose.yml"
CATALOG_FILE = ROOT / "metadata" / "catalog.yaml"
OPENMETADATA_VERSION = os.getenv("OPENMETADATA_VERSION", "1.13.0")
COMPOSE_URL = (
    "https://github.com/open-metadata/OpenMetadata/releases/"
    f"download/{OPENMETADATA_VERSION}-release/docker-compose.yml"
)
OPENMETADATA_HOST = os.getenv("OPENMETADATA_HOST", "http://localhost:8585/api").rstrip("/")
OPENMETADATA_TOKEN = os.getenv("OPENMETADATA_JWT_TOKEN")


def load_catalog() -> dict[str, Any]:
    with CATALOG_FILE.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def require_token() -> str:
    if not OPENMETADATA_TOKEN:
        raise SystemExit(
            "Set OPENMETADATA_JWT_TOKEN in .env. Create a bot token in "
            "OpenMetadata under Settings > Bots."
        )
    return OPENMETADATA_TOKEN


def api_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    headers.update(
        {
            "Authorization": f"Bearer {require_token()}",
            "Content-Type": "application/json",
        }
    )
    response = requests.request(
        method,
        f"{OPENMETADATA_HOST}/{path.lstrip('/')}",
        headers=headers,
        timeout=60,
        **kwargs,
    )
    if not response.ok:
        raise SystemExit(
            f"OpenMetadata API {method} {path} failed ({response.status_code}): "
            f"{response.text[:1000]}"
        )
    return response.json() if response.content else {}


def table_fqn(service_name: str, project_id: str, dataset_id: str, table_name: str) -> str:
    # BigQuery maps to service.project.dataset.table in OpenMetadata.
    return f"{service_name}.{project_id}.{dataset_id}.{table_name}"


def get_table(catalog: dict[str, Any], table_name: str) -> dict[str, Any]:
    fqn = table_fqn(
        catalog["service_name"],
        catalog["project_id"],
        catalog["dataset_id"],
        table_name,
    )
    return api_request(
        "GET",
        f"/v1/tables/name/{quote(fqn, safe='')}",
        params={"fields": "columns"},
    )


def apply_catalog() -> None:
    """Apply curated descriptions to tables already ingested into OpenMetadata."""
    catalog = load_catalog()
    for table_name, desired in catalog["tables"].items():
        table = get_table(catalog, table_name)
        columns = table.get("columns", [])
        desired_columns = desired.get("columns", {})
        for column in columns:
            if column.get("name") in desired_columns:
                column["description"] = desired_columns[column["name"]]

        payload = {
            "description": desired["description"],
            # The table PATCH API accepts column definitions for column descriptions.
            "columns": columns,
        }
        updated = api_request("PATCH", f"/v1/tables/{table['id']}", json=payload)
        print(f"Updated OpenMetadata: {updated.get('fullyQualifiedName', table_name)}")


def metadata_context() -> dict[str, tuple[str, list[tuple[str, str]]]]:
    """Read current descriptions from OpenMetadata in the shape used by data_agent.py."""
    catalog = load_catalog()
    result: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for table_name, fallback in catalog["tables"].items():
        table = get_table(catalog, table_name)
        table_description = table.get("description") or fallback["description"]
        fallback_columns = fallback.get("columns", {})
        om_columns = table.get("columns") or [
            {"name": name, "description": description}
            for name, description in fallback_columns.items()
        ]
        columns = []
        for column in om_columns:
            name = column.get("name")
            if not name:
                continue
            description = column.get("description") or fallback_columns.get(name, "")
            columns.append((name, description))
        result[table_name] = (table_description, columns)
    return result


def sync_agent() -> None:
    """Use OpenMetadata's current table metadata to update the text-to-SQL agent."""
    context = metadata_context()
    agent_client, _ = data_agent.clients()
    agent = data_agent.make_agent(context)
    agent.name = data_agent.agent_name()
    request = geminidataanalytics.UpdateDataAgentRequest(
        data_agent=agent,
        update_mask=FieldMask(paths=["data_analytics_agent.published_context"]),
    )
    try:
        updated = agent_client.update_data_agent_sync(request=request)
        print(f"Updated data agent from OpenMetadata: {updated.name}")
    except NotFound:
        print("Data agent does not exist; creating it from OpenMetadata metadata.")
        create_request = geminidataanalytics.CreateDataAgentRequest(
            parent=f"projects/{data_agent.PROJECT_ID}/locations/{data_agent.LOCATION}",
            data_agent_id=data_agent.AGENT_ID,
            data_agent=agent,
        )
        created = agent_client.create_data_agent_sync(request=create_request)
        print(f"Created data agent from OpenMetadata: {created.name}")


def compose(action: list[str]) -> None:
    OPENMETADATA_DIR.mkdir(parents=True, exist_ok=True)
    if not COMPOSE_FILE.exists():
        print(f"Downloading official OpenMetadata {OPENMETADATA_VERSION} Compose file...")
        urlretrieve(COMPOSE_URL, COMPOSE_FILE)
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *action],
        cwd=OPENMETADATA_DIR,
        check=True,
    )


def ingest() -> None:
    config_file = ROOT / "config" / "openmetadata-bigquery.yaml"
    subprocess.run(["metadata", "ingest", "-c", str(config_file)], cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("start", help="Download the official Compose file and start OpenMetadata.")
    subparsers.add_parser("stop", help="Stop local OpenMetadata containers.")
    subparsers.add_parser("down", help="Remove local OpenMetadata containers (keep volumes).")
    subparsers.add_parser("ingest", help="Run the official BigQuery metadata ingestion workflow.")
    subparsers.add_parser("apply", help="Apply metadata/catalog.yaml to ingested OpenMetadata tables.")
    subparsers.add_parser("sync-agent", help="Update the BigQuery data agent from OpenMetadata.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command in {"start", "stop", "down"}:
        compose({"start": ["up", "-d"], "stop": ["stop"], "down": ["down"]}[args.command])
    elif args.command == "ingest":
        ingest()
    elif args.command == "apply":
        apply_catalog()
    elif args.command == "sync-agent":
        sync_agent()


if __name__ == "__main__":
    main()
