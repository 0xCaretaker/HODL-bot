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

# Escape for Telegram MarkdownV2
def escape_md(text):
    return re.sub(r'([_*\[\]()~`>#+=|{}.!\\-])', r'\\\1', str(text))

# Send Telegram message
def send_telegram_message(stock, action, interval, time, price):
    TELEGRAM_TOKEN = "7785965061:AAEAXssnkbyj9vSVGHoCNegoUitePkZDK8U"
    TELEGRAM_CHAT_IDS = ["794061838", "6532562658"]  # List of chat IDs

    # TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    # TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'

    emoji = {
        "Buy": "🟢",
        "Sell": "🔴",
        "Hold": "🟡",
        "Wait for Buy": "🟣"
    }.get(action, "ℹ️")

    # Remove ".NS" if present
    stock_clean = stock.replace(".NS", "")

    msg = (
        f"{emoji} *{escape_md(stock_clean)}* gave a *{escape_md(action)}* signal\n"
        f"⏱️ Interval: `{escape_md(interval)}`\n"
        f"🕒 Time: `{escape_md(time.strftime('%Y-%m-%d %H:%M'))}`\n"
        f"💰 Close Price: ₹`{escape_md(f'{price:.2f}')}`"
    )
    for chat_id in TELEGRAM_CHAT_IDS:
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': msg,
            'parse_mode': 'MarkdownV2'
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Telegram Error: {e}")


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

# Main logic
def main():
    # Print current time in UTC and IST
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

    for interval in ["1d", "1h"]:
        print(f"\nChecking interval: {interval}")
        results = fetch_action(stocks, interval)

        for stock, info in results.items():
            action, time, price = info["action"], info["time"], info["price"]
            print(f"{stock} @ ₹{price:.2f}: {colored_output(action)} ")

            if action in ["Buy", "Sell"] and time and price:
                send_telegram_message(stock, action, interval, time, price)

if __name__ == "__main__":
    main()
