import sqlite3
from backend.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol        TEXT PRIMARY KEY,
    name          TEXT,
    sector        TEXT,
    last_ohlc_fetch   TEXT,
    last_news_fetch   TEXT
);

CREATE TABLE IF NOT EXISTS ohlc (
    symbol        TEXT NOT NULL,
    date          TEXT NOT NULL,
    open          REAL,
    high          REAL,
    low           REAL,
    close         REAL,
    volume        REAL,
    vwap          REAL,
    transactions  INTEGER,
    pct_chg       REAL DEFAULT 0,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS news_raw (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    description   TEXT,
    publisher     TEXT,
    author        TEXT,
    published_utc TEXT,
    article_url   TEXT,
    amp_url       TEXT,
    tickers_json  TEXT,
    insights_json TEXT,
    image_url     TEXT,
    simhash       TEXT,
    source_type   TEXT NOT NULL DEFAULT 'news'
);

CREATE TABLE IF NOT EXISTS news_ticker (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    PRIMARY KEY (news_id, symbol),
    FOREIGN KEY (news_id) REFERENCES news_raw(id)
);

CREATE TABLE IF NOT EXISTS layer0_results (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    reason        TEXT,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS layer1_results (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    relevance     TEXT,
    key_discussion      TEXT,
    chinese_summary     TEXT,
    sentiment           TEXT,
    discussion          TEXT,
    reason_growth       TEXT,
    reason_decrease     TEXT,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS layer2_results (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    discussion    TEXT,
    growth_reasons  TEXT,
    decrease_reasons TEXT,
    created_at    TEXT,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS news_aligned (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    published_utc TEXT,
    ret_t0        REAL,
    ret_t1        REAL,
    ret_t3        REAL,
    ret_t5        REAL,
    ret_t10       REAL,
    limit_up      INTEGER DEFAULT 0,
    limit_down    INTEGER DEFAULT 0,
    source        TEXT,
    PRIMARY KEY (news_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_news_aligned_symbol_date ON news_aligned(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_news_simhash ON news_raw(simhash);

CREATE TABLE IF NOT EXISTS batch_jobs (
    batch_id      TEXT PRIMARY KEY,
    symbol        TEXT,
    status        TEXT,
    total         INTEGER,
    completed     INTEGER DEFAULT 0,
    created_at    TEXT,
    finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS batch_request_map (
    batch_id      TEXT NOT NULL,
    custom_id     TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    article_ids   TEXT NOT NULL,
    PRIMARY KEY (batch_id, custom_id)
);

CREATE TABLE IF NOT EXISTS news_sources (
    source      TEXT PRIMARY KEY,
    last_sync   TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolios (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    name         TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    stock_code   TEXT NOT NULL,
    added_at     TEXT NOT NULL DEFAULT (datetime('now')),
    source       TEXT NOT NULL DEFAULT 'manual',
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, stock_code)
);

CREATE TABLE IF NOT EXISTS ohlc_cache (
    key_col       TEXT PRIMARY KEY,
    data_json     TEXT,
    fetched_at    TEXT
);

CREATE TABLE IF NOT EXISTS news_cache (
    key_col       TEXT PRIMARY KEY,
    data_json     TEXT,
    fetched_at    TEXT
);

CREATE TABLE IF NOT EXISTS limit_cache (
    key_col       TEXT PRIMARY KEY,
    data_json     TEXT,
    fetched_at    TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT,
    event_date  TEXT NOT NULL,
    category    TEXT NOT NULL,
    impact      TEXT,
    source      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

CREATE TABLE IF NOT EXISTS event_stock (
    event_id    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    PRIMARY KEY (event_id, symbol),
    FOREIGN KEY (event_id) REFERENCES events(id)
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_MIGRATIONS = [
    "ALTER TABLE news_raw ADD COLUMN source_type TEXT NOT NULL DEFAULT 'news'",
    "CREATE INDEX IF NOT EXISTS idx_news_raw_source_type ON news_raw(source_type)",
    "ALTER TABLE news_aligned ADD COLUMN contradiction INTEGER DEFAULT 0",
    "CREATE INDEX IF NOT EXISTS idx_news_aligned_contradiction ON news_aligned(contradiction)",
]


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    print(f"Database initialized at {settings.database_path}")


if __name__ == "__main__":
    init_db()
