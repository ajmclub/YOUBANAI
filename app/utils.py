"""游伴 AI · 通用格式化工具。"""
from __future__ import annotations

from datetime import datetime

from .config import (AGE_BANDS, GROWTH_DIMS, NODE_KINDS, SCENARIO_STATUS, TASK_TYPES,
                     LEVEL_NAMES, LEVEL_THRESHOLDS)


# ---------------------------------------------------------------- 文本
def ago_text(text: str | None) -> str:
    """把 'YYYY-MM-DD HH:MM' 转成「2 分钟前」这类相对时间。"""
    if not text:
        return ""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    else:
        return text
    delta = (datetime.now() - dt).total_seconds()
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    return f"{int(delta // 86400)} 天前"


def short_time(text: str | None) -> str:
    """'2026-09-22 14:20' -> '09-22 14:20'"""
    if not text:
        return "—"
    parts = text.split(" ")
    if len(parts) == 2 and len(parts[0]) == 10:
        return f"{parts[0][5:]} {parts[1][:5]}"
    return text


def thousands(n: float | int) -> str:
    try:
        return f"{int(round(float(n))):,}"
    except (TypeError, ValueError):
        return str(n)


def ages(age_band: str | None) -> str:
    if not age_band:
        return "全年龄"
    label = AGE_BANDS.get(age_band)
    return f"{age_band} 岁" if not label else f"{age_band} 岁 · {label}"


def node_kind_label(kind: str, is_current: bool = False) -> str:
    base = NODE_KINDS.get(kind, "STORY NODE")
    if is_current and kind == "main":
        return f"{base} · 当前"
    if kind == "main" and not is_current:
        return base
    return base


def task_type_label(t: str | None) -> str:
    return TASK_TYPES.get(t or "", t or "任务")


def scenario_status_label(s: str | None) -> str:
    return SCENARIO_STATUS.get(s or "", s or "")


# ---------------------------------------------------------------- 等级
def level_of(growth_total: int) -> tuple[int, str]:
    """由成长值反推等级与称号。返回 (level, name)。"""
    growth_total = int(growth_total or 0)
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if growth_total >= threshold:
            level = i + 1
    level = min(level, len(LEVEL_NAMES))
    return level, LEVEL_NAMES[level - 1]


def next_level_gap(growth_total: int) -> dict:
    """距离下一级还差多少，以及**本级之内的进度百分比**。

    返回 `floor` / `ceil` 为当前等级的成长值区间，`percent` 为本级内进度（0-100）。
    没有这两个字段时，前端只能算成 `growth_total / (growth_total + need)`，
    那是「占下一级总量的比例」，语义并不等于「本级内的进度」。
    """
    growth_total = int(growth_total or 0)
    level, name = level_of(growth_total)
    floor = LEVEL_THRESHOLDS[level - 1]
    if level >= len(LEVEL_THRESHOLDS):
        return {"level": level, "name": name, "need": 0, "next_name": None,
                "at_max": True, "floor": floor, "ceil": None, "percent": 100}
    ceil = LEVEL_THRESHOLDS[level]
    span = max(1, ceil - floor)
    percent = int(round(max(0, min(100, (growth_total - floor) * 100 / span))))
    return {"level": level, "name": name, "need": max(0, ceil - growth_total),
            "next_name": LEVEL_NAMES[level], "at_max": False,
            "floor": floor, "ceil": ceil, "percent": percent}


# ---------------------------------------------------------------- 成长
def growth_list(values: dict) -> list[dict]:
    """把 {dim: value} 转成前端需要的列表。"""
    return [{"dim": dim, "label": label, "value": int(values.get(dim, 0))}
            for dim, label in GROWTH_DIMS]


def growth_gain_label(gain: dict) -> str:
    parts = [f"+{v} {label}" for dim, label in GROWTH_DIMS if (v := int(gain.get(dim, 0)))]
    return " · ".join(parts) if parts else ""


def clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))
