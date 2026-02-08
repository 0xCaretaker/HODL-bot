# 📈 Stock Trading Signals Bot

An automated stock trading signals system that combines **Bollinger Bands** and **MACD** indicators to identify potential trading opportunities in Indian stocks (NSE). The bot sends filtered signals directly to Telegram and runs automatically using GitHub Actions.

## 🎯 Features

- **Bollinger Bands Analysis** (200-period)
  - Identifies when price touches or breaks below the lower band
  - Detects recent lower band touches (30-day lookback)
  - Generates "Buy" and "Watch" signals

- **Dual MACD Indicators**
  - Standard MACD (12, 26, 9)
  - Impulse MACD (LazyBear's implementation)
  - Crossover-based Buy/Sell signals

- **Smart Filtering**
  - Only shows MACD signals for stocks with Bollinger "Buy" or "Watch" signals
  - Reduces noise and focuses on high-probability setups

- **Market Context**
  - NIFTY 50 and NIFTY Midcap 100 movements
  - Distance from All-Time High (ATH)

- **Automated Delivery**
  - Telegram notifications with formatted signals
  - Runs automatically via GitHub Actions
  - Supports multiple recipients

## 📊 How It Works

### Signal Generation Logic

1. **Bollinger Bands Filter** (Primary Filter)
   - **Buy**: Price touches or breaks below the 200-period lower Bollinger Band
   - **Watch**: Price previously touched the lower band in the last 30 days
   - **Hold**: No recent interaction with the lower band

2. **MACD Confirmation** (Secondary Signals)
   - Only stocks passing the Bollinger filter are analyzed
   - **Standard MACD**: Traditional 12/26/9 crossover signals
   - **Impulse MACD**: LazyBear's variant using HLC/3 smoothing
   - Generates Buy, Sell, Hold, and "Wait for Buy" signals

3. **Final Output**
   - Console: Full Bollinger Bands results
   - Telegram: MACD signals for Bollinger-filtered stocks only

## 🚀 Setup

### Prerequisites

- Python 3.8+
- Telegram Bot Token
- GitHub account (for automated runs)

### Local Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd stock-signals-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your stock list**
   
   Edit `stocks.txt` and add stock symbols (one per line, without `.NS` suffix):
   ```
   RELIANCE
   TCS
   INFY
   HDFCBANK
   ```

4. **Set up Telegram Bot**
   
   Edit `bot.py` and update:
   ```python
   TELEGRAM_TOKEN = "your_bot_token_here"
   TELEGRAM_CHAT_IDS = ["your_chat_id_here"]
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

### GitHub Actions Setup

1. **Fork/Create the repository** with these files:
   - `bot.py`
   - `macd_signals.py`
   - `bollinger_signals.py`
   - `requirements.txt`
   - `stocks.txt`

2. **Create GitHub Action workflow**
   
   Create `.github/workflows/signals.yml`:
   ```yaml
   name: Stock Signals Bot

   on:
     schedule:
       # Runs at 3:45 PM IST (10:15 AM UTC) on weekdays
       - cron: '15 10 * * 1-5'
     workflow_dispatch:  # Allows manual trigger

   jobs:
     run-bot:
       runs-on: ubuntu-latest
       
       steps:
       - name: Checkout code
         uses: actions/checkout@v3
       
       - name: Set up Python
         uses: actions/setup-python@v4
         with:
           python-version: '3.10'
       
       - name: Install dependencies
         run: |
           pip install -r requirements.txt
       
       - name: Run signals bot
         run: |
           python bot.py
   ```

3. **Configure Telegram credentials**
   
   Option A: Direct in code (less secure)
   - Edit `bot.py` with your token and chat IDs

   Option B: GitHub Secrets (recommended)
   - Go to Settings → Secrets and variables → Actions
   - Add secrets: `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`
   - Modify `bot.py` to read from environment variables:
     ```python
     import os
     TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'fallback_token')
     TELEGRAM_CHAT_IDS = [os.getenv('TELEGRAM_CHAT_ID', 'fallback_id')]
     ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "Setup stock signals bot"
   git push
   ```

5. **Verify automation**
   - Go to Actions tab in GitHub
   - The workflow will run at scheduled time
   - Or click "Run workflow" to test manually

## 📁 File Structure

```
stock-signals-bot/
├── bot.py                  # Main orchestrator + Telegram sender
├── macd_signals.py         # MACD calculations (Standard + Impulse)
├── bollinger_signals.py    # Bollinger Bands calculations
├── requirements.txt        # Python dependencies
├── stocks.txt             # List of stock symbols to monitor
├── .github/
│   └── workflows/
│       └── signals.yml    # GitHub Actions configuration
└── README.md              # This file
```

## 🔧 Configuration

### Adjust Signal Parameters

**Bollinger Bands** (`bollinger_signals.py`):
```python
length = 200        # Moving average period
std_dev = 2         # Standard deviations
lookback = 30       # Days to check for past touches
```

**Standard MACD** (`macd_signals.py`):
```python
fast = 12
slow = 26
signal = 9
```

**Impulse MACD** (`macd_signals.py`):
```python
length_ma = 34
length_signal = 9
```

### Schedule Timing

Edit `.github/workflows/signals.yml` cron expression:
```yaml
# Examples:
- cron: '15 10 * * 1-5'  # 3:45 PM IST, Mon-Fri
- cron: '30 3 * * 1-5'   # 9:00 AM IST, Mon-Fri
- cron: '0 6 * * *'      # 11:30 AM IST, daily
```

**Cron format**: `minute hour day month day-of-week`

> ⚠️ **Note**: GitHub Actions uses UTC time. IST = UTC + 5:30

### Add More Stocks

Simply add new symbols to `stocks.txt` (one per line):
```
TATAMOTORS
WIPRO
ICICIBANK
```

## 📱 Telegram Message Format

```
📊 Signal Alert | [09 February, 03:45PM]

🔺 NIFTY 50: +0.45% (from ATH: -8.23%)
🔻 NIFTY Midcap 100: -0.12% (from ATH: -15.67%)

🔵 STANDARD MACD:
⏱️ 1d
🟢 RELIANCE   ₹2,450.50
🟢 TCS        ₹3,890.25

📈 Summary:
🟣 Wait for Buy: 5/15 (33.3%)
🟡 Hold: 10/15 (66.7%)

🟠 IMPULSE MACD (LazyBear):
⏱️ 1d
🟢 INFY       ₹1,567.80
🔴 WIPRO      ₹445.90

📈 Summary:
🟣 Wait for Buy: 8/15 (53.3%)
🟡 Hold: 7/15 (46.7%)
```

## 🖥️ Console Output

When running locally, you'll see detailed Bollinger Bands analysis:

```
=============================================================
BOLLINGER BANDS (Length=200)
=============================================================

🟢 BUY SIGNALS:
RELIANCE.NS @ ₹2,450.50: Buy
TCS.NS @ ₹3,890.25: Buy

🟣 WATCH SIGNALS:
INFY.NS @ ₹1,567.80: Watch
WIPRO.NS @ ₹445.90: Watch

🟡 HOLD: 45 stocks
```

## 🛠️ Standalone Usage

Each module can run independently:

### Bollinger Bands Only
```bash
python bollinger_signals.py
```

### MACD Signals Only
```bash
python macd_signals.py
```

### Full Bot with Telegram
```bash
python bot.py
```

## 📊 Data Source

- Uses **yfinance** library to fetch historical data
- NSE stocks: Automatically appends `.NS` suffix
- BSE stocks: Use `.BO` suffix in `stocks.txt`
- Data period: 1 year of daily candles

## ⚠️ Important Notes

1. **Not Financial Advice**: This bot is for educational purposes. Always do your own research before trading.

2. **Market Hours**: Best run after market close (3:30 PM IST) for accurate signals.

3. **Data Limitations**: Free data from yfinance may have occasional gaps or delays.

4. **GitHub Actions Limits**: 
   - Free tier: 2,000 minutes/month
   - This bot uses ~2-5 minutes per run
   - Running daily = ~100-150 minutes/month

5. **Rate Limits**: 
   - yfinance may throttle excessive requests
   - Keep stock list under 100 symbols for reliability

**Happy Trading! 📈**
