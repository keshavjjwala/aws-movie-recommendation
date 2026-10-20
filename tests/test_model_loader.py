import boto3
import pytest
from moto import mock_aws

from app.model_loader import load_model
from train import save_model

MODEL = {"movies": {"1": {"title": "X", "year": None, "genres": [], "count": 0}}, "neighbours": {"1": []}, "popular": [1]}


def test_loads_from_local_path(tmp_path, monkeypatch):
    path = tmp_path / "model.json.gz"
    save_model(MODEL, path)
    monkeypatch.setenv("MODEL_PATH", str(path))
    monkeypatch.delenv("MODEL_S3_BUCKET", raising=False)
    assert load_model() == MODEL


def test_missing_local_model_explains_how_to_build_it(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "nope.json.gz"))
    monkeypatch.delenv("MODEL_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="python train.py"):
        load_model()


def test_loads_from_s3_when_bucket_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("MODEL_S3_BUCKET", "models")
    monkeypatch.setenv("MODEL_S3_KEY", "model.json.gz")
    monkeypatch.setenv("MODEL_CACHE_PATH", str(tmp_path / "cached.json.gz"))
    path = tmp_path / "model.json.gz"
    save_model(MODEL, path)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="models")
        s3.upload_file(str(path), "models", "model.json.gz")
        assert load_model() == MODEL
