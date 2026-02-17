
# AI Market Monitor

An automated daily market monitoring pipeline that collects stock prices and company news, analyzes movements using an LLM, and generates a formatted PDF market brief.

The system runs end-to-end:

Data Collection → Filtering → Database → AI Analysis → Report → PDF

---

# Features

- Fetch daily stock price data  
- Fetch and filter company news  
- Store historical data in SQLite  
- Compute technical context (20-day range position)  
- Generate AI summaries using an LLM  
- Produce structured Markdown reports  
- Automatically export professionally formatted PDFs  

---

# Example Output

Daily report includes:

- Price changes (previous close → latest close)
- Volume
- 20-day range position
- Filtered company news
- AI-generated analysis

---

# Project Structure

market_monitor/

├── collector/           # Data collection scripts
│   ├── fetch_prices.py
│   └── fetch_news.py


├── analysis/            # AI analysis and caching
│   └── openai_summary.py


├── database/
│   ├── db.py
│   └── schema.sql


├── reports/
│   └── generate_report.py


├── tools/
│   └── export_report_pdf.py


├── repo/
│   ├── md/              # Saved markdown reports
│   └── pdf/             # Final PDF reports


├── config/
│   └── tickers.yaml


├── main.py              # Main pipeline entry
├── requirements.txt
├── .env
└── README.md

---

# How It Works

## 1. Price Collection
Daily prices are retrieved from a market data API

---

## 2. News Collection
Company news is fetched and filtered.

Filters remove:
- market roundups
- ETF news
- unrelated macro headlines

Only relevant company news is stored.

---

## 3. Technical Context Calculation

For each stock:

position = (current - 20d_low) / (20d_high - 20d_low)

This measures whether the price is near:
- the bottom of range
- the middle
- the top

---

## 4. AI Analysis

The AI receives:
- price movement
- volume
- 20-day range context
- filtered news summaries

The model generates:
- possible drivers of movement
- uncertainty when no clear catalyst exists
- a “watch next” item

Results are cached in SQLite to avoid duplicate API calls.

---

## 5. Report Generation

A Markdown report is created:

repo/md/report_YYYY-MM-DD.md

Then converted to a formatted PDF:

repo/pdf/report_YYYY-MM-DD.pdf

---

# Installation

## 1. Clone Repository

git clone <repo_url>
cd market_report

---

## 2. Install Dependencies

pip install -r requirements.txt

---

## 3. Configure Environment

Create `.env`:

ALPHAVANTAGE_API_KEY=your-key
SQLITE_PATH=market.db
FINNHUB_API_KEY=your-key
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5-mini(your-model)

---
## Caution

Only 25 Free stock info for ALPHAVANTAGE_API_KEY each day

---

# Running the Pipeline

Run full pipeline:

python main.py

Skip data fetching (use existing data):

python main.py --no-fetch

Refresh AI summaries:

python main.py --no-fetch --refresh-ai

---

# Technologies Used

- Python
- SQLite
- Requests
- ReportLab
- OpenAI API
- YAML

---

# Author

Neil Hu
