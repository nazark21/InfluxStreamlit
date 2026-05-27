"""Default Influx credentials from env + per-user overrides in MongoDB."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()


@dataclass
class InfluxCredentials:
    url: str
    token: str
    org: str
    bucket: str
    verify_ssl: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "token": self.token,
            "org": self.org,
            "bucket": self.bucket,
            "verify_ssl": self.verify_ssl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InfluxCredentials":
        return cls(
            url=str(data.get("url", "")).strip(),
            token=str(data.get("token", "")).strip(),
            org=str(data.get("org", "")).strip(),
            bucket=str(data.get("bucket", "")).strip(),
            verify_ssl=bool(data.get("verify_ssl", False)),
        )

    def is_complete(self) -> bool:
        return all([self.url, self.token, self.org, self.bucket])


def default_credentials() -> InfluxCredentials:
    verify = os.getenv("INFLUXDB_VERIFY_SSL", "false").lower() in ("1", "true", "yes")
    return InfluxCredentials(
        url=os.getenv("INFLUXDB_URL", "").strip(),
        token=os.getenv("INFLUXDB_TOKEN", "").strip(),
        org=os.getenv("INFLUXDB_ORG", "").strip(),
        bucket=os.getenv("INFLUXDB_BUCKET", "").strip(),
        verify_ssl=verify,
    )


def _mongo_collection():
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URL_SIMULATOR") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URL")
    db_name = os.getenv("MONGO_SIMULATOR_DB", "influxSimulator")
    collection_name = os.getenv("MONGO_SIMULATOR_CREDENTIALS_COLLECTION", "userInfluxCredentials")

    if not uri:
        raise ValueError(
            "MongoDB URI not configured. Set MONGO_URL_SIMULATOR or MONGODB_URI in .env."
        )

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client[db_name][collection_name]


def get_user_credentials(user_id: str) -> InfluxCredentials | None:
    """Load saved credentials for user_id, or None if using defaults only."""
    user_id = user_id.strip()
    if not user_id:
        return None
    col = _mongo_collection()
    doc = col.find_one({"userId": user_id})
    if not doc or "influx" not in doc:
        return None
    creds = InfluxCredentials.from_dict(doc["influx"])
    return creds if creds.is_complete() else None


def save_user_credentials(user_id: str, creds: InfluxCredentials) -> None:
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("user_id is required to save credentials")
    if not creds.is_complete():
        raise ValueError("All Influx fields (url, token, org, bucket) are required")

    col = _mongo_collection()
    col.update_one(
        {"userId": user_id},
        {
            "$set": {
                "userId": user_id,
                "influx": creds.as_dict(),
                "updatedAt": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def delete_user_credentials(user_id: str) -> None:
    user_id = user_id.strip()
    if not user_id:
        return
    col = _mongo_collection()
    col.delete_one({"userId": user_id})


def resolve_credentials(user_id: str, use_custom: bool) -> InfluxCredentials:
    """Defaults from env unless user enabled custom saved credentials."""
    if use_custom and user_id.strip():
        custom = get_user_credentials(user_id)
        if custom:
            return custom
    return default_credentials()
