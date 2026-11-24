"""通讯录：一张卡一条记录，同一个人多张卡合并成一条。

cards 表存每次识别（含原文行），contacts 表存合并后的结果。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from . import contacts

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    mobile TEXT NOT NULL DEFAULT '',
    tel TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_mobile ON contacts(mobile) WHERE mobile<>'';
CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_email ON contacts(email) WHERE email<>'';
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    image TEXT NOT NULL DEFAULT '',
    lines TEXT NOT NULL DEFAULT '[]',
    fields TEXT NOT NULL DEFAULT '{}',
    confidence TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    problems TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str = "data/shika.db") -> sqlite3.Connection:
    import os

    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def find_same(conn, card: dict) -> dict | None:
    """按手机、邮箱、公司+姓名三种键找人，命中就返回已有记录。"""
    if card.get("mobile"):
        row = conn.execute("SELECT * FROM contacts WHERE mobile=?", (card["mobile"],)).fetchone()
        if row:
            return dict(row)
    if card.get("email"):
        row = conn.execute("SELECT * FROM contacts WHERE email=?", (card["email"],)).fetchone()
        if row:
            return dict(row)
    if card.get("name"):
        row = conn.execute(
            "SELECT * FROM contacts WHERE name=? AND company=?",
            (card["name"], card.get("company") or ""),
        ).fetchone()
        if row:
            return dict(row)
    return None


def save_card(conn, card: dict, image: str = "", lines: list[str] | None = None,
              confidence: str = "", note: str = "", problems: list[str] | None = None) -> dict:
    """一条识别结果进库：能找到同一个人就合并，否则新建。返回最终记录。"""
    with _LOCK:
        old = find_same(conn, card)
        if old:
            merged = contacts.merge(old, card)
            conn.execute(
                "UPDATE contacts SET name=?, company=?, title=?, mobile=?, tel=?, email=?, "
                "address=?, note=?, updated_at=? WHERE id=?",
                (merged["name"], merged["company"], merged["title"], merged["mobile"],
                 merged["tel"], merged["email"], merged["address"], merged["note"],
                 now(), old["id"]),
            )
            cid, created = old["id"], False
        else:
            cur = conn.execute(
                "INSERT INTO contacts(name, company, title, mobile, tel, email, address, note, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (card.get("name") or "", card.get("company") or "", card.get("title") or "",
                 card.get("mobile") or "", card.get("tel") or "", card.get("email") or "",
                 card.get("address") or "", card.get("note") or "", now(), now()),
            )
            cid, created = cur.lastrowid, True

        conn.execute(
            "INSERT INTO cards(contact_id, image, lines, fields, confidence, note, problems, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (cid, image, json.dumps(lines or [], ensure_ascii=False),
             json.dumps(card, ensure_ascii=False), confidence, note,
             json.dumps(problems or [], ensure_ascii=False), now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
        out = dict(row)
        out["created"] = created
        return out


def list_contacts(conn, keyword: str = "") -> list[dict]:
    if keyword:
        like = f"%{keyword}%"
        rows = conn.execute(
            "SELECT * FROM contacts WHERE name LIKE ? OR company LIKE ? OR mobile LIKE ? "
            "OR email LIKE ? ORDER BY id", (like, like, like, like)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM contacts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_contact(conn, cid: int) -> dict | None:
    row = conn.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
    return dict(row) if row else None


def cards_of(conn, cid: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM cards WHERE contact_id=? ORDER BY id", (cid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["lines"] = json.loads(d["lines"] or "[]")
        d["fields"] = json.loads(d["fields"] or "{}")
        d["problems"] = json.loads(d["problems"] or "[]")
        out.append(d)
    return out


def delete_contact(conn, cid: int) -> None:
    with _LOCK:
        conn.execute("DELETE FROM cards WHERE contact_id=?", (cid,))
        conn.execute("DELETE FROM contacts WHERE id=?", (cid,))
        conn.commit()


def stats(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) n FROM contacts").fetchone()["n"]
    cards = conn.execute("SELECT COUNT(*) n FROM cards").fetchone()["n"]
    with_mobile = conn.execute(
        "SELECT COUNT(*) n FROM contacts WHERE mobile<>'' OR tel<>''").fetchone()["n"]
    with_email = conn.execute("SELECT COUNT(*) n FROM contacts WHERE email<>''").fetchone()["n"]
    no_contact = conn.execute(
        "SELECT COUNT(*) n FROM contacts WHERE mobile='' AND tel='' AND email=''").fetchone()["n"]
    companies = conn.execute(
        "SELECT COUNT(DISTINCT company) n FROM contacts WHERE company<>''").fetchone()["n"]
    return {"contacts": total, "cards": cards, "with_phone": with_mobile,
            "with_email": with_email, "no_contact": no_contact, "companies": companies}
