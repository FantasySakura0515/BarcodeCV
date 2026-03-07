from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3
from pathlib import Path
import uuid

import cv2
import numpy as np

from ..database.repository import ScanRecord, ScanRepository
from ..decoding.direct_scanner import ScanResult
from ..detection.box_detector import BoxDetector
from ..detection.opencv_datamatrix_detector import OpenCVDataMatrixDetector, OpenCVDataMatrixResult
from ..detection.preprocessor import preprocess_for_detection
from ..detection.spatial_matcher import SpatialMatcher
from ..services.model_service import ModelService


@dataclass
class DetectionRunResult:
    rid: str
    image_path: str
    objects: list[dict]
    source_image: dict[str, int]


@dataclass
class DetectionPreviewResult:
    rid: str
    image_path: str | None
    objects: list[dict]
    source_image: dict[str, int]


class DetectionService:
    def __init__(self, conn: sqlite3.Connection, config: dict):
        self._conn = conn
        self._config = config
        self._repo = ScanRepository(conn)
        self._model_service = ModelService(conn)
        self._detector = OpenCVDataMatrixDetector.from_config(config)
        self._fast_detector = OpenCVDataMatrixDetector.from_config(config, fast=True)
        self._box_detection_enabled = config.get("box_detection", {}).get("enabled", True)
        self._box_detector = BoxDetector.from_config(config) if self._box_detection_enabled else None
        self._spatial_matcher = SpatialMatcher.from_config(config) if self._box_detection_enabled else None
        self._output_dir = Path(config.get("system", {}).get("image_output_dir", "./output/images"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run_detection(self, file_bytes: bytes, filename: str, model_type: str = "opencv") -> DetectionRunResult:
        image = self._decode_image(file_bytes)
        return self.run_detection_on_image(
            image=image,
            filename=filename,
            model_type=model_type,
            image_source="upload",
        )

    def run_detection_on_image(
        self,
        image: np.ndarray,
        filename: str,
        model_type: str = "opencv",
        image_source: str = "upload",
        camera_id: str | None = None,
    ) -> DetectionRunResult:
        if model_type != "opencv":
            raise ValueError("目前僅支援 opencv 檢測模型")

        rid = uuid.uuid4().hex[:8].upper()
        now = datetime.now().isoformat()
        model = self._model_service.get_active_model(model_type)

        input_path = self._save_image(image, f"{rid}_input.png")
        detections = self._detect_objects(image, fast=False)
        annotated = self._draw_object_overlays(image, detections)
        annotated_path = self._save_image(annotated, f"{rid}_annotated.png")

        self._repo.insert_session(
            rid,
            config={
                "source": image_source,
                "filename": filename,
                "modelType": model_type,
                "cameraId": camera_id,
                "inputImage": input_path,
                "annotatedImage": annotated_path,
            },
        )

        objects = self._build_detection_objects(
            rid=rid,
            now=now,
            detections=detections,
            model=model,
            input_path=input_path,
            annotated_path=annotated_path,
            image_source=image_source,
            camera_id=camera_id,
            persist=True,
        )

        return DetectionRunResult(
            rid=rid,
            image_path=annotated_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
        )

    def preview_detection_on_image(
        self,
        image: np.ndarray,
        filename: str,
        model_type: str = "opencv",
        image_source: str = "preview",
        camera_id: str | None = None,
        save_preview_image: bool = False,
    ) -> DetectionPreviewResult:
        if model_type != "opencv":
            raise ValueError("目前僅支援 opencv 檢測模型")

        rid = f"LIVE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now().isoformat()
        model = self._model_service.get_active_model(model_type)

        input_path = self._save_image(image, f"{rid}_{Path(filename).stem}_preview.png") if save_preview_image else None
        detections = self._detect_objects(image, fast=True)
        objects = self._build_detection_objects(
            rid=rid,
            now=now,
            detections=detections,
            model=model,
            input_path=input_path,
            annotated_path=input_path,
            image_source=image_source,
            camera_id=camera_id,
            persist=False,
        )

        return DetectionPreviewResult(
            rid=rid,
            image_path=input_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
        )

    def _detect_objects(self, image: np.ndarray, fast: bool) -> list[OpenCVDataMatrixResult]:
        detector = self._fast_detector if fast else self._detector
        dm_detections = detector.detect_and_decode(image)

        if not self._box_detection_enabled or self._box_detector is None or self._spatial_matcher is None:
            return dm_detections

        processed = preprocess_for_detection(image)
        boxes = self._box_detector.detect(processed)
        if not boxes:
            return dm_detections

        scan_results = [
            ScanResult(
                content=item.content,
                bbox=item.bbox,
                scanner_used=item.decoder_used,
                scan_time_ms=item.scan_time_ms,
                success=bool(item.content),
            )
            for item in dm_detections
            if item.content
        ]
        match_results = self._spatial_matcher.match(boxes, scan_results)

        merged: list[OpenCVDataMatrixResult] = []
        matched_keys: set[tuple[str, tuple[int, int, int, int]]] = set()

        for match in match_results:
            if match.scan_result is not None:
                matched_keys.add((match.scan_result.content, tuple(int(v) for v in match.scan_result.bbox)))
                merged.append(
                    OpenCVDataMatrixResult(
                        content=match.scan_result.content,
                        bbox=match.box.bbox,
                        confidence=max(0.9, match.overlap_ratio),
                        decoder_used=match.scan_result.scanner_used,
                        detection_source="box-matched",
                        scan_time_ms=match.scan_result.scan_time_ms,
                    )
                )
            else:
                merged.append(
                    OpenCVDataMatrixResult(
                        content="",
                        bbox=match.box.bbox,
                        confidence=0.35,
                        decoder_used="box-detector",
                        detection_source="box-only",
                        scan_time_ms=0.0,
                    )
                )

        for item in dm_detections:
            key = (item.content, tuple(int(v) for v in item.bbox))
            if item.content and key in matched_keys:
                continue
            merged.append(item)

        return merged

    @staticmethod
    def _draw_object_overlays(image: np.ndarray, detections: list[OpenCVDataMatrixResult]) -> np.ndarray:
        output = image.copy()
        for index, detection in enumerate(detections, start=1):
            x1, y1, x2, y2 = detection.bbox
            decoded = bool(detection.content)
            color = (34, 197, 94) if decoded else (0, 191, 255)
            label = detection.content if decoded else f"Box {index}"
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            text_y = y1 - 10 if y1 > 24 else y1 + 22
            cv2.putText(
                output,
                label,
                (x1, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        return output

    def _build_detection_objects(
        self,
        rid: str,
        now: str,
        detections: list,
        model: dict,
        input_path: str | None,
        annotated_path: str | None,
        image_source: str,
        camera_id: str | None,
        persist: bool,
    ) -> list[dict]:
        objects: list[dict] = []
        for index, detection in enumerate(detections, start=1):
            row_id: int | None = None
            bid = f"LIVE-{index:03d}"

            if persist:
                record = ScanRecord(
                    session_id=rid,
                    timestamp=now,
                    detection_confidence=detection.confidence,
                    bbox_x1=detection.bbox[0],
                    bbox_y1=detection.bbox[1],
                    bbox_x2=detection.bbox[2],
                    bbox_y2=detection.bbox[3],
                    decoded_content=detection.content,
                    decode_success=bool(detection.content),
                    decoder_used=detection.decoder_used,
                    decode_time_ms=detection.scan_time_ms,
                    image_source=camera_id or detection.detection_source or image_source,
                    wide_image_path=annotated_path,
                    closeup_image_path=input_path,
                )
                row_id = self._repo.insert_scan(record)
                bid = f"BID-{row_id:06d}"

            objects.append(
                {
                    "id": str(row_id or index),
                    "rid": rid,
                    "bid": bid,
                    "bbox": {
                        "x1": int(detection.bbox[0]),
                        "y1": int(detection.bbox[1]),
                        "x2": int(detection.bbox[2]),
                        "y2": int(detection.bbox[3]),
                    },
                    "barcodeValue": detection.content or None,
                    "barcodeType": "DataMatrix" if detection.content else None,
                    "ocrText": None,
                    "confidenceScore": float(detection.confidence or 0.0),
                    "modelId": model["id"],
                    "model": model,
                    "imagePath": annotated_path,
                    "remark": None,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )

        return objects

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[dict]:
        model = self._model_service.get_active_model("opencv")
        rows = self._conn.execute(
            """
            SELECT
                s.id AS rid,
                s.started_at AS created_at,
                COUNT(r.id) AS object_count,
                SUM(CASE WHEN r.decode_success = 1 THEN 1 ELSE 0 END) AS barcode_success_count
            FROM scan_sessions s
            LEFT JOIN scan_records r ON r.session_id = s.id
            GROUP BY s.id, s.started_at
            ORDER BY s.started_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        batches: list[dict] = []
        for row in rows:
            batches.append(
                {
                    "rid": row["rid"],
                    "objectCount": row["object_count"] or 0,
                    "barcodeSuccessCount": row["barcode_success_count"] or 0,
                    "ocrSuccessCount": 0,
                    "model": model,
                    "createdAt": row["created_at"],
                    "objects": self.list_objects_by_rid(row["rid"], model=model),
                }
            )
        return batches

    def get_batch(self, rid: str) -> dict | None:
        model = self._model_service.get_active_model("opencv")
        session = self._conn.execute(
            "SELECT id, started_at FROM scan_sessions WHERE id = ?",
            (rid,),
        ).fetchone()
        if session is None:
            return None

        objects = self.list_objects_by_rid(rid, model=model)
        barcode_success_count = sum(1 for item in objects if item["barcodeValue"])
        return {
            "rid": rid,
            "objectCount": len(objects),
            "barcodeSuccessCount": barcode_success_count,
            "ocrSuccessCount": 0,
            "model": model,
            "createdAt": session["started_at"],
            "objects": objects,
        }

    def get_object(self, bid: str) -> dict | None:
        row_id = self._parse_bid(bid)
        if row_id is None:
            return None
        row = self._conn.execute(
            "SELECT * FROM scan_records WHERE id = ?",
            (row_id,),
        ).fetchone()
        if row is None:
            return None
        model = self._model_service.get_active_model("opencv")
        return self._build_object_dict(row_id=row_id, rid=row["session_id"], row=row, model=model)

    def update_object_remark(self, bid: str, remark: str) -> dict | None:
        row_id = self._parse_bid(bid)
        if row_id is None:
            return None
        self._conn.execute(
            "UPDATE scan_records SET remark = ? WHERE id = ?",
            (remark, row_id),
        )
        self._conn.commit()
        return self.get_object(bid)

    def list_objects_by_rid(self, rid: str, model: dict | None = None) -> list[dict]:
        model = model or self._model_service.get_active_model("opencv")
        rows = self._conn.execute(
            "SELECT * FROM scan_records WHERE session_id = ? ORDER BY id ASC",
            (rid,),
        ).fetchall()
        return [
            self._build_object_dict(row_id=row["id"], rid=rid, row=row, model=model)
            for row in rows
        ]

    @staticmethod
    def _parse_bid(bid: str) -> int | None:
        if not bid.startswith("BID-"):
            return None
        try:
            return int(bid.split("-", 1)[1])
        except ValueError:
            return None

    def _decode_image(self, file_bytes: bytes) -> np.ndarray:
        array = np.frombuffer(file_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("無法解析上傳影像")
        return image

    def _save_image(self, image: np.ndarray, file_name: str) -> str:
        path = self._output_dir / file_name
        cv2.imwrite(str(path), image)
        return f"/api/images/{file_name}"

    @staticmethod
    def _build_object_dict(row_id: int, rid: str, row: sqlite3.Row | dict, model: dict) -> dict:
        created_at = row["created_at"] if "created_at" in row.keys() else row["timestamp"]
        return {
            "id": str(row_id),
            "rid": rid,
            "bid": f"BID-{row_id:06d}",
            "bbox": {
                "x1": int(row["bbox_x1"] or 0),
                "y1": int(row["bbox_y1"] or 0),
                "x2": int(row["bbox_x2"] or 0),
                "y2": int(row["bbox_y2"] or 0),
            },
            "barcodeValue": row["decoded_content"] or None,
            "barcodeType": "DataMatrix" if row["decoded_content"] else None,
            "ocrText": None,
            "confidenceScore": float(row["detection_confidence"] or 0.0),
            "modelId": model["id"],
            "model": model,
            "imagePath": row["wide_image_path"] or None,
            "remark": row["remark"] if "remark" in row.keys() else None,
            "createdAt": created_at,
            "updatedAt": created_at,
        }
