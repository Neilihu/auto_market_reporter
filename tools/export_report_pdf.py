import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
# ---------------------------
# Helpers
# ---------------------------

def iso_to_short(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        # already short / unexpected format
        return s

def short_url(url: str, keep_tail: int = 10) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    # show only domain + tail, still keep full url clickable
    try:
        m = re.match(r"^(https?://)([^/]+)(/.*)?$", url)
        if not m:
            return url[:60] + ("…" if len(url) > 60 else "")
        domain = m.group(2)
        tail = url[-keep_tail:] if len(url) > keep_tail else url
        return f"{domain}…{tail}"
    except Exception:
        return url[:60] + ("…" if len(url) > 60 else "")

def esc(s: str) -> str:
    # escape for reportlab Paragraph
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def is_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")

def parse_report(md_text: str) -> Dict:
    lines = md_text.splitlines()

    report = {
        "title": "",
        "meta": "",
        "sections": []  # list of {ticker, kv, news[], ai}
    }

    current = None
    mode = None  # None / "news" / "ai"
    last_news = None

    for raw in lines:
        line = raw.rstrip("\n")

        if line.startswith("# "):
            report["title"] = line[2:].strip()
            continue

        # Treat second line "## ..." as meta header if exists
        if report["meta"] == "" and line.startswith("## "):
            report["meta"] = line[3:].strip()
            continue

        if line.startswith("### "):
            if current:
                report["sections"].append(current)
            current = {
                "ticker": line[4:].strip(),
                "kv": {},
                "news": [],
                "ai": ""
            }
            mode = None
            last_news = None
            continue

        if not current:
            continue

        # Key value lines
        if line.startswith("- Date:"):
            current["kv"]["date"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("- Close:"):
            current["kv"]["close"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("- Volume:"):
            current["kv"]["volume"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("- 20D Range:"):
            current["kv"]["range"] = line.split(":", 1)[1].strip()
            continue

        if line.startswith("- News"):
            mode = "news"
            last_news = None
            continue

        if line.startswith("- AI Summary:") or line.startswith("- Summary:"):
            mode = "ai"
            continue

        # News bullets: "  - ..."
        if mode == "news" and re.match(r"^\s{2}-\s+", line):
            txt = re.sub(r"^\s{2}-\s+", "", line).strip()
            # A new news item headline line
            last_news = {"line": txt, "summary": "", "url": ""}
            current["news"].append(last_news)
            continue

        # Sub bullets under news: "    - Summary: ..." or url
        if mode == "news" and re.match(r"^\s{4}-\s+", line) and last_news is not None:
            txt = re.sub(r"^\s{4}-\s+", "", line).strip()
            if txt.lower().startswith("summary:"):
                last_news["summary"] = txt.split(":", 1)[1].strip()
            elif is_url(txt):
                last_news["url"] = txt
            continue

        # AI summary bullet: "  - ..."
        if mode == "ai" and re.match(r"^\s{2}-\s+", line):
            txt = re.sub(r"^\s{2}-\s+", "", line).strip()
            # keep as one paragraph; if multiple bullets, append lines
            if current["ai"]:
                current["ai"] += "\n" + txt
            else:
                current["ai"] = txt
            continue

        # Sometimes AI summary may be plain lines (wrapped) - append them
        if mode == "ai" and line.strip() and not line.startswith("- "):
            # avoid accidentally eating next ticker
            current["ai"] = (current["ai"] + " " + line.strip()).strip()
            continue

    if current:
        report["sections"].append(current)

    return report


# ---------------------------
# PDF rendering
# ---------------------------

def build_styles():
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=8,
        alignment=TA_LEFT,
    )

    meta_style = ParagraphStyle(
        "MetaCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10,
    )

    ticker_style = ParagraphStyle(
        "TickerBanner",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=colors.white,
        spaceBefore=10,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=13.2,
        textColor=colors.HexColor("#111111"),
        spaceAfter=3,
    )

    small_style = ParagraphStyle(
        "SmallCustom",
        parent=body_style,
        fontSize=9.4,
        leading=12.2,
        textColor=colors.HexColor("#222222"),
    )

    news_head_style = ParagraphStyle(
        "NewsHead",
        parent=body_style,
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=4,
    )

    news_item_style = ParagraphStyle(
        "NewsItem",
        parent=small_style,
        leftIndent=10,
        spaceAfter=2,
    )

    news_summary_style = ParagraphStyle(
        "NewsSummary",
        parent=small_style,
        leftIndent=18,
        textColor=colors.HexColor("#333333"),
        spaceAfter=3,
    )

    ai_head_style = ParagraphStyle(
        "AIHead",
        parent=body_style,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=4,
    )

    ai_style = ParagraphStyle(
        "AIBoxText",
        parent=small_style,
        leftIndent=8,
        rightIndent=8,
        spaceBefore=6,
        spaceAfter=6,
    )

    return {
        "title": title_style,
        "meta": meta_style,
        "ticker": ticker_style,
        "body": body_style,
        "small": small_style,
        "news_head": news_head_style,
        "news_item": news_item_style,
        "news_summary": news_summary_style,
        "ai_head": ai_head_style,
        "ai_text": ai_style,
    }

def header_footer(canvas, doc, title):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#444444"))
    canvas.drawString(0.7 * inch, 10.7 * inch, title[:90])
    canvas.drawRightString(8.0 * inch, 0.55 * inch, f"Page {doc.page}")
    canvas.restoreState()

def kv_table(kv: Dict):
    data = []
    if kv.get("date"):
        data.append(["Date", esc(kv["date"])])
    if kv.get("close"):
        data.append(["Close", esc(kv["close"])])
    if kv.get("volume"):
        data.append(["Volume", esc(kv["volume"])])
    if kv.get("range"):
        # Fix any odd characters (your earlier pdf had ■)
        rng = kv["range"].replace("■", "")
        data.append(["20D Range", esc(rng)])

    tbl = Table(data, colWidths=[1.1 * inch, 5.7 * inch])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.6),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111111")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F6F7F9"), colors.white]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl

def ai_box(text: str, styles):
    text = (text or "").strip()
    if not text:
        text = "(No AI summary.)"

    box = Table(
        [[Paragraph(esc(text), styles["ai_text"])]],
        colWidths=[6.8 * inch]
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F4F7")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D0D5DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box

def render_report_to_flow(report: Dict):
    styles = build_styles()
    flow = []

    title = report.get("title") or "Daily Market Report"
    flow.append(Paragraph(esc(title), styles["title"]))

    if report.get("meta"):
        flow.append(Paragraph(esc(report["meta"]), styles["meta"]))

    for sec in report.get("sections", []):
        ticker = sec["ticker"]

        # Ticker banner (a table with background)
        banner = Table([[Paragraph(esc(ticker), styles["ticker"])]], colWidths=[6.8 * inch])
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
            ("BOX", (0, 0), (-1, -1), 0.0, colors.white),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        block = [banner, kv_table(sec.get("kv", {}))]

        # News block
        block.append(Spacer(1, 6))
        block.append(Paragraph("News", styles["news_head"]))

        news = sec.get("news", [])
        if not news:
            block.append(Paragraph("No recent news.", styles["small"]))
        else:
            for i, it in enumerate(news, start=1):
                head = it.get("line", "")
                # format like: "2026-02-17 16:47 | Yahoo | ..."
                # Also reduce long ISO if any
                head = head.replace("T", " ")
                # Clean potential weird squares
                head = head.replace("■", "")
                block.append(Paragraph(f"{i}. {esc(head)}", styles["news_item"]))

                summ = (it.get("summary") or "").strip()
                if summ:
                    block.append(Paragraph(f"<i>{esc(summ)}</i>", styles["news_summary"]))

                url = (it.get("url") or "").strip()
                if url:
                    show = short_url(url)
                    block.append(Paragraph(
                        f'<link href="{esc(url)}">{esc(show)}</link>',
                        styles["news_summary"]
                    ))

        block.append(Spacer(1, 8))
        block.append(Paragraph("Summary", styles["ai_head"]))
        block.append(ai_box(sec.get("ai", ""), styles))

        flow.append(KeepTogether(block))
        flow.append(Spacer(1, 10))

    return flow

def export_pdf(md_path: str, pdf_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    report = parse_report(md_text)

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.8 * inch,
        title=report.get("title") or os.path.basename(md_path),
        author="market_monitor",
    )

    flow = render_report_to_flow(report)

    title = report.get("title") or os.path.basename(md_path)
    doc.build(
        flow,
        onFirstPage=lambda c, d: header_footer(c, d, title),
        onLaterPages=lambda c, d: header_footer(c, d, title),
    )

if __name__ == "__main__":
    # Manual quick test:
    md = "repo/md/report_2026-01-13.md"
    pdf = "repo/pdf/report_2026-01-13.pdf"
    export_pdf(md, pdf)
    print(f"[OK] Exported: {pdf}")