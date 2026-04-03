from backend.services.detection_presenter import (
    build_batch_detail,
    build_batch_list_item,
    build_object_dict,
    summarize_detection_objects,
)


def test_summarize_detection_objects_marks_missing_datamatrix():
    summary = summarize_detection_objects([
        {"barcodeValue": "DM-001"},
        {"barcodeValue": None},
    ])

    assert summary["object_count"] == 2
    assert summary["datamatrix_success_count"] == 1
    assert summary["requires_reposition"] is True


def test_build_object_dict_maps_repository_payload_to_api_shape():
    row = {
        "id": 7,
        "code": "BID-001",
        "box_detected": '{"bbox": {"x1": 10, "y1": 20, "x2": 30, "y2": 40}, "confidenceScore": 0.91}',
        "matrix_detected": '{"barcodeValue": "DM-001", "barcodeType": "DataMatrix", "ocrText": null}',
        "data_url": "/api/images/demo.png",
        "remark": "checked",
        "created_at": "2026-04-03T10:00:00",
        "updated_at": "2026-04-03T10:05:00",
    }
    model = {"id": "model-1", "modelName": "OpenCV", "modelVersion": "v1"}

    payload = build_object_dict(row=row, rid="RID-001", model=model)

    assert payload["bid"] == "BID-001"
    assert payload["rid"] == "RID-001"
    assert payload["bbox"] == {"x1": 10, "y1": 20, "x2": 30, "y2": 40}
    assert payload["barcodeValue"] == "DM-001"
    assert payload["imagePath"] == "/api/images/demo.png"


def test_build_batch_payloads_preserve_customer_and_counts():
    row = {
        "code": "RID-001",
        "name": "Demo Batch",
        "description": "sample",
        "customer_id": 3,
        "customer_name": "ACME",
        "customer_code": "C-001",
        "object_count": 5,
        "barcode_success_count": 4,
        "ocr_success_count": 2,
        "created_at": "2026-04-03T10:00:00",
    }
    model = {"id": "model-1"}
    objects = [
        {"barcodeValue": "DM-001", "ocrText": None},
        {"barcodeValue": None, "ocrText": "ABC"},
    ]

    list_payload = build_batch_list_item(row=row, model=model, objects=objects)
    detail_payload = build_batch_detail(batch=row, model=model, objects=objects)

    assert list_payload["customer"]["name"] == "ACME"
    assert list_payload["objectCount"] == 5
    assert detail_payload["barcodeSuccessCount"] == 1
    assert detail_payload["ocrSuccessCount"] == 1
