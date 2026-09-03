from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
import requests
import io
import time

app = Flask(__name__)

# Liquid NSE universe
STOCKS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS",
    "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS",
    "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "HINDUNILVR.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "BEL.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS",
    "ONGC.NS", "IOC.NS", "BPCL.NS", "HCLTECH.NS",
    "WIPRO.NS", "TECHM.NS", "TRENT.NS", "M&M.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS",
    "HDFCLIFE.NS", "SBILIFE.NS", "DRREDDY.NS",
    "CIPLA.NS", "DIVISLAB.NS", "EICHERMOT.NS",
    "HEROMOTOCO.NS", "TVSMOTOR.NS", "TITAN.NS",
    "ASIANPAINT.NS", "ULTRACEMCO.NS", "GRASIM.NS",
    "JSWSTEEL.NS", "VEDL.NS", "ZOMATO.NS", "HAL.NS"
]


def analyze_stock(symbol):
    try:
        data = yf.download(
            symbol,
            period="5d",
            interval="15m",
            progress=False,
            auto_adjust=False,
            threads=False
        )

        if data is None or data.empty:
            return None

        # Handle Yahoo multi-index columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        required = ["Close", "Volume"]

        if not all(x in data.columns for x in required):
            return None

        close = pd.to_numeric(
            data["Close"],
            errors="coerce"
        ).dropna()

        volume = pd.to_numeric(
            data["Volume"],
            errors="coerce"
        ).fillna(0)

        if len(close) < 30:
            return None

        price = float(close.iloc[-1])

        # EMA
        ema9 = close.ewm(
            span=9,
            adjust=False
        ).mean()

        ema21 = close.ewm(
            span=21,
            adjust=False
        ).mean()

        # RSI
        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss.replace(0, 0.0001)

        rsi = 100 - (100 / (1 + rs))

        current_rsi = float(rsi.iloc[-1])

        if pd.isna(current_rsi):
            return None

        # Volume ratio
        avg_volume = volume.rolling(20).mean()

        current_volume = float(volume.iloc[-1])
        normal_volume = float(avg_volume.iloc[-1])

        if normal_volume > 0:
            volume_ratio = current_volume / normal_volume
        else:
            volume_ratio = 1

        # Score
        score = 50

        if ema9.iloc[-1] > ema21.iloc[-1]:
            trend = "BULLISH"
            score += 20
        else:
            trend = "BEARISH"
            score -= 20

        if 55 <= current_rsi <= 70:
            score += 15
        elif 30 <= current_rsi <= 45:
            score -= 15

        if volume_ratio >= 1.5:
            score += 15
        elif volume_ratio < 0.7:
            score -= 5

        score = max(0, min(100, int(score)))

        if score >= 75:
            signal = "BUY"
        elif score <= 25:
            signal = "SELL"
        else:
            signal = "NO TRADE"

        # Risk levels
        if signal == "BUY":
            stop_loss = price * 0.99
            target = price * 1.02
        elif signal == "SELL":
            stop_loss = price * 1.01
            target = price * 0.98
        else:
            stop_loss = price
            target = price

        return {
            "stock": symbol.replace(".NS", ""),
            "price": round(price, 2),
            "trend": trend,
            "rsi": round(current_rsi, 2),
            "volume": round(volume_ratio, 2),
            "score": score,
            "signal": signal,
            "stop_loss": round(stop_loss, 2),
            "target": round(target, 2)
        }

    except Exception as e:
        print(f"{symbol} ERROR: {e}")
        return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "scanner": "ready"
    })


@app.route("/scan")
def scan():
    results = []
    failed = 0

    print("Starting market scan...")

    for symbol in STOCKS:
        result = analyze_stock(symbol)

        if result:
            results.append(result)
        else:
            failed += 1

        # Yahoo rate-limit se bachne ke liye
        time.sleep(0.15)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return jsonify({
        "status": "ok",
        "total_scanned": len(STOCKS),
        "successful": len(results),
        "failed": failed,
        "showing": min(len(results), 20),
        "results": results[:20]
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
