-- ============================================================
-- 游伴 AI (YOUBAN AI) · 数据库结构 v1.0
-- SQLite。所有时间字段统一 'YYYY-MM-DD HH:MM' 文本格式。
-- ============================================================

PRAGMA foreign_keys = ON;

-- ---------- 景区 ----------
CREATE TABLE IF NOT EXISTS parks (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT    NOT NULL,              -- 西安 · 大唐不夜城
  city          TEXT    NOT NULL,              -- 西安
  lat           REAL,
  lng           REAL,
  radius_m      INTEGER DEFAULT 1500,          -- 景区级地理围栏半径
  emoji         TEXT    DEFAULT '🏯',
  weather       TEXT    DEFAULT '晴 24°',
  tip           TEXT    DEFAULT '宜出行冒险',
  verified      INTEGER DEFAULT 1,
  partner_mode  TEXT    DEFAULT '内容制作 + 运营分成',
  -- 地图坐标（探索页中国地图百分比定位）
  map_x         REAL    DEFAULT 50,
  map_y         REAL    DEFAULT 50,
  lit           INTEGER DEFAULT 0,             -- 是否已点亮
  sort_order    INTEGER DEFAULT 0,
  created_at    TEXT
);

-- ---------- 潮玩角色 / IP ----------
CREATE TABLE IF NOT EXISTS characters (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,                 -- 阿游
  positioning   TEXT,                          -- 儿童 AI 旅行伙伴
  dressable     TEXT,                          -- 城市服装 / 探险装备
  avatar_emoji  TEXT DEFAULT '🧭',
  tagline       TEXT
);

-- ---------- 潮玩 SKU ----------
CREATE TABLE IF NOT EXISTS skus (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,                 -- 阿游 · 大唐限定款
  character_id  INTEGER REFERENCES characters(id),
  park_id       INTEGER REFERENCES parks(id),
  city          TEXT,
  emoji         TEXT,
  stock         INTEGER DEFAULT 0,
  activated     INTEGER DEFAULT 0,
  status        TEXT DEFAULT 'onsale',         -- onsale / low / unlisted
  price         REAL DEFAULT 399,
  sort_order    INTEGER DEFAULT 0
);

-- ---------- 激活码 ----------
CREATE TABLE IF NOT EXISTS activation_codes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  code          TEXT UNIQUE NOT NULL,          -- YB-XA-2026-0001
  sku_id        INTEGER REFERENCES skus(id),
  used          INTEGER DEFAULT 0,
  user_id       INTEGER,
  used_at       TEXT
);

-- ---------- 用户 / 家庭 ----------
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname      TEXT NOT NULL,                 -- 小小探险家
  family_name   TEXT,                          -- 小小探险家 · 王家
  avatar        TEXT DEFAULT '🧭',
  city          TEXT DEFAULT '西安',
  level         INTEGER DEFAULT 1,
  growth_total  INTEGER DEFAULT 0,
  travel_days   INTEGER DEFAULT 12,
  age_band      TEXT DEFAULT '8-12',
  created_at    TEXT,
  last_active   TEXT
);

-- ---------- 潮玩设备（已激活的实体潮玩） ----------
CREATE TABLE IF NOT EXISTS devices (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  code          TEXT REFERENCES activation_codes(code),
  sku_id        INTEGER REFERENCES skus(id),
  user_id       INTEGER REFERENCES users(id),
  nickname      TEXT DEFAULT '阿游',           -- 孩子给伙伴取的名字
  outfit        TEXT,                          -- 当前装扮
  status        TEXT DEFAULT 'activated',      -- activated / online / offline
  online        INTEGER DEFAULT 1,
  activated_at  TEXT
);

-- ---------- 成长五维度 ----------
CREATE TABLE IF NOT EXISTS user_growth (
  user_id       INTEGER NOT NULL REFERENCES users(id),
  dim           TEXT    NOT NULL,              -- explore/create/observe/knowledge/courage
  value         INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, dim)
);

-- ---------- 剧本 ----------
CREATE TABLE IF NOT EXISTS scenarios (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id         INTEGER REFERENCES parks(id),
  title           TEXT NOT NULL,               -- 大唐密令
  subtitle        TEXT,
  kicker          TEXT,                        -- AI 剧本游 · 西安 34.34°N
  meta            TEXT,
  emoji           TEXT DEFAULT '🏯',
  age_band        TEXT DEFAULT '8-12',
  status          TEXT DEFAULT 'draft',        -- online/review/draft
  worldview       TEXT,
  chapter_count   INTEGER DEFAULT 0,
  completion_rate INTEGER DEFAULT 0,
  source          TEXT DEFAULT 'manual',       -- manual / ai
  created_at      TEXT,
  updated_at      TEXT
);

-- ---------- 章节 ----------
CREATE TABLE IF NOT EXISTS chapters (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id   INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  idx           INTEGER NOT NULL,
  title         TEXT NOT NULL,
  summary       TEXT
);

-- ---------- STORY NODE 剧情节点 ----------
CREATE TABLE IF NOT EXISTS nodes (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id     INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  chapter_id      INTEGER REFERENCES chapters(id) ON DELETE SET NULL,
  idx             INTEGER DEFAULT 1,
  name            TEXT NOT NULL,
  kind            TEXT DEFAULT 'main',         -- entry/main/branch/reward
  trigger_type    TEXT DEFAULT 'gps',          -- gps/qr/nfc/prev
  lat             REAL,
  lng             REAL,
  radius_m        INTEGER DEFAULT 40,
  age_band        TEXT DEFAULT '8-12',
  place           TEXT,                        -- 大雁塔
  story_text      TEXT,
  ai_dialog       TEXT,
  hint            TEXT,
  reward_badge_id INTEGER,
  x               REAL DEFAULT 100,            -- 画布坐标
  y               REAL DEFAULT 170,
  sort_order      INTEGER DEFAULT 0
);

-- ---------- 剧情连线（编辑器画布） ----------
CREATE TABLE IF NOT EXISTS node_links (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id   INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  from_node     INTEGER NOT NULL,
  to_node       INTEGER NOT NULL,
  color         TEXT DEFAULT 'gold'            -- gold/purple/forest
);

-- ---------- 任务 ----------
CREATE TABLE IF NOT EXISTS tasks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id         INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
  scenario_id     INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
  title           TEXT NOT NULL,
  type            TEXT DEFAULT 'observe',      -- observe/find/photo/solve
  age_band        TEXT DEFAULT '8-12',
  desc            TEXT,
  verify_mode     TEXT DEFAULT 'keyword',      -- auto/answer/keyword/photo
  answer          TEXT,                        -- 正确答案
  keywords        TEXT,                        -- 逗号分隔关键词
  hint            TEXT,
  target_count    INTEGER DEFAULT 1,           -- 需要完成的数量（如找 3 个符号）
  options         TEXT,                        -- JSON 数组（选择题）
  reward_growth   TEXT,                        -- JSON: {"observe":12,"knowledge":6}
  reward_badge_id INTEGER,
  completion_rate INTEGER DEFAULT 0,
  enabled         INTEGER DEFAULT 1,
  avg_minutes     INTEGER DEFAULT 12
);

-- ---------- 徽章 ----------
CREATE TABLE IF NOT EXISTS badges (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  emoji         TEXT,
  city          TEXT,
  scenario_id   INTEGER REFERENCES scenarios(id) ON DELETE SET NULL,
  rarity        TEXT DEFAULT 'common',         -- common/rare/legend
  desc          TEXT,
  sort_order    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_badges (
  user_id       INTEGER NOT NULL REFERENCES users(id),
  badge_id      INTEGER NOT NULL REFERENCES badges(id),
  got_at        TEXT,
  PRIMARY KEY (user_id, badge_id)
);

-- ---------- 装扮 / 装备 ----------
CREATE TABLE IF NOT EXISTS wardrobe_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  city          TEXT,
  emoji         TEXT,
  type          TEXT DEFAULT 'outfit',         -- outfit / gear
  park_id       INTEGER REFERENCES parks(id),
  desc          TEXT,
  sort_order    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_items (
  user_id       INTEGER NOT NULL REFERENCES users(id),
  item_id       INTEGER NOT NULL REFERENCES wardrobe_items(id),
  got_at        TEXT,
  PRIMARY KEY (user_id, item_id)
);

-- ---------- 剧本进度 ----------
CREATE TABLE IF NOT EXISTS progress (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  scenario_id   INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
  chapter_idx   INTEGER DEFAULT 1,
  percent       INTEGER DEFAULT 0,
  status        TEXT DEFAULT 'ongoing',        -- ongoing / done
  started_at    TEXT,
  updated_at    TEXT,
  UNIQUE (user_id, scenario_id)
);

CREATE TABLE IF NOT EXISTS node_visits (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  node_id       INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  scenario_id   INTEGER,
  source        TEXT DEFAULT 'gps',            -- gps/qr/chat/home/explore
  visited_at    TEXT,
  UNIQUE (user_id, node_id)
);

CREATE TABLE IF NOT EXISTS task_submissions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  task_id       INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  node_id       INTEGER,
  answer        TEXT,
  photo_note    TEXT,
  passed        INTEGER DEFAULT 0,
  growth_gain   TEXT,                          -- JSON
  submitted_at  TEXT
);

-- ---------- 内容素材 ----------
CREATE TABLE IF NOT EXISTS materials (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id       INTEGER REFERENCES parks(id),
  category      TEXT NOT NULL,                 -- history/architecture/heritage/legend/nature/geo
  title         TEXT NOT NULL,
  content       TEXT,
  tags          TEXT,
  size_label    TEXT DEFAULT '86KB',
  status        TEXT DEFAULT 'indexed',        -- indexed/parsing/failed
  uploaded_at   TEXT
);

-- ---------- AI 生成任务 ----------
CREATE TABLE IF NOT EXISTS ai_jobs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id         INTEGER REFERENCES parks(id),
  mode            TEXT DEFAULT 'full',
  age_band        TEXT,
  style           TEXT,
  scenario_title  TEXT,
  chapter_count   INTEGER,
  node_count      INTEGER,
  engine          TEXT,
  status          TEXT DEFAULT 'done',
  elapsed_ms      INTEGER DEFAULT 0,
  result_json     TEXT,
  created_scenario_id INTEGER,
  created_at      TEXT
);

-- ---------- 实时动态 / 埋点 ----------
CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  type          TEXT DEFAULT 'story',          -- story/device/content/node/reward
  title         TEXT NOT NULL,
  detail        TEXT,
  park_id       INTEGER REFERENCES parks(id),
  created_at    TEXT
);

-- ---------- 日指标 ----------
CREATE TABLE IF NOT EXISTS metrics_daily (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id         INTEGER REFERENCES parks(id),
  day             TEXT NOT NULL,               -- MM-DD
  seq             INTEGER DEFAULT 0,           -- 排序用（近 14 天 0..13）
  visitors        INTEGER DEFAULT 0,
  story_opens     INTEGER DEFAULT 0,
  completes       INTEGER DEFAULT 0,
  revenue         REAL DEFAULT 0,
  UNIQUE (park_id, day)
);

-- ---------- 营收流水 ----------
CREATE TABLE IF NOT EXISTS revenue (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id       INTEGER REFERENCES parks(id),
  channel       TEXT NOT NULL,                 -- toy/ticket/member/license
  amount        REAL DEFAULT 0,
  period        TEXT,
  created_at    TEXT
);

-- ---------- 分账配置 ----------
CREATE TABLE IF NOT EXISTS revenue_shares (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id         INTEGER REFERENCES parks(id),
  item            TEXT NOT NULL,
  park_share      TEXT,
  platform_share  TEXT,
  note            TEXT,
  sort_order      INTEGER DEFAULT 0
);

-- ---------- IP 联名合作 ----------
CREATE TABLE IF NOT EXISTS cooperations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  park_id       INTEGER REFERENCES parks(id),
  name          TEXT NOT NULL,
  type          TEXT,
  status        TEXT DEFAULT 'active',
  since         TEXT,
  amount        REAL DEFAULT 0
);

-- ---------- 索引 ----------
CREATE INDEX IF NOT EXISTS idx_nodes_scenario   ON nodes (scenario_id, idx);
CREATE INDEX IF NOT EXISTS idx_tasks_node        ON tasks (node_id);
CREATE INDEX IF NOT EXISTS idx_tasks_scenario    ON tasks (scenario_id);
CREATE INDEX IF NOT EXISTS idx_chapters_scenario ON chapters (scenario_id, idx);
CREATE INDEX IF NOT EXISTS idx_materials_park    ON materials (park_id, category);
CREATE INDEX IF NOT EXISTS idx_visits_user       ON node_visits (user_id);
CREATE INDEX IF NOT EXISTS idx_subs_user         ON task_submissions (user_id, task_id);
CREATE INDEX IF NOT EXISTS idx_events_park       ON events (park_id, id);
