# Stock-Picker-Budget-Allocator-with-Telegram-Alerts

# 📈 Stock Picker & Budget Allocator with Telegram Alerts

This project is a **Python-based stock screening and trade planning tool**.
It scans a universe of stocks, scores them using technical indicators, selects the top performers, allocates a given budget across them, and sends a **buy plan with take-profit and stop-loss levels** to Telegram.

⚠️ **Disclaimer**: This tool is for educational and research purposes only. It does **not** constitute financial advice.


## 🚀 Features

* 📊 Fetches historical stock data from **Yahoo Finance** (`yfinance`)
* 🧠 Scores stocks using:

  * 10-day momentum
  * RSI (Relative Strength Index)
  * SMA20 vs SMA50 trend relationship
  * Recent price change
* 🏆 Selects **Top-N** stocks from a configurable universe
* 💰 Allocates a fixed budget evenly across picks
* 🎯 Computes **take-profit** and **stop-loss** price levels
* 📩 Sends results to **Telegram** (optional)
* 🧪 Debug-friendly with extensive logging


## 📦 Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/IsraelAfriyie-dev/stock-picker-telegram.git
cd stock-picker-telegram
```

### 2️⃣ Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**

* `yfinance`
* `pandas`
* `python-dotenv`
* `requests`
* `ta`

## 🔐 Environment Variables

The  `.env` file in the project root:

```env
UNIVERSE=AAPL,MSFT,AMZN,NVDA,TSLA
TOP_N=3
TAKE_PROFIT_PCT=0.10
STOP_LOSS_PCT=0.05
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Telegram (Optional)

If `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are **not set**, the script will simply print the output to the console.

## ▶️ Usage

### Run interactively

```bash
python stock_picker.py
```

You’ll be prompted to enter your budget:

```
Enter budget in USD (e.g. 1000):
```

### Run with arguments

```bash
python stock_picker.py --budget 2000
```

## 🧠 Scoring Logic (Important)

Each stock is scored using a weighted combination of:

| Indicator          | Description                        |
| ------------------ | ---------------------------------- |
| 10-day Momentum    | Measures recent price acceleration |
| RSI (14)           | Penalizes overbought stocks        |
| SMA20 vs SMA50     | Trend confirmation                 |
| 1-day Price Change | Short-term confirmation            |

Higher score ⇒ better candidate.

## 🎯 Output Example

```
💰 Budget: $1,000.00
📌 Picks (top 3):

1. NVDA — Price $480.50 | Buy shares: 0.6932 | Alloc $333.33
     TP: $528.55 (+10%)  SL: $456.47 (-5%)

2. MSFT — Price $335.20 | Buy shares: 0.9946 | Alloc $333.33
     TP: $368.72 (+10%)  SL: $318.44 (-5%)

3. AAPL — Price $189.10 | Buy shares: 1.7624 | Alloc $333.33
     TP: $208.01 (+10%)  SL: $179.65 (-5%)
```

Main pipeline:

```
Universe → Scoring → Ranking → Allocation → Messaging
```


