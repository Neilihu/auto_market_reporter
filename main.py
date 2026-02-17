import argparse
import os
from database.db import init_db
from collector.fetch_prices import run as fetch_prices
from collector.fetch_news import run as fetch_news
from reports.generate_report import generate
from tools.export_report_pdf import export_pdf
from analysis.openai_summary import clear_ai_cache

def ensure_dirs():
    os.makedirs("repo/md", exist_ok=True)
    os.makedirs("repo/pdf", exist_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true", help="Skip fetching prices/news")
    parser.add_argument("--refresh-ai", action="store_true", help="Clear AI cache for latest report date")
    args = parser.parse_args()

    ensure_dirs()
    init_db()

    if not args.no_fetch:
        fetch_prices()
        fetch_news()

    md_path, report_date = generate(output_dir="repo/md")

    if args.refresh_ai:
        clear_ai_cache(report_date)
        print(f"[OK] Cleared AI cache for {report_date}")
        md_path, report_date = generate(output_dir="repo/md")

    pdf_path = os.path.join("repo", "pdf", f"report_{report_date}.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    export_pdf(md_path, pdf_path)
    print(f"[OK] Exported PDF: {pdf_path}")

if __name__ == "__main__":
    main()