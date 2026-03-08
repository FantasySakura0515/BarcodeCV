# 2026-03-08 Web zh-TW 在地化報告

## 變更範圍
已完成前端產品化 UX 文案的繁體中文（zh-TW）在地化，限定於使用者可見文字：
- 導覽、頁首標題、按鈕文案
- 空狀態、錯誤訊息、摘要資訊
- 表格欄位與狀態文字

未變更任何核心行為、API 契約、資料欄位或流程邏輯。

## 變更檔案
- docs/architecture/web-localization-zhTW-spec.md
- frontend/src/components/layout/app-shell.tsx
- frontend/src/components/detection/detection-canvas.tsx
- frontend/src/components/detection/object-result-table.tsx
- frontend/src/components/detection/upload-dropzone.tsx
- frontend/src/app/dashboard/page.tsx
- frontend/src/app/detection/page.tsx
- frontend/src/app/live-detection/page.tsx
- frontend/src/app/batches/page.tsx
- frontend/src/app/batches/[rid]/page.tsx
- frontend/src/app/models/page.tsx
- frontend/src/app/objects/[bid]/page.tsx
- frontend/src/stores/use-detection-store.ts

## 術語決策
- Dashboard → 儀表板
- Image Detection → 影像辨識
- Live Detection → 即時辨識
- Batch Records → 批次紀錄
- Run ID (RID) → 批次 ID（RID）
- Object ID (BID) → 物件 ID（BID）
- Barcode → 條碼
- OCR Text → OCR 文字
- Active / Inactive → 啟用中 / 未啟用

補充：Data Matrix、OpenCV、OCR、API 等技術名詞與縮寫保留英文，符合規格例外。

## 驗證結果
於 `frontend/` 執行：
- `npm run lint`：通過（0 errors，5 warnings；皆為既有 hook/img 警告，非本次在地化邏輯問題）
- `npm run build`：通過（Next.js production build 成功）

## 提交紀錄（小型主題提交）
1. `18bf48e` docs: add zh-TW web localization specification
2. `0f84c6d` feat(web): localize zh-TW copy for navigation and record views
3. `ff7b401` feat(web): localize zh-TW detection workflow copy
