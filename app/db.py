"""游伴 AI · SQLite 数据访问层。

设计原则：
- 使用 sqlite3 标准库，零外部依赖。
- 每次请求开一个短连接（check_same_thread=False + 线程局部），避免并发问题。
- 统一返回 dict，方便直接序列化为 JSON。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Iterable, Sequence

from .config import DB_FILE, SCHEMA_FILE

_local = threading.local()


# ---------------------------------------------------------------- 连接
def get_conn() -> sqlite3.Connection:
    """获取当前线程的连接（懒创建）。"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        _local.conn = conn
    return conn


def close_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


# ---------------------------------------------------------------- 基础查询
def query(sql: str, params: Sequence[Any] = ()) -> list[dict]:
    cur = get_conn().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def query_one(sql: str, params: Sequence[Any] = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def scalar(sql: str, params: Sequence[Any] = (), default: Any = 0) -> Any:
    row = query_one(sql, params)
    if not row:
        return default
    val = next(iter(row.values()))
    return default if val is None else val


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """执行写操作，返回 lastrowid（INSERT）或受影响行数（UPDATE/DELETE）。"""
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    rid = cur.lastrowid
    n = cur.rowcount
    cur.close()
    return rid if rid else n


def execute_many(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()


def insert(table: str, data: dict) -> int:
    cols = ", ".join(data.keys())
    marks = ", ".join("?" for _ in data)
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(data.values()))


def update(table: str, data: dict, where: str, params: Sequence[Any] = ()) -> int:
    sets = ", ".join(f"{k} = ?" for k in data)
    return execute(f"UPDATE {table} SET {sets} WHERE {where}", list(data.values()) + list(params))


def update_by_id(table: str, row_id: int, data: dict) -> int:
    if not data:
        return 0
    return update(table, data, "id = ?", (row_id,))


def json_loads(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------- 初始化
def drop_all_tables() -> None:
    """删除全部业务表（保留表结构文件为唯一来源）。"""
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys = OFF")
    names = [r["name"] for r in query(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'")]
    for name in names:
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def init_db(force: bool = False) -> None:
    """建表。force=True 时清空全部业务表（用于重新播种）。

    注意：不能直接删除 .db 文件——服务运行时 WAL 文件被占用，
    删除会失败并导致「表已存在但数据未清空」。因此统一用 DROP TABLE。
    """
    if force:
        drop_all_tables()
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = get_conn()
    conn.executescript(sql)
    conn.commit()


def table_count(table: str) -> int:
    return int(scalar(f"SELECT COUNT(*) FROM {table}", default=0))


def is_seeded() -> bool:
    try:
        return table_count("parks") > 0
    except sqlite3.OperationalError:
        return False


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_label() -> str:
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    d = datetime.now()
    return f"{d:%Y-%m-%d} {weekday[d.weekday()]}"
