"""Raw API response storage — local filesystem in dev, S3/DO Spaces in prod."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class RawStorage:
    def __init__(self) -> None:
        self._local = settings.object_storage_local

        if not self._local:
            kwargs: dict = {
                "region_name": settings.aws_region,
                "aws_access_key_id": settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
            }
            if settings.aws_endpoint_url:
                kwargs["endpoint_url"] = settings.aws_endpoint_url
            self._s3 = boto3.client("s3", **kwargs)

    def save(self, platform: str, key: str, data: dict | list) -> str:
        """
        Persist raw API response.
        Returns the storage path/key so it can be referenced later.
        """
        ts = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H")
        object_key = f"raw/{platform}/{ts}/{key}.json"
        payload = json.dumps(data, default=str).encode()

        if self._local:
            path = Path(settings.local_raw_data_dir) / object_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return str(path)

        self._s3.put_object(
            Bucket=settings.object_storage_bucket,
            Key=object_key,
            Body=payload,
            ContentType="application/json",
        )
        return object_key


raw_storage = RawStorage()
