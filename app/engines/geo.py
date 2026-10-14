"""游伴 AI · 地理围栏引擎。

实现「位置 → 识别 → 剧情触发」的核心闭环（商业计划书 P10）。
触发规则：haversine(user, node) <= node.radius_m
"""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6371000.0

# 「附近」判定倍率：距离 <= radius_m * NEARBY_FACTOR 视为附近（仅用于展示提示）
NEARBY_FACTOR = 8


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点间球面距离（米）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def distance_text(meters: float) -> str:
    if meters < 1000:
        return f"{int(round(meters))}m"
    return f"{meters / 1000:.1f}km"


def find_park(parks: list[dict], lat: float, lng: float) -> dict | None:
    """找出用户当前所在景区（含景区级围栏半径）。"""
    best, best_d = None, None
    for p in parks:
        if p.get("lat") is None or p.get("lng") is None:
            continue
        d = haversine(lat, lng, p["lat"], p["lng"])
        # 景区级围栏：允许 1.5 倍容差，避免演示坐标刚好落在边界外
        if d <= (p.get("radius_m") or 1500) * 1.5:
            if best_d is None or d < best_d:
                best, best_d = p, d
    return best


def locate_nodes(nodes: list[dict], lat: float, lng: float) -> tuple[list[dict], list[dict]]:
    """把节点分成「已触发」与「附近」两组。

    - 触发：距离 <= radius_m
    - 附近：距离 <= radius_m * NEARBY_FACTOR（用于「附近的故事点」展示）
    每个返回项附加 distance_m / distance_text。
    """
    triggered, nearby = [], []
    for n in nodes:
        if n.get("lat") is None or n.get("lng") is None:
            continue
        d = haversine(lat, lng, n["lat"], n["lng"])
        radius = n.get("radius_m") or 40
        item = {**n, "distance_m": int(round(d)), "distance_text": distance_text(d)}
        if d <= radius:
            triggered.append(item)
        elif d <= radius * NEARBY_FACTOR:
            nearby.append(item)
    triggered.sort(key=lambda x: x["distance_m"])
    nearby.sort(key=lambda x: x["distance_m"])
    return triggered, nearby
