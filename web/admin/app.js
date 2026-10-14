/* ==========================================================================
   游伴 AI · 景区剧本游运营台（B 端 SaaS 后台）—— app.js
   纯原生 JS，无框架、无构建、无外部依赖。
   接口严格遵循 docs/API.md，基础地址为同源相对路径 /api/admin/*
   ========================================================================== */
(function () {
  'use strict';

  /* ======================= 1. 常量与字典 ======================= */

  var API_BASE = '/api/admin';

  /* 内置景区目录（API 契约未提供景区列表接口，仅提供 GET /api/admin/park?park_id=N） */
  var PARKS = [
    { id: 1, name: '西安 · 大唐不夜城', city: '西安' },
    { id: 2, name: '北京 · 故宫', city: '北京' },
    { id: 3, name: '杭州 · 西湖', city: '杭州' },
    { id: 4, name: '成都 · 熊猫基地', city: '成都' },
    { id: 5, name: '贵州 · 苗岭', city: '贵州' },
    { id: 6, name: '敦煌 · 莫高窟', city: '敦煌' }
  ];

  var TITLES = {
    dashboard: ['总览 / 数据看板', '实时运营概览'],
    scenarios: ['内容生产 / 剧本管理', '管理景区 AI 剧本游内容'],
    editor: ['内容生产 / 剧情编辑器', '可视化编排 STORY NODE'],
    tasks: ['内容生产 / 任务中心', '观察 / 寻找 / 拍摄 / 解谜任务'],
    materials: ['内容生产 / 内容素材库', '景区语料与向量化进度'],
    visitors: ['运营 / 游客管理', '家庭游客档案与游玩轨迹'],
    iptoys: ['运营 / 潮玩 IP 管理', '阿游角色体系与城市限定款'],
    analytics: ['数据与配置 / 数据分析', '转化、年龄分布与营收结构'],
    observability: ['数据与配置 / 运行指标', '接口性能、慢请求与业务计数'],
    park: ['数据与配置 / 景区与联名', '景区信息、联名合作与分账配置'],
    'ai-wizard': ['AI Story Engine / 生成向导', '景区资料 → 剧本草稿']
  };

  var KIND_LABEL = { entry: 'ENTRY · 入口', main: 'STORY NODE · 主线', branch: 'BRANCH · 支线', reward: 'REWARD · 结算' };
  var KIND_OPTIONS = [['entry', '入口节点'], ['main', '主线剧情'], ['branch', '支线任务'], ['reward', '结算节点']];
  var TRIGGER_LABEL = { gps: 'GPS 地理围栏', qr: '扫码触发', nfc: 'NFC 碰一碰', prev: '前置节点完成' };
  var TRIGGER_OPTIONS = [['gps', 'GPS 地理围栏'], ['qr', '扫码 / NFC 扫码'], ['nfc', 'NFC 碰一碰'], ['prev', '前置节点完成']];
  var VERIFY_LABEL = { auto: '自动（进入即过）', answer: '文本答案', keyword: '关键词匹配', photo: '上传照片' };
  var VERIFY_OPTIONS = [['auto', '自动（进入即过）'], ['answer', '文本答案'], ['keyword', '关键词匹配'], ['photo', '上传照片']];
  var TASK_TYPE_LABEL = { observe: '观察', find: '寻找', photo: '拍摄', solve: '解谜' };
  var TASK_TYPE_EMOJI = { observe: '🔍', find: '🧭', photo: '📷', solve: '🧩' };
  var AGE_LABEL = { '4-8': '4-8 岁 · 亲子探索', '8-12': '8-12 岁 · 少年冒险', '12+': '12 岁+ · 沉浸剧本' };
  var AGE_SHORT = { '4-8': '4-8 岁', '8-12': '8-12 岁', '12+': '12 岁+' };
  var MODE_LABEL = { mainline: '生成主线', task: '生成任务', dialog: '生成对话', reward: '生成奖励', full: '一键生成全剧本' };
  var CATEGORY_FALLBACK = [
    { key: 'history', label: '历史典故', emoji: '📜', count: 0 },
    { key: 'architecture', label: '建筑风貌', emoji: '🏯', count: 0 },
    { key: 'heritage', label: '非遗技艺', emoji: '🎭', count: 0 },
    { key: 'legend', label: '民间传说', emoji: '📖', count: 0 },
    { key: 'nature', label: '自然地理', emoji: '🌿', count: 0 },
    { key: 'geo', label: '景区地理', emoji: '🗺️', count: 0 }
  ];
  var CATEGORY_EMOJI = { history: '📜', architecture: '🏯', heritage: '🎭', legend: '📖', nature: '🌿', geo: '🗺️' };
  /* 城市 → 默认 emoji（景区详情返回 park.emoji 时优先使用详情值） */
  var EDITION_EMOJI = {
    '西安': '🏯', '北京': '🏛️', '杭州': '⛩️', '成都': '🐼', '贵州': '⛰️', '敦煌': '🏜️',
    '苏州': '🌉', '洛阳': '🏺', '南京': '🏰', '重庆': '🌆', '桂林': '🏞️', '青岛': '🌊',
    '长沙': '🍊', '昆明': '🌸', '厦门': '🌴', '拉萨': '🗻', '广州': '🌃', '上海': '🌇'
  };

  var TAG_MAP = {
    scenario: { online: 'tag-green', review: 'tag-orange', draft: 'tag-gray' },
    task: { observe: 'tag-blue', find: 'tag-gold', photo: 'tag-purple', solve: 'tag-orange' },
    visitor: { ongoing: 'tag-green', done: 'tag-blue', high: 'tag-gold', vip: 'tag-gold', 'new': 'tag-gray' },
    material: { indexed: 'tag-green', parsing: 'tag-orange', pending: 'tag-gray', failed: 'tag-red' },
    sku: { onsale: 'tag-green', low: 'tag-orange', unlisted: 'tag-gray', soldout: 'tag-red' },
    coop: { active: 'tag-green', negotiating: 'tag-orange', ended: 'tag-gray' },
    node: { locked: 'tag-gray', active: 'tag-gold', done: 'tag-green' }
  };

  var GEN_STEPS = ['读取景区素材', '构建世界观', '生成主线剧情', '生成任务与判定', '生成奖励体系', '入库为草稿剧本'];

  /* ======================= 2. 全局状态 ======================= */

  var state = {
    route: 'dashboard',
    params: {},
    parkId: 1,
    parkName: '西安 · 大唐不夜城',
    engine: null,
    prevRoute: 'scenarios',
    search: '',
    data: {},           /* 各模块缓存，供导出与联动使用 */
    obsSort: 'count',   /* 运行指标：端点表排序字段 */
    obsSortDir: 'desc', /* 运行指标：排序方向 */
    obsAuto: false,     /* 运行指标：每 5 秒自动刷新开关（默认关闭） */
    obsTimer: null      /* 运行指标：自动刷新定时器 */
  };

  /* ======================= 3. 基础工具 ======================= */

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* 整数千分位（自行实现，不依赖 toLocaleString 的宿主实现差异） */
  function groupNum(n) {
    var neg = n < 0;
    n = Math.abs(n);
    var parts = String(n).split('.');
    var int = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    var frac = parts.length > 1 ? '.' + parts[1] : '';
    return (neg ? '-' : '') + int + frac;
  }

  /* 数字千分位；字符串（如 ¥286,400）原样保留 */
  function nf(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return isFinite(v) ? groupNum(v) : String(v);
    var s = String(v);
    if (/^-?\d+(\.\d+)?$/.test(s)) return groupNum(Number(s));
    return s;
  }

  function clamp(v, min, max) {
    v = Number(v);
    if (isNaN(v)) return min;
    return Math.max(min, Math.min(max, v));
  }

  function num(v, dft) {
    if (v === '' || v === null || v === undefined) return (dft === undefined ? 0 : dft);
    var n = Number(v);
    return isNaN(n) ? (dft === undefined ? 0 : dft) : n;
  }

  function tagOf(group, key, label) {
    var cls = (TAG_MAP[group] || {})[key] || 'tag-gray';
    return '<span class="tag ' + cls + '">' + esc(label || key || '—') + '</span>';
  }

  function progCell(pct, emptyText) {
    if (pct === null || pct === undefined || pct === '') {
      return '<div class="prog-wrap"><div class="prog"><i style="width:0%"></i></div><b class="muted">' + esc(emptyText || '—') + '</b></div>';
    }
    var p = clamp(pct, 0, 100);
    return '<div class="prog-wrap"><div class="prog"><i style="width:' + p + '%"></i></div><b>' + p + '%</b></div>';
  }

  function ageText(band) { return AGE_SHORT[band] || band || '—'; }

  function kindLabel(kind) { return KIND_LABEL[kind] || 'STORY NODE'; }
  function triggerLabel(t) { return TRIGGER_LABEL[t] || t || 'GPS 地理围栏'; }

  /* CSV 导出（纯前端，不联网） */
  function downloadCSV(filename, rows) {
    var csv = rows.map(function (r) {
      return r.map(function (c) {
        var s = (c === null || c === undefined) ? '' : String(c);
        return '"' + s.replace(/"/g, '""') + '"';
      }).join(',');
    }).join('\r\n');
    var blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 800);
  }

  /* ======================= 4. API 封装 ======================= */

  function qs(obj) {
    var parts = [];
    Object.keys(obj || {}).forEach(function (k) {
      var v = obj[k];
      if (v === undefined || v === null || v === '') return;
      parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return parts.length ? ('?' + parts.join('&')) : '';
  }

  function api(path, options) {
    options = options || {};
    var init = { method: options.method || 'GET', headers: { 'Accept': 'application/json' } };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    return fetch(API_BASE + path, init).then(function (res) {
      return res.text().then(function (text) {
        var data = null;
        if (text) {
          try { data = JSON.parse(text); } catch (e) { data = null; }
        }
        if (!res.ok) {
          var msg = (data && (data.error || data.detail || data.message)) || ('请求失败（HTTP ' + res.status + '）');
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        }
        if (data === null) {
          throw new Error('后端返回了非 JSON 内容，请确认接口路径正确');
        }
        if (data && data.ok === false) {
          throw new Error(data.error || '接口返回失败');
        }
        return data;
      });
    }).catch(function (e) {
      if (e && e.status) throw e;
      if (e && e.message && e.message.indexOf('后端返回') === 0) throw e;
      throw new Error('无法连接后端服务，请确认后端已启动（' + API_BASE + '）');
    });
  }

  /* ======================= 5. 加载 / 错误 / Toast / 弹窗 / 抽屉 ======================= */

  function loaderHTML(label, kind) {
    var pulse = '<div class="pulse"><i></i><i></i><i></i></div>';
    if (kind === 'kpi') {
      var kpis = '';
      for (var i = 0; i < 4; i++) kpis += '<div class="sk sk-kpi"></div>';
      return '<div class="grid g4 mb16">' + kpis + '</div>' +
        '<div class="grid" style="grid-template-columns:1.7fr 1fr"><div class="sk sk-card"></div><div class="sk sk-card"></div></div>' +
        '<div class="state-box" style="margin-top:16px">' + pulse + '<p style="margin:0">' + esc(label || '加载中') + '</p></div>';
    }
    var rows = '';
    for (var j = 0; j < 6; j++) rows += '<div class="sk sk-row"></div>';
    return '<div class="card"><div class="card-h"><b>' + esc(label || '加载中') + '</b><span>数据请求中…</span></div>' +
      pulse + rows + '</div>';
  }

  function showLoading(box, label, kind) {
    if (!box) return;
    box.innerHTML = loaderHTML(label, kind);
  }

  function showError(box, err, retry) {
    if (!box) return;
    var msg = (err && err.message) ? err.message : String(err || '未知错误');
    box.innerHTML =
      '<div class="state-box err">' +
        '<span class="sb-ic">⚠️</span>' +
        '<b>数据加载失败</b>' +
        '<p>' + esc(msg) + '<br>请检查后端服务是否已启动，或稍后重试。</p>' +
        '<div class="sb-acts"><button class="btn btn-gold retry-btn" type="button">重试</button>' +
        '<button class="btn clean-btn" type="button">返回数据看板</button></div>' +
      '</div>';
    var rb = $('.retry-btn', box);
    if (rb) rb.addEventListener('click', function () { retry(); });
    var cb = $('.clean-btn', box);
    if (cb) cb.addEventListener('click', function () { location.hash = '#dashboard'; });
  }

  /* 统一加载包装：先骨架 → 成功渲染 / 失败显示重试 */
  function loadInto(box, label, kind, task) {
    showLoading(box, label, kind);
    return task().catch(function (e) {
      showError(box, e, function () { loadInto(box, label, kind, task); });
    });
  }

  function toast(msg, type) {
    var root = $('#toastRoot');
    var el = document.createElement('div');
    el.className = 'toast ' + (type === 'err' ? 'err' : 'ok');
    el.innerHTML = '<span class="ti">' + (type === 'err' ? '⚠️' : '✦') + '</span><span>' + esc(msg) + '</span>';
    root.appendChild(el);
    setTimeout(function () {
      el.style.transition = 'opacity .25s';
      el.style.opacity = '0';
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 260);
    }, type === 'err' ? 4200 : 2800);
  }

  /* 通用弹窗 */
  function openModal(opt) {
    var root = $('#modalRoot');
    var foot = opt.footer === null ? '' :
      '<div class="modal-f">' +
        (opt.footer || ('<button class="btn" data-act="cancel" type="button">取消</button>' +
          '<button class="btn btn-gold" data-act="ok" type="button">' + esc(opt.okText || '确定') + '</button>')) +
      '</div>';
    root.innerHTML =
      '<div class="modal-mask" data-act="cancel"></div>' +
      '<div class="modal' + (opt.wide ? ' wide' : '') + '">' +
        '<div class="modal-h"><b>' + esc(opt.title || '') + '</b><button class="mclose" data-act="cancel" type="button">✕</button></div>' +
        '<div class="modal-b">' + (opt.body || '') + '</div>' + foot +
      '</div>';
    root.classList.add('show');

    function close() {
      root.classList.remove('show');
      root.innerHTML = '';
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);

    $$('[data-act="cancel"]', root).forEach(function (el) { el.addEventListener('click', close); });
    var okBtn = $('[data-act="ok"]', root);
    if (okBtn && opt.onOk) {
      okBtn.addEventListener('click', function () {
        var r = opt.onOk(close, okBtn);
        if (r === false) return;
      });
    }
    if (opt.onMount) opt.onMount(root, close);
    return { close: close, root: root };
  }

  function confirmModal(title, text, okText, onOk) {
    openModal({
      title: title,
      body: '<p style="font-size:12.5px;color:var(--text2);line-height:1.8">' + esc(text) + '</p>',
      okText: okText || '确认',
      onOk: function (close, btn) { btn.disabled = true; onOk(close, btn); }
    });
  }

  /* 右侧抽屉 */
  function openDrawer(html) {
    var d = $('#drawer');
    d.innerHTML = html;
    d.classList.add('show');
    $('#overlay').classList.add('show');
    var c = $('.close', d);
    if (c) c.addEventListener('click', closeDrawer);
  }
  function closeDrawer() {
    $('#drawer').classList.remove('show');
    $('#overlay').classList.remove('show');
  }
  $('#overlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });

  /* ======================= 6. 图表与通用片段 ======================= */

  /* 折线图：polygon 渐变填充 + polyline 双线（游客 / 故事开启） */
  function lineChart(tr) {
    var W = 560, H = 200, PL = 8, PR = 10, PT = 16, PB = 24;
    var days = (tr && tr.days) || [];
    var a = (tr && tr.visitors) || [];
    var b = (tr && tr.story_opens) || [];
    var n = Math.max(days.length, a.length, b.length, 2);
    var maxV = Math.max(1, Math.max.apply(null, a.concat([0])), Math.max.apply(null, b.concat([0]))) * 1.18;

    function x(i) { return PL + (W - PL - PR) * (n > 1 ? i / (n - 1) : 0); }
    function y(v) { return H - PB - (H - PB - PT) * (clamp(v, 0, maxV) / maxV); }
    function pts(arr) {
      return arr.map(function (v, i) { return x(i).toFixed(1) + ',' + y(v).toFixed(1); }).join(' ');
    }
    function area(arr) {
      if (!arr.length) return '';
      return pts(arr) + ' ' + x(arr.length - 1).toFixed(1) + ',' + (H - PB) + ' ' + x(0).toFixed(1) + ',' + (H - PB);
    }

    var grid = '';
    for (var k = 1; k <= 4; k++) {
      var gy = (PT + (H - PB - PT) * k / 4).toFixed(1);
      grid += '<line x1="0" y1="' + gy + '" x2="' + W + '" y2="' + gy + '" stroke="rgba(255,255,255,.06)"/>';
    }
    /* x 轴标签最多显示 6 个 */
    var labelHtml = '';
    var step = Math.max(1, Math.ceil(n / 6));
    for (var i = 0; i < n; i += step) {
      if (!days[i]) continue;
      labelHtml += '<text x="' + x(i).toFixed(1) + '" y="' + (H - 6) + '" text-anchor="middle">' + esc(days[i]) + '</text>';
    }

    function series(arr, color, gradId) {
      if (!arr.length) return '';
      var lastX = x(arr.length - 1).toFixed(1), lastY = y(arr[arr.length - 1]).toFixed(1);
      return '<polygon points="' + area(arr) + '" fill="url(#' + gradId + ')"/>' +
        '<polyline points="' + pts(arr) + '" fill="none" stroke="' + color + '" stroke-width="2.4" stroke-linejoin="round"/>' +
        '<circle cx="' + lastX + '" cy="' + lastY + '" r="4" fill="' + color + '"/>';
    }

    var svg = '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      '<defs>' +
        '<linearGradient id="gA" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E8B45A" stop-opacity=".24"/><stop offset="1" stop-color="#E8B45A" stop-opacity="0"/></linearGradient>' +
        '<linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4FA08C" stop-opacity=".2"/><stop offset="1" stop-color="#4FA08C" stop-opacity="0"/></linearGradient>' +
      '</defs>' + grid + series(a, '#E8B45A', 'gA') + series(b, '#4FA08C', 'gB') + labelHtml + '</svg>';

    return {
      svg: svg,
      peakVisitors: a.length ? Math.max.apply(null, a) : 0,
      peakStory: b.length ? Math.max.apply(null, b) : 0
    };
  }

  function funnelHTML(items) {
    items = items || [];
    if (!items.length) return '<div class="muted" style="font-size:12px">暂无漏斗数据</div>';
    return '<div class="funnel">' + items.map(function (f, i) {
      return '<div class="fn-row">' +
        '<div class="fn-bar fn-' + ((i % 5) + 1) + '" style="width:' + clamp(f.percent, 3, 100) + '%"><span>' + esc(f.label) + '</span></div>' +
        '<div class="fn-meta">' + nf(f.value) + '</div></div>';
    }).join('') + '</div>';
  }

  function barsHTML(items, alt) {
    items = items || [];
    if (!items.length) return '<div class="muted" style="font-size:12px">暂无数据</div>';
    return '<div class="bars' + (alt ? ' alt' : '') + '">' + items.map(function (it) {
      var pct = clamp(it.percent, 0, 100);
      var h = Math.max(6, Math.round(pct / 100 * 118));
      return '<div class="bar"><b>' + pct + '%</b><i style="height:' + h + 'px"></i><span>' + esc(it.label) + '</span></div>';
    }).join('') + '</div>';
  }

  function stepsHTML(steps) {
    steps = steps || [];
    return '<div class="steps">' + steps.map(function (s, i) {
      var cls = s.state === 'done' ? 'done' : (s.state === 'cur' ? 'cur' : '');
      var dot = s.state === 'done' ? '✓' : String(i + 1);
      return '<div class="step ' + cls + '"><div class="dot">' + dot + '</div>' + esc(s.label) + '</div>';
    }).join('') + '</div>';
  }

  function kvHTML(items) {
    return '<div class="kv">' + items.map(function (it) {
      return '<div class="kv-i"><span>' + esc(it.label) + '</span><b>' + (it.html || esc(nf(it.value))) + '</b></div>';
    }).join('') + '</div>';
  }

  function engineBadge(engine) {
    if (!engine) return '<span class="eng-badge eng-off">引擎状态检测中…</span>';
    if (engine.llm_enabled) {
      return '<span class="eng-badge eng-on">● ' + esc(engine.engine || 'LLM') + (engine.llm_model ? ' · ' + esc(engine.llm_model) : '') + '</span>';
    }
    return '<span class="eng-badge eng-off">○ 离线规则引擎 · ' + esc(engine.engine || 'offline-rule-engine') + '</span>';
  }

  function loadEngine() {
    if (state.engine) return Promise.resolve(state.engine);
    return api('/ai/engine').then(function (d) { state.engine = d; return d; })
      .catch(function () { return null; });
  }

  /* ======================= 7. 数据看板 ======================= */

  var dashRange = '7d';

  function rangeLabel() {
    return dashRange === 'today' ? '今日实时' : (dashRange === '7d' ? '近 7 天' : '近 30 天');
  }

  /* 按分段控件裁剪趋势窗口（客户端区间切换，接口无区间参数） */
  function sliceTrend(tr) {
    tr = tr || {};
    var days = tr.days || [], a = tr.visitors || [], b = tr.story_opens || [];
    var keep = dashRange === 'today' ? 2 : (dashRange === '7d' ? 7 : days.length);
    function tail(arr) { return arr.slice(Math.max(0, arr.length - keep)); }
    return { days: tail(days), visitors: tail(a), story_opens: tail(b) };
  }

  function renderDashboard() {
    var box = $('#dashBody');
    loadInto(box, '正在同步运营数据', 'kpi', function () {
      return api('/dashboard').then(function (d) {
        state.data.dashboard = d;
        $('#dashSub').textContent = (d.date_label || '实时运营概览') + ' · ' + rangeLabel() + ' · 全部数据实时同步';

        var kpis = (d.kpis || []).slice(0, 4).map(function (k, i) {
          var dir = k.delta_dir === 'down' ? 'down' : 'up';
          var arrow = dir === 'down' ? '▼' : '▲';
          var delta = (k.delta || k.delta_value) ? (arrow + ' ' + esc(k.delta || k.delta_value) + '% ' + esc(k.delta_label || '')) : esc(k.delta_label || '与上期持平');
          return '<div class="kpi k' + (i + 1) + '">' +
            '<div class="k-label">' + esc(k.label) + '</div>' +
            '<div class="k-val">' + esc(k.value) + (k.unit ? '<small>' + esc(k.unit) + '</small>' : '') + '</div>' +
            '<div class="k-delta ' + dir + '">' + delta + '</div></div>';
        }).join('');

        var tr = sliceTrend(d.trend);
        var chart = lineChart(tr);

        var hot = (d.hot_nodes || []).map(function (h) {
          var r = num(h.rank, 99);
          var cls = r === 1 ? 'rank-1' : (r === 2 ? 'rank-2' : (r === 3 ? 'rank-3' : 'rank-n'));
          return '<div class="lrow"><div class="rn ' + cls + '">' + r + '</div>' +
            '<div class="lt"><b>' + esc(h.name) + '</b><span>' + esc(h.kind_label || '') + '</span></div>' +
            '<div class="lv">' + nf(h.value) + '</div></div>';
        }).join('') || '<div class="muted" style="font-size:12px">暂无节点热度数据</div>';

        var tls = (d.timeline || []).map(function (t) {
          return '<div class="tl-item"><b>' + esc(t.title) + '</b><span>' + esc(t.detail || '') + '</span>' +
            '<div class="tm">' + esc(t.ago || '') + '</div></div>';
        }).join('') || '<div class="muted" style="font-size:12px">暂无实时动态</div>';

        box.innerHTML =
          '<div class="grid g4 mb16">' + (kpis || '<div class="muted">暂无 KPI 数据</div>') + '</div>' +

          '<div class="grid" style="grid-template-columns:1.7fr 1fr;margin-bottom:16px">' +
            '<div class="card"><div class="card-h"><b>游客与故事开启趋势</b><span>' + esc(rangeLabel()) + ' · ' + (tr.days.length || 0) + ' 天窗口</span></div>' +
              chart.svg +
              '<div class="legend">' +
                '<span><i style="background:#E8B45A"></i>入园游客 · 峰值 ' + nf(chart.peakVisitors) + '</span>' +
                '<span><i style="background:#4FA08C"></i>故事开启 · 峰值 ' + nf(chart.peakStory) + '</span>' +
              '</div></div>' +
            '<div class="card"><div class="card-h"><b>剧本完成漏斗</b><span>' + esc(d.date_label || '全景区汇总') + '</span></div>' +
              funnelHTML(d.funnel) + '</div>' +
          '</div>' +

          '<div class="grid g2">' +
            '<div class="card"><div class="card-h"><b>剧情节点热度榜</b><span class="link" data-goto="editor">进入编辑器 ›</span></div>' + hot + '</div>' +
            '<div class="card"><div class="card-h"><b>实时动态</b><span>' + esc(rangeLabel()) + '</span></div><div class="tl">' + tls + '</div></div>' +
          '</div>';

        var go = $('[data-goto="editor"]', box);
        if (go) go.addEventListener('click', function () { location.hash = '#editor'; });
        bindSeg('#dashRange', dashRange, function (v) { dashRange = v; renderDashboard(); });
      });
    });
  }

  /* 分段控件通用绑定 */
  function bindSeg(sel, current, onPick) {
    var seg = $(sel);
    if (!seg) return;
    $$('.s', seg).forEach(function (s) {
      s.classList.toggle('active', s.dataset.range === current || s.dataset.key === current || s.dataset.status === current);
      s.onclick = function () {
        $$('.s', seg).forEach(function (x) { x.classList.remove('active'); });
        s.classList.add('active');
        onPick(s.dataset.range || s.dataset.key || s.dataset.status || s.dataset.type);
      };
    });
  }

  /* ======================= 8. 剧本管理 ======================= */

  var scFilter = 'all';

  function renderScenarios() {
    var box = $('#scBody');
    var q = scFilter === 'all' ? '' : qs({ status: scFilter });

    loadInto(box, '正在加载剧本列表', 'table', function () {
      return api('/scenarios' + q).then(function (d) {
        state.data.scenarios = d;
        var sum = d.summary || {};
        var items = (d.items || []).filter(function (it) {
          return scFilter === 'all' || it.status === scFilter;   /* 客户端二次过滤兜底 */
        });

        $('#scSub').textContent = '当前景区共 ' + nf(sum.total || items.length) + ' 个剧本 · 已上线 ' + nf(sum.online || 0) + ' 个';
        updateSideFoot(sum.total);

        var rows = items.map(function (it) {
          return '<tr data-id="' + it.id + '">' +
            '<td class="cell-strong">' + esc(it.title) + '</td>' +
            '<td class="muted">' + esc(it.park_name || '—') + '</td>' +
            '<td class="num muted">' + nf(it.chapters_count) + ' 章 / ' + nf(it.nodes_count) + ' 节点</td>' +
            '<td>' + tagOf('scenario', it.status, it.status_label) + '</td>' +
            '<td>' + progCell(it.completion_rate) + '</td>' +
            '<td class="muted num">' + esc(it.updated_at || '—') + '</td>' +
            '<td><span class="tag tag-line">编辑</span></td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="7" class="muted" style="text-align:center;padding:26px">该状态下暂无剧本</td></tr>';

        box.innerHTML =
          kvHTML([
            { label: '剧本总数', value: sum.total },
            { label: '已上线', value: sum.online },
            { label: '审核中', value: sum.review },
            { label: '草稿', value: sum.draft }
          ]).replace('<div class="kv">', '<div class="kv" style="margin-bottom:16px">') +

          '<div class="card"><div class="card-h"><b>剧本列表</b>' +
            '<div class="seg" id="scStatus">' +
              segItem('all', '全部') + segItem('online', '已上线') + segItem('review', '审核中') + segItem('draft', '草稿') +
            '</div></div><div class="tbl-wrap"><table class="tbl">' +
            '<thead><tr><th>剧本名称</th><th>所属景区</th><th>章节 / 节点</th><th>状态</th><th>完成率</th><th>更新时间</th><th>操作</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div></div>';

        bindSeg('#scStatus', scFilter, function (v) { scFilter = v; renderScenarios(); });
        bindTableRows(box, function (id) { location.hash = '#editor?id=' + id; });
        applySearch();
      });
    });
  }

  function segItem(key, label) {
    return '<div class="s" data-key="' + key + '">' + label + '</div>';
  }

  function bindTableRows(box, onPick) {
    $$('tbody tr[data-id]', box).forEach(function (tr) {
      tr.addEventListener('click', function () { onPick(tr.dataset.id, tr); });
    });
  }

  /* 新建剧本 */
  function openNewScenarioModal() {
    var body =
      '<div class="fld2"><label>剧本名称</label><input id="nsTitle" placeholder="例如：大唐密令 · 续章"></div>' +
      '<div class="fld2"><label>所属景区</label><select id="nsPark">' +
        PARKS.map(function (p) { return '<option value="' + p.id + '"' + (p.id === state.parkId ? ' selected' : '') + '>' + esc(p.name) + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>适合年龄层</label><select id="nsAge">' +
        Object.keys(AGE_LABEL).map(function (k) { return '<option value="' + k + '"' + (k === '8-12' ? ' selected' : '') + '>' + AGE_LABEL[k] + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="hint-box">创建后将生成草稿剧本，可进入剧情编辑器继续编排 STORY NODE。</div>';

    openModal({
      title: '新建剧本', body: body, okText: '创建剧本',
      onOk: function (close, btn) {
        var title = ($('#nsTitle').value || '').trim();
        if (!title) { toast('请填写剧本名称', 'err'); return false; }
        btn.disabled = true;
        api('/scenarios', {
          method: 'POST',
          body: { title: title, park_id: num($('#nsPark').value, 1), age_band: $('#nsAge').value }
        }).then(function (sc) {
          close();
          toast('剧本《' + title + '》创建成功，草稿已生成');
          renderScenarios();
        }).catch(function (e) {
          btn.disabled = false;
          toast('创建失败：' + e.message, 'err');
        });
        return false;
      }
    });
  }

  /* ======================= 9. 剧情编辑器 ======================= */

  var ed = { scenario: null, nodes: [], links: [], sel: null, chapters: [], aiMode: 'mainline', materials: null };

  function renderEditor(params) {
    var box = $('#edBody');
    var id = params && params.id ? num(params.id, 1) : null;

    loadInto(box, '正在加载剧本画布', 'kpi', function () {
      var tasks = [api('/scenarios/' + (id || 1))];
      if (id === null) tasks[0] = api('/scenarios').then(function (list) {
        var first = (list.items || [])[0];
        if (!first) throw new Error('暂无剧本，请先新建剧本');
        return api('/scenarios/' + first.id);
      });
      tasks.push(api('/scenarios').catch(function () { return null; }));
      tasks.push(api('/materials').catch(function () { return null; }));
      tasks.push(loadEngine());

      return Promise.all(tasks).then(function (res) {
        var sc = res[0], list = res[1], mats = res[2];
        ed.scenario = sc;
        ed.nodes = (sc.nodes || []).map(function (n) {
          return {
            id: n.id, chapter_id: n.chapter_id, name: n.name, kind: n.kind,
            type_label: n.type_label || kindLabel(n.kind), desc: n.desc, trigger_type: n.trigger_type,
            lat: n.lat, lng: n.lng, radius_m: n.radius_m, age_band: n.age_band,
            story_text: n.story_text, status: n.status, task_count: n.task_count,
            x: num(n.x, 40), y: num(n.y, 120)
          };
        });
        ed.links = (sc.links || []).map(function (l) { return { from: num(l.from), to: num(l.to), color: l.color || 'gold' }; });
        ed.chapters = sc.chapters || [];
        ed.materials = mats;
        ed.sel = ed.nodes.length ? (findActiveNode() || ed.nodes[0]).id : null;

        $('#edTitle').textContent = '剧情编辑器 · ' + (sc.title || '未命名剧本');
        $('#edSub').textContent = [sc.park_name || sc.city, sc.status_label, (sc.chapters || []).length + ' 章 / ' + ed.nodes.length + ' 个 STORY NODE'].filter(Boolean).join(' · ');

        /* 剧本切换下拉 */
        var pick = $('#edPick');
        if (list && list.items) {
          pick.style.display = '';
          pick.innerHTML = list.items.map(function (it) {
            return '<option value="' + it.id + '"' + (it.id === sc.id ? ' selected' : '') + '>' + esc(it.title) + '</option>';
          }).join('');
          pick.onchange = function () { location.hash = '#editor?id=' + pick.value; };
        } else {
          pick.style.display = 'none';
        }

        paintEditor();
      });
    });
  }

  function findActiveNode() {
    for (var i = 0; i < ed.nodes.length; i++) if (ed.nodes[i].status === 'active') return ed.nodes[i];
    return null;
  }

  function currentNode() {
    for (var i = 0; i < ed.nodes.length; i++) if (ed.nodes[i].id === ed.sel) return ed.nodes[i];
    return null;
  }

  function canvasSize() {
    var maxX = 0, maxY = 0;
    ed.nodes.forEach(function (n) { maxX = Math.max(maxX, n.x + 158 + 70); maxY = Math.max(maxY, n.y + 120 + 70); });
    return { w: Math.max(880, maxX), h: Math.max(500, maxY) };
  }

  var WIRE_COLOR = { gold: '#E8B45A', purple: '#BBA5F5', forest: '#4FA08C' };
  var NODE_W = 158, NODE_H = 76;

  function wiresSVG() {
    var size = canvasSize();
    var map = {};
    ed.nodes.forEach(function (n) { map[n.id] = n; });

    var defs = Object.keys(WIRE_COLOR).map(function (c) {
      return '<marker id="arw-' + c + '" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">' +
        '<path d="M0,0 L6,3 L0,6 z" fill="' + WIRE_COLOR[c] + '"/></marker>';
    }).join('');

    var body = '';
    ed.links.forEach(function (l) {
      var a = map[l.from], b = map[l.to];
      if (!a || !b) return;
      var key = WIRE_COLOR[l.color] ? l.color : (l.color === 'green' ? 'forest' : 'gold');
      var dx = b.x - a.x, dy = b.y - a.y, d;

      if (Math.abs(dy) < 28) {
        /* 同行：右出 → 左进 直线 */
        d = 'M' + (a.x + NODE_W) + ',' + (a.y + NODE_H / 2) + ' L' + (b.x - 7) + ',' + (b.y + NODE_H / 2);
      } else if (Math.abs(dx) < 50) {
        /* 垂直：下出 → 上进 曲线 */
        var up = b.y < a.y;
        var x1 = a.x + NODE_W / 2, x2 = b.x + NODE_W / 2;
        var y1 = up ? a.y : a.y + NODE_H;
        var y2 = up ? b.y + NODE_H + 7 : b.y - 7;
        var c1 = (up ? -1 : 1) * Math.max(34, Math.abs(y2 - y1) * 0.5);
        d = 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + (y1 + c1) + ' ' + x2 + ',' + (y2 - c1) + ' ' + x2 + ',' + y2;
      } else {
        /* 斜向：下出 → 上进 曲线 */
        var sx = a.x + NODE_W / 2, sy = a.y + NODE_H;
        var tx = b.x + NODE_W / 2, ty = (b.y > a.y ? b.y : b.y + NODE_H) + (b.y > a.y ? -7 : 7);
        var c = Math.max(30, Math.abs(ty - sy) * 0.45);
        d = 'M' + sx + ',' + sy + ' C' + sx + ',' + (sy + c) + ' ' + tx + ',' + (ty - c) + ' ' + tx + ',' + ty;
      }
      body += '<path d="' + d + '" stroke="' + WIRE_COLOR[key] + '" stroke-width="2" fill="none" marker-end="url(#arw-' + key + ')"/>';
    });

    return '<svg class="wires" id="edWires" width="' + size.w + '" height="' + size.h + '" viewBox="0 0 ' + size.w + ' ' + size.h + '">' +
      '<defs>' + defs + '</defs>' + body + '</svg>';
  }

  function nodeSub(n) {
    if (n.desc) return n.desc;
    return triggerLabel(n.trigger_type) + ' · ' + ageText(n.age_band);
  }

  function nodeHTML(n) {
    var cls = ['sc-node'];
    if (n.id === ed.sel) cls.push('active');
    if (n.kind === 'branch') cls.push('branch');
    if (n.kind === 'reward') cls.push('kind-reward');
    var st = '';
    if (n.status === 'active') st = '<span class="sn-status st-on"></span>';
    else if (n.status === 'done') st = '<span class="sn-status st-draft"></span>';
    return '<div class="' + cls.join(' ') + '" data-node="' + n.id + '" style="left:' + n.x + 'px;top:' + n.y + 'px">' + st +
      '<div class="sn-tag">' + esc(n.type_label || kindLabel(n.kind)) + '</div>' +
      '<b>' + esc(n.name) + '</b><span>' + esc(nodeSub(n)) + '</span></div>';
  }

  function selectOptions(options, current) {
    return options.map(function (o) {
      return '<option value="' + esc(o[0]) + '"' + (o[0] === current ? ' selected' : '') + '>' + esc(o[1]) + '</option>';
    }).join('');
  }

  function paintEditor() {
    var box = $('#edBody');
    var size = canvasSize();
    var n = currentNode();

    var nodesHtml = ed.nodes.map(nodeHTML).join('') ||
      '<div class="muted" style="padding:20px;font-size:12px">该剧本暂无节点，点击右侧「新建节点」开始编排。</div>';

    var attrPanel = n ? (
      '<div class="fld2"><label>节点名称</label><input id="pnName" value="' + esc(n.name) + '"></div>' +
      '<div class="fld2"><label>节点类型</label><select id="pnKind">' + selectOptions(KIND_OPTIONS, n.kind) + '</select></div>' +
      '<div class="fld2"><label>触发方式</label><select id="pnTrigger">' + selectOptions(TRIGGER_OPTIONS, n.trigger_type) + '</select></div>' +
      '<div class="fld2"><label>剧情文案</label><textarea id="pnStory" rows="4">' + esc(n.story_text || '') + '</textarea></div>' +
      '<div class="fld2"><label>适合年龄层</label><select id="pnAge">' +
        Object.keys(AGE_LABEL).map(function (k) { return '<option value="' + k + '"' + (k === n.age_band ? ' selected' : '') + '>' + AGE_LABEL[k] + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>地理围栏坐标与半径</label><div class="row3">' +
        '<input id="pnLng" value="' + esc(n.lng === undefined || n.lng === null ? '' : n.lng) + '" placeholder="经度">' +
        '<input id="pnLat" value="' + esc(n.lat === undefined || n.lat === null ? '' : n.lat) + '" placeholder="纬度">' +
        '<input id="pnRadius" value="' + esc(n.radius_m === undefined || n.radius_m === null ? '' : n.radius_m) + '" placeholder="半径 m">' +
      '</div></div>' +
      '<div class="fld2"><label>画布坐标</label><div class="row2">' +
        '<input id="pnX" value="' + n.x + '" placeholder="x"><input id="pnY" value="' + n.y + '" placeholder="y">' +
      '</div></div>' +
      '<div class="fld" style="margin-bottom:12px"><span>当前状态</span><b>' + tagOf('node', n.status, ({ locked: '未解锁', active: '当前节点', done: '已完成' })[n.status] || n.status) + '</b></div>' +
      '<div class="draw-actions"><button class="btn btn-gold" id="btnSaveNode" style="flex:1" type="button">保存节点</button>' +
      '<button class="btn" id="btnDelNode" type="button">删除</button></div>' +
      '<button class="btn" id="btnNewNode" style="width:100%;margin-top:10px;justify-content:center" type="button">+ 新建节点</button>'
    ) : '<div class="hint-box">画布中尚未选中节点。点击任一节点可编辑其属性，或点击下方按钮新建节点。</div>' +
        '<button class="btn btn-gold" id="btnNewNode" style="width:100%;margin-top:12px;justify-content:center" type="button">+ 新建节点</button>';

    var matOptions = (ed.materials && ed.materials.categories ? ed.materials.categories : CATEGORY_FALLBACK).map(function (c) {
      return '<option value="' + esc(c.key) + '">' + esc((c.emoji || CATEGORY_EMOJI[c.key] || '📄') + ' ' + c.label + '（' + nf(c.count) + ' 条）') + '</option>';
    }).join('');

    var aiPanel =
      '<div class="ai-box"><b>✦ AI Story Engine</b><p>基于景区资料自动生成世界观、主线、剧情节点、对话与奖励体系。</p>' +
        '<div style="margin-top:9px">' + engineBadge(state.engine) + '</div>' +
      '</div>' +
      (state.engine && !state.engine.llm_enabled ?
        '<div class="hint-box" style="margin-bottom:14px">' + esc(state.engine.setup_hint || '当前使用离线规则引擎，设置环境变量即可切换真实大模型。') + '</div>' : '') +
      '<div class="fld2"><label>关联景区资料</label><select id="aiMatSel">' + matOptions + '</select></div>' +
      '<div class="fld2"><label>适合年龄层</label><select id="aiAge">' +
        Object.keys(AGE_LABEL).map(function (k) { return '<option value="' + k + '"' + (k === (n && n.age_band) ? ' selected' : '') + '>' + AGE_LABEL[k] + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>剧情风格</label><textarea id="aiStyle" rows="3">悬疑解谜，融入本地历史知识，鼓励孩子观察真实建筑。</textarea></div>' +
      '<button class="btn btn-gold" id="btnAiGen" style="width:100%;justify-content:center" type="button">' +
        '<svg viewBox="0 0 24 24"><path d="M12 3l2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4z"/></svg>一键生成剧情节点</button>' +
      '<div class="ai-chips" id="aiChips">' +
        ['mainline', 'task', 'dialog', 'reward'].map(function (k) {
          return '<span class="ai-chip' + (k === ed.aiMode ? ' on' : '') + '" data-mode="' + k + '">' + MODE_LABEL[k] + '</span>';
        }).join('') +
      '</div>' +
      '<div class="draw-actions" style="margin-top:12px"><button class="btn" id="btnAiWizard2" style="flex:1;justify-content:center" type="button">打开完整生成向导</button></div>' +
      '<div id="aiResult" style="margin-top:14px"></div>';

    box.innerHTML =
      '<div class="editor-grid">' +
        '<div class="canvas-wrap"><div class="canvas" id="edCanvas" style="width:' + size.w + 'px;height:' + size.h + 'px">' +
          wiresSVG() + nodesHtml +
          '<div class="canvas-tip">提示：拖动节点调整位置 · 点击节点编辑属性 · 连线按 links 自动绘制</div>' +
        '</div></div>' +
        '<div class="panel">' +
          '<div class="panel-tabs">' +
            '<div class="panel-tab active" data-pnl="attr">节点属性</div>' +
            '<div class="panel-tab" data-pnl="ai">AI 生成</div>' +
          '</div>' +
          '<div class="panel-body">' +
            '<div class="pnl active" id="pnl-attr">' + attrPanel + '</div>' +
            '<div class="pnl" id="pnl-ai">' + aiPanel + '</div>' +
          '</div>' +
        '</div>' +
      '</div>';

    /* 面板 Tab */
    $$('.panel-tab', box).forEach(function (t) {
      t.addEventListener('click', function () {
        $$('.panel-tab', box).forEach(function (x) { x.classList.remove('active'); });
        t.classList.add('active');
        $$('.pnl', box).forEach(function (p) { p.classList.remove('active'); });
        var el = $('#pnl-' + t.dataset.pnl, box);
        if (el) el.classList.add('active');
      });
    });

    bindCanvasDrag();

    var saveBtn = $('#btnSaveNode', box);
    if (saveBtn) saveBtn.addEventListener('click', saveNode);
    var delBtn = $('#btnDelNode', box);
    if (delBtn) delBtn.addEventListener('click', delNode);
    var newBtn = $('#btnNewNode', box);
    if (newBtn) newBtn.addEventListener('click', createNode);
    var genBtn = $('#btnAiGen', box);
    if (genBtn) genBtn.addEventListener('click', function () { runEditorAI(ed.aiMode); });
    var wiz2 = $('#btnAiWizard2', box);
    if (wiz2) wiz2.addEventListener('click', openWizard);
    $$('#aiChips .ai-chip', box).forEach(function (c) {
      c.addEventListener('click', function () {
        ed.aiMode = c.dataset.mode;
        $$('#aiChips .ai-chip', box).forEach(function (x) { x.classList.toggle('on', x === c); });
        runEditorAI(ed.aiMode);
      });
    });
  }

  /* 节点拖拽 */
  function bindCanvasDrag() {
    var canvas = $('#edCanvas');
    if (!canvas) return;
    $$('.sc-node', canvas).forEach(function (el) {
      el.addEventListener('pointerdown', function (e) {
        e.preventDefault();
        var id = num(el.dataset.node);
        var node = null;
        for (var i = 0; i < ed.nodes.length; i++) if (ed.nodes[i].id === id) node = ed.nodes[i];
        if (!node) return;

        var startX = e.clientX, startY = e.clientY, ox = node.x, oy = node.y, moved = false;

        function onMove(ev) {
          var dx = ev.clientX - startX, dy = ev.clientY - startY;
          if (!moved && Math.sqrt(dx * dx + dy * dy) > 3) {
            moved = true;
            el.classList.add('dragging');
            if (el.setPointerCapture) { try { el.setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ } }
          }
          if (!moved) return;
          node.x = Math.max(0, Math.round(ox + dx));
          node.y = Math.max(0, Math.round(oy + dy));
          el.style.left = node.x + 'px';
          el.style.top = node.y + 'px';
          redrawWires();
        }
        function onUp() {
          document.removeEventListener('pointermove', onMove);
          document.removeEventListener('pointerup', onUp);
          el.classList.remove('dragging');
          if (moved) {
            /* 同步属性面板中的坐标输入框，避免再次保存时用旧坐标覆盖 */
            if (ed.sel === node.id) {
              var px = $('#pnX'), py = $('#pnY');
              if (px) px.value = node.x;
              if (py) py.value = node.y;
            }
            toast('节点「' + node.name + '」坐标已更新，保存节点后同步到后台');
          } else {
            ed.sel = id;
            paintEditor();
          }
        }
        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp);
      });
    });
  }

  function redrawWires() {
    var old = $('#edWires');
    if (!old || !old.parentNode) return;
    var size = canvasSize();
    var holder = document.createElement('div');
    holder.innerHTML = wiresSVG();
    old.parentNode.replaceChild(holder.firstChild, old);
    var canvas = $('#edCanvas');
    if (canvas) { canvas.style.width = size.w + 'px'; canvas.style.height = size.h + 'px'; }
  }

  function saveNode() {
    var n = currentNode();
    if (!n) { toast('请先选中一个节点', 'err'); return; }
    var body = {
      name: ($('#pnName').value || '').trim(),
      kind: $('#pnKind').value,
      trigger_type: $('#pnTrigger').value,
      story_text: $('#pnStory').value,
      age_band: $('#pnAge').value,
      x: num($('#pnX').value, n.x),
      y: num($('#pnY').value, n.y),
      lng: num($('#pnLng').value, n.lng),
      lat: num($('#pnLat').value, n.lat),
      radius_m: num($('#pnRadius').value, n.radius_m)
    };
    if (!body.name) { toast('节点名称不能为空', 'err'); return; }
    api('/nodes/' + n.id, { method: 'PUT', body: body }).then(function (updated) {
      Object.keys(updated || {}).forEach(function (k) { if (updated[k] !== undefined && updated[k] !== null) n[k] = updated[k]; });
      n.name = body.name; n.kind = body.kind; n.trigger_type = body.trigger_type;
      n.story_text = body.story_text; n.age_band = body.age_band;
      n.x = body.x; n.y = body.y; n.lng = body.lng; n.lat = body.lat; n.radius_m = body.radius_m;
      n.type_label = kindLabel(n.kind);
      n.desc = triggerLabel(n.trigger_type) + ' · ' + ageText(n.age_band);
      toast('节点已保存并同步到后台');
      paintEditor();
    }).catch(function (e) { toast('保存节点失败：' + e.message, 'err'); });
  }

  function delNode() {
    var n = currentNode();
    if (!n) { toast('请先选中一个节点', 'err'); return; }
    confirmModal('删除节点', '确认删除节点「' + n.name + '」？该节点关联的连线也会一并移除。', '删除', function (close) {
      api('/nodes/' + n.id, { method: 'DELETE' }).then(function () {
        close();
        ed.nodes = ed.nodes.filter(function (x) { return x.id !== n.id; });
        ed.links = ed.links.filter(function (l) { return l.from !== n.id && l.to !== n.id; });
        ed.sel = ed.nodes.length ? ed.nodes[0].id : null;
        toast('节点已删除');
        paintEditor();
      }).catch(function (e) { close(); toast('删除失败：' + e.message, 'err'); });
    });
  }

  function createNode() {
    var chapterId = ed.chapters.length ? ed.chapters[0].id : 1;
    var maxX = 40, maxY = 170;
    ed.nodes.forEach(function (n) { maxX = Math.max(maxX, n.x); if (n.y > maxY) maxY = n.y; });
    var body = {
      scenario_id: ed.scenario ? ed.scenario.id : 1,
      chapter_id: chapterId,
      name: '新剧情节点',
      kind: 'main',
      trigger_type: 'gps',
      story_text: '阿游说：这里好像藏着一段新的故事……',
      age_band: '8-12',
      x: Math.min(maxX + 190, 1180),
      y: Math.max(120, maxY - 40)
    };
    api('/nodes', { method: 'POST', body: body }).then(function (created) {
      var node = created || {};
      ed.nodes.push({
        id: num(node.id, Date.now() % 100000), chapter_id: num(node.chapter_id, chapterId),
        name: node.name || body.name, kind: node.kind || body.kind,
        type_label: node.type_label || kindLabel(body.kind), desc: node.desc,
        trigger_type: node.trigger_type || body.trigger_type, lat: node.lat, lng: node.lng,
        radius_m: node.radius_m, age_band: node.age_band || body.age_band,
        story_text: node.story_text || body.story_text, status: node.status || 'locked',
        task_count: node.task_count || 0,
        x: num(node.x, body.x), y: num(node.y, body.y)
      });
      ed.sel = ed.nodes[ed.nodes.length - 1].id;
      toast('新节点已创建，可继续编辑属性');
      paintEditor();
    }).catch(function (e) { toast('新建节点失败：' + e.message, 'err'); });
  }

  /* 编辑器内 AI 生成（单模式） */
  function runEditorAI(mode) {
    var out = $('#aiResult');
    if (out) out.innerHTML = '<div class="state-box" style="padding:18px"><div class="pulse"><i></i><i></i><i></i></div>' +
      '<p style="margin:0">AI Story Engine 正在以「' + esc(MODE_LABEL[mode] || mode) + '」模式生成…</p></div>';
    api('/ai/generate', {
      method: 'POST',
      body: {
        park_id: state.parkId,
        mode: mode,
        age_band: ($('#aiAge') && $('#aiAge').value) || '8-12',
        style: ($('#aiStyle') && $('#aiStyle').value) || '',
        scenario_title: (ed.scenario && ed.scenario.title) || 'AI 生成剧本',
        chapter_count: Math.max(1, ed.chapters.length || 3),
        node_count: 6
      }
    }).then(function (d) {
      if (!out) return;
      out.innerHTML = renderGenCompact(d);
      toast('AI 生成完成 · 引擎 ' + (d.engine || '—') + ' · ' + (d.elapsed_ms || 0) + 'ms');
      var openBtn = $('#aiOpenDraft');
      if (openBtn) openBtn.addEventListener('click', function () { location.hash = '#editor?id=' + d.created_scenario_id; });
    }).catch(function (e) {
      if (out) out.innerHTML = '<div class="state-box err" style="padding:18px"><b>生成失败</b><p style="margin:6px 0 0">' + esc(e.message) + '</p></div>';
      toast('AI 生成失败：' + e.message, 'err');
    });
  }

  /* 生成结果（紧凑版，用于编辑器侧栏） */
  function renderGenCompact(d) {
    var h = '<div class="res-box" style="margin-bottom:10px"><h5>生成结果</h5>' +
      '<div class="fld"><span>引擎</span><b>' + esc(d.engine || '—') + '</b></div>' +
      '<div class="fld"><span>耗时</span><b>' + nf(d.elapsed_ms) + ' ms</b></div>' +
      '<div class="fld"><span>状态</span><b>' + esc(d.status || 'done') + '</b></div>' +
      (d.created_scenario_id ? '<div class="fld"><span>入库剧本</span><b>#' + esc(d.created_scenario_id) + '</b></div>' : '') +
      '</div>';

    if (d.worldview) h += '<div class="res-box" style="margin-bottom:10px"><h5>世界观</h5><p>' + esc(d.worldview) + '</p></div>';
    if (d.chapters && d.chapters.length) {
      h += '<div class="res-box" style="margin-bottom:10px"><h5>章节（' + d.chapters.length + '）</h5>' + chapterListHTML(d.chapters) + '</div>';
    }
    if (d.nodes && d.nodes.length) {
      h += '<div class="res-box" style="margin-bottom:10px"><h5>剧情节点（' + d.nodes.length + '）</h5>' + nodesFlowHTML(d.nodes) + '</div>';
    }
    if (d.rewards && d.rewards.length) {
      h += '<div class="res-box" style="margin-bottom:10px"><h5>奖励体系</h5>' + rewardsHTML(d.rewards) + '</div>';
    }
    if (d.sources && d.sources.length) {
      h += '<div class="res-box" style="margin-bottom:10px"><h5>引用素材来源</h5>' + sourcesHTML(d.sources) + '</div>';
    }
    if (d.notes) h += '<div class="hint-box">' + esc(d.notes) + '</div>';
    if (d.created_scenario_id) h += '<button class="btn btn-gold" id="aiOpenDraft" style="width:100%;margin-top:10px;justify-content:center" type="button">打开草稿剧本 #' + esc(d.created_scenario_id) + '</button>';
    return h;
  }

  function chapterListHTML(chapters) {
    return '<div class="chap-list">' + chapters.map(function (c, i) {
      return '<div class="chap-i"><div class="ci-n">' + esc(c.idx || (i + 1)) + '</div><div><b>' + esc(c.title) + '</b><span>' + esc(c.summary || '') + '</span></div></div>';
    }).join('') + '</div>';
  }

  function nodesFlowHTML(nodes) {
    return '<div class="node-flow">' + nodes.map(function (n) {
      var t = n.task;
      return '<div class="node-card">' +
        '<div class="nc-h"><b>' + esc(n.name) + '</b>' +
          '<span class="tag tag-gold">' + esc(kindLabel(n.kind).split(' · ')[0]) + '</span>' +
          '<span class="tag tag-line">' + esc(triggerLabel(n.trigger_type)) + '</span></div>' +
        (n.story_text ? '<div class="nc-p">' + esc(n.story_text) + '</div>' : '') +
        (n.ai_dialog ? '<div class="nc-d">💬 ' + esc(n.ai_dialog) + '</div>' : '') +
        (t ? '<div class="nc-t">🎯 <b style="color:#6FD3B8">' + esc(t.title || '') + '</b>' +
          '<div class="kvline"><span class="tag tag-blue">' + esc(TASK_TYPE_LABEL[t.type] || t.type || '') + '</span>' +
          '<span class="tag tag-gray">' + esc(VERIFY_LABEL[t.verify_mode] || t.verify_mode || '') + '</span></div>' +
          (t.answer ? '<div style="margin-top:5px">答案：' + esc(t.answer) + '</div>' : '') +
          (t.hint ? '<div>提示：' + esc(t.hint) + '</div>' : '') + '</div>' : '') +
      '</div>';
    }).join('') + '</div>';
  }

  function rewardsHTML(rewards) {
    return '<div class="badge-grid">' + rewards.map(function (r) {
      return '<div class="bg-item"><span class="bi-e">' + esc(r.emoji || '🏅') + '</span><b>' + esc(r.name) + '</b>' +
        (r.desc ? '<div style="font-size:10px;color:var(--text3);margin-top:4px;line-height:1.5">' + esc(r.desc) + '</div>' : '') + '</div>';
    }).join('') + '</div>';
  }

  function sourcesHTML(sources) {
    return '<div class="src-list">' + sources.map(function (s) {
      return '<div class="src-i">📄 <span>' + esc(s.title) + '</span>' +
        '<span class="si-n">' + esc((CATEGORY_EMOJI[s.category] || '') + ' ' + (s.category || '')) + ' · #' + esc(s.material_id) + '</span></div>';
    }).join('') + '</div>';
  }

  /* 编辑器顶部：预览 / 保存并发布 */
  function previewScenario() {
    if (!ed.scenario) { toast('剧本数据尚未加载完成', 'err'); return; }
    var body =
      '<div class="fld"><span>剧本</span><b>' + esc(ed.scenario.title) + '</b></div>' +
      '<div class="fld"><span>景区</span><b>' + esc(ed.scenario.park_name || ed.scenario.city || '—') + '</b></div>' +
      '<div class="fld"><span>状态</span><b>' + esc(ed.scenario.status_label || '—') + '</b></div>' +
      '<div class="fld"><span>章节 / 节点</span><b>' + ed.chapters.length + ' 章 / ' + ed.nodes.length + ' 节点</b></div>' +
      '<div class="fld"><span>连线</span><b>' + ed.links.length + ' 条</b></div>' +
      '<div class="drawer-sec" style="margin-top:18px"><h4>章节流</h4>' +
      (ed.chapters.length ? ed.chapters.map(function (c) {
        var ns = ed.nodes.filter(function (n) { return num(n.chapter_id) === num(c.id); });
        return '<div class="lrow"><div class="rn rank-n">' + esc(c.idx) + '</div><div class="lt"><b>' + esc(c.title) + '</b>' +
          '<span>' + ns.length + ' 个节点：' + esc(ns.map(function (n) { return n.name; }).join(' → ') || '—') + '</span></div></div>';
      }).join('') : '<div class="muted" style="font-size:12px">暂无章节</div>') + '</div>';
    openModal({ title: '剧本预览 · ' + ed.scenario.title, body: body, okText: '进入编辑器继续编排', onOk: function (c) { c(); } });
  }

  function publishScenario() {
    var n = currentNode();
    var done = function () { toast('《' + (ed.scenario ? ed.scenario.title : '剧本') + '》已保存并发布 · ' + ed.nodes.length + ' 个节点已同步'); };
    if (!n) { done(); return; }
    api('/nodes/' + n.id, {
      method: 'PUT',
      body: {
        name: n.name, kind: n.kind, trigger_type: n.trigger_type, story_text: n.story_text,
        age_band: n.age_band, x: n.x, y: n.y, lat: n.lat, lng: n.lng, radius_m: n.radius_m
      }
    }).then(done).catch(function (e) { toast('发布失败：' + e.message, 'err'); });
  }

  /* ======================= 10. 任务中心 ======================= */

  var tkFilter = 'all';

  function renderTasks() {
    var box = $('#tkBody');
    var q = tkFilter === 'all' ? '' : qs({ type: tkFilter });
    loadInto(box, '正在加载任务列表', 'table', function () {
      return api('/tasks' + q).then(function (d) {
        state.data.tasks = d;
        var sum = d.summary || {};
        var items = (d.items || []).filter(function (it) { return tkFilter === 'all' || it.type === tkFilter; });

        $('#tkSub').textContent = '共 ' + nf(sum.total) + ' 个任务 · 平均完成时长 ' + nf(sum.avg_minutes) + ' 分钟 · 参与率 ' + nf(sum.join_rate) + '%';

        var rows = items.map(function (t) {
          return '<tr data-id="' + t.id + '">' +
            '<td class="cell-strong">' + (TASK_TYPE_EMOJI[t.type] || '') + ' ' + esc(t.title) + '</td>' +
            '<td>' + tagOf('task', t.type, t.type_label || TASK_TYPE_LABEL[t.type]) + '</td>' +
            '<td class="muted">' + esc(t.scenario_title || '—') + '</td>' +
            '<td class="muted">' + esc(ageText(t.age_band)) + '</td>' +
            '<td>' + progCell(t.completion_rate) + '</td>' +
            '<td>' + (t.enabled === false ? '<span class="tag tag-gray">停用</span>' : '<span class="tag tag-green">启用</span>') + '</td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="6" class="muted" style="text-align:center;padding:26px">该类型下暂无任务</td></tr>';

        box.innerHTML =
          kvHTML([
            { label: '任务总数', value: sum.total },
            { label: '今日完成', value: sum.done_today },
            { label: '平均完成时长', html: nf(sum.avg_minutes) + ' <small>min</small>' },
            { label: '任务参与率', html: nf(sum.join_rate) + '%' }
          ]).replace('<div class="kv">', '<div class="kv" style="margin-bottom:16px">') +
          '<div class="card"><div class="card-h"><b>任务列表</b>' +
            '<div class="seg" id="tkType">' + segItem('all', '全部') + segItem('observe', '观察') + segItem('find', '寻找') +
            segItem('photo', '拍摄') + segItem('solve', '解谜') + '</div></div>' +
            '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>任务名称</th><th>类型</th><th>所属剧本</th><th>适合年龄</th><th>完成率</th><th>状态</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div></div>';

        bindSeg('#tkType', tkFilter, function (v) { tkFilter = v; renderTasks(); });
        applySearch();
      });
    });
  }

  function openNewTaskModal() {
    var scenarios = (state.data.scenarios && state.data.scenarios.items) || [];
    if (!scenarios.length) {
      api('/scenarios').then(function (d) {
        state.data.scenarios = d;
        openNewTaskModal();
      }).catch(function (e) { toast('加载剧本列表失败：' + e.message, 'err'); });
      return;
    }
    var body =
      '<div class="fld2"><label>任务名称</label><input id="ntTitle" placeholder="例如：寻找三枚古铜钱"></div>' +
      '<div class="fld2"><label>任务类型</label><select id="ntType">' +
        ['observe', 'find', 'photo', 'solve'].map(function (k) {
          return '<option value="' + k + '">' + TASK_TYPE_EMOJI[k] + ' ' + TASK_TYPE_LABEL[k] + '</option>';
        }).join('') + '</select></div>' +
      '<div class="fld2"><label>所属剧本</label><select id="ntScenario">' +
        scenarios.map(function (s) { return '<option value="' + s.id + '">' + esc(s.title) + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>适合年龄层</label><select id="ntAge">' +
        Object.keys(AGE_LABEL).map(function (k) { return '<option value="' + k + '"' + (k === '8-12' ? ' selected' : '') + '>' + AGE_LABEL[k] + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>判定方式</label><select id="ntVerify">' +
        VERIFY_OPTIONS.map(function (o) { return '<option value="' + o[0] + '">' + esc(o[1]) + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>答案 / 关键词</label><input id="ntAnswer" placeholder="例如：莲花纹"></div>' +
      '<div class="fld2"><label>提示文案</label><input id="ntHint" placeholder="例如：先看塔基，再看塔身第二层"></div>' +
      '<div class="fld2"><label>奖励成长值</label><input id="ntGrowth" value="12" placeholder="成长值点数"></div>' +
      '<div class="fld2"><label>启用状态</label><span class="switch on" id="ntEnabled"><span class="tr"></span><span>任务启用中</span></span></div>';

    openModal({
      title: '新建任务', body: body, okText: '创建任务',
      onMount: function (root) {
        var sw = $('#ntEnabled', root);
        sw.addEventListener('click', function () {
          sw.classList.toggle('on');
          $('span:last-child', sw).textContent = sw.classList.contains('on') ? '任务启用中' : '已停用';
        });
      },
      onOk: function (close, btn) {
        var title = ($('#ntTitle').value || '').trim();
        if (!title) { toast('请填写任务名称', 'err'); return false; }
        btn.disabled = true;
        api('/tasks', {
          method: 'POST',
          body: {
            title: title,
            type: $('#ntType').value,
            scenario_id: num($('#ntScenario').value, 1),
            age_band: $('#ntAge').value,
            verify_mode: $('#ntVerify').value,
            answer: $('#ntAnswer').value,
            hint: $('#ntHint').value,
            reward_growth: num($('#ntGrowth').value, 12),
            enabled: $('#ntEnabled').classList.contains('on')
          }
        }).then(function () {
          close();
          toast('任务「' + title + '」创建成功');
          renderTasks();
        }).catch(function (e) {
          btn.disabled = false;
          toast('创建失败：' + e.message, 'err');
        });
        return false;
      }
    });
  }

  /* ======================= 11. 内容素材库 ======================= */

  var mtCat = null;

  function renderMaterials() {
    var box = $('#mtBody');
    loadInto(box, '正在加载素材库', 'table', function () {
      return api('/materials').then(function (d) {
        state.data.materials = d;
        var cats = (d.categories && d.categories.length) ? d.categories : CATEGORY_FALLBACK;
        var total = cats.reduce(function (s, c) { return s + num(c.count); }, 0);

        $('#mtSub').textContent = '共 ' + nf(total) + ' 条景区资料，用于 AI Story Engine 生成剧本';

        var recent = d.recent || [];
        var list = mtCat ? recent.filter(function (r) { return r.category_label === (catLabel(cats, mtCat)); }) : recent;

        var cardHtml = cats.map(function (c) {
          var emoji = c.emoji || CATEGORY_EMOJI[c.key] || '📄';
          return '<div class="mat-card' + (mtCat === c.key ? ' on' : '') + '" data-cat="' + esc(c.key) + '">' +
            '<div class="mat-ic" style="background:var(--gold-bg)">' + emoji + '</div>' +
            '<div><b>' + esc(c.label) + '</b><span>' + nf(c.count) + ' 条素材</span></div></div>';
        }).join('');

        var recentHtml = list.map(function (r) {
          var st = r.status || 'pending';
          return '<div class="lrow"><div class="rn rank-n">📄</div>' +
            '<div class="lt"><b>' + esc(r.title) + '</b><span>' + esc((r.category_label || '未分类') + ' · ' + (r.size || '—')) + '</span></div>' +
            tagOf('material', st, r.status_label) + '</div>';
        }).join('') || '<div class="muted" style="font-size:12px;padding:12px 0">该分类下暂无最近上传记录</div>';

        box.innerHTML =
          '<div class="mat-grid mb16">' + cardHtml + '</div>' +
          '<div class="grid g2">' +
            '<div class="card"><div class="card-h"><b>AI 语料训练进度</b><span>' + esc(mtCat ? catLabel(cats, mtCat) + ' 资料包' : '景区资料包') + '</span></div>' +
              stepsHTML(d.index_steps) +
              '<p style="font-size:11.5px;color:var(--text3);margin-top:14px;line-height:1.7">' + esc(d.index_note || '') + '</p></div>' +
            '<div class="card"><div class="card-h"><b>最近上传</b><span class="link" id="mtAll">' + (mtCat ? '显示全部 ›' : '全部记录') + '</span></div>' + recentHtml + '</div>' +
          '</div>';

        $$('.mat-card', box).forEach(function (c) {
          c.addEventListener('click', function () {
            mtCat = (mtCat === c.dataset.cat) ? null : c.dataset.cat;
            renderMaterials();
          });
        });
        var all = $('#mtAll', box);
        if (all) all.addEventListener('click', function () { mtCat = null; renderMaterials(); });
      });
    });
  }

  function catLabel(cats, key) {
    for (var i = 0; i < cats.length; i++) if (cats[i].key === key) return cats[i].label;
    return key;
  }

  function openUploadModal() {
    var cats = (state.data.materials && state.data.materials.categories) || CATEGORY_FALLBACK;
    var body =
      '<div class="fld2"><label>素材分类</label><select id="mtCatSel">' +
        cats.map(function (c) { return '<option value="' + esc(c.key) + '">' + esc((c.emoji || '') + ' ' + c.label) + '</option>'; }).join('') +
      '</select></div>' +
      '<div class="fld2"><label>标题</label><input id="mtTitle" placeholder="例如：唐代长安城坊市考"></div>' +
      '<div class="fld2"><label>正文内容</label><textarea id="mtContent" rows="7" placeholder="粘贴景区历史 / 建筑 / 非遗 / 传说等资料正文，将用于向量化入库…"></textarea></div>' +
      '<div class="hint-box">上传后素材将进入「结构化解析 → 向量化入库」流程，完成后可被 AI Story Engine 引用生成剧本。</div>';
    openModal({
      title: '上传素材', body: body, okText: '上传并入库', wide: true,
      onOk: function (close, btn) {
        var title = ($('#mtTitle').value || '').trim();
        var content = ($('#mtContent').value || '').trim();
        if (!title) { toast('请填写素材标题', 'err'); return false; }
        if (!content) { toast('请填写素材正文', 'err'); return false; }
        btn.disabled = true;
        api('/materials', {
          method: 'POST',
          body: { park_id: state.parkId, category: $('#mtCatSel').value, title: title, content: content }
        }).then(function () {
          close();
          toast('素材「' + title + '」已上传，正在解析入库');
          renderMaterials();
        }).catch(function (e) {
          btn.disabled = false;
          toast('上传失败：' + e.message, 'err');
        });
        return false;
      }
    });
  }

  /* ======================= 12. 游客管理 ======================= */

  var vsFilter = 'all';

  function renderVisitors() {
    var box = $('#vsBody');
    loadInto(box, '正在加载游客档案', 'table', function () {
      /* 优先使用 age_band 查询参数，并在客户端再做一次过滤兜底 */
      var q = vsFilter === 'all' ? '' : qs({ age_band: vsFilter });
      return api('/visitors' + q).then(function (d) {
        state.data.visitors = d;
        var sum = d.summary || {};
        var all = d.items || [];
        /* 契约未强制 items 携带 age_band：后端未返回该字段时不做过滤，避免误判为空列表 */
        var hasAge = all.some(function (v) { return v.age_band; });
        var items = all.filter(function (v) { return vsFilter === 'all' || !hasAge || v.age_band === vsFilter; });

        $('#vsSub').textContent = '今日活跃家庭 ' + nf(sum.active_families) + ' · 累计注册 ' + nf(sum.total_users) + ' 用户 · 点击任意行查看详情';

        var rows = items.map(function (v) {
          return '<tr data-id="' + v.id + '">' +
            '<td class="cell-strong">' + esc(v.name) + '</td>' +
            '<td class="muted">' + esc(v.city || '—') + '</td>' +
            '<td class="muted">' + esc(v.scenario_title || '—') + '</td>' +
            '<td class="num">Lv.' + esc(v.level) + ' · ' + nf(v.growth_total) + '</td>' +
            '<td class="muted num">' + esc(v.last_play || '—') + '</td>' +
            '<td>' + tagOf('visitor', v.status, v.status_label) + '</td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="6" class="muted" style="text-align:center;padding:26px">该年龄层下暂无游客记录</td></tr>';

        box.innerHTML =
          kvHTML([
            { label: '今日活跃家庭', value: sum.active_families },
            { label: '累计注册用户', value: sum.total_users },
            { label: '平均游玩时长', html: nf(sum.avg_minutes) + ' <small>min</small>' },
            { label: '复购 / 推荐率', html: nf(sum.repeat_rate) + '%' }
          ]).replace('<div class="kv">', '<div class="kv" style="margin-bottom:16px">') +
          '<div class="card"><div class="card-h"><b>游客 / 家庭列表</b>' +
            '<div class="seg" id="vsAge">' + segItem('all', '全部') + segItem('4-8', '亲子探索') +
            segItem('8-12', '少年冒险') + segItem('12+', '沉浸剧本') + '</div></div>' +
            (vsFilter !== 'all' && !hasAge ? '<div class="hint-box" style="margin-bottom:12px">后端未返回年龄层字段，已展示全部游客记录。</div>' : '') +
            '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>游客 / 家庭</th><th>所在城市</th><th>游玩剧本</th><th>成长值</th><th>最近游玩</th><th>状态</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table></div></div>';

        bindSeg('#vsAge', vsFilter, function (v) { vsFilter = v; renderVisitors(); });
        bindTableRows(box, function (id) { openVisitorDrawer(id); });
        applySearch();
      });
    });
  }

  function openVisitorDrawer(id) {
    openDrawer('<div class="state-box" style="background:transparent;border:none"><div class="pulse"><i></i><i></i><i></i></div><p style="margin:0">正在加载游客档案…</p></div>');
    api('/visitors/' + id).then(function (v) {
      var growth = (v.growth || []).map(function (g) {
        return '<div class="grow-row"><div class="gl">' + esc(g.label) + '</div>' +
          '<div class="prog"><i style="width:' + clamp(g.value, 0, 100) + '%"></i></div>' +
          '<div class="gv">' + esc(g.value) + '</div></div>';
      }).join('') || '<div class="muted" style="font-size:12px">暂无成长维度数据</div>';

      var badges = (v.badges || []).map(function (b) {
        return '<div class="bg-item' + (b.got ? '' : ' off') + '"><span class="bi-e">' + esc(b.emoji || '🏅') + '</span><b>' + esc(b.name) + '</b></div>';
      }).join('') || '<div class="muted" style="font-size:12px">暂无徽章</div>';

      var trail = (v.trail || []).map(function (t) {
        return '<div class="tl-item"><b>' + esc(t.node_name) + '</b><span>' + esc(t.event || '') + '</span><div class="tm">' + esc(t.at || '') + '</div></div>';
      }).join('') || '<div class="muted" style="font-size:12px">暂无游玩轨迹</div>';

      openDrawer(
        '<div class="drawer-h"><div class="av">🧭</div>' +
          '<div class="dh-b"><b>' + esc(v.name) + '</b><span>' + esc((v.city || '') + ' · Lv.' + v.level + ' ' + (v.level_name || '')) + '</span></div>' +
          '<div class="close">✕</div></div>' +
        '<div class="drawer-sec"><h4>基础信息</h4>' +
          '<div class="fld"><span>所在城市</span><b>' + esc(v.city || '—') + '</b></div>' +
          '<div class="fld"><span>成长值</span><b>' + nf(v.growth_total) + '</b></div>' +
          '<div class="fld"><span>关联潮玩</span><b>' + esc(v.device ? (v.device.nickname + ' · ' + (v.device.sku_name || '')) : '—') + '</b></div>' +
        '</div>' +
        '<div class="drawer-sec"><h4>成长五维度</h4>' + growth + '</div>' +
        '<div class="drawer-sec"><h4>已获徽章</h4><div class="badge-grid">' + badges + '</div></div>' +
        '<div class="drawer-sec"><h4>游玩轨迹</h4><div class="tl">' + trail + '</div></div>' +
        '<div class="draw-actions"><button class="btn btn-gold" style="flex:1" type="button" id="dvToEditor">查看游玩剧本</button>' +
        '<button class="btn" type="button" id="dvMsg">发送消息</button></div>'
      );
      var toEd = $('#dvToEditor');
      if (toEd) toEd.addEventListener('click', function () { closeDrawer(); location.hash = '#editor'; });
      var msg = $('#dvMsg');
      if (msg) msg.addEventListener('click', function () { toast('已向「' + v.name + '」发送运营消息（演示）'); });
    }).catch(function (e) {
      openDrawer('<div class="drawer-h"><div class="dh-b"><b>加载失败</b><span>' + esc(e.message) + '</span></div><div class="close">✕</div></div>' +
        '<button class="btn btn-gold" style="width:100%;justify-content:center" type="button" id="dvRetry">重试</button>');
      var r = $('#dvRetry');
      if (r) r.addEventListener('click', function () { openVisitorDrawer(id); });
    });
  }

  /* ======================= 13. 潮玩 IP 管理 ======================= */

  function renderIptoys() {
    var box = $('#ipBody');
    loadInto(box, '正在加载潮玩 IP 数据', 'kpi', function () {
      return api('/iptoys').then(function (d) {
        state.data.iptoys = d;
        var sum = d.summary || {};
        var ch = d.character || {};

        $('#ipSub').textContent = '阿游角色体系 · 累计激活 ' + nf(sum.activated) + ' 台 · 城市限定款 ' + nf(sum.city_editions) + ' 款';

        var editions = (d.editions || []).map(function (e) {
          var emoji = e.emoji || EDITION_EMOJI[e.city] || '🧭';
          return '<div class="mat-card" style="flex-direction:column;text-align:center;padding:12px">' +
            '<div class="mat-ic" style="background:var(--gold-bg)">' + esc(emoji) + '</div>' +
            '<div><b>' + esc(e.title) + '</b><span>' + esc(e.city) + '</span></div></div>';
        }).join('') || '<div class="muted" style="font-size:12px">暂无城市限定款</div>';

        var skus = (d.skus || []).map(function (s) {
          var rate = s.activation_rate;
          return '<tr>' +
            '<td class="cell-strong">' + esc(s.name) + (s.price ? ' <span class="muted" style="font-weight:400">¥' + esc(s.price) + '</span>' : '') + '</td>' +
            '<td class="muted">' + esc(s.city || '—') + '</td>' +
            '<td class="num">' + (s.stock === null || s.stock === undefined ? '—' : nf(s.stock)) + '</td>' +
            '<td class="num">' + nf(s.activated) + '</td>' +
            '<td>' + progCell(rate) + '</td>' +
            '<td>' + tagOf('sku', s.status, s.status_label) + '</td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="6" class="muted" style="text-align:center;padding:26px">暂无 SKU 数据</td></tr>';

        box.innerHTML =
          kvHTML([
            { label: '累计激活设备', value: sum.activated },
            { label: '今日新增激活', value: sum.today_activated },
            { label: '设备在线率', html: nf(sum.online_rate) + '%' },
            { label: '城市限定款', value: sum.city_editions }
          ]).replace('<div class="kv">', '<div class="kv" style="margin-bottom:16px">') +

          '<div class="grid g2 mb16">' +
            '<div class="card"><div class="card-h"><b>基础角色 · ' + esc(ch.name || '阿游') + '</b><span>AI TRAVEL COMPANION</span></div>' +
              '<div style="display:flex;gap:16px;align-items:center">' +
                '<div style="width:96px;height:96px;border-radius:16px;flex:none;border:1px solid var(--gold-bg);display:flex;align-items:center;justify-content:center;font-size:42px;background:linear-gradient(150deg,#1D2740,#141A2E)">' + esc(ch.avatar_emoji || '🧭') + '</div>' +
                '<div style="flex:1">' +
                  '<div class="fld"><span>角色定位</span><b>' + esc(ch.positioning || '—') + '</b></div>' +
                  '<div class="fld"><span>可换装</span><b>' + esc(ch.dressable || '—') + '</b></div>' +
                  '<div class="fld"><span>已上线形态</span><b>' + nf(ch.live_editions) + ' 个城市限定</b></div>' +
                '</div>' +
              '</div></div>' +
            '<div class="card"><div class="card-h"><b>城市限定款</b><span>' + nf((d.editions || []).length) + ' 款</span></div>' +
              '<div class="mat-grid" style="grid-template-columns:repeat(3,1fr)">' + editions + '</div></div>' +
          '</div>' +

          '<div class="card"><div class="card-h"><b>SKU 与库存</b><span>库存偏低自动标橙 · 未上市标灰</span></div>' +
            '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>SKU 名称</th><th>关联城市</th><th>库存</th><th>激活量</th><th>激活率</th><th>状态</th></tr></thead>' +
            '<tbody>' + skus + '</tbody></table></div></div>';

        $$('tbody tr', box).forEach(function (tr) { tr.style.cursor = 'default'; });
      });
    });
  }

  /* 新增限定款（契约 2.14.1 POST /api/admin/iptoys/editions）
     景区下拉来自 GET /api/admin/park 的 all_parks；选中景区自动带出 city 与 emoji */
  function openNewEditionModal() {
    var loading = openModal({
      title: '新增限定款',
      body: '<div class="state-box" style="background:transparent;border:none;padding:22px">' +
        '<div class="pulse"><i></i><i></i><i></i></div><p style="margin:0">正在读取景区目录…</p></div>',
      footer: '<button class="btn" data-act="cancel" type="button">取消</button>'
    });
    api('/park' + qs({ park_id: state.parkId })).then(function (d) {
      loading.close();
      var parks = (d && d.all_parks && d.all_parks.length) ? d.all_parks : PARKS;
      editionForm(parks, (d && d.park) || null);
    }).catch(function (e) {
      loading.close();
      editionForm(PARKS, null);
      toast('景区目录读取失败，已回退内置景区列表：' + e.message, 'err');
    });
  }

  /* 限定款表单（parks: all_parks 数组；currentPark: 当前景区详情） */
  function editionForm(parks, currentPark) {
    var fallbackId = parks.length ? num(parks[0].id, 1) : 1;
    var defId = num((currentPark && currentPark.id) || state.parkId, fallbackId);
    var options = parks.map(function (p) {
      return '<option value="' + p.id + '"' + (num(p.id) === defId ? ' selected' : '') + '>' +
        esc(p.name) + '（' + esc(p.city || '') + '）</option>';
    }).join('');

    var body =
      '<div class="fld2"><label>限定款名称</label><input id="neName" placeholder="例如：阿游 · 苏绣限定款"></div>' +
      '<div class="fld2"><label>关联景区</label><select id="nePark">' + options + '</select></div>' +
      '<div class="fld2"><label>关联城市（随景区自动带出）</label><input id="neCity" readonly></div>' +
      '<div class="fld2"><label>形象标识 emoji（可修改）</label><input id="neEmoji" maxlength="4"></div>' +
      '<div class="fld2"><label>首发库存 / 售价（元）</label><div class="row2">' +
        '<input id="neStock" value="800" placeholder="库存：≥ 0 的整数">' +
        '<input id="nePrice" value="399" placeholder="售价：大于 0 的数字">' +
      '</div></div>' +
      '<div class="modal-err" id="neErr" style="display:none"></div>' +
      '<div class="hint-box">提交后新 SKU 状态固定为「在售」、激活量为 0，并立即出现在下方 SKU 与库存表格中。</div>';

    openModal({
      title: '新增限定款', body: body, okText: '提交新增',
      onMount: function (root) {
        var sel = $('#nePark', root), city = $('#neCity', root), emoji = $('#neEmoji', root);
        var autoEmoji = null;   /* 记录自动带出的 emoji，用户手改后不再覆盖 */

        function fillFrom(id) {
          var p = null;
          for (var i = 0; i < parks.length; i++) { if (num(parks[i].id) === num(id)) p = parks[i]; }
          if (p) city.value = p.city || '';
          var guess = (p && p.emoji) || EDITION_EMOJI[(p && p.city) || ''] || '🧭';
          if (emoji.value === '' || emoji.value === autoEmoji) { emoji.value = guess; autoEmoji = guess; }
          /* 景区详情里的 emoji 更权威：GET /api/admin/park?park_id=N
             （带请求景区校验，避免快速切换景区时过期响应覆盖当前值） */
          var reqId = num(id);
          api('/park' + qs({ park_id: id })).then(function (d) {
            if (num(sel.value) !== reqId) return;
            var pk = (d && d.park) || {};
            if (pk.emoji && emoji.value === autoEmoji) { emoji.value = pk.emoji; autoEmoji = pk.emoji; }
            if (pk.city && !city.value) city.value = pk.city;
          }).catch(function () { /* 详情失败时沿用已带出的城市与 emoji */ });
        }

        sel.addEventListener('change', function () { fillFrom(sel.value); });
        fillFrom(sel.value);
      },
      onOk: function (close, btn) {
        var name = ($('#neName').value || '').trim();
        var city = ($('#neCity').value || '').trim();
        var parkId = num($('#nePark').value, 0);
        var emoji = ($('#neEmoji').value || '').trim() || '🧭';
        var stockRaw = ($('#neStock').value || '').trim();
        var priceRaw = ($('#nePrice').value || '').trim();
        var stock = Number(stockRaw);
        var price = Number(priceRaw);

        function fail(msg) {
          var e1 = $('#neErr');
          if (e1) { e1.innerHTML = '<b>无法提交：</b>' + esc(msg); e1.style.display = 'block'; }
          toast(msg, 'err');
          return false;
        }

        if (!name) return fail('请填写限定款名称');
        if (!parkId) return fail('请选择关联景区');
        if (!/^\d+$/.test(stockRaw) || !(stock >= 0)) return fail('库存必须是 ≥ 0 的整数');
        if (priceRaw === '' || isNaN(price) || !(price > 0)) return fail('售价必须是大于 0 的数字');

        var e2 = $('#neErr');
        if (e2) e2.style.display = 'none';
        btn.disabled = true;
        btn.textContent = '提交中…';

        api('/iptoys/editions', {
          method: 'POST',
          body: { name: name, city: city, park_id: parkId, emoji: emoji, stock: stock, price: price }
        }).then(function (res) {
          close();
          toast('已新增限定款：' + ((res && res.name) || name));
          renderIptoys();   /* 重新拉取 GET /api/admin/iptoys，刷新 SKU 表与 summary.city_editions */
        }).catch(function (err) {
          btn.disabled = false;
          btn.textContent = '提交新增';
          var e3 = $('#neErr');
          if (e3) { e3.innerHTML = '<b>提交失败：</b>' + esc(err.message); e3.style.display = 'block'; }
          toast('新增限定款失败：' + err.message, 'err');
        });
        return false;   /* 保留弹窗与已填内容 */
      }
    });
  }

  /* ======================= 14. 数据分析 ======================= */

  var anRange = '30d';

  function renderAnalytics() {
    var box = $('#anBody');
    var label = anRange === '7d' ? '近 7 天' : (anRange === '30d' ? '近 30 天' : '本季度');
    loadInto(box, '正在汇总分析数据', 'kpi', function () {
      return api('/analytics').then(function (d) {
        state.data.analytics = d;
        var rev = d.revenue || {};
        $('#anSub').textContent = label + ' · 用户行为、转化漏斗与营收结构';

        box.innerHTML =
          '<div class="grid" style="grid-template-columns:1.3fr 1fr;margin-bottom:16px">' +
            '<div class="card"><div class="card-h"><b>用户转化漏斗</b><span>' + esc(label) + ' · 全景区汇总</span></div>' +
              funnelHTML(d.funnel) + '</div>' +
            '<div class="card"><div class="card-h"><b>用户年龄分布</b><span>按剧本开启量</span></div>' +
              barsHTML(d.age_distribution) +
              '<div class="dotlegend">' + (d.age_distribution || []).map(function (a) {
                return '<span>' + esc(a.label) + '：' + nf(a.value) + ' 次</span>';
              }).join('') + '</div></div>' +
          '</div>' +
          '<div class="grid g2">' +
            '<div class="card"><div class="card-h"><b>营收结构</b><span>本期 ' + esc(rev.total || '—') + '</span></div>' +
              kvHTML((rev.items || []).map(function (it) { return { label: it.label, value: it.amount }; }))
                .replace('class="kv"', 'class="kv" style="grid-template-columns:repeat(2,1fr)"') + '</div>' +
            '<div class="card"><div class="card-h"><b>用户留存</b><span>按周</span></div>' +
              barsHTML(d.retention, true) + '</div>' +
          '</div>';

        bindSeg('#anRange', anRange, function (v) { anRange = v; renderAnalytics(); });
      });
    });
  }

  /* ======================= 15. 景区与联名 ======================= */

  function renderPark() {
    var box = $('#pkBody');
    loadInto(box, '正在加载景区配置', 'kpi', function () {
      return api('/park' + qs({ park_id: state.parkId })).then(function (d) {
        state.data.park = d;
        var p = d.park || {};
        state.parkName = p.name || state.parkName;
        $('#pkSub').textContent = (p.name || '景区') + ' · 合作模式：' + (p.partner_mode || '—');
        updateParkChrome();

        var share = (d.revenue_share || []).map(function (s) {
          return '<div class="fld"><span>' + esc(s.item) + '</span><b>景区 ' + esc(s.park_share || '—') + ' / 平台 ' + esc(s.platform_share || '—') + '</b></div>';
        }).join('') || '<div class="muted" style="font-size:12px">暂无分账配置</div>';

        var coops = (d.cooperations || []).map(function (c) {
          return '<tr><td class="cell-strong">' + esc(c.name) + '</td>' +
            '<td><span class="tag tag-purple">' + esc(c.type || 'IP 联名') + '</span></td>' +
            '<td>' + tagOf('coop', c.status, c.status_label) + '</td>' +
            '<td class="muted num">' + esc(c.since || '—') + '</td></tr>';
        }).join('') || '<tr><td colspan="4" class="muted" style="text-align:center;padding:26px">暂无联名合作记录</td></tr>';

        box.innerHTML =
          '<div class="grid g2 mb16">' +
            '<div class="card"><div class="card-h"><b>景区基础信息</b>' +
              (p.verified ? '<span class="tag tag-green">已认证</span>' : '<span class="tag tag-orange">待认证</span>') + '</div>' +
              '<div class="fld2"><label>景区名称</label><input id="pkName" value="' + esc(p.name || '') + '"></div>' +
              '<div class="fld2"><label>地理坐标（纬度 / 经度）</label><div class="row2">' +
                '<input id="pkLat" value="' + esc(p.lat === undefined ? '' : p.lat) + '" placeholder="纬度">' +
                '<input id="pkLng" value="' + esc(p.lng === undefined ? '' : p.lng) + '" placeholder="经度"></div></div>' +
              '<div class="fld2"><label>地理围栏半径（米）</label><input id="pkRadius" value="' + esc(p.radius_m === undefined ? '' : p.radius_m) + '"></div>' +
              '<div class="fld2"><label>合作模式</label><input id="pkMode" value="' + esc(p.partner_mode || '') + '"></div>' +
              '<div class="fld"><span>已上线剧本</span><b>' + nf(p.scenario_count) + ' 个</b></div>' +
              '<div class="fld"><span>剧情节点</span><b>' + nf(p.node_count) + ' 个 STORY NODE</b></div>' +
              '<div class="fld"><span>所在城市</span><b>' + esc(p.city || '—') + '</b></div>' +
            '</div>' +
            '<div class="card"><div class="card-h"><b>双边模式 · 收益分账</b><span>C 端家庭 ↔ 平台 ↔ B 端景区</span></div>' +
              share +
              '<div class="hint-box" style="margin-top:14px">结算周期：每月 5 日对账出账；C 端潮玩销售、剧情会员订阅按比例分成，B 端 SaaS 服务费按月结算，IP 联名授权按项目另行结算。</div>' +
            '</div>' +
          '</div>' +
          '<div class="card"><div class="card-h"><b>IP 联名合作</b><span>' + nf((d.cooperations || []).length) + ' 个合作方</span></div>' +
            '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>合作方</th><th>合作类型</th><th>状态</th><th>开始时间</th></tr></thead>' +
            '<tbody>' + coops + '</tbody></table></div></div>';

        $$('tbody tr', box).forEach(function (tr) { tr.style.cursor = 'default'; });
      });
    });
  }

  function savePark() {
    var id = state.parkId;
    var body = {
      name: ($('#pkName') || {}).value || '',
      lat: num(($('#pkLat') || {}).value, 0),
      lng: num(($('#pkLng') || {}).value, 0),
      radius_m: num(($('#pkRadius') || {}).value, 0),
      partner_mode: ($('#pkMode') || {}).value || ''
    };
    if (!body.name) { toast('景区名称不能为空', 'err'); return; }
    api('/park/' + id, { method: 'PUT', body: body }).then(function () {
      toast('景区配置已保存');
      renderPark();
    }).catch(function (e) { toast('保存失败：' + e.message, 'err'); });
  }

  /* ======================= 运行指标（observability 2.21） ======================= */

  /* 秒 → 中文可读时长（如「1 小时 12 分」） */
  function fmtDuration(sec) {
    var s = Math.max(0, Math.floor(num(sec, 0)));
    if (s < 60) return s + ' 秒';
    var m = Math.floor(s / 60);
    var h = Math.floor(m / 60);
    var d = Math.floor(h / 24);
    if (d > 0) return d + ' 天 ' + (h % 24) + ' 小时';
    if (h > 0) return h + ' 小时 ' + (m % 60) + ' 分';
    return m + ' 分 ' + (s % 60) + ' 秒';
  }

  /* 毫秒格式化：小于 1ms 显示 「<1 ms」，不显示 0 ms */
  function fmtMs(v) {
    if (v === null || v === undefined || v === '') return '—';
    var n = Number(v);
    if (isNaN(n)) return '—';
    if (n < 1) return '<1 ms';
    return (n >= 100 ? String(Math.round(n)) : String(Math.round(n * 10) / 10)) + ' ms';
  }

  var OBS_METHOD_TAG = { GET: 'tag-blue', POST: 'tag-gold', PUT: 'tag-purple', DELETE: 'tag-red', PATCH: 'tag-orange' };
  function obsMethod(m) {
    var k = String(m || '').toUpperCase();
    return '<span class="tag ' + (OBS_METHOD_TAG[k] || 'tag-gray') + '">' + esc(k || '—') + '</span>';
  }
  function obsStatusTag(st) {
    var n = num(st, 0);
    var cls = n >= 500 ? 'tag-red' : (n >= 400 ? 'tag-orange' : 'tag-green');
    return '<span class="tag ' + cls + '">' + n + '</span>';
  }

  /* business 字段分组与中文标签（覆盖契约中全部字段） */
  var OBS_BIZ_GROUPS = [
    {
      title: '内容资产', hint: '库内内容规模', items: [
        ['parks', '景区'], ['parks_lit', '已点亮景区'], ['scenarios', '剧本'], ['scenarios_online', '已上线剧本'],
        ['nodes', '剧情节点'], ['tasks', '任务'], ['materials_indexed', '已入库素材']
      ]
    },
    {
      title: '用户与设备', hint: 'C 端用户与潮玩设备', items: [
        ['users', '注册用户'], ['devices_activated', '已激活设备'],
        ['codes_used', '已使用激活码'], ['users_with_trail', '有足迹的用户数']
      ]
    },
    {
      title: '行为与转化', hint: '剧情互动、任务与 AI 生成', items: [
        ['node_visits', '剧情点到访次数'], ['task_submissions', '任务提交次数'], ['tasks_passed', '任务通过数'],
        ['task_pass_rate', '任务通过率'], ['badges_granted', '已发放徽章'], ['growth_total', '累计成长值'],
        ['ai_jobs', 'AI 生成次数'], ['ai_avg_ms', 'AI 生成平均耗时'],
        ['ai_scenarios_created', 'AI 已生成剧本数'], ['events_logged', '已记录事件数']
      ]
    }
  ];

  function obsBizValue(key, biz) {
    if (key === 'ai_avg_ms') return num(biz.ai_jobs, 0) > 0 ? esc(fmtMs(biz.ai_avg_ms)) : '—';
    if (key === 'task_pass_rate') return esc(nf(biz.task_pass_rate)) + '<small>%</small>';
    return esc(nf(biz[key]));
  }

  function obsBizCard(g, biz) {
    return '<div class="card"><div class="card-h"><b>' + esc(g.title) + '</b><span>' + esc(g.hint) + '</span></div>' +
      '<div class="ob-stat-grid">' + g.items.map(function (it) {
        return '<div class="ob-stat"><span>' + esc(it[1]) + '</span><b>' + obsBizValue(it[0], biz) + '</b></div>';
      }).join('') + '</div></div>';
  }

  function renderObservability() {
    var box = $('#obBody');
    syncObsSwitch();
    loadInto(box, '正在读取运行指标', 'kpi', function () { return loadObsData(false, box); });
  }

  /* silent=true 用于自动刷新：不显示骨架、失败只提示不清空已有内容 */
  function loadObsData(silent, box) {
    return api('/observability').then(function (d) {
      state.data.observability = d;
      paintObservability();
    }).catch(function (e) {
      if (!silent) throw e;
      toast('运行指标自动刷新失败：' + e.message, 'err');
      if (!state.data.observability) {
        showError(box, e, function () { renderObservability(); });
      }
    });
  }

  function paintObservability() {
    var d = state.data.observability || {};
    var rq = d.requests || {};
    var biz = d.business || {};
    var box = $('#obBody');
    var slowTh = num(rq.slow_threshold_ms, 300);
    var errRate = num(rq.error_rate, 0);
    var avgMs = num(rq.avg_ms, 0);

    $('#obSub').textContent = (rq.version ? '版本 ' + rq.version + ' · ' : '') +
      '总请求 ' + nf(rq.requests_total) + ' 次 · 错误 ' + nf(rq.errors_total) + ' 次 · 更新于 ' +
      new Date().toTimeString().slice(0, 8);

    function kpiCard(cls, label, valHtml, unit, delta, valCls, longVal) {
      return '<div class="kpi ' + cls + '">' +
        '<div class="k-label">' + esc(label) + '</div>' +
        '<div class="k-val' + (valCls ? ' ' + valCls : '') + (longVal ? ' long' : '') + '">' + valHtml +
        (unit ? '<small>' + esc(unit) + '</small>' : '') + '</div>' +
        '<div class="k-delta">' + delta + '</div></div>';
    }

    var kpis =
      kpiCard('k1', '总请求数', esc(nf(rq.requests_total)), '次',
        '覆盖 ' + nf((rq.endpoints || []).length) + ' 个端点 · 明细 ' + nf((rq.recent || []).length) + ' 条') +
      kpiCard('k2', '平均耗时', (avgMs > 0 && avgMs < 1) ? '&lt;1' : esc(nf(avgMs)), 'ms',
        '慢请求阈值 ' + esc(nf(slowTh)) + ' ms') +
      kpiCard('k3', '错误率', esc(nf(errRate)), '%',
        errRate > 0 ? ('错误 ' + esc(nf(rq.errors_total)) + ' 次 · 需关注') : '无错误请求',
        errRate > 0 ? 'warn' : 'ok') +
      kpiCard('k4', '已运行时长', esc(fmtDuration(rq.uptime_seconds)), '',
        '原始值 ' + esc(nf(rq.uptime_seconds)) + ' 秒', '', true);

    var noteBar = d.note ? '<div class="ob-note"><b>说明</b><span>' + esc(d.note) + '</span></div>' : '';

    box.innerHTML =
      '<div class="grid g4 mb16">' + kpis + '</div>' + noteBar +
      '<div class="card mb16"><div class="card-h"><b>端点调用统计</b>' +
        '<span>点击「调用次数 / 平均耗时 / 最大耗时」表头排序</span></div>' +
        '<div id="obEndpoints"></div></div>' +
      '<div class="grid g2 mb16">' +
        '<div class="card"><div class="card-h"><b>慢请求 Top 5</b><span>按最大耗时降序</span></div>' +
          '<div id="obSlow"></div></div>' +
        '<div class="card"><div class="card-h"><b>最近请求</b><span>最新 ' + nf(Math.min((rq.recent || []).length, 40)) + ' 条</span></div>' +
          '<div class="ob-list" id="obRecent"></div></div>' +
      '</div>' +
      '<div class="grid g3">' + OBS_BIZ_GROUPS.map(function (g) { return obsBizCard(g, biz); }).join('') + '</div>';

    paintObsEndpoints();
    paintObsSlow();
    paintObsRecent();
  }

  function paintObsEndpoints() {
    var host = $('#obEndpoints');
    if (!host) return;
    var rq = (state.data.observability || {}).requests || {};
    var slowTh = num(rq.slow_threshold_ms, 300);
    var rows = (rq.endpoints || []).slice();
    var key = state.obsSort;
    var dir = state.obsSortDir === 'asc' ? 1 : -1;
    rows.sort(function (a, b) { return (num(a[key], 0) - num(b[key], 0)) * dir; });

    function th(label, sortKey, extra) {
      var on = state.obsSort === sortKey;
      var arrow = on ? (state.obsSortDir === 'desc' ? '▼' : '▲') : '↕';
      return '<th class="ob-th-sort' + (on ? ' on' : '') + '" data-sort="' + sortKey + '">' + esc(label) +
        '<span class="ob-arrow' + (on ? '' : ' off') + '">' + arrow + '</span></th>';
    }

    var body = rows.map(function (e) {
      var isSlow = num(e.avg_ms, 0) > slowTh;
      var errs = num(e.errors, 0);
      var slows = num(e.slow, 0);
      return '<tr>' +
        '<td>' + obsMethod(e.method) + '</td>' +
        '<td class="mono cell-strong">' + esc(e.path) + '</td>' +
        '<td class="num">' + esc(nf(e.count)) + '</td>' +
        '<td><span class="ob-ms' + (isSlow ? ' warn' : '') + '">' + esc(fmtMs(e.avg_ms)) + '</span>' +
          (isSlow ? ' <span class="tag tag-orange">慢</span>' : '') + '</td>' +
        '<td><span class="ob-ms">' + esc(fmtMs(e.max_ms)) + '</span></td>' +
        '<td class="num">' + (errs > 0 ? '<span class="tag tag-red">' + errs + '</span>' : '0') + '</td>' +
        '<td class="num">' + (slows > 0 ? '<span class="tag tag-orange">' + slows + '</span>' : '0') + '</td>' +
        '</tr>';
    }).join('') || '<tr><td colspan="7" class="muted" style="text-align:center;padding:26px">暂无端点调用记录（服务刚启动时可能为空）</td></tr>';

    host.innerHTML = '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      '<th>方法</th><th>端点</th>' + th('调用次数', 'count') + th('平均耗时', 'avg_ms') + th('最大耗时', 'max_ms') +
      '<th>错误数</th><th>慢请求数</th>' +
      '</tr></thead><tbody>' + body + '</tbody></table></div>';

    $$('th[data-sort]', host).forEach(function (t) {
      t.addEventListener('click', function () {
        var k = t.dataset.sort;
        if (state.obsSort === k) {
          state.obsSortDir = state.obsSortDir === 'desc' ? 'asc' : 'desc';
        } else {
          state.obsSort = k;
          state.obsSortDir = 'desc';
        }
        paintObsEndpoints();
      });
    });
  }

  function paintObsSlow() {
    var host = $('#obSlow');
    if (!host) return;
    var rq = (state.data.observability || {}).requests || {};
    var list = (rq.slowest || []).slice().sort(function (a, b) { return num(b.max_ms, 0) - num(a.max_ms, 0); }).slice(0, 5);
    if (!list.length) {
      host.innerHTML = '<div class="muted" style="font-size:12px">暂无慢请求记录</div>';
      return;
    }
    var maxV = num(list[0].max_ms, 1) || 1;
    host.innerHTML = '<div class="ob-bars">' + list.map(function (s, i) {
      var w = clamp(num(s.max_ms, 0) / maxV * 100, 4, 100);
      return '<div class="ob-bar-i">' +
        '<div class="ob-bar-name" title="' + esc(s.path) + '">' + (i + 1) + '. ' + esc(s.path) + '</div>' +
        '<div class="ob-bar-t"><i style="width:' + w + '%"></i></div>' +
        '<div class="ob-bar-v">' + esc(fmtMs(s.max_ms)) + '</div></div>';
    }).join('') + '</div>';
  }

  function paintObsRecent() {
    var host = $('#obRecent');
    if (!host) return;
    var rq = (state.data.observability || {}).requests || {};
    var slowTh = num(rq.slow_threshold_ms, 300);
    var list = (rq.recent || []).slice(0, 40);
    if (!list.length) {
      host.innerHTML = '<div class="muted" style="font-size:12px">暂无请求记录</div>';
      return;
    }
    host.innerHTML = list.map(function (x) {
      var slow = num(x.ms, 0) >= slowTh;
      return '<div class="lrow">' +
        '<div class="lt"><b class="mono">' + esc(x.method || '') + ' ' + esc(x.path) + '</b>' +
        '<span>' + esc(x.at || '') + '</span></div>' +
        '<div class="ob-ms' + (slow ? ' warn' : '') + '">' + esc(fmtMs(x.ms)) + '</div>' +
        obsStatusTag(x.status) + '</div>';
    }).join('');
  }

  /* 自动刷新：默认关闭；离开页面必须停止定时器 */
  function syncObsSwitch() {
    var sw = $('#obAuto');
    if (!sw) return;
    sw.classList.toggle('on', !!state.obsAuto);
    var lb = $('#obAutoLabel');
    if (lb) lb.textContent = state.obsAuto ? '自动刷新中（每 5 秒）' : '每 5 秒自动刷新';
  }

  function stopObsAuto() {
    if (state.obsTimer) { clearInterval(state.obsTimer); state.obsTimer = null; }
  }

  function startObsAuto() {
    stopObsAuto();
    state.obsTimer = setInterval(function () {
      if (state.route !== 'observability') { stopObsAuto(); return; }
      loadObsData(true, $('#obBody'));
    }, 5000);
  }

  function toggleObsAuto() {
    state.obsAuto = !state.obsAuto;
    if (state.obsAuto) {
      startObsAuto();
      toast('运行指标已开启自动刷新（每 5 秒）');
    } else {
      stopObsAuto();
      toast('运行指标已关闭自动刷新');
    }
    syncObsSwitch();
  }

  /* ======================= 16. AI Story Engine 生成向导（模块 10） ======================= */

  var WIZ_STEPS = [
    { n: 1, t: '选择景区', s: '确定剧本所属景区与坐标系' },
    { n: 2, t: '生成模式', s: '主线 / 任务 / 对话 / 奖励 / 全剧本' },
    { n: 3, t: '参数配置', s: '年龄层 · 风格 · 章节与节点规模' },
    { n: 4, t: '生成结果', s: '世界观 · 章节 · 节点 · 奖励 · 素材来源' }
  ];

  var wiz = { step: 1, parkId: 1, mode: 'full', ageBand: '8-12', style: '', title: '', chapters: 3, nodes: 6, park: null, result: null, busy: false, prog: 0 };

  function openWizard() {
    if (state.route !== 'ai-wizard') state.prevRoute = state.route;
    wiz.parkId = state.parkId;
    if (location.hash === '#ai-wizard') { renderWizard(); return; }
    location.hash = '#ai-wizard';
  }

  function closeWizard() {
    location.hash = '#' + (state.prevRoute || 'scenarios');
  }

  function renderWizard() {
    if (!wiz.style) wiz.style = '悬疑解谜，融入本地历史与文化知识，鼓励孩子观察真实建筑与自然环境。';
    if (!wiz.title) wiz.title = '';

    $('#wizSteps').innerHTML = WIZ_STEPS.map(function (s) {
      var cls = wiz.step === s.n ? 'cur' : (wiz.step > s.n ? 'done' : '');
      return '<div class="wiz-step ' + cls + '"><div class="ws-n">' + (wiz.step > s.n ? '✓' : s.n) + '</div>' +
        '<div><b>' + s.t + '</b><span>' + s.s + '</span></div></div>';
    }).join('');

    var engineBox = $('#wizEngine');
    engineBox.innerHTML = engineBadge(state.engine) +
      (state.engine && !state.engine.llm_enabled ? '<span class="tag tag-gray">未接大模型</span>' : '');

    if (wiz.step === 1) renderWizStep1();
    else if (wiz.step === 2) renderWizStep2();
    else if (wiz.step === 3) renderWizStep3();
    else renderWizStep4();

    renderWizFoot();
  }

  function renderWizFoot() {
    var foot = $('#wizFoot');
    var back = wiz.step > 1 && wiz.step < 4 && !wiz.busy ?
      '<button class="btn" id="wizBack" type="button">← 上一步</button>' : '';
    var next = '';
    if (wiz.step === 1) next = '<button class="btn btn-gold" id="wizNext" type="button">下一步：选择生成模式 →</button>';
    else if (wiz.step === 2) next = '<button class="btn btn-gold" id="wizNext" type="button">下一步：配置参数 →</button>';
    else if (wiz.step === 3) next = '<button class="btn btn-gold" id="wizGen" type="button">' +
      '<svg viewBox="0 0 24 24"><path d="M12 3l2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4z"/></svg>开始生成 ✦</button>';
    else next = '<button class="btn btn-gold" id="wizRegen" type="button">重新生成</button>';

    foot.innerHTML = '<button class="btn" id="wizHome" type="button">返回运营台</button>' + back + '<span class="sp"></span>' + next;
    var b = $('#wizBack');
    if (b) b.addEventListener('click', function () { wiz.step--; renderWizard(); });
    var nx = $('#wizNext');
    if (nx) nx.addEventListener('click', function () { wiz.step++; renderWizard(); });
    var g = $('#wizGen');
    if (g) g.addEventListener('click', runWizardGenerate);
    var rg = $('#wizRegen');
    if (rg) rg.addEventListener('click', function () { wiz.result = null; wiz.prog = 0; runWizardGenerate(); });
    var hm = $('#wizHome');
    if (hm) hm.addEventListener('click', closeWizard);
  }

  /* 第 1 步：选择景区 */
  function renderWizStep1() {
    var body = $('#wizBody');
    body.innerHTML =
      '<div class="wiz-h">第 1 步 · 选择景区</div>' +
      '<div class="wiz-sub">AI Story Engine 将读取该景区的素材库（历史 / 建筑 / 非遗 / 传说 / 地理），生成与该景区强绑定的剧本。</div>' +
      '<div class="grid g2">' +
        '<div class="fld2"><label>景区</label><select id="wizPark">' +
          PARKS.map(function (p) { return '<option value="' + p.id + '"' + (p.id === wiz.parkId ? ' selected' : '') + '>' + esc(p.name) + '</option>'; }).join('') +
        '</select>' +
        '<div id="wizParkInfo" style="margin-top:14px"></div></div>' +
        '<div class="res-box"><h5>数据链路</h5>' +
          '<p>景区资料 → <b style="color:var(--gold-l)">AI Story Engine</b> → 景区故事 → 用户体验 → 数据沉淀</p>' +
          '<div class="dotlegend" style="margin-top:10px"><span>C 端家庭</span><span>↔ AI STORY PLATFORM ↔</span><span>B 端景区</span></div>' +
        '</div>' +
      '</div>';

    var sel = $('#wizPark');
    sel.addEventListener('change', function () { wiz.parkId = num(sel.value, 1); loadWizPark(); });
    loadWizPark();
  }

  function loadWizPark() {
    var box = $('#wizParkInfo');
    if (!box) return;
    box.innerHTML = '<div class="pulse"><i></i><i></i><i></i></div>';
    api('/park' + qs({ park_id: wiz.parkId })).then(function (d) {
      var p = d.park || {};
      wiz.park = p;
      state.parkName = p.name || state.parkName;
      box.innerHTML = '<div class="res-box"><h5>景区档案</h5>' +
        '<div class="fld"><span>景区名称</span><b>' + esc(p.name || '—') + '</b></div>' +
        '<div class="fld"><span>地理坐标</span><b>' + esc(p.lat) + '°N · ' + esc(p.lng) + '°E</b></div>' +
        '<div class="fld"><span>围栏半径</span><b>' + nf(p.radius_m) + ' m</b></div>' +
        '<div class="fld"><span>已上线剧本</span><b>' + nf(p.scenario_count) + ' 个</b></div>' +
        '<div class="fld"><span>剧情节点</span><b>' + nf(p.node_count) + ' 个</b></div>' +
        '<div class="fld"><span>合作模式</span><b>' + esc(p.partner_mode || '—') + '</b></div>' +
        '<div class="fld"><span>认证状态</span><b>' + (p.verified ? '已认证' : '待认证') + '</b></div></div>';
    }).catch(function (e) {
      box.innerHTML = '<div class="hint-box">景区档案读取失败：' + esc(e.message) + '（可继续生成，节点坐标将按画布网格布局）</div>';
    });
  }

  /* 第 2 步：生成模式 */
  function renderWizStep2() {
    var modes = [
      { key: 'full', e: '✦', t: '一键生成全剧本', d: '世界观 + 章节 + 节点 + 任务 + 对话 + 奖励，并入库为草稿剧本', rec: true },
      { key: 'mainline', e: '🧭', t: '生成主线', d: '生成世界观与主线章节脉络，确定剧情走向' },
      { key: 'task', e: '🎯', t: '生成任务', d: '为剧情节点生成观察 / 寻找 / 拍摄 / 解谜任务与判定' },
      { key: 'dialog', e: '💬', t: '生成对话', d: '生成阿游的角色对话与引导话术' },
      { key: 'reward', e: '🏅', t: '生成奖励', d: '生成徽章与成长值奖励体系' }
    ];
    var caps = (state.engine && state.engine.capabilities) || [];

    $('#wizBody').innerHTML =
      '<div class="wiz-h">第 2 步 · 生成模式</div>' +
      '<div class="wiz-sub">默认推荐「一键生成全剧本」：一次性产出可上线的完整剧本草稿。</div>' +
      '<div class="mode-grid">' + modes.map(function (m) {
        return '<div class="mode-card' + (wiz.mode === m.key ? ' on' : '') + '" data-mode="' + m.key + '">' +
          (m.rec ? '<span class="mc-rec">推荐</span>' : '') +
          '<div class="mc-e">' + m.e + '</div><b>' + m.t + '</b><span>' + m.d + '</span></div>';
      }).join('') + '</div>' +
      '<div class="res-box" style="margin-top:16px"><h5>AI 引擎状态</h5>' +
        '<div class="fld"><span>引擎标识</span><b>' + esc((state.engine && state.engine.engine) || '检测中…') + '</b></div>' +
        '<div class="fld"><span>大模型接入</span><b>' + (state.engine && state.engine.llm_enabled ? '已接入 · ' + esc(state.engine.llm_model || '') : '未接入（离线规则引擎）') + '</b></div>' +
        (caps.length ? '<div class="fld"><span>引擎能力</span><b>' + esc(caps.map(function (c) { return c.label; }).join(' / ')) + '</b></div>' : '') +
      '</div>' +
      (state.engine && !state.engine.llm_enabled ?
        '<div class="hint-box" style="margin-top:12px">' + esc(state.engine.setup_hint || '') + '</div>' : '');

    $$('#wizBody .mode-card').forEach(function (c) {
      c.addEventListener('click', function () {
        wiz.mode = c.dataset.mode;
        $$('#wizBody .mode-card').forEach(function (x) { x.classList.toggle('on', x === c); });
      });
    });
  }

  /* 第 3 步：参数配置 */
  function renderWizStep3() {
    var ages = [
      { key: '4-8', e: '🧸', t: '4-8 岁', d: '亲子探索 · 图形与声音引导' },
      { key: '8-12', e: '🧭', t: '8-12 岁', d: '少年冒险 · 逻辑解谜' },
      { key: '12+', e: '🎭', t: '12 岁+', d: '沉浸剧本 · 多线叙事' }
    ];
    $('#wizBody').innerHTML =
      '<div class="wiz-h">第 3 步 · 参数配置</div>' +
      '<div class="wiz-sub">参数会作为 AI Story Engine 的生成约束，直接体现在世界观与任务判定难度上。</div>' +
      '<div class="age-grid mb16">' + ages.map(function (a) {
        return '<div class="age-card' + (wiz.ageBand === a.key ? ' on' : '') + '" data-age="' + a.key + '">' +
          '<div class="ac-e">' + a.e + '</div><b>' + a.t + '</b><span>' + a.d + '</span></div>';
      }).join('') + '</div>' +
      '<div class="grid g2">' +
        '<div>' +
          '<div class="fld2"><label>剧本标题</label><input id="wizTitle" value="' + esc(wiz.title) + '" placeholder="留空则由 AI 自动命名"></div>' +
          '<div class="fld2"><label>章节数</label><input id="wizChapters" type="number" min="1" max="8" value="' + wiz.chapters + '"></div>' +
          '<div class="fld2"><label>节点数</label><input id="wizNodes" type="number" min="2" max="24" value="' + wiz.nodes + '"></div>' +
        '</div>' +
        '<div><div class="fld2"><label>剧情风格</label>' +
          '<textarea id="wizStyle" rows="8">' + esc(wiz.style) + '</textarea></div></div>' +
      '</div>' +
      '<div class="res-box" style="margin-top:4px"><h5>本次生成参数预览</h5>' +
        '<div class="fld"><span>景区</span><b>' + esc(currentParkName()) + '</b></div>' +
        '<div class="fld"><span>模式</span><b>' + esc(MODE_LABEL[wiz.mode]) + '</b></div>' +
        '<div class="fld"><span>年龄层</span><b>' + esc(AGE_LABEL[wiz.ageBand]) + '</b></div>' +
        '<div class="fld"><span>规模</span><b>' + wiz.chapters + ' 章 / ' + wiz.nodes + ' 节点</b></div>' +
      '</div>';

    $$('#wizBody .age-card').forEach(function (c) {
      c.addEventListener('click', function () {
        syncWizParams();
        wiz.ageBand = c.dataset.age;
        renderWizStep3();
        renderWizFoot();
      });
    });
    ['wizTitle', 'wizChapters', 'wizNodes', 'wizStyle'].forEach(function (id) {
      var el = $('#' + id);
      if (el) el.addEventListener('change', syncWizParams);
      if (el) el.addEventListener('input', syncWizParams);
    });
  }

  function syncWizParams() {
    var t = $('#wizTitle'), c = $('#wizChapters'), n = $('#wizNodes'), s = $('#wizStyle');
    if (t) wiz.title = t.value;
    if (c) wiz.chapters = clamp(c.value, 1, 8);
    if (n) wiz.nodes = clamp(n.value, 2, 24);
    if (s) wiz.style = s.value;
  }

  function currentParkName() {
    for (var i = 0; i < PARKS.length; i++) if (PARKS[i].id === wiz.parkId) return PARKS[i].name;
    return state.parkName;
  }

  /* 第 4 步：生成与结果 */
  function renderWizStep4() {
    var body = $('#wizBody');
    if (!wiz.result) {
      body.innerHTML =
        '<div class="wiz-h">第 4 步 · 生成结果</div>' +
        '<div class="wiz-sub">正在调用 <b style="color:var(--gold-l)">POST /api/admin/ai/generate</b> …</div>' +
        '<div class="gen-progress" id="genProgress">' + genProgressHTML(wiz.prog) + '</div>' +
        '<div id="wizResult"></div>';
      if (!wiz.busy) runWizardGenerate();
      return;
    }
    var d = wiz.result;
    body.innerHTML =
      '<div class="wiz-h">第 4 步 · 生成结果</div>' +
      '<div class="wiz-sub">引擎 <b style="color:var(--gold-l)">' + esc(d.engine || '—') + '</b> · 耗时 ' + nf(d.elapsed_ms) + ' ms · 状态 ' + esc(d.status || 'done') +
        (d.created_scenario_id ? ' · 已入库为草稿剧本 <b style="color:var(--gold-l)">#' + esc(d.created_scenario_id) + '</b>' : '') + '</div>' +
      '<div class="result-grid">' +
        (d.worldview ? '<div class="res-box"><h5>世界观</h5><p>' + esc(d.worldview) + '</p></div>' : '') +
        (d.chapters && d.chapters.length ? '<div class="res-box"><h5>章节列表（' + d.chapters.length + '）</h5>' + chapterListHTML(d.chapters) + '</div>' : '') +
        (d.nodes && d.nodes.length ? '<div class="res-box"><h5>剧情节点卡片流（' + d.nodes.length + '）</h5>' + nodesFlowHTML(d.nodes) + '</div>' : '') +
        (d.rewards && d.rewards.length ? '<div class="res-box"><h5>奖励体系（徽章）</h5>' + rewardsHTML(d.rewards) + '</div>' : '') +
        (d.sources && d.sources.length ? '<div class="res-box"><h5>引用素材来源（' + d.sources.length + '）</h5>' + sourcesHTML(d.sources) + '</div>' : '') +
        (d.notes ? '<div class="hint-box">' + esc(d.notes) + '</div>' : '') +
        (!d.chapters && !d.nodes && !d.rewards ? '<div class="hint-box">该模式仅返回部分字段（' + esc(MODE_LABEL[wiz.mode] || wiz.mode) + '），其余字段为 null。</div>' : '') +
      '</div>' +
      '<div class="draw-actions" style="margin-top:16px">' +
        '<button class="btn btn-gold" id="wizStore" style="flex:1;justify-content:center" type="button"' + (d.created_scenario_id ? '' : ' disabled') + '>' +
          (d.created_scenario_id ? '入库为草稿剧本（#' + esc(d.created_scenario_id) + '）→' : '未生成草稿剧本（仅 full 模式入库）') +
        '</button>' +
        '<button class="btn" id="wizAgain" type="button">重新生成</button>' +
      '</div>';

    var st = $('#wizStore');
    if (st) st.addEventListener('click', function () {
      if (!d.created_scenario_id) return;
      toast('已入库为草稿剧本 #' + d.created_scenario_id + '，正在打开剧情编辑器');
      state.prevRoute = 'scenarios';
      location.hash = '#editor?id=' + d.created_scenario_id;
    });
    var ag = $('#wizAgain');
    if (ag) ag.addEventListener('click', function () { wiz.result = null; wiz.prog = 0; runWizardGenerate(); });
  }

  function genProgressHTML(cur) {
    return GEN_STEPS.map(function (s, i) {
      var cls = i < cur ? 'done' : (i === cur ? 'cur' : '');
      var mark = i < cur ? '✓' : (i + 1);
      var stateText = i < cur ? '完成' : (i === cur ? '进行中…' : '等待');
      return '<div class="gp-row ' + cls + '"><div class="gp-d">' + mark + '</div>' +
        '<div class="gp-t">' + esc(s) + '</div><div class="gp-s">' + stateText + '</div></div>';
    }).join('');
  }

  function runWizardGenerate() {
    if (wiz.busy) return;
    wiz.busy = true;
    wiz.result = null;
    wiz.prog = 0;
    wiz.step = 4;
    renderWizard();          /* 立即切换到第 4 步（busy 状态下不会再触发本函数） */

    /* 分步骤进度动画 */
    var timer = setInterval(function () {
      if (wiz.prog < GEN_STEPS.length - 1) wiz.prog++;
      var gp = $('#genProgress');
      if (gp) gp.innerHTML = genProgressHTML(wiz.prog);
      var rows = $$('#genProgress .gp-row');
      if (rows[wiz.prog]) {
        var t = $('.gp-s', rows[wiz.prog]);
        if (t) t.textContent = '进行中…';
      }
    }, 420);

    var reqBody = {
      park_id: wiz.parkId,
      mode: wiz.mode,
      age_band: wiz.ageBand,
      style: wiz.style,
      scenario_title: wiz.title || (currentParkName() + ' · AI 生成剧本'),
      chapter_count: wiz.chapters,
      node_count: wiz.nodes
    };

    api('/ai/generate', { method: 'POST', body: reqBody }).then(function (d) {
      clearInterval(timer);
      wiz.prog = GEN_STEPS.length;
      var gp = $('#genProgress');
      if (gp) gp.innerHTML = genProgressHTML(wiz.prog);
      wiz.result = d;
      wiz.busy = false;
      toast('AI 生成完成 · ' + (d.engine || '—') + ' · ' + nf(d.elapsed_ms) + ' ms');
      renderWizard();
    }).catch(function (e) {
      clearInterval(timer);
      wiz.busy = false;
      var gp = $('#genProgress');
      if (gp) {
        gp.innerHTML = genProgressHTML(wiz.prog) +
          '<div class="state-box err" style="margin-top:14px"><span class="sb-ic">⚠️</span><b>生成失败</b><p>' + esc(e.message) + '</p>' +
          '<div class="sb-acts"><button class="btn btn-gold" id="wizRetry" type="button">重试</button>' +
          '<button class="btn" id="wizBackCfg" type="button">返回参数配置</button></div></div>';
        var r = $('#wizRetry');
        if (r) r.addEventListener('click', function () { wiz.prog = 0; runWizardGenerate(); });
        var b = $('#wizBackCfg');
        if (b) b.addEventListener('click', function () { wiz.step = 3; renderWizard(); });
      }
      toast('生成失败：' + e.message, 'err');
    });
  }

  /* ======================= 17. 顶栏 / 景区切换 / 搜索 ======================= */

  function updateSideFoot(total) {
    var sf = $('#sfPark');
    if (!sf) return;
    // 这里传入的是「剧本总数」，不是已上线数，文案需与之匹配
    var extra = total ? ' · 共 ' + nf(total) + ' 个剧本' : '';
    sf.innerHTML = '<b>' + esc(state.parkName) + '</b><br>景区版 v1.0' + extra;
  }

  function updateParkChrome() {
    var label = $('#parkSwitchLabel');
    if (label) {
      var short = state.parkName.split(' · ').pop() || state.parkName;
      label.textContent = short + '景区';
    }
    var menu = $('#parkMenu');
    if (menu) {
      menu.innerHTML = PARKS.map(function (p) {
        return '<div class="pm-i' + (p.id === state.parkId ? ' on' : '') + '" data-park="' + p.id + '">' +
          '🧭 ' + esc(p.name) + '<small>#' + p.id + '</small></div>';
      }).join('');
      $$('.pm-i', menu).forEach(function (it) {
        it.addEventListener('click', function (e) {
          e.stopPropagation();
          selectPark(num(it.dataset.park, 1));
        });
      });
    }
    updateSideFoot(state.data.scenarios && state.data.scenarios.summary ? state.data.scenarios.summary.total : null);
  }

  function selectPark(id) {
    state.parkId = id;
    for (var i = 0; i < PARKS.length; i++) if (PARKS[i].id === id) state.parkName = PARKS[i].name;
    updateParkChrome();
    var menu = $('#parkMenu');
    if (menu) menu.classList.remove('show');
    toast('已切换到景区：' + state.parkName);
    if (state.route === 'ai-wizard') { wiz.parkId = id; loadWizPark(); }
    else applyRoute(true);
  }

  function bindTopbar() {
    var chip = $('#parkSwitch');
    chip.addEventListener('click', function (e) {
      e.stopPropagation();
      $('#parkMenu').classList.toggle('show');
    });
    document.addEventListener('click', function () { $('#parkMenu').classList.remove('show'); });

    var search = $('#tbSearch');
    search.addEventListener('input', function () { state.search = search.value.trim(); applySearch(); });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        search.focus();
        search.select();
      }
    });
  }

  /* 当前页面表格前端过滤 */
  function applySearch() {
    var page = $('.page.active');
    if (!page) return;
    var kw = (state.search || '').toLowerCase();
    $$('table.tbl', page).forEach(function (tbl) {
      var shown = 0;
      $$('tbody tr', tbl).forEach(function (tr) {
        if (tr.classList.contains('no-match')) return;
        var hit = !kw || (tr.textContent || '').toLowerCase().indexOf(kw) !== -1;
        tr.style.display = hit ? '' : 'none';
        if (hit) shown++;
      });
      var old = $('tr.no-match', tbl);
      if (old && old.parentNode) old.parentNode.removeChild(old);
      if (kw && shown === 0) {
        var tr = document.createElement('tr');
        tr.className = 'no-match';
        tr.innerHTML = '<td colspan="8" class="muted" style="text-align:center;padding:22px">没有匹配「' + esc(kw) + '」的记录</td>';
        $('tbody', tbl).appendChild(tr);
      }
    });
  }

  /* ======================= 18. hash 路由 ======================= */

  var ROUTES = {
    dashboard: renderDashboard,
    scenarios: renderScenarios,
    editor: renderEditor,
    tasks: renderTasks,
    materials: renderMaterials,
    visitors: renderVisitors,
    iptoys: renderIptoys,
    analytics: renderAnalytics,
    observability: renderObservability,
    park: renderPark,
    'ai-wizard': renderWizard
  };

  function parseHash() {
    var raw = (location.hash || '').replace(/^#\/?/, '');
    if (!raw) return { route: '', params: {} };
    var parts = raw.split('?');
    var params = {};
    if (parts[1]) {
      parts[1].split('&').forEach(function (kv) {
        var p = kv.split('=');
        if (p[0]) params[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || '');
      });
    }
    return { route: parts[0].replace(/\/$/, ''), params: params };
  }

  function setTitle(route) {
    var t = TITLES[route] || ['游伴 AI 运营台', ''];
    $('#tbTitle').innerHTML = t[0].replace(' / ', '<span class="crumb-sep">/</span>') + '<small>' + esc(t[1]) + '</small>';
  }

  function applyRoute(keepSearch) {
    var parsed = parseHash();
    var route = ROUTES[parsed.route] ? parsed.route : 'dashboard';
    state.route = route;
    state.params = parsed.params || {};
    if (!keepSearch) {
      state.search = '';
      var si = $('#tbSearch');
      if (si) si.value = '';
    }

    var wizardEl = $('#wizard');
    if (route === 'ai-wizard') {
      wizardEl.classList.add('show');
      wizardEl.setAttribute('aria-hidden', 'false');
      $$('.nav-item').forEach(function (n) { n.classList.toggle('active', n.dataset.page === 'scenarios'); });
      setTitle('ai-wizard');
      renderWizard();
      return;
    }

    wizardEl.classList.remove('show');
    wizardEl.setAttribute('aria-hidden', 'true');

    /* 离开运行指标页时停止自动刷新定时器，避免后台持续请求 */
    if (route !== 'observability') {
      stopObsAuto();
      state.obsAuto = false;
      syncObsSwitch();
    }

    $$('.page').forEach(function (p) { p.classList.toggle('active', p.id === 'page-' + route); });
    $$('.nav-item').forEach(function (n) { n.classList.toggle('active', n.dataset.page === route); });
    setTitle(route);
    $('#content').scrollTop = 0;
    ROUTES[route](state.params);
    if (state.search) applySearch();
  }

  /* ======================= 19. 启动 ======================= */

  function boot() {
    /* 导航 */
    $$('.nav-item').forEach(function (el) {
      el.addEventListener('click', function () { location.hash = '#' + el.dataset.page; });
    });
    /* 顶栏与全局按钮 */
    bindTopbar();
    $('#btnWizard').addEventListener('click', openWizard);
    $('#btnAiWizard').addEventListener('click', openWizard);
    $('#btnNewScenario').addEventListener('click', openNewScenarioModal);
    $('#btnNewTask').addEventListener('click', openNewTaskModal);
    $('#btnUploadMaterial').addEventListener('click', openUploadModal);
    $('#btnNewEdition').addEventListener('click', openNewEditionModal);
    $('#btnSavePark').addEventListener('click', savePark);
    $('#btnPreview').addEventListener('click', previewScenario);
    $('#btnPublish').addEventListener('click', publishScenario);
    $('#wizClose').addEventListener('click', closeWizard);

    /* 运行指标：刷新 + 自动刷新开关 */
    var obsRefresh = $('#btnObsRefresh');
    if (obsRefresh) obsRefresh.addEventListener('click', renderObservability);
    var obsAuto = $('#obAuto');
    if (obsAuto) {
      obsAuto.addEventListener('click', toggleObsAuto);
      obsAuto.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleObsAuto(); }
      });
    }

    $('#btnExport').addEventListener('click', function () {
      var d = state.data.dashboard;
      if (!d) { toast('数据尚未加载完成', 'err'); return; }
      var rows = [['指标', '数值', '单位', '环比']];
      (d.kpis || []).forEach(function (k) { rows.push([k.label, k.value, k.unit || '', (k.delta || '') + '%']); });
      (d.hot_nodes || []).forEach(function (h) { rows.push(['热度榜 #' + h.rank, h.name, h.value, h.kind_label || '']); });
      downloadCSV('游伴AI_数据看板_' + (d.date_label || '') + '.csv', rows);
      toast('报表已导出（CSV）');
    });
    $('#btnExportVisitors').addEventListener('click', function () {
      var d = state.data.visitors;
      if (!d) { toast('游客数据尚未加载完成', 'err'); return; }
      var rows = [['游客/家庭', '城市', '游玩剧本', '等级', '成长值', '最近游玩', '状态']];
      (d.items || []).forEach(function (v) { rows.push([v.name, v.city, v.scenario_title, 'Lv.' + v.level, v.growth_total, v.last_play, v.status_label]); });
      downloadCSV('游伴AI_游客名单.csv', rows);
      toast('名单已导出（CSV）');
    });

    /* 引擎状态（顶栏向导徽章用） */
    loadEngine().then(function () {
      if (state.route === 'ai-wizard') renderWizard();
    });

    /* 景区信息（侧栏 / 切换器） */
    api('/park' + qs({ park_id: state.parkId })).then(function (d) {
      if (d && d.park) {
        state.parkName = d.park.name || state.parkName;
        updateParkChrome();
      }
    }).catch(function () { updateParkChrome(); });

    window.addEventListener('hashchange', function () { applyRoute(); });
    if (!location.hash) location.hash = '#dashboard';
    else applyRoute();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

})();
