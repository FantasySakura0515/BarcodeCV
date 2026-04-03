import sqlite3

from ..database.business_repository import BusinessRepository
from .detection_records_service import DetectionRecordsService
from .model_service import ModelService


class StatsService:
    def __init__(self, conn: sqlite3.Connection, config: dict):
        self._conn = conn
        self._config = config
        self._biz_repo = BusinessRepository(conn)
        self._biz_repo.ensure_seed_data()
        self._records_service = DetectionRecordsService(conn)
        self._model_service = ModelService(conn)

    def get_summary(self) -> dict:
        task_row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total_objects,
                SUM(
                    CASE
                        WHEN json_extract(matrix_detected, '$.barcodeValue') IS NOT NULL
                             AND json_extract(matrix_detected, '$.barcodeValue') <> ''
                        THEN 1
                        ELSE 0
                    END
                ) AS successful_decodes,
                SUM(
                    CASE
                        WHEN json_extract(matrix_detected, '$.ocrText') IS NOT NULL
                             AND json_extract(matrix_detected, '$.ocrText') <> ''
                        THEN 1
                        ELSE 0
                    END
                ) AS ocr_successes
            FROM tasks
            WHERE deleted_at IS NULL
            """
        ).fetchone()
        round_row = self._conn.execute(
            "SELECT COUNT(*) AS total_rounds FROM batchs WHERE deleted_at IS NULL"
        ).fetchone()
        active_model_row = self._conn.execute(
            "SELECT COUNT(*) AS active_models FROM model_registry WHERE is_active = 1"
        ).fetchone()
        trends = self._conn.execute(
            """
            SELECT
                substr(created_at, 1, 10) AS label,
                COUNT(*) AS rounds,
                (
                    SELECT COUNT(*)
                    FROM tasks t
                    WHERE t.batchs_id IN (
                        SELECT b2.id FROM batchs b2 WHERE substr(b2.created_at, 1, 10) = substr(b.created_at, 1, 10)
                    )
                    AND t.deleted_at IS NULL
                ) AS objects
            FROM batchs b
            WHERE deleted_at IS NULL
            GROUP BY substr(created_at, 1, 10)
            ORDER BY label DESC
            LIMIT 7
            """
        ).fetchall()

        total_objects = task_row["total_objects"] or 0
        successful_decodes = task_row["successful_decodes"] or 0
        ocr_successes = task_row["ocr_successes"] or 0

        return {
            "totalRounds": round_row["total_rounds"] or 0,
            "totalObjects": total_objects,
            "barcodeSuccessRate": round((successful_decodes / total_objects) * 100, 2) if total_objects else 0.0,
            "ocrSuccessRate": round((ocr_successes / total_objects) * 100, 2) if total_objects else 0.0,
            "activeModelCount": active_model_row["active_models"] or 0,
            "recentRounds": self._records_service.list_batches(limit=5),
            "trends": [
                {
                    "label": row["label"],
                    "rounds": row["rounds"] or 0,
                    "objects": row["objects"] or 0,
                }
                for row in reversed(trends)
            ],
        }
