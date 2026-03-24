# Flight Price Monitor

自動監控機票價格，當出現符合條件的低價機票時，透過 Email 通知你。

## 功能

- 支援多條航線同時監控（每條航線獨立設定）
- 彈性日期範圍搜尋（出發日期區間 + 停留天數區間）
- 支援單程 / 來回
- 支援經濟艙 / 豪華經濟艙 / 商務艙 / 頭等艙
- 可設定是否允許轉機
- 價格門檻過濾，低於目標價自動通知
- 每條航線可設定不同的顯示貨幣
- HTML 格式 Email，含航班詳情表格與訂票連結
- 透過 cron 每日自動執行

### 資料來源

| Provider | 類型 | API Key | 說明 |
|----------|------|---------|------|
| **Google Flights** | 網頁抓取 | 不需要 | 透過 `fast-flights` 套件直接抓取 Google Flights 即時資料 |
| **Travelpayouts** | 免費 API | 需要（免費） | 快取價格資料（每 48 小時更新），適合輔助比價 |

> Google Flights 為主要資料源，開箱即用不需要任何 API key。Travelpayouts 為可選的補充資料源。

---

## 快速開始

### 1. 環境需求

- Python 3.9+
- 網路連線

### 2. 安裝

```bash
cd /path/to/flight-price-monitor

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 3. 設定 Email（必要）

```bash
cp .env.example .env
```

編輯 `.env`，填入 Gmail 資訊：

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_FROM=your.email@gmail.com
```

> Google Flights provider 不需要 API key，安裝完就能用。

### 4. 設定航線

編輯 `config.yaml`，詳細說明見下方 [設定檔說明](#設定檔說明)。

### 5. 執行

```bash
# 測試模式（只搜尋並印出結果，不寄 Email）
./venv/bin/python main.py --dry-run -v

# 正式執行（搜尋 + 寄 Email）
./venv/bin/python main.py

# 只執行特定航線
./venv/bin/python main.py --watch "MY-TW Business May-Jun" --dry-run
```

---

## API 設定教學

### Google Flights（主要資料源）

**不需要 API key。** 安裝 `fast-flights` 套件後即可使用。

在 `config.yaml` 中確認已啟用：

```yaml
providers:
  - name: google_flights
    enabled: true
```

> 注意：Google Flights 使用網頁抓取方式，搜尋速度較慢（每次約 2 秒），程式已內建速率控制避免被封鎖。

### Travelpayouts（選填，補充資料源）

Travelpayouts 提供免費的快取票價資料（每 48 小時更新），適合輔助比價。

1. 前往 [https://www.travelpayouts.com/](https://www.travelpayouts.com/) 註冊帳號
2. 登入後，進入 **Programs** > 加入 **Aviasales** 計畫
3. 進入 **Tools** > **API**
4. 複製你的 API Token
5. 貼到 `.env` 的 `TRAVELPAYOUTS_TOKEN=` 後面
6. 在 `config.yaml` 中啟用：

```yaml
providers:
  - name: google_flights
    enabled: true
  - name: travelpayouts
    enabled: true     # 改為 true
```

### Gmail App Password（Email 通知）

1. 登入 Google 帳號 → [安全性](https://myaccount.google.com/security)
2. 確認已啟用 **兩步驟驗證**
3. 進入 **兩步驟驗證** 頁面，滑到最下面找到 **應用程式密碼**
4. 選擇「郵件」，裝置選「其他」，輸入名稱（例如 "Flight Monitor"）
5. Google 會產生一組 16 位元密碼，複製它
6. 貼到 `.env` 的 `SMTP_PASSWORD=` 後面

> 注意：不能使用 Gmail 原始密碼，必須使用 App Password。

---

## 設定檔說明

設定檔為 `config.yaml`，分為四個區塊：

### email - Email 通知設定

```yaml
email:
  recipient: "your.email@example.com"   # 接收通知的 Email
```

### currency - 全域貨幣設定

```yaml
currency:
  display: "TWD"   # 預設顯示貨幣（可被每條航線覆蓋）
```

### providers - 資料源設定

```yaml
providers:
  - name: google_flights
    enabled: true          # 主要資料源，免費不需 API key
  - name: travelpayouts
    enabled: false         # 補充資料源，需要免費 API token
```

### watches - 航線監控設定

每條航線是一個獨立的搜尋任務，可以設定任意多條：

```yaml
watches:
  - name: "航線名稱"              # 自訂名稱，用於辨識和 Email 標題
    enabled: true                  # true=啟用, false=停用

    # === 地點 ===
    origins:                       # 出發機場（IATA 代碼，可多個）
      - "KUL"
      - "PEN"
    destinations:                  # 目的地機場（IATA 代碼，可多個）
      - "TPE"
      - "KHH"

    # === 行程類型 ===
    trip_type: "round_trip"        # "round_trip"（來回）或 "one_way"（單程）

    # === 日期 ===
    departure_date_from: "2026-05-15"   # 出發日期範圍起始
    departure_date_to: "2026-06-07"     # 出發日期範圍結束

    # === 停留天數（僅 round_trip 需要）===
    stay_nights_min: 4             # 最少停留幾晚
    stay_nights_max: 7             # 最多停留幾晚

    # === 艙等 ===
    cabin_class: "business"        # 見下方艙等對照表

    # === 轉機 ===
    max_stopovers: 0               # 0=直飛, 1=允許1次轉機, 2=允許2次...

    # === 乘客 ===
    adults: 1                      # 成人人數

    # === 價格 ===
    max_price: 7000                # 價格門檻（低於此價格才通知）
    currency: "TWD"                # 此航線的顯示貨幣（覆蓋全域設定）

    # === 結果數量 ===
    max_results: 20                # 每次搜尋最多回傳幾筆結果
```

### 艙等對照表

| 設定值 | 說明 |
|--------|------|
| `economy` | 經濟艙 |
| `premium_economy` | 豪華經濟艙 |
| `business` | 商務艙 |
| `first` | 頭等艙 |

### 常用機場 IATA 代碼

| 代碼 | 機場 |
|------|------|
| **馬來西亞** | |
| KUL | 吉隆坡國際機場 (KLIA/KLIA2) |
| PEN | 檳城國際機場 |
| BKI | 亞庇國際機場 |
| SZB | 蘇丹阿都阿茲沙機場 (Subang) |
| **台灣** | |
| TPE | 桃園國際機場 |
| TSA | 台北松山機場 |
| KHH | 高雄小港國際機場 |
| RMQ | 台中清泉崗機場 |
| **日本** | |
| NRT | 東京成田機場 |
| HND | 東京羽田機場 |
| KIX | 大阪關西機場 |
| **其他** | |
| LHR | 倫敦希斯洛 |
| SIN | 新加坡樟宜 |
| BKK | 曼谷素萬那普 |
| ICN | 首爾仁川 |

> 完整 IATA 代碼可在 [iata.org](https://www.iata.org/en/publications/directories/code-search/) 查詢。

---

## 設定範例

### 範例 1：馬來西亞 → 台灣商務艙來回

5 月中到 6 月初出發，待 5-7 天，直飛，商務艙。

```yaml
- name: "MY-TW Business"
  enabled: true
  origins: ["KUL", "PEN", "SZB", "BKI"]
  destinations: ["TPE", "KHH", "RMQ", "TSA"]
  trip_type: "round_trip"
  departure_date_from: "2026-05-15"
  departure_date_to: "2026-06-07"
  stay_nights_min: 4
  stay_nights_max: 7
  cabin_class: "business"
  max_stopovers: 0
  adults: 1
  max_price: 5000
  currency: "MYR"
  max_results: 20
```

### 範例 2：台灣 → 日本經濟艙暑假

7 月出發，2 人同行，待一週左右。

```yaml
- name: "TW-JP Economy Summer"
  enabled: true
  origins: ["TPE"]
  destinations: ["NRT", "HND", "KIX"]
  trip_type: "round_trip"
  departure_date_from: "2026-07-01"
  departure_date_to: "2026-07-31"
  stay_nights_min: 5
  stay_nights_max: 9
  cabin_class: "economy"
  max_stopovers: 0
  adults: 2
  max_price: 15000
  currency: "TWD"
  max_results: 20
```

### 範例 3：吉隆坡 → 倫敦單程

允許一次轉機，經濟艙。

```yaml
- name: "KUL-London One-way"
  enabled: true
  origins: ["KUL"]
  destinations: ["LHR", "LGW", "STN"]
  trip_type: "one_way"
  departure_date_from: "2026-11-01"
  departure_date_to: "2026-11-15"
  cabin_class: "economy"
  max_stopovers: 1
  adults: 1
  max_price: 2000
  currency: "MYR"
  max_results: 10
```

---

## CLI 指令

```
usage: main.py [-h] [-c CONFIG] [-e ENV] [-v] [--dry-run] [--watch WATCH]
```

| 參數 | 說明 |
|------|------|
| `-c`, `--config` | 指定設定檔路徑（預設 `config.yaml`） |
| `-e`, `--env` | 指定環境變數檔路徑（預設 `.env`） |
| `-v`, `--verbose` | 顯示詳細 debug 日誌 |
| `--dry-run` | 只搜尋並印出結果，不寄 Email |
| `--watch NAME` | 只執行指定名稱的航線 |

### 常用指令組合

```bash
# 第一次使用，測試設定是否正確
./venv/bin/python main.py -v --dry-run

# 只測試某條航線
./venv/bin/python main.py --watch "MY-TW Business" --dry-run -v

# 正式執行（搜尋 + 寄信）
./venv/bin/python main.py

# 使用自訂設定檔
./venv/bin/python main.py -c my_config.yaml -e my_secrets.env
```

---

## 設定每日自動執行

使用系統 cron 每天自動搜尋：

```bash
crontab -e
```

加入以下內容（每天早上 8 點執行）：

```cron
0 8 * * * cd /path/to/flight-price-monitor && ./venv/bin/python main.py >> logs/flight-monitor.log 2>&1
```

### Cron 時間格式

```
分 時 日 月 週
0  8  *  *  *     # 每天 08:00
0  */6 *  *  *    # 每 6 小時
0  8,20 * * *     # 每天 08:00 和 20:00
```

### 查看執行日誌

```bash
tail -f logs/flight-monitor.log
```

---

## Email 通知範例

當搜尋到低於門檻的機票時，你會收到一封類似這樣的 Email：

```
Subject: Flight Alert: 3 deals found!

MY-TW Business May-Jun
3 deals under TWD 7,000 threshold

┌──────────┬───────────┬────────────┬────────────┬──────────┬───────────┬──────┐
│ Airline  │ Route     │ Depart     │ Return     │ Duration │ Price     │ Book │
├──────────┼───────────┼────────────┼────────────┼──────────┼───────────┼──────┤
│ CI       │ KUL→TPE   │ 2026-05-20 │ 2026-05-26 │ 4h35m    │ TWD 6,850 │ Link │
│ MH       │ KUL→TPE   │ 2026-05-22 │ 2026-05-28 │ 5h15m    │ TWD 6,920 │ Link │
│ AK       │ KUL→TPE   │ 2026-06-01 │ 2026-06-06 │ 4h50m    │ TWD 6,990 │ Link │
└──────────┴───────────┴────────────┴────────────┴──────────┴───────────┴──────┘
```

> 實際 Email 為 HTML 格式，含可點擊的 Google Flights 搜尋連結。若沒有符合條件的機票，不會寄信。

---

## 專案結構

```
flight-price-monitor/
├── main.py                          # CLI 入口
├── config.yaml                      # 航線設定
├── .env                             # Email 密碼 + API token（不進版控）
├── .env.example                     # .env 模板
├── .gitignore
├── requirements.txt                 # Python 依賴（4 個）
├── logs/                            # cron 執行日誌
├── flight_monitor/
│   ├── models.py                    # 資料結構定義
│   ├── config.py                    # 設定檔載入與驗證
│   ├── rate_limiter.py              # API 速率限制器
│   ├── currency.py                  # 匯率轉換（免費，不需 API key）
│   ├── date_utils.py                # 彈性日期組合生成
│   ├── notifier.py                  # Email 通知（HTML + 純文字）
│   ├── engine.py                    # 主引擎
│   └── providers/
│       ├── base.py                  # Provider 抽象介面
│       ├── google_flights.py        # Google Flights 抓取（主要）
│       └── travelpayouts.py         # Travelpayouts API（補充）
└── venv/                            # Python 虛擬環境
```

---

## 兩個資料源的差異

| | Google Flights | Travelpayouts |
|--|----------------|---------------|
| 資料即時性 | 即時（直接抓取） | 快取（48 小時更新） |
| API Key | 不需要 | 需要（免費） |
| 搜尋速度 | 較慢（每次約 2 秒） | 快（API 回應） |
| 價格準確度 | 高（即時） | 中（可能已過期） |
| 艙等篩選 | 支援 | 支援 |
| 直飛篩選 | 搜尋後過濾 | 有專用 endpoint |
| 訂票連結 | Google Flights 搜尋連結 | Google Flights 搜尋連結 |
| 風險 | 可能被 Google 暫時封鎖 | 穩定 |

> 建議：兩者都啟用。Google Flights 提供即時價格，Travelpayouts 提供穩定的補充資料。

---

## 常見問題

### Q: 完全不需要 API key 就能用嗎？

是的。只啟用 `google_flights` provider 的話，不需要任何 API key。只需設定 Gmail App Password 來寄通知信。

### Q: 為什麼搜不到結果？

- 用 `-v` 看 debug 日誌，檢查是否有錯誤
- 確認日期沒有過期（必須是未來的日期）
- 確認 IATA 代碼正確
- 某些冷門航線可能確實沒有直飛航班
- Google Flights 可能暫時封鎖請求，稍後再試

### Q: 搜尋好慢？

Google Flights provider 為避免被封鎖，預設每 2 秒搜尋一次。4 個出發地 x 4 個目的地 x 10 個日期 = 160 次搜尋，約需 5-6 分鐘。可以減少 origins/destinations 數量來加速。

### Q: Email 寄不出去？

- 確認使用的是 Gmail **App Password**，不是帳號密碼
- 確認已啟用 Google 兩步驟驗證
- 檢查 `SMTP_USER` 和 `EMAIL_FROM` 是否正確
- 用 `-v` 查看 SMTP 錯誤訊息

### Q: 如何同時監控多條航線？

在 `config.yaml` 的 `watches` 下加入多個項目即可，每條航線獨立設定。不需要的航線將 `enabled` 設為 `false`。

### Q: 支援哪些貨幣？

支援 200+ 種貨幣，包括 TWD、MYR、USD、EUR、JPY、GBP、SGD、THB、KRW 等。匯率透過免費 API 自動轉換。

### Q: 訂票連結是什麼？

連結為 Google Flights 搜尋頁面，方便你找到航班後到航空公司官網購買。

### Q: 價格門檻要設多少才合理？

建議先用 `--dry-run` 跑一次，看看目前的市場價格，再決定門檻。以下是大概的參考範圍（來回）：

| 航線 | 經濟艙 | 商務艙 |
|------|--------|--------|
| KUL↔TPE | MYR 800-1,500 | MYR 3,000-8,000 |
| TPE↔NRT | TWD 6,000-15,000 | TWD 25,000-60,000 |
| KUL↔LHR | MYR 2,000-4,000 | MYR 8,000-20,000 |

> 以上為概略範圍，實際價格隨季節和提前購買時間而異。

### Q: Google Flights 的價格是什麼貨幣？

Google Flights 預設回傳 USD 價格，程式會自動透過匯率 API 轉換成你設定的顯示貨幣（如 TWD 或 MYR）。
