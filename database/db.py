import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

def get_db_path() -> str:
    return os.getenv("SQLITE_PATH", "market.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    with open("database/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()