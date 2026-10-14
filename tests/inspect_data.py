#!/usr/bin/env python
"""游伴 AI · 数据体检：查看播种后的关键数据是否与原型一致。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

LINES: list[str] = []


def p(s: str = "") -> None:
    LINES.append(s)


p("=" * 78)
p("游伴 AI · 数据体检")
p("=" * 78)

# ---------------- 总体
p("\n【表统计】")
for t in ("parks", "scenarios", "chapters", "nodes", "tasks", "badges",
          "materials", "users", "skus", "wardrobe_items", "node_visits",
          "task_submissions", "progress", "events", "ai_jobs"):
    p(f"  {t:<20} {db.table_count(t)}")

# ---------------- 剧本
p("\n【剧本（对齐后台「剧本管理」）】")
p(f"  {'ID':<3} {'剧本名':<14} {'城市':<5} {'状态':<7} {'章节':<4} {'节点':<4} {'完成率'}")
for r in db.query(
        "SELECT s.id, s.title, COALESCE(p.city,'—') city, s.status, s.completion_rate, "
        "(SELECT COUNT(*) FROM chapters c WHERE c.scenario_id=s.id) ch, "
        "(SELECT COUNT(*) FROM nodes n WHERE n.scenario_id=s.id) nd "
        "FROM scenarios s LEFT JOIN parks p ON p.id=s.park_id ORDER BY s.id"):
    p(f"  {r['id']:<3} {r['title']:<14} {r['city']:<5} {r['status']:<7} "
      f"{r['ch']:<4} {r['nd']:<4} {r['completion_rate']}%")

st = db.query("SELECT status, COUNT(*) c FROM scenarios GROUP BY status")
p("  状态汇总: " + ", ".join(f"{r['status']}={r['c']}" for r in st))

# ---------------- 大唐密令
p("\n【《大唐密令》章节 / 节点 / 任务】")
for c in db.query("SELECT * FROM chapters WHERE scenario_id=1 ORDER BY idx"):
    p(f"  第{c['idx']}章 {c['title']} —— {c['summary']}")
    for n in db.query("SELECT * FROM nodes WHERE chapter_id=? ORDER BY idx", (c["id"],)):
        tasks = db.query("SELECT title, type, verify_mode, target_count FROM tasks "
                         "WHERE node_id=? ORDER BY id", (n["id"],))
        p(f"      [{n['kind']:<6}] #{n['id']:<3} {n['name']:<22} {n['trigger_type']:<4} "
          f"({n['lat']},{n['lng']}) r={n['radius_m']}m ×{len(tasks)}任务")
        for t in tasks:
            p(f"               · {t['title']} [{t['type']}/{t['verify_mode']}] "
              f"target={t['target_count']}")

# ---------------- 素材
p("\n【内容素材库（对齐后台分类条数 128/96/42/61/78/34 = 439）】")
tot = 0
for r in db.query("SELECT category, COUNT(*) c FROM materials WHERE status='indexed' "
                  "GROUP BY category ORDER BY c DESC"):
    p(f"  {r['category']:<14} {r['c']}")
    tot += r["c"]
p(f"  {'已入库合计':<14} {tot}")
p(f"  {'解析中':<14} {db.scalar(chr(83) + chr(69) + chr(76) + chr(69) + chr(67) + chr(84) + ' COUNT(*) FROM materials WHERE status=' + chr(39) + 'parsing' + chr(39))}")
p(f"  {'总计':<14} {db.table_count('materials')}")
p(f"  本景区(西安)素材: {db.scalar('SELECT COUNT(*) FROM materials WHERE park_id=1')} 条")

# ---------------- 结构与枚举分布
p("\n【任务 / 徽章 / 剧本 结构分布（供 README 与文档核对）】")
rows = db.query("SELECT type, COUNT(*) c FROM tasks GROUP BY type ORDER BY c DESC")
p("  任务类型: " + " / ".join(f"{r['type']}={r['c']}" for r in rows))
p(f"  计数型任务(target_count>1): {db.scalar('SELECT COUNT(*) FROM tasks WHERE target_count > 1')}")
rows = db.query("SELECT verify_mode, COUNT(*) c FROM tasks GROUP BY verify_mode ORDER BY c DESC")
p("  判定方式: " + " / ".join(f"{r['verify_mode']}={r['c']}" for r in rows))
rows = db.query("SELECT age_band, COUNT(*) c FROM tasks GROUP BY age_band ORDER BY c DESC")
p("  年龄层: " + " / ".join(f"{r['age_band']}={r['c']}" for r in rows))
rows = db.query("SELECT type, COUNT(*) c FROM tasks WHERE enabled = 1 GROUP BY type")
p(f"  启用任务: {sum(r['c'] for r in rows)}")
rows = db.query("SELECT status, COUNT(*) c FROM scenarios GROUP BY status")
p("  剧本状态: " + " / ".join(f"{r['status']}={r['c']}" for r in rows))
rows = db.query("SELECT rarity, COUNT(*) c FROM badges GROUP BY rarity ORDER BY c DESC")
p("  徽章稀有度: " + " / ".join(f"{r['rarity']}={r['c']}" for r in rows))
p(f"  关联到剧本的徽章: {db.scalar('SELECT COUNT(*) FROM badges WHERE scenario_id IS NOT NULL')}")
p(f"  已使用激活码: {db.scalar('SELECT COUNT(*) FROM activation_codes WHERE used = 1')} / "
  f"{db.table_count('activation_codes')}")

# 徽章条件必须指向真实存在的剧本
import re as _re  # noqa: E402
titles = {r["title"] for r in db.query("SELECT title FROM scenarios")}
dangling = []
for b in db.query("SELECT name, desc FROM badges"):
    m = _re.search(r"完成《(.+?)》", b["desc"] or "")
    if m and m.group(1) not in titles:
        dangling.append(f"{b['name']}→《{m.group(1)}》")
p("  徽章条件自洽: " + ("✓ 全部指向真实剧本" if not dangling else f"✗ 悬空 {dangling}"))

# ---------------- 演示账号
p("\n【演示账号 user_id=1（对齐 C 端原型）】")
u = db.query_one("SELECT * FROM users WHERE id=1")
p(f"  {u['family_name']} · Lv.{u['level']} · 成长值 {u['growth_total']} · "
  f"旅行 {u['travel_days']} 天")
g = db.query("SELECT dim, value FROM user_growth WHERE user_id=1")
p("  成长五维度: " + ", ".join(f"{r['dim']}={r['value']}" for r in g) +
  f"  （合计 {sum(r['value'] for r in g)}）")
p(f"  徽章: {db.scalar('SELECT COUNT(*) FROM user_badges WHERE user_id=1')} / "
  f"{db.table_count('badges')}")
d = db.query_one("SELECT * FROM devices WHERE user_id=1")
p(f"  潮玩: {d['nickname']} · {d['outfit']}")
p(f"  装扮 {db.scalar('SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id=ui.item_id WHERE ui.user_id=1 AND w.type=\"outfit\"')} 套 / "
  f"装备 {db.scalar('SELECT COUNT(*) FROM user_items ui JOIN wardrobe_items w ON w.id=ui.item_id WHERE ui.user_id=1 AND w.type=\"gear\"')} 件")

p("\n  剧本进度:")
for r in db.query("SELECT pr.*, s.title FROM progress pr JOIN scenarios s ON s.id=pr.scenario_id "
                  "WHERE pr.user_id=1 ORDER BY pr.scenario_id"):
    p(f"    {r['title']:<12} 第{r['chapter_idx']}章 {r['percent']}% [{r['status']}]")

nodes1 = db.query("SELECT id, idx, name, kind FROM nodes WHERE scenario_id=1 ORDER BY idx")
visited = {r["node_id"] for r in db.query("SELECT node_id FROM node_visits WHERE user_id=1")}
passed: dict[int, int] = {}
for r in db.query("SELECT task_id, COUNT(*) c FROM task_submissions "
                  "WHERE user_id=1 AND passed=1 GROUP BY task_id"):
    passed[r["task_id"]] = r["c"]
p("\n  《大唐密令》节点状态（原型：已探索 6/10 = 60%，第 3 章进行中）:")
for n in nodes1:
    tasks = db.query("SELECT id, target_count, title FROM tasks WHERE node_id=? AND enabled=1",
                     (n["id"],))
    if tasks:
        done = all(passed.get(t["id"], 0) >= int(t["target_count"] or 1) for t in tasks)
    else:
        done = n["id"] in visited
    state = "✓完成" if done else ("▶进行中" if n["id"] in visited else "  未解锁")
    prog = ""
    if tasks and n["id"] in visited and not done:
        t = tasks[0]
        prog = f"  当前任务：{t['title']}（{passed.get(t['id'], 0)}/{t['target_count']}）"
    p(f"    {state}  #{n['id']:<3} {n['name']}{prog}")
p(f"  已探索 {len([n for n in nodes1 if n['id'] in visited])}/{len(nodes1)} 节点 = "
  f"{int(round(len([n for n in nodes1 if n['id'] in visited])*100/len(nodes1)))}%")

# ---------------- 地图
p("\n【探索地图（对齐原型：5 座已点亮 / 12 座）】")
lit = db.query("SELECT p.*, (SELECT title FROM scenarios s WHERE s.park_id=p.id ORDER BY s.id LIMIT 1) sc "
               "FROM parks p ORDER BY p.sort_order")
for r in lit:
    mark = "✓ 已点亮" if r["lit"] else "🔒 未解锁"
    p(f"  {r['emoji']} {r['city']:<4} {r['name']:<20} {r['sc'] or '—':<12} {mark} "
      f"({r['map_x']}%,{r['map_y']}%)")

# ---------------- AI
p("\n【AI Story Engine】")
eng = db.query_one("SELECT * FROM ai_jobs ORDER BY id DESC LIMIT 1")
if eng:
    p(f"  最近一次生成: mode={eng['mode']} engine={eng['engine']} "
      f"{eng['elapsed_ms']}ms 入库剧本={eng['created_scenario_id']}")

report = "\n".join(LINES)
out = Path(__file__).parent / "_inspect.txt"
out.write_text(report, encoding="utf-8")
print("体检报告已写入:", out)
