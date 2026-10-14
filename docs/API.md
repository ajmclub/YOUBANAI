# 游伴 AI · API 契约 v1.0

> 本文档是前后端唯一契约。C 端 H5 与 B 端 SaaS 后台均按本契约开发。
> 基础地址：`http://127.0.0.1:8770`（默认端口；若被占用，`run.py` 会自动改用其它端口，
> 请以启动时终端打印的地址为准）
> 所有接口返回 JSON。失败统一返回 `{"ok": false, "error": "..."}`，HTTP 状态码 4xx/5xx。

---

## 0. 通用约定

### 0.1 统一响应包装

成功：直接返回业务对象（不额外包 `data`）。
失败：`{"ok": false, "error": "<中文错误信息>"}`

### 0.2 时间格式

统一 `YYYY-MM-DD HH:MM`（字符串）。日期字段额外提供 `ts`（Unix 秒，整数）。

### 0.3 枚举字典

| 枚举 | 取值 |
|---|---|
| `age_band` 年龄层 | `4-8` 亲子探索 / `8-12` 少年冒险 / `12+` 沉浸剧本 |
| `node.kind` 节点类型 | `entry` 入口 / `main` 主线剧情 / `branch` 支线 / `reward` 结算 |
| `node.trigger_type` 触发方式 | `gps` 地理围栏 / `qr` 扫码 / `nfc` 碰一碰 / `prev` 前置节点完成 |
| `node.status` | `locked` / `active` / `done` |
| `task.type` 任务类型 | `observe` 观察 / `find` 寻找 / `photo` 拍摄 / `solve` 解谜 |
| `task.verify_mode` 判定方式 | `auto` 自动（进入即过） / `answer` 文本答案 / `keyword` 关键词 / `photo` 上传照片 |
| `scenario.status` | `online` 已上线 / `review` 审核中 / `draft` 草稿 |
| `material.category` | `history` 历史典故 / `architecture` 建筑风貌 / `heritage` 非遗技艺 / `legend` 民间传说 / `nature` 自然地理 / `geo` 景区地理 |
| `ai.mode` | `mainline` 生成主线 / `task` 生成任务 / `dialog` 生成对话 / `reward` 生成奖励 / `full` 一键生成全剧本 |
| `event.type` | `story` / `device` / `content` / `node` / `reward` |

### 0.4 品牌常量（前端可直接使用）

```
深夜蓝  #0B1020    暖白  #F5F1E8    沙金  #E8B45A
森林绿  #4FA08C    活力橙 #F0873F
```

---

## 1. C 端接口 `/api/c`

### 1.1 `POST /api/c/activate` 开箱激活潮玩

打开包装 → 输入激活码 → 给伙伴取名。原型 P07「第一次使用」。

**请求**
```json
{ "code": "YB-XA-2026-0001", "nickname": "阿游", "family_name": "小小探险家" }
```
- `code`：潮玩底部激活码。种子数据内置可用码：`YB-XA-2026-0001`（西安限定）、`YB-BJ-2026-0002`（北京限定）、`YB-HZ-2026-0003`（杭州限定）。
- `nickname`：孩子给伙伴取的名字（1-8 字），默认「阿游」。

**响应**
```json
{
  "ok": true,
  "user": { "id": 1, "nickname": "小小探险家", "family_name": "小小探险家 · 王家",
            "level": 1, "level_name": "初识伙伴", "growth_total": 0, "avatar": "🧭" },
  "device": { "id": 1, "code": "YB-XA-2026-0001", "nickname": "阿游",
              "sku_name": "阿游 · 大唐限定款", "city": "西安", "status": "activated" },
  "greeting": "你愿意带我一起去看看这个世界吗？"
}
```

**错误**：激活码不存在 → `{"ok": false, "error": "激活码不存在或已被使用"}`

### 1.2 `GET /api/c/home` 旅伴首页

原型 Tab1「旅伴」。

**Query**：`user_id`（必填），`lat`、`lng`（选填，用于定位文案）

**响应**
```json
{
  "user": { "id": 1, "nickname": "小小探险家", "level": 3, "level_name": "探索家",
            "growth_total": 361, "avatar": "🧭" },
  "device": { "id": 1, "nickname": "阿游", "city": "西安", "sku_name": "阿游 · 大唐限定款",
              "outfit": "大唐限定装扮", "outfit_count": 3, "gear_count": 2 },
  "location": { "park_id": 1, "name": "西安 · 大唐不夜城", "city": "西安",
                "weather": "晴 24°", "tip": "宜出行冒险", "lat": 34.34, "lng": 108.94 },
  "speech": "嗨！我是阿游 👋 今天我们去哪儿冒险？",
  "status_pill": "正在西安等你 · 附近有 3 个故事待开启",
  "today_adventure": {
    "scenario_id": 1, "title": "大唐密令", "chapter_idx": 3, "chapter_title": "密令现世",
    "node_id": 5, "node_name": "密令现世", "node_place": "大雁塔",
    "done_nodes": 6, "total_nodes": 10, "percent": 60
  },
  "quick_actions": [ {"key": "chat", "label": "AI对话"}, {"key": "task", "label": "任务"},
                     {"key": "badge", "label": "徽章"}, {"key": "dress", "label": "换装"} ],
  "nearby_nodes": [
    { "node_id": 3, "name": "大雁塔 · 密令现世", "kind": "main", "kind_label": "主线剧情",
      "desc": "需观察建筑纹样", "distance_m": 120, "emoji": "🏯", "status": "active" }
  ],
  "badge_count": 8, "badge_total": 24
}
```

> **注意 `node_place` 的用途**：`chapter_title` 与 `node_name` 可能同名
> （如第 3 章「密令现世」下就是节点「密令现世」）。首页「今日冒险」卡片
> 请渲染为 `第 {chapter_idx} 章 · {chapter_title} · {node_place}`，
> 即「第 3 章 · 密令现世 · 大雁塔」，与原型一致；`node_place` 为空时回退 `node_name`。

### 1.3 `GET /api/c/explore` 探索 · 我的故事地图

原型 Tab2「探索」。

**Query**：`user_id`

**响应**
```json
{
  "stats": { "lit_cities": 5, "total_cities": 12, "badges": 23, "stories_done": 8 },
  "nodes": [
    { "city": "北京", "scenario": "皇家秘境", "emoji": "🏛️", "state": "done",
      "x": 66, "y": 13, "tooltip": "北京 · 皇家秘境 ✓ 已点亮" }
  ],
  "cities": [
    { "scenario_id": 1, "city": "西安", "title": "大唐密令", "emoji": "🏯",
      "tagline": "一封来自千年前的信，正在等待你", "state": "ongoing",
      "state_label": "探索中", "progress_percent": 60 }
  ]
}
```
- `state`：`done` 已点亮 / `ongoing` 探索中 / `locked` 未解锁
- `x`、`y`：地图百分比坐标（0-100），直接用于绝对定位

### 1.4 `POST /api/c/chat` 与阿游对话

原型 Tab3「对话」。

**请求**
```json
{ "user_id": 1, "text": "好呀！我这就去找～", "lat": 34.34, "lng": 108.94 }
```

**响应**
```json
{
  "messages": [ { "role": "ai", "text": "太棒啦！找到 3 个特殊符号，我就把藏了很久的徽章送给你 ✨" } ],
  "quest_card": {
    "kicker": "NEW QUEST · 主线任务", "title": "密令现世",
    "desc": "观察大雁塔的砖纹图案，找出隐藏在其中的 3 个神秘符号。",
    "cta": "接受任务 →", "task_id": 1, "node_id": 3
  },
  "suggestions": ["附近还有什么故事？", "我有点累了", "给我讲讲大雁塔"]
}
```
- `quest_card` 可为 `null`（无新任务时）。

### 1.5 `GET /api/c/scenario/{scenario_id}` 剧本详情

原型 Tab4「剧本」。

**Query**：`user_id`

**响应**
```json
{
  "id": 1, "title": "大唐密令", "city": "西安", "emoji": "🏯",
  "kicker": "AI 剧本游 · 西安 34.34°N",
  "subtitle": "一封来自千年前的神秘信件出现了……",
  "meta": "跟随阿游，破解大雁塔的秘密。",
  "age_band": "8-12", "age_label": "少年冒险",
  "chapters_count": 5, "current_chapter": 3,
  "progress_percent": 60,
  "chapters": [
    { "idx": 1, "title": "长安初遇", "summary": "你带着阿游走进古城，故事从此开始。",
      "state": "done", "nodes": [
        { "id": 1, "name": "抵达大雁塔", "kind": "entry", "type_label": "ENTRY · 入口",
          "desc": "GPS 触发", "state": "done" } ] },
    { "idx": 3, "title": "密令现世", "summary": "阿游说，大雁塔的砖纹里藏着方向的答案。",
      "state": "now", "nodes": [
        { "id": 3, "name": "密令现世", "kind": "main", "type_label": "STORY NODE",
          "desc": "任务触发", "state": "active",
          "current_task": { "id": 1, "title": "找出塔身上 3 个特殊符号", "type": "observe",
                            "progress": "1/3", "done": 1, "total": 3 } } ] }
  ]
}
```
- 章节 `state`：`done` / `now` / `todo`

### 1.6 `POST /api/c/locate` 位置上报与剧情触发

核心闭环：位置 → 识别 → AI 角色出现 → 任务。原型 P10。

**请求**
```json
{ "user_id": 1, "lat": 34.2186, "lng": 108.9644 }
```

**响应**
```json
{
  "park": { "id": 1, "name": "西安 · 大唐不夜城" },
  "triggered": [
    { "node_id": 3, "scenario_id": 1, "name": "密令现世", "kind": "main",
      "kind_label": "STORY NODE · 主线剧情", "distance_m": 12,
      "story_text": "阿游说：塔身上的砖纹里，藏着长安城的方向……",
      "ai_dialog": "哇！你走到大雁塔啦 🎉 我感觉到这里有千年前的故事在呼唤我们～",
      "task": { "id": 1, "title": "观察大雁塔的砖纹", "type": "observe", "type_label": "观察" } }
  ],
  "nearby": [ { "node_id": 5, "name": "铜钱线索", "distance_m": 340 } ]
}
```

### 1.7 `GET /api/c/task/{task_id}` 任务详情

**Query**：`user_id`

**响应**
```json
{
  "id": 1, "title": "观察大雁塔的砖纹", "type": "observe", "type_label": "观察",
  "desc": "在塔身寻找 3 个特殊符号，注意砖块上的莲花纹与卷草纹。",
  "age_band": "8-12", "verify_mode": "keyword",
  "hint": "提示：先看塔基，再看塔身第二层。",
  "target_count": 3, "done_count": 1,
  "options": null,
  "reward_preview": { "growth": {"observe": 12, "knowledge": 6}, "badge": null }
}
```
- `verify_mode = answer` 时 `options` 为 `["A. 莲花纹","B. 卷草纹", ...]`。

### 1.8 `POST /api/c/task/{task_id}/submit` 提交任务

**请求**
```json
{ "user_id": 1, "answer": "莲花纹", "photo_note": "拍到了塔基的莲花纹", "count": 2 }
```

**响应（通过）**
```json
{
  "pass": true,
  "feedback": "太棒了！你观察得真仔细 ✨",
  "growth_gain": { "observe": 12, "knowledge": 6 },
  "growth_total": 379,
  "level_up": null,
  "badge": { "id": 1, "name": "大唐探索家", "emoji": "🏯", "desc": "完成《大唐密令》全部章节" },
  "node_completed": false,
  "next_node": { "id": 4, "name": "纹样之谜" }
}
```
**响应（未通过）**
```json
{ "pass": false, "feedback": "再仔细看看塔基上的花纹哦～", "growth_gain": { "observe": 2 }, "growth_total": 363, "level_up": null, "badge": null }
```
- `level_up`：升级时返回 `{"level": 4, "level_name": "资深探险家"}`，否则 `null`。
- `growth_gain`：本次实际增加的成长值；未通过时给 20% 保底成长值（至少 1 点）。
- `badge`：本次解锁的徽章，未解锁时为 `null`。
- `task_progress`：`{done, total}`，用于 `target_count > 1` 的计数型任务。

### 1.9 `GET /api/c/mine` 我的

原型 Tab5「我的」。

**Query**：`user_id`

**响应**
```json
{
  "user": { "id": 1, "nickname": "小小探险家", "family_name": "小小探险家 · 王家",
            "level": 3, "level_name": "探索家", "growth_total": 361, "avatar": "🧭",
            "travel_days": 12, "cities": 5 },
  "growth": [ {"dim": "explore", "label": "探索", "value": 78},
              {"dim": "create", "label": "创造", "value": 62},
              {"dim": "observe", "label": "观察", "value": 85},
              {"dim": "knowledge", "label": "知识", "value": 70},
              {"dim": "courage", "label": "勇气", "value": 66} ],
  "badges": [ { "id": 1, "name": "大唐探索家", "emoji": "🏯", "got": true,
                "city": "西安", "rarity": "rare", "rarity_label": "稀有", "desc": "…" },
              { "id": 5, "name": "飞天传人", "emoji": "🏜️", "got": false,
                "city": "敦煌", "rarity": "legend", "rarity_label": "传说", "desc": "…" } ],
  "badge_stat": { "got": 8, "total": 24 },
  "toy": { "device_id": 1, "nickname": "阿游", "sku_name": "阿游 · 大唐限定款",
           "outfit": "大唐限定装扮", "outfits": 3, "gear": 2 },
  "entries": [ {"key": "map", "label": "我的旅行地图", "value": "5 座城市"},
               {"key": "fav", "label": "我的收藏", "value": "23 件"},
               {"key": "honor", "label": "成就与称号", "value": "Lv.3"},
               {"key": "settings", "label": "设置", "value": ""} ]
}
```
- `badges[]` 的 `rarity` 为 `common / rare / legend`，同时提供中文 `rarity_label`
  （`常见 / 稀有 / 传说`）。
- `next_level` 含 `floor` / `ceil` / `percent`，`percent` 是**本级之内**的进度。
- `entries` 由后端给出；C 端会在「设置」之前自行插入一项「家长模式 · 成长报告」，
  因此前端不应假设 `entries` 就是最终列表。

### 1.10 `GET /api/c/wardrobe` 换装

**Query**：`user_id`

**响应**
```json
{ "current": "大唐限定装扮",
  "items": [ { "id": 1, "name": "大唐限定装扮", "city": "西安", "emoji": "🏯",
               "type": "outfit", "unlocked": true, "owned": true } ],
  "gear": [ { "id": 11, "name": "探险背包", "emoji": "🎒", "unlocked": true } ] }
```

### 1.11 `POST /api/c/wardrobe/equip` 装备换装

**请求** `{ "user_id": 1, "item_id": 2 }`
**响应** `{ "ok": true, "current": "皇家限定装扮" }`

### 1.12 `GET /api/c/session` 恢复会话
### 1.12.1 `GET /api/c/demo` 演示账号

见第 5 节「演示与调试接口」。

---

## 1A. C 端 · 家长模式 `/api/c/parent`

> 商业计划书把**家长**列为三大用户之一（「想让孩子玩得开心，也希望旅行有内容，
> 但缺少好的亲子体验工具」），两个原型都没有覆盖家长视角。
> 本节补齐「成长报告」：所有数字与文案均由数据库真实记录推导，
> 知识点从景区素材库反查，提问由孩子真实完成过的任务生成。

### 1.12 `GET /api/c/parent/summary` 家庭成长概览

**Query**：`user_id`（必填）

```json
{
  "child": { "id": 1, "nickname": "小小探险家", "family_name": "小小探险家 · 王家",
             "avatar": "🧭", "level": 3, "level_name": "探索家", "growth_total": 361,
             "age_band": "8-12", "age_label": "少年冒险", "travel_days": 12 },
  "device": { "nickname": "阿游", "sku_name": "阿游 · 大唐限定款", "outfit": "大唐限定装扮" },
  "next_level": { "level": 3, "name": "探索家", "need": 239, "next_name": "资深探险家",
                  "at_max": false, "floor": 300, "ceil": 600, "percent": 20 },
  "overview": [
    { "key": "cities",  "label": "走过的城市",   "value": 5,  "unit": "座",   "of": 12 },
    { "key": "stories", "label": "完成的剧本",   "value": 3,  "unit": "个",   "of": 7  },
    { "key": "nodes",   "label": "探索的剧情点", "value": 6,  "unit": "个",   "of": 51 },
    { "key": "tasks",   "label": "完成的任务",   "value": 7,  "unit": "个",   "of": null },
    { "key": "badges",  "label": "获得的徽章",   "value": 8,  "unit": "枚",   "of": 24 },
    { "key": "minutes", "label": "累计探索时长", "value": 94, "unit": "分钟", "of": null }
  ],
  "growth": [ { "dim": "explore", "label": "探索", "value": 78 } ],
  "growth_note": "孩子在「观察」上表现最突出（85），「创造」相对最少（62），整体发展比较自然。",
  "weekly": { "days": ["09-16"], "labels": ["周三"], "values": [0],
              "total": 9, "peak": 9 },
  "badges_recent": [ { "id": 1, "name": "大唐探索家", "emoji": "🏯", "desc": "…",
                       "rarity": "rare", "rarity_label": "稀有",
                       "got_at": "09-22 15:10" } ],
  "scenarios": [ { "scenario_id": 1, "title": "大唐密令", "emoji": "🏯", "city": "西安",
                   "park_name": "西安 · 大唐不夜城",
                   "place_label": "西安 · 大唐不夜城",
                   "percent": 60, "status": "ongoing",
                   "status_label": "进行中", "updated_at": "09-22 15:10" } ],
  "suggestions": [ { "dim": "create", "label": "创造", "value": 62,
                     "title": "「创造」还有提升空间",
                     "advice": "鼓励孩子把旅途中看到的东西画下来、讲出来，或者自己编一个后续剧情。" } ]
}
```

**规则说明**
- **`place_label`**：后端已去重的「可直接渲染」地点文案。`park_name` 本身是
  「西安 · 大唐不夜城」，若前端再拼上 `city`（西安）会渲染成
  「西安 · 西安 · 大唐不夜城」；请直接使用 `place_label`，不要在客户端拼接。
- **`next_level.percent`** 是**本级之内**的进度 `(growth_total - floor) / (ceil - floor) * 100`；
  没有 `floor`/`ceil` 时前端只能算成 `growth_total / (growth_total + need)`，
  那是「占下一级总量的比例」，语义不同，不要再用那种估算。
- `rarity_label` 与其它枚举一致，取值 `常见 / 稀有 / 传说`。
- `overview` 的 `of` 为 `null` 表示该项没有上限（如任务数、时长）。
  `stories.of` 只统计**非草稿**剧本（当前 7 个）。
- `growth_note` 由五维最高/最低值与差值自动生成。
- `weekly` 为近 7 天每天**通过的任务数**（真实统计，非估算）。
- `minutes` 按孩子实际通过的任务在 `tasks.avg_minutes` 上求和。
- `suggestions` 为规则生成，最多 4 条，来源依次为：
  五维中最低的两项 → 下一座未点亮的城市 → 当前可获取但尚未获得的徽章。

### 1.13 `GET /api/c/parent/reports` 旅行报告列表

**Query**：`user_id`

```json
{ "items": [ { "scenario_id": 1, "title": "大唐密令", "emoji": "🏯", "city": "西安",
               "percent": 60, "status": "ongoing", "status_label": "进行中",
               "updated_at": "09-22 15:10" } ] }
```

### 1.14 `GET /api/c/parent/report` 单次旅行报告

**Query**：`user_id`、`scenario_id`（均必填）

```json
{
  "user_id": 1,
  "scenario": { "id": 1, "title": "大唐密令", "emoji": "🏯", "city": "西安",
                "park_name": "西安 · 大唐不夜城",
                "place_label": "西安 · 大唐不夜城",
                "age_band": "8-12", "age_label": "少年冒险",
                "subtitle": "一封来自千年前的神秘信件出现了……", "worldview": "唐长安城…" },
  "summary": { "visited": 6, "done": 4, "total": 10, "percent": 60,
               "status": "ongoing", "status_label": "进行中",
               "chapters_done": 2, "chapters_total": 5,
               "tasks_done": 7, "minutes": 94,
               "started_at": "09-17 15:38", "updated_at": "09-22 18:38" },
  "chapters": [ { "idx": 1, "title": "长安初遇", "summary": "…", "state": "done",
                  "nodes": [ { "name": "抵达大雁塔", "place": "大雁塔", "state": "done" } ] } ],
  "trail": [ { "at": "09-17 15:38", "node": "大雁塔 · 抵达大雁塔",
               "event": "到达剧情点", "kind": "entry", "type": "visit", "source": "gps" },
             { "at": "09-18 09:12", "node": "抵达大雁塔，用眼睛找到塔的层数",
               "event": "完成任务", "kind": "task", "type": "task", "passed": true } ],
  "growth_gain": { "observe": 68, "knowledge": 44, "explore": 42, "courage": 20 },
  "badges": [ { "id": 1, "name": "大唐探索家", "emoji": "🏯", "desc": "…" } ],
  "knowledge": [ { "material_id": 3, "title": "大雁塔塔影的传说",
                  "category": "legend", "category_label": "民间传说",
                  "node": "抵达大雁塔", "place": "大雁塔",
                  "point": "民间传说大雁塔的塔影会随时间指向不同方向……" } ],
  "questions": [
    "今天你完成了「找出塔身上 3 个特殊符号」，你还记得答案是什么吗？",
    "在大雁塔，你第一眼注意到的是什么？有没有什么是后来才发现的？",
    "考考你：关于「关中平原的地理形胜」，你能用自己的话讲给爸爸妈妈听吗？"
  ]
}
```

**规则说明**
- `knowledge`：由孩子**实际到访过的节点**出发，按节点的 `place` 回查该景区素材库
  （`materials`，仅 `status='indexed'`），命中则取该素材前两句作为「知识点」，
  并标注来源节点；同一素材不重复，最多 6 条。
- `questions`：固定 3 条 ——
  ① 取孩子最近一次通过的任务，问是否还记得答案；
  ② 取最近到访的节点，问第一印象与后来的新发现；
  ③ 从该剧本所属景区素材库取一条知识点，让孩子复述。
- `trail` 由 `node_visits` 与 `task_submissions` 合并后按时间排序。
- `minutes` 同样按实际通过任务在 `tasks.avg_minutes` 上求和。

**错误**：`user_id` 不存在或 `scenario_id` 不存在 → `用户不存在` / `剧本不存在`。

---

## 2. B 端接口 `/api/admin`

### 2.1 `GET /api/admin/dashboard` 数据看板

```json
{
  "date_label": "2026-09-22 周二",
  "kpis": [ { "key": "visitors", "label": "今日入园游客", "value": "12,486", "unit": "人次",
              "delta": "8.2", "delta_dir": "up", "delta_label": "较昨日" } ],
  "trend": { "days": ["09-09"], "visitors": [9800], "story_opens": [3200] },
  "funnel": [ { "label": "到达景区", "value": 12486, "percent": 100 } ],
  "hot_nodes": [ { "rank": 1, "name": "大雁塔 · 密令现世", "kind_label": "主线剧情点", "value": 8420 } ],
  "timeline": [ { "title": "小小探险家 完成了《大唐密令》第 3 章",
                  "detail": "获得徽章「大唐探索家」 · 大雁塔", "ago": "2 分钟前" } ]
}
```

### 2.2 `GET /api/admin/scenarios` 剧本管理

**Query**：`status`（选填：`online`/`review`/`draft`），`park_id`

```json
{
  "summary": { "total": 5, "online": 3, "review": 1, "draft": 1 },
  "items": [ { "id": 1, "title": "大唐密令", "park_name": "西安 · 大雁塔",
               "chapters_count": 5, "nodes_count": 10, "status": "online",
               "status_label": "已上线", "completion_rate": 68, "updated_at": "09-22 14:20" } ]
}
```

### 2.3 `POST /api/admin/scenarios` 新建剧本

**请求** `{ "title": "新剧本", "park_id": 1, "age_band": "8-12" }`
**响应** 新建的 scenario 对象（同 2.2 items 元素）。

### 2.4 `GET /api/admin/scenarios/{id}` 剧本详情（含画布）

剧情编辑器数据源。节点自带 `x`、`y` 画布坐标与 `links`。

```json
{
  "id": 1, "title": "大唐密令", "city": "西安", "park_name": "西安 · 大雁塔",
  "status": "online", "status_label": "已上线",
  "chapters": [ {"id": 1, "idx": 1, "title": "长安初遇"} ],
  "nodes": [ { "id": 3, "chapter_id": 1, "name": "密令现世", "kind": "main",
               "type_label": "STORY NODE · 当前", "desc": "任务触发 · 编辑中",
               "trigger_type": "gps", "lat": 34.2186, "lng": 108.9644, "radius_m": 40,
               "age_band": "8-12", "story_text": "阿游说：……", "status": "active",
               "x": 372, "y": 170, "task_count": 1 } ],
  "links": [ { "from": 1, "to": 2, "color": "gold" }, { "from": 3, "to": 4, "color": "purple" } ]
}
```

### 2.5 `PUT /api/admin/nodes/{id}` 保存节点

**请求**
```json
{ "name": "密令现世", "kind": "main", "trigger_type": "gps", "story_text": "...",
  "age_band": "8-12", "x": 372, "y": 170, "lat": 34.2186, "lng": 108.9644, "radius_m": 40 }
```
**响应** 更新后的节点对象。

### 2.6 `POST /api/admin/nodes` 新建节点
### 2.7 `DELETE /api/admin/nodes/{id}` 删除节点 → `{"ok": true}`

### 2.8 `GET /api/admin/tasks` 任务中心

**Query**：`type`（选填）

```json
{
  "summary": { "total": 42, "done_today": 8420, "avg_minutes": 12, "join_rate": 74 },
  "items": [ { "id": 1, "title": "观察大雁塔的砖纹", "type": "observe", "type_label": "观察",
               "scenario_title": "大唐密令", "age_band": "8-12",
               "completion_rate": 81, "enabled": true } ]
}
```

### 2.9 `POST /api/admin/tasks` / `PUT /api/admin/tasks/{id}` 新建/编辑任务

### 2.10 `GET /api/admin/materials` 内容素材库

```json
{
  "categories": [ { "key": "history", "label": "历史典故", "emoji": "📜", "count": 128 } ],
  "index_steps": [ { "label": "上传资料", "state": "done" },
                   { "label": "结构化解析", "state": "done" },
                   { "label": "向量化入库", "state": "done" },
                   { "label": "可生成剧本", "state": "cur" } ],
  "index_note": "已完成 439 条素材的语义向量化，AI Story Engine 可基于此生成《大唐密令》后续章节。",
  "recent": [ { "title": "大雁塔砖纹样式考据.pdf", "category_label": "建筑风貌",
                "size": "2.4MB", "status": "indexed", "status_label": "已入库" } ]
}
```

### 2.11 `POST /api/admin/materials` 上传素材

**请求** `{ "park_id": 1, "category": "history", "title": "唐代长安城坊市考", "content": "……" }`
**响应** 新建素材对象。

### 2.12 `GET /api/admin/visitors` 游客管理

```json
{
  "summary": { "active_families": 2140, "total_users": 68420, "avg_minutes": 96, "repeat_rate": 22 },
  "items": [ { "id": 1, "name": "小小探险家 · 王家", "city": "西安", "scenario_title": "大唐密令",
               "level": 3, "growth_total": 361, "last_play": "09-22 15:10", "status": "ongoing",
               "status_label": "进行中" } ]
}
```

### 2.13 `GET /api/admin/visitors/{id}` 游客详情

```json
{
  "id": 1, "name": "小小探险家 · 王家", "city": "西安", "level": 3, "level_name": "探索家",
  "growth_total": 361, "device": { "nickname": "阿游", "sku_name": "阿游 · 大唐限定款" },
  "growth": [ {"dim": "explore", "label": "探索", "value": 78} ],
  "badges": [ {"name": "大唐探索家", "emoji": "🏯", "got": true} ],
  "trail": [ { "node_name": "大雁塔 · 密令现世", "at": "09-22 15:10", "event": "完成任务" } ]
}
```

### 2.14 `GET /api/admin/iptoys` 潮玩 IP 管理

```json
{
  "summary": { "activated": 128600, "today_activated": 128, "online_rate": 92, "city_editions": 6 },
  "character": { "name": "阿游", "positioning": "儿童 AI 旅行伙伴",
                 "dressable": "城市服装 / 探险装备", "live_editions": 6, "avatar_emoji": "🧭" },
  "editions": [ { "id": 1, "title": "大唐密令", "city": "西安", "emoji": "🏯" } ],
  "skus": [ { "id": 1, "name": "阿游 · 大唐限定款", "city": "西安", "stock": 3240,
              "activated": 28610, "activation_rate": 88, "status": "onsale",
              "status_label": "在售", "price": 399 } ]
}
```

### 2.14.1 `POST /api/admin/iptoys/editions` 新增城市限定款

对应后台「潮玩 IP 管理」右上角「新增限定款」按钮。

**请求**
```json
{ "name": "阿游 · 苏绣限定款", "city": "苏州", "park_id": 8,
  "emoji": "🌉", "stock": 800, "price": 399 }
```
- `park_id` 必须存在，否则返回 `景区不存在`。
- 新 SKU 的 `status` 固定为 `onsale`，`activated` 初始为 0。

**响应**
```json
{ "ok": true, "id": 7, "name": "阿游 · 苏绣限定款", "city": "苏州",
  "park_name": "苏州 · 拙政园", "status": "onsale", "status_label": "在售" }
```

### 2.15 `GET /api/admin/analytics` 数据分析

```json
{
  "funnel": [ {"label": "到达景区", "value": 86420, "percent": 100} ],
  "age_distribution": [ {"label": "4-8岁", "percent": 42, "value": 11270} ],
  "revenue": { "total": "¥286,400", "items": [ {"label": "潮玩销售分成", "amount": "¥128,200"} ] },
  "retention": [ {"label": "首周", "percent": 100} ]
}
```

### 2.16 `GET /api/admin/park` 景区与联名

**Query**：`park_id`（选填，默认 1）

```json
{
  "park": { "id": 1, "name": "西安 · 大唐不夜城", "city": "西安", "lat": 34.34, "lng": 108.94,
            "radius_m": 1500, "verified": true, "scenario_count": 1, "node_count": 10,
            "partner_mode": "内容制作 + 运营分成" },
  "revenue_share": [ { "item": "C 端 · 潮玩销售", "park_share": "15%", "platform_share": "85%" } ],
  "cooperations": [ { "name": "西安文旅集团", "type": "IP 联名", "status": "active",
                      "status_label": "合作中", "since": "2026-03" } ]
}
```

### 2.17 `PUT /api/admin/park/{id}` 保存景区配置

### 2.18 `POST /api/admin/ai/generate` AI Story Engine 生成

原型 P12 + 后台「AI 生成剧本」。

**请求**
```json
{ "park_id": 1, "mode": "full", "age_band": "8-12",
  "style": "悬疑解谜，融入唐代历史知识，鼓励孩子观察真实建筑。",
  "scenario_title": "大唐密令 · 续章", "chapter_count": 3, "node_count": 6 }
```
- `mode`：`mainline` / `task` / `dialog` / `reward` / `full`

**响应（`full` 模式）**
```json
{
  "job_id": 7, "status": "done", "engine": "offline-rule-engine",
  "elapsed_ms": 240,
  "worldview": "……",
  "scenario": { "title": "大唐密令 · 续章", "subtitle": "……", "age_band": "8-12" },
  "chapters": [ { "idx": 1, "title": "……", "summary": "……" } ],
  "nodes": [ { "name": "……", "kind": "main", "trigger_type": "gps",
               "story_text": "……", "ai_dialog": "……",
               "task": { "title": "……", "type": "observe", "verify_mode": "keyword",
                         "desc": "……", "answer": "……", "hint": "……" } } ],
  "rewards": [ { "name": "大唐探索家", "emoji": "🏯", "desc": "……" } ],
  "sources": [ { "material_id": 3, "title": "大雁塔砖纹样式考据.pdf", "category": "architecture" } ],
  "notes": "由离线规则引擎基于 439 条景区素材生成。已入库为草稿剧本（ID 6）。",
  "created_scenario_id": 6
}
```

**响应（`mainline` / `task` / `dialog` / `reward` 模式）** 返回对应字段，其余为 `null`。

### 2.19 `GET /api/admin/ai/jobs` 生成历史

```json
{ "items": [ { "id": 7, "park_name": "西安 · 大雁塔", "mode": "full", "mode_label": "一键生成全剧本",
               "age_band": "8-12", "status": "done", "created_at": "09-22 16:02" } ] }
```

### 2.20 `GET /api/admin/ai/engine` 引擎能力与配置状态

```json
{ "engine": "offline-rule-engine", "llm_enabled": false,
  "llm_provider": null, "llm_model": null,
  "capabilities": [ {"key": "mainline", "label": "生成主线", "desc": "……"} ],
  "setup_hint": "设置环境变量 YOUBAN_LLM_BASE_URL / YOUBAN_LLM_API_KEY / YOUBAN_LLM_MODEL 即可切换真实大模型。" }
```

### 2.21 `GET /api/admin/observability` 运行指标

与 `GET /api/metrics` 等价（后者在系统命名空间下，便于脚本巡检）。
请求指标来自进程内存，业务计数从数据库实时统计。

```json
{
  "requests": {
    "version": "1.0.0", "uptime_seconds": 620,
    "requests_total": 26, "errors_total": 1, "error_rate": 3.85, "avg_ms": 21.0,
    "slow_threshold_ms": 300.0,
    "endpoints": [ { "method": "GET", "path": "/api/c/task/{id}", "count": 7,
                     "avg_ms": 5.4, "max_ms": 13.2, "errors": 0, "slow": 0 } ],
    "slowest": [ { "path": "/api/admin/scenarios", "max_ms": 249.9 } ],
    "recent": [ { "method": "GET", "path": "/api/c/home", "status": 200,
                  "ms": 41.5, "at": "18:38:02" } ]
  },
  "business": {
    "parks": 12, "parks_lit": 5, "scenarios": 8, "scenarios_online": 6,
    "nodes": 51, "tasks": 63, "materials_indexed": 439,
    "users": 6, "devices_activated": 2, "codes_used": 1,
    "node_visits": 6, "task_submissions": 9, "tasks_passed": 9, "task_pass_rate": 100.0,
    "badges_granted": 8, "growth_total": 361,
    "ai_jobs": 0, "ai_scenarios_created": 0, "ai_avg_ms": 0.0,
    "users_with_trail": 1, "events_logged": 6
  },
  "note": "请求指标保存在进程内存中，服务重启即清零；业务计数实时查库。"
}
```

**说明**
- `endpoints[].path` 已做归一化：`/api/c/task/12` → `/api/c/task/{id}`，便于按端点聚合。
- 慢请求阈值 `slow_threshold_ms` 默认 300ms，超过则计入 `slow`。
- 静态资源（`/c/`、`/admin/`）与门户 `/` 不计入日志，但仍计入指标。
- 每个响应都会带 `X-Response-Time` 头（如 `12.4ms`），便于在浏览器 Network 里直接观察。

---

## 3. 静态资源

| 路径 | 内容 |
|---|---|
| `GET /` | 项目门户（C 端 / B 端 / API 文档入口） |
| `GET /c/` | C 端 H5（手机端，桌面自动加手机外框） |
| `GET /admin/` | B 端 SaaS 后台 |
| `GET /docs` | FastAPI 自带 Swagger |
| `GET /health` | 健康检查（含 `uptime_seconds` / `requests_total` / `avg_ms` / `error_rate`） |
| `GET /api/metrics` | 可观测性指标（等价于 `2.21`） |

---

## 4. 关键业务规则

1. **地理围栏触发**：`haversine(user, node) <= node.radius_m` 即触发节点；同一用户同一节点仅首次触发时返回 `triggered`，后续进入 `nearby`。
2. **任务判定**
   - `auto`：进入节点即通过。
   - `keyword`：`answer` 包含任一关键词即通过（不区分大小写与空格）。
   - `answer`：与 `answer` 字段精确匹配（忽略大小写与首尾空格）。
   - `photo`：提交 `photo_note` 非空即视为通过，记录到 `task_submissions`。
3. **成长值**：每次任务通过按 `reward_growth` 增加对应维度；未通过给 20% 保底成长值（至少 1 点）。
4. **等级**：`growth_total` 阈值 `[0,100,300,600,1000,1600,2400,3600,5200,7200]` 对应
   `初识伙伴 / 小旅人 / 探索家 / 资深探险家 / 少年冒险家 / 城市猎人 / 故事收藏家 / 传说旅人 / 星图守护者 / 世界发现者`。
5. **徽章解锁**：剧本所有节点 `done` 时解锁该剧本的 `reward` 徽章；特定节点自带 `reward_badge_id` 时即时解锁。
6. **家长模式统计口径**
   - `走过城市` = 有进度的剧本所属景区去重计数（`of` = 景区总数 12）。
   - `完成的剧本` = `progress.status='done'` 的条数（`of` = 非草稿剧本数 7）。
   - `累计探索时长` = 孩子**实际通过**的任务在 `tasks.avg_minutes` 上求和，无记录时按 12 分钟/任务估算。
   - `knowledge` 只取 `status='indexed'` 的素材，同一素材在同一份报告里只出现一次。
6. **剧本完成率**：`done_nodes / total_nodes * 100`，四舍五入整数。
7. **AI 生成入库**：`mode=full` 时自动创建 `status=draft` 的剧本，节点坐标按画布网格自动布局，`trigger_type` 默认 `gps` 并在景区坐标附近做半径抖动。

---

## 5. 错误码表

| 场景 | error 文案 |
|---|---|
| `user_id` 缺失或不存在 | `用户不存在` |
| 激活码无效 | `激活码不存在或已被使用` |
| 剧本不存在 | `剧本不存在` |
| 节点不存在 | `节点不存在` |
| 任务不存在 | `任务不存在` |
| 景区不存在 | `景区不存在` |
| AI 模式不支持 | `不支持的生成模式` |
