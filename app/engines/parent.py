"""游伴 AI · 家长模式引擎。

商业计划书里家长是三大用户之一：
「想让孩子玩得开心，也希望旅行有内容，但缺少好的亲子体验工具。」
两个原型都没有覆盖家长视角，这里补齐两块内容：

1. 家庭成长概览（`family_summary`）—— 看得见的成长：走过的城市、完成的剧本、
   五维成长、近期徽章、近 7 天活跃度，以及**基于真实数据生成的亲子共玩建议**。
2. 单次旅行报告（`trip_report`）—— 一次旅行的完整复盘：剧情时间轴、完成的任务、
   这次真正接触到的**知识点**（从景区素材库反查），以及**回家路上可以问孩子的 3 个问题**。

设计原则：全部由数据库中的真实记录推导，不编造数字。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from .. import db
from ..config import AGE_BANDS, GROWTH_DIMS, MATERIAL_CATEGORIES, RARITY_LABELS
from ..utils import level_of, next_level_gap, short_time
from . import growth, story

CATEGORY_LABEL = {k: label for k, label, _e in MATERIAL_CATEGORIES}


def place_label(city: str | None, park_name: str | None) -> str:
    """给前端一个「可直接渲染、不会重复」的地点标签。

    `park_name` 本身就是「西安 · 大唐不夜城」，如果再拼上 `city`（西安）
    就会渲染成「西安 · 西安 · 大唐不夜城」。这里统一收敛成一个字段。
    """
    city = (city or "").strip()
    park_name = (park_name or "").strip()
    if not park_name:
        return city
    if not city or city in park_name:
        return park_name
    return f"{city} · {park_name}"


def rarity_label(rarity: str | None) -> str:
    return RARITY_LABELS.get(rarity or "", rarity or "")

# 五维度对应的「可以怎么陪孩子玩」建议
DIM_ADVICE = {
    "explore": "多带孩子走没走过的小路、逛没进过的展馆，让「去发现」变成习惯。",
    "create": "鼓励孩子把旅途中看到的东西画下来、讲出来，或者自己编一个后续剧情。",
    "observe": "和孩子玩「三分钟找不同」：在同一处景物前，各自说出三个别人没注意到的细节。",
    "knowledge": "回家后一起查一个今天遇到的「为什么」，把答案讲给家里人听。",
    "courage": "把选择权交给孩子：今天走哪条路、进哪个馆，让他自己做决定并承担结果。",
}


# ---------------------------------------------------------------- 家庭概览
def family_summary(user_id: int) -> dict:
    user = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise ValueError("用户不存在")

    device = db.query_one(
        "SELECT d.*, s.name AS sku_name FROM devices d LEFT JOIN skus s ON s.id = d.sku_id "
        "WHERE d.user_id = ? ORDER BY d.id LIMIT 1", (user_id,))
    level, level_name = level_of(user["growth_total"])
    dims = growth.get_growth(user_id)

    # ---------- 概览数字（全部实测） ----------
    total_parks = int(db.scalar("SELECT COUNT(*) FROM parks"))
    total_scenarios = int(db.scalar("SELECT COUNT(*) FROM scenarios WHERE status != 'draft'"))
    total_nodes = int(db.scalar("SELECT COUNT(*) FROM nodes"))
    total_badges = int(db.scalar("SELECT COUNT(*) FROM badges"))

    cities = int(db.scalar(
        "SELECT COUNT(DISTINCT s.park_id) FROM progress pr "
        "JOIN scenarios s ON s.id = pr.scenario_id WHERE pr.user_id = ?", (user_id,)))
    stories_done = int(db.scalar(
        "SELECT COUNT(*) FROM progress WHERE user_id = ? AND status = 'done'", (user_id,)))
    nodes_visited = int(db.scalar(
        "SELECT COUNT(*) FROM node_visits WHERE user_id = ?", (user_id,)))
    tasks_done = int(db.scalar(
        "SELECT COUNT(DISTINCT task_id) FROM task_submissions "
        "WHERE user_id = ? AND passed = 1", (user_id,)))
    badges_got = int(db.scalar(
        "SELECT COUNT(*) FROM user_badges WHERE user_id = ?", (user_id,)))

    # 累计游玩时长：按「每个已完成任务的平均时长」估算（数据来自 tasks.avg_minutes）
    minutes = int(db.scalar(
        "SELECT COALESCE(SUM(t.avg_minutes), 0) FROM ("
        "  SELECT DISTINCT ts.task_id FROM task_submissions ts "
        "  WHERE ts.user_id = ? AND ts.passed = 1) x "
        "JOIN tasks t ON t.id = x.task_id", (user_id,))) or 12 * tasks_done

    overview = [
        {"key": "cities", "label": "走过的城市", "value": cities, "unit": "座", "of": total_parks},
        {"key": "stories", "label": "完成的剧本", "value": stories_done, "unit": "个",
         "of": total_scenarios},
        {"key": "nodes", "label": "探索的剧情点", "value": nodes_visited, "unit": "个",
         "of": total_nodes},
        {"key": "tasks", "label": "完成的任务", "value": tasks_done, "unit": "个", "of": None},
        {"key": "badges", "label": "获得的徽章", "value": badges_got, "unit": "枚",
         "of": total_badges},
        {"key": "minutes", "label": "累计探索时长", "value": minutes, "unit": "分钟", "of": None},
    ]

    # ---------- 近 7 天活跃度 ----------
    weekly = _weekly_activity(user_id)

    # ---------- 近期获得的徽章 ----------
    recent_badges = db.query(
        "SELECT b.id, b.name, b.emoji, b.desc, b.rarity, ub.got_at FROM user_badges ub "
        "JOIN badges b ON b.id = ub.badge_id WHERE ub.user_id = ? "
        "ORDER BY ub.got_at DESC, ub.badge_id DESC LIMIT 6", (user_id,))
    badges_recent = [{"id": b["id"], "name": b["name"], "emoji": b["emoji"],
                      "desc": b["desc"], "rarity": b["rarity"],
                      "rarity_label": rarity_label(b["rarity"]),
                      "got_at": short_time(b["got_at"])} for b in recent_badges]

    # ---------- 进行中的剧本 ----------
    ongoing = db.query(
        "SELECT pr.scenario_id, pr.percent, pr.chapter_idx, pr.status, pr.updated_at, "
        "s.title, s.emoji, p.city, p.name AS park_name FROM progress pr "
        "JOIN scenarios s ON s.id = pr.scenario_id LEFT JOIN parks p ON p.id = s.park_id "
        "WHERE pr.user_id = ? ORDER BY pr.updated_at DESC", (user_id,))
    ongoing_list = [{
        "scenario_id": r["scenario_id"], "title": r["title"], "emoji": r["emoji"],
        "city": r["city"], "park_name": r["park_name"],
        "place_label": place_label(r["city"], r["park_name"]),
        "percent": r["percent"],
        "status": r["status"], "status_label": "已完成" if r["status"] == "done" else "进行中",
        "updated_at": short_time(r["updated_at"]),
    } for r in ongoing]

    # ---------- 亲子共玩建议（规则生成，基于真实短板） ----------
    weakest = sorted(dims.items(), key=lambda kv: kv[1])[:2]
    label_of = {k: v for k, v in GROWTH_DIMS}
    suggestions = []
    for dim, val in weakest:
        suggestions.append({
            "dim": dim, "label": label_of.get(dim, dim), "value": val,
            "title": f"「{label_of.get(dim, dim)}」还有提升空间",
            "advice": DIM_ADVICE.get(dim, "多陪孩子做这件事，会看到变化。"),
        })
    # 未点亮的城市 → 下一站建议
    nxt = db.query_one(
        "SELECT p.city, p.name, s.title FROM parks p "
        "LEFT JOIN scenarios s ON s.park_id = p.id AND s.status != 'draft' "
        "WHERE p.lit = 0 AND s.id IS NOT NULL ORDER BY p.sort_order LIMIT 1")
    if nxt:
        suggestions.append({
            "dim": "explore", "label": "探索", "value": dims.get("explore", 0),
            "title": f"下一站可以去{nxt['city']}",
            "advice": f"《{nxt['title']}》的剧本已经准备好了，走到{nxt['name']}就会自动开启。",
        })
    # 未获得的徽章中，挑一枚「当前就能去拿」的（对应剧本已上线）
    locked = db.query_one(
        "SELECT b.name, b.emoji, b.desc FROM badges b "
        "JOIN scenarios s ON s.id = b.scenario_id AND s.status = 'online' "
        "WHERE b.id NOT IN (SELECT badge_id FROM user_badges WHERE user_id = ?) "
        "ORDER BY b.sort_order LIMIT 1", (user_id,))
    if locked:
        suggestions.append({
            "dim": "courage", "label": "勇气", "value": dims.get("courage", 0),
            "title": f"再完成一个剧本就能拿到「{locked['name']}」",
            "advice": locked["desc"] or "完成对应剧本即可解锁。",
        })

    return {
        "child": {
            "id": user["id"], "nickname": user["nickname"],
            "family_name": user["family_name"], "avatar": user["avatar"],
            "level": level, "level_name": level_name,
            "growth_total": user["growth_total"],
            "age_band": user["age_band"],
            "age_label": AGE_BANDS.get(user["age_band"] or "", ""),
            "travel_days": user["travel_days"],
        },
        "device": {
            "nickname": (device or {}).get("nickname") or "阿游",
            "sku_name": (device or {}).get("sku_name"),
            "outfit": (device or {}).get("outfit"),
        },
        "next_level": next_level_gap(user["growth_total"]),
        "overview": overview,
        "growth": [{"dim": d, "label": l, "value": int(dims.get(d, 0))} for d, l in GROWTH_DIMS],
        "growth_note": _growth_note(dims),
        "weekly": weekly,
        "badges_recent": badges_recent,
        "scenarios": ongoing_list,
        "suggestions": suggestions[:4],
    }


def _weekly_activity(user_id: int) -> dict:
    """近 7 天每天通过的任务数（真实统计）。"""
    today = datetime.now().date()
    days, values, labels = [], [], []
    cn = ["一", "二", "三", "四", "五", "六", "日"]
    rows = db.query(
        "SELECT substr(submitted_at, 1, 10) AS d, COUNT(*) AS c FROM task_submissions "
        "WHERE user_id = ? AND passed = 1 GROUP BY d", (user_id,))
    by_day = {r["d"]: r["c"] for r in rows}
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        days.append(key[5:])
        labels.append("周" + cn[day.weekday()])
        values.append(int(by_day.get(key, 0)))
    return {"days": days, "labels": labels, "values": values,
            "total": sum(values), "peak": max(values) if values else 0}


def _growth_note(dims: dict) -> str:
    """一句话解读五维画像。全为 0 时说明还没开始，不给无意义的「均衡」结论。"""
    label_of = {k: v for k, v in GROWTH_DIMS}
    if not dims or max(dims.values(), default=0) <= 0:
        return "孩子还没有开始探索，五维成长数据会在第一次完成任务后出现。"
    top = max(dims.items(), key=lambda kv: kv[1])
    low = min(dims.items(), key=lambda kv: kv[1])
    spread = top[1] - low[1]
    if spread <= 5:
        return (f"孩子目前的成长值主要集中在「{label_of.get(top[0], top[0])}」，"
                f"各项还比较平均，多走几次不同主题的景区就会有明显分化。")
    tone = "很均衡" if spread <= 15 else ("偏向明显" if spread >= 30 else "比较自然")
    return (f"孩子在「{label_of.get(top[0], top[0])}」上表现最突出（{top[1]}），"
            f"「{label_of.get(low[0], low[0])}」相对最少（{low[1]}），整体发展{tone}。")


# ---------------------------------------------------------------- 单次旅行报告
def trip_report(user_id: int, scenario_id: int) -> dict:
    scenario = db.query_one("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    if not scenario:
        raise ValueError("剧本不存在")
    park = db.query_one("SELECT * FROM parks WHERE id = ?", (scenario["park_id"],)) or {}
    detail = story.scenario_detail(user_id, scenario_id)

    nodes = db.query("SELECT * FROM nodes WHERE scenario_id = ? ORDER BY idx", (scenario_id,))
    states = story.node_status_chain(user_id, scenario_id)
    visited_nodes = [n for n in nodes if states.get(n["id"]) != "locked"]
    done_nodes = [n for n in nodes if states.get(n["id"]) == "done"]

    # ---------- 剧情时间轴（到访记录 + 任务提交，按时间排序） ----------
    trail = []
    for v in db.query(
            "SELECT nv.*, n.name, n.place, n.kind FROM node_visits nv "
            "JOIN nodes n ON n.id = nv.node_id WHERE nv.user_id = ? AND nv.scenario_id = ? "
            "ORDER BY nv.visited_at", (user_id, scenario_id)):
        trail.append({
            "at": short_time(v["visited_at"]), "node": f"{v['place'] or ''} · {v['name']}".strip(" ·"),
            "event": "到达剧情点", "kind": v["kind"], "type": "visit",
            "source": v["source"],
        })
    for s in db.query(
            "SELECT ts.*, t.title, t.type FROM task_submissions ts "
            "JOIN tasks t ON t.id = ts.task_id "
            "WHERE ts.user_id = ? AND t.scenario_id = ? "
            "ORDER BY ts.submitted_at", (user_id, scenario_id)):
        trail.append({
            "at": short_time(s["submitted_at"]), "node": s["title"],
            "event": "完成任务" if s["passed"] else "任务未通过",
            "kind": "task", "type": "task", "passed": bool(s["passed"]),
        })
    trail.sort(key=lambda x: x["at"])

    # ---------- 本次旅行累计获得的成长 ----------
    # 注意：task_submissions 表本身没有 scenario_id，必须经 tasks 关联。
    gain_total: dict[str, int] = {}
    for s in db.query(
            "SELECT ts.growth_gain FROM task_submissions ts "
            "JOIN tasks t ON t.id = ts.task_id "
            "WHERE ts.user_id = ? AND t.scenario_id = ? AND ts.passed = 1",
            (user_id, scenario_id)):
        for dim, val in (db.json_loads(s["growth_gain"], {}) or {}).items():
            gain_total[dim] = gain_total.get(dim, 0) + int(val)

    # ---------- 这次真正接触到的知识点（从景区素材库反查） ----------
    knowledge = _knowledge_for(visited_nodes, park.get("id"))

    # ---------- 回家路上可以问孩子的 3 个问题 ----------
    questions = _questions_for(user_id, scenario_id, visited_nodes)

    # ---------- 获得的徽章 ----------
    badges = db.query(
        "SELECT b.id, b.name, b.emoji, b.desc FROM badges b "
        "WHERE b.scenario_id = ? AND b.id IN "
        "(SELECT badge_id FROM user_badges WHERE user_id = ?)", (scenario_id, user_id))

    started = db.query_one(
        "SELECT started_at, updated_at, status, percent, chapter_idx FROM progress "
        "WHERE user_id = ? AND scenario_id = ?", (user_id, scenario_id)) or {}
    tasks_passed = int(db.scalar(
        "SELECT COUNT(DISTINCT ts.task_id) FROM task_submissions ts "
        "JOIN tasks t ON t.id = ts.task_id "
        "WHERE ts.user_id = ? AND t.scenario_id = ? AND ts.passed = 1",
        (user_id, scenario_id)))
    minutes = int(db.scalar(
        "SELECT COALESCE(SUM(t.avg_minutes), 0) FROM ("
        "  SELECT DISTINCT ts.task_id FROM task_submissions ts "
        "  JOIN tasks t2 ON t2.id = ts.task_id "
        "  WHERE ts.user_id = ? AND t2.scenario_id = ? AND ts.passed = 1) x "
        "JOIN tasks t ON t.id = x.task_id", (user_id, scenario_id))) or 12 * tasks_passed

    return {
        "user_id": user_id,
        "scenario": {
            "id": scenario["id"], "title": scenario["title"], "emoji": scenario["emoji"],
            "city": park.get("city"), "park_name": park.get("name"),
            "place_label": place_label(park.get("city"), park.get("name")),
            "age_band": scenario["age_band"],
            "age_label": AGE_BANDS.get(scenario["age_band"] or "", ""),
            "subtitle": scenario["subtitle"], "worldview": scenario["worldview"],
        },
        "summary": {
            "visited": len(visited_nodes), "done": len(done_nodes), "total": len(nodes),
            "percent": detail["progress_percent"] if detail else 0,
            "status": started.get("status", "not_started"),
            "status_label": {"done": "已完成", "ongoing": "进行中",
                             "not_started": "还没开始"}.get(started.get("status", "not_started")),
            "chapters_done": len([c for c in (detail or {}).get("chapters", [])
                                  if c["state"] == "done"]),
            "chapters_total": (detail or {}).get("chapters_count", 0),
            "tasks_done": tasks_passed,
            "minutes": minutes,
            "started_at": short_time(started.get("started_at")),
            "updated_at": short_time(started.get("updated_at")),
        },
        "chapters": [{"idx": c["idx"], "title": c["title"], "summary": c["summary"],
                      "state": c["state"],
                      "nodes": [{"name": n["name"], "place": n["place"], "state": n["state"]}
                                for n in c["nodes"]]}
                     for c in (detail or {}).get("chapters", [])],
        "trail": trail,
        "growth_gain": gain_total,
        "badges": [{"id": b["id"], "name": b["name"], "emoji": b["emoji"], "desc": b["desc"]}
                   for b in badges],
        "knowledge": knowledge,
        "questions": questions,
    }


def _knowledge_for(visited_nodes: list[dict], park_id: int | None) -> list[dict]:
    """从孩子到访过的节点出发，反查该景区素材库，给出「这次接触到的知识点」。"""
    out: list[dict] = []
    seen: set[int] = set()
    for n in visited_nodes:
        place = (n.get("place") or "").strip()
        mat = None
        if place and park_id:
            mat = db.query_one(
                "SELECT * FROM materials WHERE park_id = ? AND status = 'indexed' "
                "AND (title LIKE ? OR tags LIKE ?) ORDER BY LENGTH(content) ASC LIMIT 1",
                (park_id, f"%{place}%", f"%{place}%"))
        if not mat:
            # 退化为按节点文案关键词在素材正文中检索
            kw = _keyword_of(n.get("story_text") or "")
            if kw and park_id:
                mat = db.query_one(
                    "SELECT * FROM materials WHERE park_id = ? AND status = 'indexed' "
                    "AND content LIKE ? ORDER BY LENGTH(content) ASC LIMIT 1",
                    (park_id, f"%{kw}%"))
        if not mat or mat["id"] in seen:
            continue
        seen.add(mat["id"])
        out.append({
            "material_id": mat["id"],
            "title": mat["title"],
            "category": mat["category"],
            "category_label": CATEGORY_LABEL.get(mat["category"], mat["category"]),
            "node": n["name"],
            "place": n.get("place"),
            "point": _first_sentences(mat.get("content") or "", 2, 120),
        })
    return out[:6]


def _keyword_of(text: str) -> str:
    """从节点文案里抽一个 2-4 字的关键词用于素材检索。"""
    m = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    stop = {"阿游", "我们", "什么", "这个", "那个", "为什么", "可以", "一个", "已经", "这里"}
    for w in m:
        if w not in stop:
            return w
    return ""


def _first_sentences(text: str, n: int, limit: int) -> str:
    parts = re.split(r"(?<=[。！？])", text.strip())
    return "".join(parts[:n])[:limit]


def _questions_for(user_id: int, scenario_id: int, visited_nodes: list[dict]) -> list[str]:
    """生成 3 个「回家路上可以问孩子」的问题。

    优先用孩子真实完成过的任务与到访过的节点提问；
    如果这次旅行还没有记录（例如刚开启剧本），则用景区素材库 + 通用开放题补足到 3 个，
    保证家长任何时候打开报告都有话可聊。
    """
    questions: list[str] = []

    # ① 从孩子真实完成过的任务里挑一个
    task = db.query_one(
        "SELECT t.title, t.answer FROM task_submissions ts JOIN tasks t ON t.id = ts.task_id "
        "WHERE ts.user_id = ? AND t.scenario_id = ? AND ts.passed = 1 "
        "ORDER BY ts.submitted_at DESC LIMIT 1", (user_id, scenario_id))
    if task:
        questions.append(f"今天你完成了「{task['title']}」，你还记得答案是什么吗？")

    # ② 从孩子到访过的节点里挑一个
    if visited_nodes:
        node = visited_nodes[-1]
        place = node.get("place") or node["name"]
        questions.append(f"在{place}，你第一眼注意到的是什么？"
                         f"有没有什么是后来才发现的？")

    # ③ 从该剧本所属景区素材库取一条知识点，让孩子复述
    mat = db.query_one(
        "SELECT m.title, m.content FROM materials m JOIN scenarios s ON s.park_id = m.park_id "
        "WHERE s.id = ? AND m.status = 'indexed' ORDER BY LENGTH(m.content) ASC LIMIT 1",
        (scenario_id,))
    if mat:
        questions.append(f"考考你：关于「{mat['title']}」，你能用自己的话讲给爸爸妈妈听吗？")

    # 兜底：补足到 3 个（顺序固定，保证结果稳定）
    fallbacks = [
        "这个故事里，你最喜欢哪一个地方？为什么？",
        "如果让你给这个故事换个结局，你会怎么编？",
        "今天有没有哪件事是你自己想办法解决的？",
        "如果明天再去一次，你最想先去看什么？",
    ]
    for q in fallbacks:
        if len(questions) >= 3:
            break
        if q not in questions:
            questions.append(q)
    return questions[:3]


def scenario_reports(user_id: int) -> list[dict]:
    """家长模式下可查看报告的全部剧本（按最近游玩排序）。"""
    rows = db.query(
        "SELECT pr.scenario_id, pr.percent, pr.status, pr.updated_at, s.title, s.emoji, "
        "p.city FROM progress pr JOIN scenarios s ON s.id = pr.scenario_id "
        "LEFT JOIN parks p ON p.id = s.park_id WHERE pr.user_id = ? "
        "ORDER BY pr.updated_at DESC", (user_id,))
    return [{"scenario_id": r["scenario_id"], "title": r["title"], "emoji": r["emoji"],
             "city": r["city"], "percent": r["percent"],
             "status": r["status"],
             "status_label": "已完成" if r["status"] == "done" else "进行中",
             "updated_at": short_time(r["updated_at"])} for r in rows]
