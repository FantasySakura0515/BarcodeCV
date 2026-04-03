import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("barcodecv.database")

SCHEMA_SQL = """
-- ============================================================
-- Legacy tables (kept for CLI/pipeline backward compatibility)
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_sessions (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    config_snapshot TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS scan_records (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT NOT NULL,
    timestamp            TEXT NOT NULL,
    detection_confidence REAL,
    bbox_x1              INTEGER,
    bbox_y1              INTEGER,
    bbox_x2              INTEGER,
    bbox_y2              INTEGER,
    decoded_content      TEXT,
    decode_success       INTEGER NOT NULL DEFAULT 0,
    decoder_used         TEXT,
    decode_time_ms       REAL,
    decode_error         TEXT,
    image_source         TEXT,
    wide_image_path      TEXT,
    closeup_image_path   TEXT,
    camera_distance_mm   REAL,
    remark               TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
);

CREATE TABLE IF NOT EXISTS calibration_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    distance_mm       REAL NOT NULL,
    sharpness_score   REAL,
    decode_success    INTEGER NOT NULL DEFAULT 0,
    decode_time_ms    REAL,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scan_records_session
    ON scan_records(session_id);
CREATE INDEX IF NOT EXISTS idx_scan_records_content
    ON scan_records(decoded_content);
CREATE INDEX IF NOT EXISTS idx_scan_records_timestamp
    ON scan_records(timestamp);

CREATE TABLE IF NOT EXISTS box_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    box_bbox_x1      INTEGER,
    box_bbox_y1      INTEGER,
    box_bbox_x2      INTEGER,
    box_bbox_y2      INTEGER,
    box_area         REAL,
    status           TEXT NOT NULL,
    scan_record_id   INTEGER,
    decoded_content  TEXT,
    overlap_ratio    REAL,
    wide_image_path  TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES scan_sessions(id),
    FOREIGN KEY (scan_record_id) REFERENCES scan_records(id)
);

CREATE INDEX IF NOT EXISTS idx_box_records_session ON box_records(session_id);
CREATE INDEX IF NOT EXISTS idx_box_records_status  ON box_records(status);

CREATE TABLE IF NOT EXISTS model_registry (
    id             TEXT PRIMARY KEY,
    model_name     TEXT NOT NULL,
    model_type     TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    framework      TEXT NOT NULL,
    model_path     TEXT,
    is_active      INTEGER NOT NULL DEFAULT 0,
    remark         TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_registry_type ON model_registry(model_type);
CREATE INDEX IF NOT EXISTS idx_model_registry_active ON model_registry(is_active);

-- ============================================================
-- v1.0 business schema (docs/database.md)
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name        TEXT     NOT NULL,
    code        TEXT     NOT NULL,
    description TEXT,
    email       TEXT,
    phone       TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  DATETIME,
    CONSTRAINT uq_customers_code  UNIQUE (code),
    CONSTRAINT uq_customers_email UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS devices (
    id           INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name         TEXT     NOT NULL,
    code         TEXT     NOT NULL,
    type         TEXT     NOT NULL,
    location     TEXT,
    is_active    INTEGER  NOT NULL DEFAULT 1,
    is_deletable INTEGER  NOT NULL DEFAULT 1,
    last_seen_at DATETIME,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at   DATETIME,
    CONSTRAINT uq_devices_code      UNIQUE (code),
    CONSTRAINT ck_devices_is_active CHECK (is_active IN (0, 1)),
    CONSTRAINT ck_devices_deletable CHECK (is_deletable IN (0, 1))
);

CREATE TABLE IF NOT EXISTS batchs (
    id          INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER  NOT NULL,
    name        TEXT     NOT NULL,
    code        TEXT     NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  DATETIME,
    CONSTRAINT uq_batchs_code UNIQUE (code),
    CONSTRAINT fk_batchs_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    batchs_id       INTEGER  NOT NULL,
    code            TEXT     NOT NULL,
    status          TEXT     NOT NULL DEFAULT 'pending',
    data_url        TEXT,
    box_expected    TEXT,
    matrix_expected TEXT,
    box_detected    TEXT,
    matrix_detected TEXT,
    remark          TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      DATETIME,
    CONSTRAINT uq_tasks_code UNIQUE (code),
    CONSTRAINT ck_tasks_status CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT fk_tasks_batch
        FOREIGN KEY (batchs_id)
        REFERENCES batchs (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    id            INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name          TEXT     NOT NULL,
    description   TEXT,
    setting_key   TEXT     NOT NULL,
    setting_value TEXT     NOT NULL,
    is_deletable  INTEGER  NOT NULL DEFAULT 1,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at    DATETIME,
    CONSTRAINT uq_settings_key UNIQUE (setting_key),
    CONSTRAINT ck_settings_deletable CHECK (is_deletable IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_customers_deleted ON customers (deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_code ON customers (code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_code ON devices (code);
CREATE INDEX IF NOT EXISTS idx_devices_active ON devices (is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_batchs_code ON batchs (code);
CREATE INDEX IF NOT EXISTS idx_batchs_customer_id ON batchs (customer_id);
CREATE INDEX IF NOT EXISTS idx_batchs_deleted ON batchs (deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_code ON tasks (code);
CREATE INDEX IF NOT EXISTS idx_tasks_batchs_id ON tasks (batchs_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted ON tasks (deleted_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_key ON settings (setting_key);

CREATE TRIGGER IF NOT EXISTS trg_customers_updated_at
AFTER UPDATE ON customers
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_devices_updated_at
AFTER UPDATE ON devices
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE devices SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_batchs_updated_at
AFTER UPDATE ON batchs
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE batchs SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_settings_updated_at
AFTER UPDATE ON settings
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""


class DatabaseManager:
    """Manages SQLite database connection and schema."""

    def __init__(self, db_path: str, wal_mode: bool = True):
        self._db_path = db_path
        self._wal_mode = wal_mode
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        if self._wal_mode:
            self._conn.execute("PRAGMA journal_mode=WAL")
        logger.info("Connected to database: %s", self._db_path)
        return self._conn

    def initialize_schema(self) -> None:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        self._conn.executescript(SCHEMA_SQL)
        self._ensure_column("scan_records", "remark", "TEXT")
        self._ensure_column("tasks", "remark", "TEXT")
        self._conn.commit()
        logger.info("Database schema initialized")

    def _ensure_column(self, table_name: str, column_name: str, column_sql: str) -> None:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")

        rows = self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing_columns = {row["name"] for row in rows}
        if column_name not in existing_columns:
            self._conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
            )

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    def __enter__(self):
        self.connect()
        self.initialize_schema()
        return self

    def __exit__(self, *args):
        self.close()
