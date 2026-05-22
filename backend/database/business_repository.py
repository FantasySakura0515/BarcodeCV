from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime


DEFAULT_CUSTOMER_CODE = "SYS-DEFAULT-CUSTOMER"
DEFAULT_DEVICE_CODE = "SYS-DEFAULT-DEVICE"


@dataclass
class DetectionTaskPayload:
    batch_id: int
    code: str
    status: str
    data_url: str | None
    box_detected: dict | None
    matrix_detected: dict | None
    remark: str | None = None


class BusinessRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ------------------------------------------------------------------
    # bootstrap
    # ------------------------------------------------------------------
    def ensure_seed_data(self) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO customers (name, code, description, email, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "System Default Customer",
                DEFAULT_CUSTOMER_CODE,
                "Default customer used by automatic detection flows.",
                None,
                None,
            ),
        )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO devices (name, code, type, location, is_active, is_deletable)
            VALUES (?, ?, ?, ?, 1, 0)
            """,
            (
                "System Default Device",
                DEFAULT_DEVICE_CODE,
                "camera",
                "default",
            ),
        )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO settings (name, description, setting_key, setting_value, is_deletable)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                "Minimum Output Confidence",
                "Confidence threshold used by detection result filtering.",
                "detection.min_output_confidence",
                "0.6",
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # batch/task helpers for detection flow
    # ------------------------------------------------------------------
    def create_batch(
        self,
        code: str,
        name: str | None = None,
        customer_id: int | None = None,
        description: str | None = None,
    ) -> int:
        customer_id = customer_id or self.get_default_customer_id()
        name = name or code
        cursor = self._conn.execute(
            """
            INSERT INTO batchs (customer_id, name, code, description)
            VALUES (?, ?, ?, ?)
            """,
            (customer_id, name, code, description),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def create_task(self, payload: DetectionTaskPayload) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO tasks
            (batchs_id, code, status, data_url, box_detected, matrix_detected, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.batch_id,
                payload.code,
                payload.status,
                payload.data_url,
                json.dumps(payload.box_detected, ensure_ascii=False) if payload.box_detected is not None else None,
                json.dumps(payload.matrix_detected, ensure_ascii=False) if payload.matrix_detected is not None else None,
                payload.remark,
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT
                b.id,
                b.code,
                b.name,
                b.description,
                b.created_at,
                c.id AS customer_id,
                c.name AS customer_name,
                c.code AS customer_code,
                COUNT(t.id) AS object_count,
                SUM(CASE
                        WHEN json_extract(t.matrix_detected, '$.barcodeValue') IS NOT NULL
                             AND json_extract(t.matrix_detected, '$.barcodeValue') <> ''
                        THEN 1
                        ELSE 0
                    END
                ) AS barcode_success_count,
                SUM(CASE
                        WHEN json_extract(t.matrix_detected, '$.ocrText') IS NOT NULL
                             AND json_extract(t.matrix_detected, '$.ocrText') <> ''
                        THEN 1
                        ELSE 0
                    END
                ) AS ocr_success_count
            FROM batchs b
            INNER JOIN customers c ON c.id = b.customer_id
            LEFT JOIN tasks t ON t.batchs_id = b.id AND t.deleted_at IS NULL
            WHERE b.deleted_at IS NULL
            GROUP BY b.id, c.id
            ORDER BY b.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    def get_batch_by_code(self, code: str) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT
                b.id,
                b.code,
                b.name,
                b.description,
                b.created_at,
                c.id AS customer_id,
                c.name AS customer_name,
                c.code AS customer_code
            FROM batchs b
            INNER JOIN customers c ON c.id = b.customer_id
            WHERE b.code = ? AND b.deleted_at IS NULL
            """,
            (code,),
        ).fetchone()

    def list_tasks_by_batch_id(self, batch_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE batchs_id = ? AND deleted_at IS NULL
            ORDER BY id ASC
            """,
            (batch_id,),
        ).fetchall()

    def get_task_by_code(self, code: str) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT t.*, b.code AS batch_code
            FROM tasks t
            INNER JOIN batchs b ON b.id = t.batchs_id
            WHERE t.code = ? AND t.deleted_at IS NULL AND b.deleted_at IS NULL
            """,
            (code,),
        ).fetchone()

    def update_task_remark(self, task_code: str, remark: str) -> sqlite3.Row | None:
        self._conn.execute(
            "UPDATE tasks SET remark = ? WHERE code = ? AND deleted_at IS NULL",
            (remark, task_code),
        )
        self._conn.commit()
        return self.get_task_by_code(task_code)

    def get_default_customer_id(self) -> int:
        row = self._conn.execute(
            "SELECT id FROM customers WHERE code = ? AND deleted_at IS NULL LIMIT 1",
            (DEFAULT_CUSTOMER_CODE,),
        ).fetchone()
        if row is None:
            self.ensure_seed_data()
            row = self._conn.execute(
                "SELECT id FROM customers WHERE code = ? AND deleted_at IS NULL LIMIT 1",
                (DEFAULT_CUSTOMER_CODE,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to resolve default customer ID")
        return int(row["id"])

    # ------------------------------------------------------------------
    # generic master data
    # ------------------------------------------------------------------
    def list_customers(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM customers
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()

    def create_customer(
        self,
        name: str,
        code: str,
        description: str | None,
        email: str | None,
        phone: str | None,
    ) -> sqlite3.Row:
        self._conn.execute(
            """
            INSERT INTO customers (name, code, description, email, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, code, description, email, phone),
        )
        self._conn.commit()
        return self._conn.execute(
            "SELECT * FROM customers WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()

    def list_devices(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM devices
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()

    def create_device(
        self,
        name: str,
        code: str,
        device_type: str,
        location: str | None,
        is_active: bool = True,
        is_deletable: bool = True,
    ) -> sqlite3.Row:
        self._conn.execute(
            """
            INSERT INTO devices (name, code, type, location, is_active, is_deletable)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, code, device_type, location, int(is_active), int(is_deletable)),
        )
        self._conn.commit()
        return self._conn.execute(
            "SELECT * FROM devices WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()

    def list_settings(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            """
            SELECT *
            FROM settings
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()

    def upsert_setting(
        self,
        name: str,
        setting_key: str,
        setting_value: str,
        description: str | None = None,
        is_deletable: bool = True,
    ) -> sqlite3.Row:
        now = datetime.now().isoformat()
        self._conn.execute(
            """
            INSERT INTO settings (name, description, setting_key, setting_value, is_deletable, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                setting_value = excluded.setting_value,
                is_deletable = excluded.is_deletable,
                updated_at = excluded.updated_at
            """,
            (name, description, setting_key, setting_value, int(is_deletable), now, now),
        )
        self._conn.commit()
        return self._conn.execute(
            "SELECT * FROM settings WHERE setting_key = ? LIMIT 1",
            (setting_key,),
        ).fetchone()

    @staticmethod
    def make_task_code(batch_code: str) -> str:
        return f"{batch_code}-T-{uuid.uuid4().hex[:10].upper()}"
