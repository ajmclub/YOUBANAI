"""游伴 AI · 剧情状态引擎。

负责把数据库中的剧本 / 章节 / 节点 / 任务，结合某个用户的进度，
组装成前端可直接渲染的剧情状态（章节时间轴、节点状态、当前任务）。
"""
from __future__ import annotations

from .. import db
from ..utils import node_kind_label, task_type_label
from . import growth


# ---------------------------------------------------------------- 节点状态
def node_state(user_id: int | None, node: dict) -> str:
    """done 已完成 / active 进行中 / locked 未解锁。"""
    if not user_id:
        return "locked"
    if growth.node_is_done(user_id, node["id"]):
        return "done"
    visited = db.query_one("SELECT 1 FROM node_visits WHERE user_id = ? AND node_id = ?",
                           (user_id, node["id"]))
    if visited:
        return "active"
    return "locked"


def node_status_chain(user_id: int | None, scenario_id: int) -> dict[int, str]:
    """一次性算出某剧本全部节点状态，避免 N+1 查询。"""
    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    if not user_id:
        return {n["id"]: "locked" for n in nodes}

    visited = {r["node_id"] for r in db.query(
        "SELECT node_id FROM node_visits WHERE user_id = ?", (user_id,))}
    # 已通过任务数（按任务聚合）
    passed = {r["task_id"]: r["c"] for r in db.query(
        "SELECT task_id, COUNT(*) AS c FROM task_submissions "
        "WHERE user_id = ? AND passed = 1 GROUP BY task_id", (user_id,))}
    tasks_by_node: dict[int, list[dict]] = {}
    for t in db.query("SELECT * FROM tasks WHERE scenario_id = ? AND enabled = 1", (scenario_id,)):
        tasks_by_node.setdefault(t["node_id"], []).append(t)

    out: dict[int, str] = {}
    for n in nodes:
        nid = n["id"]
        node_tasks = tasks_by_node.get(nid, [])
        if node_tasks:
            all_done = all(passed.get(t["id"], 0) >= int(t["target_count"] or 1)
                           for t in node_tasks)
        else:
            all_done = nid in visited
        if all_done:
            out[nid] = "done"
        elif nid in visited:
            out[nid] = "active"
        else:
            out[nid] = "locked"
    return out


def current_node(user_id: int, scenario_id: int) -> dict | None:
    """当前应当推进的节点：第一个未完成的节点。"""
    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    states = node_status_chain(user_id, scenario_id)
    for n in nodes:
        if states.get(n["id"]) != "done":
            return n
    return nodes[-1] if nodes else None


# ---------------------------------------------------------------- 任务
def task_progress(user_id: int | None, task: dict) -> dict:
    target = int(task.get("target_count") or 1)
    done = growth.task_done_count(user_id, task["id"]) if user_id else 0
    return {"done": min(done, target), "total": target, "complete": done >= target}


def task_brief(user_id: int | None, task: dict) -> dict:
    p = task_progress(user_id, task)
    return {
        "id": task["id"], "title": task["title"], "type": task["type"],
        "type_label": task_type_label(task["type"]), "age_band": task["age_band"],
        "done": p["done"], "total": p["total"], "complete": p["complete"],
        "progress": f"{p['done']}/{p['total']}" if p["total"] > 1 else None,
    }


def node_tasks(user_id: int | None, node_id: int) -> list[dict]:
    tasks = db.query("SELECT * FROM tasks WHERE node_id = ? AND enabled = 1 ORDER BY id", (node_id,))
    return [task_brief(user_id, t) for t in tasks]


def node_brief(user_id: int | None, node: dict, current_id: int | None = None) -> dict:
    state = node_state(user_id, node)
    return {
        "id": node["id"],
        "name": node["name"],
        "kind": node["kind"],
        "type_label": node_kind_label(node["kind"], is_current=node["id"] == current_id),
        "desc": node.get("place") or "",
        "place": node.get("place"),
        "state": state,
        "tasks": node_tasks(user_id, node["id"]),
    }


# ---------------------------------------------------------------- 剧本详情
def scenario_detail(user_id: int | None, scenario_id: int) -> dict | None:
    sc = db.query_one("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    if not sc:
        return None
    park = db.query_one("SELECT * FROM parks WHERE id = ?", (sc["park_id"],)) or {}

    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    chapters = db.query("SELECT * FROM chapters WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    states = node_status_chain(user_id, scenario_id)
    cur = current_node(user_id, scenario_id) if user_id else None
    cur_id = cur["id"] if cur else None

    nodes_by_chapter: dict[int, list[dict]] = {}
    for n in nodes:
        nodes_by_chapter.setdefault(n["chapter_id"], []).append(n)

    chapter_items = []
    for c in chapters:
        c_nodes = nodes_by_chapter.get(c["id"], [])
        c_states = [states.get(n["id"], "locked") for n in c_nodes]
        if c_states and all(s == "done" for s in c_states):
            c_state = "done"
        elif any(s in ("done", "active") for s in c_states):
            c_state = "now"
        else:
            c_state = "todo"
        chapter_items.append({
            "idx": c["idx"], "title": c["title"], "summary": c["summary"],
            "state": c_state,
            "nodes": [node_brief(user_id, n, cur_id) for n in c_nodes],
        })

    total = len(nodes)
    visited = 0
    if user_id:
        visited = len([1 for n in nodes if states.get(n["id"]) != "locked"])
    percent = int(round(visited * 100 / total)) if total else 0
    current_chapter = 1
    if cur and cur.get("chapter_id"):
        row = db.query_one("SELECT idx FROM chapters WHERE id = ?", (cur["chapter_id"],))
        current_chapter = row["idx"] if row else 1

    # 当前任务进度（用于「当前任务：xxx（1/3）」）
    cur_tasks = node_tasks(user_id, cur_id) if cur_id else []
    return {
        "id": sc["id"],
        "title": sc["title"],
        "city": park.get("city", ""),
        "park_id": sc["park_id"],
        "park_name": park.get("name", ""),
        "emoji": sc["emoji"],
        "kicker": sc["kicker"],
        "subtitle": sc["subtitle"],
        "meta": sc["meta"],
        "worldview": sc["worldview"],
        "age_band": sc["age_band"],
        "status": sc["status"],
        "chapters_count": len(chapters),
        "current_chapter": current_chapter,
        "nodes_count": total,
        "visited_nodes": visited,
        "progress_percent": percent,
        "current_node": node_brief(user_id, cur, cur_id) if cur else None,
        "current_tasks": cur_tasks,
        "chapters": chapter_items,
    }


# ---------------------------------------------------------------- 编辑器（B 端）
def scenario_canvas(scenario_id: int) -> dict | None:
    sc = db.query_one("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    if not sc:
        return None
    park = db.query_one("SELECT * FROM parks WHERE id = ?", (sc["park_id"],)) or {}
    chapters = db.query("SELECT * FROM chapters WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    links = db.query("SELECT * FROM node_links WHERE scenario_id = ?", (scenario_id,))

    current = current_node(1, scenario_id)
    cur_id = current["id"] if current else None

    node_items = []
    for n in nodes:
        cnt = int(db.scalar("SELECT COUNT(*) FROM tasks WHERE node_id = ?", (n["id"],)))
        state = "done" if n["id"] != cur_id and n["idx"] < (current["idx"] if current else 0) else "active"
        node_items.append({
            "id": n["id"], "chapter_id": n["chapter_id"], "name": n["name"],
            "kind": n["kind"], "type_label": node_kind_label(n["kind"], is_current=n["id"] == cur_id),
            "desc": n.get("place") or "", "trigger_type": n["trigger_type"],
            "lat": n["lat"], "lng": n["lng"], "radius_m": n["radius_m"],
            "age_band": n["age_band"], "story_text": n["story_text"],
            "ai_dialog": n["ai_dialog"], "hint": n["hint"], "place": n["place"],
            "x": n["x"], "y": n["y"], "task_count": cnt, "status": state,
        })
    return {
        "id": sc["id"], "title": sc["title"], "city": park.get("city", ""),
        "park_id": sc["park_id"], "park_name": park.get("name", ""),
        "emoji": sc["emoji"], "status": sc["status"],
        "age_band": sc["age_band"], "worldview": sc["worldview"],
        "chapters": [{"id": c["id"], "idx": c["idx"], "title": c["title"],
                      "summary": c["summary"]} for c in chapters],
        "nodes": node_items,
        "links": [{"from": l["from_node"], "to": l["to_node"], "color": l["color"]}
                  for l in links],
    }


# ---------------------------------------------------------------- 触发
def available_nodes(user_id: int, scenario_id: int) -> list[dict]:
    """当前「可达」的节点：所有前置节点（idx 更小）都已完成。

    这是剧情推进的核心规则——孩子必须按顺序解锁剧情，
    避免同一个景区内多个节点在同一个坐标同时触发。
    """
    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    out = []
    for n in nodes:
        if growth.node_is_done(user_id, n["id"]):
            continue
        # 检查前置节点（kind=entry 无前置）
        prev = db.query(
            "SELECT id FROM nodes WHERE scenario_id = ? AND idx < ? ORDER BY idx",
            (scenario_id, n["idx"]))
        if all(growth.node_is_done(user_id, p["id"]) for p in prev):
            out.append(n)
    return out


def triggerable_nodes(user_id: int, lat: float, lng: float,
                      scenario_id: int | None = None) -> list[dict]:
    """返回可触发的节点（可达 + 未完成 + 在围栏内）。"""
    from .geo import haversine

    if scenario_id:
        candidates = available_nodes(user_id, scenario_id)
    else:
        candidates = []
        for row in db.query("SELECT id FROM scenarios"):
            candidates += available_nodes(user_id, row["id"])

    out = []
    for n in candidates:
        if n.get("lat") is None or n.get("lng") is None:
            continue
        d = haversine(lat, lng, n["lat"], n["lng"])
        if d <= (n.get("radius_m") or 40):
            out.append({**n, "distance_m": int(round(d))})
    out.sort(key=lambda x: x["distance_m"])
    return out


def locked_reason(user_id: int, node: dict) -> str | None:
    """节点为什么还不能触发（用于前端提示）。"""
    if growth.node_is_done(user_id, node["id"]):
        return "已完成"
    prev = db.query(
        "SELECT id, name FROM nodes WHERE scenario_id = ? AND idx < ? ORDER BY idx",
        (node["scenario_id"], node["idx"]))
    for p in prev:
        if not growth.node_is_done(user_id, p["id"]):
            return f"需要先完成「{p['name']}」"
    return None
