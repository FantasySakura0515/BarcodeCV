from __future__ import annotations

import json
import math
from typing import Any, Mapping

from ..decoding.direct_scanner import sanitize_decoded_text


def load_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def summarize_detection_objects(objects: list[dict[str, Any]]) -> dict[str, int | bool | str]:
    object_count = len(objects)
    datamatrix_success_count = sum(1 for item in objects if (item.get("barcodeValue") or "").strip())
    requires_reposition = object_count != datamatrix_success_count

    if requires_reposition:
        placement_hint = (
            f"偵測到 {object_count} 個物件，但僅成功解析 {datamatrix_success_count} 個 DataMatrix。"
            " 請重新擺放物件後再次辨識。"
        )
    else:
        placement_hint = (
            f"偵測到 {object_count} 個物件，且成功解析 {datamatrix_success_count} 個 DataMatrix。"
        )

    return {
        "object_count": object_count,
        "datamatrix_success_count": datamatrix_success_count,
        "requires_reposition": requires_reposition,
        "placement_hint": placement_hint,
    }


def build_object_dict(row: Mapping[str, Any], rid: str, model: dict[str, Any]) -> dict[str, Any]:
    keys = row.keys()
    box_detected = load_json(row["box_detected"] if "box_detected" in keys else None)
    matrix_detected = load_json(row["matrix_detected"] if "matrix_detected" in keys else None)
    bbox = box_detected.get("bbox") or {}
    raw_confidence = box_detected.get("confidenceScore") or 0.0
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    if not math.isfinite(confidence):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    barcode_value = sanitize_decoded_text(matrix_detected.get("barcodeValue"))
    barcode_type = matrix_detected.get("barcodeType") if barcode_value else None

    return {
        "id": str(row["id"]),
        "rid": rid,
        "bid": row["code"],
        "bbox": {
            "x1": int(bbox.get("x1") or 0),
            "y1": int(bbox.get("y1") or 0),
            "x2": int(bbox.get("x2") or 0),
            "y2": int(bbox.get("y2") or 0),
        },
        "barcodeValue": barcode_value or None,
        "barcodeType": barcode_type,
        "ocrText": matrix_detected.get("ocrText"),
        "confidenceScore": confidence,
        "modelId": model["id"],
        "model": model,
        "imagePath": row["data_url"] if "data_url" in keys else None,
        "remark": row["remark"] if "remark" in keys else None,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def build_batch_list_item(
    row: Mapping[str, Any],
    model: dict[str, Any],
    objects: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "rid": row["code"],
        "name": row["name"],
        "description": row["description"],
        "customer": {
            "id": str(row["customer_id"]),
            "name": row["customer_name"],
            "code": row["customer_code"],
        },
        "objectCount": row["object_count"] or 0,
        "barcodeSuccessCount": row["barcode_success_count"] or 0,
        "ocrSuccessCount": row["ocr_success_count"] or 0,
        "model": model,
        "createdAt": row["created_at"],
        "objects": objects,
    }


def build_batch_detail(
    batch: Mapping[str, Any],
    model: dict[str, Any],
    objects: list[dict[str, Any]],
) -> dict[str, Any]:
    barcode_success_count = sum(1 for item in objects if item["barcodeValue"])
    ocr_success_count = sum(1 for item in objects if item["ocrText"])

    return {
        "rid": batch["code"],
        "name": batch["name"],
        "description": batch["description"],
        "customer": {
            "id": str(batch["customer_id"]),
            "name": batch["customer_name"],
            "code": batch["customer_code"],
        },
        "objectCount": len(objects),
        "barcodeSuccessCount": barcode_success_count,
        "ocrSuccessCount": ocr_success_count,
        "model": model,
        "createdAt": batch["created_at"],
        "objects": objects,
    }
