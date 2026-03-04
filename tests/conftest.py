import sqlite3

import numpy as np
import pytest

from src.database.db_manager import SCHEMA_SQL


@pytest.fixture
def sample_image():
    """A 640x640 BGR test image."""
    return np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)


@pytest.fixture
def in_memory_db():
    """In-memory SQLite database with schema initialized."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()
