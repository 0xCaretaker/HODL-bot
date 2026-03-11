# HODL Signal Bot

Automated stock trading signals for Indian stocks (NSE) using **Bollinger Bands** and **MACD** indicators, delivered via Telegram. Runs on GitHub Actions.

## How It Works

1. **Bollinger Bands** (200-period) — primary filter
   - **Buy**: Price at or below lower band
   - **Watch**: Lower band touch in last 30 days
   - **Hold**: No recent lower band interaction

2. **MACD** — secondary confirmation (only for Bollinger-filtered stocks)
   - Standard MACD (12/26/9) and Impulse MACD (LazyBear)
   - Generates Buy, Sell, Hold, and "Wait for Buy" signals

3. **Market Context** — NIFTY 50 and NIFTY Midcap 100 movements with ATH distance

## Setup

### Prerequisites

- Python 3.8+
- Telegram Bot Token and Chat ID(s)

### Run Locally

```bash
git clone <your-repo-url>
cd HODL-bot
pip install -r requirements.txt
```

Edit `bot.py` with your Telegram token and chat IDs, then:

```bash
python bot.py
```

### GitHub Actions

The workflow (`.github/workflows/hodl.yml`) runs hourly during market hours on weekdays (`cron: '45 3-9 * * 1-5'` UTC = 9:15 AM–3:15 PM IST).

For secrets, add `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` under Settings > Secrets > Actions, and update `bot.py` to use `os.getenv()`.

## File Structure

```
HODL-bot/
├── bot.py                  # Main orchestrator + Telegram sender
├── macd_signals.py         # Standard + Impulse MACD calculations
├── bollinger_signals.py    # Bollinger Bands calculations
├── requirements.txt        # yfinance, requests
├── stocks.txt              # Stock symbols (one per line, no .NS suffix)
└── .github/workflows/
    └── hodl.yml            # GitHub Actions workflow
```

## Configuration

| Parameter | File | Default |
|-----------|------|---------|
| Bollinger period | `bollinger_signals.py` | 200 |
| Bollinger std dev | `bollinger_signals.py` | 2 |
| Lookback days | `bollinger_signals.py` | 30 |
| MACD fast/slow/signal | `macd_signals.py` | 12/26/9 |
| Impulse MA / signal | `macd_signals.py` | 34/9 |

Add stocks by editing `stocks.txt` (one symbol per line).

## Notes

- **Not financial advice** — for educational purposes only.
- Best run after market close (3:30 PM IST) for final signals.
- Uses [yfinance](https://github.com/ranaroussi/yfinance) — keep stock list under 100 symbols.
- GitHub Actions free tier: ~2,000 min/month; this bot uses ~2–5 min/run.
