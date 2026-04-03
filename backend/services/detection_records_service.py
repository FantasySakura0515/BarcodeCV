from __future__ import annotations

import sqlite3

from ..database.business_repository import BusinessRepository
from .detection_presenter import build_batch_detail, build_batch_list_item, build_object_dict
from .model_service import ModelService


class DetectionRecordsService:
    """Read/write access to persisted detection batches and objects."""

    def __init__(self, conn: sqlite3.Connection):
        self._biz_repo = BusinessRepository(conn)
        self._biz_repo.ensure_seed_data()
        self._model_service = ModelService(conn)

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[dict]:
        model = self._model_service.get_active_model("opencv")
        rows = self._biz_repo.list_batches(limit=limit, offset=offset)
        return [self._build_batch_list_item(row=row, model=model) for row in rows]

    def get_batch(self, rid: str) -> dict | None:
        model = self._model_service.get_active_model("opencv")
        batch = self._biz_repo.get_batch_by_code(rid)
        if batch is None:
            return None

        objects = self.list_objects_by_rid(rid=rid, model=model)
        return build_batch_detail(batch=batch, model=model, objects=objects)

    def get_object(self, bid: str) -> dict | None:
        row = self._biz_repo.get_task_by_code(bid)
        if row is None:
            return None

        model = self._model_service.get_active_model("opencv")
        return build_object_dict(row=row, rid=row["batch_code"], model=model)

    def update_object_remark(self, bid: str, remark: str) -> dict | None:
        row = self._biz_repo.update_task_remark(bid, remark)
        if row is None:
            return None

        model = self._model_service.get_active_model("opencv")
        return build_object_dict(row=row, rid=row["batch_code"], model=model)

    def list_objects_by_rid(self, rid: str, model: dict | None = None) -> list[dict]:
        resolved_model = model or self._model_service.get_active_model("opencv")
        batch = self._biz_repo.get_batch_by_code(rid)
        if batch is None:
            return []

        rows = self._biz_repo.list_tasks_by_batch_id(int(batch["id"]))
        return [build_object_dict(row=row, rid=rid, model=resolved_model) for row in rows]

    def _build_batch_list_item(self, row, model: dict) -> dict:
        rid = row["code"]
        objects = self.list_objects_by_rid(rid=rid, model=model)
        return build_batch_list_item(row=row, model=model, objects=objects)
