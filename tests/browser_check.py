#!/usr/bin/env python
"""游伴 AI · 真实浏览器端到端验证（Playwright + Chromium）。

覆盖：
1. C 端 H5：开箱激活 → 五大页面（逐页内容断言）→ 节点剧情页 → 任务提交 → 换装
2. B 端后台：九大模块 + AI 生成向导（按真实 hash 路由逐页内容断言）→ 游客详情抽屉
3. 收集浏览器控制台错误与失败请求
4. 输出截图到 tests/shots/

脚本开头会把数据库重置为初始演示状态，因此结果确定、可重复。
运行后如需恢复，执行 `python run.py --reseed`。

用法：python tests/browser_check.py [base_url]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TMP = ROOT / "_tmp"
TMP.mkdir(exist_ok=True)
os.environ["TEMP"] = str(TMP)
os.environ["TMP"] = str(TMP)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8801"
SHOTS = ROOT / "tests" / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)

LINES: list[str] = []
CONSOLE_ERRORS: list[str] = []
FAILED_REQUESTS: list[str] = []
PASS = 0
FAIL = 0


def p(s: str = "") -> None:
    LINES.append(s)


def onboard_hidden(page) -> bool:
    """开箱引导是否真的已隐藏。

    前端用 `.onboard.hide { opacity:0; pointer-events:none }` 隐藏，
    Playwright 的 is_visible() 不考虑 opacity，因此这里检查 hide 类与 pointer-events。
    """
    return page.evaluate("""() => {
      const el = document.querySelector('#onboard');
      if (!el) return true;
      const cs = getComputedStyle(el);
      return el.classList.contains('hide') || cs.pointerEvents === 'none'
             || cs.display === 'none' || cs.opacity === '0';
    }""")


def check(label: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        p(f"  [OK ] {label}" + (f"   {extra}" if extra else ""))
    else:
        FAIL += 1
        p(f"  [BAD] {label}" + (f"   {extra}" if extra else ""))


def main() -> int:
    # 浏览器验证会断言「与原型一致的演示状态」（Lv.3 / 361 / 6-10 / 60% / 8-24 徽章），
    # 而 e2e_check.py 等脚本会写入数据库。为保证结果确定，这里先重置为初始演示状态。
    sys.path.insert(0, str(ROOT))
    try:
        from app import seed
        seed.seed_all(force=True)
        print("已重置为初始演示状态（seed_all(force=True)）")
    except Exception as exc:  # noqa: BLE001
        print(f"警告：重置演示数据失败（{type(exc).__name__}: {exc}），"
              f"演示状态相关断言可能失败")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        ctx = browser.new_context(viewport={"width": 1340, "height": 940},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        page = ctx.new_page()
        page.on("console", lambda m: CONSOLE_ERRORS.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: FAILED_REQUESTS.append(
            f"{r.method} {r.url.split('127.0.0.1:8801')[-1]} -> {r.failure}"))

        # ============================================================ C 端
        p("=" * 78)
        p("一、C 端 H5（儿童旅行潮玩小程序）")
        p("=" * 78)
        # ---- 阶段 A：开箱激活（新账号，杭州限定款） ----
        page.goto(f"{BASE}/c/", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(2000)

        check("开箱引导出现", page.locator("#onboard").is_visible())
        ob = page.inner_text("#onboard")
        check("开箱文案 TAKE IT", "TAKE IT" in ob)
        check("开箱文案「你愿意带我一起」", "你愿意带我一起" in ob)
        check("开箱含取名输入框", page.locator("#obName").count() > 0)
        check("开箱含激活码输入框", page.locator("#obCode").count() > 0)
        page.screenshot(path=str(SHOTS / "c-01-开箱激活.png"))

        page.fill("#obName", "小游")
        page.fill("#obCode", "YB-HZ-2026-0003")
        page.click("#obStart")
        page.wait_for_timeout(3200)
        check("激活后开箱引导隐藏", onboard_hidden(page))
        home_new = page.inner_text("#view-home")
        check("新账号首页渲染", len(home_new) > 200, f"{len(home_new)} 字符")
        check("新账号定位到杭州（激活码决定城市）",
              "杭州" in home_new or "西湖" in home_new,
              home_new[:70].replace("\n", " / "))
        check("新账号伙伴改名生效", "小游" in home_new)
        page.screenshot(path=str(SHOTS / "c-02-新账号首页.png"))

        # ---- 阶段 B：切回演示账号 user_id=1，核对与原型一致的状态 ----
        page.evaluate("localStorage.setItem('youban_user_id','1')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(3000)
        check("演示账号跳过了开箱引导", onboard_hidden(page))
        home = page.inner_text("#view-home")
        p(f"  [首页文本 {len(home)} 字符]")
        check("首页·定位景区", "大唐不夜城" in home or "西安" in home,
              home[:44].replace("\n", " "))
        check("首页·角色名", "阿游" in home)
        check("首页·今日冒险剧本", "大唐密令" in home)
        check("首页·章节与进度（原型 第3章 6/10 = 60%）",
              "第 3 章" in home and "密令现世" in home
              and "6/10" in home and "60%" in home,
              [ln for ln in home.split("\n") if "第 3 章" in ln])
        check("首页·不重复显示章节名与节点名（用地点）",
              "密令现世 · 密令现世" not in home,
              [ln for ln in home.split("\n") if "第 3 章" in ln])
        check("首页·等级 Lv.3 探索家", "Lv.3" in home or "探索家" in home)
        check("首页·快捷入口", "AI对话" in home and "任务" in home and "徽章" in home)
        check("首页·附近故事点", "故事点" in home)
        page.screenshot(path=str(SHOTS / "c-03-旅伴首页.png"))

        # 逐 Tab 强断言
        TAB_CASES = [
            ("explore", "#view-explore", ["我的故事地图", "CHINA STORY MAP",
                                          "点亮城市", "西安", "杭州", "贵州"], "c-04-探索地图"),
            ("chat", "#view-chat", ["阿游", "在线", "AI 智慧陪伴"], "c-05-AI对话"),
            ("story", "#view-story", ["大唐密令", "第 1 章", "长安初遇", "进行中",
                                      "第 3 / 5 章"], "c-06-剧本进度"),
            ("mine", "#view-mine", ["成长维度", "探索", "观察", "我的徽章", "Lv.3",
                                    "我的潮玩"], "c-07-我的"),
        ]
        for tab, sel, musts, shot in TAB_CASES:
            page.click(f'.tab[data-tab="{tab}"]')
            page.wait_for_timeout(1800)
            txt = page.inner_text(sel)
            missing = [m for m in musts if m not in txt]
            check(f"Tab「{tab}」内容完整", not missing,
                  f"{len(txt)} 字符" + (f"，缺少 {missing}" if missing else ""))
            check(f"Tab「{tab}」页面可见", page.locator(sel.replace("#view-", "#s-")).is_visible())
            page.screenshot(path=str(SHOTS / f"{shot}.png"))

        # 探索页点亮统计与地图三态
        explore = page.inner_text("#view-explore")
        check("探索页·点亮城市 5/12", "5/12" in explore)
        check("探索页·已点亮城市名", all(c in explore for c in ["西安", "北京", "杭州", "成都", "贵州"]))
        check("探索页·未解锁城市带锁标记", "🔒" in explore)
        check("探索页·三格统计", "点亮城市" in explore and "收集徽章" in explore
              and "完成故事" in explore)
        # 剧本页章节时间轴
        story_txt = page.inner_text("#view-story")
        check("剧本页·五章时间轴", all(f"第 {i} 章" in story_txt for i in range(1, 6)))
        check("剧本页·进行中标记", "进行中" in story_txt)
        check("剧本页·节点地点", "大雁塔" in story_txt and "大唐不夜城" in story_txt)
        # 我的页徽章墙与成长
        mine = page.inner_text("#view-mine")
        check("我的页·徽章墙 8/24", "8 / 24" in mine, "已收集/总数")
        check("我的页·成长五维度", all(d in mine for d in ["探索", "创造", "观察", "知识", "勇气"]))
        check("我的页·成长值 361", "361" in mine)
        check("我的页·潮玩换装", "我的潮玩" in mine and "换装" in mine)
        check("我的页·设置列表", "我的旅行地图" in mine and "成就与称号" in mine)

        # 换装抽屉（严格限定在可见的「我的」页内点击）
        page.click('.tab[data-tab="mine"]')
        page.wait_for_timeout(1600)
        dress = page.locator("#mineDress:visible")
        if dress.count() == 0:
            dress = page.locator("#view-mine").get_by_text("换装").first
        if dress.count():
            dress.click()
            page.wait_for_timeout(2200)
            page.screenshot(path=str(SHOTS / "c-07-换装抽屉.png"))
            drawer_open = page.locator("#drawerMask.show").count() > 0
            check("换装抽屉打开", drawer_open,
                  page.inner_text("#drawerBody")[:40].replace("\n", " ") if drawer_open else "")
            if drawer_open:
                items = page.locator("#drawerBody .dress-item[data-item]")
                check("换装抽屉含装扮列表", items.count() > 0, f"{items.count()} 项")
                if items.count():
                    items.nth(1).click()
                    page.wait_for_timeout(2000)
                    page.screenshot(path=str(SHOTS / "c-08b-换装完成.png"))
                    check("换装后当前装扮更新",
                          page.locator("#drawerBody .dress-item.on").count() > 0)
        else:
            check("换装入口存在", False)

        # 关闭抽屉，避免遮挡后续点击
        if page.locator("#drawerBack").count():
            page.locator("#drawerBack").click()
            page.wait_for_timeout(900)

        # 节点剧情页（限定在可见的首页内点击故事点）
        page.click('.tab[data-tab="home"]')
        page.wait_for_timeout(1600)
        entry = page.locator("#view-home [data-node]:visible").first
        if entry.count() == 0:
            entry = page.locator("#view-home .sp-item:visible").first
        if entry.count():
            entry.click()
            page.wait_for_timeout(2500)
            ntxt = page.inner_text("body")
            check("节点剧情页打开", "剧情" in ntxt or "任务" in ntxt, f"{len(ntxt)} 字符")
            page.screenshot(path=str(SHOTS / "c-08-节点剧情页.png"))
            inputs = page.locator("input[type=text]:visible, textarea:visible")
            if inputs.count():
                inputs.first.fill("莲花")
            for j in range(page.locator("button:visible").count()):
                b = page.locator("button:visible").nth(j)
                label = (b.inner_text() or "").strip()
                if any(k in label for k in ["提交", "我已到达", "拍摄完成", "确认", "完成"]):
                    b.click()
                    page.wait_for_timeout(2500)
                    break
            page.screenshot(path=str(SHOTS / "c-09-任务结果.png"))
            res = page.inner_text("body")
            check("任务提交有反馈", any(k in res for k in ["成长", "经验", "通过", "再试", "观察", "徽章"]))
        else:
            check("节点剧情页入口存在", False, "未找到可点击的故事点")

        # 关闭节点子页，否则它作为全屏子页会挡住底部 Tab（返回箭头是设计上的退出方式）
        if page.locator("#nodeBack").count():
            page.click("#nodeBack")
            page.wait_for_timeout(1400)
        check("节点子页可关闭（返回箭头）", page.locator("#page-node.show").count() == 0)

        # ============================================================ 家长模式
        p("")
        p("=" * 78)
        p("一之补、C 端 · 家长模式（成长报告）")
        p("=" * 78)

        # 从「我的」页进入
        page.click('.tab[data-tab="mine"]')
        page.wait_for_timeout(1600)
        check("「我的」页有家长模式入口", page.locator("#mineParentHint").count() > 0,
              (page.inner_text("#mineParentHint")[:30].replace("\n", " ")
               if page.locator("#mineParentHint").count() else ""))
        page.screenshot(path=str(SHOTS / "c-30-我的页家长入口.png"))

        entry = page.locator("#mineParentHint:visible")
        if entry.count() == 0:
            entry = page.locator("#view-mine").get_by_text("家长模式").first
        entry.click()
        page.wait_for_timeout(3500)

        check("家长模式子页打开", page.locator("#page-parent.show").count() > 0)
        check("  导航标题为「家长模式」",
              page.inner_text("#parentNavTitle").strip() == "家长模式",
              page.inner_text("#parentNavTitle").strip())
        check("  导航副标题为「成长报告」",
              "成长报告" in page.inner_text("#parentNavSub"))
        page.screenshot(path=str(SHOTS / "c-31-家长模式-概览.png"), full_page=True)

        body = page.inner_text("#parentBody")
        check("概览渲染内容", len(body) > 500, f"{len(body)} 字符")

        # —— 与真实接口逐项核对（最强断言） ——
        api_sum = page.evaluate(
            "async () => (await (await fetch('/api/c/parent/summary?user_id=1')).json())")

        # ① 孩子档案
        hero = page.inner_text(".pr-hero")
        ch = api_sum["child"]
        check("① 档案卡含昵称", ch["nickname"] in hero, ch["nickname"])
        check("① 档案卡含等级", f"Lv.{ch['level']}" in hero and ch["level_name"] in hero,
              f"Lv.{ch['level']} {ch['level_name']}")
        check("① 档案卡含成长值", str(ch["growth_total"]) in hero, str(ch["growth_total"]))
        check("① 档案卡含旅行天数", f"已旅行 {ch['travel_days']} 天" in hero,
              f"已旅行 {ch['travel_days']} 天")

        # ② 距离下一级（用后端 floor/ceil/percent 核对）
        nl = api_sum["next_level"]
        nxt = page.inner_text(".pr-next")
        check("② 距离下一级文案", f"还差" in nxt and str(nl["need"]) in nxt
              and nl["next_name"] in nxt,
              f"还差 {nl['need']} 成长值 → {nl['next_name']}")
        bar_w = page.evaluate(
            "() => {const i=document.querySelector('.pr-next .pr-track i');"
            "return i ? i.style.width : null}")
        check("② 本级进度条宽度 = 接口 percent",
              bar_w is not None and abs(float(bar_w.replace("%", "")) - nl["percent"]) <= 1,
              f"UI {bar_w} vs API {nl['percent']}%")
        check("② 显示本级进度百分比", f"{nl['percent']}%" in nxt, f"{nl['percent']}%")

        # ③ 成长概览 6 指标
        metrics = page.locator(".pr-metric")
        check("③ 成长概览 6 个指标", metrics.count() == 6, f"{metrics.count()} 个")
        ov = {o["key"]: o for o in api_sum["overview"]}
        mtxt = page.inner_text(".pr-metrics")
        check("③ 走过城市 5 / 12 座",
              f"{ov['cities']['value']} / {ov['cities']['of']}" in mtxt,
              f"{ov['cities']['value']} / {ov['cities']['of']}")
        check("③ 完成的剧本 = 接口值 / 非草稿总数",
              f"{ov['stories']['value']} / {ov['stories']['of']}" in mtxt,
              f"{ov['stories']['value']} / {ov['stories']['of']}")
        check("③ 徽章 = 接口值 / 总数",
              f"{ov['badges']['value']} / {ov['badges']['of']}" in mtxt,
              f"{ov['badges']['value']} / {ov['badges']['of']}")
        check("③ 六项标签齐全",
              all(o["label"] in mtxt for o in api_sum["overview"]),
              "、".join(o["label"] for o in api_sum["overview"]))

        # ④ 成长画像
        note = page.inner_text(".pr-note")
        check("④ 成长画像文字 = 接口 growth_note",
              api_sum["growth_note"] in note, note[:46])
        bars = page.locator(".pr-bar-row")
        check("④ 五维条形图 5 条", bars.count() == 5, f"{bars.count()} 条")
        first_bar = page.evaluate(
            "() => {const i=document.querySelector('.pr-bar-row .pr-track i');"
            "return i ? i.style.width : null}")
        check("④ 首条宽度 = 对应维度值",
              first_bar is not None and
              abs(float(first_bar.replace("%", "")) - api_sum["growth"][0]["value"]) <= 1,
              f"UI {first_bar} vs API {api_sum['growth'][0]['value']}")

        # ⑤ 近 7 天活跃度
        wk = page.locator(".pr-wcol")
        check("⑤ 近 7 天 7 根柱", wk.count() == 7, f"{wk.count()} 根")
        wnote = page.inner_text(".pr-week-note")
        check("⑤ 本周任务数 = 接口 weekly.total",
              str(api_sum["weekly"]["total"]) in wnote, wnote.replace("\n", " "))
        labels_ui = page.evaluate(
            "() => Array.from(document.querySelectorAll('.pr-wl')).map(e=>e.textContent)")
        check("⑤ 柱标签 = 接口 weekly.labels",
              labels_ui == api_sum["weekly"]["labels"], str(labels_ui))

        # ⑥ 近期徽章
        bmini = page.locator(".pr-bmini")
        check("⑥ 近期徽章条", bmini.count() == len(api_sum["badges_recent"]),
              f"UI {bmini.count()} / API {len(api_sum['badges_recent'])}")
        if api_sum["badges_recent"]:
            rar = api_sum["badges_recent"][0].get("rarity_label")
            check("⑥ 稀有度用中文标签", (rar or "") in page.inner_text(".pr-bstrip"),
                  f"第一枚稀有度 {rar}")

        # ⑦ 剧本进度行（可点进报告）
        scn = page.locator(".pr-scn[data-report]")
        check("⑦ 剧本进度行数 = 接口 scenarios",
              scn.count() == len(api_sum["scenarios"]),
              f"UI {scn.count()} / API {len(api_sum['scenarios'])}")
        scn_txt = page.inner_text(".pr-scn >> nth=0")
        s0 = api_sum["scenarios"][0]
        check("⑦ 首行含剧本名与状态", s0["title"] in scn_txt and s0["status_label"] in scn_txt,
              f"{s0['title']} [{s0['status_label']}]")
        place_lines = [ln for ln in scn_txt.split("\n") if "西安" in ln]
        check("⑦ 地点不重复渲染（无「西安 · 西安」）",
              "西安 · 西安" not in scn_txt, place_lines[:2])
        check("⑦ 地点保留了景区名（不能只剩城市）",
              any("大唐不夜城" in ln or "西安 · " in ln and len(ln) > 8
                  for ln in place_lines),
              place_lines[:2])
        check("⑦ 地点文案与接口 place_label 一致",
              (s0.get("place_label") or "") in scn_txt, s0.get("place_label"))

        # ⑧ 亲子建议
        cards = page.locator(".pr-advice .pr-card")
        check("⑧ 亲子建议卡 = 接口 suggestions",
              cards.count() == len(api_sum["suggestions"]),
              f"UI {cards.count()} / API {len(api_sum['suggestions'])}")
        if api_sum["suggestions"]:
            check("⑧ 首卡含维度标签与建议",
                  api_sum["suggestions"][0]["label"] in page.inner_text(".pr-advice") and
                  api_sum["suggestions"][0]["advice"][:20] in page.inner_text(".pr-advice"),
                  api_sum["suggestions"][0]["title"])
        check("⑧ 页脚标注数据来源", "家长模式" in page.inner_text(".pr-foot"))

        # —— 进入单次旅行报告 ——
        scn.nth(0).click()
        page.wait_for_timeout(3500)
        api_rep = page.evaluate(
            "async () => (await (await fetch('/api/c/parent/report?user_id=1&scenario_id="
            + str(s0["scenario_id"]) + "')).json())")
        page.screenshot(path=str(SHOTS / "c-32-家长模式-旅行报告.png"), full_page=True)

        check("报告页导航标题 = 剧本名",
              page.inner_text("#parentNavTitle").strip() == api_rep["scenario"]["title"],
              page.inner_text("#parentNavTitle").strip())
        check("报告页有进度环", page.locator(".pr-ring").count() > 0)
        dash = page.evaluate(
            "() => {const c=document.querySelectorAll('.pr-ring circle')[1];"
            "return c ? c.getAttribute('stroke-dasharray') : null}")
        exp_pct = api_rep["summary"]["percent"]
        ring_pct = None
        if dash:
            try:
                got = float(dash.split(" ")[0])
                total_c = float(dash.split(" ")[1])
                ring_pct = round(got / total_c * 100)
            except (ValueError, IndexError):
                ring_pct = None
        check("  进度环角度 = 接口 percent",
              ring_pct is not None and abs(ring_pct - exp_pct) <= 1,
              f"环 {ring_pct}% vs API {exp_pct}%")
        check("  报告页显示百分比", f"{exp_pct}%" in page.inner_text("#parentBody"))

        stats = page.locator(".pr-stat")
        sm = api_rep["summary"]
        check("  4 个小指标", stats.count() == 4, f"{stats.count()} 个")
        stxt = page.inner_text(".pr-stats")
        check("  剧情点 = visited/total",
              f"{sm['visited']}/{sm['total']}" in stxt, f"{sm['visited']}/{sm['total']}")
        check("  完成任务数 = 接口值", str(sm["tasks_done"]) in stxt, str(sm["tasks_done"]))
        check("  时长 = 接口 minutes", str(sm["minutes"]) in stxt, str(sm["minutes"]))

        chap = page.locator(".pr-chap")
        check("  章节数 = 接口 chapters", chap.count() == len(api_rep["chapters"]),
              f"UI {chap.count()} / API {len(api_rep['chapters'])}")
        done_ch = page.locator(".pr-chap.done")
        exp_done = len([c for c in api_rep["chapters"] if c["state"] == "done"])
        check("  已完成章节数一致", done_ch.count() == exp_done,
              f"UI {done_ch.count()} / API {exp_done}")
        node_done_ui = page.locator(".pr-node.done")
        exp_node_done = len([n for c in api_rep["chapters"] for n in c["nodes"]
                             if n["state"] == "done"])
        check("  已完成节点打勾一致", node_done_ui.count() == exp_node_done,
              f"UI {node_done_ui.count()} / API {exp_node_done}")

        ti = page.locator(".pr-ti")
        check("  时间轴条数 = 接口 trail", ti.count() == len(api_rep["trail"]),
              f"UI {ti.count()} / API {len(api_rep['trail'])}")
        kinds_ui = page.evaluate(
            "() => Array.from(document.querySelectorAll('.pr-ti')).map(e=>"
            "e.className.replace('pr-ti','').trim())")
        exp_kinds = [("task" if t["type"] == "task" and t.get("passed") else
                      "fail" if t["type"] == "task" else "visit") for t in api_rep["trail"]]
        check("  时间轴三类状态与接口一致", kinds_ui == exp_kinds,
              f"UI {sorted(set(kinds_ui))} / API {sorted(set(exp_kinds))}")

        kc = page.locator(".pr-knowcard")
        check("  知识点卡 = 接口 knowledge", kc.count() == len(api_rep["knowledge"]),
              f"UI {kc.count()} / API {len(api_rep['knowledge'])}")
        if api_rep["knowledge"]:
            k0 = api_rep["knowledge"][0]
            ktxt = page.inner_text(".pr-know")
            check("  知识点含分类标签与来源节点",
                  k0["category_label"] in ktxt and (k0["node"] or "") in ktxt,
                  f"[{k0['category_label']}] {k0['title']} ← {k0['node']}")

        asks = page.locator(".pr-ask")
        check("  回家提问 3 个", asks.count() == len(api_rep["questions"]) == 3,
              f"UI {asks.count()} / API {len(api_rep['questions'])}")
        check("  提问卡有 ? 图标", page.locator(".pr-ask .pa-q").count() == asks.count())
        if api_rep["questions"]:
            check("  首个提问文本与接口一致",
                  api_rep["questions"][0][:24] in page.inner_text(".pr-asks"),
                  api_rep["questions"][0][:40])

        gains = page.locator(".pr-gain")
        check("  本次成长标签 = 接口 growth_gain 维度数",
              gains.count() == len(api_rep["growth_gain"]),
              f"UI {gains.count()} / API {len(api_rep['growth_gain'])}")
        check("  页脚标注", "家长模式" in page.inner_text("#parentBody"))

        # —— 返回链路 ——
        page.click("#prBackSummary")
        page.wait_for_timeout(2200)
        check("「← 返回成长概览」回到概览",
              page.inner_text("#parentNavTitle").strip() == "家长模式",
              page.inner_text("#parentNavTitle").strip())
        page.click("#parentBack")
        page.wait_for_timeout(1600)
        check("返回箭头关闭家长模式", page.locator("#page-parent.show").count() == 0)
        check("  关闭后回到「我的」Tab", page.locator("#s-mine").is_visible())

        # —— 故障注入：接口 500 时必须有中文提示 + 重试，且不白屏 ——
        def fail_parent_route(route):
            route.fulfill(status=500, content_type="application/json; charset=utf-8",
                          body='{"ok":false,"error":"服务器开小差了"}')

        page.route("**/api/c/parent/summary*", fail_parent_route)
        page.locator("#mineParentHint").click()
        page.wait_for_timeout(3000)
        fail_txt = page.inner_text("#parentBody")
        check("家长接口失败：给出中文错误提示",
              page.locator("#parentBody").count() > 0 and len(fail_txt) > 0,
              fail_txt[:60].replace("\n", " "))
        check("  失败时不是白屏（有可见内容）", len(fail_txt.strip()) > 5, f"{len(fail_txt)} 字符")
        retry = page.locator("#parentBody button, #parentBody [id*=etry]")
        check("  提供了重试入口", retry.count() > 0, f"{retry.count()} 个按钮")
        page.screenshot(path=str(SHOTS / "c-33-家长模式-接口失败.png"))

        # 恢复接口后点重试，应能正常加载
        page.unroute("**/api/c/parent/summary*")
        if retry.count():
            retry.first.click()
            page.wait_for_timeout(3500)
            ok_txt = page.inner_text("#parentBody")
            check("  点重试后恢复正常", len(ok_txt) > 500 and "成长概览" in ok_txt,
                  f"{len(ok_txt)} 字符")
        page.click("#parentBack")
        page.wait_for_timeout(1400)

        # —— 故障注入：报告 404（剧本文案错误）应显示后端中文错误 ——
        page.route("**/api/c/parent/report*", lambda route: route.fulfill(
            status=404, content_type="application/json; charset=utf-8",
            body='{"ok":false,"error":"剧本不存在"}'))
        page.locator("#mineParentHint").click()
        page.wait_for_timeout(3000)
        page.locator(".pr-scn[data-report]").first.click()
        page.wait_for_timeout(2800)
        rep_fail = page.inner_text("#parentBody")
        check("报告 404 显示后端中文错误", "剧本不存在" in rep_fail or "失败" in rep_fail,
              rep_fail[:60].replace("\n", " "))
        page.screenshot(path=str(SHOTS / "c-34-家长模式-报告失败.png"))
        page.unroute("**/api/c/parent/report*")
        page.click("#parentBack")
        page.wait_for_timeout(1200)

        # ============================================================ B 端
        p("")
        p("=" * 78)
        p("二、B 端 SaaS 运营台（九大模块 + AI 向导）")
        p("=" * 78)
        page.goto(f"{BASE}/admin/", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(2500)

        # 真实 hash 路由：dashboard/scenarios/editor/tasks/materials/visitors/iptoys/analytics/park
        MODULE_CASES = [
            ("dashboard", "page-dashboard", ["今日入园游客", "12,486", "剧本完成率",
                                             "剧情节点热度榜", "实时动态"], "a-1-数据看板"),
            ("scenarios", "page-scenarios", ["剧本列表", "大唐密令", "苗岭宝藏",
                                             "已上线", "完成率"], "a-2-剧本管理"),
            ("editor", "page-editor", ["节点属性", "AI 生成", "剧情文案"], "a-3-剧情编辑器"),
            ("tasks", "page-tasks", ["任务列表", "观察", "寻找", "拍摄", "解谜"], "a-4-任务中心"),
            ("materials", "page-materials", ["历史典故", "建筑风貌", "非遗技艺",
                                             "128 条素材", "96 条素材",
                                             "解析中", "已入库"], "a-5-内容素材库"),
            ("visitors", "page-visitors", ["游客", "小小探险家", "成长值"], "a-6-游客管理"),
            ("iptoys", "page-iptoys", ["阿游", "城市限定款", "SKU", "库存"], "a-7-潮玩IP"),
            ("analytics", "page-analytics", ["用户转化漏斗", "营收结构",
                                             "用户留存", "286,400"], "a-8-数据分析"),
            ("park", "page-park", ["景区基础信息", "收益分账", "西安"], "a-9-景区与联名"),
            ("observability", "page-observability",
             ["运行指标", "总请求数", "平均耗时", "错误率", "已运行时长",
              "端点", "慢请求", "最近请求", "业务计数"], "a-16-运行指标"),
        ]
        for route, page_id, musts, shot in MODULE_CASES:
            # 用点击左侧导航（真实用户路径）
            nav = page.locator(f'.nav-item[data-page="{route}"]')
            if nav.count():
                nav.first.click()
            else:
                page.goto(f"{BASE}/admin/#{route}", wait_until="domcontentloaded")
            page.wait_for_timeout(2200)
            visible = page.locator(f"#{page_id}").is_visible()
            txt = page.inner_text(f"#{page_id}") if visible else ""
            missing = [m for m in musts if m not in txt]
            check(f"模块「{route}」可见", visible)
            check(f"模块「{route}」内容完整", visible and not missing,
                  f"{len(txt)} 字符" + (f"，缺少 {missing}" if missing else ""))
            page.screenshot(path=str(SHOTS / f"{shot}.png"))

        # 游客详情抽屉（真实点击表格行）
        page.locator('.nav-item[data-page="visitors"]').first.click()
        page.wait_for_timeout(2200)
        rows = page.locator("#page-visitors tbody tr")
        p(f"  游客表格行数: {rows.count()}")
        check("游客表格有数据", rows.count() > 0)
        if rows.count():
            rows.first.click()
            page.wait_for_timeout(2200)
            page.screenshot(path=str(SHOTS / "a-10-游客详情抽屉.png"))
            drawer = page.inner_text("body")
            check("游客详情抽屉打开", page.locator("#overlay.show").count() > 0)
            check("游客详情含成长/徽章/轨迹",
                  any(k in drawer for k in ["成长", "徽章", "轨迹"]))
            # 关闭抽屉（ESC），否则遮罩会拦截后续点击
            page.keyboard.press("Escape")
            page.wait_for_timeout(900)
            check("游客抽屉可关闭", page.locator("#overlay.show").count() == 0)

        # 剧情编辑器：点击节点 + 拖拽
        page.locator('.nav-item[data-page="editor"]').first.click()
        page.wait_for_timeout(2500)
        nodes = page.locator("#page-editor .sc-node")
        p(f"  编辑器节点数: {nodes.count()}")
        check("编辑器渲染剧情节点", nodes.count() >= 5)
        if nodes.count():
            nodes.nth(2).click()
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / "a-11-编辑器选中节点.png"))
            check("编辑器节点可选中", len(page.inner_text("#page-editor")) > 200)

        # AI 生成向导（真实入口按钮）
        page.goto(f"{BASE}/admin/#scenarios", wait_until="domcontentloaded")
        page.wait_for_timeout(2200)
        ai_btn = None
        for j in range(page.locator("#page-scenarios button").count()):
            b = page.locator("#page-scenarios button").nth(j)
            if "AI" in (b.inner_text() or ""):
                ai_btn = b
                break
        if ai_btn:
            ai_btn.click()
        else:
            page.goto(f"{BASE}/admin/#ai-wizard", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOTS / "a-12-AI向导-1选景区.png"))
        wiz = page.inner_text("#wizard") if page.locator("#wizard").count() else ""
        check("AI 向导打开", page.locator("#wizard.show").count() > 0, f"{len(wiz)} 字符")
        check("AI 向导·标题", "AI Story Engine" in wiz and "生成向导" in wiz)
        check("AI 向导·第1步选景区", "第 1 步" in wiz and "选择景区" in wiz)
        check("AI 向导·引擎状态", "离线规则引擎" in wiz or "未接大模型" in wiz)
        check("AI 向导·景区档案", "地理坐标" in wiz and "围栏半径" in wiz)
        check("AI 向导·数据链路", "数据沉淀" in wiz or "AI STORY PLATFORM" in wiz)

        # 走到第 3 步核对年龄层三选一
        def click_next():
            for j in range(page.locator("#wizard button:visible").count()):
                b = page.locator("#wizard button:visible").nth(j)
                if "下一步" in (b.inner_text() or ""):
                    b.click()
                    return True
            return False

        if click_next():
            page.wait_for_timeout(2200)
            step2 = page.inner_text("#wizard")
            check("AI 向导·第2步生成模式", "生成模式" in step2)
            check("AI 向导·五种模式", sum(
                1 for m in ["生成主线", "生成任务", "生成对话", "生成奖励", "全剧本"]
                if m in step2) >= 4, step2[:80].replace("\n", " / "))
            page.screenshot(path=str(SHOTS / "a-13-AI向导-2生成模式.png"))
            if click_next():
                page.wait_for_timeout(2200)
                step3 = page.inner_text("#wizard")
                check("AI 向导·第3步参数配置", "参数配置" in step3 or "年龄层" in step3)
                # 界面渲染为「4-8 岁」「8-12 岁」「12 岁+」，注意 12+ 中间有空格
                check("AI 向导·三层年龄玩法",
                      all(a in step3 for a in ["4-8 岁", "8-12 岁", "12 岁+"]),
                      [ln for ln in step3.split("\n") if "岁" in ln][:4])
                check("AI 向导·玩法副标题",
                      "亲子探索" in step3 and "少年冒险" in step3 and "沉浸剧本" in step3)
                check("AI 向导·参数预览", "本次生成参数预览" in step3)
                page.screenshot(path=str(SHOTS / "a-14-AI向导-3参数配置.png"))

                # 真正执行一次生成，验证向导端到端可用
                gen_btn = None
                for j in range(page.locator("#wizard button:visible").count()):
                    b = page.locator("#wizard button:visible").nth(j)
                    if "开始生成" in (b.inner_text() or ""):
                        gen_btn = b
                        break
                if gen_btn:
                    gen_btn.click()
                    page.wait_for_timeout(6000)
                    page.screenshot(path=str(SHOTS / "a-15-AI向导-4生成结果.png"))
                    res = page.inner_text("#wizard")
                    check("AI 向导·生成完成并展示结果", len(res) > 500, f"{len(res)} 字符")
                    check("AI 向导·结果含世界观", "世界观" in res)
                    check("AI 向导·结果含章节", "章" in res and ("章节" in res or "第 1 章" in res))
                    check("AI 向导·结果含节点", "节点" in res or "STORY NODE" in res)
                    check("AI 向导·结果含奖励体系", "奖励" in res or "徽章" in res)
                    check("AI 向导·结果含素材来源", "素材" in res)
                else:
                    check("AI 向导·有「开始生成」按钮", False)
        else:
            check("AI 向导·可进入下一步", False, "未找到「下一步」按钮")

        # ---- 运行指标模块（深入断言 + 与接口对账） ----
        page.locator('.nav-item[data-page="observability"]').first.click()
        page.wait_for_timeout(3000)
        ob = page.locator("#page-observability")
        check("运行指标模块可见", ob.is_visible())
        api_obs = page.evaluate(
            "async () => (await (await fetch('/api/admin/observability')).json())")

        kpis = page.locator("#page-observability .kpi")
        check("  4 个 KPI 卡", kpis.count() == 4, f"{kpis.count()} 个")
        kpi_txt = page.inner_text("#page-observability")
        rq = api_obs["requests"]
        check("  总请求数 = 接口值", str(rq["requests_total"]) in kpi_txt,
              str(rq["requests_total"]))
        check("  慢请求阈值来自接口",
              str(int(rq["slow_threshold_ms"])) in kpi_txt, f"{rq['slow_threshold_ms']}ms")
        # 运行时长必须是中文可读形式，而不是裸秒数
        dur = page.evaluate("""() => {
          const cards = Array.from(document.querySelectorAll('#page-observability .kpi'));
          const c = cards.find(e => e.textContent.includes('已运行') || e.textContent.includes('运行时长'));
          return c ? c.querySelector('.k-val').textContent.trim() : null;
        }""")
        check("  已运行时长格式化为中文（非裸秒数）",
              dur is not None and ("秒" in dur or "分" in dur or "小时" in dur or "天" in dur),
              f"「{dur}」")

        # 端点表：与接口逐值对账 + 排序
        rows = page.locator("#page-observability tbody tr")
        check("  端点表行数 = 接口 endpoints",
              rows.count() == len(rq["endpoints"]),
              f"UI {rows.count()} / API {len(rq['endpoints'])}")
        rows_txt = page.inner_text("#page-observability tbody")
        check("  端点路径已归一化（/api/c/task/{id}）",
              "/api/c/task/{id}" in rows_txt or "{id}" in rows_txt,
              "含 {id} 占位")
        counts_before = page.evaluate(
            "() => document.querySelectorAll('#page-observability tbody tr').length")
        # 点「调用次数」表头排序（默认已按次数降序，再点一次应反转）
        th = page.locator("#page-observability th.ob-th-sort")
        check("  存在可排序表头", th.count() >= 3, f"{th.count()} 个")
        if th.count():
            first_col_before = page.evaluate(
                "() => document.querySelector('#page-observability tbody tr td:nth-child(3)')"
                ".textContent.trim()")
            th.first.click()
            page.wait_for_timeout(900)
            first_col_after = page.evaluate(
                "() => document.querySelector('#page-observability tbody tr td:nth-child(3)')"
                ".textContent.trim()")
            check("  点击表头排序生效（首行变化）",
                  first_col_before != first_col_after,
                  f"{first_col_before} → {first_col_after}")
            counts_after = page.evaluate(
                "() => document.querySelectorAll('#page-observability tbody tr').length")
            check("  排序不重新请求（行数不变）", counts_before == counts_after)
            page.screenshot(path=str(SHOTS / "a-17-运行指标-排序.png"))

        # 慢请求 Top5 / 最近请求 / 业务计数
        check("  慢请求 Top5 区域", page.locator("#page-observability .ob-bars").count() > 0)
        check("  最近请求列表", page.locator("#page-observability .ob-list").count() > 0)
        biz = page.locator("#page-observability .ob-stat")
        check("  业务计数项数 = 接口 business 字段数",
              biz.count() >= len(api_obs["business"]),
              f"UI {biz.count()} / API {len(api_obs['business'])}")
        check("  业务计数用中文标签（无英文裸字段名）",
              "materials_indexed" not in kpi_txt and "task_pass_rate" not in kpi_txt
              and "已入库素材" in kpi_txt,
              "已入库素材 / 任务通过率 等中文标签")
        check("  业务计数数值与接口一致（景区 12）",
              str(api_obs["business"]["parks"]) in kpi_txt,
              str(api_obs["business"]["parks"]))
        page.screenshot(path=str(SHOTS / "a-18-运行指标-业务计数.png"))

        # 刷新按钮
        n_before = page.evaluate(
            "async () => (await (await fetch('/api/admin/observability')).json())"
            ".requests.requests_total")
        page.locator("#btnObsRefresh").click()
        page.wait_for_timeout(2200)
        check("  刷新按钮可用且不报错", ob.is_visible() and
              page.locator("#page-observability .state-box").count() == 0,
              f"刷新前总请求 {n_before}")

        # 自动刷新开关：开启后离开路由必须停止
        sw = page.locator("#obAuto")
        if sw.count():
            sw.click()
            page.wait_for_timeout(800)
            on_cls = page.evaluate("() => document.querySelector('#obAuto').className")
            check("  自动刷新开关可开启", "on" in on_cls, on_cls)
            req_seen = page.evaluate("""async () => {
              let n = 0;
              const of = window.fetch;
              window.fetch = function(u, o) {
                if (String(u).includes('/observability')) n++;
                return of.apply(this, arguments);
              };
              await new Promise(r => setTimeout(r, 6200));
              window.fetch = of;
              return n;
            }""")
            check("  开启后每 5 秒确实自动请求", req_seen >= 1, f"6.2 秒内 {req_seen} 次")
            # 切到别的模块
            page.locator('.nav-item[data-page="dashboard"]').first.click()
            page.wait_for_timeout(900)
            off_seen = page.evaluate("""async () => {
              let n = 0;
              const of = window.fetch;
              window.fetch = function(u, o) {
                if (String(u).includes('/observability')) n++;
                return of.apply(this, arguments);
              };
              await new Promise(r => setTimeout(r, 6200));
              window.fetch = of;
              return n;
            }""")
            check("  离开路由后自动刷新停止", off_seen == 0, f"6.2 秒内 {off_seen} 次")
            back_cls = page.evaluate("() => document.querySelector('#obAuto').className")
            check("  开关已复位为关闭", "on" not in back_cls, back_cls)
        else:
            check("  自动刷新开关存在", False)

        # 运行指标失败态
        page.route("**/api/admin/observability*", lambda route: route.fulfill(
            status=500, content_type="application/json; charset=utf-8",
            body='{"ok":false,"error":"服务器开小差了"}'))
        page.locator('.nav-item[data-page="observability"]').first.click()
        page.wait_for_timeout(3000)
        ob_fail = page.inner_text("#page-observability")
        check("  运行指标失败：有提示且不白屏", len(ob_fail.strip()) > 5, f"{len(ob_fail)} 字符")
        page.screenshot(path=str(SHOTS / "a-19-运行指标-失败态.png"))
        page.unroute("**/api/admin/observability*")

        # ============================================================ 门户
        p("")
        p("=" * 78)
        p("三、项目门户")
        p("=" * 78)
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)
        h = page.inner_text("body")
        check("门户加载", len(h) > 400, f"{len(h)} 字符")
        check("门户品牌主张", "带着它，去发现世界" in h)
        check("门户三个入口", "/c/" in page.content() and "/admin/" in page.content())
        check("门户统计已由 API 填充", "12" in h and "439" in h or "441" in h)
        check("门户 AI 引擎区块", "AI Story Engine" in h or "离线规则引擎" in h)
        page.screenshot(path=str(SHOTS / "p-门户.png"), full_page=True)

        browser.close()

    # ============================================================ 汇总
    p("")
    p("=" * 78)
    p("【控制台错误】")
    for e in (CONSOLE_ERRORS[:40] or ["  无"]):
        p(f"  {e}")
    p("")
    p("【失败的网络请求】")
    for r in (FAILED_REQUESTS[:40] or ["  无"]):
        p(f"  {r}")
    p("")
    p("=" * 78)
    p(f"【结论】通过 {PASS} 项，失败 {FAIL} 项")
    p(f"  控制台错误 {len(CONSOLE_ERRORS)} 条 · 失败请求 {len(FAILED_REQUESTS)} 条")
    p(f"  截图 {len(list(SHOTS.glob('*.png')))} 张 -> {SHOTS}")
    p("=" * 78)

    (ROOT / "tests" / "_browser.txt").write_text("\n".join(LINES), encoding="utf-8")

    # 清理临时目录（Playwright 的浏览器临时文件）
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)

    print(f"浏览器验证：通过 {PASS}，失败 {FAIL}；"
          f"控制台错误 {len(CONSOLE_ERRORS)}，失败请求 {len(FAILED_REQUESTS)}")
    for e in CONSOLE_ERRORS[:12]:
        print("  [console]", e)
    for r in FAILED_REQUESTS[:12]:
        print("  [request]", r)
    print("截图：", SHOTS)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
