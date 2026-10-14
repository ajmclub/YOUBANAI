"""游伴 AI · C 端 API（小程序 / H5）。

对应原型 5 大页面：旅伴 / 探索 / 对话 / 剧本 / 我的，以及开箱激活与任务执行流程。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db
from ..config import AGE_BANDS, RARITY_LABELS
from ..engines import chat as chat_engine
from ..engines import geo, growth, parent, story
from ..utils import (ages, clamp_percent, level_of, next_level_gap, node_kind_label,
                     short_time, task_type_label, thousands)

router = APIRouter(prefix="/api/c", tags=["C 端 · 小程序"])

# 演示用默认定位偏移：让「附近的故事点」有真实距离（约 140m）
DEMO_OFFSET = (0.0011, -0.0009)


# ---------------------------------------------------------------- 依赖
def _user_or_404(user_id: int) -> dict:
    u = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    return u


def _device_of(user_id: int) -> dict | None:
    row = db.query_one(
        "SELECT d.*, s.name AS sku_name, s.city AS sku_city, s.emoji AS sku_emoji "
        "FROM devices d LEFT JOIN skus s ON s.id = d.sku_id "
        "WHERE d.user_id = ? ORDER BY d.id LIMIT 1", (user_id,))
    return row


def _park_for(user: dict) -> dict | None:
    """用户当前所在景区：优先最近有进度的剧本所属景区，其次同名城市，最后第 1 个。"""
    row = db.query_one(
        "SELECT p.* FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
        "JOIN parks p ON p.id = s.park_id WHERE pr.user_id = ? "
        "ORDER BY pr.updated_at DESC LIMIT 1", (user["id"],))
    if row:
        return row
    row = db.query_one("SELECT * FROM parks WHERE city = ? LIMIT 1", (user["city"],))
    if row:
        return row
    return db.query_one("SELECT * FROM parks ORDER BY sort_order LIMIT 1")


def _current_scenario(user_id: int, park_id: int) -> dict | None:
    row = db.query_one(
        "SELECT s.* FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
        "WHERE pr.user_id = ? AND s.park_id = ? AND pr.status = 'ongoing' "
        "ORDER BY pr.updated_at DESC LIMIT 1", (user_id, park_id))
    if row:
        return row
    return db.query_one(
        "SELECT * FROM scenarios WHERE park_id = ? AND status = 'online' "
        "ORDER BY id LIMIT 1", (park_id,))


def _user_brief(u: dict) -> dict:
    level, name = level_of(u["growth_total"])
    return {
        "id": u["id"], "nickname": u["nickname"], "family_name": u["family_name"],
        "avatar": u["avatar"], "city": u["city"], "level": level, "level_name": name,
        "growth_total": u["growth_total"], "travel_days": u["travel_days"],
        "age_band": u["age_band"], "age_label": AGE_BANDS.get(u["age_band"] or "", ""),
    }


# ---------------------------------------------------------------- 1. 开箱激活
class ActivateReq(BaseModel):
    code: str = Field(..., description="潮玩底部激活码")
    nickname: str = Field("阿游", max_length=8, description="孩子给伙伴取的名字")
    family_name: str | None = None


@router.post("/activate", summary="开箱激活潮玩")
def activate(req: ActivateReq):
    code = (req.code or "").strip().upper()
    row = db.query_one(
        "SELECT ac.*, s.name AS sku_name, s.city AS sku_city, s.park_id, s.emoji "
        "FROM activation_codes ac LEFT JOIN skus s ON s.id = ac.sku_id WHERE ac.code = ?",
        (code,))
    if not row:
        raise HTTPException(status_code=404, detail="激活码不存在或已被使用")
    if row["used"] and not row["user_id"]:
        raise HTTPException(status_code=409, detail="激活码不存在或已被使用")

    nickname = (req.nickname or "阿游").strip() or "阿游"
    now = db.now_text()

    if row["user_id"]:
        # 已激活过的码：更新伙伴名字，直接返回（方便反复演示）
        uid = row["user_id"]
        db.update("devices", {"nickname": nickname}, "code = ?", (code,))
    else:
        family = req.family_name or f"小小探险家 · 新朋友"
        uid = db.insert("users", {
            "nickname": "小小探险家", "family_name": family, "avatar": "🧭",
            "city": row["sku_city"] or "西安", "level": 1, "growth_total": 0,
            "travel_days": 1, "age_band": "8-12",
            "created_at": now, "last_active": now,
        })
        for dim in ("explore", "create", "observe", "knowledge", "courage"):
            db.insert("user_growth", {"user_id": uid, "dim": dim, "value": 0})
        db.insert("devices", {
            "code": code, "sku_id": row["sku_id"], "user_id": uid, "nickname": nickname,
            "outfit": None, "status": "activated", "online": 1, "activated_at": now,
        })
        db.update("activation_codes", {"used": 1, "user_id": uid, "used_at": now},
                  "code = ?", (code,))
        db.update("skus", {"activated": int(db.scalar(
            "SELECT activated FROM skus WHERE id = ?", (row["sku_id"],))) + 1},
            "id = ?", (row["sku_id"],))
        db.insert("events", {"type": "device", "title": f"新增激活潮玩 1 台（{code}）",
                             "detail": f"{row['sku_name']} · 取名「{nickname}」",
                             "park_id": row["park_id"], "created_at": now})

    user = db.query_one("SELECT * FROM users WHERE id = ?", (uid,))
    device = _device_of(uid)
    return {
        "ok": True,
        "user": _user_brief(user),
        "device": {
            "id": device["id"] if device else None, "code": code, "nickname": nickname,
            "sku_name": device["sku_name"] if device else None,
            "city": device["sku_city"] if device else None,
            "status": device["status"] if device else "activated",
            "emoji": device["sku_emoji"] if device else "🧭",
        },
        "greeting": "你愿意带我一起去看看这个世界吗？",
    }


# ---------------------------------------------------------------- 2. 旅伴首页
@router.get("/home", summary="旅伴首页")
def home(user_id: int = Query(...), lat: float | None = None, lng: float | None = None):
    user = _user_or_404(user_id)
    device = _device_of(user_id)
    park = _park_for(user)
    scenario = _current_scenario(user_id, park["id"]) if park else None

    # 定位信息
    if lat is None or lng is None:
        lat = (park["lat"] if park else 34.2186) + DEMO_OFFSET[0]
        lng = (park["lng"] if park else 108.9644) + DEMO_OFFSET[1]

    location = {
        "park_id": park["id"] if park else None,
        "name": park["name"] if park else "未定位",
        "city": park["city"] if park else "",
        "weather": park["weather"] if park else "",
        "tip": park["tip"] if park else "",
        "lat": park["lat"] if park else None,
        "lng": park["lng"] if park else None,
    }

    # 附近的故事点 + 今日冒险
    nearby_nodes: list[dict] = []
    today = None
    if park and scenario:
        nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx",
                         (scenario["id"],))
        states = story.node_status_chain(user_id, scenario["id"])
        cur = story.current_node(user_id, scenario["id"])
        cur_id = cur["id"] if cur else None
        avail = story.available_nodes(user_id, scenario["id"])
        avail_ids = {n["id"] for n in avail}

        # 「附近的故事点」= 当前可达节点（前置已完成），当前节点优先
        for n in sorted(avail, key=lambda x: (x["id"] != cur_id, x["idx"])):
            d = int(round(geo.haversine(park["lat"], park["lng"], n["lat"], n["lng"]))) \
                if n["lat"] and park["lat"] else 0
            task_title = (db.query_one(
                "SELECT title FROM tasks WHERE node_id = ? AND enabled = 1 LIMIT 1",
                (n["id"],)) or {}).get("title")
            nearby_nodes.append({
                "node_id": n["id"],
                "name": f"{n['place'] or ''} · {n['name']}".strip(" ·"),
                "kind": n["kind"], "kind_label": node_kind_label(n["kind"]),
                "desc": task_title or (n.get("story_text") or "")[:24],
                "distance_m": d, "distance_text": geo.distance_text(d),
                "emoji": park["emoji"], "status": states.get(n["id"], "active"),
                "available": True, "locked_reason": None,
                "is_current": n["id"] == cur_id,
            })
        # 补一个「还需先完成」的节点，让进度目标可见
        for n in nodes:
            if n["id"] in avail_ids or states.get(n["id"]) == "done":
                continue
            reason = story.locked_reason(user_id, n)
            if not reason or reason == "已完成":
                continue
            d = int(round(geo.haversine(park["lat"], park["lng"], n["lat"], n["lng"]))) \
                if n["lat"] and park["lat"] else 0
            nearby_nodes.append({
                "node_id": n["id"],
                "name": f"{n['place'] or ''} · {n['name']}".strip(" ·"),
                "kind": n["kind"], "kind_label": node_kind_label(n["kind"]),
                "desc": reason, "distance_m": d, "distance_text": geo.distance_text(d),
                "emoji": park["emoji"], "status": "locked",
                "available": False, "locked_reason": reason, "is_current": False,
            })
            break
        nearby_nodes = nearby_nodes[:4]

        total = len(nodes)
        visited = len([1 for n in nodes if states.get(n["id"]) != "locked"])
        chapter_title = ""
        if cur and cur.get("chapter_id"):
            row = db.query_one("SELECT idx, title FROM chapters WHERE id = ?",
                               (cur["chapter_id"],))
            if row:
                chapter_title = row["title"]
                chapter_idx = row["idx"]
            else:
                chapter_idx = 1
        else:
            chapter_idx = 1
        today = {
            "scenario_id": scenario["id"], "title": scenario["title"],
            "chapter_idx": chapter_idx, "chapter_title": chapter_title,
            "node_id": (cur or {}).get("id"),
            "node_name": (cur or {}).get("name"),
            # 节点所在地点（如「大雁塔」）。前端展示「第 N 章 · 章节名 · 地点」，
            # 因为章节名与节点名可能同名（第 3 章「密令现世」= 节点「密令现世」）。
            "node_place": (cur or {}).get("place"),
            "done_nodes": visited, "total_nodes": total,
            "percent": clamp_percent(visited * 100 / total) if total else 0,
        }

    badge_got = int(db.scalar("SELECT COUNT(*) FROM user_badges WHERE user_id = ?", (user_id,)))
    badge_total = int(db.scalar("SELECT COUNT(*) FROM badges"))
    pending = len(nearby_nodes)
    city = park["city"] if park else user["city"]

    return {
        "user": _user_brief(user),
        "device": {
            "id": device["id"] if device else None,
            "nickname": (device or {}).get("nickname") or "阿游",
            "city": (device or {}).get("sku_city") or city,
            "sku_name": (device or {}).get("sku_name"),
            "emoji": (device or {}).get("sku_emoji") or "🧭",
            "outfit": (device or {}).get("outfit") or "基础装扮",
            "outfit_count": int(db.scalar(
                "SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id = ui.item_id "
                "WHERE ui.user_id = ? AND w.type = 'outfit'", (user_id,))),
            "gear_count": int(db.scalar(
                "SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id = ui.item_id "
                "WHERE ui.user_id = ? AND w.type = 'gear'", (user_id,))),
        },
        "location": location,
        "speech": f"嗨！我是{(device or {}).get('nickname') or '阿游'} 👋 今天我们去哪儿冒险？",
        "status_pill": f"正在{city}等你 · 附近有 {pending} 个故事待开启",
        "today_adventure": today,
        "quick_actions": [
            {"key": "chat", "label": "AI对话"}, {"key": "task", "label": "任务"},
            {"key": "badge", "label": "徽章"}, {"key": "dress", "label": "换装"},
        ],
        "nearby_nodes": nearby_nodes,
        "badge_count": badge_got,
        "badge_total": badge_total,
    }


# ---------------------------------------------------------------- 3. 探索 · 故事地图
@router.get("/explore", summary="探索 · 我的故事地图")
def explore(user_id: int = Query(...)):
    user = _user_or_404(user_id)
    parks = db.query("SELECT * FROM parks ORDER BY sort_order")

    lit = int(db.scalar("SELECT COUNT(*) FROM parks WHERE lit = 1"))
    total_cities = len(parks)
    badges = int(db.scalar("SELECT COUNT(*) FROM user_badges WHERE user_id = ?", (user_id,)))
    stories_done = int(db.scalar(
        "SELECT COUNT(*) FROM progress WHERE user_id = ? AND status = 'done'", (user_id,)))

    # 地图节点
    nodes = []
    for p in parks:
        sc = db.query_one(
            "SELECT * FROM scenarios WHERE park_id = ? ORDER BY id LIMIT 1", (p["id"],))
        prog = None
        if sc:
            prog = db.query_one(
                "SELECT * FROM progress WHERE user_id = ? AND scenario_id = ?",
                (user_id, sc["id"]))
        if prog and prog["status"] == "done":
            state = "done"
        elif prog:
            state = "ongoing"
        elif p["lit"]:
            state = "done"
        else:
            state = "locked"
        label = {"done": "✓ 已点亮", "ongoing": "▶ 探索中", "locked": "🔒 未解锁"}[state]
        nodes.append({
            "park_id": p["id"], "city": p["city"], "scenario": sc["title"] if sc else "",
            "scenario_id": sc["id"] if sc else None, "emoji": p["emoji"],
            "state": state, "x": p["map_x"], "y": p["map_y"],
            "tooltip": f"{p['city']} · {sc['title'] if sc else p['name']} {label}",
            "label": label,
        })

    # 城市故事卡片
    cities = []
    for p in parks:
        sc = db.query_one(
            "SELECT * FROM scenarios WHERE park_id = ? AND status != 'draft' "
            "ORDER BY CASE status WHEN 'online' THEN 0 ELSE 1 END, id LIMIT 1", (p["id"],))
        if not sc:
            continue
        prog = db.query_one(
            "SELECT * FROM progress WHERE user_id = ? AND scenario_id = ?",
            (user_id, sc["id"]))
        if prog and prog["status"] == "done":
            state, state_label = "done", "已完成"
        elif prog:
            state, state_label = "ongoing", "探索中"
        else:
            state, state_label = "locked", "未解锁"
        cities.append({
            "scenario_id": sc["id"], "park_id": p["id"], "city": p["city"],
            "title": sc["title"], "emoji": sc["emoji"], "tagline": sc["subtitle"],
            "state": state, "state_label": state_label,
            "progress_percent": int(prog["percent"]) if prog else 0,
            "age_band": sc["age_band"], "age_label": AGE_BANDS.get(sc["age_band"], ""),
        })
    # 探索中的排前面
    order = {"ongoing": 0, "done": 1, "locked": 2}
    cities.sort(key=lambda c: (order[c["state"]], c["scenario_id"]))

    return {
        "user": _user_brief(user),
        "stats": {"lit_cities": lit, "total_cities": total_cities,
                  "badges": badges, "stories_done": stories_done},
        "nodes": nodes,
        "cities": cities,
    }


# ---------------------------------------------------------------- 4. AI 对话
class ChatReq(BaseModel):
    user_id: int
    text: str = ""
    lat: float | None = None
    lng: float | None = None
    history: list[dict] | None = None


@router.post("/chat", summary="与阿游对话")
def chat(req: ChatReq):
    user = _user_or_404(req.user_id)
    device = _device_of(req.user_id)
    result = chat_engine.reply(user, device, req.text, req.lat, req.lng, req.history)
    db.update_by_id("users", req.user_id, {"last_active": db.now_text()})
    return result


# ---------------------------------------------------------------- 5. 剧本详情
@router.get("/scenario/{scenario_id}", summary="剧本详情")
def scenario(scenario_id: int, user_id: int | None = None):
    detail = story.scenario_detail(user_id, scenario_id)
    if not detail:
        raise HTTPException(status_code=404, detail="剧本不存在")
    detail["age_label"] = AGE_BANDS.get(detail["age_band"], "")
    return detail


# ---------------------------------------------------------------- 6. 位置触发
class LocateReq(BaseModel):
    user_id: int
    lat: float
    lng: float


@router.post("/locate", summary="位置上报与剧情触发")
def locate(req: LocateReq):
    user = _user_or_404(req.user_id)
    parks = db.query("SELECT * FROM parks")
    park = geo.find_park(parks, req.lat, req.lng)

    triggered_out: list[dict] = []
    nearby_out: list[dict] = []
    locked_out: list[dict] = []

    if park:
        sids = [r["id"] for r in db.query(
            "SELECT id FROM scenarios WHERE park_id = ?", (park["id"],))]

        # 1) 可达节点（前置节点已完成）→ 参与地理围栏判定
        candidates: list[dict] = []
        for sid in sids:
            candidates += story.available_nodes(req.user_id, sid)
        trig, near = geo.locate_nodes(candidates, req.lat, req.lng)

        for n in trig:
            first = growth.ensure_visit(req.user_id, n["id"], n["scenario_id"], "gps")
            task_row = db.query_one(
                "SELECT * FROM tasks WHERE node_id = ? AND enabled = 1 ORDER BY id LIMIT 1",
                (n["id"],))
            task = None
            if task_row:
                task = {"id": task_row["id"], "title": task_row["title"],
                        "type": task_row["type"],
                        "type_label": task_type_label(task_row["type"]),
                        "verify_mode": task_row["verify_mode"],
                        "target_count": task_row["target_count"]}
            triggered_out.append({
                "node_id": n["id"], "scenario_id": n["scenario_id"], "name": n["name"],
                "kind": n["kind"], "kind_label": node_kind_label(n["kind"]),
                "place": n["place"], "age_band": n["age_band"],
                "distance_m": n["distance_m"], "distance_text": n["distance_text"],
                "story_text": n["story_text"], "ai_dialog": n["ai_dialog"],
                "hint": n["hint"], "first_visit": first, "task": task,
            })
            if first:
                db.insert("events", {
                    "type": "node",
                    "title": f"{user['nickname']} 到达了「{n['name']}」",
                    "detail": f"{park['name']} · 距离 {n['distance_m']}m",
                    "park_id": park["id"], "created_at": db.now_text(),
                })

        # 2) 附近（可达但还不在围栏内）
        for n in near:
            nearby_out.append({
                "node_id": n["id"], "name": n["name"], "kind": n["kind"],
                "distance_m": n["distance_m"], "distance_text": n["distance_text"],
            })
        nearby_out = nearby_out[:6]

        # 3) 已到访但前置未完成 / 顺序未解锁的节点 → 给出「为什么还不能触发」
        cur_ids = {n["id"] for n in candidates}
        for sid in sids:
            for n in db.query(
                    "SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (sid,)):
                if n["id"] in cur_ids or growth.node_is_done(req.user_id, n["id"]):
                    continue
                reason = story.locked_reason(req.user_id, n)
                if reason and reason != "已完成":
                    d = int(round(geo.haversine(req.lat, req.lng, n["lat"], n["lng"]))) \
                        if n["lat"] else 0
                    locked_out.append({"node_id": n["id"], "name": n["name"],
                                       "reason": reason, "distance_m": d})
        locked_out = locked_out[:3]

    return {
        "park": {"id": park["id"], "name": park["name"], "city": park["city"]} if park else None,
        "located": park is not None,
        "triggered": triggered_out,
        "nearby": nearby_out,
        "locked": locked_out,
        "tip": None if park else "还没有进入任何景区，走到景点附近就会自动触发故事～",
    }


# ---------------------------------------------------------------- 7. 任务详情
@router.get("/task/{task_id}", summary="任务详情")
def task_detail(task_id: int, user_id: int | None = None):
    t = db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    node = db.query_one("SELECT * FROM nodes WHERE id = ?", (t["node_id"],)) or {}
    scenario = db.query_one("SELECT * FROM scenarios WHERE id = ?", (t["scenario_id"],)) or {}
    prog = story.task_progress(user_id, t)
    reward = db.json_loads(t["reward_growth"], {}) or {}
    badge = None
    if t["reward_badge_id"]:
        b = db.query_one("SELECT * FROM badges WHERE id = ?", (t["reward_badge_id"],))
        if b:
            badge = {"id": b["id"], "name": b["name"], "emoji": b["emoji"], "desc": b["desc"]}

    return {
        "id": t["id"], "title": t["title"], "type": t["type"],
        "type_label": task_type_label(t["type"]), "desc": t["desc"],
        "age_band": t["age_band"], "age_label": AGE_BANDS.get(t["age_band"], ""),
        "verify_mode": t["verify_mode"], "hint": t["hint"],
        "target_count": prog["total"], "done_count": prog["done"],
        "complete": prog["complete"],
        "options": db.json_loads(t["options"]),
        "answer_hint": _answer_hint(t),
        "node": {
            "id": node.get("id"), "name": node.get("name"), "kind": node.get("kind"),
            "kind_label": node_kind_label(node.get("kind") or "main"),
            "place": node.get("place"), "story_text": node.get("story_text"),
            "ai_dialog": node.get("ai_dialog"), "lat": node.get("lat"), "lng": node.get("lng"),
            "radius_m": node.get("radius_m"),
        },
        "scenario": {"id": scenario.get("id"), "title": scenario.get("title"),
                     "emoji": scenario.get("emoji")},
        "reward_preview": {"growth": reward, "badge": badge},
    }


def _answer_hint(t: dict) -> str | None:
    """给前端的作答提示（不直接暴露答案）。"""
    mode = t.get("verify_mode")
    if mode == "photo":
        return "拍一张照片作为证据"
    if mode == "auto":
        return "到达后即可完成"
    target = int(t.get("target_count") or 1)
    if target > 1:
        return f"需要找到 {target} 个不同的答案"
    return "填入你的答案"


# ---------------------------------------------------------------- 8. 提交任务
class SubmitReq(BaseModel):
    user_id: int
    answer: str | None = None
    photo_note: str | None = None
    count: int | None = None


@router.post("/task/{task_id}/submit", summary="提交任务")
def submit_task(task_id: int, req: SubmitReq):
    user = _user_or_404(req.user_id)
    t = db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = growth.submit(req.user_id, t, {"answer": req.answer,
                                           "photo_note": req.photo_note})

    db.update_by_id("users", req.user_id, {"last_active": db.now_text()})
    if result["pass"]:
        node = db.query_one("SELECT name FROM nodes WHERE id = ?", (t["node_id"],)) or {}
        db.insert("events", {
            "type": "reward" if result.get("badge") else "story",
            "title": f"{user['nickname']} 完成了「{t['title']}」",
            "detail": (f"获得徽章「{result['badge']['name']}」 · {node.get('name', '')}"
                       if result.get("badge") else
                       f"成长值 +{sum((result.get('growth_gain') or {}).values())} · "
                       f"{node.get('name', '')}"),
            "park_id": (db.query_one(
                "SELECT park_id FROM scenarios WHERE id = ?", (t["scenario_id"],)) or {}
            ).get("park_id") if t["scenario_id"] else None,
            "created_at": db.now_text(),
        })

    result["ok"] = True
    return result


# ---------------------------------------------------------------- 9. 我的
@router.get("/mine", summary="我的")
def mine(user_id: int = Query(...)):
    user = _user_or_404(user_id)
    values = growth.get_growth(user_id)
    gap = next_level_gap(user["growth_total"])

    badges = []
    for b in db.query("SELECT * FROM badges ORDER BY sort_order, id"):
        got = db.query_one("SELECT 1 FROM user_badges WHERE user_id = ? AND badge_id = ?",
                           (user_id, b["id"]))
        badges.append({"id": b["id"], "name": b["name"], "emoji": b["emoji"],
                       "city": b["city"], "rarity": b["rarity"],
                       "rarity_label": RARITY_LABELS.get(b["rarity"] or "", b["rarity"] or ""),
                       "desc": b["desc"], "got": got is not None})
    got_count = len([b for b in badges if b["got"]])

    device = _device_of(user_id)
    # 走过的城市 = 有过进度的剧本所属景区去重计数（原型「走过 5 座城市」）
    cities = int(db.scalar(
        "SELECT COUNT(DISTINCT s.park_id) FROM progress pr "
        "JOIN scenarios s ON s.id = pr.scenario_id WHERE pr.user_id = ?", (user_id,)))
    fav = int(db.scalar("SELECT COUNT(*) FROM user_badges WHERE user_id = ?", (user_id,))) \
        + int(db.scalar("SELECT COUNT(*) FROM user_items WHERE user_id = ?", (user_id,)))

    return {
        "user": {**_user_brief(user), "cities": cities},
        "next_level": gap,
        "growth": [{"dim": d, "label": l, "value": v}
                   for (d, l), v in zip(
                       [("explore", "探索"), ("create", "创造"), ("observe", "观察"),
                        ("knowledge", "知识"), ("courage", "勇气")],
                       [values["explore"], values["create"], values["observe"],
                        values["knowledge"], values["courage"]])],
        "badges": badges,
        "badge_stat": {"got": got_count, "total": len(badges)},
        "toy": {
            "device_id": (device or {}).get("id"),
            "nickname": (device or {}).get("nickname") or "阿游",
            "sku_name": (device or {}).get("sku_name"),
            "emoji": (device or {}).get("sku_emoji") or "🧭",
            "outfit": (device or {}).get("outfit") or "基础装扮",
            "outfits": int(db.scalar(
                "SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id = ui.item_id "
                "WHERE ui.user_id = ? AND w.type = 'outfit'", (user_id,))),
            "gear": int(db.scalar(
                "SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id = ui.item_id "
                "WHERE ui.user_id = ? AND w.type = 'gear'", (user_id,))),
        },
        "entries": [
            {"key": "map", "label": "我的旅行地图", "value": f"{cities} 座城市"},
            {"key": "fav", "label": "我的收藏", "value": f"{fav} 件"},
            {"key": "honor", "label": "成就与称号", "value": f"Lv.{gap['level']}"},
            {"key": "settings", "label": "设置", "value": ""},
        ],
    }


# ---------------------------------------------------------------- 10. 换装
@router.get("/wardrobe", summary="我的潮玩 · 换装")
def wardrobe(user_id: int = Query(...)):
    _user_or_404(user_id)
    device = _device_of(user_id)
    owned = {r["item_id"] for r in db.query(
        "SELECT item_id FROM user_items WHERE user_id = ?", (user_id,))}
    items, gear = [], []
    for w in db.query("SELECT * FROM wardrobe_items ORDER BY sort_order, id"):
        row = {"id": w["id"], "name": w["name"], "city": w["city"], "emoji": w["emoji"],
               "type": w["type"], "desc": w["desc"], "owned": w["id"] in owned,
               "unlocked": w["id"] in owned,
               "current": (device or {}).get("outfit") == w["name"]}
        (items if w["type"] == "outfit" else gear).append(row)
    return {"current": (device or {}).get("outfit") or "基础装扮",
            "items": items, "gear": gear}


class EquipReq(BaseModel):
    user_id: int
    item_id: int


@router.post("/wardrobe/equip", summary="装备换装")
def equip(req: EquipReq):
    _user_or_404(req.user_id)
    item = db.query_one("SELECT * FROM wardrobe_items WHERE id = ?", (req.item_id,))
    if not item:
        raise HTTPException(status_code=404, detail="装扮不存在")
    owned = db.query_one("SELECT 1 FROM user_items WHERE user_id = ? AND item_id = ?",
                         (req.user_id, req.item_id))
    if not owned:
        # 演示友好：未拥有的装扮自动解锁
        db.insert("user_items", {"user_id": req.user_id, "item_id": req.item_id,
                                 "got_at": db.now_text()})
    if item["type"] == "outfit":
        db.update("devices", {"outfit": item["name"]}, "user_id = ?", (req.user_id,))
    return {"ok": True, "current": item["name"], "type": item["type"],
            "unlocked_now": owned is None}


# ---------------------------------------------------------------- 11. 会话恢复
@router.get("/session", summary="恢复会话")
def session(user_id: int = Query(...)):
    """前端刷新后校验 user_id 是否仍然有效。"""
    user = _user_or_404(user_id)
    device = _device_of(user_id)
    return {"ok": True, "user": _user_brief(user),
            "device": {"id": (device or {}).get("id"),
                       "nickname": (device or {}).get("nickname") or "阿游",
                       "city": (device or {}).get("sku_city"),
                       "sku_name": (device or {}).get("sku_name")}}


@router.get("/demo", summary="演示账号")
def demo_user():
    """返回可用于演示的账号与激活码，方便前端一键登录。"""
    u = db.query_one("SELECT * FROM users ORDER BY id LIMIT 1")
    codes = db.query("SELECT code, used FROM activation_codes ORDER BY id")
    return {
        "user": _user_brief(u) if u else None,
        "codes": [{"code": c["code"], "used": bool(c["used"])} for c in codes],
        "tip": "首次演示请先使用未使用的激活码完成「开箱激活」流程。",
    }


# ---------------------------------------------------------------- 12. 家长模式
# 商业计划书把家长列为三大用户之一（「希望旅行有内容，但缺少好的亲子体验工具」），
# 两个原型都没有覆盖家长视角，这里补齐「成长报告」。

@router.get("/parent/summary", summary="家长模式 · 家庭成长概览")
def parent_summary(user_id: int = Query(...)):
    try:
        return parent.family_summary(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/parent/reports", summary="家长模式 · 可查看的旅行报告列表")
def parent_reports(user_id: int = Query(...)):
    _user_or_404(user_id)
    return {"items": parent.scenario_reports(user_id)}


@router.get("/parent/report", summary="家长模式 · 单次旅行报告")
def parent_report(user_id: int = Query(...), scenario_id: int = Query(...)):
    _user_or_404(user_id)
    try:
        return parent.trip_report(user_id, scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
