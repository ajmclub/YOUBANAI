"""游伴 AI · 数据播种。

把 seed_data.py 中的原型数据写入 SQLite，并构造一个与原型完全一致的演示账号状态：
- 小小探险家（王家）：Lv.3 探索家，成长值 361，5 维 78/62/85/70/66
- 已获得 8 枚徽章
- 《大唐密令》进度：第 3 章「密令现世」进行中，已探索 6/10 剧情点（60%）
- 当前任务「找出塔身上 3 个特殊符号」进度 1/3
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from . import db
from . import seed_data as S
from .config import GROWTH_DIMS, MATERIAL_CATEGORIES

RNG = random.Random(20260922)


# ---------------------------------------------------------------- 工具
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _ago(minutes: int) -> str:
    return (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 各表播种
def _seed_parks() -> None:
    for p in S.PARKS:
        db.insert("parks", {**p, "created_at": _now()})


def _seed_character_and_skus() -> None:
    db.insert("characters", S.CHARACTER)
    for sku in S.SKUS:
        db.insert("skus", sku)
    for c in S.ACTIVATION_CODES:
        db.insert("activation_codes", {**c, "user_id": 1 if c["used"] else None,
                                       "used_at": _ago(4320) if c["used"] else None})


def _seed_users() -> None:
    for u in S.USERS:
        db.insert("users", {
            "id": u["id"], "nickname": u["nickname"], "family_name": u["family_name"],
            "avatar": u["avatar"], "city": u["city"], "level": u["level"],
            "growth_total": u["growth_total"], "travel_days": u["travel_days"],
            "age_band": u["age_band"], "created_at": _ago(60 * 24 * 30),
            "last_active": _ago(3),
        })
    for uid, dims in S.USER_GROWTH.items():
        for dim, _label in GROWTH_DIMS:
            db.insert("user_growth", {"user_id": uid, "dim": dim, "value": dims.get(dim, 0)})

    for d in S.DEVICES:
        db.insert("devices", {**d, "activated_at": _ago(4320)})


def _seed_scenarios() -> None:
    for s in S.SCENARIOS:
        db.insert("scenarios", {
            "id": s["id"], "park_id": s["park_id"], "title": s["title"],
            "subtitle": s["subtitle"], "kicker": s["kicker"], "meta": s["meta"],
            "emoji": s["emoji"], "age_band": s["age_band"], "status": s["status"],
            "worldview": s["worldview"], "completion_rate": s["completion_rate"],
            "source": "manual", "created_at": _ago(60 * 24 * 20), "updated_at": _ago(45),
        })


def _seed_badges() -> None:
    for bid, name, emoji, city, sid, rarity, desc in S.BADGES:
        db.insert("badges", {"id": bid, "name": name, "emoji": emoji, "city": city,
                             "scenario_id": sid, "rarity": rarity, "desc": desc,
                             "sort_order": bid})
    for bid in S.USER_1_BADGES:
        db.insert("user_badges", {"user_id": 1, "badge_id": bid, "got_at": _ago(2880)})


def _seed_wardrobe() -> None:
    for iid, name, city, emoji, typ, pid, desc in S.WARDROBE:
        db.insert("wardrobe_items", {"id": iid, "name": name, "city": city, "emoji": emoji,
                                     "type": typ, "park_id": pid, "desc": desc,
                                     "sort_order": iid})
    for iid in S.USER_1_ITEMS:
        db.insert("user_items", {"user_id": 1, "item_id": iid, "got_at": _ago(4320)})


def _insert_chapter(scenario_id: int, idx: int, title: str, summary: str) -> int:
    return db.insert("chapters", {"scenario_id": scenario_id, "idx": idx,
                                  "title": title, "summary": summary})


def _insert_node(scenario_id: int, chapter_id: int, data: tuple) -> int:
    (idx, _cidx, name, kind, trig, lat, lng, radius, place,
     age, story, dialog, x, y) = data
    return db.insert("nodes", {
        "scenario_id": scenario_id, "chapter_id": chapter_id, "idx": idx,
        "name": name, "kind": kind, "trigger_type": trig, "lat": lat, "lng": lng,
        "radius_m": radius, "age_band": age, "place": place,
        "story_text": story, "ai_dialog": dialog, "x": x, "y": y, "sort_order": idx,
    })


def _insert_task(scenario_id: int, node_id: int, t: tuple, age_band: str = "8-12") -> int:
    (_nidx, title, typ, verify, answer, keywords, target,
     desc, hint, reward, badge_id, rate) = t
    return db.insert("tasks", {
        "node_id": node_id, "scenario_id": scenario_id, "title": title, "type": typ,
        "age_band": age_band, "desc": desc, "verify_mode": verify, "answer": answer,
        "keywords": keywords, "hint": hint, "target_count": target,
        "reward_growth": db.json_dumps(reward), "reward_badge_id": badge_id,
        "completion_rate": rate, "enabled": 1,
        "avg_minutes": RNG.randint(7, 18),
    })


def _insert_extra_task(scenario_id: int, node_id: int, t: tuple) -> int:
    """延展任务：同一节点 × 不同年龄层（商业计划书 P13）。"""
    (_sid, title, typ, verify, answer, keywords, target,
     desc, hint, reward, _node_idx, age) = t
    return db.insert("tasks", {
        "node_id": node_id, "scenario_id": scenario_id, "title": title, "type": typ,
        "age_band": age, "desc": desc, "verify_mode": verify, "answer": answer,
        "keywords": keywords, "hint": hint, "target_count": target,
        "reward_growth": db.json_dumps(reward), "reward_badge_id": None,
        "completion_rate": RNG.randint(40, 85), "enabled": 1,
        "avg_minutes": RNG.randint(6, 16),
    })


def _seed_xian_story() -> None:
    """旗舰剧本《大唐密令》：5 章 / 10 节点 / 任务 / 连线 + 延展任务。"""
    ch_ids: dict[int, int] = {}
    for idx, sid, title, summary in S.XIAN_CHAPTERS:
        ch_ids[idx] = _insert_chapter(sid, idx, title, summary)

    node_ids: dict[int, int] = {}
    for data in S.XIAN_NODES:
        idx, cidx = data[0], data[1]
        node_ids[idx] = _insert_node(1, ch_ids[cidx], data)

    for t in S.XIAN_TASKS:
        if t[0] in node_ids:
            _insert_task(1, node_ids[t[0]], t)

    for frm, to, color in S.XIAN_LINKS:
        if frm in node_ids and to in node_ids:
            db.insert("node_links", {"scenario_id": 1, "from_node": node_ids[frm],
                                     "to_node": node_ids[to], "color": color})

    for t in S.EXTRA_TASKS:
        if t[0] != 1:
            continue
        nid = node_ids.get(t[10])
        if nid:
            _insert_extra_task(1, nid, t)


def _seed_other_scenarios() -> None:
    for scenario_id, (chapters, nodes, tasks) in S.OTHER_SCENARIOS_DATA.items():
        ch_ids: dict[int, int] = {}
        for idx, title, summary in chapters:
            ch_ids[idx] = _insert_chapter(scenario_id, idx, title, summary)

        node_ids: dict[int, int] = {}
        for data in nodes:
            idx, cidx = data[0], data[1]
            node_ids[idx] = _insert_node(scenario_id, ch_ids[cidx], data)

        for t in tasks:
            if t[0] in node_ids:
                _insert_task(scenario_id, node_ids[t[0]], t)

        ordered = sorted(node_ids.items())
        for (a, aid), (b, bid) in zip(ordered, ordered[1:]):
            db.insert("node_links", {"scenario_id": scenario_id, "from_node": aid,
                                     "to_node": bid,
                                     "color": "gold" if b - a == 1 else "purple"})

    # 其他剧本的延展任务
    for t in S.EXTRA_TASKS:
        scenario_id = t[0]
        if scenario_id == 1:
            continue
        row = db.query_one("SELECT id FROM nodes WHERE scenario_id = ? AND idx = ?",
                           (scenario_id, t[10]))
        if row:
            _insert_extra_task(scenario_id, row["id"], t)


def _seed_materials() -> None:
    """素材库：旗舰景区用真实内容，其余按主题模板扩展，总量与原型一致（439 条）。"""
    # 1) 西安 · 大唐不夜城 真实素材
    for cat, title, content, tags in S.XIAN_MATERIALS:
        db.insert("materials", {
            "park_id": 1, "category": cat, "title": title, "content": content,
            "tags": tags, "size_label": f"{RNG.randint(80, 5200)}KB",
            "status": "indexed", "uploaded_at": _ago(RNG.randint(600, 40000)),
        })

    # 2) 其余景区按主题模板补足到原型目标数量
    counts = {cat: int(db.scalar("SELECT COUNT(*) FROM materials WHERE category = ?", (cat,)))
              for cat, _l, _e in MATERIAL_CATEGORIES}

    other_parks = [p for p in S.PARKS if p["id"] != 1]
    for cat, label, _emoji in MATERIAL_CATEGORIES:
        topics = S.MATERIAL_TOPICS.get(cat, ["资料条目"])
        target = S.MATERIAL_CATEGORY_TARGET.get(cat, 0)
        need = max(0, target - counts.get(cat, 0))
        for i in range(need):
            park = other_parks[i % len(other_parks)]
            topic = topics[i % len(topics)]
            seq = i // len(topics) + 1
            title = f"{park['city']} · {topic}" if seq == 1 else f"{park['city']} · {topic}（{seq}）"
            content = (
                f"{topic}。{park['name']}的{topic}是 AI Story Engine 生成剧情节点的重要依据。"
                f"本条素材记录了{label}维度下的关键信息：包括历史背景、空间位置、可观察细节"
                f"与适合儿童理解的知识点，可用于生成观察类、寻找类与解谜类任务。"
                f"建议在剧情节点中结合现场环境引导孩子主动发现。"
            )
            db.insert("materials", {
                "park_id": park["id"], "category": cat, "title": title, "content": content,
                "tags": f"{cat},{park['city']},{topic}",
                "size_label": f"{RNG.randint(60, 4800)}KB", "status": "indexed",
                "uploaded_at": _ago(RNG.randint(600, 50000)),
            })

    # 3) 「解析中」状态演示（原型最近上传列表中有此状态）
    for title, cat in [("大雁塔实景照片集.zip", "architecture"),
                       ("唐代长安城坊市舆图.pdf", "history")]:
        db.insert("materials", {
            "park_id": 1, "category": cat, "title": title,
            "content": "上传中，正在解析。", "tags": cat,
            "size_label": f"{RNG.randint(800, 5200)}KB",
            "status": "parsing", "uploaded_at": _ago(RNG.randint(5, 120)),
        })


def _seed_ops_data() -> None:
    for day, seq, visitors, opens, revenue in S.METRICS_14D:
        db.insert("metrics_daily", {
            "park_id": 1, "day": day, "seq": seq, "visitors": visitors,
            "story_opens": opens, "completes": int(opens * 0.68), "revenue": revenue,
        })

    for _label, amount, channel in S.REVENUE_ITEMS:
        db.insert("revenue", {"park_id": 1, "channel": channel, "amount": amount,
                              "period": "近 30 天", "created_at": _now()})

    for pid, item, ps, pl, note, order in S.REVENUE_SHARES:
        db.insert("revenue_shares", {"park_id": pid, "item": item, "park_share": ps,
                                     "platform_share": pl, "note": note, "sort_order": order})

    for pid, name, typ, status, since, amount in S.COOPERATIONS:
        db.insert("cooperations", {"park_id": pid, "name": name, "type": typ,
                                   "status": status, "since": since, "amount": amount})

    for i, (typ, title, detail, pid) in enumerate(S.EVENTS):
        db.insert("events", {"type": typ, "title": title, "detail": detail,
                             "park_id": pid, "created_at": _ago(2 + i * 47)})


def _seed_demo_progress() -> None:
    """演示账号进度：已探索 6/10，第 3 章进行中，当前任务 1/3。"""
    nodes = db.query(
        "SELECT id, idx, chapter_id, name FROM nodes WHERE scenario_id = 1 ORDER BY idx")

    for n in nodes:
        if n["idx"] <= 6:
            db.insert("node_visits", {
                "user_id": 1, "node_id": n["id"], "scenario_id": 1,
                "source": "gps" if n["idx"] <= 5 else "chat",
                "visited_at": _ago(180 - n["idx"] * 12),
            })

    # 已通过任务：节点 1—4 的「全部」任务都要按 target_count 通过，节点才算真正完成。
    # 这样当前节点正好落在第 3 章「密令现世」（原型状态）。
    for n in nodes:
        if n["idx"] > 4:
            continue
        for t in db.query(
                "SELECT id, reward_growth, verify_mode, answer, target_count FROM tasks "
                "WHERE node_id = ? AND enabled = 1 ORDER BY id", (n["id"],)):
            for k in range(max(1, int(t["target_count"] or 1))):
                db.insert("task_submissions", {
                    "user_id": 1, "task_id": t["id"], "node_id": n["id"],
                    "answer": t["answer"] or "已完成",
                    "photo_note": (f"演示数据：第 {k + 1} 处记录"
                                   if t["verify_mode"] == "photo" else None),
                    "passed": 1,
                    "growth_gain": t["reward_growth"],
                    "submitted_at": _ago(170 - n["idx"] * 12 + k),
                })

    # 当前任务「找出塔身上 3 个特殊符号」进度 1/3
    cur = db.query_one(
        "SELECT t.id, t.node_id, t.reward_growth FROM tasks t JOIN nodes n ON n.id = t.node_id "
        "WHERE n.scenario_id = 1 AND n.idx = 5 LIMIT 1")
    if cur:
        db.insert("task_submissions", {
            "user_id": 1, "task_id": cur["id"], "node_id": cur["node_id"],
            "answer": "莲花", "photo_note": "找到第一个符号：莲花纹", "passed": 1,
            "growth_gain": cur["reward_growth"], "submitted_at": _ago(6),
        })

    # 其它已完成剧本：西湖奇缘 / 熊猫调查局 / 苗岭宝藏
    # （对应原型「我的」页「走过 5 座城市」与地图上 5 座已点亮城市）
    for sid, chapter_idx, percent in [(2, 4, 100), (3, 5, 100), (6, 4, 100)]:
        db.insert("progress", {
            "user_id": 1, "scenario_id": sid, "chapter_idx": chapter_idx,
            "percent": percent, "status": "done",
            "started_at": _ago(60 * 24 * 12), "updated_at": _ago(60 * 24 * 3),
        })
    # 北京（皇家秘境）已解锁未完成
    db.insert("progress", {
        "user_id": 1, "scenario_id": 4, "chapter_idx": 2, "percent": 40,
        "status": "ongoing", "started_at": _ago(60 * 24 * 8), "updated_at": _ago(60 * 24 * 2),
    })
    # 《大唐密令》第 3 章进行中
    db.insert("progress", {
        "user_id": 1, "scenario_id": 1, "chapter_idx": 3, "percent": 60,
        "status": "ongoing", "started_at": _ago(60 * 24 * 5), "updated_at": _ago(6),
    })

    for uid, sid, pct, status in [(2, 4, 75, "ongoing"), (3, 3, 100, "done"),
                                  (4, 2, 100, "done"), (5, 6, 100, "done"),
                                  (6, 1, 20, "ongoing")]:
        db.insert("progress", {
            "user_id": uid, "scenario_id": sid, "chapter_idx": max(1, pct // 25),
            "percent": pct, "status": status, "started_at": _ago(60 * 24 * 4),
            "updated_at": _ago(60 * 24),
        })


def _refresh_completion_rates() -> None:
    """按真实数据刷新剧本的章节 / 节点计数与完成率。"""
    for row in db.query("SELECT id, completion_rate FROM scenarios"):
        sid = row["id"]
        chapters = int(db.scalar("SELECT COUNT(*) FROM chapters WHERE scenario_id = ?", (sid,)))
        nodes = int(db.scalar("SELECT COUNT(*) FROM nodes WHERE scenario_id = ?", (sid,)))
        done = int(db.scalar(
            "SELECT COUNT(DISTINCT nv.node_id) FROM node_visits nv "
            "JOIN nodes n ON n.id = nv.node_id WHERE n.scenario_id = ?", (sid,)))
        rate = int(round(done * 100 / nodes)) if nodes else 0
        cur = int(row["completion_rate"] or 0)
        db.update_by_id("scenarios", sid, {
            "chapter_count": chapters,
            "completion_rate": max(rate, cur),
        })


def seed_all(force: bool = True) -> dict:
    """执行完整播种，返回统计信息。"""
    db.init_db(force=force)
    # 顺序受外键约束：parks → skus/codes → users/devices → scenarios → chapters/nodes
    _seed_parks()
    _seed_character_and_skus()
    _seed_users()
    _seed_scenarios()
    _seed_badges()
    _seed_wardrobe()
    _seed_xian_story()
    _seed_other_scenarios()
    _seed_materials()
    _seed_ops_data()
    _seed_demo_progress()
    _refresh_completion_rates()

    return {
        "parks": db.table_count("parks"),
        "scenarios": db.table_count("scenarios"),
        "chapters": db.table_count("chapters"),
        "nodes": db.table_count("nodes"),
        "tasks": db.table_count("tasks"),
        "badges": db.table_count("badges"),
        "materials": db.table_count("materials"),
        "users": db.table_count("users"),
        "skus": db.table_count("skus"),
        "events": db.table_count("events"),
    }


if __name__ == "__main__":
    stats = seed_all(force=True)
    print("游伴 AI 播种完成：")
    for k, v in stats.items():
        print(f"  {k:12s} {v}")
