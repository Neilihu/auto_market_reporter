import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI
from database.db import get_connection

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_cached_summary(report_date: str, ticker: str, model: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT summary FROM ai_summaries
        WHERE report_date=? AND ticker=? AND model=?
    """, (report_date, ticker, model))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def save_summary(report_date: str, ticker: str, model: str, summary: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_summaries (report_date, ticker, model, summary, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(report_date, ticker, model) DO UPDATE SET
          summary=excluded.summary,
          created_at=excluded.created_at
    """, (report_date, ticker, model, summary, _now_iso()))
    conn.commit()
    conn.close()

def _format_news_items(news_items):
    """
    news_items: list[dict] with keys:
      published_at, source, headline, summary, url
    """
    if not news_items:
        return "(No recent company news content was provided.)"

    blocks = []
    for i, it in enumerate(news_items, start=1):
        published_at = (it.get("published_at") or "").strip()
        source = (it.get("source") or "").strip()
        headline = (it.get("headline") or "").strip()
        summary = (it.get("summary") or "").strip()
        url = (it.get("url") or "").strip()

        block = [
            f"[News {i}]",
            f"Time: {published_at}" if published_at else "Time: (unknown)",
            f"Source: {source}" if source else "Source: (unknown)",
            f"Headline: {headline}" if headline else "Headline: (missing)",
            f"Summary: {summary}" if summary else "Summary: (missing)",
            f"URL: {url}" if url else "URL: (missing)",
        ]
        blocks.append("\n".join(block))

    return "\n\n".join(blocks)

def build_prompt(
    ticker,
    d0, d1,
    c0, c1,
    pct,
    volume,
    range_low=None,
    range_high=None,
    range_pos=None,
    news_items=None,
    headlines=None,
):
    if news_items is None and headlines is not None:
        news_items = [{"headline": h, "summary": "", "source": "", "url": "", "published_at": ""} for h in headlines]

    news_text = _format_news_items(news_items)

    if range_low is None or range_high is None or range_pos is None:
        range_text = "20-trading-day context: (not provided)"
    else:
        range_text = (
            "20-trading-day context:\n"
            f"- Range low: {float(range_low):.2f}\n"
            f"- Range high: {float(range_high):.2f}\n"
            f"- Current position in range (0=low, 1=high): {float(range_pos):.2f}"
        )

    return f"""
You are writing a concise daily market brief. Your job is to summarize *possible* drivers of the price move using ONLY:
1) the provided price/volume data,
2) the provided news headlines + summaries.

Hard rules:
- Do NOT browse the web.
- Do NOT invent catalysts not supported by the provided news content.
- Only use news that is directly relevant to the company’s business, products, earnings, regulation, or industry conditions.
- Ignore news that is generic market commentary, macro news, or not clearly related to this specific company.
- If the provided news does not clearly explain the move, explicitly say:
  "No clear catalyst found in provided news."
- Prefer saying "No clear catalyst found" rather than speculating."

Stock: {ticker}
Move: {d0} -> {d1}
Close: {c0:.2f} -> {c1:.2f} ({pct:+.2f}%)
Volume (latest day): {int(volume):,}

{range_text}

Provided news content:
{news_text}

Write 3–6 sentences:
- Sentence 1: what happened (move + where it sits in the 20D range if available).
- Sentence 2–4: connect the move to the provided news summaries (quote/paraphrase specifics).
- Sentence 5: mention uncertainty if evidence is weak.
- Final: "Watch next: ..." (earnings/guidance/product/regulatory/etc.), but NO price prediction.
""".strip()


def summarize(
    report_date,
    ticker,
    d0, d1,
    c0, c1,
    pct,
    volume,
    range_low=None,
    range_high=None,
    range_pos=None,
    news_items=None,
    headlines=None,
):
    cached = get_cached_summary(report_date, ticker, MODEL)
    if cached:
        return cached

    prompt = build_prompt(
        ticker=ticker,
        d0=d0, d1=d1,
        c0=c0, c1=c1,
        pct=pct,
        volume=volume,
        range_low=range_low,
        range_high=range_high,
        range_pos=range_pos,
        news_items=news_items,
        headlines=headlines,
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.choices[0].message.content.strip()
    save_summary(report_date, ticker, MODEL, text)
    return text

def clear_ai_cache(report_date: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM ai_summaries WHERE report_date=?",
        (report_date,)
    )
    conn.commit()
    conn.close()