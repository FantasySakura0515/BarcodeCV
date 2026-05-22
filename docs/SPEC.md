# BarcodeCV 專案規格書

## 1. 專案概要

| 項目 | 說明 |
|---|---|
| 專案名稱 | BarcodeCV |
| 專案目標 | 透過 OpenCV 與 YOLO 辨識畫面中多個任意數量物件，讀取物件內的 barcode 與文字資訊，並提供前端操作與後端統計能力 |
| 目前偵測策略 | 先以 OpenCV 為主，YOLO 納入架構設計並保留後續導入空間 |
| 前端技術 | Next.js、shadcn/ui、Framer Motion、Axios、Store |
| 後端責任 | 偵測結果接收、資料儲存、統計分析、模型資訊管理 |

---

## 2. 專案目標

### 2.1 核心目標

1. 辨識單張影像或即時畫面中的多個物件
2. 取得每個物件的座標資訊 `xyxy`
3. 嘗試讀取物件內的 `barcode` 與 `文字`
4. 保存每一批檢測結果與模型資訊
5. 提供前端頁面做檢視、搜尋、篩選與統計

### 2.2 MVP 目標

| 模組 | MVP 範圍 |
|---|---|
| 物件偵測 | 以 OpenCV 為主，支援多物件框選與座標輸出 |
| barcode 讀取 | 支援物件區域內 barcode 偵測與解碼 |
| 文字辨識 | 支援基礎 OCR 讀取 |
| 前端介面 | 上傳影像、查看辨識結果、查看統計與歷史紀錄 |
| 後端 | 提供檢測 API、查詢 API、統計 API、模型資訊 API |
| 資料庫 | 至少包含 `物件檢測資料表` 與 `模型資訊表` |

---

## 3. 使用情境

| 情境 | 說明 |
|---|---|
| 單張圖片檢測 | 使用者上傳一張圖片，系統辨識所有物件並讀取其內容 |
| 批次檢測 | 同一批次多張圖片，共用同一個 `RID` |
| 歷史查詢 | 依 `RID`、`BID`、barcode、時間區間查詢過去結果 |
| 統計檢視 | 查看檢測數量、辨識成功率、模型使用狀況 |

---

## 4. 系統範圍

### 4.1 In Scope

| 類別 | 內容 |
|---|---|
| 影像輸入 | 單張圖片、批次圖片、未來可擴充即時串流 |
| 物件偵測 | 多物件定位與 bounding box 產出 |
| barcode 辨識 | 讀取一維或二維 barcode 資訊 |
| OCR | 擷取物件區域內文字 |
| 前端互動 | 上傳、預覽、列表、詳情、統計頁 |
| 後端統計 | 按批次、模型、時間統計檢測成果 |
| 模型管理 | 紀錄目前使用模型與版本 |

### 4.2 Out of Scope（目前）

| 類別 | 說明 |
|---|---|
| 使用者權限系統 | 目前不做登入 / RBAC |
| 複雜工作流 | 目前不做人工複核流程 |
| 模型訓練平台 | 目前只保留模型紀錄與切換能力 |
| 多租戶 | 目前不區分組織或客戶 |

---

## 5. 系統架構概念

```text
前端 Next.js
	↓
API / Backend
	↓
影像處理流程
	├─ OpenCV 物件偵測
	├─ YOLO 偵測器（預留）
	├─ Barcode 解碼
	└─ OCR 文字辨識
	↓
資料庫儲存
	├─ object_records
	└─ model_registry
```

---

## 6. 功能規格

### 6.1 影像檢測功能

| 功能 | 說明 |
|---|---|
| 上傳影像 | 使用者可上傳單張或多張圖片 |
| 多物件偵測 | 辨識畫面中任意數量物件 |
| 座標輸出 | 每個物件需輸出 `x1, y1, x2, y2` |
| barcode 讀取 | 從物件區域內擷取 barcode 內容 |
| 文字辨識 | 從物件區域內擷取 OCR 文字 |
| 信心分數 | 每個物件需有辨識信心值 |
| 模型資訊綁定 | 每筆結果需紀錄使用的模型資訊 |

### 6.2 結果管理功能

| 功能 | 說明 |
|---|---|
| 批次編號 | 每次檢測批次產生一個 `RID` |
| 物件編號 | 同一批次中每個物件有唯一 `BID` |
| 歷史查詢 | 支援依 `RID`、`BID`、barcode、時間查詢 |
| 備註管理 | 可對單筆結果補充備註 |
| 統計分析 | 統計檢測量、成功率、模型使用次數 |

### 6.3 模型管理功能

| 功能 | 說明 |
|---|---|
| 模型登記 | 記錄模型名稱、版本、類型、狀態 |
| 模型查詢 | 查詢目前啟用與歷史模型 |
| 模型綁定結果 | 檢測結果需可回溯使用之模型 |
| 模型切換 | 後續支援 OpenCV / YOLO / OCR 模型切換 |

---

## 7. 前端規格

### 7.1 技術選型

| 類別 | 技術 |
|---|---|
| Framework | Next.js |
| UI | shadcn/ui |
| 動畫 | Framer Motion |
| HTTP Client | Axios |
| 狀態管理 | Store（建議 Zustand） |

### 7.2 前端頁面

| 頁面 | 功能 |
|---|---|
| Dashboard | 總覽檢測數據、成功率、最近批次 |
| Detection | 上傳圖片、開始辨識、查看結果框與內容 |
| Batch Detail | 查看指定 `RID` 的全部物件結果 |
| Object Detail | 查看單一 `BID` 詳細資訊 |
| Model Management | 查看模型清單與目前啟用模型 |

### 7.3 前端互動需求

| 功能 | 說明 |
|---|---|
| 影像預覽 | 上傳後立即顯示原圖 |
| 框選呈現 | 將偵測框疊加在影像上 |
| 明細面板 | 顯示 barcode、OCR、信心值、備註 |
| 篩選與搜尋 | 依 `RID`、`BID`、barcode、模型、時間篩選 |
| 動畫回饋 | 透過 Framer Motion 增加切換與載入體驗 |

---

## 8. 後端規格

### 8.1 主要責任

| 模組 | 說明 |
|---|---|
| 檢測流程 | 呼叫 OpenCV / YOLO / barcode / OCR 管線 |
| 資料儲存 | 儲存批次與物件檢測結果 |
| 統計分析 | 提供各類統計查詢 |
| 模型管理 | 管理模型資訊與版本 |
| API 提供 | 提供前端查詢與操作所需資料 |

### 8.2 建議 API

| Method | Path | 用途 |
|---|---|---|
| `POST` | `/api/detections` | 上傳圖片並建立檢測批次 |
| `GET` | `/api/detections` | 查詢檢測批次列表 |
| `GET` | `/api/detections/{rid}` | 查詢單一批次結果 |
| `GET` | `/api/objects/{bid}` | 查詢單一物件結果 |
| `PATCH` | `/api/objects/{bid}` | 更新備註等欄位 |
| `GET` | `/api/stats/summary` | 取得統計摘要 |
| `GET` | `/api/models` | 取得模型列表 |
| `POST` | `/api/models` | 新增模型資訊 |

---

## 9. 資料庫規格

## 9.1 Table 1：`object_records`

用途：記錄每一個被辨識到的物件。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | bigint / uuid | 主鍵 |
| `rid` | varchar | Round ID，檢測批次編號 |
| `bid` | varchar | Box ID，檢測物件編號 |
| `x1` | int / float | 左上 X |
| `y1` | int / float | 左上 Y |
| `x2` | int / float | 右下 X |
| `y2` | int / float | 右下 Y |
| `barcode_value` | varchar / text | barcode 內容 |
| `barcode_type` | varchar | barcode 類型 |
| `ocr_text` | text | OCR 文字結果 |
| `confidence_score` | float | 辨識信心分數 |
| `model_id` | varchar / bigint | 對應模型資訊 |
| `image_path` | varchar | 原圖或結果圖路徑 |
| `remark` | text | 備註 |
| `created_at` | datetime | 建立時間 |
| `updated_at` | datetime | 更新時間 |

規則：

- `rid + bid` 應具唯一性
- barcode 與 OCR 可允許為空
- `model_id` 必須可追溯至模型資訊表

### 9.2 Table 2：`model_registry`

用途：記錄目前與歷史使用模型資訊。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | bigint / uuid | 主鍵 |
| `model_name` | varchar | 模型名稱 |
| `model_type` | varchar | 例如 `opencv`、`yolo`、`ocr` |
| `model_version` | varchar | 模型版本 |
| `framework` | varchar | 例如 `opencv`、`ultralytics` |
| `model_path` | varchar | 模型檔案路徑 |
| `is_active` | boolean | 是否為目前啟用模型 |
| `remark` | text | 備註 |
| `created_at` | datetime | 建立時間 |
| `updated_at` | datetime | 更新時間 |

### 9.3 備註

| 項目 | 規格 |
|---|---|
| 目前最小需求 | 先維持 `object_records` + `model_registry` 兩張表 |
| 未來可擴充 | 可新增 `detection_rounds` 作為批次主表 |
| 模型策略 | 目前預設使用 OpenCV，YOLO 為後續可切換方案 |

---

## 10. 辨識流程規格

| 步驟 | 說明 |
|---|---|
| 1 | 前端上傳圖片至後端 |
| 2 | 後端建立 `RID` |
| 3 | 執行物件偵測，取得多個 bounding boxes |
| 4 | 對每個物件區域執行 barcode 解碼 |
| 5 | 對每個物件區域執行 OCR |
| 6 | 彙整結果並計算信心分數 |
| 7 | 將結果寫入 `object_records` |
| 8 | 回傳前端呈現影像框與結果列表 |

---

## 11. 統計需求

| 類別 | 指標 |
|---|---|
| 批次統計 | 批次數量、每批物件數、每批成功辨識數 |
| barcode 統計 | barcode 讀取成功率、空值數量 |
| OCR 統計 | 文字辨識成功率 |
| 模型統計 | 各模型使用次數、成功率、最近使用時間 |
| 時間統計 | 日 / 週 / 月檢測量 |

---

## 12. 非功能需求

| 類別 | 規格 |
|---|---|
| 可維護性 | 前後端、辨識流程、資料層需明確分離 |
| 可擴充性 | OpenCV 與 YOLO 可替換或並存 |
| 可追溯性 | 每筆辨識資料可追溯所用模型 |
| 可觀測性 | 需記錄錯誤日誌與檢測時間 |
| 效能 | 支援單批次多物件辨識，不因物件數增加而失控 |

---

## 13. 開發階段建議

| 階段 | 內容 |
|---|---|
| Phase 1 | OpenCV 多物件偵測、barcode/OCR、資料入庫 |
| Phase 2 | 前端 Dashboard、批次查詢、模型管理頁 |
| Phase 3 | 導入 YOLO 偵測器並支援模型切換 |
| Phase 4 | 強化統計、報表、即時串流或攝影機輸入 |

---

## 14. 結論

本專案的 MVP 應聚焦在三件事：

1. **準確取得多物件座標**
2. **穩定讀取 barcode 與文字**
3. **完整保存批次、物件與模型資訊**

在此基礎上，再逐步擴充 YOLO、多模型切換、前端統計與更完整的後端分析能力。
