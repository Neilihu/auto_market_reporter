import os
from datetime import datetime
from database.db import get_connection
from analysis.openai_summary import summarize

def get_latest_report_date():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM prices_daily")
    row = cur.fetchone()
    conn.close()
    return row[0]

def generate(output_dir="repo/md"):
    os.makedirs(output_dir, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ticker, date, close, volume
        FROM prices_daily
        ORDER BY ticker, date DESC
    """)
    rows = cur.fetchall()

    latest_map = {}
    for ticker, date, close, volume in rows:
        latest_map.setdefault(ticker, [])
        if len(latest_map[ticker]) < 2:
            latest_map[ticker].append(
                (str(date), float(close), int(volume) if volume is not None else 0)
            )

    all_latest_dates = [items[0][0] for items in latest_map.values() if items]
    report_date = max(all_latest_dates) if all_latest_dates else datetime.now().strftime("%Y-%m-%d")

    output_path = os.path.join(output_dir, f"report_{report_date}.md")

    lines = []
    lines.append(f"# Daily Market Report ({report_date})\n")

    for ticker in sorted(latest_map.keys()):
        items = latest_map[ticker]
        d1, c1, v1 = items[0]

        lines.append(f"### {ticker}")

        if len(items) >= 2:
            d0, c0, v0 = items[1]
            pct = (c1 - c0) / c0 * 100 if c0 else 0.0
            lines.append(f"- Date: {d0} → {d1}")
            lines.append(f"- Close: {c0:.2f} → {c1:.2f} ({pct:+.2f}%)")
            lines.append(f"- Volume: {v1:,}")
        else:
            d0, c0, pct = d1, c1, None
            lines.append(f"- Latest: {d1} | Close: {c1:.2f} | Vol: {v1:,}")

        cur.execute("""
            SELECT published_at, headline, summary, source, url
            FROM news
            WHERE ticker=?
            ORDER BY published_at DESC
            LIMIT 3
        """, (ticker,))
        news_rows = cur.fetchall()

        lines.append("- News (headline + summary):")
        news_items = []

        if not news_rows:
            lines.append("  - (no recent news)")
        else:
            for published_at, headline, summary, source, url in news_rows:
                published_at = str(published_at or "")
                if published_at:
                    try:
                        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        published_at = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        # keep original string if parsing fails
                        pass

                headline = (headline or "").strip()
                summary = (summary or "").strip()
                source = (source or "").strip()
                url = (url or "").strip()

                lines.append(f"  - {published_at} | {source} | {headline}")
                if summary:
                    lines.append(f"    - Summary: {summary}")
                if url:
                    lines.append(f"    - {url}")

                news_items.append({
                    "published_at": published_at,
                    "source": source,
                    "headline": headline,
                    "summary": summary,
                    "url": url
                })

        cur.execute("""
            SELECT close
            FROM prices_daily
            WHERE ticker=?
            ORDER BY date DESC
            LIMIT 20
        """, (ticker,))
        close_rows = cur.fetchall()
        closes_20 = [float(r[0]) for r in close_rows if r and r[0] is not None]

        if closes_20:
            high_20 = max(closes_20)
            low_20 = min(closes_20)
            range_pos = (c1 - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5
        else:
            low_20 = high_20 = c1
            range_pos = 0.5

        lines.append(f"- 20D Range: low {low_20:.2f}, high {high_20:.2f}, position {range_pos:.2f}")

        lines.append("- Summary:")
        if pct is None:
            lines.append("  - (need at least 2 trading days of price data)")
        else:
            try:
                ai_summary = summarize(
                    report_date=report_date,
                    ticker=ticker,
                    d0=d0,
                    d1=d1,
                    c0=c0,
                    c1=c1,
                    pct=pct,
                    volume=v1,
                    range_low=low_20,
                    range_high=high_20,
                    range_pos=range_pos,
                    news_items=news_items,
                )
                lines.append(f"  - {ai_summary}")
            except Exception as e:
                lines.append(f"  - (Error: {str(e)})")

        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    cur.close()
    conn.close()

    print(f"[OK] Wrote {output_path}")
    return output_path, report_date

if __name__ == "__main__":
    generate()