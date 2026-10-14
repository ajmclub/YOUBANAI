"""游伴 AI · 全局配置与品牌常量。"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- 路径
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = ROOT_DIR / "docs"
SCHEMA_FILE = APP_DIR / "schema.sql"
DB_FILE = DATA_DIR / "youban.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- 应用
APP_NAME = "游伴 AI"
APP_NAME_EN = "YOUBAN AI"
VERSION = "1.0.0"
TAGLINE = "带着它，去发现世界。"
MECHANISM = "走到哪里，故事发生在哪里。"

# ---------------------------------------------------------------- 品牌色
BRAND = {
    "night": "#0B1020",    # 深夜蓝
    "warm": "#F5F1E8",     # 暖白
    "gold": "#E8B45A",     # 沙金
    "forest": "#4FA08C",   # 森林绿
    "orange": "#F0873F",   # 活力橙
}

# ---------------------------------------------------------------- 等级体系
# growth_total 阈值 -> 等级名称
LEVEL_THRESHOLDS = [0, 100, 300, 600, 1000, 1600, 2400, 3600, 5200, 7200]
LEVEL_NAMES = [
    "初识伙伴", "小旅人", "探索家", "资深探险家", "少年冒险家",
    "城市猎人", "故事收藏家", "传说旅人", "星图守护者", "世界发现者",
]

# ---------------------------------------------------------------- 枚举字典
AGE_BANDS = {
    "4-8": "亲子探索",
    "8-12": "少年冒险",
    "12+": "沉浸剧本",
}

GROWTH_DIMS = [
    ("explore", "探索"),
    ("create", "创造"),
    ("observe", "观察"),
    ("knowledge", "知识"),
    ("courage", "勇气"),
]

NODE_KINDS = {
    "entry": "ENTRY · 入口",
    "main": "STORY NODE",
    "branch": "BRANCH · 支线",
    "reward": "REWARD · 结算",
}

TASK_TYPES = {
    "observe": "观察",
    "find": "寻找",
    "photo": "拍摄",
    "solve": "解谜",
}

MATERIAL_CATEGORIES = [
    ("history", "历史典故", "📜"),
    ("architecture", "建筑风貌", "🏯"),
    ("heritage", "非遗技艺", "🎭"),
    ("legend", "民间传说", "📖"),
    ("nature", "自然地理", "🌿"),
    ("geo", "景区地理", "🗺️"),
]

SCENARIO_STATUS = {
    "online": "已上线",
    "review": "审核中",
    "draft": "草稿",
}

# 徽章稀有度（其他枚举都配了 *_label，这里保持一致）
RARITY_LABELS = {
    "common": "常见",
    "rare": "稀有",
    "legend": "传说",
}

AI_MODES = {
    "mainline": "生成主线",
    "task": "生成任务",
    "dialog": "生成对话",
    "reward": "生成奖励",
    "full": "一键生成全剧本",
}

# ---------------------------------------------------------------- 大模型接入（预留）
# 未配置时自动使用内置离线规则引擎。
LLM_BASE_URL = os.environ.get("YOUBAN_LLM_BASE_URL", "").strip()
LLM_API_KEY = os.environ.get("YOUBAN_LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("YOUBAN_LLM_MODEL", "").strip()
LLM_TIMEOUT = int(os.environ.get("YOUBAN_LLM_TIMEOUT", "60"))

LLM_ENABLED = bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)

LLM_SETUP_HINT = (
    "设置环境变量 YOUBAN_LLM_BASE_URL / YOUBAN_LLM_API_KEY / YOUBAN_LLM_MODEL "
    "即可把 AI Story Engine 切换为真实大模型（OpenAI 兼容接口）。"
    "未配置时使用内置离线规则引擎，无需联网即可完整演示。"
)

# ---------------------------------------------------------------- 服务
# 默认端口刻意避开 8000：该端口在开发机上常被其它项目占用。
# 可用环境变量 YOUBAN_PORT 或 `python run.py --port N` 覆盖。
DEFAULT_PORT = 8770
HOST = os.environ.get("YOUBAN_HOST", "127.0.0.1")
PORT = int(os.environ.get("YOUBAN_PORT", str(DEFAULT_PORT)))
