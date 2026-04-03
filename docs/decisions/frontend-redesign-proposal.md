# 視覺與架構重構提案 (BarcodeCV Web 介面 2.0)

為解決目前 BarcodeCV 前端介面過於「工程化」、缺乏整體佈局規劃與使用體驗不友善的問題，我們將對前端架構與視覺風格進行全面重構（重新設計介面邏輯、導入一致的科技感 UI 元件、確保 100% RWD 與 SEO 友善）。

重構目標：**打造具備現代科技感、高可用性、視覺結構清晰的企業級電腦視覺產品介面。**

---

## 1. 視覺風格定義 (Visual Design System)
目標是在第一時間給使用者帶來「先進、專業、穩定」的科技感。

*   **基礎色調 (Theme)**: 切換為 **暗色系 (Dark Mode) 或深灰科技風** 為主搭配。
    *   **背景 (Background)**: `#0F111A` (深藏青/近黑) 或 `#121212`。確保資料在畫面上能形成強烈對比。
    *   **卡片/區塊背景 (Surface)**: `#1E212B`。利用極細微的邊框 `border-white/10` 與背景區分。
    *   **主色 (Primary Accent)**: 採用高亮度的科技色彩系列，例如 **霓虹青/賽博藍 (Cyan/Electric Blue: `#00F0FF`)** 或 **翠綠色 (Neon Green: `#00FF66`)**。這些顏色極好地映襯「電腦視覺、掃描、AI辨識」的意象。
    *   **輔助/狀態色 (Status)**:
        *   成功 (Success): 深綠 `#10b981` (用於已解碼物件)
        *   警示 (Warning): 亮橘 `#f59e0b` (用於模糊或框出未解碼物件)
        *   錯誤 (Error): 嫣紅 `#ef4444` (用於離線、辨識失敗)
*   **字體排版 (Typography)**:
    *   介面主字型：`Inter` 或系統原生字型 (如 `San Francisco`, `Segoe UI`) 以確保極致的易讀性。
    *   數據/代碼字型：`Roboto Mono` 或 `JetBrains Mono`。對條碼數值 (BarcodeValue)、FPS 或信心指數 (Confidence) 等使用等寬字型，以提供機器/數據的嚴謹感。
*   **視覺裝飾 (Visual Enhancements)**:
    *   **毛玻璃效應 (Glassmorphism)**: 側邊欄、懸浮面板(Popover) 或載入中(Loading) 狀態使用 backdrop-blur，增強介面層次感。
    *   **掃描動畫 (Scanner Effects)**: 在偵測畫面或載入中，加入極具科技感的垂直掃描線 (Scanning Line) 動畫或閃爍的十字準星 (Crosshair) UI 設計。

---

## 2. 佈局結構 (Layout Structure)
放棄過度分散或沒有重點的堆疊，改用業界標準的 **Dashboard 佈局 (App Shell)**。

### 2.1 全域佈局 (App Shell)
*   **側邊欄 (Sidebar) - 可收合 (Collapsible)**:
    *   取代傳統頂部選單，讓出更多垂直空間給影像辨識畫面。
    *   包含清晰的導航：儀表板 (Dashboard)、單張檢測 (Detection)、即時攝影 (Live Camera)、歷史紀錄 (Batch History)、模型管理 (Models)。
    *   底端放置系統狀態燈號 (Backend: Online/Offline, Camera: Ready)。
*   **頂部導航 (Top Navbar / Header)**:
    *   僅保留當前頁面標題 (Page Title)、麵包屑 (Breadcrumb) 與全域快捷操作 (如深淺色切換、清空快取)。

### 2.2 響應式策略 (RWD Strategy)
*   **Desktop 大螢幕 (lg+)**: 採用左右分欄設計 (Split View)。左側或上方為「操作輸入 或 辨識結果」，右側為「影像預覽 (Canvas)」。
*   **Tablet 平板 (md)**: 取消 Split View，改為上下佈局，並優化觸控體驗 (例如按鈕加大至至少 `44x44px`)。
*   **Mobile 手機 (sm)**: 側邊欄收納至漢堡選單 (Hamburger Menu)，表格改為卡片列表 (Card List)，影像Canvas支援原比例縮放且能雙指放大。

---

## 3. 頁面重構規劃 (Page-by-Page Refactor)

### 3.1 儀表板 (Dashboard / 總覽)
*   **現狀問題**: 只是資料文字或表格的堆砌，重點不突出。
*   **改進方向**:
    *   **Hero Section**: 頂部以4個關鍵數據卡片展現（今日總辨識數、平均解碼成功率、系統 FPS、條碼類型分佈）。
    *   **視覺化圖表**: 引入 Recharts 或簡單的進度條顯示過去的處理量趨勢。
    *   **快速檢視模組**: 增加一個「近期批次快速檢視 (Recent Batches)」表格。

### 3.2 影像辨識與即時影像頁面 (Detection / Live Detection)
*   **現狀問題**: Canvas、上傳區塊與結果表格互相推擠，排版混亂，缺乏重點。
*   **改進方向**:
    *   **雙欄佈局 (大螢幕)**: 左欄為操作控制面板 (上傳、選擇相機、啟動按鈕) 與即時結果表格；右欄(佔螢幕 2/3) 為極大化的 **影像/視覺化檢視區 (Canvas Area)**。
    *   **專注模式 (Focus Mode)**: 在 Live Detection 中，提供全螢幕按鈕，隱藏非必要 UI，僅保留影像串流與 OSD (On-Screen Display) 數據，模擬工業檢驗機台。
    *   **強化的 Canvas UI**:
        *   解碼成功的物件框出綠色科技感準星框，並附帶優雅的浮水印式 Tag 顯示數值。
        *   未解碼或異常的提供橘紅色警示框與閃爍效果。
        *   新增「影像控制工具列」在 Canvas 右下角：縮放、平移、對比度調整。

### 3.3 結果表格與細節 (Results Table / Batch View)
*   **現狀問題**: 表格在手機端容易破版、互動體驗差。
*   **改進方向**:
    *   導入 Radix UI 或 Shadcn Table，確保跨裝置響應式呈現（小螢幕改為卡片式排列）。
    *   **互動聯動 (Hover Sync)**: 滑鼠懸浮在表格列上時，右側 Canvas 中對應的 Bounding Box 會高亮 (Highlight)。反之亦然。

---

## 4. 前端技術與 SEO 優化方案

### 4.1 元件庫優化 (Component Revamp)
*   全面檢視並加強 **Shadcn UI + Tailwind CSS** 的運用，統一圓角 `rounded-lg` 或 `rounded-none`（如果追求極致硬派科技感）。
*   修改 `tailwind.config.ts` 中的顏色配置，對齊上文提及的賽博科技色票。
*   加入極簡微互動 (Micro-interactions, 如按鈕懸停呼吸燈效果、選單展開轉場)。

### 4.2 SEO 與效能 (SEO & Web Vitals)
雖然是工具型產品，但良好的 SEO 架構有助於維護與渲染效能：
*   **Metadata**: 完備 Next.js 14/15 的 metadata 設定，確保各大頁面擁有清晰的 Title & Description。
*   **渲染策略化次 (Rendering Strategy)**: 靜態頁面(如 Dashboard 骨架)儘量用 RSC (React Server Components)，而需要高頻重繪的 Canvas 或 Webcam 組件封裝進嚴格隔離的 `"use client"` 元件。
*   **效能優化 (Performance)**:
    *   Canvas 效能層：隔離複雜的繪圖邏輯與 React 狀態更新，避免每秒 30 幀的即時影像導致整個頁面重新渲染卡頓。
    *   對圖片檔案實行 `next/image` 延遲載入 (Lazy loading)。

---

## 5. 實踐與重構步驟建議 (Next Actions)
一旦確認此提案方向，我們可以按以下步驟開始寫扣：
1.  **主題與全域樣式設定**: 更新 `tailwind.config.ts`、`globals.css` 轉換為預設 Dark Theme，並套用 Primary Accent Color。
2.  **架構佈局重建 (App Shell)**: 重寫 `components/layout/app-shell.tsx`，建立新的側邊導航欄與響應式主視圖。
3.  **核心辨識頁面重構**: 優先修改 `/detection` 和 `/live-detection`，這包含雙欄佈局、Canvas 互動以及 Hover 聯動。
4.  **其餘頁面與細節打磨**: 重構 Dashboard 圖表、物件歷史表格列表等，確保全站組件風格一致。
