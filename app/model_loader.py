"""Loads the gzipped-JSON model built by train.py, from disk or from S3."""

import gzip
import json
import os
from pathlib import Path

DEFAULT_MODEL_PATH = "model/model.json.gz"


def load_model():
    bucket = os.environ.get("MODEL_S3_BUCKET")
    if bucket:
        import boto3

        # Lambda can only write to /tmp; the file stays cached for warm starts.
        path = Path(os.environ.get("MODEL_CACHE_PATH", "/tmp/model.json.gz"))
        if not path.exists():
            key = os.environ.get("MODEL_S3_KEY", "model.json.gz")
            boto3.client("s3").download_file(bucket, key, str(path))
    else:
        path = Path(os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH))
        if not path.exists():
            raise RuntimeError(f"Model file {path} not found. Build it first with: python train.py")

    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
