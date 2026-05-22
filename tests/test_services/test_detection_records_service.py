from backend.services.detection_records_service import DetectionRecordsService


class StubBusinessRepository:
    def list_batches(self, limit: int = 50, offset: int = 0):
        return [
            {
                "id": 1,
                "code": "RID-001",
                "name": "Batch 1",
                "description": "demo",
                "created_at": "2026-04-03T12:00:00",
                "customer_id": 7,
                "customer_name": "ACME",
                "customer_code": "C-001",
                "object_count": 1,
                "barcode_success_count": 1,
                "ocr_success_count": 0,
            }
        ]

    def get_batch_by_code(self, code: str):
        if code != "RID-001":
            return None
        return {
            "id": 1,
            "code": "RID-001",
            "name": "Batch 1",
            "description": "demo",
            "created_at": "2026-04-03T12:00:00",
            "customer_id": 7,
            "customer_name": "ACME",
            "customer_code": "C-001",
        }

    def list_tasks_by_batch_id(self, batch_id: int):
        return [
            {
                "id": 9,
                "code": "BID-001",
                "box_detected": '{"bbox":{"x1":1,"y1":2,"x2":3,"y2":4},"confidenceScore":0.95}',
                "matrix_detected": '{"barcodeValue":"DM-001","barcodeType":"DataMatrix","ocrText":null}',
                "data_url": "/api/images/demo.png",
                "remark": "checked",
                "created_at": "2026-04-03T12:00:00",
                "updated_at": "2026-04-03T12:01:00",
            }
        ]

    def get_task_by_code(self, code: str):
        if code != "BID-001":
            return None
        row = self.list_tasks_by_batch_id(1)[0].copy()
        row["batch_code"] = "RID-001"
        return row

    def update_task_remark(self, task_code: str, remark: str):
        if task_code != "BID-001":
            return None
        row = self.get_task_by_code(task_code)
        row["remark"] = remark
        return row


class StubModelService:
    def get_active_model(self, model_type: str):
        assert model_type == "opencv"
        return {"id": "model-1", "modelName": "OpenCV", "modelVersion": "v1"}


def test_list_batches_builds_nested_objects_payloads():
    service = DetectionRecordsService.__new__(DetectionRecordsService)
    service._biz_repo = StubBusinessRepository()
    service._model_service = StubModelService()

    payload = service.list_batches(limit=5)

    assert len(payload) == 1
    assert payload[0]["rid"] == "RID-001"
    assert payload[0]["customer"]["name"] == "ACME"
    assert payload[0]["objects"][0]["bid"] == "BID-001"


def test_update_object_remark_returns_updated_object_payload():
    service = DetectionRecordsService.__new__(DetectionRecordsService)
    service._biz_repo = StubBusinessRepository()
    service._model_service = StubModelService()

    payload = service.update_object_remark("BID-001", "verified")

    assert payload is not None
    assert payload["bid"] == "BID-001"
    assert payload["remark"] == "verified"
