import os
import time
import requests
import yaml
from dotenv import load_dotenv
from database.db import get_connection

load_dotenv()
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

def _call_alpha_vantage(ticker: str, max_retries: int = 3):
    url = "https://www.alphavantage.co/query"
    params = {"function": "TIME_SERIES_DAILY", "symbol": ticker, "apikey": API_KEY}

    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=30)
        data = r.json()

        if "Time Series (Daily)" in data:
            return data

        info = data.get("Information") or data.get("Note")
        if info:
            print(f"[WARN] {ticker}: {info}")

            if "per day" in info or "daily" in info:
                print("[STOP] Daily API quota exhausted. Stopping further requests.")
                return None

            wait = 60 * (attempt + 1)
            print(f"[RATE_LIMIT] sleeping {wait}s then retry")
            time.sleep(wait)
            continue

        print(f"[WARN] unexpected response keys={list(data.keys())}")
        return None

    return None

def fetch_last_n_days(ticker: str, n: int = 5):
    data = _call_alpha_vantage(ticker)
    ts = data.get("Time Series (Daily)", {})
    if not ts:
        print(f"[WARN] No time series for {ticker}. Response keys: {list(data.keys())}")
        return []

    dates = sorted(ts.keys(), reverse=True)[:n]
    records = []
    for d in dates:
        x = ts[d]
        records.append({
            "ticker": ticker,
            "date": d,
            "open": float(x["1. open"]),
            "high": float(x["2. high"]),
            "low": float(x["3. low"]),
            "close": float(x["4. close"]),
            "volume": int(x["5. volume"]),
            "source": "alphavantage",
        })
    return records

def save_to_db(record: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO prices_daily (ticker, date, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            source=excluded.source
    """, (
        record["ticker"], record["date"], record["open"], record["high"],
        record["low"], record["close"], record["volume"], record["source"]
    ))

    conn.commit()
    conn.close()

def run(n_days: int = 5):
    with open("config/tickers.yaml", "r", encoding="utf-8") as f:
        tickers = yaml.safe_load(f)["tickers"]

    for i, t in enumerate(tickers, 1):
        records = fetch_last_n_days(t, n=n_days)
        if records:
            for rec in records:
                save_to_db(rec)
            print(f"[OK] Saved {t}: {len(records)} days (latest {records[0]['date']})")
        elif records is None:
            print("[STOP] Stopping job due to API quota.")
            break
        time.sleep(15)

if __name__ == "__main__":
    run()