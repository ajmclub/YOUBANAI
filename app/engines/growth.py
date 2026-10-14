"""游伴 AI · 任务判定与成长系统。

包含：
- 四类任务判定（auto / answer / keyword / photo）
- 成长五维度累加
- 等级提升
- 徽章解锁
"""
from __future__ import annotations

from .. import db
from ..utils import level_of
from . import geo  # noqa: F401  (保持引擎包内聚合)

GROWTH_DIMS_ORDER = ["explore", "create", "observe", "knowledge", "courage"]

# 未通过时的保底成长值比例
FAIL_RATIO = 0.2

FEEDBACK_OK = [
    "太棒了！你观察得真仔细 ✨",
    "答对啦！阿游为你鼓掌 👏",
    "完全正确！你越来越像个小探险家了～",
    "这就是长安想告诉你的答案 ✨",
]
FEEDBACK_FAIL = [
    "再仔细看看哦，答案就藏在眼前～",
    "差一点点！换个角度再试一次吧 💪",
    "别着急，阿游陪你一起再找找看～",
]


# ---------------------------------------------------------------- 用户成长
def get_growth(user_id: int) -> dict:
    rows = db.query("SELECT dim, value FROM user_growth WHERE user_id = ?", (user_id,))
    values = {r["dim"]: r["value"] for r in rows}
    return {dim: int(values.get(dim, 0)) for dim in GROWTH_DIMS_ORDER}


def add_growth(user_id: int, gain: dict) -> int:
    """累加成长值，返回新的成长总值。"""
    total_gain = 0
    for dim, val in (gain or {}).items():
        val = int(val or 0)
        if not val:
            continue
        total_gain += val
        row = db.query_one("SELECT value FROM user_growth WHERE user_id = ? AND dim = ?",
                           (user_id, dim))
        if row:
            db.update("user_growth", {"value": int(row["value"]) + val},
                      "user_id = ? AND dim = ?", (user_id, dim))
        else:
            db.insert("user_growth", {"user_id": user_id, "dim": dim, "value": val})

    new_total = int(db.scalar("SELECT growth_total FROM users WHERE id = ?", (user_id,))) + total_gain
    level, _name = level_of(new_total)
    db.update_by_id("users", user_id, {"growth_total": new_total, "level": level})
    return new_total


def fail_gain(task: dict) -> dict:
    """未通过时给保底成长值（至少 1 点）。"""
    base = db.json_loads(task.get("reward_growth"), {}) or {}
    out: dict[str, int] = {}
    for dim, val in base.items():
        v = max(1, int(round(int(val) * FAIL_RATIO)))
        out[dim] = v
    if not out:
        out = {"courage": 1}
    return out


# ---------------------------------------------------------------- 任务进度
def task_done_count(user_id: int, task_id: int) -> int:
    """该任务已通过的次数（用于 target_count > 1 的计数型任务）。"""
    return int(db.scalar(
        "SELECT COUNT(*) FROM task_submissions WHERE user_id = ? AND task_id = ? AND passed = 1",
        (user_id, task_id)))


def task_is_complete(user_id: int, task: dict) -> bool:
    target = int(task.get("target_count") or 1)
    return task_done_count(user_id, task["id"]) >= target


def node_is_done(user_id: int, node_id: int) -> bool:
    """节点下所有启用的任务都完成，才算节点完成。"""
    tasks = db.query("SELECT * FROM tasks WHERE node_id = ? AND enabled = 1", (node_id,))
    if not tasks:
        # 无任务的节点（入口 / 纯剧情）只要到访即算完成
        return db.query_one(
            "SELECT 1 FROM node_visits WHERE user_id = ? AND node_id = ?",
            (user_id, node_id)) is not None
    return all(task_is_complete(user_id, t) for t in tasks)


# ---------------------------------------------------------------- 判定
def _norm(text: str | None) -> str:
    return (text or "").strip().lower().replace(" ", "").replace("　", "")


def judge(task: dict, payload: dict) -> tuple[bool, str, str]:
    """判定任务是否通过。返回 (passed, feedback, user_answer)。

    判定方式：
    - auto    : 提交即通过
    - answer  : 与 answer 精确匹配（忽略大小写与空格），或在 keywords 中命中
    - keyword : answer 命中任一关键词即通过
    - photo   : photo_note 非空即通过
    """
    mode = task.get("verify_mode") or "keyword"
    answer = payload.get("answer")
    photo_note = payload.get("photo_note")
    raw = (answer or photo_note or "").strip()

    if mode == "auto":
        return True, FEEDBACK_OK[0], "已到达"

    if mode == "photo":
        if photo_note and photo_note.strip():
            return True, "拍得真好！阿游把你的照片收进故事里了 📷", photo_note.strip()
        return False, "还没有拍下照片哦，先找到目标再按快门～", raw

    user = _norm(answer)
    if not user:
        return False, "还没有填写答案哦～", raw

    keywords = [k for k in (task.get("keywords") or "").split(",") if k.strip()]
    expected = _norm(task.get("answer"))

    if mode == "answer":
        if user == expected or user in [_norm(k) for k in keywords]:
            return True, FEEDBACK_OK[1], raw
        return False, FEEDBACK_FAIL[0], raw

    # keyword 模式（默认）
    pool = [expected] + [_norm(k) for k in keywords]
    pool = [p for p in pool if p]
    # 需要命中 target_count 个不同关键词中的任意一个（计数型任务由调用方累计）
    for p in pool:
        if p and p in user:
            return True, FEEDBACK_OK[0], raw
    return False, FEEDBACK_FAIL[1], raw


def submit(user_id: int, task: dict, payload: dict) -> dict:
    """处理一次任务提交，落库并结算奖励。"""
    node_id = task.get("node_id")
    target = int(task.get("target_count") or 1)

    # 计数型任务：已达标的重复提交直接返回完成态
    already = task_done_count(user_id, task["id"])
    if already >= target:
        node_done = node_is_done(user_id, node_id) if node_id else True
        return {
            "pass": True, "feedback": "这个任务你已经完成啦 ✨", "growth_gain": {},
            "growth_total": int(db.scalar("SELECT growth_total FROM users WHERE id = ?", (user_id,))),
            "level_up": None, "badge": None, "node_completed": node_done,
            "task_progress": {"done": already, "total": target},
            "next_node": _next_node(node_id),
        }

    passed, feedback, user_answer = judge(task, payload)

    if passed:
        gain = db.json_loads(task.get("reward_growth"), {}) or {}
    else:
        gain = fail_gain(task)

    db.insert("task_submissions", {
        "user_id": user_id, "task_id": task["id"], "node_id": node_id,
        "answer": (payload.get("answer") or "")[:500],
        "photo_note": (payload.get("photo_note") or "")[:500],
        "passed": 1 if passed else 0,
        "growth_gain": db.json_dumps(gain) if gain else None,
        "submitted_at": db.now_text(),
    })

    before_total = int(db.scalar("SELECT growth_total FROM users WHERE id = ?", (user_id,)))
    before_level, _ = level_of(before_total)
    new_total = add_growth(user_id, gain) if gain else before_total
    after_level, after_name = level_of(new_total)

    level_up = None
    if after_level > before_level:
        level_up = {"level": after_level, "level_name": after_name}

    badge = None
    node_completed = False
    if passed and node_id:
        # 确保到访记录存在（任务可能在未上报位置时提交）
        ensure_visit(user_id, node_id, task.get("scenario_id"), "task")
        badge = _try_unlock_badge(user_id, task, node_id)
        node_completed = node_is_done(user_id, node_id)
        if node_completed:
            _refresh_progress(user_id, task.get("scenario_id"))

    return {
        "pass": passed,
        "feedback": feedback,
        "user_answer": user_answer,
        "growth_gain": gain,
        "growth_total": new_total,
        "level_up": level_up,
        "badge": badge,
        "node_completed": node_completed,
        "task_progress": {
            "done": task_done_count(user_id, task["id"]),
            "total": target,
        },
        "next_node": _next_node(node_id) if node_completed else None,
    }


# ---------------------------------------------------------------- 到访 / 徽章 / 进度
def ensure_visit(user_id: int, node_id: int, scenario_id: int | None, source: str = "gps") -> bool:
    """记录节点到访，返回是否首次到访。"""
    exists = db.query_one("SELECT 1 FROM node_visits WHERE user_id = ? AND node_id = ?",
                          (user_id, node_id))
    if exists:
        return False
    db.insert("node_visits", {
        "user_id": user_id, "node_id": node_id, "scenario_id": scenario_id,
        "source": source, "visited_at": db.now_text(),
    })
    return True


def _try_unlock_badge(user_id: int, task: dict, node_id: int) -> dict | None:
    """徽章解锁优先级：
    1) 任务自带的 reward_badge_id
    2) 节点自带的 reward_badge_id
    3) 该剧本的「结算节点」（kind=reward）完成 → 解锁剧本徽章
    """
    candidate_id = task.get("reward_badge_id")
    if not candidate_id:
        node = db.query_one("SELECT reward_badge_id FROM nodes WHERE id = ?", (node_id,))
        candidate_id = node.get("reward_badge_id") if node else None

    if not candidate_id and task.get("scenario_id"):
        sid = task["scenario_id"]
        reward_node = db.query_one(
            "SELECT id FROM nodes WHERE scenario_id = ? AND kind = 'reward' ORDER BY idx LIMIT 1",
            (sid,))
        if reward_node and node_is_done(user_id, reward_node["id"]):
            row = db.query_one(
                "SELECT id FROM badges WHERE scenario_id = ? ORDER BY id LIMIT 1", (sid,))
            candidate_id = row["id"] if row else None

    if not candidate_id:
        return None
    return grant_badge(user_id, int(candidate_id))


def grant_badge(user_id: int, badge_id: int) -> dict | None:
    exists = db.query_one("SELECT 1 FROM user_badges WHERE user_id = ? AND badge_id = ?",
                          (user_id, badge_id))
    if exists:
        return None
    badge = db.query_one("SELECT * FROM badges WHERE id = ?", (badge_id,))
    if not badge:
        return None
    db.insert("user_badges", {"user_id": user_id, "badge_id": badge_id,
                              "got_at": db.now_text()})
    return {"id": badge["id"], "name": badge["name"], "emoji": badge["emoji"],
            "desc": badge["desc"], "rarity": badge["rarity"]}


def _refresh_progress(user_id: int, scenario_id: int | None) -> None:
    """刷新用户在某剧本的进度（章节 / 百分比 / 状态）。"""
    if not scenario_id:
        return
    total = int(db.scalar("SELECT COUNT(*) FROM nodes WHERE scenario_id = ?", (scenario_id,)))
    if not total:
        return
    visited = int(db.scalar(
        "SELECT COUNT(DISTINCT nv.node_id) FROM node_visits nv JOIN nodes n ON n.id = nv.node_id "
        "WHERE nv.user_id = ? AND n.scenario_id = ?", (user_id, scenario_id)))
    percent = int(round(visited * 100 / total))
    status = "done" if visited >= total else "ongoing"

    # 当前章节 = 最靠后的「已到访且未全部完成」节点所属章节，否则最后一个已到访章节
    row = db.query_one(
        "SELECT c.idx AS chapter_idx FROM node_visits nv "
        "JOIN nodes n ON n.id = nv.node_id JOIN chapters c ON c.id = n.chapter_id "
        "WHERE nv.user_id = ? AND n.scenario_id = ? ORDER BY n.idx DESC LIMIT 1",
        (user_id, scenario_id))
    chapter_idx = row["chapter_idx"] if row and row["chapter_idx"] else 1

    exists = db.query_one("SELECT 1 FROM progress WHERE user_id = ? AND scenario_id = ?",
                          (user_id, scenario_id))
    data = {"chapter_idx": chapter_idx, "percent": percent, "status": status,
            "updated_at": db.now_text()}
    if exists:
        db.update("progress", data, "user_id = ? AND scenario_id = ?", (user_id, scenario_id))
    else:
        db.insert("progress", {**data, "user_id": user_id, "scenario_id": scenario_id,
                               "started_at": db.now_text()})

    # 剧本完成 → 解锁剧本徽章
    if status == "done":
        badge = db.query_one(
            "SELECT id FROM badges WHERE scenario_id = ? ORDER BY id LIMIT 1", (scenario_id,))
        if badge:
            grant_badge(user_id, badge["id"])


def _next_node(node_id: int | None) -> dict | None:
    if not node_id:
        return None
    cur = db.query_one("SELECT scenario_id, idx FROM nodes WHERE id = ?", (node_id,))
    if not cur:
        return None
    nxt = db.query_one(
        "SELECT id, name, kind FROM nodes WHERE scenario_id = ? AND idx > ? ORDER BY idx LIMIT 1",
        (cur["scenario_id"], cur["idx"]))
    if not nxt:
        return None
    return {"id": nxt["id"], "name": nxt["name"], "kind": nxt["kind"]}
