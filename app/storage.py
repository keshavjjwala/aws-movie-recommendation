"""A user's movie library in DynamoDB: one item per (userId, movieId) holding
an optional list status and an optional rating."""

import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

STATUSES = ("plan_to_watch", "watching", "watched", "dropped")


class StoreUnavailable(Exception):
    """DynamoDB could not be reached (locally: is `docker compose up` running?)."""


def _unavailable(error):
    if isinstance(error, ClientError) and error.response["Error"]["Code"] != "ResourceNotFoundException":
        raise error
    raise StoreUnavailable(f"library store unavailable: {error}") from error


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dynamodb_resource(endpoint_url=None, region=None):
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    config = Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2})
    return boto3.resource("dynamodb", endpoint_url=endpoint_url, region_name=region, config=config)


def ensure_table(dynamodb, table, keys):
    """Create the table if it does not exist (local development only; on AWS
    the SAM template creates it). keys: [(name, "S" | "N"), ...], hash key first."""
    try:
        table.load()
        return table
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    except BotoCoreError as error:
        _unavailable(error)
    table = dynamodb.create_table(
        TableName=table.name,
        KeySchema=[{"AttributeName": n, "KeyType": t} for (n, _), t in zip(keys, ("HASH", "RANGE"))],
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": t} for n, t in keys],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


class LibraryStore:
    def __init__(self, table_name, endpoint_url=None, region=None):
        self._dynamodb = dynamodb_resource(endpoint_url, region)
        self._table = self._dynamodb.Table(table_name)

    def ensure_table(self):
        self._table = ensure_table(self._dynamodb, self._table, [("userId", "S"), ("movieId", "N")])

    def _update(self, user_id, movie_id, expression, values=None, condition=None):
        kwargs = {
            "Key": {"userId": user_id, "movieId": movie_id},
            "UpdateExpression": expression,
        }
        if "#s" in expression:  # "status" is a DynamoDB reserved word
            kwargs["ExpressionAttributeNames"] = {"#s": "status"}
        if values:
            kwargs["ExpressionAttributeValues"] = values
        if condition:
            kwargs["ConditionExpression"] = condition
        try:
            self._table.update_item(**kwargs)
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                _unavailable(error)
        except BotoCoreError as error:
            _unavailable(error)

    def set_rating(self, user_id, movie_id, rating):
        """Rating a movie you haven't listed, or only planned to watch, means
        you've seen it: it goes on your list as watched."""
        self._update(
            user_id, movie_id,
            "SET rating = :r, updatedAt = :t, #s = if_not_exists(#s, :watched)",
            {":r": Decimal(str(rating)), ":t": _now(), ":watched": "watched"},
        )
        self._update(
            user_id, movie_id, "SET #s = :watched", {":watched": "watched", ":plan": "plan_to_watch"},
            condition="#s = :plan",
        )

    def clear_rating(self, user_id, movie_id):
        self._update(
            user_id, movie_id, "REMOVE rating SET updatedAt = :t", {":t": _now()},
            condition="attribute_exists(movieId)",  # don't create an empty entry
        )

    def set_status(self, user_id, movie_id, status):
        self._update(user_id, movie_id, "SET #s = :s, updatedAt = :t", {":s": status, ":t": _now()})

    def remove(self, user_id, movie_id):
        try:
            self._table.delete_item(Key={"userId": user_id, "movieId": movie_id})
        except (BotoCoreError, ClientError) as error:
            _unavailable(error)

    def get_library(self, user_id):
        """{movie_id: {"status", "rating" (float | None), "updated"}}"""
        library = {}
        kwargs = {"KeyConditionExpression": Key("userId").eq(user_id)}
        try:
            while True:
                page = self._table.query(**kwargs)
                for item in page["Items"]:
                    rating = float(item["rating"]) if "rating" in item else None
                    status = item.get("status") or ("watched" if rating is not None else None)
                    if status is None:
                        continue
                    library[int(item["movieId"])] = {
                        "status": status,
                        "rating": rating,
                        "updated": item.get("updatedAt", ""),
                    }
                if "LastEvaluatedKey" not in page:
                    return library
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        except (BotoCoreError, ClientError) as error:
            _unavailable(error)

    def get_ratings(self, user_id):
        return {i: e["rating"] for i, e in self.get_library(user_id).items() if e["rating"] is not None}
