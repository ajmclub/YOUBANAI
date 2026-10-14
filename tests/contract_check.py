#!/usr/bin/env python
"""游伴 AI · 前后端契约一致性检查。

不依赖浏览器：静态提取前端 JS 中调用的所有 /api/... 路径，
与后端 OpenAPI 实际暴露的路由逐条比对，并抽查响应字段的使用情况。

用法：python tests/contract_check.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

LINES: list[str] = []


def p(s: str = "") -> None:
    LINES.append(s)


# ---------------------------------------------------------------- 后端路由
schema = app.openapi()
routes: list[tuple[str, str]] = []
for path, ops in schema.get("paths", {}).items():
    for method in ops:
        if method.lower() in ("get", "post", "put", "delete", "patch"):
            routes.append((method.upper(), path))

api_routes = [(m, pa) for m, pa in routes if pa.startswith("/api/")]
all_api = sorted(api_routes, key=lambda x: (x[1], x[0]))

p("=" * 78)
p("游伴 AI · 前后端契约一致性检查")
p("=" * 78)
p(f"\n【后端 OpenAPI 路由】共 {len(routes)} 条，其中 /api/ 接口 {len(api_routes)} 条")
for m, pa in all_api:
    p(f"  {m:<7} {pa}")


# ---------------------------------------------------------------- 匹配工具
PLACEHOLDER = "XSEGX"


def to_regex(path: str) -> str:
    """后端路径 → 正则：{param} 匹配任意一段；前端归一化的 {} 也视为一段。"""
    esc = re.escape(path)
    esc = re.sub(r"\\\{[^}]*\\\}", "[^/]+", esc)      # re.escape 后的 {param}
    esc = re.sub(r"\\\{\\\}", "[^/]+", esc)           # 已归一化的 {}
    esc = esc.replace(PLACEHOLDER, "[^/]+")
    return "^" + esc + "$"


def _norm_call(call_path: str) -> str:
    """前端归一化路径里的 {} 换成占位符，便于与路由正则匹配。"""
    return call_path.replace("{}", PLACEHOLDER)


def match_route(method: str, call_path: str) -> tuple[bool, str]:
    """返回 (是否匹配, 说明)。"""
    call = _norm_call(call_path)
    for m, pa in routes:
        if m == method and re.match(to_regex(pa), call):
            return True, pa
    # 方法维度回退：只要前端用了错的 HTTP 方法就明确指出来
    for m, pa in routes:
        if re.match(to_regex(pa), call):
            return False, f"路径存在，但后端方法是 {m}，前端用了 {method}"
    return False, "后端没有这条路由"


# ---------------------------------------------------------------- 前端调用
PATH_RE = re.compile(r"""[`'"]([^`'"\r\n]*?/api/[^`'"\r\n]*)[`'"]""")
CALL_RE = re.compile(r"fetch\s*\(", re.I)
METHOD_RE = re.compile(r"""method\s*:\s*[`'"]([A-Z]+)[`'"]""")

total_calls = 0
problems: list[str] = []
checked_pairs: set[tuple[str, str]] = set()

TARGETS = [
    ("C 端 H5", ROOT / "web" / "c" / "app.js"),
    ("B 端后台", ROOT / "web" / "admin" / "app.js"),
    ("项目门户", ROOT / "web" / "index.html"),
]

for label, src_file in TARGETS:
    if not src_file.exists():
        p(f"\n【{label}】文件缺失：{src_file}")
        problems.append(f"{label}: 缺少 {src_file.name}")
        continue

    src = src_file.read_text(encoding="utf-8")

    # 收集所有含 /api/ 的字符串字面量（模板变量归一化）
    raw: set[str] = set()
    for m in PATH_RE.finditer(src):
        s = m.group(1)
        if "/api/" not in s or " " in s.strip():
            continue
        s = re.sub(r"\$\{[^}]*\}", "{}", s)
        # 拼接式：'/api/c/task/' + id   /  '/a' + id + '/b'
        s = re.sub(r"\+\s*[A-Za-z_$][\w.$\[\]']*\s*(\+)?", "{}", s)
        s = re.sub(r"['\"]\s*\+\s*", "", s)
        # 去掉查询串再比对（查询参数不影响路由匹配）
        if "?" in s:
            s = s.split("?")[0]
        s = s.strip()
        if s.endswith("/") and s.count("/") > 2 and not s.endswith("/api/"):
            s = s + "{}"
        if s in ("/api/admin", "/api/c", "/api"):
            continue
        raw.add(s)

    p(f"\n【{label}】{src_file.name}　接口引用 {len(raw)} 个")
    for r in sorted(raw):
        # 在源码中定位该字面量，向前 500 字符内找 method:
        pos = src.find(r.split("{}")[0] if "{}" in r else r)
        ctx = src[max(0, pos - 500): pos + 500] if pos >= 0 else ""
        methods = METHOD_RE.findall(ctx)
        method = methods[-1] if methods else "GET"
        total_calls += 1
        checked_pairs.add((method, r))
        ok, info = match_route(method, r)
        p(f"  {'OK ' if ok else 'BAD'} {method:<6} {r}")
        if not ok:
            problems.append(f"{label}: {method} {r} -> {info}")

    if "/api/" not in src:
        problems.append(f"{label}: 未发现任何 /api/ 调用，可能未对接后端")

# ---------------------------------------------------------------- 字段抽查
p("\n【响应字段抽查】前端是否使用了后端返回的关键字段")
FIELD_CHECKS = {
    "C 端 H5": (ROOT / "web" / "c" / "app.js", [
        "today_adventure", "nearby_nodes", "status_pill", "growth_total",
        "badge_count", "progress_percent", "current_tasks", "quest_card",
        "verify_mode", "target_count", "reward_preview", "lit_cities",
        "state_label", "suggestions", "chapters", "badges", "quick_actions",
    ]),
    "B 端后台": (ROOT / "web" / "admin" / "app.js", [
        "kpis", "trend", "funnel", "hot_nodes", "timeline", "completion_rate",
        "chapters_count", "nodes_count", "revenue_share", "cooperations",
        "age_distribution", "retention", "index_steps", "activation_rate",
        "status_label", "engine", "sources", "worldview", "links", "index_note",
    ]),
}
for label, (path, fields) in FIELD_CHECKS.items():
    src = path.read_text(encoding="utf-8") if path.exists() else ""
    hit = [f for f in fields if f in src]
    miss = [f for f in fields if f not in src]
    p(f"\n  [{label}] 使用 {len(hit)}/{len(fields)} 个关键字段")
    if miss:
        p(f"    未直接引用（可能由其它字段派生）: {', '.join(miss)}")

# ---------------------------------------------------------------- 未使用的后端接口
used_paths = {r for _m, r in checked_pairs}
unused = [f"{m} {pa}" for m, pa in all_api
          if not any(re.match(to_regex(r), pa) or r == pa for r in used_paths)]
p(f"\n【后端接口被前端使用情况】{len(all_api) - len(unused)}/{len(all_api)} 条被引用")
if unused:
    p("  未被前端调用（多为管理/调试接口，属正常）:")
    for u in unused:
        p(f"    · {u}")

# ---------------------------------------------------------------- 汇总
p("\n" + "=" * 78)
p("【结论】")
p(f"  前端接口引用：{total_calls} 处（去重 {len(checked_pairs)} 个「方法+路径」组合）")
p(f"  后端 /api/ 路由：{len(api_routes)} 条")
p(f"  契约问题：{len(problems)} 处")
for x in problems:
    p(f"    ✗ {x}")
if not problems:
    p("    ✓ 前端调用的每一个接口路径与方法，后端均存在")
p("=" * 78)

report = "\n".join(LINES)
out = ROOT / "tests" / "_contract.txt"
out.write_text(report, encoding="utf-8")
print(f"契约检查：{total_calls} 处调用 / {len(api_routes)} 条后端路由 / {len(problems)} 个问题")
for x in problems:
    print("  [BAD]", x)
if not problems:
    print("  [OK] 前端调用的接口后端全部存在")
print("报告：", out)
