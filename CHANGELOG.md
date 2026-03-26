# Changelog

所有重要的版本變更都會記錄在此文件。格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)。

---

## [Unreleased]

---

## [0.3.0] - 2026-03-26

### Added
- **Railway 雲端部署支援**
  - 新增 `Procfile`，使用 gunicorn 作為生產環境 WSGI server（2 workers，120s timeout）
  - `requirements.txt` 加入 `gunicorn>=21.0`
  - `webapp.py` 改從環境變數 `PORT` 讀取 port，相容 Railway 動態分配
  - 部署網址：`https://web-production-94e4d.up.railway.app`

---

## [0.2.0] - 2026-03-26

### Added
- **Flask Web UI（Phase 2）**
  - Dashboard：統計卡片（總 Watch 數、已啟用數、今日搜尋數、今日 Deals 數）、最近搜尋記錄
  - Watches 管理：新增、編輯、刪除、啟用/停用、手動觸發搜尋
  - Searches 歷史：搜尋記錄列表、單次搜尋結果詳細頁（deals 綠色高亮）
  - Settings 頁面：Email (SMTP)、資料來源、排程設定
  - APScheduler 背景排程，可設定每日自動搜尋時間
  - 機場欄位使用 Tom Select 自動完成下拉，支援 100+ 機場按國家分組
  - 輸入首字母自動篩選機場，支援代碼或城市名搜尋
  - 手動輸入不在列表中的 IATA 代碼
  - 日期防呆：Departure To ≥ Departure From、Return From ≥ Departure To、Return To ≥ Return From
  - 選擇機場後自動清空輸入欄位，避免重複 tag
  - Bootstrap 5.3 CDN 響應式 UI

- **Web 框架初始化**
  - Flask app factory（`flight_monitor/web/__init__.py`）
  - SQLAlchemy 資料庫模型：`Watch`、`SearchRun`、`FlightOfferRow`、`Setting`
  - WTForms 表單驗證：`WatchForm`、`EmailSettingsForm`、`ProviderSettingsForm`、`ScheduleSettingsForm`
  - CSRFProtect 初始化，所有表單受 CSRF 保護
  - `webapp.py` 入口，預設 port 8080

### Changed
- `.gitignore` 加入 `instance/` 和 `*.db`，排除 SQLite 資料庫

### Fixed
- `csrf_token` 在 Jinja2 template 中 undefined 錯誤（補上 `CSRFProtect` 初始化）
- Tom Select 選擇已知機場代碼後產生重複 tag（改用函式型 `createFilter` 檢查是否已在列表中）
- Tom Select 輸入一半文字選擇選項後殘留輸入文字（`onItemAdd` 後呼叫 `setTextboxValue('')`）

---

## [0.1.1] - 2026-03-26

### Added
- `config.yaml.example` 範例設定檔

### Changed
- `config.yaml` 加入 `.gitignore`，避免個人設定被提交

---

## [0.1.0] - 2026-03-26

### Added
- **CLI 機票價格監控工具（Phase 1）**
  - 支援 Google Flights（free-flights 爬蟲）和 Travelpayouts（免費 API）雙資料來源
  - YAML 設定檔驅動，支援多個 Watch（航線監控）同時運作
  - 每個 Watch 可設定：出發地/目的地（多個 IATA 代碼）、日期範圍、艙等、最大中轉、人數、價格上限
  - 支援單程/來回行程，來回可分別設定出發/回程日期範圍
  - 多艙等同時搜尋（economy、premium_economy、business、first）
  - 自動貨幣轉換（fawazahmed0 免費 API，快取 12 小時）
  - Email 通知（SMTP，支援 Gmail App Password），HTML + 純文字格式
  - CLI 參數：`--dry-run`、`--watch NAME`、`--verbose`、自訂 config/env 路徑
  - Token bucket rate limiter，Google Flights 0.5 req/s，Travelpayouts 5 req/s
  - Retry 機制（指數退避）

### Changed
- 來回行程改為 `return_date_from` / `return_date_to` 日期範圍（取代原本 `stay_nights`）
