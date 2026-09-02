from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
import requests
import io
import time

app = Flask(__name__)

# NSE official equity master
NSE_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def get_nse_stocks():
    """
    NSE ki current equity list automatically load karta hai.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,*/*"
        }

        session = requests.Session()

        # NSE homepage visit karke session cookies lena
        session.get(
            "https://www.nseindia.com",
            headers=headers,
            timeout=10
        )

        response = session.get(
            NSE_URL,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        df = pd.read_csv(io.StringIO(response.text))

        # Sirf normal equity securities
        if "SERIES" in df.columns:
            df = df[df["SERIES"] == "EQ"]

        symbols = df["SYMBOL"].dropna().astype(str).tolist()

        # Yahoo Finance format
        stocks = [
            symbol + ".NS"
            for symbol in symbols
            if symbol.isalnum()
        ]

        return stocks

    except Exception as e:
        print("NSE list error:", e)

        # Backup universe
        return [
            "RELIANCE.NS",
            "TCS.NS",
            "INFY.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "BHARTIARTL.NS",
            "ITC.NS",
            "LT.NS",
            "AXISBANK.NS",
            "KOTAKBANK.NS",
            "SUNPHARMA.NS",
            "MARUTI.NS",
            "TATASTEEL.NS",
            "TATAMOTORS.NS",
            "NTPC.NS",
            "POWERGRID.NS",
            "ADANIENT.NS",
            "BEL.NS",
            "TRENT.NS"
        ]


def analyze_stock(symbol):

    try:

        data = yf.download(
            symbol,
            period="5d",
            interval="15m",
            progress=False,
            auto_adjust=False
        )

        if data.empty or len(data) < 50:
            return None

        close = data["Close"].squeeze()
        volume = data["Volume"].squeeze()

        price = float(close.iloc[-1])

        # -------------------------
        # EMA
        # -------------------------

        ema9 = close.ewm(
            span=9,
            adjust=False
        ).mean()

        ema21 = close.ewm(
            span=21,
            adjust=False
        ).mean()

        # -------------------------
        # RSI
        # -------------------------

        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            0.0001
        )

        rsi = 100 - (
            100 / (1 + rs)
        )

        current_rsi = float(rsi.iloc[-1])

        # -------------------------
        # Volume
        # -------------------------

        avg_volume = volume.rolling(20).mean()

        volume_ratio = float(
            volume.iloc[-1]
            /
            max(float(avg_volume.iloc[-1]), 1)
        )

        # -------------------------
        # Score
        # -------------------------

        score = 50

        if ema9.iloc[-1] > ema21.iloc[-1]:

            score += 20
            trend = "BULLISH"

        else:

            score -= 20
            trend = "BEARISH"

        # RSI

        if 55 <= current_rsi <= 70:

            score += 15

        elif 30 <= current_rsi <= 45:

            score -= 15

        # Volume

        if volume_ratio >= 1.5:

            score += 15

        elif volume_ratio < 0.7:

            score -= 5

        score = max(
            0,
            min(100, score)
        )

        # -------------------------
        # Signal
        # -------------------------

        if score >= 75:

            signal = "BUY"

        elif score <= 25:

            signal = "SELL"

        else:

            signal = "NO TRADE"

        # -------------------------
        # Risk levels
        # -------------------------

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

            "stock": symbol.replace(
                ".NS",
                ""
            ),

            "price": round(
                price,
                2
            ),

            "trend": trend,

            "rsi": round(
                current_rsi,
                2
            ),

            "volume": round(
                volume_ratio,
                2
            ),

            "score": score,

            "signal": signal,

            "stop_loss": round(
                stop_loss,
                2
            ),

            "target": round(
                target,
                2
            )
        }

    except Exception as e:

        print(
            "Analysis error:",
            symbol,
            e
        )

        return None


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route("/scan")
def scan():

    stocks = get_nse_stocks()

    results = []

    print(
        "Total NSE stocks:",
        len(stocks)
    )

    # Broad universe scan
    for i, stock in enumerate(stocks):

        print(
            "Scanning:",
            i + 1,
            "/",
            len(stocks),
            stock
        )

        result = analyze_stock(
            stock
        )

        if result:

            results.append(
                result
            )

        # Server ko overload hone se bachane ke liye
        time.sleep(0.05)

    # Highest score first
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # Sirf best 20 dashboard par
    results = results[:20]

    return jsonify({

        "total_scanned": len(stocks),

        "showing": len(results),

        "results": results

    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
