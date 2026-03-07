from datetime import datetime
import sqlite3


DEFAULT_MODELS = [
    {
        "id": "opencv-dm-v1",
        "model_name": "OpenCV DataMatrix Detector",
        "model_type": "opencv",
        "model_version": "1.0.0",
        "framework": "opencv+pylibdmtx+zxing-cpp",
        "model_path": "builtin://opencv-datamatrix-detector",
        "is_active": 1,
        "remark": "OpenCV candidate detection with multi-decoder fallback for full-frame DataMatrix scanning.",
    }
]


class ModelService:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def ensure_seed_models(self) -> None:
        now = datetime.now().isoformat()
        for model in DEFAULT_MODELS:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO model_registry
                (id, model_name, model_type, model_version, framework, model_path, is_active, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model["id"],
                    model["model_name"],
                    model["model_type"],
                    model["model_version"],
                    model["framework"],
                    model["model_path"],
                    model["is_active"],
                    model["remark"],
                    now,
                    now,
                ),
            )
        self._conn.commit()

    def list_models(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM model_registry ORDER BY is_active DESC, updated_at DESC"
        ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_active_model(self, model_type: str = "opencv") -> dict:
        row = self._conn.execute(
            "SELECT * FROM model_registry WHERE model_type = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1",
            (model_type,),
        ).fetchone()
        if row is None:
            self.ensure_seed_models()
            row = self._conn.execute(
                "SELECT * FROM model_registry WHERE model_type = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1",
                (model_type,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"No active model found for model_type={model_type}")
        return self._row_to_model(row)

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "modelName": row["model_name"],
            "modelType": row["model_type"],
            "modelVersion": row["model_version"],
            "framework": row["framework"],
            "modelPath": row["model_path"] or "",
            "isActive": bool(row["is_active"]),
            "remark": row["remark"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
