#!/usr/bin/env python
"""游伴 AI · 交付一致性终检。

核对：文件完整性、数据库表数、接口数、文档中引用的数字是否与实际一致。
用法：python tests/final_audit.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.main import app  # noqa: E402

L: list[str] = []
BAD: list[str] = []


def p(s: str = "") -> None:
    L.append(s)


def chk(label: str, cond: bool, extra: str = "") -> None:
    p(f"  [{'OK ' if cond else 'BAD'}] {label}" + (f"   {extra}" if extra else ""))
    if not cond:
        BAD.append(label)


p("=" * 78)
p("游伴 AI · 交付一致性终检")
p("=" * 78)

# ---------------------------------------------------------------- 文件完整性
p("\n【一、交付文件完整性】")
REQUIRED = [
    "README.md", "requirements.txt", "run.py", "启动游伴AI.bat",
    "app/__init__.py", "app/main.py", "app/config.py", "app/db.py", "app/schema.sql",
    "app/seed.py", "app/seed_data.py", "app/utils.py",
    "app/engines/__init__.py", "app/engines/geo.py", "app/engines/story.py",
    "app/engines/growth.py", "app/engines/chat.py", "app/engines/story_engine.py",
    "app/routers/__init__.py", "app/routers/c_end.py", "app/routers/admin.py",
    "web/index.html",
    "web/c/index.html", "web/c/app.css", "web/c/app.js",
    "web/admin/index.html", "web/admin/app.css", "web/admin/app.js",
    "docs/API.md", "docs/产品设计说明书.md", "docs/技术架构.md",
    "docs/数据模型.md", "docs/原型对照表.md", "docs/延展路线图.md",
    "tests/e2e_check.py", "tests/contract_check.py", "tests/browser_check.py",
    "tests/inspect_data.py",
]
for f in REQUIRED:
    fp = ROOT / f
    chk(f, fp.exists() and fp.stat().st_size > 0,
        f"{fp.stat().st_size} B" if fp.exists() else "缺失")

# ---------------------------------------------------------------- 无残留临时文件
p("\n【二、无残留临时/调试文件】")
junk = []
for pat in ("**/_mock.py", "**/_e2e*", "**/.app-*.js", "**/.edge-tmp", "**/_chromeprofile",
            "**/_tmp", "**/_verify", "**/*.pyc", "**/.nodetest.js", "**/.crosscheck.py",
            "**/.syntaxcheck.js", "**/.runtest.js", "**/.capcheck.js", "**/.gen_test.py",
            "**/.edge-dump.*", "**/_probe_*.js", "**/_dbg.js", "**/_test_write.json"):
    for f in ROOT.glob(pat):
        if "__pycache__" in str(f):
            continue
        junk.append(str(f.relative_to(ROOT)))
chk("无临时文件残留", not junk, str(junk[:6]) if junk else "")

# ---------------------------------------------------------------- 数据库
p("\n【三、数据库结构】")
tables = [r["name"] for r in db.query(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
    "ORDER BY name")]
indexes = [r["name"] for r in db.query(
    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name")]
schema_tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)",
                           (ROOT / "app" / "schema.sql").read_text(encoding="utf-8"))
chk("schema.sql 表数 == 数据库表数", len(schema_tables) == len(tables),
    f"schema {len(schema_tables)} / db {len(tables)}")
p(f"       表（{len(tables)}）：{', '.join(tables)}")
p(f"       索引（{len(indexes)}）：{', '.join(indexes)}")

# ---------------------------------------------------------------- 接口
p("\n【四、接口规模】")
schema = app.openapi()
paths = schema.get("paths", {})
n_ops = sum(1 for ops in paths.values() for m in ops
            if m.lower() in ("get", "post", "put", "delete", "patch"))
n_c = sum(1 for pa, ops in paths.items() if pa.startswith("/api/c/") for _ in ops)
n_a = sum(1 for pa, ops in paths.items() if pa.startswith("/api/admin/") for _ in ops)
p(f"       总操作数 {n_ops} · C 端 {n_c} · B 端 {n_a} · 系统 {n_ops - n_c - n_a}")
chk("接口规模合理（C≥12, B≥20）", n_c >= 12 and n_a >= 20, f"C={n_c} B={n_a}")

# ---------------------------------------------------------------- 数据规模
p("\n【五、种子数据规模（与文档/原型对照）】")
stats = {
    "景区 parks": db.table_count("parks"),
    "剧本 scenarios": db.table_count("scenarios"),
    "章节 chapters": db.table_count("chapters"),
    "剧情节点 nodes": db.table_count("nodes"),
    "任务 tasks": db.table_count("tasks"),
    "徽章 badges": db.table_count("badges"),
    "素材 materials": db.table_count("materials"),
    "用户 users": db.table_count("users"),
    "潮玩 SKU": db.table_count("skus"),
    "装扮 wardrobe": db.table_count("wardrobe_items"),
}
for k, v in stats.items():
    p(f"       {k:<18} {v}")

indexed = int(db.scalar("SELECT COUNT(*) FROM materials WHERE status='indexed'"))
parsing = int(db.scalar("SELECT COUNT(*) FROM materials WHERE status='parsing'"))
chk("素材：439 条已入库 + 2 条解析中 = 441",
    indexed == 439 and parsing == 2 and db.table_count("materials") == 441,
    f"indexed={indexed} parsing={parsing}")

cats = {r["category"]: r["c"] for r in db.query(
    "SELECT category, COUNT(*) c FROM materials WHERE status='indexed' GROUP BY category")}
target = {"history": 128, "architecture": 96, "heritage": 42,
          "legend": 61, "nature": 78, "geo": 34}
chk("六分类条数与原型一致 128/96/42/61/78/34", cats == target, str(cats))

# ---------------------------------------------------------------- 演示账号
p("\n【六、演示账号状态（对齐 C 端原型）】")
u = db.query_one("SELECT * FROM users WHERE id=1")
chk("昵称/等级/成长值 = Lv.3 / 361",
    u["level"] == 3 and u["growth_total"] == 361,
    f"Lv.{u['level']} {u['growth_total']}")
dims = {r["dim"]: r["value"] for r in db.query(
    "SELECT dim,value FROM user_growth WHERE user_id=1")}
chk("成长五维度 78/62/85/70/66",
    dims == {"explore": 78, "create": 62, "observe": 85, "knowledge": 70, "courage": 66},
    str(dims))
got = int(db.scalar("SELECT COUNT(*) FROM user_badges WHERE user_id=1"))
chk("徽章 8 / 24", got == 8 and db.table_count("badges") == 24, f"{got}/24")
prog = db.query_one("SELECT * FROM progress WHERE user_id=1 AND scenario_id=1")
chk("《大唐密令》第 3 章 60% 进行中",
    prog and prog["chapter_idx"] == 3 and prog["percent"] == 60
    and prog["status"] == "ongoing",
    f"第{prog['chapter_idx']}章 {prog['percent']}% {prog['status']}" if prog else "无")
visits = int(db.scalar(
    "SELECT COUNT(*) FROM node_visits nv JOIN nodes n ON n.id=nv.node_id "
    "WHERE nv.user_id=1 AND n.scenario_id=1"))
chk("已探索 6/10 剧情点", visits == 6, f"{visits}/10")
lit = int(db.scalar("SELECT COUNT(*) FROM parks WHERE lit=1"))
chk("已点亮 5 座城市", lit == 5, str(lit))

# 当前节点 = 密令现世
from app.engines import story  # noqa: E402
cur = story.current_node(1, 1)
chk("当前节点 = 密令现世", cur and cur["name"] == "密令现世", cur["name"] if cur else "无")
if cur:
    tasks = story.node_tasks(1, cur["id"])
    t0 = next((t for t in tasks if t["total"] > 1), None)
    chk("当前任务进度 1/3", t0 and t0["done"] == 1 and t0["total"] == 3,
        f"{t0['title']} {t0['progress']}" if t0 else "无多步任务")

# ---------------------------------------------------------------- 文档数字一致性
p("\n【七、文档中的关键数字与实际一致】")
readme = (ROOT / "README.md").read_text(encoding="utf-8")
for label, needle in [("README 提到 26 张表", "26 张表"),
                      ("README 提到 439 条素材", "439"),
                      ("README 提到 12 景区", "12"),
                      ("README 提到 6 剧本", "6"),
                      ("README 提到 49 接口自检", "49"),
                      ("README 提到 90 项浏览器验证", "90")]:
    chk(label, needle in readme)

api_md = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
chk("API.md 收录 node_place", "node_place" in api_md)
chk("API.md 收录 iptoys/editions", "/api/admin/iptoys/editions" in api_md)
# API.md 中出现的每个 /api/ 路径都应真实存在
md_paths = set(re.findall(r"`(/(?:api/)?[a-z/{}A-Z_\-]+)`", api_md))
real = set(paths.keys())
missing = []
BARE_PREFIXES = {"/api", "/api/c", "/api/admin", "/api/c/parent"}  # 文中提到的前缀，不是具体接口
for mp in md_paths:
    if not mp.startswith("/api/") or mp in BARE_PREFIXES:
        continue
    norm = re.sub(r"\{[^}]*\}", "{}", mp)
    if not any(re.sub(r"\{[^}]*\}", "{}", rp) == norm for rp in real):
        missing.append(mp)
chk("API.md 中所有 /api/ 路径后端均存在", not missing, str(missing[:5]))

# ---------------------------------------------------------------- 汇总
p("\n" + "=" * 78)
p(f"【结论】{'全部通过' if not BAD else f'{len(BAD)} 项不通过'} · 共检查 "
  f"{len([l for l in L if l.strip().startswith('[')])} 项")
for x in BAD:
    p(f"    ✗ {x}")
p("=" * 78)

(ROOT / "tests" / "_audit.txt").write_text("\n".join(L), encoding="utf-8")
print(f"终检：{'全部通过' if not BAD else str(len(BAD)) + ' 项不通过'}")
for x in BAD:
    print("  [BAD]", x)
print("报告：", ROOT / "tests" / "_audit.txt")
raise SystemExit(0 if not BAD else 1)
