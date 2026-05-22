# BarcodeCV 前端規格書

## 1. 文件目的

本文件定義 BarcodeCV 前端系統的頁面範圍、互動流程、元件分工、狀態管理與 API 串接規格，作為後續 UI/UX 設計與實作依據。

---

## 2. 前端目標

| 項目 | 說明 |
|---|---|
| 核心目的 | 提供影像上傳、辨識結果檢視、歷史查詢、統計分析與模型資訊查看 |
| 使用者 | 操作人員、檢測管理者、開發測試人員 |
| 主要情境 | 上傳圖片進行辨識、查看批次結果、查看單一物件資訊、檢視統計摘要 |
| 設計原則 | 清楚、快速、低學習成本、可視化結果明確 |

---

## 3. 技術規格

| 類別 | 技術 |
|---|---|
| Framework | Next.js |
| UI Components | shadcn/ui |
| Animation | Framer Motion |
| HTTP Client | Axios |
| State Management | Store，建議 Zustand |
| Styling | Tailwind CSS |
| Data Fetching | Client fetch + 必要頁面可搭配 server fetch |

---

## 4. 資訊架構

```text
前端系統
├─ Dashboard
├─ Detection
├─ Batch Records
├─ Object Detail
└─ Model Management
```

---

## 5. 頁面規格

## 5.1 Dashboard

### 目的

提供整體系統狀態與統計摘要。

### 內容

| 區塊 | 說明 |
|---|---|
| Summary Cards | 總批次數、總物件數、barcode 成功率、OCR 成功率 |
| Recent Rounds | 最近檢測批次列表 |
| Model Status | 目前啟用模型資訊 |
| Trend Chart | 日 / 週 / 月檢測趨勢 |

### 操作

| 操作 | 說明 |
|---|---|
| 點擊批次 | 進入批次詳情頁 |
| 點擊模型 | 進入模型管理頁 |
| 切換區間 | 查看不同時間統計 |

---

## 5.2 Detection Page

### 目的

作為主要操作頁，讓使用者上傳圖片並查看辨識結果。

### 內容

| 區塊 | 說明 |
|---|---|
| Upload Panel | 拖拉或選擇圖片上傳 |
| Preview Area | 顯示原始圖片與辨識框 |
| Result List | 顯示每個物件的辨識結果 |
| Filter Panel | 篩選只看成功 / 失敗 / 有 barcode / 有文字 |
| Action Bar | 重新辨識、清除、下載結果 |

### 操作流程

| 步驟 | 說明 |
|---|---|
| 1 | 使用者上傳圖片 |
| 2 | 前端顯示圖片預覽 |
| 3 | 呼叫檢測 API |
| 4 | 顯示 loading 狀態 |
| 5 | 回傳後疊加 bounding boxes |
| 6 | 顯示物件明細列表 |
| 7 | 點擊單一物件可高亮對應框 |

### 顯示欄位

| 欄位 | 說明 |
|---|---|
| BID | 物件編號 |
| 座標 | `x1, y1, x2, y2` |
| Barcode | barcode 值 |
| Barcode Type | barcode 類型 |
| OCR Text | 文字辨識結果 |
| Confidence | 信心分數 |
| Model | 模型資訊 |
| Remark | 備註 |

---

## 5.3 Batch Records Page

### 目的

查看歷史檢測批次與批次下所有辨識紀錄。

### 內容

| 區塊 | 說明 |
|---|---|
| Search Bar | 依 `RID`、barcode、日期搜尋 |
| Batch Table | 顯示批次列表 |
| Filter Controls | 依時間、模型、結果狀態篩選 |
| Pagination | 分頁查詢 |

### 批次列表欄位

| 欄位 | 說明 |
|---|---|
| RID | 批次編號 |
| Object Count | 物件數量 |
| Barcode Success Count | barcode 成功數 |
| OCR Success Count | OCR 成功數 |
| Model | 使用模型 |
| Created At | 建立時間 |

---

## 5.4 Batch Detail Page

### 目的

檢視指定 `RID` 下所有物件結果。

### 內容

| 區塊 | 說明 |
|---|---|
| Batch Summary | 顯示批次摘要資訊 |
| Image / Canvas | 顯示圖片與所有框 |
| Object Table | 顯示該批次所有 `BID` 結果 |
| Side Panel | 顯示目前選取物件詳情 |

### 操作

| 操作 | 說明 |
|---|---|
| 點擊表格列 | 高亮圖片中的對應框 |
| 點擊框 | 同步定位到表格與詳情 |
| 編輯備註 | 可更新物件備註 |

---

## 5.5 Object Detail Page

### 目的

查看單一物件詳細辨識資訊。

### 顯示內容

| 欄位 | 說明 |
|---|---|
| RID / BID | 批次與物件編號 |
| Bounding Box | 物件座標 |
| Barcode 資訊 | 值與類型 |
| OCR 結果 | 文字內容 |
| Confidence | 信心分數 |
| Model Info | 模型名稱、版本、框架 |
| Created At | 建立時間 |
| Remark | 備註 |

---

## 5.6 Model Management Page

### 目的

查看目前使用與歷史模型資訊。

### 內容

| 區塊 | 說明 |
|---|---|
| Active Model Card | 顯示目前啟用模型 |
| Model Table | 顯示所有模型 |
| Model Detail Drawer | 查看單一模型詳情 |

### 欄位

| 欄位 | 說明 |
|---|---|
| Model Name | 模型名稱 |
| Model Type | `opencv` / `yolo` / `ocr` |
| Version | 模型版本 |
| Framework | 使用框架 |
| Status | 啟用 / 停用 |
| Created At | 建立時間 |
| Remark | 備註 |

---

## 6. 共用元件規格

| 元件 | 用途 |
|---|---|
| `PageHeader` | 頁面標題與操作區 |
| `StatCard` | Dashboard 統計卡片 |
| `UploadDropzone` | 圖片上傳區 |
| `DetectionCanvas` | 顯示影像與辨識框 |
| `ObjectResultTable` | 顯示辨識結果列表 |
| `FilterBar` | 列表篩選器 |
| `ModelBadge` | 標示模型類型與狀態 |
| `EmptyState` | 無資料顯示 |
| `LoadingState` | 載入中 |
| `ErrorState` | API 或處理失敗提示 |

---

## 7. 狀態管理規格

建議以 Zustand 進行 store 管理。

### 7.1 Store 分類

| Store | 內容 |
|---|---|
| `useDetectionStore` | 上傳圖片、辨識結果、目前選取物件 |
| `useBatchStore` | 批次列表、查詢條件、分頁資訊 |
| `useStatsStore` | Dashboard 統計資料 |
| `useModelStore` | 模型列表、目前啟用模型 |
| `useUiStore` | Dialog、Drawer、Toast、Loading 狀態 |

### 7.2 Detection Store 欄位

| 欄位 | 說明 |
|---|---|
| `imageFile` | 目前上傳檔案 |
| `imageUrl` | 預覽圖 URL |
| `rid` | 本次辨識批次編號 |
| `objects` | 辨識結果列表 |
| `selectedBid` | 目前選取物件 |
| `isLoading` | 是否辨識中 |
| `error` | 錯誤訊息 |

---

## 8. API 串接規格

## 8.1 檢測 API

### `POST /api/detections`

用途：上傳圖片並執行辨識。

#### Request

| 欄位 | 型別 | 說明 |
|---|---|---|
| `file` | multipart file | 圖片檔案 |
| `modelType` | string | 可選，預設 `opencv` |

#### Response

| 欄位 | 型別 | 說明 |
|---|---|---|
| `rid` | string | 批次編號 |
| `imageUrl` | string | 結果圖 URL |
| `objects` | array | 物件辨識結果 |

#### `objects[]`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `bid` | string | 物件編號 |
| `bbox` | object | `x1, y1, x2, y2` |
| `barcodeValue` | string/null | barcode 值 |
| `barcodeType` | string/null | barcode 類型 |
| `ocrText` | string/null | OCR 結果 |
| `confidenceScore` | number | 信心值 |
| `model` | object | 模型資訊 |
| `remark` | string/null | 備註 |

---

## 8.2 批次 API

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/api/detections` | 批次列表 |
| `GET` | `/api/detections/{rid}` | 單一批次結果 |
| `GET` | `/api/objects/{bid}` | 單一物件詳情 |
| `PATCH` | `/api/objects/{bid}` | 更新備註 |
| `GET` | `/api/stats/summary` | 統計摘要 |
| `GET` | `/api/models` | 模型列表 |

---

## 9. 互動與 UX 規格

| 項目 | 規範 |
|---|---|
| 上傳回饋 | 上傳後立即顯示預覽與 loading |
| 結果呈現 | 影像框與列表需可雙向同步 |
| 篩選效率 | 常用條件需在 1~2 次操作內可完成 |
| 錯誤提示 | API 失敗需顯示明確訊息與重試操作 |
| 空狀態 | 無資料時顯示引導文字 |
| 動畫 | 僅用於切換、展開、載入，不可影響操作效率 |

---

## 10. RWD 規格

| 裝置 | 規範 |
|---|---|
| Desktop | 完整功能，為主要操作場景 |
| Tablet | 保留列表與詳情切換 |
| Mobile | 以查詢與查看結果為主，不作為主要操作端 |

---

## 11. 權限與安全性

| 項目 | 規格 |
|---|---|
| 登入 | MVP 暫不實作 |
| 上傳限制 | 限制圖片格式與大小 |
| 錯誤資訊 | 不直接暴露後端堆疊資訊 |
| API 保護 | 後續可補 token 或 session 驗證 |

---

## 12. 前端資料夾建議

```text
frontend/
├─ app/
│  ├─ dashboard/
│  ├─ detection/
│  ├─ batches/
│  ├─ objects/
│  └─ models/
├─ components/
│  ├─ common/
│  ├─ detection/
│  ├─ dashboard/
│  └─ models/
├─ lib/
│  ├─ api/
│  ├─ utils/
│  └─ constants/
├─ stores/
├─ types/
└─ hooks/
```

---

## 13. MVP 驗收標準

| 項目 | 驗收條件 |
|---|---|
| 圖片上傳 | 可成功上傳並觸發辨識 |
| 結果呈現 | 可顯示多物件框與結果列表 |
| 批次查詢 | 可依 `RID` 查詢歷史資料 |
| 物件詳情 | 可查看單一 `BID` 詳細資訊 |
| 模型查看 | 可查看目前模型資訊 |
| 統計頁 | 可顯示基本統計卡片與趨勢 |

---

## 14. 設計前確認事項

在開始設計網頁前，需先確認以下項目：

| 項目 | 待確認內容 |
|---|---|
| 品牌風格 | 是否需要品牌色、Logo、深色模式 |
| 上傳方式 | 單張優先或需同時支援批次多檔 |
| 主要操作裝置 | Desktop only 或需兼顧平板 |
| 結果圖呈現 | 使用 Canvas 疊框或 SVG 疊框 |
| OCR 顯示策略 | 顯示全文或僅重點欄位 |
| 備註流程 | 是否允許前端直接編輯備註 |

---

## 15. 結論

前端 MVP 應先聚焦在：

1. `Detection`：上傳與結果檢視
2. `Batch Records / Batch Detail`：歷史與追蹤
3. `Dashboard`：統計摘要
4. `Model Management`：模型資訊可視化
