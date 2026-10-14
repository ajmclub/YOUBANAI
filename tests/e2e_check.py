#!/usr/bin/env python
"""游伴 AI · 端到端接口自检。

用法：python tests/e2e_check.py [base_url]
输出 UTF-8 报告到 tests/_report.txt 并打印摘要。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8801"
LINES: list[str] = []
FAILS: list[str] = []
PASS = 0


def call(method: str, path: str, body: dict | None = None):
    global PASS
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            PASS += 1
            return json.loads(raw) if raw.strip().startswith(("{", "[")) else raw
    except urllib.error.HTTPError as e:
        FAILS.append(f"{method} {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
        return None
    except Exception as e:  # noqa: BLE001
        FAILS.append(f"{method} {path} -> {type(e).__name__}: {e}")
        return None


def sec(title: str) -> None:
    LINES.append("")
    LINES.append("=" * 72)
    LINES.append(title)
    LINES.append("=" * 72)


def show(label: str, value) -> None:
    LINES.append(f"  {label:<26} {value}")


# ================================================================ 1. 系统
sec("1. 系统接口")
h = call("GET", "/health")
show("health", h)
m = call("GET", "/api/meta")
show("app", f"{m['app']} / {m['app_en']} v{m['version']}")
show("tagline", m["tagline"])
show("counts", m["counts"])

# ================================================================ 2. C 端
sec("2. C 端 · 开箱激活 → 首页 → 探索 → 对话 → 剧本 → 我的")

act = call("POST", "/api/c/activate", {"code": "YB-HZ-2026-0003", "nickname": "小游"})
show("activate.user", act["user"]["nickname"] if act else "FAIL")
show("activate.device", f"{act['device']['nickname']} / {act['device']['sku_name']}" if act else "FAIL")
show("activate.greeting", act["greeting"] if act else "FAIL")
uid = act["user"]["id"] if act else 1
show("new user_id", uid)

home = call("GET", f"/api/c/home?user_id=1")
show("home.location", home["location"]["name"])
show("home.device", f"{home['device']['nickname']} · {home['device']['outfit']}")
show("home.status_pill", home["status_pill"])
ta = home["today_adventure"]
show("home.today_adventure", f"{ta['title']} 第{ta['chapter_idx']}章 {ta['chapter_title']} "
                              f"{ta['done_nodes']}/{ta['total_nodes']} = {ta['percent']}%")
show("home.nearby_nodes", len(home["nearby_nodes"]))
for n in home["nearby_nodes"][:2]:
    show("  · 附近故事点", f"{n['name']} ({n['distance_text']}) {n['kind_label']}")
show("home.speech", home["speech"])

exp = call("GET", "/api/c/explore?user_id=1")
show("explore.stats", exp["stats"])
show("explore.map nodes", [(n["city"], n["state"]) for n in exp["nodes"]])
show("explore.cities", len(exp["cities"]))
for c in exp["cities"][:4]:
    show("  · 城市", f"{c['emoji']} {c['city']}·{c['title']} [{c['state_label']}] {c['progress_percent']}%")

sc = call("GET", "/api/c/scenario/1?user_id=1")
show("scenario.title", f"{sc['title']} / {sc['chapters_count']}章 {sc['nodes_count']}节点")
show("scenario.progress", f"第{sc['current_chapter']}章 · {sc['visited_nodes']}/{sc['nodes_count']}"
                          f" = {sc['progress_percent']}%")
show("scenario.current_node", sc["current_node"]["name"])
show("scenario.current_tasks", [(t["title"], t["progress"]) for t in sc["current_tasks"]])
for ch in sc["chapters"]:
    states = [n["state"] for n in ch["nodes"]]
    show(f"  第{ch['idx']}章 {ch['title']}", f"{ch['state']} · 节点状态 {states}")

# 对话
for text in ["你好阿游", "附近还有什么故事？", "给我讲讲大雁塔", "我有点累了"]:
    r = call("POST", "/api/c/chat", {"user_id": 1, "text": text, "lat": 34.2186, "lng": 108.9644})
    show(f"chat 「{text}」", f"intent={r['intent']} · {r['messages'][0]['text'][:46]}")
    if r["quest_card"]:
        show("  └ quest_card", f"{r['quest_card']['title']} → {r['quest_card']['cta']}")

# 定位触发
loc = call("POST", "/api/c/locate", {"user_id": 1, "lat": 34.2186, "lng": 108.9644})
show("locate.park", loc["park"]["name"] if loc["park"] else "未定位")
show("locate.triggered", [(t["name"], t["distance_text"], t["kind_label"])
                          for t in loc["triggered"]])
show("locate.nearby", [(t["name"], t["distance_text"]) for t in loc["nearby"][:3]])

loc2 = call("POST", "/api/c/locate", {"user_id": 1, "lat": 30.2470, "lng": 120.1490})
show("locate(杭州).park", loc2["park"]["name"] if loc2["park"] else "未定位")

# 任务流程：取一个未完成任务，先答错再答对
t9 = call("GET", "/api/c/task/9?user_id=1")
show("task9.title", f"{t9['title']} [{t9['type_label']}] mode={t9['verify_mode']}")
show("task9.node", t9["node"]["name"])
bad = call("POST", "/api/c/task/9/submit", {"user_id": 1, "answer": "完全错误的答案"})
show("submit 错误答案", f"pass={bad['pass']} · {bad['feedback']} · +{sum(bad['growth_gain'].values())}")
good = call("POST", "/api/c/task/9/submit", {"user_id": 1, "answer": "塔影、铜钱、钟声、砖纹"})
show("submit 正确答案", f"pass={good['pass']} · {good['feedback']}")
show("  └ growth_gain", good["growth_gain"])
show("  └ growth_total", good["growth_total"])
show("  └ level_up", good["level_up"])
show("  └ node_completed", good["node_completed"])
show("  └ next_node", good["next_node"])

# 计数型任务：找一个 target_count > 1 的任务演示 3 步
tasks = call("GET", "/api/admin/tasks")
count_task = next((t for t in tasks["items"] if t["target_count"] > 1 and t["type"] == "find"), None)
if count_task:
    show("计数型任务", f"#{count_task['id']} {count_task['title']} target={count_task['target_count']}")
    for i, kw in enumerate(["莲花", "卷草", "联珠"], 1):
        r = call("POST", f"/api/c/task/{count_task['id']}/submit",
                 {"user_id": uid, "answer": kw, "photo_note": f"第{i}枚铜钱"})
        show(f"  第{i}次提交", f"pass={r['pass']} progress={r['task_progress']} "
                              f"node_completed={r['node_completed']} badge={r['badge']}")

# 拍照型任务
photo_task = next((t for t in tasks["items"] if t["verify_mode"] == "photo"), None)
if photo_task:
    withphoto = call("POST", f"/api/c/task/{photo_task['id']}/submit",
                     {"user_id": uid, "photo_note": "拍到了唐代莲花纹砖"})
    show("拍照任务(有照片)", f"pass={withphoto['pass']} · {withphoto['feedback'][:30]}")

mine = call("GET", "/api/c/mine?user_id=1")
show("mine.user", f"{mine['user']['nickname']} Lv.{mine['user']['level']} "
                  f"{mine['user']['level_name']} · {mine['user']['growth_total']}")
show("mine.growth", [(g["label"], g["value"]) for g in mine["growth"]])
show("mine.badge_stat", mine["badge_stat"])
show("mine.toy", mine["toy"])
show("mine.entries", [(e["label"], e["value"]) for e in mine["entries"]])

wd = call("GET", "/api/c/wardrobe?user_id=1")
show("wardrobe.current", wd["current"])
show("wardrobe.items", len(wd["items"]))
eq = call("POST", "/api/c/wardrobe/equip", {"user_id": 1, "item_id": 4})
show("equip", eq)

# ================================================================ 3. B 端
sec("3. B 端 · 九大模块")

db = call("GET", "/api/admin/dashboard")
show("dashboard.date", db["date_label"])
for k in db["kpis"]:
    show(f"  KPI {k['label']}", f"{k['value']}{k['unit']} {k['delta_dir']}{k['delta']}% {k['delta_label']}")
show("dashboard.trend", f"{len(db['trend']['days'])} 天 · 游客峰值 {db['trend']['visitor_peak']}")
show("dashboard.funnel", [(f["label"], f["value"]) for f in db["funnel"]])
show("dashboard.hot_nodes", [(h["rank"], h["name"], h["value"]) for h in db["hot_nodes"][:3]])
show("dashboard.timeline", [t["title"] for t in db["timeline"][:3]])

scs = call("GET", "/api/admin/scenarios")
show("scenarios.summary", scs["summary"])
for s in scs["items"]:
    show(f"  · {s['title']}", f"{s['park_name']} {s['chapters_count']}章/{s['nodes_count']}节点 "
                              f"[{s['status_label']}] {s['completion_rate']}%")

cv = call("GET", "/api/admin/scenarios/1")
show("canvas.title", f"{cv['title']} · {cv['city']} [{cv['status_label']}]")
show("canvas.chapters", [(c["idx"], c["title"]) for c in cv["chapters"]])
show("canvas.nodes", len(cv["nodes"]))
for n in cv["nodes"]:
    show(f"  · 节点{n['id']}", f"{n['name']} [{n['type_label']}] {n['trigger_type']} "
                               f"({n['x']},{n['y']}) tasks={n['task_count']}")
show("canvas.links", [(l["from"], l["to"], l["color"]) for l in cv["links"]])

upd = call("PUT", "/api/admin/nodes/5", {"name": "密令现世", "story_text": "（编辑器保存测试）",
                                         "x": 372, "y": 170, "radius_m": 45})
show("PUT node 5", f"{upd['name']} radius={upd['radius_m']} pos=({upd['x']},{upd['y']})")
newn = call("POST", "/api/admin/nodes", {"scenario_id": 1, "name": "编辑器新建节点",
                                         "kind": "branch", "place": "测试"})
show("POST node", f"#{newn['id']} {newn['name']}")
deln = call("DELETE", f"/api/admin/nodes/{newn['id']}")
show("DELETE node", deln)

tk = call("GET", "/api/admin/tasks")
show("tasks.summary", tk["summary"])
show("tasks.types", [t["label"] for t in tk["types"]])
for t in tk["items"][:4]:
    show(f"  · 任务{t['id']}", f"{t['title'][:26]} [{t['type_label']}] {t['scenario_title']} "
                              f"{t['age_label']} {t['completion_rate']}%")
tk2 = call("GET", "/api/admin/tasks?type=solve")
show("tasks?type=solve", f"{len(tk2['items'])} 条")

mt = call("GET", "/api/admin/materials")
show("materials.categories", [(c["label"], c["count"], f"目标{c['target']}") for c in mt["categories"]])
show("materials.stats", mt["stats"])
show("materials.index_note", mt["index_note"])
show("materials.recent", [(r["title"], r["status_label"]) for r in mt["recent"][:4]])
newm = call("POST", "/api/admin/materials", {"park_id": 1, "category": "heritage",
                                             "title": "唐代砖瓦烧制技艺", "content": "唐代砖瓦以……"})
show("POST material", f"#{newm['id']} {newm['title']} {newm['status_label']} "
                      f"总入库 {newm['indexed_total']}")

vs = call("GET", "/api/admin/visitors")
show("visitors.summary", vs["summary"])
for v in vs["items"]:
    show(f"  · {v['name']}", f"{v['city']} {v['scenario_title']} Lv.{v['level']}·{v['growth_total']} "
                             f"[{v['status_label']}]")
vd = call("GET", "/api/admin/visitors/1")
show("visitor1.growth", [(g["label"], g["value"]) for g in vd["growth"]])
show("visitor1.badges", f"{vd['badge_stat']['got']}/{vd['badge_stat']['total']}")
show("visitor1.trail", len(vd["trail"]))
show("visitor1.device", vd["device"])

ip = call("GET", "/api/admin/iptoys")
show("iptoys.summary", ip["summary"])
show("iptoys.character", ip["character"]["name"] + " · " + ip["character"]["positioning"])
show("iptoys.editions", [(e["title"], e["city"]) for e in ip["editions"]])
for s in ip["skus"]:
    show(f"  · SKU", f"{s['name']} 库存{s['stock']} 激活{s['activated']} "
                     f"{s['activation_rate']}% [{s['status_label']}]")
newe = call("POST", "/api/admin/iptoys/editions", {"name": "阿游 · 苏绣限定款", "city": "苏州",
                                                   "park_id": 8, "emoji": "🌉", "stock": 800})
show("POST edition", newe)

an = call("GET", "/api/admin/analytics")
show("analytics.funnel", [(f["label"], f["value"]) for f in an["funnel"]])
show("analytics.age", [(a["label"], f"{a['percent']}%") for a in an["age_distribution"]])
show("analytics.revenue", f"{an['revenue']['total']} · "
                          f"{[(i['label'], i['amount']) for i in an['revenue']['items']]}")
show("analytics.retention", [(r["label"], f"{r['percent']}%") for r in an["retention"]])
show("analytics.scale", an["scale"])

pk = call("GET", "/api/admin/park")
show("park", f"{pk['park']['name']} {pk['park']['lat']},{pk['park']['lng']} "
             f"{pk['park']['scenario_count']}剧本 {pk['park']['node_count']}节点")
for s in pk["revenue_share"]:
    show("  · 分账", f"{s['item']}: {s['park_share']} / {s['platform_share']}")
show("park.cooperations", [(c["name"], c["type"], c["status_label"]) for c in pk["cooperations"]])
pu = call("PUT", "/api/admin/park/1", {"tip": "宜出行冒险（已保存）", "radius_m": 1800})
show("PUT park", pu)

# ================================================================ 4. AI Story Engine
sec("4. AI Story Engine（景区资料 → 剧本）")

eng = call("GET", "/api/admin/ai/engine")
show("engine", f"{eng['engine']} ({eng['engine_label']}) llm_enabled={eng['llm_enabled']}")
show("capabilities", [(c["label"], c["desc"]) for c in eng["capabilities"]])
show("node_structure", [n["name"] for n in eng["node_structure"]])
show("material_stats", eng["material_stats"])
show("setup_hint", eng["setup_hint"][:80] + "……")

gen = call("POST", "/api/admin/ai/generate",
           {"park_id": 6, "mode": "full", "age_band": "12+",
            "style": "悬疑解谜，融入敦煌壁画与丝绸之路知识，鼓励孩子观察真实色彩。",
            "scenario_title": "飞天密码 · 续章", "chapter_count": 4, "node_count": 8})
show("generate.engine", f"{gen['engine']} · {gen['elapsed_ms']}ms · mode={gen['mode_label']}")
show("generate.worldview", gen["worldview"][:150].replace("\n", " ") + "……")
show("generate.scenario", f"{gen['scenario']['title']} / {gen['scenario']['age_label']}")
show("generate.chapters", [(c["idx"], c["title"]) for c in gen["chapters"]])
show("generate.nodes", len(gen["nodes"]))
for n in gen["nodes"][:4]:
    t = n.get("task") or {}
    show(f"  · {n['name'][:30]}", f"[{n['kind']}] {t.get('type_label', '—')} "
                                   f"verify={t.get('verify_mode', '—')}")
show("generate.rewards", [(r["emoji"], r["name"], r["rarity"]) for r in gen["rewards"]])
show("generate.sources", [(s["category"], s["title"][:28]) for s in gen["sources"][:5]])
show("generate.notes", gen["notes"])
show("created_scenario_id", gen["created_scenario_id"])

# 其他模式
for mode in ["mainline", "task", "dialog", "reward"]:
    g = call("POST", "/api/admin/ai/generate",
             {"park_id": 3, "mode": mode, "age_band": "8-12", "chapter_count": 3, "node_count": 6})
    non_null = [k for k in ("worldview", "chapters", "nodes", "rewards") if g.get(k)]
    show(f"mode={mode}", f"{g['mode_label']} · 非空字段 {non_null} · {g['elapsed_ms']}ms")

jobs = call("GET", "/api/admin/ai/jobs")
show("ai.jobs", [(j["mode_label"], j["park_name"], j["elapsed_ms"]) for j in jobs["items"][:6]])

# 生成结果落库校验
gensc = call("GET", f"/api/admin/scenarios/{gen['created_scenario_id']}")
show("落库剧本", f"{gensc['title']} [{gensc['status_label']}] {len(gensc['chapters'])}章 "
                 f"{len(gensc['nodes'])}节点 {len(gensc['links'])}连线")

ov = call("GET", "/api/admin/overview")
show("overview.counts", ov["counts"])

# ================================================================ 汇总
sec("5. 自检结果")
LINES.append(f"  通过：{PASS} 项")
LINES.append(f"  失败：{len(FAILS)} 项")
for f in FAILS:
    LINES.append(f"    ✗ {f}")
LINES.append("")
LINES.append("  注意：本脚本会真实写入数据库（激活新账号、提交任务、新建剧本/节点/素材、")
LINES.append("        执行 AI 生成），因此运行后演示账号状态会发生变化。")
LINES.append("        如需恢复到与原型一致的初始演示状态，请执行：")
LINES.append("            python run.py --reseed")
LINES.append("        或  python -c \"import sys;sys.path.insert(0,'.');"
             "from app import seed;seed.seed_all(force=True)\"")

report = "\n".join(LINES)
out = Path(__file__).parent / "_report.txt"
out.write_text(report, encoding="utf-8")
print(f"通过 {PASS} 项，失败 {len(FAILS)} 项")
for f in FAILS:
    print("  FAIL:", f)
print(f"报告已写入 {out}")
print("提示：本脚本会写入数据库；如需恢复原型演示状态请执行  python run.py --reseed")
raise SystemExit(0 if not FAILS else 1)
