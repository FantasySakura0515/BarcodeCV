# BarcodeCV 後端規格書

## 1. 文件目的

本文件定義 BarcodeCV 後端系統的責任範圍、模組架構、資料流程、API 契約、資料儲存策略與後續擴充方向，作為後端實作、前後端串接與部署設計依據。

---

## 2. 後端目標

| 項目 | 說明 |
|---|---|
| 核心目的 | 接收影像輸入、執行物件偵測與條碼 / OCR 解讀、儲存結果、提供查詢與統計 API |
| 主要使用者 | 前端頁面、維運人員、開發測試人員 |
| MVP 任務 | 完成單張影像檢測、批次結果查詢、物件詳情查詢、模型資訊查詢、統計摘要輸出 |
| 設計原則 | 可觀測、易替換、低耦合、可逐步從 CLI 演進到 API 服務 |
| 現況基礎 | 已具備 Python 掃描流程、資料庫存取層、偵測 / 解碼模組 |

---

## 3. 系統定位

### 3.1 後端責任

| 類別 | 說明 |
|---|---|
| 影像處理 | 接收圖片或鏡頭影像，執行前處理、偵測、解碼、OCR |
| 流程協調 | 串接 camera、detection、decoding、matching、repository |
| 結果持久化 | 儲存批次、物件、模型、統計所需資料 |
| API 提供 | 對前端提供查詢、更新、管理與統計接口 |
| 可觀測性 | 記錄 log、錯誤碼、執行時間、模型版本與處理來源 |

### 3.2 非目標範圍（目前）

| 類別 | 說明 |
|---|---|
| 使用者登入 / 權限 | MVP 階段不處理認證與 RBAC |
| 任務佇列 | MVP 先以同步請求處理，不引入 Celery / Kafka |
| 分散式部署 | MVP 先以單機或單板部署為主 |
| 模型訓練平台 | 僅管理模型資訊與切換，不處理訓練流程 |

---

## 4. 技術定位與建議

| 類別 | 現況 / 建議 |
|---|---|
| 語言 | Python 3.11+ |
| 影像處理 | OpenCV |
| 條碼解碼 | `pylibdmtx`、`zxing-cpp` |
| OCR | 可先保留抽象介面，後續接 Tesseract / PaddleOCR / EasyOCR |
| API 框架 | 建議 FastAPI |
| 資料驗證 | Pydantic |
| 資料庫 | MVP 可用 SQLite；正式環境建議 PostgreSQL |
| ORM / Repository | MVP 維持 repository pattern；後續可評估 SQLAlchemy |
| 設定管理 | YAML + 環境變數覆蓋 |
| 日誌 | Python logging |
| 測試 | pytest |

---

## 5. 目前後端程式結構對應

```text
backend/
├─ main.py                    # CLI 入口與模式切換
├─ pipeline.py                # 掃描流程協調
├─ calibration/               # 距離校正、清晰度評估
├─ camera/                    # 鏡頭抽象與雙鏡頭管理
├─ database/                  # DB manager 與 repository
├─ decoding/                  # 條碼解碼器與 fallback 掃描器
├─ detection/                 # OpenCV box detector、YOLO detector、前處理、空間配對
└─ utils/                     # config、logger、影像工具
```

### 5.1 模組責任切分

| 模組 | 責任 |
|---|---|
| `main.py` | 啟動模式切換，整合 config、logger、pipeline |
| `pipeline.py` | 協調整體掃描生命週期與資料落庫 |
| `camera/` | 控制 global / local camera 與 frame capture |
| `detection/` | 物件框選、前處理、空間配對 |
| `decoding/` | 條碼掃描與多解碼器 fallback |
| `database/` | session / scan / box 相關資料存取 |
| `calibration/` | 對焦與距離校正能力 |
| `utils/` | logger、config、影像增強、公用工具 |

---

## 6. 執行模式規格

| 模式 | 說明 | 主要用途 |
|---|---|---|
| `single` | 執行單次掃描流程 | 現場單次辨識 / API 內部觸發 |
| `continuous` | 固定間隔持續掃描 | 連續監控、產線場景 |
| `preview` | 顯示即時影像預覽與框線 | 相機檢查、現場調整 |
| `calibration` | 執行拍攝距離與清晰度校正 | 部署與維護 |

### 6.1 API 化後的對應策略

| CLI 模式 | API 服務中的角色 |
|---|---|
| `single` | 對應 `POST /api/detections` 的同步辨識流程 |
| `continuous` | 保留為背景服務或排程服務，不直接暴露給前端 |
| `preview` | 先不對前端公開，保留為現場工具 |
| `calibration` | 保留為內部維運端點或 CLI 工具 |

---

## 7. 核心流程規格

## 7.1 單次檢測流程

```text
前端上傳圖片
  ↓
API 接收請求並建立 RID
  ↓
影像前處理
  ↓
物件偵測（OpenCV / YOLO）
  ↓
逐一裁切 ROI
  ├─ 條碼解碼
  └─ OCR 辨識
  ↓
組裝 DetectionObject
  ↓
寫入資料庫
  ↓
回傳批次結果與摘要
```

### 7.2 細部步驟

| 步驟 | 說明 |
|---|---|
| 1 | 驗證請求格式、檔案類型、檔案大小 |
| 2 | 建立批次編號 `RID` |
| 3 | 儲存原始影像或建立暫存路徑 |
| 4 | 執行 detection pipeline，取得多個 bounding boxes |
| 5 | 對每個 ROI 嘗試 barcode 與 OCR |
| 6 | 產生每個物件的 `BID` 與結果欄位 |
| 7 | 綁定當次使用模型資訊 |
| 8 | 寫入 `object_records` 與必要批次摘要 |
| 9 | 組裝 API response 回傳前端 |

### 7.3 流程原則

| 原則 | 說明 |
|---|---|
| 可替換偵測器 | OpenCV 與 YOLO 需透過抽象介面切換 |
| 解碼器可鏈式 fallback | 先主解碼器，失敗再走備援 |
| 物件級資料完整 | 每個偵測物件都需具備 bbox、barcode、OCR、confidence、model |
| 可追溯性 | 任一筆結果都需可追溯到影像、模型、時間與批次 |

---

## 8. 後端模組設計

## 8.1 建議服務分層

```text
API Router
  ↓
Application Service
  ↓
Pipeline / Domain Service
  ↓
Repository
  ↓
Database
```

### 8.2 分層責任

| 層級 | 責任 |
|---|---|
| Router | 接收 HTTP 請求、驗證輸入、回傳 response |
| Service | 組裝 use case，例如建立批次、查詢明細、統計彙整 |
| Pipeline | 執行 detection / decode / OCR 的技術流程 |
| Repository | 與資料庫互動 |
| Infrastructure | camera、檔案儲存、設定、logger |

### 8.3 建議新增目錄（API 化時）

```text
backend/
├─ api/
│  ├─ routes/
│  │  ├─ detections.py
│  │  ├─ objects.py
│  │  ├─ models.py
│  │  └─ stats.py
│  ├─ schemas/
│  │  ├─ detection.py
│  │  ├─ object.py
│  │  ├─ model.py
│  │  └─ stats.py
│  └─ dependencies.py
├─ services/
│  ├─ detection_service.py
│  ├─ object_service.py
│  ├─ model_service.py
│  └─ stats_service.py
```

---

## 9. API 規格

## 9.1 API 設計原則

| 原則 | 說明 |
|---|---|
| REST 為主 | 採用資源導向命名 |
| 一致回傳結構 | 成功與失敗皆維持一致 envelope |
| 明確錯誤碼 | 驗證失敗、找不到資料、處理失敗應可區分 |
| 支援分頁 | 列表 API 預留 `page`、`pageSize` |
| 支援查詢參數 | `RID`、`BID`、barcode、模型、日期區間 |

## 9.2 API 一覽

| Method | Path | 用途 |
|---|---|---|
| `POST` | `/api/detections` | 建立單次辨識批次 |
| `GET` | `/api/detections` | 取得批次列表 |
| `GET` | `/api/detections/{rid}` | 取得單一批次詳情 |
| `GET` | `/api/objects/{bid}` | 取得單一物件詳情 |
| `PATCH` | `/api/objects/{bid}` | 更新物件備註 |
| `GET` | `/api/stats/summary` | 取得儀表板摘要 |
| `GET` | `/api/models` | 取得模型列表 |
| `POST` | `/api/models` | 新增模型資訊 |
| `PATCH` | `/api/models/{id}/activate` | 切換啟用模型（建議） |

---

## 10. API 契約細節

## 10.1 `POST /api/detections`

### Request

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `file` | multipart file | 是 | 上傳影像 |
| `modelType` | string | 否 | 指定偵測模式，例如 `opencv` / `yolo` |
| `enableOcr` | boolean | 否 | 是否執行 OCR |
| `remark` | string | 否 | 批次備註 |

### Response

| 欄位 | 型別 | 說明 |
|---|---|---|
| `rid` | string | 批次編號 |
| `imageUrl` | string | 原圖或結果圖位置 |
| `objectCount` | number | 偵測物件總數 |
| `objects` | array | 物件結果列表 |
| `model` | object | 本次使用模型 |
| `createdAt` | string | 建立時間 |

### Object item

| 欄位 | 型別 | 說明 |
|---|---|---|
| `bid` | string | 物件編號 |
| `bbox` | object | `x1, y1, x2, y2` |
| `barcodeValue` | string \| null | 條碼值 |
| `barcodeType` | string \| null | 條碼類型 |
| `ocrText` | string \| null | OCR 結果 |
| `confidenceScore` | number | 信心分數 |
| `remark` | string \| null | 備註 |

## 10.2 `GET /api/detections`

### Query Parameters

| 參數 | 型別 | 說明 |
|---|---|---|
| `page` | int | 頁碼 |
| `pageSize` | int | 每頁筆數 |
| `rid` | string | 批次編號關鍵字 |
| `barcode` | string | 條碼關鍵字 |
| `modelType` | string | 模型類型 |
| `dateFrom` | string | 起始時間 |
| `dateTo` | string | 結束時間 |

### Response

| 欄位 | 型別 | 說明 |
|---|---|---|
| `items` | array | 批次列表 |
| `pagination` | object | 分頁資訊 |

## 10.3 `GET /api/detections/{rid}`

回傳指定批次摘要與該批次下所有物件。

## 10.4 `GET /api/objects/{bid}`

回傳單一物件詳細欄位、模型資訊、建立時間、備註與影像資訊。

## 10.5 `PATCH /api/objects/{bid}`

### Request

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `remark` | string | 是 | 更新備註內容 |

## 10.6 `GET /api/stats/summary`

### Response 區塊

| 欄位 | 說明 |
|---|---|
| `totalRounds` | 累積批次數 |
| `totalObjects` | 累積物件數 |
| `barcodeSuccessRate` | 條碼成功率 |
| `ocrSuccessRate` | OCR 成功率 |
| `recentRounds` | 最近批次 |
| `trends` | 日 / 週趨勢資料 |

## 10.7 `GET /api/models`

回傳模型列表、啟用狀態、版本、備註、建立與更新時間。

---

## 11. 回傳格式規範

## 11.1 成功格式

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

## 11.2 失敗格式

```json
{
  "success": false,
  "message": "validation_error",
  "error": {
    "code": "INVALID_IMAGE_FORMAT",
    "detail": "Only jpg, jpeg, png are allowed"
  }
}
```

## 11.3 建議錯誤碼

| Code | 說明 |
|---|---|
| `INVALID_IMAGE_FORMAT` | 不支援的影像格式 |
| `FILE_TOO_LARGE` | 檔案超過限制 |
| `RID_NOT_FOUND` | 找不到批次 |
| `BID_NOT_FOUND` | 找不到物件 |
| `MODEL_NOT_FOUND` | 找不到模型 |
| `DETECTION_FAILED` | 偵測流程執行失敗 |
| `DATABASE_ERROR` | 資料庫錯誤 |

---

## 12. 資料模型規格

## 12.1 MVP 建議資料表

| 資料表 | 用途 |
|---|---|
| `object_records` | 儲存每一個辨識物件 |
| `model_registry` | 儲存模型資訊 |
| `detection_rounds` | 建議新增，儲存批次主資料 |

## 12.2 `detection_rounds`（建議新增）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid / bigint | 主鍵 |
| `rid` | varchar | 批次編號，唯一 |
| `source_type` | varchar | `upload` / `camera` |
| `input_image_path` | varchar | 原圖路徑 |
| `result_image_path` | varchar | 疊框結果圖路徑 |
| `object_count` | int | 偵測物件數 |
| `barcode_success_count` | int | 成功讀到條碼數 |
| `ocr_success_count` | int | OCR 成功數 |
| `model_id` | uuid / bigint | 本次主要模型 |
| `status` | varchar | `success` / `partial_success` / `failed` |
| `remark` | text | 批次備註 |
| `created_at` | datetime | 建立時間 |
| `updated_at` | datetime | 更新時間 |

## 12.3 `object_records`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid / bigint | 主鍵 |
| `rid` | varchar | 批次編號 |
| `bid` | varchar | 物件編號，批次內唯一 |
| `x1` | int / float | 左上角 X |
| `y1` | int / float | 左上角 Y |
| `x2` | int / float | 右下角 X |
| `y2` | int / float | 右下角 Y |
| `barcode_value` | text | 條碼內容 |
| `barcode_type` | varchar | 條碼格式 |
| `ocr_text` | text | OCR 辨識文字 |
| `confidence_score` | float | 偵測 / 解碼綜合信心值 |
| `model_id` | uuid / bigint | 參照模型 |
| `image_path` | varchar | 物件裁切圖或來源圖 |
| `remark` | text | 備註 |
| `created_at` | datetime | 建立時間 |
| `updated_at` | datetime | 更新時間 |

### 約束條件

| 條件 | 說明 |
|---|---|
| `rid + bid` 唯一 | 同一批次下物件不得重複 |
| `barcode_value` 可空 | 允許偵測到物件但讀不到條碼 |
| `ocr_text` 可空 | 允許沒有文字 |
| `model_id` 必填 | 每筆資料需可追溯模型 |

## 12.4 `model_registry`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid / bigint | 主鍵 |
| `model_name` | varchar | 模型名稱 |
| `model_type` | varchar | `opencv` / `yolo` / `ocr` / `barcode` |
| `model_version` | varchar | 版本 |
| `framework` | varchar | 框架名稱 |
| `model_path` | varchar | 模型路徑 |
| `is_active` | boolean | 是否啟用 |
| `remark` | text | 備註 |
| `created_at` | datetime | 建立時間 |
| `updated_at` | datetime | 更新時間 |

---

## 13. 與現有資料層對齊

目前程式中已存在以下 repository：

| 現有結構 | 目前用途 | 對應未來規格 |
|---|---|---|
| `scan_sessions` | 連續掃描 session 管理 | 可對應 `detection_rounds` 的前身 |
| `scan_records` | 條碼掃描結果 | 可演進為 `object_records` 子集合或原始掃描記錄 |
| `box_records` | 盒框與配對狀態 | 可作為偵測輔助資料表 |

### 13.1 演進建議

| 階段 | 說明 |
|---|---|
| Phase 1 | 保留現有 `scan_records` / `box_records`，API 端以轉譯方式輸出前端需要格式 |
| Phase 2 | 新增 `detection_rounds` 與新版 `object_records` |
| Phase 3 | 視需要整併舊表或保留為低階原始紀錄表 |

---

## 14. 模型與策略管理

## 14.1 模型類型

| 類型 | 用途 |
|---|---|
| `opencv` | 基於輪廓 / 傳統影像處理的物件偵測 |
| `yolo` | 深度學習物件偵測 |
| `barcode` | 條碼解碼器組合 |
| `ocr` | 文字辨識 |

## 14.2 啟用策略

| 規則 | 說明 |
|---|---|
| 單一主偵測模型 | 同時間只允許一個主偵測模型啟用 |
| 解碼器可多組合 | barcode 可採 primary + fallback |
| OCR 可獨立切換 | 不影響主偵測模型 |
| 模型需版本化 | 前後端顯示與追蹤都需標記版本 |

---

## 15. 檔案與影像管理

| 項目 | 規格 |
|---|---|
| 上傳格式 | `jpg`、`jpeg`、`png` |
| 最大大小 | 建議 MVP 限制 10MB |
| 暫存策略 | 先存本地 `output/` 或系統 temp 目錄 |
| 命名方式 | 使用 `RID` + timestamp |
| 回傳策略 | 前端可先用相對路徑或暫時 URL |
| 清理機制 | 可由排程清除超過保存期限的暫存圖 |

---

## 16. 設定管理規格

| 類別 | 說明 |
|---|---|
| `config/default.yaml` | 開發預設參數 |
| `config/pi5_deploy.yaml` | Pi 5 佈署參數 |
| 環境變數 | 覆蓋 DB path、log level、image dir、API port |
| 啟動參數 | 保留 `--config`、`--mode` 作為 CLI / 維運工具 |

### 16.1 建議環境變數

| 變數 | 說明 |
|---|---|
| `BARCODECV_DB_PATH` | 資料庫路徑 |
| `BARCODECV_LOG_LEVEL` | 日誌等級 |
| `BARCODECV_IMAGE_DIR` | 影像輸出目錄 |
| `BARCODECV_API_HOST` | API Host |
| `BARCODECV_API_PORT` | API Port |

---

## 17. 日誌與可觀測性

| 類別 | 規格 |
|---|---|
| 系統啟動 | 記錄 config 摘要、模式、版本 |
| 請求日誌 | 記錄 path、latency、status code |
| 偵測日誌 | 記錄物件數、成功率、模型、耗時 |
| 錯誤日誌 | 記錄 stack trace 與 request context |
| 模型追蹤 | 記錄本次使用模型版本 |

### 17.1 建議觀測指標

| 指標 | 說明 |
|---|---|
| `detection_request_count` | API 檢測請求數 |
| `detection_latency_ms` | 檢測平均耗時 |
| `barcode_success_rate` | 條碼辨識成功率 |
| `ocr_success_rate` | OCR 成功率 |
| `db_write_latency_ms` | 資料寫入耗時 |

---

## 18. 錯誤處理規格

| 情境 | 處理方式 |
|---|---|
| 圖片格式錯誤 | 回傳 `400 Bad Request` |
| 找不到批次 / 物件 | 回傳 `404 Not Found` |
| 模型未設定 | 回傳 `409 Conflict` 或 `500` |
| 偵測流程失敗 | 回傳 `500 Internal Server Error`，保留 trace log |
| 部分物件辨識失敗 | 批次仍可成功，但物件欄位為空值 |

### 18.1 部分成功原則

若單張圖片中部分物件無法解碼：

- 批次狀態可標記為 `partial_success`
- 單一物件的 `barcode_value` / `ocr_text` 可為空
- API 仍需完整回傳 bbox 與可用結果

---

## 19. 效能與部署考量

| 類別 | 建議 |
|---|---|
| 同步處理 | MVP 可接受單張圖片同步處理 |
| 影像大小 | 規範最大解析度，避免 Pi 5 記憶體壓力 |
| 模型載入 | API 啟動時預載入常用模型 |
| DB 策略 | SQLite 開發可行，正式可切 PostgreSQL |
| 部署型態 | Pi 5 可直接執行；開發環境可用 Windows / Linux |

### 19.1 後續擴充

| 項目 | 說明 |
|---|---|
| 背景任務 | 大量圖片可改為 async job |
| WebSocket | 回傳即時進度 |
| 多相機來源 | 支援 USB camera / RTSP |
| 雲端儲存 | 圖檔與結果改存 S3 / MinIO |

---

## 20. 測試規格

| 類型 | 重點 |
|---|---|
| 單元測試 | detector、decoder、repository、service |
| 整合測試 | detection API、batch detail API、stats API |
| 資料庫測試 | CRUD、查詢條件、統計正確性 |
| 失敗情境 | 無效圖片、無偵測物件、資料庫異常 |
| 回歸測試 | 模型切換與 response schema 相容性 |

### 20.1 最小測試覆蓋建議

| 模組 | 測試案例 |
|---|---|
| `pipeline.py` | 單次掃描結果組裝、空結果、例外中止 |
| `repository.py` | insert / query / statistics |
| API routes | 200 / 400 / 404 / 500 |
| model service | active model 讀取與切換 |

---

## 21. 開發里程碑建議

| 階段 | 內容 |
|---|---|
| Phase A | 將現有 CLI 掃描流程封裝成可重用 service |
| Phase B | 建立 FastAPI 與 `/api/detections`、`/api/models`、`/api/stats/summary` |
| Phase C | 建立 `detection_rounds` 與新版 `object_records` |
| Phase D | 完成前端正式串接、備註更新與查詢篩選 |
| Phase E | 導入 YOLO、OCR 切換與部署優化 |

---

## 22. 與前端對齊摘要

| 前端頁面 | 後端需提供 |
|---|---|
| Dashboard | `GET /api/stats/summary` |
| Detection | `POST /api/detections` |
| Batch Records | `GET /api/detections` |
| Batch Detail | `GET /api/detections/{rid}` |
| Object Detail | `GET /api/objects/{bid}` + `PATCH /api/objects/{bid}` |
| Model Management | `GET /api/models` |

---

## 23. 結論

BarcodeCV 後端應以「可從現有掃描 CLI 平滑演進至 API 服務」為核心方向，優先完成：

1. 將現有 detection / decoding / repository 能力服務化
2. 建立前端所需的最小 REST API
3. 統一批次、物件、模型的資料結構
4. 保留 OpenCV 為預設策略，同時預留 YOLO / OCR 擴充點

此規格可作為下一階段實作 FastAPI、資料表演進與前後端正式串接的基準文件。
