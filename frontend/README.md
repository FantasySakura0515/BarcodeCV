# Frontend Console

`frontend/` 是 BarcodeCV 唯一支援的前端工作台。

## 責任範圍

這個 workspace 負責：
- dashboard 與操作頁面
- 瀏覽器端互動流程與狀態管理
- `src/app/api/*` 的 BFF 代理層
- 前端 lint 與 production build 驗證

這個 workspace 不負責：
- 偵測與解碼演算法
- 資料持久化
- 相機商業邏輯

## 常用指令

```bash
npm install
npm run dev
npm run verify
```

預設網址：
- `http://localhost:3000`

## 環境變數

需要時建立 `frontend/.env.local`。

常用設定：
- `BACKEND_API_BASE_URL=http://127.0.0.1:8000/api`
- `FRONTEND_INTERNAL_API_BASE_URL=http://127.0.0.1:3000/api`

## 交付標準

交付前至少確認：
- `npm run verify` 通過
- 使用者可見頁面沒有 placeholder、亂碼或 boilerplate 文字
- 新增路由與元件都有明確責任邊界
