import sqlite3

from backend.database.db_manager import DatabaseManager


def test_initialize_schema_migrates_legacy_scan_and_box_tables(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE scan_sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            config_snapshot TEXT,
            notes TEXT
        );

        CREATE TABLE scan_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            detection_confidence REAL,
            bbox_x1 INTEGER,
            bbox_y1 INTEGER,
            bbox_x2 INTEGER,
            bbox_y2 INTEGER,
            decoded_content TEXT,
            decode_success INTEGER NOT NULL DEFAULT 0,
            decoder_used TEXT,
            decode_time_ms REAL,
            decode_error TEXT,
            image_source TEXT,
            wide_image_path TEXT,
            closeup_image_path TEXT,
            camera_distance_mm REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE box_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            box_bbox_x1 INTEGER,
            box_bbox_y1 INTEGER,
            box_bbox_x2 INTEGER,
            box_bbox_y2 INTEGER,
            box_area REAL,
            status TEXT NOT NULL,
            scan_record_id INTEGER,
            decoded_content TEXT,
            overlap_ratio REAL,
            wide_image_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        INSERT INTO scan_sessions (id, started_at) VALUES ('session-1', '2026-04-03T00:00:00');
        INSERT INTO scan_records (
            session_id, timestamp, decoded_content, decode_success, image_source,
            wide_image_path, closeup_image_path, camera_distance_mm
        ) VALUES (
            'session-1', '2026-04-03T00:00:01', 'DM-001', 1, 'local',
            '/tmp/wide.jpg', '/tmp/close.jpg', 100.0
        );
        INSERT INTO box_records (
            session_id, timestamp, status, wide_image_path
        ) VALUES (
            'session-1', '2026-04-03T00:00:02', 'matched', '/tmp/wide.jpg'
        );
        """
    )
    conn.commit()
    conn.close()

    manager = DatabaseManager(str(db_path), wal_mode=False)
    manager.connect()
    manager.initialize_schema()
    migrated = manager.get_connection()

    scan_columns = {row["name"] for row in migrated.execute("PRAGMA table_info(scan_records)").fetchall()}
    assert "frame_image_path" in scan_columns
    assert "wide_image_path" not in scan_columns
    assert "closeup_image_path" not in scan_columns

    box_columns = {row["name"] for row in migrated.execute("PRAGMA table_info(box_records)").fetchall()}
    assert "frame_image_path" in box_columns
    assert "wide_image_path" not in box_columns

    scan_row = migrated.execute(
        "SELECT image_source, frame_image_path FROM scan_records WHERE decoded_content = 'DM-001'"
    ).fetchone()
    assert scan_row["image_source"] == "main"
    assert scan_row["frame_image_path"] == "/tmp/close.jpg"

    box_row = migrated.execute(
        "SELECT frame_image_path FROM box_records WHERE session_id = 'session-1'"
    ).fetchone()
    assert box_row["frame_image_path"] == "/tmp/wide.jpg"

    manager.close()
