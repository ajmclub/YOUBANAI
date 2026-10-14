#!/usr/bin/env python
"""游伴 AI · 第二轮延展功能自检（家长模式 / 新剧本 / 可观测性）。

用法：python tests/round2_check.py [base_url]
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8802"

# 本脚本断言「与原型一致的演示状态」（5/12 城市、3 剧本、6/51 节点、8/24 徽章），
# 而 e2e_check 等脚本会写库，因此先重置，保证结果确定、可重复。
sys.path.insert(0, str(ROOT))
try:
    from app import seed
    seed.seed_all(force=True)
    print("已重置为初始演示状态（seed_all(force=True)）")
except Exception as exc:  # noqa: BLE001
    print(f"警告：重置演示数据失败（{type(exc).__name__}: {exc}）")

L: list[str] = []
BAD: list[str] = []
PASS = 0


def get(path: str, expect_error: bool = False):
    """expect_error=True 用于故意制造 404 以产生错误指标，不计入失败。"""
    global PASS
    try:
        with urllib.request.urlopen(BASE + path, timeout=60) as r:
            raw = r.read().decode("utf-8")
            PASS += 1
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        if expect_error:
            PASS += 1
            return {"_expected_error": e.code,
                    "body": e.read().decode("utf-8", "ignore")[:120]}
        BAD.append(f"GET {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:160]}")
        return None
    except Exception as e:  # noqa: BLE001
        BAD.append(f"GET {path} -> {type(e).__name__}: {e}")
        return None


def chk(label: str, cond: bool, extra: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        L.append(f"  [OK ] {label}" + (f"   {extra}" if extra else ""))
    else:
        BAD.append(label + (f" ({extra})" if extra else ""))
        L.append(f"  [BAD] {label}" + (f"   {extra}" if extra else ""))


def sec(t: str) -> None:
    L.append("")
    L.append("=" * 78)
    L.append(t)
    L.append("=" * 78)


# ================================================================ 一、新剧本
sec("一、新增剧本《雨林寻踪》（云南）与《园林谜题》（苏州）")

scs = get("/api/admin/scenarios")
items = {s["title"]: s for s in (scs or {}).get("items", [])}
chk("剧本总数 = 8", (scs or {}).get("summary", {}).get("total") == 8,
    str((scs or {}).get("summary")))
for title, city, ch, nd in [("雨林寻踪", "云南", 4, 7), ("园林谜题", "苏州", 4, 7)]:
    it = items.get(title)
    chk(f"《{title}》已建（{city}）", it is not None)
    if it:
        chk(f"  《{title}》章节/节点 = {ch}/{nd}",
            it["chapters_count"] == ch and it["nodes_count"] == nd,
            f"{it['chapters_count']}章 {it['nodes_count']}节点 [{it['status_label']}]")

for sid, title in [(7, "雨林寻踪"), (8, "园林谜题")]:
    cv = get(f"/api/admin/scenarios/{sid}")
    if not cv:
        continue
    chk(f"《{title}》画布节点有坐标与任务", all(
        n["lat"] and n["lng"] and n["task_count"] >= 1 for n in cv["nodes"]),
        f"{len(cv['nodes'])} 节点 / {len(cv['links'])} 连线")
    chk(f"《{title}》有剧情连线", len(cv["links"]) >= len(cv["nodes"]) - 1)
    # 详情（C 端）
    d = get(f"/api/c/scenario/{sid}?user_id=1")
    chk(f"《{title}》C 端可读", d is not None and d["chapters_count"] == 4)
    chk(f"  《{title}》章节时间轴完整",
        all(len(c["nodes"]) >= 1 for c in d["chapters"]) and len(d["chapters"]) == 4)
    # 每个节点都有故事文案与阿游台词
    flat = [n for c in d["chapters"] for n in c["nodes"]]
    chk(f"  《{title}》全部节点有任务", all(len(n["tasks"]) >= 1 for n in flat),
        f"{len(flat)} 节点")
    # 任务详情
    tids = [t["id"] for n in flat for t in n["tasks"]]
    ok = 0
    for tid in tids[:6]:
        t = get(f"/api/c/task/{tid}?user_id=1")
        if t and t.get("desc") and t["node"]["story_text"]:
            ok += 1
    chk(f"  《{title}》任务详情可读且有文案", ok == min(6, len(tids)), f"{ok} 条")

# 徽章关联
sec("二、徽章体系自洽")
mine = get("/api/c/mine?user_id=1")
badges = {b["name"]: b for b in (mine or {}).get("badges", [])}
chk("徽章总数 = 24", len(badges) == 24, str(len(badges)))
for name in ("雨林探险家", "桥梁建筑师"):
    b = badges.get(name)
    chk(f"「{name}」条件已指向真实剧本", b is not None and "完成《" in (b or {}).get("desc", ""),
        (b or {}).get("desc", "缺失"))
# 检查所有「完成《X》」类条件指向的剧本都真实存在
import re  # noqa: E402
titles = set(items.keys())
dangling = []
for b in badges.values():
    m = re.search(r"完成《(.+?)》", b.get("desc") or "")
    if m and m.group(1) not in titles:
        dangling.append(f"{b['name']}→《{m.group(1)}》")
chk("没有指向不存在剧本的徽章条件", not dangling, str(dangling))

# ================================================================ 三、家长模式
sec("三、家长模式 · 成长概览")
ps = get("/api/c/parent/summary?user_id=1")
if ps:
    chk("返回孩子档案", ps["child"]["nickname"] == "小小探险家" and ps["child"]["level"] == 3,
        f"Lv.{ps['child']['level']} {ps['child']['level_name']}")
    ov = {o["key"]: o for o in ps["overview"]}
    chk("概览含 6 项指标", len(ps["overview"]) == 6, "、".join(o["label"] for o in ps["overview"]))
    chk("  走过城市 5/12", ov["cities"]["value"] == 5 and ov["cities"]["of"] == 12,
        f"{ov['cities']['value']}/{ov['cities']['of']}")
    # 可选剧本数 = 非 draft 的剧本（飞天密码为 draft，不计入）
    online = int(get("/api/admin/scenarios")["summary"]["total"]) - 1
    chk(f"  完成剧本 3/{online}", ov["stories"]["value"] == 3 and ov["stories"]["of"] == online,
        f"{ov['stories']['value']}/{ov['stories']['of']}")
    chk("  探索剧情点 6/51", ov["nodes"]["value"] == 6, f"{ov['nodes']['value']}/{ov['nodes']['of']}")
    chk("  获得徽章 8/24", ov["badges"]["value"] == 8 and ov["badges"]["of"] == 24,
        f"{ov['badges']['value']}/{ov['badges']['of']}")
    chk("  累计时长为正数", ov["minutes"]["value"] > 0, f"{ov['minutes']['value']} 分钟")
    chk("五维成长完整", len(ps["growth"]) == 5,
        " ".join(f"{g['label']}{g['value']}" for g in ps["growth"]))
    chk("含成长画像解读", bool(ps.get("growth_note")), (ps.get("growth_note") or "")[:60])
    chk("近 7 天活跃度", len(ps["weekly"]["values"]) == 7,
        f"合计 {ps['weekly']['total']} 个任务 / 峰值 {ps['weekly']['peak']}")
    chk("近期徽章列表", len(ps["badges_recent"]) > 0, f"{len(ps['badges_recent'])} 枚")
    chk("进行中的剧本列表", len(ps["scenarios"]) > 0, f"{len(ps['scenarios'])} 个")
    chk("亲子共玩建议（规则生成）", 2 <= len(ps["suggestions"]) <= 4,
        " / ".join(s["title"] for s in ps["suggestions"]))
    for s in ps["suggestions"]:
        L.append(f"        · {s['title']} → {s['advice'][:46]}")
    L.append(f"  成长画像：{ps['growth_note']}")

sec("四、家长模式 · 单次旅行报告")
rp = get("/api/c/parent/reports?user_id=1")
chk("报告列表", rp is not None and len(rp["items"]) > 0,
    " / ".join(f"{i['title']}({i['status_label']})" for i in (rp or {}).get("items", [])))

rep = get("/api/c/parent/report?user_id=1&scenario_id=1")
if rep:
    s = rep["summary"]
    chk("《大唐密令》报告汇总", s["visited"] == 6 and s["total"] == 10 and s["percent"] == 60,
        f"{s['visited']}/{s['total']} = {s['percent']}% [{s['status_label']}]")
    chk("  完成章节 2/5", s["chapters_done"] == 2 and s["chapters_total"] == 5,
        f"{s['chapters_done']}/{s['chapters_total']}")
    chk("  完成任务数 > 0", s["tasks_done"] > 0, f"{s['tasks_done']} 个")
    chk("  估算时长 > 0", s["minutes"] > 0, f"{s['minutes']} 分钟")
    chk("剧情时间轴有记录", len(rep["trail"]) > 0, f"{len(rep['trail'])} 条")
    chk("知识点反查成功", len(rep["knowledge"]) > 0, f"{len(rep['knowledge'])} 条")
    for k in rep["knowledge"][:3]:
        L.append(f"        · [{k['category_label']}] {k['title']}  ← 节点「{k['node']}」")
    chk("回家提问 3 个", len(rep["questions"]) == 3)
    for q in rep["questions"]:
        L.append(f"        ? {q}")
    chk("本次成长累计非空", bool(rep["growth_gain"]),
        " ".join(f"{k}+{v}" for k, v in rep["growth_gain"].items()))
    chk("章节结构完整", len(rep["chapters"]) == 5)

# ================================================================ 五、可观测性
sec("五、可观测性")
# 先打一些请求产生指标（最后一条是故意制造的 404，用于验证错误指标）
for p in ["/api/c/home?user_id=1", "/api/c/explore?user_id=1",
          "/api/admin/dashboard"]:
    get(p)
get("/api/c/task/999999?user_id=1", expect_error=True)

m = get("/api/metrics")
if m:
    req = m["requests"]
    chk("请求指标：总请求数 > 0", req["requests_total"] > 0, f"{req['requests_total']} 次")
    chk("请求指标：平均耗时", req["avg_ms"] >= 0, f"{req['avg_ms']} ms")
    chk("请求指标：按端点聚合", len(req["endpoints"]) > 0, f"{len(req['endpoints'])} 个端点")
    chk("请求指标：路径已归一化（/api/c/task/{id}）",
        any(e["path"] == "/api/c/task/{id}" for e in req["endpoints"]),
        " / ".join(e["path"] for e in req["endpoints"][:4]))
    chk("请求指标：记录了 404 错误", req["errors_total"] > 0,
        f"错误率 {req['error_rate']}%")
    chk("请求指标：慢请求榜单", "slowest" in req)
    chk("请求指标：最近请求明细", len(req["recent"]) > 0, f"{len(req['recent'])} 条")

    biz = m["business"]
    chk("业务计数：景区/剧本/节点", biz["parks"] == 12 and biz["scenarios"] == 8
        and biz["nodes"] == 51,
        f"{biz['parks']} / {biz['scenarios']} / {biz['nodes']}")
    chk("业务计数：素材已入库 439", biz["materials_indexed"] == 439,
        str(biz["materials_indexed"]))
    chk("业务计数：任务通过率", 0 <= biz["task_pass_rate"] <= 100,
        f"{biz['task_pass_rate']}%（{biz['tasks_passed']}/{biz['task_submissions']}）")
    chk("业务计数：激活设备数", biz["devices_activated"] > 0, str(biz["devices_activated"]))
    chk("业务计数：已获徽章数", biz["badges_granted"] > 0, str(biz["badges_granted"]))
    chk("业务计数：AI 生成次数", "ai_jobs" in biz, f"{biz['ai_jobs']} 次")

h = get("/health")
chk("健康检查含运行指标", h is not None and "uptime_seconds" in h and "requests_total" in h,
    f"uptime {h['uptime_seconds']}s / {h['requests_total']} 请求 / 平均 {h['avg_ms']}ms"
    if h else "")

# ================================================================ 六、新剧本可玩性
sec("六、新剧本可玩性（真实走一遍剧情闭环）")


def post(path: str, body: dict):
    global PASS
    import json as _json
    req = urllib.request.Request(
        BASE + path, data=_json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            PASS += 1
            return _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        BAD.append(f"POST {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:160]}")
        return None
    except Exception as e:  # noqa: BLE001
        BAD.append(f"POST {path} -> {type(e).__name__}: {e}")
        return None


# 云南 · 雨林寻踪：用景区真实坐标上报位置 → 应触发第 1 个节点
loc = post("/api/c/locate", {"user_id": 6, "lat": 22.0080, "lng": 100.7970})
chk("位置上报识别到云南景区", (loc or {}).get("park", {}) and
    "西双版纳" in (loc["park"]["name"] if loc.get("park") else ""),
    (loc or {}).get("park", {}).get("name") if loc else "无")
trig = (loc or {}).get("triggered", [])
chk("触发剧情节点", len(trig) >= 1, " / ".join(t["name"] for t in trig[:2]))
if trig:
    n = trig[0]
    chk("  触发节点是入口节点", n["kind"] == "entry", f"{n['name']} [{n['kind_label']}]")
    chk("  节点带阿游台词", bool(n.get("ai_dialog")), (n.get("ai_dialog") or "")[:34])
    chk("  节点关联任务", n.get("task") is not None,
        f"{n['task']['title']}（{n['task']['type_label']}）" if n.get("task") else "无")
    if n.get("task"):
        tid = n["task"]["id"]
        t = get(f"/api/c/task/{tid}?user_id=6")
        chk("  任务详情完整", t and t["desc"] and t["hint"],
            f"dest={t['verify_mode']} target={t['target_count']}" if t else "")
        # 先答错
        wrong = post(f"/api/c/task/{tid}/submit", {"user_id": 6, "answer": "肯定不对的答案"})
        chk("  答错有保底成长值", wrong and not wrong["pass"] and sum(
            wrong["growth_gain"].values()) > 0,
            f"pass={wrong['pass']} +{sum(wrong['growth_gain'].values())}" if wrong else "")
        # 再答对（用真实答案）
        ans = t.get("node") and None
        right = None
        for cand in ["4", "四", "四层", "热带雨林"]:
            right = post(f"/api/c/task/{tid}/submit", {"user_id": 6, "answer": cand})
            if right and right["pass"]:
                break
        chk("  答对通过并结算成长", right and right["pass"],
            f"growth_total={right['growth_total']} node_completed={right['node_completed']}"
            if right else "未通过")
        # 进度应被刷新
        rep = get("/api/c/parent/report?user_id=6&scenario_id=7")
        chk("  家长报告反映新进度", rep and rep["summary"]["visited"] >= 1,
            f"已探索 {rep['summary']['visited']}/{rep['summary']['total']} = "
            f"{rep['summary']['percent']}%" if rep else "")
        if rep and rep["trail"]:
            chk("  报告时间轴含本次记录", len(rep["trail"]) >= 1, f"{len(rep['trail'])} 条")

# 苏州 · 园林谜题：同样验证可达
loc2 = post("/api/c/locate", {"user_id": 6, "lat": 31.3240, "lng": 120.6290})
chk("位置上报识别到苏州景区", (loc2 or {}).get("park") and
    "拙政园" in (loc2["park"]["name"] if loc2.get("park") else ""),
    (loc2 or {}).get("park", {}).get("name") if loc2 else "无")
chk("苏州剧情可触发", len((loc2 or {}).get("triggered", [])) >= 1,
    " / ".join(t["name"] for t in (loc2 or {}).get("triggered", [])[:2]))

# 未解锁城市不应误触发（云南/苏州 lit=0，但仍应能玩——剧本已上线）
ex = get("/api/c/explore?user_id=1")
if ex:
    cities = {c["city"]: c for c in ex["cities"]}
    chk("探索页新增两座城市卡片", "云南" in cities and "苏州" in cities,
        f"{len(ex['cities'])} 张卡片")
    chk("  城市故事总数 = 7", len(ex["cities"]) == 7, str(len(ex["cities"])))
    chk("  新城市初始为未解锁", cities.get("云南", {}).get("state") == "locked",
        cities.get("云南", {}).get("state_label", ""))

# ================================================================ 七、边界与错误处理
sec("七、边界与错误处理")


def post_raw(path: str, body: dict):
    """允许非 2xx 的 POST，返回 (status, json_or_None)。"""
    global PASS
    import json as _json
    req = urllib.request.Request(
        BASE + path, data=_json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            PASS += 1
            return r.status, _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        PASS += 1
        return e.code, None


def get_status(path: str) -> int:
    global PASS
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            PASS += 1
            return r.status
    except urllib.error.HTTPError as e:
        PASS += 1
        return e.code
    except Exception:  # noqa: BLE001
        return 0


# 全新账号（无任何进度）
st, act = post_raw("/api/c/activate", {"code": "YB-CD-2026-0004", "nickname": "小小竹"})
new_uid = (act or {}).get("user", {}).get("id")
chk("开箱激活新账号", st == 200 and new_uid is not None, f"user_id={new_uid}")

fresh = get(f"/api/c/parent/summary?user_id={new_uid}")
if fresh:
    ov = {o["key"]: o["value"] for o in fresh["overview"]}
    chk("新账号概览全为 0", all(v == 0 for v in ov.values()), str(ov))
    chk("  新账号成长画像是友好提示（不是「均衡」）",
        "还没有开始探索" in fresh["growth_note"], fresh["growth_note"])
    chk("  新账号也给共玩建议", len(fresh["suggestions"]) >= 1,
        f"{len(fresh['suggestions'])} 条")
    chk("  新账号周活跃为空", fresh["weekly"]["total"] == 0)

chk("新账号报告列表为空", (get(f"/api/c/parent/reports?user_id={new_uid}") or {}).get("items") == [])

fresh_rep = get(f"/api/c/parent/report?user_id={new_uid}&scenario_id=7")
if fresh_rep:
    chk("未开始的剧本也能出报告", fresh_rep["summary"]["status"] == "not_started",
        fresh_rep["summary"]["status_label"])
    chk("  未开始报告有 3 个兜底提问", len(fresh_rep["questions"]) == 3,
        str(len(fresh_rep["questions"])))

chk("不存在的 user_id -> 404", get_status("/api/c/parent/summary?user_id=99999") == 404)
chk("不存在的 scenario_id -> 404",
    get_status("/api/c/parent/report?user_id=1&scenario_id=99999") == 404)
chk("不存在的 user_id（reports）-> 404",
    get_status("/api/c/parent/reports?user_id=99999") == 404)
chk("缺少必填参数 -> 422",
    get_status("/api/c/parent/summary") == 422)
st, _ = post_raw("/api/c/activate", {"code": "YB-NOT-EXIST", "nickname": "x"})
chk("无效激活码 -> 404", st == 404)

# ================================================================ 汇总
sec("八、结论")
L.append(f"  通过 {PASS} 项，失败 {len(BAD)} 项")
for b in BAD:
    L.append(f"    ✗ {b}")

(ROOT / "tests" / "_round2.txt").write_text("\n".join(L), encoding="utf-8")
print(f"第二轮自检：通过 {PASS} 项，失败 {len(BAD)} 项")
for b in BAD:
    print("  [BAD]", b)
print("报告：", ROOT / "tests" / "_round2.txt")
raise SystemExit(0 if not BAD else 1)
