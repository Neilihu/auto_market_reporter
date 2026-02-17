CREATE TABLE IF NOT EXISTS prices_daily (
  ticker TEXT NOT NULL,
  date   TEXT NOT NULL,          -- YYYY-MM-DD
  open   REAL,
  high   REAL,
  low    REAL,
  close  REAL,
  volume INTEGER,
  source TEXT,
  PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS news (
  ticker       TEXT NOT NULL,
  published_at TEXT NOT NULL,  -- ISO string
  headline     TEXT,
  summary      TEXT,
  url          TEXT,
  source       TEXT,
  PRIMARY KEY (ticker, published_at, url)
);

CREATE TABLE IF NOT EXISTS ai_summaries (
  report_date TEXT NOT NULL,
  ticker TEXT NOT NULL,
  model TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (report_date, ticker, model)
);