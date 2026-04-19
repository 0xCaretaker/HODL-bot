# Roadmap

## Backtest Module
- [ ] Run the existing BB + MACD strategy over historical data
- [ ] Report: win rate, avg return per signal, max drawdown, time to recovery
- [ ] Compare Standard MACD vs Impulse MACD signal quality
- [ ] Validate the 200-period BB as a filter vs shorter periods

## Watchlist Management via Telegram
- [ ] `/add SYMBOL` and `/remove SYMBOL` commands
- [ ] Update `stocks.txt` via bot replies (polling or webhook)
- [ ] Confirmation messages with current watchlist count

## Price Alerts (% from 52-week low/high)
- [ ] Calculate distance from 52-week low and high for each stock
- [ ] Flag stocks near 52-week lows that also have BB Watch/Buy
- [ ] Add to Telegram output as additional context

## Historical Signal Log
- [ ] Append each run's signals to a CSV/JSON in the repo
- [ ] Auto-commit via workflow after each run
- [ ] Build dataset to track how signals played out over time
- [ ] Eventually: auto-calculate signal hit rate from the log

## Multi-Timeframe Confirmation
- [ ] Add weekly MACD alongside daily
- [ ] Highlight when daily + weekly MACD align (stronger signal)
- [ ] Separate section or tag in Telegram output
