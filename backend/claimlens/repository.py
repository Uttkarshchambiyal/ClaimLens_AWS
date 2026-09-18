from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from time import time
from uuid import uuid4
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ddb(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _ddb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_ddb(item) for item in value]
    if isinstance(value, tuple):
        return [_ddb(item) for item in value]
    return value


class ConditionalConflict(Exception):
    pass


class NotFound(Exception):
    pass


class TenantDenied(Exception):
    pass


class RequestInProgress(Exception):
    pass


class InMemoryRepository:
    def __init__(self, retention_days: int = 90):
        if retention_days < 1:
            raise ValueError("Retention must be at least one day")
        self.retention_days = retention_days
        self.records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def put_once(self, tenant_id: str, kind: str, record_id: str, value: dict[str, Any]) -> dict[str, Any]:
        key = (tenant_id, kind, record_id)
        if key in self.records:
            raise ConditionalConflict(record_id)
        record = {
            "expiresAt": int(time()) + self.retention_days * 86400,
            **deepcopy(value),
            "tenantId": tenant_id,
            "recordType": kind,
            "id": record_id,
        }
        self.records[key] = record
        return deepcopy(record)

    def get_for_tenant(self, tenant_id: str, kind: str, record_id: str) -> dict[str, Any]:
        record = self.records.get((tenant_id, kind, record_id))
        if not record:
            if any(k == kind and r == record_id for _, k, r in self.records):
                raise TenantDenied(record_id)
            raise NotFound(record_id)
        if record["tenantId"] != tenant_id:
            raise TenantDenied(record_id)
        return deepcopy(record)

    def update_for_tenant(self, tenant_id: str, kind: str, record_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        self.get_for_tenant(tenant_id, kind, record_id)
        self.records[(tenant_id, kind, record_id)].update(deepcopy(updates))
        return self.get_for_tenant(tenant_id, kind, record_id)

    def list_for_tenant(self, tenant_id: str, kind: str, prefix: str = "") -> list[dict[str, Any]]:
        return [deepcopy(value) for (tenant, record_kind, record_id), value in self.records.items() if tenant == tenant_id and record_kind == kind and record_id.startswith(prefix)]

    def idempotent(self, tenant_id: str, operation: str, key: str, producer):
        with self._lock:
            cache_key = (tenant_id, operation, key)
            if cache_key in self.idempotency:
                return deepcopy(self.idempotency[cache_key])
            value = producer()
            self.idempotency[cache_key] = deepcopy(value)
            return value


class DynamoRepository:
    def __init__(self, table: Any, retention_days: int = 90):
        if retention_days < 1:
            raise ValueError("Retention must be at least one day")
        self.table = table
        self.retention_days = retention_days

    def put_once(self, tenant_id: str, kind: str, record_id: str, value: dict[str, Any]) -> dict[str, Any]:
        item = _ddb({
            "expiresAt": int(time()) + self.retention_days * 86400,
            **value,
            "pk": f"TENANT#{tenant_id}",
            "sk": f"{kind}#{record_id}",
            "tenantId": tenant_id,
            "recordType": kind,
            "id": record_id,
        })
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)")
        except Exception as exc:
            if exc.__class__.__name__ == "ConditionalCheckFailedException":
                raise ConditionalConflict(record_id) from exc
            raise
        return item

    def get_for_tenant(self, tenant_id: str, kind: str, record_id: str) -> dict[str, Any]:
        response = self.table.get_item(Key={"pk": f"TENANT#{tenant_id}", "sk": f"{kind}#{record_id}"}, ConsistentRead=True)
        if "Item" not in response:
            raise NotFound(record_id)
        return response["Item"]

    def list_for_tenant(self, tenant_id: str, kind: str, prefix: str = "") -> list[dict[str, Any]]:
        args = {"KeyConditionExpression": "pk = :tenant AND begins_with(sk, :prefix)", "ExpressionAttributeValues": {":tenant": f"TENANT#{tenant_id}", ":prefix": f"{kind}#{prefix}"}, "ConsistentRead": True}
        items = []
        while True:
            response = self.table.query(**args)
            items.extend(response.get("Items", []))
            if not response.get("LastEvaluatedKey"): return items
            args["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    def update_for_tenant(self, tenant_id: str, kind: str, record_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        self.get_for_tenant(tenant_id, kind, record_id)
        names = {f"#n{i}": name for i, name in enumerate(updates)}
        values = {f":v{i}": _ddb(value) for i, value in enumerate(updates.values())}
        expression = "SET " + ", ".join(f"{name_key} = {value_key}" for name_key, value_key in zip(names, values))
        response = self.table.update_item(Key={"pk": f"TENANT#{tenant_id}", "sk": f"{kind}#{record_id}"}, UpdateExpression=expression, ExpressionAttributeNames=names, ExpressionAttributeValues={**values, ":tenant": tenant_id}, ConditionExpression="tenantId = :tenant", ReturnValues="ALL_NEW")
        return response["Attributes"]

    def idempotent(self, tenant_id: str, operation: str, key: str, producer):
        record_id = f"{operation}#{key}"
        owner = uuid4().hex
        now = int(time())
        record_key = {"pk": f"TENANT#{tenant_id}", "sk": f"IDEMPOTENCY#{record_id}"}
        try:
            self.put_once(tenant_id, "IDEMPOTENCY", record_id, {"owner": owner, "leaseUntil": now + 180, "createdAt": now_iso()})
        except ConditionalConflict:
            existing = self.get_for_tenant(tenant_id, "IDEMPOTENCY", record_id)
            if "response" in existing:
                return existing["response"]
            if int(existing.get("leaseUntil", now + 1)) > now:
                raise RequestInProgress("A matching request is still in progress")
            try:
                self.table.update_item(
                    Key=record_key,
                    UpdateExpression="SET #owner = :owner, leaseUntil = :lease",
                    ConditionExpression="leaseUntil <= :now AND attribute_not_exists(#response)",
                    ExpressionAttributeNames={"#owner": "owner", "#response": "response"},
                    ExpressionAttributeValues={":owner": owner, ":lease": now + 180, ":now": now},
                )
            except Exception as exc:
                if exc.__class__.__name__ == "ConditionalCheckFailedException":
                    raise RequestInProgress("A matching request is still in progress") from exc
                raise
        try:
            value = producer()
            self.table.update_item(
                Key=record_key, UpdateExpression="SET #response = :response",
                ConditionExpression="#owner = :owner",
                ExpressionAttributeNames={"#owner": "owner", "#response": "response"},
                ExpressionAttributeValues={":owner": owner, ":response": _ddb(value)},
            )
            return value
        except Exception:
            # Release only this invocation's lease. Durable domain records use
            # deterministic IDs, so an interrupted operation can safely resume.
            self.table.update_item(Key=record_key, UpdateExpression="SET leaseUntil = :expired",
                                   ConditionExpression="#owner = :owner",
                                   ExpressionAttributeNames={"#owner": "owner"},
                                   ExpressionAttributeValues={":expired": 0, ":owner": owner})
            raise
