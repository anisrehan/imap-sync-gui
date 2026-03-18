"""
SQLite database layer.
Stores server profiles and email account pairs.
Passwords are encrypted via app.crypto before being written to disk.
"""
import sqlite3
import csv
from pathlib import Path
from typing import List, Dict, Optional

from app.crypto import encrypt, decrypt

DB_DIR = Path.home() / ".config" / "imap-sync-gui"
DB_PATH = DB_DIR / "data.db"


def _connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                host        TEXT    NOT NULL,
                port        INTEGER NOT NULL DEFAULT 993,
                use_ssl     INTEGER NOT NULL DEFAULT 1,
                username    TEXT    NOT NULL DEFAULT '',
                password    TEXT    NOT NULL DEFAULT '',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                src_server_id   INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                dst_server_id   INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                src_email       TEXT    NOT NULL,
                src_password    TEXT    NOT NULL,
                dst_email       TEXT    NOT NULL,
                dst_password    TEXT    NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Server CRUD
# ---------------------------------------------------------------------------

def get_servers() -> List[Dict]:
    with _connection() as conn:
        rows = conn.execute("SELECT * FROM servers ORDER BY name").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["password"] = decrypt(d["password"])
        result.append(d)
    return result


def get_server(server_id: int) -> Optional[Dict]:
    with _connection() as conn:
        row = conn.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if row:
        d = dict(row)
        d["password"] = decrypt(d["password"])
        return d
    return None


def add_server(name: str, host: str, port: int, use_ssl: bool,
               username: str, password: str) -> int:
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO servers (name, host, port, use_ssl, username, password) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, host, int(port), 1 if use_ssl else 0, username, encrypt(password)),
        )
        conn.commit()
        return cur.lastrowid


def update_server(server_id: int, name: str, host: str, port: int, use_ssl: bool,
                  username: str, password: str) -> None:
    with _connection() as conn:
        conn.execute(
            "UPDATE servers SET name=?, host=?, port=?, use_ssl=?, username=?, password=? "
            "WHERE id=?",
            (name, host, int(port), 1 if use_ssl else 0, username, encrypt(password), server_id),
        )
        conn.commit()


def delete_server(server_id: int) -> None:
    with _connection() as conn:
        conn.execute("DELETE FROM servers WHERE id=?", (server_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------

def get_accounts() -> List[Dict]:
    with _connection() as conn:
        rows = conn.execute("""
            SELECT a.*,
                   s1.name AS src_server_name, s1.host AS src_host,
                   s1.port AS src_port, s1.use_ssl AS src_ssl,
                   s2.name AS dst_server_name, s2.host AS dst_host,
                   s2.port AS dst_port, s2.use_ssl AS dst_ssl
            FROM   accounts a
            JOIN   servers s1 ON a.src_server_id = s1.id
            JOIN   servers s2 ON a.dst_server_id = s2.id
            ORDER  BY a.src_email
        """).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["src_password"] = decrypt(d["src_password"])
        d["dst_password"] = decrypt(d["dst_password"])
        result.append(d)
    return result


def get_account(account_id: int) -> Optional[Dict]:
    with _connection() as conn:
        row = conn.execute("""
            SELECT a.*,
                   s1.name AS src_server_name, s1.host AS src_host,
                   s1.port AS src_port, s1.use_ssl AS src_ssl,
                   s2.name AS dst_server_name, s2.host AS dst_host,
                   s2.port AS dst_port, s2.use_ssl AS dst_ssl
            FROM   accounts a
            JOIN   servers s1 ON a.src_server_id = s1.id
            JOIN   servers s2 ON a.dst_server_id = s2.id
            WHERE  a.id=?
        """, (account_id,)).fetchone()
    if row:
        d = dict(row)
        d["src_password"] = decrypt(d["src_password"])
        d["dst_password"] = decrypt(d["dst_password"])
        return d
    return None


def add_account(src_server_id: int, dst_server_id: int,
                src_email: str, src_password: str,
                dst_email: str, dst_password: str) -> int:
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO accounts "
            "(src_server_id, dst_server_id, src_email, src_password, dst_email, dst_password) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (src_server_id, dst_server_id,
             src_email, encrypt(src_password),
             dst_email, encrypt(dst_password)),
        )
        conn.commit()
        return cur.lastrowid


def update_account(account_id: int, src_server_id: int, dst_server_id: int,
                   src_email: str, src_password: str,
                   dst_email: str, dst_password: str) -> None:
    with _connection() as conn:
        conn.execute(
            "UPDATE accounts SET src_server_id=?, dst_server_id=?, "
            "src_email=?, src_password=?, dst_email=?, dst_password=? "
            "WHERE id=?",
            (src_server_id, dst_server_id,
             src_email, encrypt(src_password),
             dst_email, encrypt(dst_password),
             account_id),
        )
        conn.commit()


def delete_account(account_id: int) -> None:
    with _connection() as conn:
        conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        conn.commit()


def import_accounts_csv(filepath: str, src_server_id: int, dst_server_id: int) -> int:
    """
    Bulk-import accounts from a CSV file.
    Expected columns (no header required, but supported):
        src_email, src_password, dst_email, dst_password
    Returns the number of rows imported.
    """
    count = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            # Skip header-like rows
            if not row or row[0].strip().lower() in ("src_email", "source_email", "email"):
                continue
            if len(row) < 4:
                continue
            se, sp, de, dp = (c.strip() for c in row[:4])
            if se and de:
                add_account(src_server_id, dst_server_id, se, sp, de, dp)
                count += 1
    return count
