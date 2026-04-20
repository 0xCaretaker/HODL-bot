#!/usr/bin/env python3
"""
Backtest: Portfolio-level BB + Impulse MACD timed investing vs SIP.

Uses stocks from stocks.txt as a single portfolio with shared monthly budget.
Compares: Your Strategy (Timed HODL) vs SIP on same stocks vs SIP on NIFTY 50.

Run: python3 backtest.py
Output: console summary + PNG charts in backtest_output/
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from scipy.optimize import brentq
from macd_signals import calc_smma, calc_zlema, to_1d

warnings.filterwarnings("ignore")

OUTPUT_DIR = "backtest_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

C_SIP     = "#2196F3"
C_TIMED   = "#4CAF50"
C_EXIT    = "#FF9800"
C_NIFTY   = "#9C27B0"
C_RED     = "#F44336"
C_YELLOW  = "#FFC107"
C_GRAY    = "#9E9E9E"

LABEL_SIP   = "SIP on Your Stocks"
LABEL_TIMED = "Your Strategy (Timed HODL)"
LABEL_EXIT  = "Timed Entry+Exit"
LABEL_NIFTY = "SIP on NIFTY 50"

CONFIG = {
    "start": "2000-01-01",
    "end": "2026-04-20",
    "initial_salary": 10_000,
    "invest_pct": 0.25,
    "salary_growth": 0.10,
    "bb_length": 200,
    "bb_std": 2,
    "bb_lookback": 30,
    "impulse_length_ma": 34,
    "impulse_length_signal": 9,
    "slippage_bps": 5,
}

REGIMES = {
    "Dot-com crash\n(2000-03)":     ("2000-01-01", "2003-05-01", "Bear/Crash"),
    "Bull run\n(2003-08)":          ("2003-05-01", "2008-01-01", "Bull"),
    "GFC crash\n(2008)":            ("2008-01-01", "2009-03-31", "Bear/Crash"),
    "Recovery\n(2009-15)":          ("2009-04-01", "2015-03-01", "Recovery"),
    "Sideways\n(2015-20)":          ("2015-03-01", "2020-01-01", "Sideways"),
    "COVID\n(2020)":                ("2020-01-01", "2020-06-01", "Bear/Crash"),
    "Post-COVID\nbull (20-22)":     ("2020-06-01", "2022-01-01", "Bull"),
    "2022\nbear":                   ("2022-01-01", "2023-01-01", "Bear/Crash"),
    "Recent bull\n(2023+)":         ("2023-01-01", "2026-12-31", "Bull"),
}

REGIME_BG = {"Bull": "#4CAF5015", "Bear/Crash": "#F4433615", "Sideways": "#FFC10715", "Recovery": "#2196F315"}


# ─── Data ───────────────────────────────────────────────────────────────────

def flatten_cols(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def extract_stock(data, symbol):
    if not isinstance(data.columns, pd.MultiIndex):
        return data
    if symbol not in data.columns.get_level_values(1).unique():
        return pd.DataFrame()
    return data.xs(symbol, axis=1, level=1)

def download_batch(symbols, cfg, batch_size=30):
    all_data = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        print(f"  Downloading batch {i//batch_size+1}/{(len(symbols)+batch_size-1)//batch_size} ({len(batch)} symbols)...")
        data = yf.download(batch, start=cfg["start"], end=cfg["end"], progress=False)
        if data.empty:
            continue
        for sym in batch:
            try:
                df = (flatten_cols(data) if len(batch) == 1 else extract_stock(data, sym)).dropna()
                if not df.empty:
                    all_data[sym] = df
            except:
                pass
    return all_data


# ─── Signals ────────────────────────────────────────────────────────────────

def bb_signals(df, length=200, std_dev=2, lookback=30):
    close, low = df["Close"].values, df["Low"].values
    mid = pd.Series(close).rolling(length).mean().values
    std = pd.Series(close).rolling(length).std().values
    lower = mid - std_dev * std
    touch = (low <= lower) | (close <= lower)
    past = pd.Series(touch).rolling(lookback, min_periods=1).max().shift(1).fillna(0).astype(bool).values
    sig = pd.Series("Hold", index=df.index)
    sig.values[touch] = "Buy"
    sig.values[~touch & past] = "Watch"
    return sig

def impulse_macd_signals(df, length_ma=34, length_signal=9):
    high, low, close = to_1d(df["High"]), to_1d(df["Low"]), to_1d(df["Close"])
    src = (high + low + close) / 3.0
    hi, lo = calc_smma(high, length_ma), calc_smma(low, length_ma)
    mi = calc_zlema(src, length_ma)
    md = np.where(mi > hi, mi - hi, np.where(mi < lo, mi - lo, 0.0))
    sb = pd.Series(md).rolling(length_signal).mean().values
    prev_md, prev_sb = np.concatenate([[np.nan], md[:-1]]), np.concatenate([[np.nan], sb[:-1]])
    sig = pd.Series("Neutral", index=df.index)
    sig[(prev_md < prev_sb) & (md > sb)] = "Buy"
    sig[(prev_md > prev_sb) & (md < sb)] = "Sell"
    state = sig.copy()
    last = "Wait"
    for i in range(len(state)):
        v = state.iloc[i]
        if v == "Buy": last = "Hold"
        elif v == "Sell": last = "Wait"
        elif last == "Hold": state.iloc[i] = "Hold"
        else: state.iloc[i] = "Wait"
    return sig, state

def generate_all_signals(stock_dfs, cfg):
    min_bars = cfg["bb_length"] + cfg["bb_lookback"] + 50
    bb, imp, imp_st, skipped = {}, {}, {}, []
    for sym, df in stock_dfs.items():
        if len(df) < min_bars:
            skipped.append(sym); continue
        bb[sym] = bb_signals(df, cfg["bb_length"], cfg["bb_std"], cfg["bb_lookback"])
        s, st = impulse_macd_signals(df, cfg["impulse_length_ma"], cfg["impulse_length_signal"])
        imp[sym] = s; imp_st[sym] = st
    return bb, imp, imp_st, skipped


# ─── Monthly investment schedule ────────────────────────────────────────────

def build_monthly_investments(dates, cfg):
    start_year, start_month = dates[0].year, dates[0].month
    inv = {}
    for dt in dates:
        me = (dt.year - start_year) * 12 + (dt.month - start_month)
        salary = cfg["initial_salary"] * (1 + cfg["salary_growth"]) ** int(me / 12.0)
        key = (dt.year, dt.month)
        if key not in inv:
            inv[key] = {"date": dt, "amount": round(salary * cfg["invest_pct"], 2)}
    return inv


# ─── Portfolio simulations ──────────────────────────────────────────────────

def get_all_dates(stock_dfs, symbols):
    dates = set()
    for s in symbols:
        if s in stock_dfs:
            dates.update(stock_dfs[s].index)
    return sorted(dates)

def _update_prices(last_price, stock_dfs, symbols, dt):
    for s in symbols:
        if s in stock_dfs and dt in stock_dfs[s].index:
            last_price[s] = stock_dfs[s].loc[dt, "Close"]

def _portfolio_value(holdings, last_price, symbols, cash):
    val = cash
    for s in symbols:
        if holdings[s] > 0 and last_price[s] > 0:
            val += holdings[s] * last_price[s]
    return val

def simulate_sip(stock_dfs, symbols, monthly_inv, slippage_bps=5):
    dates = get_all_dates(stock_dfs, symbols)
    holdings = {s: 0.0 for s in symbols}
    last_price = {s: 0.0 for s in symbols}
    cash = 0.0
    done_months = set()
    records, cashflows = [], []
    for dt in dates:
        _update_prices(last_price, stock_dfs, symbols, dt)
        key = (dt.year, dt.month)
        if key in monthly_inv and key not in done_months:
            amt = monthly_inv[key]["amount"]
            cash += amt; done_months.add(key); cashflows.append((dt, -amt))
            avail = [s for s in symbols if s in stock_dfs and dt in stock_dfs[s].index]
            if avail:
                per = cash / len(avail)
                for s in avail:
                    holdings[s] += per / (last_price[s] * (1 + slippage_bps / 10000))
                cash = 0.0
        records.append({"date": dt, "portfolio": _portfolio_value(holdings, last_price, symbols, cash), "cash": cash})
    return pd.DataFrame(records).set_index("date"), cashflows

def simulate_timed_hodl(stock_dfs, symbols, monthly_inv, bb_sig, imp_sig, slippage_bps=5):
    dates = get_all_dates(stock_dfs, symbols)
    holdings = {s: 0.0 for s in symbols}
    last_price = {s: 0.0 for s in symbols}
    cash = 0.0
    done_months = set()
    records, cashflows, buy_log = [], [], []
    for dt in dates:
        _update_prices(last_price, stock_dfs, symbols, dt)
        key = (dt.year, dt.month)
        if key in monthly_inv and key not in done_months:
            amt = monthly_inv[key]["amount"]
            cash += amt; done_months.add(key); cashflows.append((dt, -amt))
        if cash > 0:
            buying = [s for s in symbols
                      if s in bb_sig and s in imp_sig
                      and dt in bb_sig[s].index and dt in imp_sig[s].index
                      and bb_sig[s].loc[dt] in ("Buy", "Watch") and imp_sig[s].loc[dt] == "Buy"]
            if buying:
                per = cash / len(buying)
                for s in buying:
                    holdings[s] += per / (last_price[s] * (1 + slippage_bps / 10000))
                    buy_log.append({"date": dt, "stock": s, "price": last_price[s], "amount": per})
                cash = 0.0
        records.append({"date": dt, "portfolio": _portfolio_value(holdings, last_price, symbols, cash), "cash": cash})
    return pd.DataFrame(records).set_index("date"), cashflows, buy_log

def simulate_timed_exit(stock_dfs, symbols, monthly_inv, bb_sig, imp_sig, imp_state, slippage_bps=5):
    dates = get_all_dates(stock_dfs, symbols)
    holdings = {s: 0.0 for s in symbols}
    last_price = {s: 0.0 for s in symbols}
    cash = 0.0
    done_months = set()
    records, cashflows, trade_log = [], [], []
    for dt in dates:
        _update_prices(last_price, stock_dfs, symbols, dt)
        key = (dt.year, dt.month)
        if key in monthly_inv and key not in done_months:
            amt = monthly_inv[key]["amount"]
            cash += amt; done_months.add(key); cashflows.append((dt, -amt))
        for s in symbols:
            if holdings[s] > 0 and s in imp_sig and dt in imp_sig[s].index and imp_sig[s].loc[dt] == "Sell":
                proceeds = holdings[s] * last_price[s] * (1 - slippage_bps / 10000)
                trade_log.append({"date": dt, "type": "SELL", "stock": s, "price": last_price[s], "proceeds": proceeds})
                cash += proceeds; holdings[s] = 0.0
        if cash > 0:
            buying = [s for s in symbols
                      if s in bb_sig and s in imp_sig
                      and dt in bb_sig[s].index and dt in imp_sig[s].index
                      and bb_sig[s].loc[dt] in ("Buy", "Watch") and imp_sig[s].loc[dt] == "Buy"]
            if buying:
                per = cash / len(buying)
                for s in buying:
                    holdings[s] += per / (last_price[s] * (1 + slippage_bps / 10000))
                    trade_log.append({"date": dt, "type": "BUY", "stock": s, "price": last_price[s], "amount": per})
                cash = 0.0
        records.append({"date": dt, "portfolio": _portfolio_value(holdings, last_price, symbols, cash), "cash": cash})
    return pd.DataFrame(records).set_index("date"), cashflows, trade_log

def simulate_nifty_sip(cfg, slippage_bps=5):
    print("  Downloading NIFTY 50...")
    data = yf.download("^NSEI", start=cfg["start"], end=cfg["end"], progress=False)
    if data.empty:
        return None, None
    data = flatten_cols(data).dropna()
    monthly_inv = build_monthly_investments(data.index, cfg)
    units = cash = 0.0
    done_months = set()
    records, cashflows = [], []
    for dt, row in data.iterrows():
        price = row["Close"]
        key = (dt.year, dt.month)
        if key in monthly_inv and key not in done_months:
            amt = monthly_inv[key]["amount"]
            cash += amt; done_months.add(key); cashflows.append((dt, -amt))
            units += cash / (price * (1 + slippage_bps / 10000))
            cash = 0.0
        records.append({"date": dt, "portfolio": units * price + cash, "cash": cash})
    return pd.DataFrame(records).set_index("date"), cashflows


# ─── Metrics ────────────────────────────────────────────────────────────────

def compute_xirr(cashflows, final_value, final_date):
    cfs = list(cashflows) + [(final_date, final_value)]
    t0 = cfs[0][0]
    years = [(d - t0).days / 365.25 for d, _ in cfs]
    amounts = [a for _, a in cfs]
    try:
        return brentq(lambda r: sum(a / (1+r)**y for a, y in zip(amounts, years)), -0.5, 10.0) * 100
    except (ValueError, RuntimeError):
        return np.nan

def compute_metrics(series, name, cashflows=None):
    dr = series.pct_change().dropna().replace([np.inf, -np.inf], 0)
    yrs = (series.index[-1] - series.index[0]).days / 365.25
    if yrs <= 0:
        return {k: 0 for k in ["name","final_value","total_return","cagr","xirr","sharpe","sortino","max_drawdown","max_dd_days","calmar","volatility","best_day","worst_day"]}
    tr = series.iloc[-1] / series.iloc[0] - 1
    cagr = (1 + tr) ** (1 / yrs) - 1
    rf = (1.06) ** (1/252) - 1
    ex = dr - rf
    sharpe = np.sqrt(252) * ex.mean() / ex.std() if ex.std() > 0 else 0
    down = ex[ex < 0]
    sortino = np.sqrt(252) * ex.mean() / down.std() if len(down) > 0 and down.std() > 0 else 0
    dd = (series - series.cummax()) / series.cummax()
    max_dd = dd.min()
    dd_dur = max_dd_dur = 0
    for d in dd:
        if d < 0: dd_dur += 1; max_dd_dur = max(max_dd_dur, dd_dur)
        else: dd_dur = 0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0
    xirr = compute_xirr(cashflows, series.iloc[-1], series.index[-1]) if cashflows else np.nan
    return {"name": name, "final_value": series.iloc[-1], "total_return": tr*100, "cagr": cagr*100, "xirr": xirr,
            "sharpe": sharpe, "sortino": sortino, "max_drawdown": max_dd*100, "max_dd_days": max_dd_dur,
            "calmar": calmar, "volatility": dr.std()*np.sqrt(252)*100, "best_day": dr.max()*100, "worst_day": dr.min()*100}


# ─── Charts ─────────────────────────────────────────────────────────────────

def _style_ax(ax, ylabel="", title=""):
    ax.set_ylabel(ylabel, fontsize=10)
    if title: ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(labelsize=9)
    ax.grid(True, alpha=0.3)

def _rupee_fmt(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'₹{x/100000:.1f}L' if x >= 100000 else f'₹{x:,.0f}'))


def chart_1_equity(portfolios, nifty_series, total_invested, filename):
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(portfolios[LABEL_TIMED].index, portfolios[LABEL_TIMED].values, color=C_TIMED, linewidth=2.2, label=LABEL_TIMED, zorder=4)
    ax.plot(portfolios[LABEL_SIP].index, portfolios[LABEL_SIP].values, color=C_SIP, linewidth=1.8, label=LABEL_SIP, zorder=3)
    ax.plot(portfolios[LABEL_EXIT].index, portfolios[LABEL_EXIT].values, color=C_EXIT, linewidth=1.3, alpha=0.7, label=LABEL_EXIT, zorder=2)
    if nifty_series is not None:
        ax.plot(nifty_series.index, nifty_series.values, color=C_NIFTY, linewidth=1.3, linestyle="--", label=LABEL_NIFTY, zorder=1)
    inv_dates = sorted(portfolios[LABEL_SIP].index)
    cum_inv = []
    inv = 0
    monthly_seen = set()
    for dt in inv_dates:
        key = (dt.year, dt.month)
        if key not in monthly_seen:
            monthly_seen.add(key)
            inv += 2500
        cum_inv.append(inv)
    ax.plot(inv_dates, cum_inv, color=C_GRAY, linewidth=1, linestyle=":", alpha=0.6, label="Total Invested")

    _style_ax(ax, "Portfolio Value", "Portfolio Growth: Your Strategy vs SIP vs NIFTY 50")
    _rupee_fmt(ax)
    ax.legend(loc="upper left", fontsize=10, framealpha=0.9)

    final_timed = portfolios[LABEL_TIMED].iloc[-1]
    final_sip = portfolios[LABEL_SIP].iloc[-1]
    ax.annotate(f'₹{final_timed/100000:.1f}L', xy=(portfolios[LABEL_TIMED].index[-1], final_timed),
                fontsize=10, fontweight="bold", color=C_TIMED, ha="left", va="bottom")
    ax.annotate(f'₹{final_sip/100000:.1f}', xy=(portfolios[LABEL_SIP].index[-1], final_sip),
                fontsize=9, color=C_SIP, ha="left", va="top")

    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_2_drawdowns(portfolios, nifty_series, filename):
    items = [(LABEL_TIMED, C_TIMED), (LABEL_SIP, C_SIP)]
    if nifty_series is not None:
        items.append((LABEL_NIFTY, C_NIFTY))

    fig, axes = plt.subplots(len(items), 1, figsize=(14, 3.5 * len(items)), sharex=True)
    if len(items) == 1: axes = [axes]
    for ax, (name, color) in zip(axes, items):
        pf = nifty_series if name == LABEL_NIFTY else portfolios[name]
        dd = (pf - pf.cummax()) / pf.cummax() * 100
        ax.fill_between(dd.index, dd.values, 0, color=color, alpha=0.35)
        ax.plot(dd.index, dd.values, color=color, linewidth=0.7)
        ax.set_ylim(min(dd.min() * 1.15, -5), 5)
        _style_ax(ax, "Drawdown %", name)
        ax.annotate(f'Max: {dd.min():.1f}%', xy=(dd.idxmin(), dd.min()), fontsize=9, fontweight="bold",
                    color=color, ha="center", va="top")

    fig.suptitle("Drawdowns — How Much Did Each Strategy Fall From Peak?", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_3_cash(timed_sim, exit_sim, filename):
    fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    for ax, (sim, name, color) in zip(axes, [(timed_sim, LABEL_TIMED, C_TIMED), (exit_sim, LABEL_EXIT, C_EXIT)]):
        total = sim["portfolio"].replace(0, np.nan)
        cash_pct = (sim["cash"] / total * 100).fillna(100)
        invested_pct = 100 - cash_pct
        ax.fill_between(invested_pct.index, invested_pct.values, 0, color=color, alpha=0.4, label="Invested")
        ax.fill_between(invested_pct.index, 100, invested_pct.values, color=C_GRAY, alpha=0.2, label="Cash")
        ax.set_ylim(0, 105)
        _style_ax(ax, "% of Portfolio", name)
        avg_inv = invested_pct.mean()
        ax.axhline(avg_inv, color=color, linestyle="--", linewidth=0.8, alpha=0.7)
        ax.annotate(f'Avg {avg_inv:.0f}% invested', xy=(invested_pct.index[len(invested_pct)//2], avg_inv + 3),
                    fontsize=9, color=color, fontweight="bold")
        ax.legend(loc="lower right", fontsize=9)

    fig.suptitle("Cash Utilization — How Much of Your Money Is Actually Working?", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_4_regimes(portfolios, nifty_series, filename):
    all_series = dict(portfolios)
    if nifty_series is not None:
        all_series[LABEL_NIFTY] = nifty_series
    strats = [LABEL_TIMED, LABEL_SIP, LABEL_NIFTY] if nifty_series is not None else [LABEL_TIMED, LABEL_SIP]
    colors = {LABEL_TIMED: C_TIMED, LABEL_SIP: C_SIP, LABEL_NIFTY: C_NIFTY}

    regime_names = list(REGIMES.keys())
    data_rows = []
    for rname in regime_names:
        start, end, rtype = REGIMES[rname]
        row = {"regime": rname, "type": rtype}
        for sname in strats:
            pf = all_series.get(sname)
            if pf is None:
                row[sname] = np.nan; continue
            sub = pf[(pf.index >= start) & (pf.index <= end)]
            row[sname] = (sub.iloc[-1] / sub.iloc[0] - 1) * 100 if len(sub) >= 2 else np.nan
        data_rows.append(row)

    x = np.arange(len(regime_names))
    width = 0.8 / len(strats)
    fig, ax = plt.subplots(figsize=(16, 7))
    for i, sname in enumerate(strats):
        vals = [r[sname] if not np.isnan(r.get(sname, np.nan)) else 0 for r in data_rows]
        bars = ax.bar(x + i * width - 0.4 + width/2, vals, width, label=sname, color=colors[sname], edgecolor="white", zorder=3)
        for bar, val in zip(bars, vals):
            if val != 0:
                va = "bottom" if val > 0 else "top"
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{val:+.0f}%',
                        ha='center', va=va, fontsize=7, fontweight="bold")

    for j, row in enumerate(data_rows):
        c = REGIME_BG.get(row["type"], "#EEEEEE15")
        ax.axvspan(j - 0.45, j + 0.45, color=c, zorder=0)

    ax.set_xticks(x)
    ax.set_xticklabels(regime_names, fontsize=9)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(fontsize=10)
    _style_ax(ax, "Return %", "How Each Strategy Performed in Different Market Conditions")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_5_rolling_alpha(portfolios, filename):
    sip = portfolios[LABEL_SIP]
    timed = portfolios[LABEL_TIMED]
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for ax, (window, label) in zip(axes, [(252, "1-Year Rolling"), (252*3, "3-Year Rolling")]):
        sip_r = (sip / sip.shift(window) - 1) * 100
        timed_r = (timed / timed.shift(window) - 1) * 100
        alpha = (timed_r - sip_r).dropna()
        if len(alpha) == 0: continue
        pos = alpha.clip(lower=0)
        neg = alpha.clip(upper=0)
        ax.fill_between(pos.index, pos.values, 0, color=C_TIMED, alpha=0.5, label="Your Strategy wins")
        ax.fill_between(neg.index, neg.values, 0, color=C_RED, alpha=0.5, label="SIP wins")
        ax.axhline(0, color="black", linewidth=0.5)
        pct_win = (alpha > 0).mean() * 100
        _style_ax(ax, "Alpha %", f"{label} — Your Strategy outperforms {pct_win:.0f}% of the time")
        ax.legend(loc="upper left", fontsize=9)

    fig.suptitle("Rolling Outperformance: Your Strategy vs SIP on Same Stocks", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_6_buy_distribution(buy_log, n_stocks, filename):
    counts = {}
    for b in buy_log:
        sym = b["stock"].replace(".NS", "")
        counts[sym] = counts.get(sym, 0) + 1
    if not counts: return

    sorted_stocks = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top = sorted_stocks[:25]
    syms = [s[0] for s in top]
    vals = [s[1] for s in top]
    never = n_stocks - len(counts)

    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh(range(len(syms)), vals, color=C_TIMED, edgecolor="white")
    ax.set_yticks(range(len(syms)))
    ax.set_yticklabels(syms, fontsize=10)
    ax.invert_yaxis()
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, str(val),
                va="center", fontsize=9, fontweight="bold")
    _style_ax(ax, "", f"Which Stocks Got Bought? (top 25 of {len(counts)}, {never} never triggered)")
    ax.set_xlabel("Number of Buy Signals", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_7_buy_timeline(buy_log, filename):
    if not buy_log: return
    dates = [b["date"] for b in buy_log]
    amounts = [b["amount"] for b in buy_log]
    stocks = [b["stock"].replace(".NS", "") for b in buy_log]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.scatter(dates, amounts, c=C_TIMED, s=20, alpha=0.6, edgecolors="white", linewidth=0.3, zorder=3)

    by_month = {}
    for d, a in zip(dates, amounts):
        key = (d.year, d.month)
        by_month[key] = by_month.get(key, 0) + a
    m_dates = [pd.Timestamp(year=k[0], month=k[1], day=15) for k in sorted(by_month)]
    m_vals = [by_month[k] for k in sorted(by_month)]
    ax.bar(m_dates, m_vals, width=25, color=C_TIMED, alpha=0.2, zorder=1)

    _style_ax(ax, "Amount Deployed (₹)", f"When Did Your Strategy Buy? ({len(buy_log)} buys across {len(set(stocks))} stocks)")
    _rupee_fmt(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_8_summary_table(metrics_list, total_invested, n_stocks, n_signals, n_stocks_bought, filename):
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis("off")

    rows = [
        ("Final Value", [f'₹{m["final_value"]/100000:.1f}L' for m in metrics_list]),
        ("Total Invested", [f'₹{total_invested/100000:.1f}L'] * len(metrics_list)),
        ("Wealth Multiple", [f'{m["final_value"]/total_invested:.1f}x' for m in metrics_list]),
        ("XIRR (True Return)", [f'{m["xirr"]:.1f}%' if not np.isnan(m["xirr"]) else "—" for m in metrics_list]),
        ("CAGR", [f'{m["cagr"]:.1f}%' for m in metrics_list]),
        ("Sharpe Ratio", [f'{m["sharpe"]:.2f}' for m in metrics_list]),
        ("Sortino Ratio", [f'{m["sortino"]:.2f}' for m in metrics_list]),
        ("Max Drawdown", [f'{m["max_drawdown"]:.1f}%' for m in metrics_list]),
        ("Max DD Duration", [f'{m["max_dd_days"]} days' for m in metrics_list]),
        ("Volatility (annual)", [f'{m["volatility"]:.1f}%' for m in metrics_list]),
        ("Best Single Day", [f'{m["best_day"]:+.1f}%' for m in metrics_list]),
        ("Worst Single Day", [f'{m["worst_day"]:+.1f}%' for m in metrics_list]),
    ]

    col_labels = [m["name"] for m in metrics_list]
    row_labels = [r[0] for r in rows]
    cell_text = [r[1] for r in rows]

    colors_header = [C_TIMED, C_SIP, C_EXIT, C_NIFTY][:len(col_labels)]
    table = ax.table(cellText=cell_text, rowLabels=row_labels, colLabels=col_labels,
                     cellLoc="center", rowLoc="right", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.6)

    for j, color in enumerate(colors_header):
        table[0, j].set_facecolor(color)
        table[0, j].set_text_props(color="white", fontweight="bold", fontsize=12)

    for i in range(len(rows)):
        table[i+1, -1].set_text_props(fontweight="bold", fontsize=10)
        for j in range(len(col_labels)):
            table[i+1, j].set_facecolor("#f8f9fa" if i % 2 == 0 else "white")

    best_vals = {"Final Value": max, "XIRR (True Return)": max, "Sharpe Ratio": max, "Sortino Ratio": max,
                 "Max Drawdown": max, "Volatility (annual)": min}
    for i, (rname, vals) in enumerate(rows):
        if rname in best_vals:
            fn = best_vals[rname]
            numeric = []
            for v in vals:
                try: numeric.append(float(v.replace("₹","").replace("L","").replace("x","").replace("%","").replace("days","").replace(",","").replace("—","nan")))
                except: numeric.append(np.nan)
            if any(not np.isnan(n) for n in numeric):
                if rname == "Max Drawdown":
                    best_j = numeric.index(fn(n for n in numeric if not np.isnan(n)))
                elif rname == "Volatility (annual)":
                    best_j = numeric.index(fn(n for n in numeric if not np.isnan(n)))
                else:
                    best_j = numeric.index(fn(n for n in numeric if not np.isnan(n)))
                table[i+1, best_j].set_text_props(fontweight="bold", color=colors_header[best_j])

    ax.set_title(f"Performance Summary — {n_stocks} Stocks, {n_signals} Buy Signals, {n_stocks_bought} Stocks Bought",
                 fontsize=14, fontweight="bold", pad=20)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ─── Console output ────────────────────────────────────────────────────────

def print_summary(metrics_list, total_invested, n_stocks, n_signals, n_bought, cash_pct):
    print(f"\n{'═'*80}")
    print(f"  RESULTS — {n_stocks} stocks, ₹{total_invested/100000:.1f}L invested")
    print(f"{'═'*80}")
    hdr = f"  {'':25s}" + "".join(f" {m['name']:>22s}" for m in metrics_list)
    print(hdr)
    print(f"  {'─'*75}")
    rows = [
        ("Final Value", [f"₹{m['final_value']/100000:.1f}L" for m in metrics_list]),
        ("Wealth Multiple", [f"{m['final_value']/total_invested:.1f}x" for m in metrics_list]),
        ("XIRR", [f"{m['xirr']:.1f}%" if not np.isnan(m['xirr']) else "—" for m in metrics_list]),
        ("Sharpe", [f"{m['sharpe']:.2f}" for m in metrics_list]),
        ("Sortino", [f"{m['sortino']:.2f}" for m in metrics_list]),
        ("Max Drawdown", [f"{m['max_drawdown']:.1f}%" for m in metrics_list]),
        ("Max DD Duration", [f"{m['max_dd_days']} days" for m in metrics_list]),
        ("Volatility", [f"{m['volatility']:.1f}%" for m in metrics_list]),
    ]
    for name, vals in rows:
        print(f"  {name:25s}" + "".join(f" {v:>22s}" for v in vals))

    print(f"\n  Buy signals fired on {n_signals} days across {n_bought}/{n_stocks} stocks")
    print(f"  Cash drag (Your Strategy): {cash_pct:.1f}%")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    cfg = CONFIG
    print("=" * 80)
    print("  BACKTEST: Your Strategy vs SIP vs NIFTY 50")
    print("=" * 80)
    print(f"  Period:   {cfg['start']} → {cfg['end']}")
    print(f"  Budget:   ₹{cfg['initial_salary']:,}/month salary, {cfg['invest_pct']*100:.0f}% invested, {cfg['salary_growth']*100:.0f}%/yr growth")
    print(f"  Signals:  BB({cfg['bb_length']}, {cfg['bb_std']}σ, {cfg['bb_lookback']}d) + Impulse MACD({cfg['impulse_length_ma']}, {cfg['impulse_length_signal']})")
    print(f"  Slippage: {cfg['slippage_bps']} bps")
    print()

    try:
        with open("stocks.txt", "r") as f:
            watchlist = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        print("  ✗ stocks.txt not found"); return

    symbols = [s + ".NS" for s in watchlist]
    print(f"  Loading {len(symbols)} stocks from stocks.txt...")

    stock_dfs = download_batch(symbols, cfg)
    print(f"  Downloaded: {len(stock_dfs)}/{len(symbols)} stocks")

    bb_sig, imp_sig, imp_state, skipped = generate_all_signals(stock_dfs, cfg)
    sig_syms = list(bb_sig.keys())
    print(f"  Signals: {len(sig_syms)} stocks ready ({len(skipped)} skipped, insufficient data)")

    if not sig_syms:
        print("  ✗ No stocks with enough data"); return

    dates = get_all_dates(stock_dfs, sig_syms)
    monthly_inv = build_monthly_investments(dates, cfg)
    total_invested = sum(v["amount"] for v in monthly_inv.values())

    print(f"\n  Simulating strategies...")
    sip_sim, sip_cf = simulate_sip(stock_dfs, sig_syms, monthly_inv, cfg["slippage_bps"])
    timed_sim, timed_cf, buy_log = simulate_timed_hodl(stock_dfs, sig_syms, monthly_inv, bb_sig, imp_sig, cfg["slippage_bps"])
    exit_sim, exit_cf, trade_log = simulate_timed_exit(stock_dfs, sig_syms, monthly_inv, bb_sig, imp_sig, imp_state, cfg["slippage_bps"])
    nifty_sim, nifty_cf = simulate_nifty_sip(cfg)

    m_timed = compute_metrics(timed_sim["portfolio"], LABEL_TIMED, timed_cf)
    m_sip = compute_metrics(sip_sim["portfolio"], LABEL_SIP, sip_cf)
    m_exit = compute_metrics(exit_sim["portfolio"], LABEL_EXIT, exit_cf)
    m_nifty = compute_metrics(nifty_sim["portfolio"], LABEL_NIFTY, nifty_cf) if nifty_sim is not None else None

    portfolios = {LABEL_TIMED: timed_sim["portfolio"], LABEL_SIP: sip_sim["portfolio"], LABEL_EXIT: exit_sim["portfolio"]}
    nifty_series = nifty_sim["portfolio"] if nifty_sim is not None else None

    buy_dates = set(b["date"] for b in buy_log)
    stocks_bought = set(b["stock"] for b in buy_log)
    cash_total = timed_sim["portfolio"].replace(0, np.nan)
    cash_pct = (timed_sim["cash"] / cash_total * 100).fillna(100).mean()

    metrics_list = [m_timed, m_sip, m_exit]
    if m_nifty: metrics_list.append(m_nifty)

    print_summary(metrics_list, total_invested, len(sig_syms), len(buy_dates), len(stocks_bought), cash_pct)

    print(f"\n  Generating charts...")
    chart_1_equity(portfolios, nifty_series, total_invested, "1_equity_curves.png")
    chart_2_drawdowns(portfolios, nifty_series, "2_drawdowns.png")
    chart_3_cash(timed_sim, exit_sim, "3_cash_utilization.png")
    chart_4_regimes(portfolios, nifty_series, "4_regime_returns.png")
    chart_5_rolling_alpha(portfolios, "5_rolling_alpha.png")
    chart_6_buy_distribution(buy_log, len(sig_syms), "6_buy_distribution.png")
    chart_7_buy_timeline(buy_log, "7_buy_timeline.png")
    chart_8_summary_table(metrics_list, total_invested, len(sig_syms), len(buy_dates), len(stocks_bought), "8_summary_table.png")

    charts = sorted(f for f in os.listdir(OUTPUT_DIR) if f.endswith(".png"))
    print(f"\n  {len(charts)} charts saved to {OUTPUT_DIR}/:")
    for c in charts:
        print(f"    • {c}")
    print()


if __name__ == "__main__":
    main()
