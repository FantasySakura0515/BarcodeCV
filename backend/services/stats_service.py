import sqlite3

from .detection_service import DetectionService
from .model_service import ModelService


class StatsService:
    def __init__(self, conn: sqlite3.Connection, config: dict):
        self._conn = conn
        self._config = config
        self._detection_service = DetectionService(conn, config)
        self._model_service = ModelService(conn)

    def get_summary(self) -> dict:
        scan_row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total_objects,
                SUM(CASE WHEN decode_success = 1 THEN 1 ELSE 0 END) AS successful_decodes
            FROM scan_records
            """
        ).fetchone()
        round_row = self._conn.execute(
            "SELECT COUNT(*) AS total_rounds FROM scan_sessions"
        ).fetchone()
        active_model_row = self._conn.execute(
            "SELECT COUNT(*) AS active_models FROM model_registry WHERE is_active = 1"
        ).fetchone()
        trends = self._conn.execute(
            """
            SELECT
                substr(started_at, 1, 10) AS label,
                COUNT(*) AS rounds,
                (
                    SELECT COUNT(*)
                    FROM scan_records r
                    WHERE r.session_id IN (
                        SELECT s2.id FROM scan_sessions s2 WHERE substr(s2.started_at, 1, 10) = substr(s.started_at, 1, 10)
                    )
                ) AS objects
            FROM scan_sessions s
            GROUP BY substr(started_at, 1, 10)
            ORDER BY label DESC
            LIMIT 7
            """
        ).fetchall()

        total_objects = scan_row["total_objects"] or 0
        successful_decodes = scan_row["successful_decodes"] or 0

        return {
            "totalRounds": round_row["total_rounds"] or 0,
            "totalObjects": total_objects,
            "barcodeSuccessRate": round((successful_decodes / total_objects) * 100, 2) if total_objects else 0.0,
            "ocrSuccessRate": 0.0,
            "activeModelCount": active_model_row["active_models"] or 0,
            "recentRounds": self._detection_service.list_batches(limit=5),
            "trends": [
                {
                    "label": row["label"],
                    "rounds": row["rounds"] or 0,
                    "objects": row["objects"] or 0,
                }
                for row in reversed(trends)
            ],
        }
