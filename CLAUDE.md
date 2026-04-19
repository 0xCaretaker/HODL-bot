# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## How this runs

The only real entry point is `bot.py`, invoked by `.github/workflows/hodl.yml` on a cron schedule. `bollinger_signals.py` and `macd_signals.py` have `__main__` blocks but they are not part of the production path — treat them as import-only modules. There are no tests, linter, or build step.

Local invocation (rarely needed):
```bash
pip install -r requirements.txt
python bot.py
```

## Strategy

Long-only signals for NSE stocks listed in `stocks.txt` (symbols without `.NS` suffix; `bot.py` appends it). The pipeline is:

1. **Bollinger Bands as a universe filter** (`bollinger_signals.py`). 200-period, 2σ. A stock is `Buy` if today's low/close touches or breaks the lower band, `Watch` if it did so within the last 30 bars, else `Hold`. This is the *gate* — MACD output for stocks outside Buy+Watch is discarded from the Telegram message.

2. **MACD crossovers as the long signal** (`macd_signals.py`). Two indicators run in parallel on the same data:
   - Standard MACD (12/26/9 EMA)
   - Impulse MACD (LazyBear — SMMA of high/low, ZLEMA of HLC/3, length_ma=34, signal=9)

   Both feed `_trend_to_action`, which walks the crossover series and emits the *latest* state: `Buy`/`Sell` on the crossover bar, then `Hold` (after Buy) or `Wait for Buy` (after Sell) until the next cross. Only `Buy`/`Sell` rows render as stock lines in Telegram; `Hold`/`Wait for Buy` are counted into the summary.

3. **Telegram delivery** (`bot.py:send_bulk_telegram_message`). MarkdownV2, sent to multiple chat IDs. Two sections: Standard MACD and Impulse MACD, each restricted to the Bollinger-filtered universe. Header includes NIFTY 50 and NIFTY Midcap 100 day move + % from ATH (`get_index_moves`).

## Architecture notes

**Single download, shared DataFrame.** `bot.py` calls `yf.download` once for all tickers (period=1y, interval=1d) and passes that multi-index DataFrame to `process_both_signals` and `process_bollinger_signals`. Per-stock frames are sliced with `data.xs(stock, axis=1, level=1)`. Do not reintroduce per-stock downloads in the hot path.

**Bollinger is the filter, not a co-equal signal.** If you add or change signals, preserve the invariant that MACD lines in Telegram are gated by `bollinger_filter = {Buy, Watch}`. Console output prints full Bollinger results separately.

**MarkdownV2 escaping.** Any dynamic text inserted into the Telegram message must go through `escape_md` — the special-char set is broad (`.`, `-`, `!`, `(`, `)` etc. all require escaping) and unescaped output will cause Telegram to reject the message.

**Data sufficiency guards.** Bollinger needs `length + 30` bars (230 by default); MACD needs ≥50. Tickers with insufficient history are skipped with a `✗` log line. Timestamps are converted to Asia/Kolkata.

**Secrets.** `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_IDS` (comma-separated) are read from environment variables. Set them in GitHub Secrets and pass via the workflow.
