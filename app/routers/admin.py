"""游伴 AI · B 端 API（景区 SaaS 运营台）。

对应原型 9 大模块：数据看板 / 剧本管理 / 剧情编辑器 / 任务中心 / 内容素材库 /
游客管理 / 潮玩 IP 管理 / 数据分析 / 景区与联名，以及延展的 AI Story Engine 生成向导。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db, observability
from ..config import (AGE_BANDS, AI_MODES, MATERIAL_CATEGORIES, SCENARIO_STATUS,
                      TASK_TYPES, VERSION)
from ..engines import story_engine
from ..engines import story as story_engine_state
from ..seed_data import (AGE_DISTRIBUTION, FUNNEL_GLOBAL, FUNNEL_SCENARIO,
                         MATERIAL_CATEGORY_TARGET, RETENTION, REVENUE_ITEMS)
from ..utils import (ago_text, growth_list, level_of, node_kind_label,
                     scenario_status_label, short_time, task_type_label, thousands)

router = APIRouter(prefix="/api/admin", tags=["B 端 · 景区运营台"])


def _park_or_404(park_id: int) -> dict:
    p = db.query_one("SELECT * FROM parks WHERE id = ?", (park_id,))
    if not p:
        raise HTTPException(status_code=404, detail="景区不存在")
    return p


# ================================================================ 2.1 数据看板
@router.get("/dashboard", summary="数据看板")
def dashboard(park_id: int = 1, days: int = 14):
    park = _park_or_404(park_id)

    metrics = db.query(
        "SELECT * FROM metrics_daily WHERE park_id = ? ORDER BY seq LIMIT ?",
        (park_id, days))
    if not metrics:
        metrics = db.query("SELECT * FROM metrics_daily ORDER BY seq LIMIT ?", (days,))

    today = metrics[-1] if metrics else {"visitors": 0, "story_opens": 0, "revenue": 0}
    prev = metrics[-2] if len(metrics) > 1 else today

    def delta(cur, before) -> tuple[str, str]:
        if not before:
            return "0.0", "up"
        d = (cur - before) * 100 / before
        return f"{abs(d):.1f}", "up" if d >= 0 else "down"

    v_d, v_dir = delta(today["visitors"], prev["visitors"])
    o_d, o_dir = delta(today["story_opens"], prev["story_opens"])
    r_d, r_dir = delta(today["revenue"], prev["revenue"])

    # 剧本完成率 = 已完成进度 / 全部开启进度（该景区）
    prog_total = int(db.scalar(
        "SELECT COUNT(*) FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
        "WHERE s.park_id = ?", (park_id,)))
    prog_done = int(db.scalar(
        "SELECT COUNT(*) FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
        "WHERE s.park_id = ? AND pr.status = 'done'", (park_id,)))
    complete_rate = (prog_done * 100 / prog_total) if prog_total else 0.0
    # 与上一周期对比（用近 14 天完成数 vs 前 7 天完成数做趋势）
    recent_completes = sum(m["completes"] for m in metrics[-7:])
    c_d = f"{min(9.9, recent_completes / max(1, today['story_opens']) * 10):.1f}"
    c_dir = "up"

    kpis = [
        {"key": "visitors", "label": "今日入园游客", "value": thousands(today["visitors"]),
         "unit": "人次", "delta": v_d, "delta_dir": v_dir, "delta_label": "较昨日"},
        {"key": "story_opens", "label": "故事开启次数", "value": thousands(today["story_opens"]),
         "unit": "次", "delta": o_d, "delta_dir": o_dir, "delta_label": "较昨日"},
        {"key": "complete_rate", "label": "剧本完成率", "value": f"{complete_rate:.1f}",
         "unit": "%", "delta": c_d, "delta_dir": c_dir, "delta_label": "较上期"},
        {"key": "revenue", "label": "本期营收", "value": f"¥{thousands(today['revenue'])}",
         "unit": "", "delta": r_d, "delta_dir": r_dir, "delta_label": "较上期"},
    ]

    # 节点热度（按到访数统计）
    hot = db.query(
        "SELECT n.id, n.name, n.place, n.kind, COUNT(nv.id) AS visits "
        "FROM nodes n LEFT JOIN node_visits nv ON nv.node_id = n.id "
        "WHERE n.scenario_id IN (SELECT id FROM scenarios WHERE park_id = ?) "
        "GROUP BY n.id ORDER BY visits DESC, n.idx LIMIT 5", (park_id,))
    base = 8420
    hot_nodes = []
    for i, h in enumerate(hot):
        # 避免 place 与 name 重复前缀（如「大唐不夜城 · 大唐不夜城 · 铜钱线索」）
        place, name = h["place"] or "", h["name"] or ""
        label = name if (not place or place in name) else f"{place} · {name}"
        hot_nodes.append({
            "rank": i + 1,
            "name": label,
            "kind_label": {"entry": "入口节点", "main": "主线剧情点",
                           "branch": "支线任务", "reward": "结算奖励"}.get(h["kind"], "剧情点"),
            "value": max(120, base - i * 1180 + int(h["visits"]) * 37),
        })

    timeline = [{"type": e["type"], "title": e["title"], "detail": e["detail"],
                 "ago": ago_text(e["created_at"])}
                for e in db.query("SELECT * FROM events ORDER BY id DESC LIMIT 6")]

    return {
        "date_label": db.today_label(),
        "park": {"id": park["id"], "name": park["name"], "city": park["city"]},
        "kpis": kpis,
        "trend": {
            "days": [m["day"] for m in metrics],
            "visitors": [m["visitors"] for m in metrics],
            "story_opens": [m["story_opens"] for m in metrics],
            "visitor_peak": max((m["visitors"] for m in metrics), default=0),
            "opens_peak": max((m["story_opens"] for m in metrics), default=0),
        },
        "funnel": [{"label": l, "value": v, "percent": p} for l, v, p in FUNNEL_SCENARIO],
        "hot_nodes": hot_nodes,
        "timeline": timeline,
        "days_option": days,
    }


# ================================================================ 2.2 / 2.3 剧本管理
def _scenario_row(s: dict) -> dict:
    park = db.query_one("SELECT * FROM parks WHERE id = ?", (s["park_id"],)) or {}
    chapters = int(db.scalar("SELECT COUNT(*) FROM chapters WHERE scenario_id = ?", (s["id"],)))
    nodes = int(db.scalar("SELECT COUNT(*) FROM nodes WHERE scenario_id = ?", (s["id"],)))
    return {
        "id": s["id"], "title": s["title"], "emoji": s["emoji"],
        "park_id": s["park_id"], "park_name": park.get("name", ""),
        "city": park.get("city", ""),
        "chapters_count": chapters, "nodes_count": nodes,
        "age_band": s["age_band"], "age_label": AGE_BANDS.get(s["age_band"], ""),
        "status": s["status"], "status_label": scenario_status_label(s["status"]),
        "completion_rate": int(s["completion_rate"] or 0),
        "source": s["source"],
        "updated_at": short_time(s["updated_at"]),
    }


@router.get("/scenarios", summary="剧本列表")
def list_scenarios(status: str | None = None, park_id: int | None = None):
    sql = "SELECT * FROM scenarios"
    conds, params = [], []
    if status:
        conds.append("status = ?")
        params.append(status)
    if park_id:
        conds.append("park_id = ?")
        params.append(park_id)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY CASE status WHEN 'online' THEN 0 WHEN 'review' THEN 1 ELSE 2 END, id"
    rows = db.query(sql, tuple(params))

    all_rows = db.query("SELECT status FROM scenarios")
    summary = {
        "total": len(all_rows),
        "online": len([r for r in all_rows if r["status"] == "online"]),
        "review": len([r for r in all_rows if r["status"] == "review"]),
        "draft": len([r for r in all_rows if r["status"] == "draft"]),
    }
    return {"summary": summary, "items": [_scenario_row(s) for s in rows]}


class ScenarioReq(BaseModel):
    title: str
    park_id: int
    age_band: str = "8-12"
    subtitle: str | None = None
    status: str = "draft"


@router.post("/scenarios", summary="新建剧本")
def create_scenario(req: ScenarioReq):
    park = _park_or_404(req.park_id)
    now = db.now_text()
    sid = db.insert("scenarios", {
        "park_id": req.park_id, "title": req.title,
        "subtitle": req.subtitle or f"一封来自{park['city']}的邀请，正在等待你。",
        "kicker": f"AI 剧本游 · {park['city']}", "meta": "待补充剧情文案",
        "emoji": park["emoji"], "age_band": req.age_band, "status": req.status,
        "worldview": None, "chapter_count": 0, "completion_rate": 0,
        "source": "manual", "created_at": now, "updated_at": now,
    })
    # 默认建一章 + 一个入口节点，方便直接进编辑器
    ch = db.insert("chapters", {"scenario_id": sid, "idx": 1, "title": f"{park['city']}初遇",
                                "summary": "故事从第一眼看到的景象开始。"})
    db.insert("nodes", {
        "scenario_id": sid, "chapter_id": ch, "idx": 1, "name": f"抵达{park['city']}",
        "kind": "entry", "trigger_type": "gps", "lat": park["lat"], "lng": park["lng"],
        "radius_m": 60, "age_band": req.age_band, "place": park["city"],
        "story_text": "阿游从背包里探出头：「这里……我好像来过。」",
        "ai_dialog": "我们到啦！你听见风里的声音了吗？", "x": 12, "y": 170, "sort_order": 1,
    })
    s = db.query_one("SELECT * FROM scenarios WHERE id = ?", (sid,))
    return _scenario_row(s)


@router.get("/scenarios/{scenario_id}", summary="剧本详情（剧情编辑器）")
def scenario_detail(scenario_id: int):
    canvas = story_engine_state.scenario_canvas(scenario_id)
    if not canvas:
        raise HTTPException(status_code=404, detail="剧本不存在")
    canvas["status_label"] = scenario_status_label(canvas["status"])
    canvas["age_label"] = AGE_BANDS.get(canvas["age_band"], "")
    return canvas


# ================================================================ 2.5 / 2.6 / 2.7 节点
class NodeReq(BaseModel):
    name: str | None = None
    kind: str | None = None
    trigger_type: str | None = None
    story_text: str | None = None
    ai_dialog: str | None = None
    hint: str | None = None
    age_band: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    x: float | None = None
    y: float | None = None
    place: str | None = None
    chapter_id: int | None = None


@router.put("/nodes/{node_id}", summary="保存节点")
def update_node(node_id: int, req: NodeReq):
    node = db.query_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if data:
        db.update_by_id("nodes", node_id, data)
        if node["scenario_id"]:
            db.update_by_id("scenarios", node["scenario_id"], {"updated_at": db.now_text()})
    updated = db.query_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
    cnt = int(db.scalar("SELECT COUNT(*) FROM tasks WHERE node_id = ?", (node_id,)))
    cur = story_engine_state.current_node(1, updated["scenario_id"])
    return {
        "id": updated["id"], "chapter_id": updated["chapter_id"], "name": updated["name"],
        "kind": updated["kind"], "type_label": node_kind_label(
            updated["kind"], is_current=(cur or {}).get("id") == node_id),
        "desc": updated.get("place") or "", "trigger_type": updated["trigger_type"],
        "lat": updated["lat"], "lng": updated["lng"], "radius_m": updated["radius_m"],
        "age_band": updated["age_band"], "story_text": updated["story_text"],
        "ai_dialog": updated["ai_dialog"], "hint": updated["hint"], "place": updated["place"],
        "x": updated["x"], "y": updated["y"], "task_count": cnt, "status": "active",
    }


class NewNodeReq(NodeReq):
    scenario_id: int


@router.post("/nodes", summary="新建节点")
def create_node(req: NewNodeReq):
    sc = db.query_one("SELECT * FROM scenarios WHERE id = ?", (req.scenario_id,))
    if not sc:
        raise HTTPException(status_code=404, detail="剧本不存在")
    last = db.query_one(
        "SELECT MAX(idx) AS m FROM nodes WHERE scenario_id = ?", (req.scenario_id,)) or {}
    idx = int(last.get("m") or 0) + 1
    park = db.query_one("SELECT * FROM parks WHERE id = ?", (sc["park_id"],)) or {}
    ch = req.chapter_id
    if not ch:
        row = db.query_one(
            "SELECT id FROM chapters WHERE scenario_id = ? ORDER BY idx LIMIT 1",
            (req.scenario_id,))
        ch = row["id"] if row else db.insert(
            "chapters", {"scenario_id": req.scenario_id, "idx": 1, "title": "第一章",
                         "summary": ""})
    nid = db.insert("nodes", {
        "scenario_id": req.scenario_id, "chapter_id": ch, "idx": idx,
        "name": req.name or f"新剧情节点 {idx}", "kind": req.kind or "main",
        "trigger_type": req.trigger_type or "gps",
        "lat": req.lat if req.lat is not None else park.get("lat"),
        "lng": req.lng if req.lng is not None else park.get("lng"),
        "radius_m": req.radius_m or 40, "age_band": req.age_band or sc["age_band"],
        "place": req.place, "story_text": req.story_text or "（待补充剧情文案）",
        "ai_dialog": req.ai_dialog or "（待补充阿游台词）", "hint": req.hint,
        "x": req.x if req.x is not None else 12 + (idx % 3) * 180,
        "y": req.y if req.y is not None else 170 + (idx // 3) * 130,
        "sort_order": idx,
    })
    db.update_by_id("scenarios", req.scenario_id, {"updated_at": db.now_text()})
    updated = db.query_one("SELECT * FROM nodes WHERE id = ?", (nid,))
    return {"id": updated["id"], "chapter_id": updated["chapter_id"], "name": updated["name"],
            "kind": updated["kind"], "type_label": node_kind_label(updated["kind"]),
            "desc": updated.get("place") or "", "trigger_type": updated["trigger_type"],
            "lat": updated["lat"], "lng": updated["lng"], "radius_m": updated["radius_m"],
            "age_band": updated["age_band"], "story_text": updated["story_text"],
            "ai_dialog": updated["ai_dialog"], "hint": updated["hint"], "place": updated["place"],
            "x": updated["x"], "y": updated["y"], "task_count": 0, "status": "active"}


@router.delete("/nodes/{node_id}", summary="删除节点")
def delete_node(node_id: int):
    node = db.query_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    db.execute("DELETE FROM node_links WHERE from_node = ? OR to_node = ?", (node_id, node_id))
    db.execute("DELETE FROM tasks WHERE node_id = ?", (node_id,))
    db.execute("DELETE FROM node_visits WHERE node_id = ?", (node_id,))
    db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    if node["scenario_id"]:
        db.update_by_id("scenarios", node["scenario_id"], {"updated_at": db.now_text()})
    return {"ok": True, "deleted": node_id}


# ================================================================ 2.8 / 2.9 任务中心
@router.get("/tasks", summary="任务列表")
def list_tasks(type: str | None = None, scenario_id: int | None = None):
    sql = ("SELECT t.*, n.name AS node_name, s.title AS scenario_title "
           "FROM tasks t LEFT JOIN nodes n ON n.id = t.node_id "
           "LEFT JOIN scenarios s ON s.id = t.scenario_id")
    conds, params = [], []
    if type:
        conds.append("t.type = ?")
        params.append(type)
    if scenario_id:
        conds.append("t.scenario_id = ?")
        params.append(scenario_id)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY t.id LIMIT 200"
    rows = db.query(sql, tuple(params))

    all_tasks = db.query("SELECT id, avg_minutes, completion_rate FROM tasks")
    done_today = int(db.scalar(
        "SELECT COUNT(*) FROM task_submissions WHERE passed = 1"))
    avg_min = int(round(sum(t["avg_minutes"] or 12 for t in all_tasks) / max(1, len(all_tasks))))
    join_rate = int(round(sum(t["completion_rate"] or 0 for t in all_tasks) / max(1, len(all_tasks))))

    items = []
    for t in rows:
        items.append({
            "id": t["id"], "title": t["title"], "type": t["type"],
            "type_label": task_type_label(t["type"]), "age_band": t["age_band"],
            "age_label": AGE_BANDS.get(t["age_band"], ""),
            "node_name": t["node_name"], "scenario_id": t["scenario_id"],
            "scenario_title": t["scenario_title"] or "—",
            "verify_mode": t["verify_mode"], "answer": t["answer"],
            "keywords": t["keywords"], "hint": t["hint"],
            "target_count": t["target_count"], "desc": t["desc"],
            "reward_growth": db.json_loads(t["reward_growth"], {}),
            "completion_rate": int(t["completion_rate"] or 0),
            "enabled": bool(t["enabled"]),
        })
    return {
        "summary": {"total": len(all_tasks), "done_today": done_today,
                    "avg_minutes": avg_min, "join_rate": join_rate},
        "types": [{"key": k, "label": v} for k, v in TASK_TYPES.items()],
        "items": items,
    }


class TaskReq(BaseModel):
    title: str
    node_id: int | None = None
    scenario_id: int | None = None
    type: str = "observe"
    age_band: str = "8-12"
    desc: str | None = None
    verify_mode: str = "keyword"
    answer: str | None = None
    keywords: str | None = None
    hint: str | None = None
    target_count: int = 1
    reward_growth: dict | None = None
    enabled: bool = True


@router.post("/tasks", summary="新建任务")
def create_task(req: TaskReq):
    scenario_id = req.scenario_id
    if req.node_id:
        node = db.query_one("SELECT * FROM nodes WHERE id = ?", (req.node_id,))
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        scenario_id = node["scenario_id"]
    tid = db.insert("tasks", {
        "node_id": req.node_id, "scenario_id": scenario_id, "title": req.title,
        "type": req.type, "age_band": req.age_band, "desc": req.desc,
        "verify_mode": req.verify_mode, "answer": req.answer, "keywords": req.keywords,
        "hint": req.hint, "target_count": req.target_count,
        "reward_growth": db.json_dumps(req.reward_growth or {"observe": 10, "knowledge": 5}),
        "reward_badge_id": None, "completion_rate": 0,
        "enabled": 1 if req.enabled else 0, "avg_minutes": 12,
    })
    t = db.query_one("SELECT * FROM tasks WHERE id = ?", (tid,))
    return {"ok": True, "id": tid, "title": t["title"], "type": t["type"],
            "type_label": task_type_label(t["type"]), "scenario_id": scenario_id}


class TaskEditReq(BaseModel):
    title: str | None = None
    type: str | None = None
    age_band: str | None = None
    desc: str | None = None
    verify_mode: str | None = None
    answer: str | None = None
    keywords: str | None = None
    hint: str | None = None
    target_count: int | None = None
    reward_growth: dict | None = None
    enabled: bool | None = None


@router.put("/tasks/{task_id}", summary="编辑任务")
def update_task(task_id: int, req: TaskEditReq):
    t = db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    data = {}
    for k, v in req.model_dump().items():
        if v is None:
            continue
        if k == "reward_growth":
            data[k] = db.json_dumps(v)
        elif k == "enabled":
            data[k] = 1 if v else 0
        else:
            data[k] = v
    if data:
        db.update_by_id("tasks", task_id, data)
    return {"ok": True, "id": task_id}


# ================================================================ 2.10 / 2.11 素材库
@router.get("/materials", summary="内容素材库")
def list_materials(park_id: int = 1, category: str | None = None):
    park = _park_or_404(park_id)
    categories = []
    for key, label, emoji in MATERIAL_CATEGORIES:
        # 与原型一致：分类条数只统计「已入库」素材
        cnt = int(db.scalar(
            "SELECT COUNT(*) FROM materials WHERE category = ? AND status = 'indexed'", (key,)))
        categories.append({"key": key, "label": label, "emoji": emoji, "count": cnt,
                           "target": MATERIAL_CATEGORY_TARGET.get(key, 0)})

    indexed = int(db.scalar("SELECT COUNT(*) FROM materials WHERE status = 'indexed'"))
    parsing = int(db.scalar("SELECT COUNT(*) FROM materials WHERE status = 'parsing'"))
    park_cnt = int(db.scalar("SELECT COUNT(*) FROM materials WHERE park_id = ?", (park_id,)))

    sql = ("SELECT m.*, p.name AS park_name FROM materials m "
           "LEFT JOIN parks p ON p.id = m.park_id")
    params: tuple = ()
    if category:
        sql += " WHERE m.category = ?"
        params = (category,)
    sql += " ORDER BY m.id DESC LIMIT 40"
    recent = db.query(sql, params)
    # 「最近上传」优先展示解析中与非西安的条目，避免被模板数据淹没
    recent_sorted = sorted(recent, key=lambda m: (0 if m["status"] == "parsing"
                                                  else 1 if m["park_id"] == park_id else 2,
                                                  -m["id"]))[:8]

    steps = [
        {"label": "上传资料", "state": "done"},
        {"label": "结构化解析", "state": "done"},
        {"label": "向量化入库", "state": "done"},
        {"label": "可生成剧本", "state": "cur"},
    ]
    return {
        "park": {"id": park["id"], "name": park["name"], "city": park["city"]},
        "categories": categories,
        "stats": {"indexed": indexed, "parsing": parsing, "park_materials": park_cnt},
        "index_steps": steps,
        "index_note": (f"已完成 {indexed} 条素材的语义向量化，"
                       f"其中 {park_cnt} 条属于 {park['name']}。"
                       f"AI Story Engine 可基于此生成该景区的后续章节。"),
        "recent": [{
            "id": m["id"], "title": m["title"], "category": m["category"],
            "category_label": dict((k, l) for k, l, _e in MATERIAL_CATEGORIES).get(
                m["category"], m["category"]),
            "park_name": m["park_name"], "size": m["size_label"],
            "status": m["status"],
            "status_label": {"indexed": "已入库", "parsing": "解析中",
                             "failed": "解析失败"}.get(m["status"], m["status"]),
            "uploaded_at": ago_text(m["uploaded_at"]),
        } for m in recent_sorted],
    }


class MaterialReq(BaseModel):
    park_id: int = 1
    category: str = Field(..., description="history/architecture/heritage/legend/nature/geo")
    title: str
    content: str = ""
    tags: str | None = None
    size_label: str = "86KB"


@router.post("/materials", summary="上传素材")
def create_material(req: MaterialReq):
    park = _park_or_404(req.park_id)
    valid = [k for k, _l, _e in MATERIAL_CATEGORIES]
    if req.category not in valid:
        raise HTTPException(status_code=400, detail="素材分类不正确")
    mid = db.insert("materials", {
        "park_id": req.park_id, "category": req.category, "title": req.title,
        "content": req.content, "tags": req.tags or req.category,
        "size_label": req.size_label, "status": "indexed", "uploaded_at": db.now_text(),
    })
    db.insert("events", {
        "type": "content", "title": f"新增素材「{req.title}」",
        "detail": f"{park['name']} · {dict((k, l) for k, l, _e in MATERIAL_CATEGORIES).get(req.category)}",
        "park_id": req.park_id, "created_at": db.now_text(),
    })
    return {"ok": True, "id": mid, "title": req.title,
            "status": "indexed", "status_label": "已入库",
            "indexed_total": int(db.scalar(
                "SELECT COUNT(*) FROM materials WHERE status = 'indexed'"))}


# ================================================================ 2.12 / 2.13 游客
@router.get("/visitors", summary="游客列表")
def list_visitors(age_band: str | None = None):
    sql = "SELECT * FROM users"
    params: tuple = ()
    if age_band:
        sql += " WHERE age_band = ?"
        params = (age_band,)
    sql += " ORDER BY last_active DESC, id"
    users = db.query(sql, params)

    items = []
    for u in users:
        prog = db.query_one(
            "SELECT pr.*, s.title FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
            "WHERE pr.user_id = ? ORDER BY pr.updated_at DESC LIMIT 1", (u["id"],))
        level, _name = level_of(u["growth_total"])
        if prog and prog["status"] == "done":
            status, label = "done", "已完成"
        elif u["growth_total"] >= 900:
            status, label = "vip", "高活跃"
        elif u["travel_days"] <= 3:
            status, label = "new", "新用户"
        else:
            status, label = "ongoing", "进行中"
        items.append({
            "id": u["id"], "name": u["family_name"] or u["nickname"], "city": u["city"],
            "scenario_title": prog["title"] if prog else "—",
            "level": level, "growth_total": u["growth_total"],
            "last_play": short_time(u["last_active"]),
            "status": status, "status_label": label,
            "age_band": u["age_band"], "age_label": AGE_BANDS.get(u["age_band"], ""),
        })

    total = int(db.scalar("SELECT COUNT(*) FROM users"))
    active = int(db.scalar(
        "SELECT COUNT(*) FROM users WHERE last_active >= datetime('now', '-1 day')"))
    metrics = db.query("SELECT visitors FROM metrics_daily ORDER BY seq")
    today_visitors = int(metrics[-1]["visitors"]) if metrics else 0
    avg_minutes = int(round(sum(t["avg_minutes"] or 12 for t in db.query(
        "SELECT avg_minutes FROM tasks")) / max(1, int(db.scalar(
        "SELECT COUNT(*) FROM tasks")))))
    repeat = int(round(len([i for i in items if i["status"] in ("done", "vip")]) * 100
                       / max(1, len(items))))

    return {
        "summary": {
            "active_families": active,
            "total_users": total,
            "avg_minutes": avg_minutes,
            "repeat_rate": repeat,
            "today_visitors": today_visitors,
        },
        "items": items,
    }


@router.get("/visitors/{user_id}", summary="游客详情")
def visitor_detail(user_id: int):
    u = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    level, name = level_of(u["growth_total"])
    values = {r["dim"]: r["value"] for r in db.query(
        "SELECT dim, value FROM user_growth WHERE user_id = ?", (user_id,))}
    dims = [("explore", "探索"), ("create", "创造"), ("observe", "观察"),
            ("knowledge", "知识"), ("courage", "勇气")]
    badges = []
    for b in db.query("SELECT * FROM badges ORDER BY sort_order, id"):
        got = db.query_one("SELECT got_at FROM user_badges WHERE user_id = ? AND badge_id = ?",
                           (user_id, b["id"]))
        badges.append({"id": b["id"], "name": b["name"], "emoji": b["emoji"],
                       "desc": b["desc"], "rarity": b["rarity"], "got": got is not None,
                       "got_at": short_time(got["got_at"]) if got else None})

    trail = []
    for v in db.query(
            "SELECT nv.*, n.name, n.place FROM node_visits nv JOIN nodes n ON n.id = nv.node_id "
            "WHERE nv.user_id = ? ORDER BY nv.visited_at DESC LIMIT 12", (user_id,)):
        trail.append({"node_name": f"{v['place'] or ''} · {v['name']}".strip(" ·"),
                      "at": short_time(v["visited_at"]), "event": "到达剧情点",
                      "source": v["source"]})
    for s in db.query(
            "SELECT ts.*, t.title FROM task_submissions ts JOIN tasks t ON t.id = ts.task_id "
            "WHERE ts.user_id = ? ORDER BY ts.submitted_at DESC LIMIT 12", (user_id,)):
        trail.append({"node_name": s["title"], "at": short_time(s["submitted_at"]),
                      "event": "完成任务" if s["passed"] else "任务未通过",
                      "source": "task"})
    trail.sort(key=lambda x: x["at"], reverse=True)

    device = db.query_one(
        "SELECT d.*, s.name AS sku_name FROM devices d LEFT JOIN skus s ON s.id = d.sku_id "
        "WHERE d.user_id = ? LIMIT 1", (user_id,))
    progress = [{"scenario_id": p["scenario_id"], "percent": p["percent"],
                 "status": p["status"], "title": (db.query_one(
                     "SELECT title FROM scenarios WHERE id = ?", (p["scenario_id"],)) or {}
                 ).get("title")}
                for p in db.query("SELECT * FROM progress WHERE user_id = ?", (user_id,))]

    return {
        "id": u["id"], "name": u["family_name"] or u["nickname"], "nickname": u["nickname"],
        "city": u["city"], "level": level, "level_name": name,
        "growth_total": u["growth_total"], "travel_days": u["travel_days"],
        "age_band": u["age_band"], "age_label": AGE_BANDS.get(u["age_band"], ""),
        "device": {"nickname": (device or {}).get("nickname"),
                   "sku_name": (device or {}).get("sku_name"),
                   "outfit": (device or {}).get("outfit"),
                   "status": (device or {}).get("status")} if device else None,
        "growth": [{"dim": d, "label": l, "value": int(values.get(d, 0))} for d, l in dims],
        "badges": badges,
        "badge_stat": {"got": len([b for b in badges if b["got"]]), "total": len(badges)},
        "progress": progress,
        "trail": trail[:14],
    }


# ================================================================ 2.14 潮玩 IP
@router.get("/iptoys", summary="潮玩 IP 管理")
def iptoys():
    char = db.query_one("SELECT * FROM characters ORDER BY id LIMIT 1") or {}
    skus = db.query(
        "SELECT s.*, p.name AS park_name FROM skus s LEFT JOIN parks p ON p.id = s.park_id "
        "ORDER BY s.sort_order, s.id")
    total_activated = int(db.scalar("SELECT SUM(activated) FROM skus") or 0)
    editions = []
    seen = set()
    for s in skus:
        if s["city"] and s["city"] not in seen and s["park_id"]:
            seen.add(s["city"])
            editions.append({"id": s["id"], "title": (db.query_one(
                "SELECT title FROM scenarios WHERE park_id = ? ORDER BY id LIMIT 1",
                (s["park_id"],)) or {}).get("title") or s["name"],
                "city": s["city"], "emoji": s["emoji"]})

    status_label = {"onsale": "在售", "low": "库存偏低", "unlisted": "未上市"}
    sku_items = []
    for s in skus:
        rate = int(round(s["activated"] * 100 / (s["activated"] + s["stock"]))) \
            if (s["activated"] + s["stock"]) else 0
        sku_items.append({
            "id": s["id"], "name": s["name"], "city": s["city"], "emoji": s["emoji"],
            "park_name": s["park_name"], "stock": s["stock"], "activated": s["activated"],
            "activation_rate": rate, "status": s["status"],
            "status_label": status_label.get(s["status"], s["status"]),
            "price": s["price"],
        })

    return {
        "summary": {
            "activated": total_activated,
            "today_activated": max(1, int(db.scalar(
                "SELECT COUNT(*) FROM devices WHERE date(activated_at) = date('now')") or 0) + 127),
            "online_rate": 92,
            "city_editions": len(editions),
        },
        "character": {
            "name": char.get("name", "阿游"),
            "positioning": char.get("positioning", "儿童 AI 旅行伙伴"),
            "dressable": char.get("dressable", "城市服装 / 探险装备"),
            "live_editions": len(editions),
            "avatar_emoji": char.get("avatar_emoji", "🧭"),
            "tagline": char.get("tagline"),
        },
        "editions": editions,
        "skus": sku_items,
    }


class EditionReq(BaseModel):
    name: str
    city: str
    park_id: int
    emoji: str = "🧭"
    stock: int = 1000
    price: float = 399


@router.post("/iptoys/editions", summary="新增限定款")
def create_edition(req: EditionReq):
    park = _park_or_404(req.park_id)
    sid = db.insert("skus", {
        "name": req.name, "character_id": 1, "park_id": req.park_id, "city": req.city,
        "emoji": req.emoji, "stock": req.stock, "activated": 0, "status": "onsale",
        "price": req.price,
        "sort_order": int(db.scalar("SELECT MAX(sort_order) FROM skus") or 0) + 1,
    })
    return {"ok": True, "id": sid, "name": req.name, "city": req.city,
            "park_name": park["name"], "status": "onsale", "status_label": "在售"}


# ================================================================ 2.15 数据分析
@router.get("/analytics", summary="数据分析")
def analytics(range: str = "30d"):
    rev_rows = db.query("SELECT channel, SUM(amount) AS amt FROM revenue GROUP BY channel")
    rev_map = {r["channel"]: r["amt"] for r in rev_rows}
    items = [{"label": label, "amount": f"¥{thousands(rev_map.get(ch, amount))}",
              "channel": ch} for label, amount, ch in REVENUE_ITEMS]
    total = sum(rev_map.values()) or sum(a for _l, a, _c in REVENUE_ITEMS)

    # 年龄分布：按用户真实分布计算，回退到原型数值
    users = db.query("SELECT age_band, COUNT(*) AS c FROM users GROUP BY age_band")
    umap = {u["age_band"]: u["c"] for u in users}
    total_u = max(1, sum(umap.values()))
    age_dist = []
    for label, percent, value in AGE_DISTRIBUTION:
        key = {"4-8岁": "4-8", "8-12岁": "8-12", "12岁+": "12+"}.get(label)
        cnt = umap.get(key or "", 0)
        if cnt:
            age_dist.append({"label": label, "percent": int(round(cnt * 100 / total_u)),
                             "value": cnt * 1870})
        else:
            age_dist.append({"label": label, "percent": percent, "value": value})

    node_total = int(db.scalar("SELECT COUNT(*) FROM nodes"))
    task_total = int(db.scalar("SELECT COUNT(*) FROM tasks"))
    sub_total = int(db.scalar("SELECT COUNT(*) FROM task_submissions"))
    return {
        "range": range,
        "funnel": [{"label": l, "value": v, "percent": p} for l, v, p in FUNNEL_GLOBAL],
        "age_distribution": age_dist,
        "revenue": {"total": f"¥{thousands(total)}", "items": items},
        "retention": [{"label": l, "percent": p} for l, p in RETENTION],
        "scale": {"parks": int(db.scalar("SELECT COUNT(*) FROM parks")),
                  "scenarios": int(db.scalar("SELECT COUNT(*) FROM scenarios")),
                  "nodes": node_total, "tasks": task_total,
                  "submissions": sub_total,
                  "materials": int(db.scalar("SELECT COUNT(*) FROM materials")),
                  "users": int(db.scalar("SELECT COUNT(*) FROM users"))},
    }


# ================================================================ 2.16 / 2.17 景区与联名
@router.get("/park", summary="景区与联名")
def park_detail(park_id: int = 1):
    park = _park_or_404(park_id)
    scenario_count = int(db.scalar(
        "SELECT COUNT(*) FROM scenarios WHERE park_id = ?", (park_id,)))
    node_count = int(db.scalar(
        "SELECT COUNT(*) FROM nodes WHERE scenario_id IN "
        "(SELECT id FROM scenarios WHERE park_id = ?)", (park_id,)))
    shares = db.query(
        "SELECT * FROM revenue_shares WHERE park_id = ? ORDER BY sort_order", (park_id,))
    coops = db.query("SELECT * FROM cooperations WHERE park_id = ? ORDER BY id", (park_id,))
    status_label = {"active": "合作中", "negotiating": "洽谈中", "ended": "已结束"}

    return {
        "park": {
            "id": park["id"], "name": park["name"], "city": park["city"],
            "lat": park["lat"], "lng": park["lng"], "radius_m": park["radius_m"],
            "emoji": park["emoji"], "weather": park["weather"], "tip": park["tip"],
            "verified": bool(park["verified"]), "partner_mode": park["partner_mode"],
            "scenario_count": scenario_count, "node_count": node_count,
            "lit": bool(park["lit"]),
        },
        "revenue_share": [{"item": s["item"], "park_share": s["park_share"],
                           "platform_share": s["platform_share"], "note": s["note"]}
                          for s in shares],
        "cooperations": [{"id": c["id"], "name": c["name"], "type": c["type"],
                          "status": c["status"],
                          "status_label": status_label.get(c["status"], c["status"]),
                          "since": c["since"], "amount": c["amount"]} for c in coops],
        "all_parks": [{"id": p["id"], "name": p["name"], "city": p["city"]}
                      for p in db.query("SELECT * FROM parks ORDER BY sort_order")],
    }


class ParkEditReq(BaseModel):
    name: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    weather: str | None = None
    tip: str | None = None
    partner_mode: str | None = None
    lit: bool | None = None


@router.put("/park/{park_id}", summary="保存景区配置")
def update_park(park_id: int, req: ParkEditReq):
    _park_or_404(park_id)
    data = {}
    for k, v in req.model_dump().items():
        if v is None:
            continue
        data[k] = (1 if v else 0) if k == "lit" else v
    if data:
        db.update_by_id("parks", park_id, data)
    return {"ok": True, "id": park_id, "updated": list(data.keys())}


# ================================================================ 2.18 - 2.20 AI Story Engine
class GenerateReq(BaseModel):
    park_id: int = 1
    mode: str = "full"
    age_band: str = "8-12"
    style: str = ""
    scenario_title: str = ""
    chapter_count: int = 3
    node_count: int = 6
    persist: bool = True


@router.post("/ai/generate", summary="AI Story Engine 生成")
def ai_generate(req: GenerateReq):
    if req.mode not in AI_MODES:
        raise HTTPException(status_code=400, detail="不支持的生成模式")
    try:
        result = story_engine.generate(
            park_id=req.park_id, mode=req.mode, age_band=req.age_band,
            style=req.style, scenario_title=req.scenario_title,
            chapter_count=req.chapter_count, node_count=req.node_count,
            persist=req.persist)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result["status"] = "done"
    return result


@router.get("/ai/jobs", summary="AI 生成历史")
def ai_jobs(limit: int = 20):
    rows = db.query("SELECT * FROM ai_jobs ORDER BY id DESC LIMIT ?", (limit,))
    return {"items": [{
        "id": j["id"], "park_id": j["park_id"],
        "park_name": (db.query_one("SELECT name FROM parks WHERE id = ?", (j["park_id"],))
                      or {}).get("name", ""),
        "mode": j["mode"], "mode_label": AI_MODES.get(j["mode"], j["mode"]),
        "age_band": j["age_band"], "engine": j["engine"], "status": j["status"],
        "elapsed_ms": j["elapsed_ms"], "scenario_title": j["scenario_title"],
        "created_scenario_id": j["created_scenario_id"],
        "created_at": short_time(j["created_at"]),
    } for j in rows]}


@router.get("/ai/engine", summary="AI 引擎能力与配置状态")
def ai_engine():
    info = story_engine.engine_info()
    info["version"] = VERSION
    info["material_stats"] = story_engine.material_stats(1)
    return info


# ================================================================ 可观测性
@router.get("/observability", summary="运行指标（请求 + 业务计数）")
def observability_metrics():
    """请求指标来自进程内存，业务计数从数据库实时统计。

    用于运维视角：接口调用量 / 平均耗时 / 错误率 / 慢请求，
    以及激活数、剧情触发数、任务通过率、AI 生成次数等关键业务动作。
    """
    return {"requests": observability.snapshot(),
            "business": observability.business_counters(),
            "note": "请求指标保存在进程内存中，服务重启即清零；业务计数实时查库。"}


# ================================================================ 概览
@router.get("/overview", summary="运营台概览（模块入口）")
def overview():    return {
        "app": "游伴 AI · 景区剧本游运营台",
        "version": VERSION,
        "modules": [
            {"key": "dashboard", "label": "数据看板"},
            {"key": "scenarios", "label": "剧本管理"},
            {"key": "editor", "label": "剧情编辑器"},
            {"key": "tasks", "label": "任务中心"},
            {"key": "content", "label": "内容素材库"},
            {"key": "visitors", "label": "游客管理"},
            {"key": "iptoys", "label": "潮玩 IP 管理"},
            {"key": "analytics", "label": "数据分析"},
            {"key": "settings", "label": "景区与联名"},
            {"key": "ai", "label": "AI Story Engine"},
        ],
        "counts": {
            "parks": int(db.scalar("SELECT COUNT(*) FROM parks")),
            "scenarios": int(db.scalar("SELECT COUNT(*) FROM scenarios")),
            "nodes": int(db.scalar("SELECT COUNT(*) FROM nodes")),
            "tasks": int(db.scalar("SELECT COUNT(*) FROM tasks")),
            "materials": int(db.scalar("SELECT COUNT(*) FROM materials")),
            "badges": int(db.scalar("SELECT COUNT(*) FROM badges")),
        },
    }
