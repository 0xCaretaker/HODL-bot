import yfinance as yf
import requests
import re
import os
from datetime import datetime, timezone, timedelta

# Fetch MACD-based action for each stock
def fetch_action(stocks, interval):
    actions = {}
    data = yf.download(
        stocks,
        period="60d",
        interval=interval,
        auto_adjust=False,
        progress=False
    )

    for stock in stocks:
        try:
            df = data.xs(stock, level=1, axis=1).copy()

            # Convert timezone to IST
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
            else:
                df.index = df.index.tz_convert('Asia/Kolkata')

            ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
            ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()

            df['MACD'] = macd_line
            df['Signal'] = signal_line
            df['Trend_Reversal'] = ""

            df['Prev_MACD'] = df['MACD'].shift(1)
            df['Prev_Signal'] = df['Signal'].shift(1)

            bullish = (df['Prev_MACD'] < df['Prev_Signal']) & (df['MACD'] > df['Signal'])
            bearish = (df['Prev_MACD'] > df['Prev_Signal']) & (df['MACD'] < df['Signal'])

            df.loc[bullish, 'Trend_Reversal'] = "Bullish"
            df.loc[bearish, 'Trend_Reversal'] = "Bearish"

            df.drop(columns=['Prev_MACD', 'Prev_Signal'], inplace=True)

            action_list, last_trend = [], None
            for trend in df['Trend_Reversal']:
                if trend == "Bullish":
                    action_list.append("Buy")
                    last_trend = "Bullish"
                elif trend == "Bearish":
                    action_list.append("Sell")
                    last_trend = "Bearish"
                else:
                    if last_trend == "Bullish":
                        action_list.append("Hold")
                    elif last_trend == "Bearish":
                        action_list.append("Wait for Buy")
                    else:
                        action_list.append("")

            df['Action'] = action_list
            last_index = df.index[-1]
            actions[stock] = {
                "action": df['Action'].iloc[-1],
                "time": last_index,
                "price": df['Close'].iloc[-1]
            }

        except Exception as e:
            actions[stock] = {"action": f"Error: {e}", "time": None, "price": None}

    return actions


# Colorful terminal output
def colored_output(action):
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

    return {
        "Buy": f"{GREEN}{action}{RESET}",
        "Hold": f"{YELLOW}{action}{RESET}",
        "Sell": f"{RED}{action}{RESET}",
        "Wait for Buy": f"{MAGENTA}{action}{RESET}"
    }.get(action, action)


# Escape for Telegram MarkdownV2
def escape_md(text):
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\\-])', r'\\\1', str(text))

# send notifications to telegram
def send_bulk_telegram_message(all_interval_signals):
    TELEGRAM_TOKEN = "7785965061:AAEAXssnkbyj9vSVGHoCNegoUitePkZDK8U"
    TELEGRAM_CHAT_IDS = ["794061838", "6532562658"]
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'

    emoji = {
        "Buy": "🟢",
        "Sell": "🔴",
        "Hold": "🟡",
        "Wait for Buy": "🟣"
    }

    #  Calculate global max_len across all intervals
    all_stock_names = []
    for all_signals in all_interval_signals.values():
        for stock, info in all_signals.items():
            action, time, price = info["action"], info["time"], info["price"]
            if action in ["Buy", "Sell"] and time and price:
                stock_clean = stock.replace(".NS", "")
                all_stock_names.append(stock_clean)
    max_len = max((len(stock) for stock in all_stock_names), default=0)

    combined_lines = []
    now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30) 
    now_str = f"{now.day}{('th' if 11<=now.day<=13 else {1:'st',2:'nd',3:'rd'}.get(now.day%10,'th'))} {now.strftime('%B, %I:%M%p')}"
    combined_lines.append(f"*📊 Signal Alert \| [{escape_md(now_str)}]*\n")

    for interval, all_signals in all_interval_signals.items():
        entries = []
        for stock, info in all_signals.items():
            action, time, price = info["action"], info["time"], info["price"]
            if action in ["Buy", "Sell"] and time and price:
                stock_clean = stock.replace(".NS", "")
                entries.append((stock_clean, action, price))

        if not entries:
            continue

        # Add interval header
        combined_lines.append(f"⏱️ Interval: `{escape_md(interval)}`")

        # Format each stock signal line
        for stock, action, price in entries:
            padded_stock = stock.ljust(max_len)
            combined_lines.append(f"{emoji[action]} `{escape_md(padded_stock)} ₹{price:.2f}`")

        combined_lines.append("")  # spacing between intervals

    if len(combined_lines) <= 1:
        return  # no valid messages to send

    final_message = "\n".join(combined_lines)

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

# Main logic
def main():
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    print("UTC Time:", now_utc.strftime('%Y-%m-%d %H:%M:%S'))
    print("IST Time:", now_ist.strftime('%Y-%m-%d %H:%M:%S'))

    stocks = [
        "ACE", "ADANIPOWER", "AETHER", "AIIL", "AMJLAND", "ANUP", "APOLLO", "ARIHANTCAP", "ARROWGREEN", "ARVSMART",
        "BANCOINDIA", "BIRLAMONEY", "BLUEJET", "BSE", "CONFIPET", "CONSOFINVT", "DATAPATTNS", "DOLATALGO", "DVL",
        "ELECON", "EPIGRAL", "GANESHHOUC", "GENUSPOWER", "GEOJITFSL", "GOKULAGRO", "GRSE", "GRWRHITECH", "IIFLCAPS",
        "INDIAMART", "INDOTECH", "INTLCONV", "IPL", "JINDALPHOT", "JUBLFOOD", "JWL", "KIRLPNU", "KITEX", "LLOYDSENGG",
        "MANINDS", "MANORAMA", "MOTILALOFS", "NATIONALUM", "OBEROIRLTY", "PARADEEP", "POKARNA", "RKFORGE", "SARDAEN",
        "SHAKTIPUMP", "SPIC", "SUZLON", "TATAMOTORS", "TDPOWERSYS", "UTIAMC", "V2RETAIL"
    ]
    stocks = [s + ".NS" for s in stocks]
    intervals = ["1d", "1h"]

    all_interval_signals = {}

    for interval in intervals:
        print(f"\nChecking interval: {interval}")
        results = fetch_action(stocks, interval)

        for stock, info in results.items():
            action, time, price = info["action"], info["time"], info["price"]
            print(f"{stock} @ ₹{price:.2f}: {colored_output(action)} ")

        all_interval_signals[interval] = results

    send_bulk_telegram_message(all_interval_signals)


if __name__ == "__main__":
    main()
