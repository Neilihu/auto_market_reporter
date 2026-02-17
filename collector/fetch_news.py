import os
import time
import yaml
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from database.db import get_connection

load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")

def _to_yyyy_mm_dd(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def fetch_company_news(ticker: str, days_back: int = 14):
    if not API_KEY:
        raise RuntimeError("FINNHUB_API_KEY missing in .env")

    now = datetime.now(timezone.utc)
    _from = now - timedelta(days=days_back)

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker,
        "from": _to_yyyy_mm_dd(_from),
        "to": _to_yyyy_mm_dd(now),
        "token": API_KEY,
    }

    r = requests.get(url, params=params, timeout=30)
    data = r.json()

    if not isinstance(data, list):
        print(f"[WARN] Finnhub {ticker}: {data}")
        return []

    return data[:5]

def is_relevant_news(ticker: str, headline: str, summary: str) -> bool:
    text = (headline + " " + (summary or "")).lower()

    blacklist = [
        "market roundup",
        "stocks mixed",
        "most active",
        "top gainers",
        "top losers",
        "stock market today",
        "dividend king",
        "best stocks",
        "watchlist",
        "sector performance",
        "etf"
    ]

    for kw in blacklist:
        if kw in text:
            return False
    if ticker.lower() not in text:
        return False

    return True

def save_news_items(ticker: str, items: list):
    conn = get_connection()
    cur = conn.cursor()

    for it in items:
        published = datetime.fromtimestamp(it.get("datetime", 0), tz=timezone.utc).isoformat()
        headline = it.get("headline")
        summary = it.get("summary")
        url = it.get("url")
        source = it.get("source")

        cur.execute("""
            INSERT INTO news (ticker, published_at, headline, summary, url, source)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, published_at, url) DO UPDATE SET
                headline=excluded.headline,
                summary=excluded.summary,
                source=excluded.source
        """, (ticker, published, headline, summary, url, source))

    conn.commit()
    conn.close()

def run(days_back: int = 14):
    with open("config/tickers.yaml", "r", encoding="utf-8") as f:
        tickers = yaml.safe_load(f)["tickers"]

    for t in tickers:
        items = fetch_company_news(t, days_back=days_back)
        filtered = [ it for it in items if is_relevant_news(t, it.get("headline",""), it.get("summary",""))]
        save_news_items(t, items)
        print(f"[OK] Saved news for {t}: {len(items)} items")
        time.sleep(1)

if __name__ == "__main__":
    run()