from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("barcodecv.database")


@dataclass
class ScanRecord:
    """A single scan result record."""

    session_id: str
    timestamp: str
    detection_confidence: float | None = None
    bbox_x1: int | None = None
    bbox_y1: int | None = None
    bbox_x2: int | None = None
    bbox_y2: int | None = None
    decoded_content: str | None = None
    decode_success: bool = False
    decoder_used: str | None = None
    decode_time_ms: float | None = None
    decode_error: str | None = None
    image_source: str | None = None  # "main"
    frame_image_path: str | None = None
    camera_distance_mm: float | None = None
    id: int | None = None


class ScanRepository:
    """CRUD operations for scan records."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert_session(
        self,
        session_id: str,
        config: dict | None = None,
        notes: str | None = None,
    ) -> str:
        self._conn.execute(
            "INSERT INTO scan_sessions (id, started_at, config_snapshot, notes) VALUES (?, ?, ?, ?)",
            (
                session_id,
                datetime.now().isoformat(),
                json.dumps(config) if config else None,
                notes,
            ),
        )
        self._conn.commit()
        return session_id

    def end_session(self, session_id: str) -> None:
        self._conn.execute(
            "UPDATE scan_sessions SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        )
        self._conn.commit()

    def insert_scan(self, record: ScanRecord) -> int:
        cursor = self._conn.execute(
            """INSERT INTO scan_records
            (session_id, timestamp, detection_confidence,
             bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             decoded_content, decode_success, decoder_used,
             decode_time_ms, decode_error, image_source,
             frame_image_path, camera_distance_mm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.session_id,
                record.timestamp,
                record.detection_confidence,
                record.bbox_x1,
                record.bbox_y1,
                record.bbox_x2,
                record.bbox_y2,
                record.decoded_content,
                int(record.decode_success),
                record.decoder_used,
                record.decode_time_ms,
                record.decode_error,
                record.image_source,
                record.frame_image_path,
                record.camera_distance_mm,
            ),
        )
        self._conn.commit()
        row_id = cursor.lastrowid
        logger.debug("Inserted scan record id=%d content=%s", row_id, record.decoded_content)
        return row_id

    def get_scans_by_session(self, session_id: str) -> list[ScanRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM scan_records WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_all_scans(self, limit: int = 100, offset: int = 0) -> list[ScanRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM scan_records ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def search_by_content(self, query: str) -> list[ScanRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM scan_records WHERE decoded_content LIKE ? ORDER BY timestamp DESC",
            (f"%{query}%",),
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(decode_success) as successful,
                AVG(decode_time_ms) as avg_decode_time_ms
            FROM scan_records"""
        ).fetchone()
        return {
            "total_scans": row["total"],
            "successful_decodes": row["successful"],
            "avg_decode_time_ms": row["avg_decode_time_ms"],
            "success_rate": row["successful"] / row["total"] if row["total"] > 0 else 0,
        }

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ScanRecord:
        return ScanRecord(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            detection_confidence=row["detection_confidence"],
            bbox_x1=row["bbox_x1"],
            bbox_y1=row["bbox_y1"],
            bbox_x2=row["bbox_x2"],
            bbox_y2=row["bbox_y2"],
            decoded_content=row["decoded_content"],
            decode_success=bool(row["decode_success"]),
            decoder_used=row["decoder_used"],
            decode_time_ms=row["decode_time_ms"],
            decode_error=row["decode_error"],
            image_source=row["image_source"],
            frame_image_path=row["frame_image_path"],
            camera_distance_mm=row["camera_distance_mm"],
        )


# ---------------------------------------------------------------------------
# BoxRecord + BoxRepository
# ---------------------------------------------------------------------------

@dataclass
class BoxRecord:
    """Database record for one detected box and its DataMatrix pairing status."""

    session_id: str
    timestamp: str
    status: str                          # "matched" | "missing_datamatrix"
    box_bbox_x1: int | None = None
    box_bbox_y1: int | None = None
    box_bbox_x2: int | None = None
    box_bbox_y2: int | None = None
    box_area: float | None = None
    scan_record_id: int | None = None   # FK → scan_records.id
    decoded_content: str | None = None
    overlap_ratio: float | None = None
    frame_image_path: str | None = None
    id: int | None = None


class BoxRepository:
    """CRUD operations for box records."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert_box(self, record: BoxRecord) -> int:
        cursor = self._conn.execute(
            """INSERT INTO box_records
            (session_id, timestamp, box_bbox_x1, box_bbox_y1,
             box_bbox_x2, box_bbox_y2, box_area, status,
             scan_record_id, decoded_content, overlap_ratio, frame_image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.session_id,
                record.timestamp,
                record.box_bbox_x1,
                record.box_bbox_y1,
                record.box_bbox_x2,
                record.box_bbox_y2,
                record.box_area,
                record.status,
                record.scan_record_id,
                record.decoded_content,
                record.overlap_ratio,
                record.frame_image_path,
            ),
        )
        self._conn.commit()
        row_id = cursor.lastrowid
        logger.debug(
            "Inserted box record id=%d status=%s", row_id, record.status
        )
        return row_id

    def get_boxes_by_session(self, session_id: str) -> list[BoxRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM box_records WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        return [self._row_to_box(row) for row in cursor.fetchall()]

    def get_missing_boxes(self, session_id: str) -> list[BoxRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM box_records WHERE session_id = ? AND status = 'missing_datamatrix'",
            (session_id,),
        )
        return [self._row_to_box(row) for row in cursor.fetchall()]

    def get_box_statistics(self, session_id: str) -> dict:
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'matched' THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN status = 'missing_datamatrix' THEN 1 ELSE 0 END) as missing
            FROM box_records WHERE session_id = ?""",
            (session_id,),
        ).fetchone()
        total = row["total"] or 0
        matched = row["matched"] or 0
        return {
            "total_boxes": total,
            "matched": matched,
            "missing": row["missing"] or 0,
            "success_rate": matched / total if total > 0 else 0.0,
        }

    @staticmethod
    def _row_to_box(row: sqlite3.Row) -> BoxRecord:
        return BoxRecord(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            box_bbox_x1=row["box_bbox_x1"],
            box_bbox_y1=row["box_bbox_y1"],
            box_bbox_x2=row["box_bbox_x2"],
            box_bbox_y2=row["box_bbox_y2"],
            box_area=row["box_area"],
            status=row["status"],
            scan_record_id=row["scan_record_id"],
            decoded_content=row["decoded_content"],
            overlap_ratio=row["overlap_ratio"],
            frame_image_path=row["frame_image_path"],
        )
