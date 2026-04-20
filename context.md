# Goal
Long-only signal bot for NSE stocks: BB + Impulse MACD timing strategy with Telegram delivery. Backtest validates the strategy at portfolio level against equal-weight SIP and NIFTY 50.

# Current Status
- **Bot**: Production-ready, runs via GitHub Actions cron (`hodl.yml`)
- **Backtest**: Focused portfolio-level simulation. stocks.txt stocks share a single monthly budget. Compares 3 strategies + NIFTY 50 benchmark. Generates 8 clean PNG charts + console summary.
- **Latest results** (2026-04-20, 61 stocks, ₹27.5L invested over 24 years):
  - Your Strategy (Timed HODL): ₹256L, XIRR 20.3%, Sharpe 0.98, MaxDD -77%
  - SIP on Your Stocks: ₹317L, XIRR 21.9%, Sharpe 0.92, MaxDD -79%
  - SIP on NIFTY 50: ₹34L, XIRR 10.9%, Sharpe 1.13, MaxDD -38%
  - Timed Entry+Exit: ₹9.8L — destroys returns, don't use
  - Cash drag only 6.8% (48/61 stocks got signals across 178 buy days)
  - Timed HODL wins on Sharpe (0.98 vs 0.92), Sortino (1.88 vs 1.58), volatility (41% vs 47%)
  - SIP wins on absolute returns (+19% more final value)
  - Both crush NIFTY 50 by ~10x

# Architecture
- `bot.py` — single entry point. Downloads all tickers once via `yf.download`, passes shared DataFrame to signal modules. Sends MarkdownV2 Telegram messages.
- `bollinger_signals.py` — BB 200-period, 2σ. Gate filter: Buy/Watch/Hold.
- `macd_signals.py` — Standard MACD (12/26/9) + Impulse MACD (LazyBear, SMMA/ZLEMA, length=34, signal=9). Crossover → Buy/Sell/Hold/Wait.
- `backtest.py` — Portfolio-level backtest. Reads stocks.txt, downloads via yfinance, runs 3 strategies + NIFTY 50. Outputs 8 numbered PNG charts + console summary.

# Backtest Charts (backtest_output/)
1. `1_equity_curves.png` — All strategies + NIFTY 50 + invested line on one chart
2. `2_drawdowns.png` — Side-by-side drawdowns with max annotated
3. `3_cash_utilization.png` — % invested vs cash over time
4. `4_regime_returns.png` — Bar chart of returns during bull/bear/sideways/recovery
5. `5_rolling_alpha.png` — 1Y and 3Y rolling outperformance vs SIP
6. `6_buy_distribution.png` — Which stocks got bought and how often
7. `7_buy_timeline.png` — When buys happened over time
8. `8_summary_table.png` — Full metrics table as image, best values highlighted

# Key Design Decisions
- BB is the **gate**, MACD is the **signal** — this invariant must be preserved
- Portfolio-level simulation: single budget split across signaling stocks. Point of 60+ stocks is temporal diversification (something always dipping → less cash drag)
- yfinance v1.x: columns are always MultiIndex `(Price, Ticker)`, no `auto_adjust` param
- Risk-free rate = 6% (India) for Sharpe/Sortino
- Slippage = 5 bps
- Backtest salary: ₹10K/month starting 2000, 25% invested, 10% annual growth

# Key Files
- `bot.py` — production entry point
- `backtest.py` — portfolio-level backtest (run: `python3 backtest.py`)
- `stocks.txt` — watchlist (62 symbols, no `.NS` suffix)
- `backtest_output/` — 8 numbered PNG charts
- `.github/workflows/hodl.yml` — cron schedule
- `requirements.txt` — yfinance, requests (backtest also needs matplotlib, scipy)

# Known Issues
- ~14 stocks from old BROAD_NSE_UNIVERSE are delisted/renamed on Yahoo (MINDTREE→LTIM, etc.)
- `requirements.txt` doesn't include matplotlib/scipy (backtest-only deps)
- Timed HODL has last-price carry-forward for stocks missing data on a given day
