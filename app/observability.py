"""游伴 AI · 可观测性。

提供三样东西：
1. **结构化请求日志**：`[游伴] GET /api/c/home 200 12.4ms`，一行一条，便于 grep。
2. **进程内请求指标**：按路径聚合调用次数、平均耗时、最慢请求、错误数。
3. **业务计数**：从数据库实时统计关键业务动作（激活 / 触发 / 任务通过 / AI 生成）。

指标保存在进程内存中，不依赖外部服务；重启即清零，符合本地工具的定位。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from . import db
from .config import VERSION

_LOCK = threading.Lock()

# 路径聚合：method+path -> {"count", "total_ms", "max_ms", "errors", "slow"}
_stats: dict[str, dict] = defaultdict(
    lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "errors": 0, "slow": 0})
_recent: list[dict] = []
_recent_limit = 50

SLOW_MS = 300.0          # 超过该耗时计入「慢请求」
STARTED_AT = time.time()

# 不记录日志的静态资源前缀（避免刷屏）
QUIET_PREFIXES = ("/c/", "/admin/", "/favicon")


def should_log(path: str) -> bool:
    if path in ("/",):
        return False
    return not path.startswith(QUIET_PREFIXES)


def record(method: str, path: str, status: int, elapsed_ms: float) -> None:
    """记录一次请求。path 已由调用方归一化（动态段替换为 {}）。"""
    key = f"{method} {path}"
    slow = elapsed_ms >= SLOW_MS
    with _LOCK:
        s = _stats[key]
        s["count"] += 1
        s["total_ms"] += elapsed_ms
        s["max_ms"] = max(s["max_ms"], elapsed_ms)
        if status >= 400:
            s["errors"] += 1
        if slow:
            s["slow"] += 1
        _recent.append({"method": method, "path": path, "status": status,
                        "ms": round(elapsed_ms, 1), "at": time.strftime("%H:%M:%S")})
        if len(_recent) > _recent_limit:
            del _recent[0:len(_recent) - _recent_limit]


def log_line(method: str, path: str, status: int, elapsed_ms: float) -> None:
    print(f"[游伴] {method:<7} {path:<44} {status:<4} {elapsed_ms:7.1f}ms", flush=True)


def snapshot() -> dict:
    """进程内请求指标快照。"""
    with _LOCK:
        items = []
        for key, s in _stats.items():
            method, _, path = key.partition(" ")
            items.append({
                "method": method, "path": path, "count": s["count"],
                "avg_ms": round(s["total_ms"] / s["count"], 1) if s["count"] else 0.0,
                "max_ms": round(s["max_ms"], 1),
                "errors": s["errors"], "slow": s["slow"],
            })
        recent = list(_recent)
        total = sum(s["count"] for s in _stats.values())
        errors = sum(s["errors"] for s in _stats.values())
        total_ms = sum(s["total_ms"] for s in _stats.values())

    items.sort(key=lambda x: (-x["count"], x["path"]))
    slowest = sorted(items, key=lambda x: -x["max_ms"])[:5]
    return {
        "version": VERSION,
        "uptime_seconds": int(time.time() - STARTED_AT),
        "requests_total": total,
        "errors_total": errors,
        "error_rate": round(errors * 100 / total, 2) if total else 0.0,
        "avg_ms": round(total_ms / total, 1) if total else 0.0,
        "slow_threshold_ms": SLOW_MS,
        "endpoints": items,
        "slowest": slowest,
        "recent": recent[-20:],
    }


def business_counters() -> dict:
    """业务计数：全部从数据库实时统计。"""
    def one(sql: str, params: tuple = ()) -> int:
        return int(db.scalar(sql, params) or 0)

    return {
        "parks": one("SELECT COUNT(*) FROM parks"),
        "parks_lit": one("SELECT COUNT(*) FROM parks WHERE lit = 1"),
        "scenarios": one("SELECT COUNT(*) FROM scenarios"),
        "scenarios_online": one("SELECT COUNT(*) FROM scenarios WHERE status = 'online'"),
        "nodes": one("SELECT COUNT(*) FROM nodes"),
        "tasks": one("SELECT COUNT(*) FROM tasks"),
        "materials_indexed": one(
            "SELECT COUNT(*) FROM materials WHERE status = 'indexed'"),
        "users": one("SELECT COUNT(*) FROM users"),
        "devices_activated": one("SELECT COUNT(*) FROM devices"),
        "codes_used": one("SELECT COUNT(*) FROM activation_codes WHERE used = 1"),
        "node_visits": one("SELECT COUNT(*) FROM node_visits"),
        "task_submissions": one("SELECT COUNT(*) FROM task_submissions"),
        "tasks_passed": one(
            "SELECT COUNT(*) FROM task_submissions WHERE passed = 1"),
        "task_pass_rate": round(
            one("SELECT COUNT(*) FROM task_submissions WHERE passed = 1") * 100
            / max(1, one("SELECT COUNT(*) FROM task_submissions")), 2),
        "badges_granted": one("SELECT COUNT(*) FROM user_badges"),
        "growth_total": one("SELECT COALESCE(SUM(growth_total), 0) FROM users"),
        "ai_jobs": one("SELECT COUNT(*) FROM ai_jobs"),
        "ai_scenarios_created": one(
            "SELECT COUNT(*) FROM scenarios WHERE source = 'ai'"),
        "ai_avg_ms": round(float(db.scalar(
            "SELECT COALESCE(AVG(elapsed_ms), 0) FROM ai_jobs") or 0), 1),
        # events 表没有 user_id 字段，改为统计「留下过足迹的用户数」
        "users_with_trail": one("SELECT COUNT(DISTINCT user_id) FROM node_visits"),
        "events_logged": one("SELECT COUNT(*) FROM events"),
    }
