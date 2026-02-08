import requests
import re
from datetime import datetime, timezone, timedelta
import yfinance as yf

from macd_signals import fetch_both_signals, colored_output


# =========================
# Escape for Telegram MarkdownV2
# =========================
def escape_md(text):
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\\-])', r'\\\1', str(text))


# =========================
# Index movement
# =========================
def get_index_moves():
    index_symbols = {
        "NIFTY 50": "^NSEI",
        "NIFTY Midcap 100": "NIFTY_MIDCAP_100.NS"
    }

    index_moves = {}

    try:
        history = yf.download(
            list(index_symbols.values()),
            period="10y",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        latest = yf.download(
            list(index_symbols.values()),
            period="1d",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        for name, symbol in index_symbols.items():
            hist_close = history['Close'][symbol].dropna()
            ath = hist_close.max()

            latest_open = latest['Open'][symbol][0]
            latest_close = latest['Close'][symbol][0]

            pct_move = ((latest_close - latest_open) / latest_open) * 100
            from_ath_pct = ((latest_close - ath) / ath) * 100

            index_moves[name] = {
                "pct_move": round(pct_move, 2),
                "from_ath": round(from_ath_pct, 2),
            }

    except Exception as e:
        print(f"Error fetching index data: {e}")

    return index_moves


# =========================
# Telegram sender
# =========================
def send_bulk_telegram_message(all_interval_signals, index_moves):
    TELEGRAM_TOKEN = "7785965061:AAEAXssnkbyj9vSVGHoCNegoUitePkZDK8U"
    TELEGRAM_CHAT_IDS = ["794061838", "6532562658"]
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'

    emoji = {
        "Buy": "🟢",
        "Sell": "🔴",
        "Hold": "🟡",
        "Wait for Buy": "🟣"
    }

    all_stock_names = []
    for all_signals in all_interval_signals.values():
        for stock, info in all_signals.items():
            action, time, price = info["action"], info["time"], info["price"]
            if action and time and price:
                stock_clean = stock.replace(".NS", "").replace(".BO", "")
                all_stock_names.append(stock_clean)

    max_len = max((len(stock) for stock in all_stock_names), default=0)

    combined_lines = []
    now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = now.strftime('%d %B, %I:%M%p')
    combined_lines.append(f"*📊 Signal Alert \\| [{escape_md(now_str)}]*")

    # Index summary
    if index_moves:
        for name, info in index_moves.items():
            pct = info['pct_move']
            ath_diff = info['from_ath']
            arrow = "🔺" if pct > 0 else "🔻"
            combined_lines.append(
                f"{arrow} {escape_md(name)}: `{pct:+.2f}%` "
                f"_\\(from ATH: `{ath_diff:+.2f}%`\\)_"
            )
        combined_lines.append("")

    # Signals
    for interval, all_signals in all_interval_signals.items():
        entries = []
        total_stocks = 0
        wait_for_buy_count = 0
        hold_count = 0

        for stock, info in all_signals.items():
            action, time, price = info["action"], info["time"], info["price"]

            if action and time and price:
                total_stocks += 1
                if action == "Wait for Buy":
                    wait_for_buy_count += 1
                elif action == "Hold":
                    hold_count += 1

            if action in ["Buy", "Sell"] and time and price:
                stock_clean = stock.replace(".NS", "").replace(".BO", "")
                entries.append((stock_clean, action, price))

        if not entries and total_stocks == 0:
            continue

        # Section header
        if "Impulse" in interval:
            combined_lines.append("\n🟠 *IMPULSE MACD \\(LazyBear\\):*")
        else:
            combined_lines.append("\n🔵 *STANDARD MACD:*")

        combined_lines.append(f"⏱️ `{escape_md(interval)}`")

        for stock, action, price in entries:
            padded_stock = stock.ljust(max_len)
            combined_lines.append(
                f"{emoji[action]} `{escape_md(padded_stock)} ₹{price:.2f}`"
            )

        if total_stocks > 0:
            wait_pct = (wait_for_buy_count / total_stocks) * 100
            hold_pct = (hold_count / total_stocks) * 100

            summary = (
                f"\n📈 *Summary:*  \n"
                f"🟣 Wait for Buy: "
                f"`{escape_md(f'{wait_for_buy_count}/{total_stocks}')} ({wait_pct:.1f}%)`\n"
                f"🟡 Hold: "
                f"`{escape_md(f'{hold_count}/{total_stocks}')} ({hold_pct:.1f}%)`\n"
            )
            combined_lines.append(summary)

        combined_lines.append("")

    if len(combined_lines) <= 1:
        return

    final_message = "\n".join(combined_lines)

    print("\n" + "=" * 60)
    print("TELEGRAM MESSAGE:")
    print("=" * 60)
    print(final_message)
    print("=" * 60 + "\n")

    for chat_id in TELEGRAM_CHAT_IDS:
        data = {
            'chat_id': chat_id,
            'text': final_message,
            'parse_mode': 'MarkdownV2'
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Telegram Error: {e}")


# =========================
# Main logic
# =========================
def main():
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)

    print("UTC Time:", now_utc.strftime('%Y-%m-%d %H:%M:%S'))
    print("IST Time:", now_ist.strftime('%Y-%m-%d %H:%M:%S'))

    try:
        with open("stocks.txt", "r") as f:
            stocks = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: stocks.txt file not found.")
        return

    stocks = [s + ".NS" for s in stocks]
    intervals = ["1d"]

    index_moves = get_index_moves()
    print("\n📈 Index Moves:")
    for name, info in index_moves.items():
        pct = info['pct_move']
        ath_diff = info['from_ath']
        arrow = "🔺" if pct > 0 else "🔻"
        print(f"{arrow} {name}: {pct:+.2f}%  (from ATH: {ath_diff:+.2f}%)")

    all_interval_signals = {}

    for interval in intervals:
        print(f"\nChecking interval: {interval}")

        results_macd, results_impulse = fetch_both_signals(stocks, interval)

        print("\n" + "=" * 60)
        print("STANDARD MACD")
        print("=" * 60)
        for stock, info in results_macd.items():
            print(f"{stock} @ ₹{info['price']:.2f}: {colored_output(info['action'])}")

        print("\n" + "=" * 60)
        print("IMPULSE MACD (LazyBear)")
        print("=" * 60)
        for stock, info in results_impulse.items():
            print(f"{stock} @ ₹{info['price']:.2f}: {colored_output(info['action'])}")


        all_interval_signals[interval] = results_macd
        all_interval_signals[f"{interval} Impulse MACD"] = results_impulse


    send_bulk_telegram_message(all_interval_signals, index_moves)


if __name__ == "__main__":
    main()
