"""游伴 AI · AI Story Engine（景区故事引擎）。

对应商业计划书 P12：
    景区输入（历史 / 人物 / 建筑 / 非遗 / 传说 / 自然 / 地理）
        ↓ AI 生成
    世界观 / 主线 / 剧情节点 / 任务 / 对话 / 知识内容 / 奖励体系
        ↓
    AI 景区剧本游

实现策略：
- **默认走内置离线规则引擎**：基于数据库中的真实景区素材（materials）做结构化拼装，
  无需联网、无需 API Key 即可完整演示，且生成内容确实来源于该景区资料。
- **可选接入真实大模型**：设置 YOUBAN_LLM_BASE_URL / YOUBAN_LLM_API_KEY /
  YOUBAN_LLM_MODEL 后自动切换为 OpenAI 兼容接口调用（见 config.py）。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .. import db
from ..config import (AI_MODES, LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL,
                      LLM_SETUP_HINT, LLM_TIMEOUT, AGE_BANDS)

ENGINE_OFFLINE = "offline-rule-engine"
ENGINE_LLM = "llm"

# 剧情节点八点结构（商业计划书 P11：一个景区 = 一个故事世界）
NODE_STRUCTURE = [
    ("入口", "entry", "讲述故事的起点，让孩子先「进入」这个世界。"),
    ("古建筑", "main", "观察建筑的形制与纹样，埋下第一条线索。"),
    ("古树", "branch", "以自然物作为时间刻度，引出历史的长度。"),
    ("博物馆", "main", "用一件具体文物把抽象知识变成可见的细节。"),
    ("山谷", "branch", "走出建筑，用身体感受地形与空间。"),
    ("观景台", "main", "登高回望，把散落的线索连成一张图。"),
    ("隐藏地点", "branch", "找到大多数人都错过的那一处细节。"),
    ("终极任务", "reward", "把所有线索拼合，给出最终的答案与奖励。"),
]

# 四类任务轮转（商业计划书 P10：观察 / 寻找 / 拍摄 / 解谜）
TASK_CYCLE = ["observe", "find", "photo", "solve"]
TASK_TYPE_CN = {"observe": "观察", "find": "寻找", "photo": "拍摄", "solve": "解谜"}

# 三层年龄玩法（商业计划书 P13）
AGE_PLAY = {
    "4-8": {
        "label": "亲子探索",
        "worldview_prefix": "这是一个关于「发现」的故事。",
        "story_tone": "语言简单、有节奏感，多用拟声词和身体动作，"
                      "每次只让孩子做一件事，重点在「找到」与「看见」。",
        "tasks": ["数一数", "找一找", "拍一拍", "比一比"],
        "reward": ("小小发现家", "🌟", "完成亲子探索路线的全部观察任务"),
    },
    "8-12": {
        "label": "少年冒险",
        "worldview_prefix": "这是一个关于「解谜」的故事。",
        "story_tone": "有明确的目标与悬念，线索层层递进，"
                      "需要孩子观察真实环境并做简单推理，鼓励提问。",
        "tasks": ["观察细节", "搜集线索", "拍摄记录", "推理判断"],
        "reward": ("少年解密者", "🔎", "完成少年冒险路线的全部解谜任务"),
    },
    "12+": {
        "label": "沉浸剧本",
        "worldview_prefix": "这是一个关于「选择」的故事。",
        "story_tone": "有角色、有立场、有取舍。允许开放式结局，"
                      "引导孩子用史料与实物互相印证，形成自己的判断。",
        "tasks": ["考据比对", "逻辑推演", "影像取证", "观点论证"],
        "reward": ("深度考据家", "📚", "完成沉浸剧本路线的全部论证任务"),
    },
}

CHAPTER_TEMPLATES = [
    ("{place}初遇", "孩子与阿游抵达{place}，故事从第一眼看到的景象开始。"),
    ("藏起来的线索", "{anchor}里藏着第一条线索，需要仔细观察才能发现。"),
    ("时间的刻度", "从{nature}身上读出时间的长度，把过去和现在连起来。"),
    ("文物的低语", "一件具体的文物开口说话，把抽象的知识变成可见的细节。"),
    ("走出高墙", "离开建筑，用身体去感受这片土地的高低与远近。"),
    ("回望全景", "登高回望，把散落的线索连成一张属于自己的地图。"),
    ("被忽略的角落", "找到大多数人都错过的那一处细节。"),
    ("最后的答案", "把所有线索拼合，说出你的答案，领取属于你的徽章。"),
]

DIALOG_OPENERS = [
    "哇！你走到{place}啦 🎉 我感觉到这里有故事在呼唤我们～",
    "看！{place}。这里的东西好像都在跟我说话，你听见了吗？",
    "我们到{place}了！先别急着走，我有个小秘密要告诉你……",
    "这里就是{place}呀。我在资料里读过它，但亲眼看到还是很不一样！",
]

DIALOG_HINTS = [
    "别急，先看一看，再想一想。答案通常就藏在最普通的地方哦～",
    "我提示你一下：{anchor}。剩下的交给你啦！",
    "这个有点难对不对？我们可以换个角度再看看～",
    "你观察得好仔细！顺着这条线索继续往下找找看 ✨",
]

FEEDBACK_STYLES = ["悬疑解谜", "历史探秘", "自然观察", "非遗体验", "城市漫游", "诗词人文"]


# ================================================================ 素材读取
def load_materials(park_id: int, limit: int = 240) -> list[dict]:
    """读取素材：优先本景区，不足时用同城/全库补齐。"""
    rows = db.query(
        "SELECT * FROM materials WHERE park_id = ? AND status = 'indexed' "
        "ORDER BY category, id LIMIT ?", (park_id, limit))
    if len(rows) < 20:
        rows += db.query(
            "SELECT * FROM materials WHERE status = 'indexed' AND park_id != ? "
            "ORDER BY category, id LIMIT ?", (park_id, limit - len(rows)))
    return rows


def material_stats(park_id: int) -> dict:
    total = int(db.scalar("SELECT COUNT(*) FROM materials WHERE park_id = ?", (park_id,)))
    indexed = int(db.scalar(
        "SELECT COUNT(*) FROM materials WHERE park_id = ? AND status = 'indexed'", (park_id,)))
    all_indexed = int(db.scalar("SELECT COUNT(*) FROM materials WHERE status = 'indexed'"))
    return {"park_materials": total, "park_indexed": indexed, "library_indexed": all_indexed}


def _pick(materials: list[dict], category: str, idx: int) -> dict | None:
    pool = [m for m in materials if m["category"] == category]
    if not pool:
        pool = materials
    return pool[idx % len(pool)] if pool else None


def _keywords_of(material: dict) -> list[str]:
    tags = (material.get("tags") or "").split(",")
    return [t.strip() for t in tags if t.strip()][:6]


# ================================================================ 离线规则引擎
def _offline_generate(park: dict, materials: list[dict], mode: str, age_band: str,
                      style: str, scenario_title: str, chapter_count: int,
                      node_count: int) -> dict:
    age = AGE_PLAY.get(age_band, AGE_PLAY["8-12"])
    place = park.get("city") or park.get("name", "")
    stats = material_stats(park["id"])

    # ---------- 世界观 ----------
    arch = _pick(materials, "architecture", 0)
    hist = _pick(materials, "history", 0)
    legend = _pick(materials, "legend", 0)
    nature = _pick(materials, "nature", 0)
    heritage = _pick(materials, "heritage", 0)

    style_note = style.strip() or f"{age['label']}，走进真实景区，边走边解谜。"
    worldview = (
        f"{age['worldview_prefix']}{park['name']}。\n\n"
        f"阿游带着孩子走进这片土地。根据景区资料，这里的核心是「"
        f"{(arch or {}).get('title', place + '的建筑')}」——"
        f"{_trim((arch or {}).get('content'), 90)}"
        f"沿着时间往回走，{(hist or {}).get('title', '这里的历史')}告诉我们："
        f"{_trim((hist or {}).get('content'), 90)}"
        f"而当地的传说里还留着另一条线：{(legend or {}).get('title', '一段旧事')}。\n\n"
        f"故事基调：{style_note}\n"
        f"叙事要求：{age['story_tone']}"
    )

    # ---------- 章节 ----------
    ch_total = max(1, min(12, int(chapter_count or 3)))
    chapters = []
    for i in range(ch_total):
        tpl_title, tpl_summary = CHAPTER_TEMPLATES[i % len(CHAPTER_TEMPLATES)]
        chapters.append({
            "idx": i + 1,
            "title": tpl_title.format(place=place),
            "summary": tpl_summary.format(
                place=place,
                anchor=(arch or {}).get("title", "古建筑"),
                nature=(nature or {}).get("title", "古树与山林"),
            ),
        })

    # ---------- 节点 ----------
    want_nodes = max(2, min(12, int(node_count or 6)))
    nodes = []
    tasks = []
    for i in range(want_nodes):
        struct = NODE_STRUCTURE[i % len(NODE_STRUCTURE)]
        node_title, kind, purpose = struct
        is_last = i == want_nodes - 1
        if is_last:
            kind = "reward"
            node_title = f"{age['reward'][0]}"
        category_map = {
            "入口": "geo", "古建筑": "architecture", "古树": "nature",
            "博物馆": "heritage", "山谷": "nature", "观景台": "geo",
            "隐藏地点": "legend", "终极任务": "history",
        }
        cat = category_map.get(struct[0], "history")
        mat = _pick(materials, cat, i)
        anchor = mat["title"] if mat else f"{place}的{struct[0]}"
        anchor_text = _trim(mat.get("content") if mat else "", 70) if mat else ""

        name = f"{anchor}" if mat else f"{place} · {node_title}"
        story_text = (
            f"{purpose}阿游翻着资料说：「{anchor_text}」"
            f"现在轮到你用自己的眼睛去验证它了——"
            f"请完成一次「{age['tasks'][i % len(age['tasks'])]}」。"
            if anchor_text else
            f"{purpose}阿游说：「我们要在这里完成一次{age['tasks'][i % len(age['tasks'])]}。」"
        )
        dialog = DIALOG_OPENERS[i % len(DIALOG_OPENERS)].format(place=anchor)
        hint = DIALOG_HINTS[i % len(DIALOG_HINTS)].format(anchor=anchor)

        node = {
            "name": name,
            "kind": kind,
            "trigger_type": "gps",
            "place": anchor,
            "structure": node_title,
            "story_text": story_text,
            "ai_dialog": dialog,
            "hint": hint,
            "age_band": age_band,
            "lat": _jitter(park.get("lat") or 34.0, i),
            "lng": _jitter(park.get("lng") or 108.0, i + 7),
            "radius_m": 40 + (i % 3) * 10,
            "source_material_id": mat["id"] if mat else None,
            "task": None,
        }

        if kind != "reward":
            ttype = TASK_CYCLE[i % len(TASK_CYCLE)]
            kws = _keywords_of(mat) if mat else [node_title]
            answer = kws[0] if kws else node_title
            task = {
                "title": f"{age['tasks'][i % len(age['tasks'])]}：{anchor}",
                "type": ttype,
                "type_label": TASK_TYPE_CN[ttype],
                "verify_mode": "photo" if ttype == "photo" else "keyword",
                "desc": f"围绕「{anchor}」完成一次{TASK_TYPE_CN[ttype]}任务。"
                        f"{anchor_text}",
                "answer": "" if ttype == "photo" else answer,
                "keywords": ",".join(kws) if ttype != "photo" else "",
                "hint": hint,
                "target_count": 3 if ttype == "find" else 1,
                "reward_growth": _reward_for(ttype, age_band),
                "age_band": age_band,
            }
            node["task"] = task
            tasks.append({"node_index": i, **task})

        nodes.append(node)

    # ---------- 奖励体系 ----------
    reward_name, reward_emoji, reward_desc = age["reward"]
    rewards = [
        {"name": reward_name, "emoji": reward_emoji, "desc": f"{place} · {reward_desc}",
         "rarity": "rare"},
        {"name": f"{place}记忆", "emoji": park.get("emoji", "🧭"),
         "desc": f"完整走过一次{place}的故事路线", "rarity": "common"},
        {"name": "连环解密者", "emoji": "🧩",
         "desc": "在同一座景区连续完成 3 个剧情节点", "rarity": "common"},
    ]
    if heritage:
        rewards.append({"name": f"{_short(heritage['title'])}传承人", "emoji": "🎭",
                        "desc": f"完成非遗主题任务：{heritage['title']}", "rarity": "rare"})

    # ---------- 来源素材 ----------
    used_ids = {n["source_material_id"] for n in nodes if n.get("source_material_id")}
    sources = [{"material_id": m["id"], "title": m["title"], "category": m["category"]}
               for m in materials if m["id"] in used_ids][:12]

    result: dict[str, Any] = {
        "engine": ENGINE_OFFLINE,
        "worldview": worldview,
        "scenario": {
            "title": scenario_title or f"{place} · {FEEDBACK_STYLES[hash(place) % len(FEEDBACK_STYLES)]}",
            "subtitle": f"一封来自{place}的邀请，正在等待你。",
            "age_band": age_band,
            "age_label": age["label"],
            "style": style_note,
        },
        "chapters": chapters,
        "nodes": nodes,
        "rewards": rewards,
        "sources": sources,
        "notes": (
            f"由离线规则引擎基于 {stats['park_indexed']} 条本景区素材"
            f"（全库 {stats['library_indexed']} 条已向量化素材）生成。"
        ),
    }

    # 按模式裁剪返回值（未生成的字段返回 null）
    if mode == "mainline":
        return {**result, "nodes": None, "rewards": None}
    if mode == "task":
        return {**result, "worldview": None, "chapters": None,
                "nodes": [{"name": n["name"], "kind": n["kind"], "task": n["task"]}
                          for n in nodes if n.get("task")],
                "rewards": None}
    if mode == "dialog":
        return {**result, "worldview": None, "chapters": None, "rewards": None,
                "nodes": [{"name": n["name"], "ai_dialog": n["ai_dialog"],
                           "story_text": n["story_text"], "hint": n["hint"]} for n in nodes]}
    if mode == "reward":
        return {**result, "worldview": None, "chapters": None, "nodes": None}
    return result  # full


def _reward_for(ttype: str, age_band: str) -> dict:
    scale = {"4-8": 1.0, "8-12": 1.3, "12+": 1.6}.get(age_band, 1.0)
    base = {
        "observe": {"observe": 10, "knowledge": 5},
        "find": {"explore": 12, "observe": 6},
        "photo": {"create": 12, "observe": 6},
        "solve": {"knowledge": 14, "courage": 8},
    }.get(ttype, {"explore": 8})
    return {k: int(round(v * scale)) for k, v in base.items()}


def _jitter(value: float, seed: int) -> float:
    """在景区坐标附近做小范围抖动，生成节点坐标（约 ±0.004°，≈400m）。"""
    offsets = [0.0, 0.0012, -0.0011, 0.0021, -0.0020, 0.0031, -0.0029, 0.0008,
               0.0019, -0.0016, 0.0026, -0.0006]
    return round(float(value) + offsets[seed % len(offsets)], 6)


def _trim(text: str | None, n: int) -> str:
    t = (text or "").strip().replace("\n", "")
    return t[:n] + ("……" if len(t) > n else "")


def _short(title: str) -> str:
    return re.sub(r"[·（(].*?[)）]?", "", title).strip()[:6] or title[:6]


# ================================================================ 大模型接入
LLM_SYSTEM_PROMPT = """你是「游伴」儿童 AI 旅行潮玩的 AI Story Engine。
你的任务是把景区资料转化为适合儿童实地游玩的「AI 剧本游」内容。

硬性要求：
1. 所有内容必须基于给定的景区资料，不得编造不存在的地名、文物或史实。
2. 语言面向儿童，句子短、有画面感，不使用说教口吻。
3. 任务必须是孩子在现场能用眼睛看、用脚走到、用手机拍到的具体动作。
4. 只输出 JSON，不要输出任何解释、markdown 代码围栏或多余文字。

输出 JSON 结构：
{
  "worldview": "字符串，200 字以内的世界观",
  "scenario": {"title": "剧本名", "subtitle": "一句话副标题"},
  "chapters": [{"idx": 1, "title": "章节名", "summary": "一句话摘要"}],
  "nodes": [{
      "name": "节点名（含具体地点）", "kind": "entry|main|branch|reward",
      "story_text": "剧情文案，80 字以内", "ai_dialog": "阿游对孩子说的话，40 字以内",
      "hint": "给孩子的提示", "place": "具体地点名",
      "task": {"title": "任务名", "type": "observe|find|photo|solve",
               "verify_mode": "keyword|photo|answer", "desc": "任务描述",
               "answer": "参考答案关键词", "keywords": "逗号分隔的关键词",
               "hint": "提示", "target_count": 1}
  }],
  "rewards": [{"name": "徽章名", "emoji": "一个 emoji", "desc": "获得条件"}]
}"""


def _llm_generate(park: dict, materials: list[dict], mode: str, age_band: str,
                  style: str, scenario_title: str, chapter_count: int,
                  node_count: int) -> dict:
    """调用 OpenAI 兼容接口生成。失败时抛异常，由上层回退到离线引擎。"""
    mat_text = "\n".join(
        f"[{m['category']}] {m['title']}：{_trim(m.get('content'), 160)}"
        for m in materials[:60])
    age = AGE_PLAY.get(age_band, AGE_PLAY["8-12"])

    user_prompt = (
        f"景区：{park['name']}（{park.get('city', '')}，坐标 "
        f"{park.get('lat')},{park.get('lng')}）\n"
        f"生成模式：{AI_MODES.get(mode, mode)}\n"
        f"适合年龄：{age_band} 岁（{age['label']}）\n"
        f"剧情风格：{style or '悬疑解谜，融入当地历史文化知识'}\n"
        f"剧本标题：{scenario_title or '（请起一个名字）'}\n"
        f"章节数：{chapter_count}，剧情节点数：{node_count}\n\n"
        f"景区资料：\n{mat_text}\n\n"
        f"请严格按系统要求输出 JSON。"
    )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        LLM_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {LLM_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    text = body["choices"][0]["message"]["content"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)

    nodes = []
    for i, n in enumerate(data.get("nodes") or []):
        task = n.get("task")
        if task:
            task.setdefault("type_label", TASK_TYPE_CN.get(task.get("type", ""), "任务"))
            task.setdefault("target_count", 1)
            task.setdefault("reward_growth", _reward_for(task.get("type", "observe"), age_band))
            task["age_band"] = age_band
        nodes.append({
            "name": n.get("name"), "kind": n.get("kind", "main"),
            "trigger_type": "gps", "place": n.get("place") or n.get("name"),
            "story_text": n.get("story_text"), "ai_dialog": n.get("ai_dialog"),
            "hint": n.get("hint"), "age_band": age_band,
            "lat": _jitter(park.get("lat") or 34.0, i),
            "lng": _jitter(park.get("lng") or 108.0, i + 7),
            "radius_m": 40, "task": task,
        })

    return {
        "engine": ENGINE_LLM,
        "worldview": data.get("worldview"),
        "scenario": {
            "title": (data.get("scenario") or {}).get("title") or scenario_title,
            "subtitle": (data.get("scenario") or {}).get("subtitle"),
            "age_band": age_band, "age_label": age["label"], "style": style,
        },
        "chapters": data.get("chapters") or [],
        "nodes": nodes,
        "rewards": data.get("rewards") or [],
        "sources": [{"material_id": m["id"], "title": m["title"], "category": m["category"]}
                    for m in materials[:12]],
        "notes": f"由大模型 {LLM_MODEL} 基于 {len(materials)} 条景区素材生成。",
    }


# ================================================================ 对外入口
def generate(park_id: int, mode: str = "full", age_band: str = "8-12", style: str = "",
             scenario_title: str = "", chapter_count: int = 3, node_count: int = 6,
             persist: bool = True) -> dict:
    """执行一次 AI 生成。自动在离线引擎与大模型之间选择，失败自动回退。"""
    if mode not in AI_MODES:
        raise ValueError("不支持的生成模式")

    park = db.query_one("SELECT * FROM parks WHERE id = ?", (park_id,))
    if not park:
        raise ValueError("景区不存在")

    materials = load_materials(park_id)
    t0 = time.perf_counter()

    engine_used = ENGINE_OFFLINE
    fallback_note = None
    if LLM_ENABLED:
        try:
            result = _llm_generate(park, materials, mode, age_band, style,
                                   scenario_title, chapter_count, node_count)
            engine_used = ENGINE_LLM
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
                ValueError, TimeoutError, OSError) as exc:
            result = _offline_generate(park, materials, mode, age_band, style,
                                       scenario_title, chapter_count, node_count)
            fallback_note = f"大模型调用失败（{type(exc).__name__}），已自动回退到离线规则引擎。"
            engine_used = ENGINE_OFFLINE
    else:
        result = _offline_generate(park, materials, mode, age_band, style,
                                   scenario_title, chapter_count, node_count)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if fallback_note:
        result["notes"] = f"{result['notes']} {fallback_note}"

    result["mode"] = mode
    result["mode_label"] = AI_MODES[mode]
    result["age_band"] = age_band
    result["elapsed_ms"] = elapsed_ms

    created_scenario_id = None
    if persist and mode == "full":
        created_scenario_id = persist_scenario(park, result, age_band, style)
        result["created_scenario_id"] = created_scenario_id
        if created_scenario_id:
            result["notes"] += f" 已入库为草稿剧本（ID {created_scenario_id}）。"

    job_id = None
    if persist:
        job_id = db.insert("ai_jobs", {
            "park_id": park_id, "mode": mode, "age_band": age_band, "style": style,
            "scenario_title": result.get("scenario", {}).get("title") or scenario_title,
            "chapter_count": chapter_count, "node_count": node_count,
            "engine": engine_used, "status": "done", "elapsed_ms": elapsed_ms,
            "result_json": db.json_dumps(_shrink(result)), "created_at": db.now_text(),
            "created_scenario_id": created_scenario_id,
        })
    result["job_id"] = job_id
    return result


def _shrink(result: dict) -> dict:
    """落库时裁剪结果，避免 ai_jobs 过大。"""
    return {
        "engine": result.get("engine"),
        "mode": result.get("mode"),
        "worldview": (result.get("worldview") or "")[:2000],
        "scenario": result.get("scenario"),
        "chapters": result.get("chapters"),
        "node_count": len(result.get("nodes") or []),
        "rewards": result.get("rewards"),
        "elapsed_ms": result.get("elapsed_ms"),
    }


def persist_scenario(park: dict, result: dict, age_band: str, style: str) -> int | None:
    """把生成结果落库为 draft 剧本（含章节、节点、任务、连线、徽章）。"""
    nodes = result.get("nodes") or []
    if not nodes:
        return None
    sc = result.get("scenario") or {}
    now = db.now_text()

    sid = db.insert("scenarios", {
        "park_id": park["id"], "title": sc.get("title") or f"{park['city']} · AI 剧本",
        "subtitle": sc.get("subtitle"), "kicker": f"AI 剧本游 · {park['city']}",
        "meta": style or "由 AI Story Engine 生成",
        "emoji": park.get("emoji", "🧭"), "age_band": age_band, "status": "draft",
        "worldview": result.get("worldview"), "chapter_count": len(result.get("chapters") or []),
        "completion_rate": 0, "source": "ai", "created_at": now, "updated_at": now,
    })

    ch_ids: list[int] = []
    for c in result.get("chapters") or []:
        ch_ids.append(db.insert("chapters", {
            "scenario_id": sid, "idx": c.get("idx", len(ch_ids) + 1),
            "title": c.get("title") or f"第 {len(ch_ids) + 1} 章",
            "summary": c.get("summary"),
        }))

    # 徽章（先落库，节点可引用）
    badge_ids: dict[str, int] = {}
    for r in result.get("rewards") or []:
        bid = db.insert("badges", {
            "name": r.get("name") or "探索徽章", "emoji": r.get("emoji") or "🏅",
            "city": park.get("city"), "scenario_id": sid,
            "rarity": r.get("rarity") or "common", "desc": r.get("desc"),
            "sort_order": 100 + len(badge_ids),
        })
        badge_ids[r.get("name") or ""] = bid

    n_ch = max(1, len(ch_ids))
    node_ids: list[int] = []
    for i, n in enumerate(nodes):
        ch_id = ch_ids[min(i * n_ch // max(1, len(nodes)), n_ch - 1)] if ch_ids else None
        nid = db.insert("nodes", {
            "scenario_id": sid, "chapter_id": ch_id, "idx": i + 1,
            "name": n.get("name") or f"剧情节点 {i + 1}",
            "kind": n.get("kind") or "main",
            "trigger_type": n.get("trigger_type") or "gps",
            "lat": n.get("lat"), "lng": n.get("lng"),
            "radius_m": n.get("radius_m") or 40, "age_band": age_band,
            "place": n.get("place"), "story_text": n.get("story_text"),
            "ai_dialog": n.get("ai_dialog"), "hint": n.get("hint"),
            "reward_badge_id": badge_ids.get((result.get("rewards") or [{}])[0].get("name", ""))
            if n.get("kind") == "reward" and result.get("rewards") else None,
            # 画布自动布局：每行 3 个
            "x": 12 + (i % 3) * 180, "y": 170 + (i // 3) * 130,
            "sort_order": i + 1,
        })
        node_ids.append(nid)

        task = n.get("task")
        if task:
            db.insert("tasks", {
                "node_id": nid, "scenario_id": sid,
                "title": task.get("title") or f"任务 {i + 1}",
                "type": task.get("type") or "observe", "age_band": age_band,
                "desc": task.get("desc"), "verify_mode": task.get("verify_mode") or "keyword",
                "answer": task.get("answer"), "keywords": task.get("keywords"),
                "hint": task.get("hint"),
                "target_count": int(task.get("target_count") or 1),
                "reward_growth": db.json_dumps(
                    task.get("reward_growth") or _reward_for(task.get("type", "observe"), age_band)),
                "reward_badge_id": None, "completion_rate": 0, "enabled": 1,
                "avg_minutes": 12,
            })

    for a, b in zip(node_ids, node_ids[1:]):
        db.insert("node_links", {"scenario_id": sid, "from_node": a, "to_node": b,
                                 "color": "gold"})

    return sid


# ================================================================ 引擎信息
def engine_info() -> dict:
    return {
        "engine": ENGINE_LLM if LLM_ENABLED else ENGINE_OFFLINE,
        "engine_label": "大模型" if LLM_ENABLED else "内置离线规则引擎",
        "llm_enabled": LLM_ENABLED,
        "llm_provider": LLM_BASE_URL or None,
        "llm_model": LLM_MODEL or None,
        "capabilities": [
            {"key": "mainline", "label": "生成主线", "desc": "输出世界观、剧本名与章节结构"},
            {"key": "task", "label": "生成任务", "desc": "按观察/寻找/拍摄/解谜四类生成现场任务"},
            {"key": "dialog", "label": "生成对话", "desc": "生成阿游对孩子说的话与提示"},
            {"key": "reward", "label": "生成奖励", "desc": "生成徽章体系与获得条件"},
            {"key": "full", "label": "一键生成全剧本", "desc": "完整生成并直接入库为草稿剧本"},
        ],
        "age_bands": [{"key": k, "label": v, "name": AGE_BANDS[k]} for k, v in age_bands_items()],
        "node_structure": [{"name": n, "kind": k, "purpose": p} for n, k, p in NODE_STRUCTURE],
        "setup_hint": LLM_SETUP_HINT,
    }


def age_bands_items():
    return [(k, v) for k, v in AGE_BANDS.items()]
