"""游伴 AI · 阿游对话引擎。

规则驱动的对话意图识别 + 景区素材检索回答，可选接入大模型。
覆盖意图：问候 / 询问附近 / 询问知识 / 表示疲惫 / 接受任务 / 闲聊。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .. import db
from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL, LLM_TIMEOUT
from . import geo, story

SUGGESTIONS = ["附近还有什么故事？", "我有点累了", "给我讲讲这里", "换一个任务"]

GREETING_REPLIES = [
    "嗨！我是阿游 👋 今天我们去哪儿冒险？",
    "我在呢！你走到哪里啦？我一直在看着地图～",
    "你回来啦！我刚刚又发现了一个没去过的地方，要不要去看看？",
]

TIRED_REPLIES = [
    "那我们找个地方坐下歇一会儿吧。我讲个小故事给你听好不好？☁️",
    "累了吗？没关系的，旅行本来就要慢慢来。喝口水，我们休息五分钟～",
]

KNOWLEDGE_HINTS = {
    "大雁塔": "大雁塔", "塔": "大雁塔", "钟楼": "钟楼", "城墙": "城墙",
    "博物馆": "博物馆", "铜钱": "铜钱", "飞天": "飞天", "熊猫": "熊猫",
}


def _material_answer(keyword: str) -> str | None:
    """从素材库检索一条与关键词相关的知识，转成孩子能听懂的话。"""
    row = db.query_one(
        "SELECT title, content FROM materials WHERE status = 'indexed' AND "
        "(title LIKE ? OR tags LIKE ? OR content LIKE ?) ORDER BY LENGTH(content) ASC LIMIT 1",
        (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
    if not row:
        return None
    content = (row["content"] or "").strip()
    # 取前两句，避免一次给孩子太多信息
    parts = re.split(r"(?<=[。！？])", content)
    brief = "".join(parts[:2])[:160]
    return f"好呀，我给你讲讲「{row['title']}」——{brief}"


def _detect_intent(text: str) -> str:
    t = text.strip()
    if not t:
        return "empty"
    if re.search(r"附近|周围|还有什么|哪里|哪儿|下一个", t):
        return "nearby"
    if re.search(r"累|休息|走不动|饿|渴|不想", t):
        return "tired"
    if re.search(r"讲讲|介绍|为什么|是什么|历史|知识|说说", t):
        return "knowledge"
    if re.search(r"好呀|好的|接受|这就去|我去|开始|出发|嗯", t):
        return "accept"
    if re.search(r"你好|嗨|hi|hello|在吗|阿游", t, re.I):
        return "greeting"
    return "chat"


def _llm_reply(user: dict, device: dict, history_text: str, text: str,
               context: str) -> str | None:
    """可选：调用大模型生成更自然的回复。失败返回 None。"""
    if not LLM_ENABLED:
        return None
    system = (
        "你是「游伴」儿童 AI 旅行潮玩中的角色「阿游」，是孩子的旅行伙伴。"
        "用简短、温暖、有画面感的中文回答，1-3 句话，可以用 emoji。"
        "不要使用说教口吻，不要输出与儿童旅行无关的内容。"
        f"当前上下文：{context}"
    )
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{history_text}\n孩子说：{text}"},
        ],
        "temperature": 0.8,
    }
    try:
        req = urllib.request.Request(
            LLM_BASE_URL.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {LLM_API_KEY}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
            ValueError, TimeoutError, OSError):
        return None


def reply(user: dict, device: dict | None, text: str, lat: float | None,
          lng: float | None, history: list[dict] | None = None) -> dict:
    """生成阿游的回复，并可能附带一张任务卡。"""
    uid = user["id"]
    intent = _detect_intent(text)
    messages: list[dict] = []
    quest_card = None
    device_name = (device or {}).get("nickname") or "阿游"

    # 位置 → 当前景区
    park = None
    triggered: list[dict] = []
    nearby: list[dict] = []
    if lat is not None and lng is not None:
        parks = db.query("SELECT * FROM parks")
        park = geo.find_park(parks, lat, lng)
        if park:
            # 只考虑「可达节点」（前置剧情已完成），与 /locate 保持同一套规则
            candidates: list[dict] = []
            for row in db.query("SELECT id FROM scenarios WHERE park_id = ?", (park["id"],)):
                candidates += story.available_nodes(uid, row["id"])
            triggered, nearby = geo.locate_nodes(candidates, lat, lng)

    context_parts = []
    if park:
        context_parts.append(f"孩子正在{park['name']}")
    context_parts.append(f"伙伴名字叫{device_name}")
    context = "；".join(context_parts)

    # ---------- 大模型优先 ----------
    hist_text = "\n".join(f"{m.get('role')}: {m.get('text')}" for m in (history or [])[-6:])
    llm_text = _llm_reply(user, device or {}, hist_text, text, context) if text.strip() else None

    # ---------- 规则回复 ----------
    if llm_text:
        messages.append({"role": "ai", "text": llm_text})
    elif intent == "empty":
        messages.append({"role": "ai", "text": "我一直在这儿呢，随时可以出发～"})
    elif intent == "tired":
        messages.append({"role": "ai", "text": TIRED_REPLIES[len(text) % len(TIRED_REPLIES)]})
    elif intent == "greeting":
        messages.append({"role": "ai", "text": GREETING_REPLIES[len(text) % len(GREETING_REPLIES)]})
    elif intent == "knowledge":
        hit = None
        for k, v in KNOWLEDGE_HINTS.items():
            if k in text:
                hit = v
                break
        ans = _material_answer(hit) if hit else None
        if not ans and park:
            row = db.query_one(
                "SELECT title, content FROM materials WHERE park_id = ? AND status = 'indexed' "
                "ORDER BY LENGTH(content) DESC LIMIT 1", (park["id"],))
            if row:
                ans = f"我给你讲讲「{row['title']}」——" + (row["content"] or "")[:140]
        messages.append({"role": "ai",
                         "text": ans or "这个问题我还得查查资料～要不我们先去找找看，"
                                        "找到了我就告诉你！"})
    elif intent == "nearby":
        if triggered:
            n = triggered[0]
            messages.append({
                "role": "ai",
                "text": f"就在旁边！{n['name']} 离我们只有 {n['distance_m']} 米。"
                        f"我已经把任务准备好啦～",
            })
            quest_card = _quest_card(n)
        elif nearby:
            n = nearby[0]
            messages.append({
                "role": "ai",
                "text": f"前面 {n.get('distance_text') or str(n['distance_m']) + 'm'} "
                        f"有个「{n['name']}」，我们走过去看看好不好？",
            })
        elif park:
            messages.append({
                "role": "ai",
                "text": f"{park['name']}里的故事我们差不多都走完了！"
                        f"要不要换一座城市，去开一个新的故事？🗺️",
            })
        else:
            messages.append({"role": "ai",
                             "text": "我们现在好像不在任何景区里。等你走到目的地，"
                                     "我就能感觉到故事在哪里啦～"})
    elif intent == "accept":
        if triggered:
            n = triggered[0]
            messages.append({"role": "ai",
                             "text": f"太棒啦！那我们开始吧——{n['name']}。"})
            quest_card = _quest_card(n)
        else:
            messages.append({"role": "ai",
                             "text": "好呀！你先走到景点旁边，我就能把任务给你啦～"})
    else:
        # 闲聊：尽量结合当前节点
        if triggered:
            n = triggered[0]
            messages.append({
                "role": "ai",
                "text": (n.get("ai_dialog") or "我感觉到这里有故事在呼唤我们～")
                        + f"（{n['name']} · {n['distance_m']}m）",
            })
            quest_card = _quest_card(n)
        else:
            messages.append({
                "role": "ai",
                "text": "嗯嗯，我在听着呢。你说什么我都觉得有意思～"
                        "要不我们一起看看附近有什么？",
            })

    return {
        "intent": intent,
        "messages": messages,
        "quest_card": quest_card,
        "suggestions": SUGGESTIONS,
        "park": {"id": park["id"], "name": park["name"]} if park else None,
    }


def _quest_card(node: dict) -> dict | None:
    task = db.query_one(
        "SELECT * FROM tasks WHERE node_id = ? AND enabled = 1 ORDER BY id LIMIT 1",
        (node["id"],))
    if not task:
        return None
    return {
        "kicker": "NEW QUEST · 主线任务" if node["kind"] == "main" else "NEW QUEST · 支线任务",
        "title": task["title"],
        "desc": task["desc"],
        "cta": "接受任务 →",
        "task_id": task["id"],
        "node_id": node["id"],
        "verify_mode": task["verify_mode"],
        "type_label": story.task_brief(None, task)["type_label"],
    }
