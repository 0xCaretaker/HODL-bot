# Algorithmic Trading Bot — Crash-Buy Signals for Indian Equities (NSE)

An automated **algo-trading signal system** that identifies deeply undervalued stocks during market crashes using **200-period Bollinger Bands** and **dual MACD crossovers**, then delivers actionable buy signals with market sentiment to Telegram — fully automated via GitHub Actions.

> **Philosophy**: Buy the crash, hold forever. This bot watches 60+ fundamentally screened NSE stocks and alerts when they hit statistically extreme lows with confirmed momentum reversal. No day-trading, no exits — just long entries at high-conviction dips.
>
> The watchlist in `stocks.txt` is curated via a separate fundamental analysis tool (not included in this repo) — this bot handles the technical timing layer on top of that fundamental filter.

### [Join the Telegram channel to receive live signals](https://t.me/dipmafia)

---

## How It Works

```
┌─────────────────────────────────────┐
│         stocks.txt (watchlist)      │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│     yfinance — 1yr daily OHLCV     │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Bollinger Bands (200-period, 2σ)  │
│  ┌─────┐  ┌───────┐  ┌──────┐     │
│  │ Buy │  │ Watch │  │ Hold │     │
│  └──┬──┘  └───┬───┘  └──┬───┘     │
│     │         │         │ filtered │
│     ▼         ▼         ✗ out     │
│  ┌─────────────────┐              │
│  │   MACD Filter   │              │
│  │  Standard 12/26 │              │
│  │  Impulse MACD   │              │
│  └────────┬────────┘              │
└───────────┼────────────────────────┘
            ▼
┌─────────────────────────────────────┐
│  Sentiment (Hold/Wait for Buy %)   │
│  Bullish · Neutral · Cautious ·    │
│  Bearish                           │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│     Telegram (if signals changed)  │
└─────────────────────────────────────┘
```

### Signal Logic

| Stage | Indicator | Signal | Meaning |
|---|---|---|---|
| **Gate** | Bollinger Bands (200, 2σ) | Buy | Price at or below lower band today |
| | | Watch | Touched lower band in last 30 days |
| | | Hold | No recent lower band interaction — **filtered out** |
| **Signal** | Standard MACD (12/26/9) | Buy/Sell | Crossover on current bar |
| | Impulse MACD (LazyBear) | Buy/Sell | SMMA + ZLEMA crossover on current bar |
| | Both | Hold / Wait for Buy | Between crossovers |
| **Context** | NIFTY 50 + Midcap 100 | % move, % from ATH | Market-wide context |
| **Sentiment** | Hold vs Wait ratio | Bullish/Neutral/Cautious/Bearish | Aggregate market mood |

### Deduplication

Signals are hashed each run. If unchanged from the previous run, Telegram notifications are skipped — no spam during sideways markets.

## Sample Output

```
📊 Signal Alert | 19 April, 03:15PM
🔻 NIFTY 50: -3.42% (from ATH: -18.50%)
🔻 NIFTY Midcap 100: -4.10% (from ATH: -25.30%)
🔴 Sentiment: Bearish

🔵 STANDARD MACD:
⏱️ 1d
🟢 SUZLON      ₹38.50
🟢 GRSE        ₹1850.00

📈 Summary:
🟣 Wait for Buy: 25/34 (73.5%)
🟡 Hold: 7/34 (20.6%)

🟠 IMPULSE MACD (LazyBear):
⏱️ 1d Impulse MACD
🟢 SUZLON      ₹38.50
🟢 GRSE        ₹1850.00
🟢 AIIL        ₹320.00

📈 Summary:
🟣 Wait for Buy: 28/34 (82.4%)
🟡 Hold: 4/34 (11.8%)
```

## Quick Start

### 1. Fork & configure secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Value |
|---|---|
| `TELEGRAM_TOKEN` | Your bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_IDS` | Comma-separated chat IDs |

### 2. Edit your watchlist

`stocks.txt` — one NSE symbol per line, without `.NS`:
```
RELIANCE
TCS
INFY
```

### 3. Done

The bot runs automatically:
- **Weekdays**: every hour, 9:15 AM – 3:15 PM IST (market hours)
- **Weekends**: once at 10:15 AM IST

Or trigger manually: **Actions tab → Run workflow**

### Local run

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="your_token"
export TELEGRAM_CHAT_IDS="id1,id2"
python bot.py
```

## Backtest

A portfolio-level backtest validates the timing strategy against plain SIP investing. All stocks in `stocks.txt` share a single monthly budget — the point of 60+ stocks is that something is always dipping, keeping cash deployed.

### Run it

```bash
pip install matplotlib scipy  # one-time, in addition to requirements.txt
python3 backtest.py
```

Generates 8 charts in `backtest_output/` + console summary.

### Latest Results (61 stocks, 2010–2026)

```
════════════════════════════════════════════════════════════════════════════════════════════════════
  INVESTMENT ASSUMPTIONS
────────────────────────────────────────────────────────────────────────────────────────────────────
  Period:             2010-01-04 → 2026-04-17 (16.3 years)
  Starting salary:    ₹22,000/month → ₹101,089/month (10% annual hike)
  Monthly SIP:        ₹5,500 → ₹25,272 (25% of salary)
  Total invested:     ₹24.7L (inflation-adjusted: ₹9.6L in 2010 rupees)
  Inflation (6%/yr):  ₹1 in 2010 = ₹2.6 today

════════════════════════════════════════════════════════════════════════════════════════════════════
  RESULTS — 61 stocks, ₹24.7L invested
════════════════════════════════════════════════════════════════════════════════════════════════════
                            Your Strategy (Timed HODL)     SIP on Your Stocks       Timed Entry+Exit        SIP on NIFTY 50
  ───────────────────────────────────────────────────────────────────────────────────────────────
  Final Value                              ₹194.2L                ₹197.3L                  ₹9.9L                 ₹52.3L
  Inflation-Adj Value                       ₹75.2L                 ₹76.4L                  ₹3.8L                 ₹20.2L
  Wealth Multiple                             7.9x                   8.0x                   0.4x                   2.1x
  Real Multiple (infl-adj)                    3.0x                   3.1x                   0.2x                   0.8x
  XIRR                                       26.9%                  27.0%                 -18.5%                  10.9%
  Real XIRR (minus 6% infl)                  20.9%                  21.0%                 -24.5%                   4.9%
  Sharpe                                      1.24                   1.28                   0.76                   1.13
  Sortino                                     2.83                   3.00                   1.58                   3.40
  Max Drawdown                              -54.1%                 -63.6%                 -55.6%                 -37.3%
  Max DD Duration                         733 days               820 days               589 days               183 days
  Volatility                                 42.8%                  40.7%                  49.2%                  37.7%

  Buy signals fired on 136 days across 46/61 stocks
  Cash drag (Your Strategy): 6.2%
```

### Key Findings

| Metric | Your Strategy | SIP (same stocks) | NIFTY 50 SIP |
|---|---|---|---|
| Final Value | ₹194L | ₹197L | ₹52L |
| Inflation-Adjusted | ₹75L | ₹76L | ₹20L |
| XIRR | 26.9% | 27.0% | 10.9% |
| Real XIRR (−6% inflation) | **20.9%** | 21.0% | 4.9% |
| Sharpe | 1.24 | **1.28** | 1.13 |
| Sortino | 2.83 | 3.00 | 3.40 |
| Max Drawdown | **-54%** | -64% | -37% |
| Volatility | 42.8% | **40.7%** | 37.7% |

- **Both strategies crush NIFTY 50 by ~4x** — stock picking matters more than timing
- **Timed HODL and SIP are neck-and-neck on returns** — but Timed HODL has significantly lower max drawdown (-54% vs -64%)
- **Real returns beat inflation easily** — 20.9% real XIRR for Timed HODL vs 4.9% for NIFTY 50
- **Cash drag is only 6.2%** — 60+ stocks keep money deployed
- **Entry+Exit is terrible** — selling on MACD Sell destroys compounding

### Charts

| Chart | What it shows |
|---|---|
| `1_equity_curves.png` | All strategies + NIFTY 50 on one chart |
| `2_drawdowns.png` | How deep each strategy fell from peak |
| `3_cash_utilization.png` | % of money actually invested vs cash |
| `4_regime_returns.png` | Returns during bull, bear, sideways, recovery |
| `5_rolling_alpha.png` | When your strategy beats/loses to SIP |
| `6_buy_distribution.png` | Which stocks got bought most often |
| `7_buy_timeline.png` | When buys happened over time |
| `8_summary_table.png` | Full metrics table with best values highlighted |

![Equity Curves](backtest_output/1_equity_curves.png)
![Regime Returns](backtest_output/4_regime_returns.png)
![Summary Table](backtest_output/8_summary_table.png)

## Architecture

```
├── bot.py                 # Orchestrator, Telegram sender, sentiment
├── macd_signals.py        # Standard + Impulse MACD (standalone capable)
├── bollinger_signals.py   # 200-period Bollinger Bands (standalone capable)
├── stocks.txt             # Watchlist
├── requirements.txt       # yfinance, requests
└── .github/workflows/
    └── hodl.yml           # GitHub Actions (cron + cache)
```

Each signal module can run standalone for quick analysis:
```bash
python bollinger_signals.py   # Bollinger only
python macd_signals.py        # MACD only
```

## Configuration

| Parameter | File | Default |
|---|---|---|
| BB period | `bollinger_signals.py` | 200 |
| BB std dev | `bollinger_signals.py` | 2 |
| BB watch window | `bollinger_signals.py` | 30 bars |
| MACD fast/slow/signal | `macd_signals.py` | 12/26/9 |
| Impulse MA length | `macd_signals.py` | 34 |
| Impulse signal length | `macd_signals.py` | 9 |

## Disclaimer

This is not financial advice. The bot generates signals for educational and research purposes. Always do your own due diligence before making investment decisions.
