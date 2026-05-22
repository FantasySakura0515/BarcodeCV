from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import sqlite3
from pathlib import Path
import uuid

import cv2
import numpy as np

from ..database.business_repository import BusinessRepository, DetectionTaskPayload
from ..decoding.direct_scanner import sanitize_decoded_text
from ..detection.box_detector import BoxDetector
from ..detection.opencv_datamatrix_detector import OpenCVDataMatrixDetector
from ..detection.spatial_matcher import SpatialMatcher
from ..services.model_service import ModelService
from .detection_pipeline import DetectionPipeline
from .detection_presenter import summarize_detection_objects

@dataclass
class DetectionRunResult:
    rid: str
    image_path: str
    objects: list[dict]
    source_image: dict[str, int]
    object_count: int
    datamatrix_success_count: int
    requires_reposition: bool
    placement_hint: str


@dataclass
class DetectionPreviewResult:
    rid: str
    image_path: str | None
    objects: list[dict]
    source_image: dict[str, int]
    object_count: int
    datamatrix_success_count: int
    requires_reposition: bool
    placement_hint: str


class DetectionService:
    def __init__(self, conn: sqlite3.Connection, config: dict):
        self._conn = conn
        self._config = config
        box_cfg = config.get("box_detection", {})
        detector_cfg = config.get("opencv_datamatrix", {})
        self._biz_repo = BusinessRepository(conn)
        self._biz_repo.ensure_seed_data()
        self._model_service = ModelService(conn)
        self._detector = OpenCVDataMatrixDetector.from_config(config)
        self._fast_detector = OpenCVDataMatrixDetector.from_config(config, fast=True)
        self._box_detection_enabled = box_cfg.get("enabled", True)
        self._box_detector = BoxDetector.from_config(config) if self._box_detection_enabled else None
        self._spatial_matcher = SpatialMatcher.from_config(config) if self._box_detection_enabled else None
        self._min_result_confidence = float(
            detector_cfg.get("min_output_confidence", 0.6)
        )
        self._square_ratio_max = float(box_cfg.get("square_ratio_max", 1.35))
        self._square_candidate_limit = max(1, int(box_cfg.get("square_candidate_limit", 180)))
        self._supplement_when_mismatch = bool(detector_cfg.get("supplement_when_mismatch", True))
        self._output_dir = Path(config.get("system", {}).get("image_output_dir", "./output/images"))
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._pipeline = DetectionPipeline(
            detector=self._detector,
            fast_detector=self._fast_detector,
            box_detection_enabled=self._box_detection_enabled,
            box_detector=self._box_detector,
            spatial_matcher=self._spatial_matcher,
            min_result_confidence=self._min_result_confidence,
            square_ratio_max=self._square_ratio_max,
            square_candidate_limit=self._square_candidate_limit,
            supplement_when_mismatch=self._supplement_when_mismatch,
        )

    def run_detection(self, file_bytes: bytes, filename: str, model_type: str = "opencv") -> DetectionRunResult:
        image = self.decode_upload_bytes(file_bytes=file_bytes, filename=filename, content_type=None)
        return self.run_detection_on_image(
            image=image,
            filename=filename,
            model_type=model_type,
            image_source="upload",
        )

    def decode_upload_bytes(
        self,
        file_bytes: bytes,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> np.ndarray:
        if self._is_pdf_upload(filename=filename, content_type=content_type):
            return self._decode_pdf_first_page(file_bytes)
        return self._decode_image(file_bytes)

    def run_detection_on_image(
        self,
        image: np.ndarray,
        filename: str,
        model_type: str = "opencv",
        image_source: str = "upload",
        camera_id: str | None = None,
    ) -> DetectionRunResult:
        if model_type != "opencv":
            raise ValueError("Only opencv model type is supported currently")

        rid = uuid.uuid4().hex[:8].upper()
        now = datetime.now().isoformat()
        model = self._normalize_model_payload(self._model_service.get_active_model(model_type), now)
        batch_id = self._biz_repo.create_batch(
            code=rid,
            name=f"Detection Batch {rid}",
            description=f"Auto-created from {image_source} source ({filename}).",
        )

        input_path = self._save_image(image, f"{rid}_input.png")
        detections = self._pipeline.apply_confidence_filter(
            self._pipeline.detect_objects(image, fast=False)
        )
        annotated = self._pipeline.draw_object_overlays(image, detections)
        annotated_path = self._save_image(annotated, f"{rid}_annotated.png")

        objects = self._build_detection_objects(
            batch_id=batch_id,
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
        summary = summarize_detection_objects(objects)

        return DetectionRunResult(
            rid=rid,
            image_path=annotated_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
            object_count=summary["object_count"],
            datamatrix_success_count=summary["datamatrix_success_count"],
            requires_reposition=summary["requires_reposition"],
            placement_hint=summary["placement_hint"],
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
            raise ValueError("Only opencv model type is supported currently")

        rid = f"LIVE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now().isoformat()
        model = self._normalize_model_payload(self._model_service.get_active_model(model_type), now)

        input_path = self._save_image(image, f"{rid}_{Path(filename).stem}_preview.png") if save_preview_image else None
        detections = self._pipeline.apply_confidence_filter(
            self._pipeline.detect_objects(image, fast=True, camera_id=camera_id)
        )
        objects = self._build_detection_objects(
            batch_id=0,
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
        summary = summarize_detection_objects(objects)

        return DetectionPreviewResult(
            rid=rid,
            image_path=input_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
            object_count=summary["object_count"],
            datamatrix_success_count=summary["datamatrix_success_count"],
            requires_reposition=summary["requires_reposition"],
            placement_hint=summary["placement_hint"],
        )

    def clear_live_known(self, camera_id: str) -> None:
        self._pipeline.clear_live_known(camera_id)

    def _merge_box_and_dm(self, boxes, dm_detections):
        pipeline = getattr(self, "_pipeline", None)
        if pipeline is None:
            pipeline = DetectionPipeline(
                detector=self._detector if hasattr(self, "_detector") else None,
                fast_detector=self._fast_detector if hasattr(self, "_fast_detector") else None,
                box_detection_enabled=getattr(self, "_box_detection_enabled", False),
                box_detector=getattr(self, "_box_detector", None),
                spatial_matcher=getattr(self, "_spatial_matcher", None),
                min_result_confidence=getattr(self, "_min_result_confidence", 0.0),
                square_ratio_max=getattr(self, "_square_ratio_max", 1.35),
                square_candidate_limit=getattr(self, "_square_candidate_limit", 180),
                supplement_when_mismatch=getattr(self, "_supplement_when_mismatch", True),
            )
        return pipeline._merge_box_and_dm(boxes, dm_detections)

    @staticmethod
    def _deduplicate_dm_detections(detections):
        return DetectionPipeline._deduplicate_dm_detections(detections)

    def _build_detection_objects(
        self,
        batch_id: int,
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
            normalized_content = sanitize_decoded_text(detection.content)
            bbox = self._normalize_bbox(getattr(detection, "bbox", None))
            confidence_score = self._normalize_confidence(getattr(detection, "confidence", 0.0))

            if persist:
                bid = self._biz_repo.make_task_code(rid)
                status = "completed" if normalized_content else "failed"
                row_id = self._biz_repo.create_task(
                    DetectionTaskPayload(
                        batch_id=batch_id,
                        code=bid,
                        status=status,
                        data_url=annotated_path,
                        box_detected={
                            "bbox": {
                                "x1": bbox[0],
                                "y1": bbox[1],
                                "x2": bbox[2],
                                "y2": bbox[3],
                            },
                            "confidenceScore": confidence_score,
                            "source": camera_id or detection.detection_source or image_source,
                            "inputImagePath": input_path,
                        },
                        matrix_detected={
                            "barcodeValue": normalized_content or None,
                            "barcodeType": "DataMatrix" if normalized_content else None,
                            "ocrText": None,
                            "decoderUsed": detection.decoder_used,
                            "decodeTimeMs": detection.scan_time_ms,
                        },
                        remark=None,
                    )
                )

            objects.append(
                {
                    "id": str(row_id or index),
                    "rid": rid,
                    "bid": bid,
                    "bbox": {
                        "x1": bbox[0],
                        "y1": bbox[1],
                        "x2": bbox[2],
                        "y2": bbox[3],
                    },
                    "barcodeValue": normalized_content or None,
                    "barcodeType": "DataMatrix" if normalized_content else None,
                    "ocrText": None,
                    "confidenceScore": confidence_score,
                    "modelId": model["id"],
                    "model": model,
                    "imagePath": annotated_path,
                    "remark": None,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )

        return objects

    @staticmethod
    def _normalize_confidence(value: object) -> float:
        try:
            score = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if not math.isfinite(score):
            return 0.0

        return max(0.0, min(1.0, score))

    @staticmethod
    def _normalize_bbox(raw_bbox: object) -> tuple[int, int, int, int]:
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4:
            return (0, 0, 0, 0)

        values: list[int] = []
        for raw in raw_bbox[:4]:
            try:
                num = float(raw)
                if not math.isfinite(num):
                    values.append(0)
                else:
                    values.append(int(round(num)))
            except (TypeError, ValueError):
                values.append(0)

        x1, y1, x2, y2 = values
        # Ensure bbox is not inverted.
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        return (x1, y1, x2, y2)

    @staticmethod
    def _normalize_model_payload(model: dict, now: str) -> dict:
        return {
            "id": str(model.get("id") or "opencv-dm-v1"),
            "modelName": str(model.get("modelName") or "OpenCV DataMatrix Detector"),
            "modelType": str(model.get("modelType") or "opencv"),
            "modelVersion": str(model.get("modelVersion") or "unknown"),
            "framework": str(model.get("framework") or "opencv"),
            "modelPath": str(model.get("modelPath") or ""),
            "isActive": bool(model.get("isActive", True)),
            "remark": str(model["remark"]) if model.get("remark") is not None else None,
            "createdAt": str(model.get("createdAt") or now),
            "updatedAt": str(model.get("updatedAt") or now),
        }

    def _decode_image(self, file_bytes: bytes) -> np.ndarray:
        array = np.frombuffer(file_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image file")
        return image

    @staticmethod
    def _is_pdf_upload(filename: str | None, content_type: str | None) -> bool:
        if content_type:
            mime = content_type.split(";", 1)[0].strip().lower()
            if mime == "application/pdf":
                return True
        return bool(filename and filename.lower().endswith(".pdf"))

    def _decode_pdf_first_page(self, file_bytes: bytes) -> np.ndarray:
        try:
            import pypdfium2 as pdfium
        except Exception as exc:  # noqa: BLE001
            raise ValueError("PDF support is unavailable (missing pypdfium2 dependency).") from exc

        try:
            pdf = pdfium.PdfDocument(file_bytes)
            if len(pdf) == 0:
                raise ValueError("PDF has no pages.")

            page = pdf[0]
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            rgb = np.array(pil_image)
            if rgb.size == 0:
                raise ValueError("Unable to render PDF page.")

            if rgb.ndim == 2:
                image = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)
            elif rgb.shape[2] == 4:
                image = cv2.cvtColor(rgb, cv2.COLOR_RGBA2BGR)
            else:
                image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            return image
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid PDF file: {exc}") from exc

    def _save_image(self, image: np.ndarray, file_name: str) -> str:
        path = self._output_dir / file_name
        cv2.imwrite(str(path), image)
        return f"/api/images/{file_name}"
