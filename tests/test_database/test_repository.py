from datetime import datetime

from src.database.repository import ScanRecord, ScanRepository


class TestScanRepository:
    def test_insert_and_retrieve_scan(self, in_memory_db):
        repo = ScanRepository(in_memory_db)
        session_id = "test-session"
        repo.insert_session(session_id)

        record = ScanRecord(
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            detection_confidence=0.95,
            bbox_x1=100,
            bbox_y1=200,
            bbox_x2=300,
            bbox_y2=400,
            decoded_content="HELLO123",
            decode_success=True,
            decoder_used="zxing-cpp",
            decode_time_ms=25.5,
            image_source="local",
        )
        row_id = repo.insert_scan(record)
        assert row_id is not None

        scans = repo.get_scans_by_session(session_id)
        assert len(scans) == 1
        assert scans[0].decoded_content == "HELLO123"
        assert scans[0].decode_success is True

    def test_search_by_content(self, in_memory_db):
        repo = ScanRepository(in_memory_db)
        session_id = "test-session"
        repo.insert_session(session_id)

        for content in ["ABC123", "ABC456", "XYZ789"]:
            repo.insert_scan(ScanRecord(
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                decoded_content=content,
                decode_success=True,
            ))

        results = repo.search_by_content("ABC")
        assert len(results) == 2

    def test_statistics(self, in_memory_db):
        repo = ScanRepository(in_memory_db)
        session_id = "test-session"
        repo.insert_session(session_id)

        repo.insert_scan(ScanRecord(
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            decode_success=True,
            decode_time_ms=30.0,
        ))
        repo.insert_scan(ScanRecord(
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            decode_success=False,
            decode_time_ms=50.0,
        ))

        stats = repo.get_statistics()
        assert stats["total_scans"] == 2
        assert stats["successful_decodes"] == 1
        assert stats["success_rate"] == 0.5

    def test_end_session(self, in_memory_db):
        repo = ScanRepository(in_memory_db)
        session_id = "test-session"
        repo.insert_session(session_id)
        repo.end_session(session_id)

        row = in_memory_db.execute(
            "SELECT ended_at FROM scan_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        assert row["ended_at"] is not None
