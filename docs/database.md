# 資料庫設計文件

**資料庫引擎**：SQLite 3.x  
**字元編碼**：UTF-8  
**版本**：v1.0

---

## 目錄

1. [設計原則](#設計原則)
2. [資料表概覽](#資料表概覽)
3. [ER 關聯圖](#er-關聯圖)
4. [資料表詳細設計](#資料表詳細設計)
   - [customers 客戶表](#1-customers-客戶表)
   - [devices 設備表](#2-devices-設備表)
   - [batchs 批次表](#3-batchs-批次表)
   - [tasks 任務表](#4-tasks-任務表)
   - [settings 設定表](#5-settings-設定表)
5. [索引設計](#索引設計)
6. [完整 DDL 建表語句](#完整-ddl-建表語句)
7. [效能與維護建議](#效能與維護建議)

---

## 設計原則

| 原則 | 說明 |
| --- | --- |
| **Soft Delete** | 所有主要資料表均以 `deleted_at` 欄位進行邏輯刪除，保留歷史資料可追溯性 |
| **時間戳記** | 每張資料表均含 `created_at`、`updated_at`，記錄資料生命週期 |
| **唯一碼約束** | `code` 欄位於各資料表設有 `UNIQUE` 約束，確保業務識別碼不重複 |
| **外鍵完整性** | 啟用 `PRAGMA foreign_keys = ON`，確保參照完整性 |
| **CHECK 約束** | 對狀態類欄位使用 `CHECK` 限制合法值，防止髒資料寫入 |
| **預設值** | 時間欄位使用 `CURRENT_TIMESTAMP`，布林欄位提供合理預設 |

---

## 資料表概覽

| 資料表 | 中文名稱 | 說明 | 主要關聯 |
| --- | --- | --- | --- |
| `customers` | 客戶表 | 儲存客戶基本資訊 | 被 `batchs` 參照 |
| `devices` | 設備表 | 儲存辨識設備資訊 | 獨立主表 |
| `batchs` | 批次表 | 客戶所產生的辨識批次 | FK → `customers` |
| `tasks` | 任務表 | 批次下的辨識任務資料 | FK → `batchs` |
| `settings` | 設定表 | 系統全域設定鍵值對 | 獨立主表 |

---

## 資料表詳細設計

---

### 1. customers 客戶表

**用途**：儲存所有客戶的基本資料，為批次作業的頂層擁有者。

| 欄位名稱 | 資料型別 | 約束 | 預設值 | 說明 |
| --- | --- | --- | --- | --- |
| `id` | `INTEGER` | `PK, NOT NULL` | 自動遞增 | 主鍵，自動遞增 |
| `name` | `TEXT` | `NOT NULL` | — | 客戶名稱 |
| `code` | `TEXT` | `NOT NULL, UNIQUE` | — | 客戶唯一識別碼（業務碼） |
| `description` | `TEXT` | — | `NULL` | 客戶描述備註 |
| `email` | `TEXT` | `UNIQUE` | `NULL` | 電子郵件（允許 NULL 但不可重複） |
| `phone` | `TEXT` | — | `NULL` | 聯絡電話 |
| `created_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 建立時間 |
| `updated_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 最後更新時間 |
| `deleted_at` | `DATETIME` | — | `NULL` | 軟刪除時間（NULL 表示未刪除） |

**約束說明**：
- `PK`：`id`
- `UNIQUE`：`code`（業務碼全域唯一）
- `UNIQUE`：`email`（同一 email 不可重複登錄）
- 軟刪除查詢應加上 `WHERE deleted_at IS NULL`

---

### 2. devices 設備表

**用途**：儲存系統中所有辨識設備的資訊，管理設備狀態與位置。

| 欄位名稱 | 資料型別 | 約束 | 預設值 | 說明 |
| --- | --- | --- | --- | --- |
| `id` | `INTEGER` | `PK, NOT NULL` | 自動遞增 | 主鍵，自動遞增 |
| `name` | `TEXT` | `NOT NULL` | — | 設備名稱 |
| `code` | `TEXT` | `NOT NULL, UNIQUE` | — | 設備唯一識別碼 |
| `type` | `TEXT` | `NOT NULL` | — | 設備類型（如 camera、scanner） |
| `location` | `TEXT` | — | `NULL` | 設備安裝位置描述 |
| `is_active` | `INTEGER` | `NOT NULL, CK` | `1` | 是否啟用（1=啟用, 0=停用） |
| `is_deletable` | `INTEGER` | `NOT NULL, CK` | `1` | 是否允許刪除（1=允許, 0=保護） |
| `last_seen_at` | `DATETIME` | — | `NULL` | 設備最後連線時間 |
| `created_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 建立時間 |
| `updated_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 最後更新時間 |
| `deleted_at` | `DATETIME` | — | `NULL` | 軟刪除時間 |

**約束說明**：
- `PK`：`id`
- `UNIQUE`：`code`
- `CHECK`：`is_active IN (0, 1)`
- `CHECK`：`is_deletable IN (0, 1)`
- 刪除前須先確認 `is_deletable = 1`

---

### 3. batchs 批次表

**用途**：記錄客戶所提交的辨識批次，為任務的上層容器。

| 欄位名稱 | 資料型別 | 約束 | 預設值 | 說明 |
| --- | --- | --- | --- | --- |
| `id` | `INTEGER` | `PK, NOT NULL` | 自動遞增 | 主鍵，自動遞增 |
| `customer_id` | `INTEGER` | `NOT NULL, FK` | — | 外鍵 → `customers.id` |
| `name` | `TEXT` | `NOT NULL` | — | 批次名稱 |
| `code` | `TEXT` | `NOT NULL, UNIQUE` | — | 批次唯一識別碼 |
| `description` | `TEXT` | — | `NULL` | 批次描述備註 |
| `created_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 建立時間 |
| `updated_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 最後更新時間 |
| `deleted_at` | `DATETIME` | — | `NULL` | 軟刪除時間 |

**約束說明**：
- `PK`：`id`
- `FK`：`customer_id` → `customers(id)` ON DELETE RESTRICT ON UPDATE CASCADE
- `UNIQUE`：`code`
- 查詢批次需同時過濾 `deleted_at IS NULL` 及客戶是否已軟刪除

---

### 4. tasks 任務表

**用途**：記錄每個批次下的辨識任務，含辨識結果的預期值與實際檢測值。

| 欄位名稱 | 資料型別 | 約束 | 預設值 | 說明 |
| --- | --- | --- | --- | --- |
| `id` | `INTEGER` | `PK, NOT NULL` | 自動遞增 | 主鍵，自動遞增 |
| `batchs_id` | `INTEGER` | `NOT NULL, FK` | — | 外鍵 → `batchs.id` |
| `code` | `TEXT` | `NOT NULL, UNIQUE` | — | 任務唯一識別碼 |
| `status` | `TEXT` | `NOT NULL, CK` | `'pending'` | 任務狀態：`pending / running / completed / failed` |
| `data_url` | `TEXT` | — | `NULL` | 任務資料來源 URL |
| `box_expected` | `TEXT` | — | `NULL` | 預期框選結果（JSON 或座標字串） |
| `matrix_expected` | `TEXT` | — | `NULL` | 預期矩陣結果 |
| `box_detected` | `TEXT` | — | `NULL` | 實際偵測框選結果 |
| `matrix_detected` | `TEXT` | — | `NULL` | 實際偵測矩陣結果 |
| `created_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 建立時間 |
| `updated_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 最後更新時間 |
| `deleted_at` | `DATETIME` | — | `NULL` | 軟刪除時間 |

**約束說明**：
- `PK`：`id`
- `FK`：`batchs_id` → `batchs(id)` ON DELETE RESTRICT ON UPDATE CASCADE
- `UNIQUE`：`code`
- `CHECK`：`status IN ('pending', 'running', 'completed', 'failed')`
- `status` 狀態流轉：`pending → running → completed / failed`

---

### 5. settings 設定表

**用途**：儲存系統全域設定，採用鍵值對（Key-Value）結構，方便動態擴充。

| 欄位名稱 | 資料型別 | 約束 | 預設值 | 說明 |
| --- | --- | --- | --- | --- |
| `id` | `INTEGER` | `PK, NOT NULL` | 自動遞增 | 主鍵，自動遞增 |
| `name` | `TEXT` | `NOT NULL` | — | 設定項目名稱（人類可讀） |
| `description` | `TEXT` | — | `NULL` | 設定說明 |
| `setting_key` | `TEXT` | `NOT NULL, UNIQUE` | — | 設定鍵名（程式存取用） |
| `setting_value` | `TEXT` | `NOT NULL` | — | 設定值（統一以文字儲存） |
| `is_deletable` | `INTEGER` | `NOT NULL, CK` | `1` | 是否允許刪除（1=允許, 0=系統保護） |
| `created_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 建立時間 |
| `updated_at` | `DATETIME` | `NOT NULL` | `CURRENT_TIMESTAMP` | 最後更新時間 |
| `deleted_at` | `DATETIME` | — | `NULL` | 軟刪除時間 |

**約束說明**：
- `PK`：`id`
- `UNIQUE`：`setting_key`（鍵名不可重複）
- `CHECK`：`is_deletable IN (0, 1)`
- 系統核心設定應設 `is_deletable = 0` 以防誤刪

---

## 索引設計

| 索引名稱 | 資料表 | 欄位 | 類型 | 用途說明 |
| --- | --- | --- | --- | --- |
| `idx_customers_code` | `customers` | `code` | UNIQUE | 快速以業務碼查詢客戶 |
| `idx_customers_email` | `customers` | `email` | UNIQUE | 快速以 email 查詢客戶 |
| `idx_customers_deleted` | `customers` | `deleted_at` | INDEX | 加速軟刪除過濾 |
| `idx_devices_code` | `devices` | `code` | UNIQUE | 快速以設備碼查詢設備 |
| `idx_devices_active` | `devices` | `is_active` | INDEX | 快速篩選啟用設備 |
| `idx_batchs_code` | `batchs` | `code` | UNIQUE | 快速以批次碼查詢批次 |
| `idx_batchs_customer_id` | `batchs` | `customer_id` | INDEX | 加速 JOIN 與客戶批次查詢 |
| `idx_batchs_deleted` | `batchs` | `deleted_at` | INDEX | 加速軟刪除過濾 |
| `idx_tasks_code` | `tasks` | `code` | UNIQUE | 快速以任務碼查詢任務 |
| `idx_tasks_batchs_id` | `tasks` | `batchs_id` | INDEX | 加速 JOIN 與批次任務查詢 |
| `idx_tasks_status` | `tasks` | `status` | INDEX | 快速篩選特定狀態任務 |
| `idx_tasks_deleted` | `tasks` | `deleted_at` | INDEX | 加速軟刪除過濾 |
| `idx_settings_key` | `settings` | `setting_key` | UNIQUE | 快速以 key 查詢設定值 |

---

## 完整 DDL 建表語句

```sql
-- ============================================================
-- 啟用外鍵支援（SQLite 預設關閉，每次連線均需執行）
-- ============================================================
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;      -- 提升並發讀寫效能
PRAGMA synchronous = NORMAL;    -- 平衡效能與資料安全

-- ============================================================
-- 1. customers 客戶表
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name        TEXT     NOT NULL,
    code        TEXT     NOT NULL,
    description TEXT,
    email       TEXT,
    phone       TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  DATETIME,

    CONSTRAINT uq_customers_code  UNIQUE (code),
    CONSTRAINT uq_customers_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_customers_deleted ON customers (deleted_at);

-- ============================================================
-- 2. devices 設備表
-- ============================================================
CREATE TABLE IF NOT EXISTS devices (
    id           INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name         TEXT     NOT NULL,
    code         TEXT     NOT NULL,
    type         TEXT     NOT NULL,
    location     TEXT,
    is_active    INTEGER  NOT NULL DEFAULT 1,
    is_deletable INTEGER  NOT NULL DEFAULT 1,
    last_seen_at DATETIME,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at   DATETIME,

    CONSTRAINT uq_devices_code       UNIQUE (code),
    CONSTRAINT ck_devices_is_active  CHECK (is_active    IN (0, 1)),
    CONSTRAINT ck_devices_deletable  CHECK (is_deletable IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_devices_active ON devices (is_active);

-- ============================================================
-- 3. batchs 批次表
-- ============================================================
CREATE TABLE IF NOT EXISTS batchs (
    id          INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER  NOT NULL,
    name        TEXT     NOT NULL,
    code        TEXT     NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at  DATETIME,

    CONSTRAINT uq_batchs_code     UNIQUE (code),
    CONSTRAINT fk_batchs_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_batchs_customer_id ON batchs (customer_id);
CREATE INDEX IF NOT EXISTS idx_batchs_deleted     ON batchs (deleted_at);

-- ============================================================
-- 4. tasks 任務表
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    batchs_id       INTEGER  NOT NULL,
    code            TEXT     NOT NULL,
    status          TEXT     NOT NULL DEFAULT 'pending',
    data_url        TEXT,
    box_expected    TEXT,
    matrix_expected TEXT,
    box_detected    TEXT,
    matrix_detected TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      DATETIME,

    CONSTRAINT uq_tasks_code   UNIQUE (code),
    CONSTRAINT ck_tasks_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed')
    ),
    CONSTRAINT fk_tasks_batch
        FOREIGN KEY (batchs_id)
        REFERENCES batchs (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_batchs_id ON tasks (batchs_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status    ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted   ON tasks (deleted_at);

-- ============================================================
-- 5. settings 設定表
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    id            INTEGER  NOT NULL PRIMARY KEY AUTOINCREMENT,
    name          TEXT     NOT NULL,
    description   TEXT,
    setting_key   TEXT     NOT NULL,
    setting_value TEXT     NOT NULL,
    is_deletable  INTEGER  NOT NULL DEFAULT 1,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at    DATETIME,

    CONSTRAINT uq_settings_key       UNIQUE (setting_key),
    CONSTRAINT ck_settings_deletable CHECK (is_deletable IN (0, 1))
);
```

---

## 效能與維護建議

### 必要 PRAGMA 設定

每次連線 SQLite 時務必執行：

```sql
PRAGMA foreign_keys = ON;    -- 啟用外鍵約束（SQLite 預設關閉）
PRAGMA journal_mode = WAL;   -- Write-Ahead Logging，提升讀寫並發
PRAGMA synchronous = NORMAL;
```

### 軟刪除查詢範本

所有一般查詢應附加軟刪除條件，避免讀取已刪除資料：

```sql
-- 查詢有效客戶
SELECT * FROM customers WHERE deleted_at IS NULL;

-- 查詢某客戶的有效批次
SELECT b.* FROM batchs b
WHERE b.customer_id = :customer_id
  AND b.deleted_at IS NULL;

-- 查詢某批次下待處理的任務
SELECT * FROM tasks
WHERE batchs_id = :batchs_id
  AND status = 'pending'
  AND deleted_at IS NULL;
```

### updated_at 自動更新（Trigger）

SQLite 不支援 `ON UPDATE CURRENT_TIMESTAMP`，需建立觸發器：

```sql
-- 以 customers 為例，其他資料表依此類推
CREATE TRIGGER IF NOT EXISTS trg_customers_updated_at
AFTER UPDATE ON customers
FOR EACH ROW
BEGIN
    UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
```

### 定期維護

```sql
VACUUM;   -- 回收已刪除資料的磁碟空間
ANALYZE;  -- 更新統計資訊，協助查詢規劃器優化索引使用
```

### 約束彙整

| 約束類型 | 資料表 | 欄位 | 說明 |
|----------|--------|------|------|
| PK | 全部 | `id` | 主鍵自動遞增 |
| UNIQUE | `customers` | `code`, `email` | 業務碼與信箱唯一 |
| UNIQUE | `devices` | `code` | 設備碼唯一 |
| UNIQUE | `batchs` | `code` | 批次碼唯一 |
| UNIQUE | `tasks` | `code` | 任務碼唯一 |
| UNIQUE | `settings` | `setting_key` | 設定鍵唯一 |
| FK | `batchs` | `customer_id → customers.id` | ON DELETE RESTRICT |
| FK | `tasks` | `batchs_id → batchs.id` | ON DELETE RESTRICT |
| CHECK | `devices` | `is_active IN (0,1)` | 布林值限制 |
| CHECK | `devices` | `is_deletable IN (0,1)` | 布林值限制 |
| CHECK | `tasks` | `status IN (...)` | 狀態合法值限制 |
| CHECK | `settings` | `is_deletable IN (0,1)` | 布林值限制 |