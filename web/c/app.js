/* ============================================================================
 * 游伴 AI (YOUBAN AI) · C 端 H5 应用逻辑
 * 契约来源：docs/API.md（唯一前后端契约，不臆造接口）
 * 纯原生 JS，无构建、无依赖、完全离线可用
 * ========================================================================== */
(function () {
  'use strict';

  /* ======================= 0. 常量与字典 ======================= */

  var API = '';                                   // 同源，使用相对路径 /api/...
  var LS = {
    user: 'youban_user_id',
    device: 'youban_device_nick',
    family: 'youban_family_name'
  };
  var DEMO_USER = 1;
  var DEMO_CODE = 'YB-XA-2026-0001';
  var DEFAULT_GEO = { lat: 34.2186, lng: 108.9644 };   // 大雁塔附近坐标

  var DIM_LABEL = { explore: '探索', create: '创造', observe: '观察', knowledge: '知识', courage: '勇气' };
  var TYPE_CLASS = { observe: 't-observe', find: 't-find', photo: 't-photo', solve: 't-solve' };
  var TYPE_EMOJI = { observe: '👀', find: '🔍', photo: '📷', solve: '🧩' };
  var KIND_LABEL = { entry: 'ENTRY · 入口', main: 'STORY NODE · 主线剧情', branch: 'BRANCH · 支线剧情', reward: 'REWARD · 奖励结算' };
  var VERIFY_LABEL = { auto: '到达即完成', answer: '选择或填写答案', keyword: '关键词判定', photo: '拍照记录' };
  var QUICK_ICON = {
    chat: '<path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.5 9 9 0 0 1-3.9-.9L3 21l1.9-5.1A8.4 8.4 0 0 1 4 11.5 8.4 8.4 0 0 1 12.5 3 8.4 8.4 0 0 1 21 11.5z"/>',
    task: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    badge: '<circle cx="12" cy="8" r="6"/><path d="M15.5 13.5 17 22l-5-3-5 3 1.5-8.5"/>',
    dress: '<path d="M20.4 14.5 16 10 5.6 20.4a2 2 0 0 0 2.8 2.8z"/><path d="M6 2 4 6l4 2 3-3-2-4z"/><path d="M10 8.5 15.5 3"/>'
  };
  var ENTRY_ICON = {
    map: '<circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 0 0-8 8c0 5.4 8 12 8 12s8-6.6 8-12a8 8 0 0 0-8-8z"/>',
    fav: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l8.8 8.8 8.8-8.8a5.5 5.5 0 0 0 0-7.8z"/>',
    honor: '<circle cx="12" cy="8" r="6"/><path d="M15.5 13.5 17 22l-5-3-5 3 1.5-8.5"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    parent: '<path d="M12 3l7.5 3v5.5c0 4.6-3.1 7.8-7.5 9.5-4.4-1.7-7.5-4.9-7.5-9.5V6z"/><path d="M9 12.2l2.1 2.1L15.2 10"/>'
  };
  /* 徽章稀有度文案（schema: common/rare/legend） */
  var RARITY_LABEL = { common: '常见', rare: '稀有', legend: '传说' };

  /* ======================= 1. 全局状态 ======================= */

  var S = {
    userId: null,
    deviceNick: '阿游',
    familyName: '小小探险家',
    tab: 'home',
    geo: { lat: DEFAULT_GEO.lat, lng: DEFAULT_GEO.lng },
    /* 缓存 */
    home: null,
    explore: null,
    mine: null,
    story: null,
    scenarioId: 1,
    /* 节点 → 任务 映射（契约未提供 node→task 直查，由剧本/对话/定位三处汇总） */
    nodeTaskMap: {},
    nodeNameMap: {},
    nodeKindMap: {},
    nodeStoryMap: {},
    /* 对话 */
    chat: [],
    chatInited: false,
    suggestions: [],
    /* 节点页 */
    task: null,
    taskNodeId: null,
    photoNote: '',
    pickedOption: '',
    doneCount: 0,
    busy: false,          // 防重复提交
    submitting: false,
    inflight: {},         // 并发去重：同一资源只发一次请求
    /* 家长模式（成长报告） */
    parent: null,         // { summary, reports, reportsOk, reportsError }
    parentView: 'summary', // summary 概览 / report 单次报告
    parentScenarioId: null
  };

  /* ======================= 2. 小工具 ======================= */

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function nowTime() {
    var d = new Date();
    var p = function (n) { return n < 10 ? '0' + n : '' + n; };
    return p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function num(v, dft) {
    var n = Number(v);
    return isFinite(n) ? n : (dft || 0);
  }

  function clampPct(v) { return Math.max(0, Math.min(100, num(v, 0))); }

  /** 距离显示：米 / 公里 */
  function distLabel(m) {
    var n = num(m, 0);
    return n >= 1000 ? (n / 1000).toFixed(1) + 'km' : n + 'm';
  }

  /* 全局 Toast：成功金色 / 错误橙色 */
  function toast(msg, kind) {
    var wrap = $('#toast-wrap');
    if (!wrap) return;
    var t = document.createElement('div');
    t.className = 'toast' + (kind === 'err' ? ' err' : '');
    t.textContent = msg;
    wrap.appendChild(t);
    setTimeout(function () {
      t.classList.add('out');
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 320);
    }, kind === 'err' ? 2600 : 2000);
  }

  /* 全屏 loading（金色脉冲） */
  var loadingCount = 0;
  function showLoading(text) {
    loadingCount++;
    $('#loadingText').textContent = text || '正在连接阿游…';
    $('#loading').classList.add('show');
  }
  function hideLoading() {
    loadingCount = Math.max(0, loadingCount - 1);
    if (loadingCount === 0) $('#loading').classList.remove('show');
  }

  /* ======================= 3. 网络层 ======================= */

  function api(path, opts) {
    opts = opts || {};
    var url = API + path;
    if (opts.query) {
      var qs = [];
      Object.keys(opts.query).forEach(function (k) {
        var v = opts.query[k];
        if (v !== undefined && v !== null && v !== '') qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
      });
      if (qs.length) url += (url.indexOf('?') >= 0 ? '&' : '?') + qs.join('&');
    }
    var init = { method: opts.method || 'GET', headers: {} };
    if (opts.body) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    return fetch(url, init).then(function (res) {
      return res.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        if (!res.ok || (data && data.ok === false)) {
          var msg = (data && data.error) || ('服务暂时不可用（HTTP ' + res.status + '）');
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        }
        if (data === null) throw new Error('返回数据格式异常，请稍后重试');
        return data;
      });
    }, function () {
      throw new Error('无法连接服务，请检查后端是否已启动');
    });
  }

  /* ======================= 4. 通用视图状态 ======================= */

  /** 并发去重：同一 key 的请求在飞时复用同一个 Promise */
  function once(key, fn) {
    if (S.inflight[key]) return S.inflight[key];
    var p = fn().then(function (r) {
      delete S.inflight[key];
      return r;
    }, function (e) {
      delete S.inflight[key];
      throw e;
    });
    S.inflight[key] = p;
    return p;
  }

  function skeletonHTML(kind) {
    if (kind === 'home') {
      return '<div class="sk sk-hero"></div><div class="sk sk-card"></div><div class="sk sk-row">' +
        '<div class="sk"></div><div class="sk"></div><div class="sk"></div><div class="sk"></div></div>' +
        '<div class="sk sk-card"></div><div class="sk sk-card"></div>';
    }
    if (kind === 'mine') {
      return '<div class="sk sk-card" style="height:104px"></div><div class="sk sk-card" style="height:78px"></div>' +
        '<div class="sk sk-card" style="height:180px"></div><div class="sk sk-card" style="height:200px"></div>';
    }
    if (kind === 'parent') {
      return '<div class="sk sk-card" style="height:132px"></div>' +
        '<div class="sk sk-card" style="height:64px"></div>' +
        '<div class="sk sk-row"><div class="sk"></div><div class="sk"></div><div class="sk"></div></div>' +
        '<div class="sk sk-card" style="height:150px"></div>' +
        '<div class="sk sk-card" style="height:120px"></div>';
    }
    return '<div class="sk sk-card" style="height:120px"></div><div class="sk sk-card"></div>' +
      '<div class="sk sk-card"></div><div class="sk sk-card"></div>';
  }

  function errorHTML(message) {
    return '<div class="err-box">' +
      '<div class="e-ic">🧭</div>' +
      '<b>阿游暂时联系不上</b>' +
      '<p>' + esc(message || '网络异常') + '</p>' +
      '<button class="btn-ghost btn-sm" data-retry>重试</button>' +
      '</div>';
  }

  /** 带骨架 + 错误重试的视图装载 */
  function withView(box, kind, loader, painter) {
    box.innerHTML = skeletonHTML(kind);
    return loader().then(function (data) {
      painter(data);
    }).catch(function (err) {
      box.innerHTML = errorHTML(err && err.message);
      var btn = $('[data-retry]', box);
      if (btn) btn.addEventListener('click', function () { withView(box, kind, loader, painter); });
    });
  }

  /* ======================= 5. 数据装载 ======================= */

  function loadHome(force) {
    if (S.home && !force) return Promise.resolve(S.home);
    return once('home', function () {
      return api('/api/c/home', { query: { user_id: S.userId, lat: S.geo.lat, lng: S.geo.lng } })
        .then(function (d) {
          S.home = d;
          if (d.location && num(d.location.lat, 0) && num(d.location.lng, 0)) {
            S.geo = { lat: d.location.lat, lng: d.location.lng };
          }
          if (d.device && d.device.nickname) S.deviceNick = d.device.nickname;
          return d;
        });
    });
  }

  function loadExplore(force) {
    if (S.explore && !force) return Promise.resolve(S.explore);
    return once('explore', function () {
      return api('/api/c/explore', { query: { user_id: S.userId } }).then(function (d) { S.explore = d; return d; });
    });
  }

  function loadMine(force) {
    if (S.mine && !force) return Promise.resolve(S.mine);
    return once('mine', function () {
      return api('/api/c/mine', { query: { user_id: S.userId } }).then(function (d) { S.mine = d; return d; });
    });
  }

  function loadStory(force) {
    if (S.story && !force) return Promise.resolve(S.story);
    return once('story:' + S.scenarioId, function () {
      return api('/api/c/scenario/' + S.scenarioId, { query: { user_id: S.userId } }).then(function (d) {
        S.story = d;
        buildNodeMaps(d);
        return d;
      });
    });
  }

  /** 从剧本详情里汇总 节点→任务 / 节点名 / 节点类型 映射 */
  function buildNodeMaps(story) {
    if (!story || !story.chapters) return;
    story.chapters.forEach(function (ch) {
      (ch.nodes || []).forEach(function (nd) {
        if (!nd || nd.id === undefined) return;
        S.nodeNameMap[nd.id] = nd.name || ('节点 ' + nd.id);
        S.nodeKindMap[nd.id] = nd.type_label || KIND_LABEL[nd.kind] || 'STORY NODE';
        if (nd.current_task && (nd.current_task.id || nd.current_task.id === 0)) {
          S.nodeTaskMap[nd.id] = nd.current_task.id;
        }
      });
    });
  }

  function invalidate() {
    S.home = null; S.explore = null; S.mine = null; S.story = null; S.parent = null;
  }

  /* ======================= 12.5 家长模式数据装载 ======================= */

  /** 家长概览 + 报告列表（报告列表失败不拖垮整页，单独给出重试） */
  function loadParent(force) {
    if (S.parent && !force) return Promise.resolve(S.parent);
    return once('parent', function () {
      return Promise.all([
        api('/api/c/parent/summary', { query: { user_id: S.userId } }),
        api('/api/c/parent/reports', { query: { user_id: S.userId } }).then(function (d) {
          return { items: (d && d.items) || [], ok: true, error: '' };
        }, function (err) {
          return { items: [], ok: false, error: (err && err.message) || '报告列表加载失败' };
        })
      ]).then(function (r) {
        S.parent = {
          summary: r[0] || {},
          reports: r[1].items,
          reportsOk: r[1].ok,
          reportsError: r[1].error
        };
        return S.parent;
      });
    });
  }

  /* ======================= 6. 开箱激活引导 ======================= */

  function showOnboard() {
    $('#onboard').classList.remove('hide');
    $('#obStart').disabled = false;
    $('#obStart').textContent = '开始冒险 →';
  }

  function hideOnboard() {
    $('#onboard').classList.add('hide');
  }

  function doActivate() {
    var name = $('#obName').value.trim() || '阿游';
    var code = $('#obCode').value.trim() || DEMO_CODE;
    if (name.length > 8) name = name.slice(0, 8);
    if (!code) { toast('请先输入潮玩上的激活码', 'err'); return; }

    var btn = $('#obStart');
    btn.disabled = true;
    btn.textContent = '激活中…';
    showLoading('正在唤醒你的潮玩伙伴…');

    api('/api/c/activate', {
      method: 'POST',
      body: { code: code, nickname: name, family_name: S.familyName }
    }).then(function (res) {
      hideLoading();
      var uid = res && res.user && res.user.id;
      if (!uid) throw new Error('激活返回数据异常，请稍后重试');
      S.userId = uid;
      S.deviceNick = (res.device && res.device.nickname) || name;
      S.familyName = (res.user && res.user.family_name) || S.familyName;
      try {
        localStorage.setItem(LS.user, String(uid));
        localStorage.setItem(LS.device, S.deviceNick);
        localStorage.setItem(LS.family, S.familyName);
      } catch (e) { /* 隐私模式下忽略 */ }

      invalidate();
      S.chat = []; S.chatInited = false; S.nodeTaskMap = {}; S.nodeStoryMap = {};
      hideOnboard();
      toast('激活成功 · ' + S.deviceNick + ' 已上线 ✨');
      if (res.greeting) setTimeout(function () { toast(res.greeting); }, 900);
      go('home');
      preload();
    }).catch(function (err) {
      hideLoading();
      btn.disabled = false;
      btn.textContent = '开始冒险 →';
      toast(err.message || '激活失败，请稍后重试', 'err');
    });
  }

  function skipOnboard() {
    S.userId = DEMO_USER;
    try { localStorage.setItem(LS.user, String(DEMO_USER)); } catch (e) { }
    hideOnboard();
    toast('已进入演示模式 · 数据来自示例账号');
    invalidate();
    go('home');
    preload();
  }

  /** 重置本地体验（我的 → 设置） */
  function resetLocal() {
    try { localStorage.removeItem(LS.user); } catch (e) { }
    S.userId = null;
    S.home = S.explore = S.mine = S.story = null;
    S.parent = null; S.parentView = 'summary'; S.parentScenarioId = null;
    S.chat = []; S.chatInited = false;
    S.nodeTaskMap = {}; S.nodeNameMap = {}; S.nodeKindMap = {}; S.nodeStoryMap = {};
    $('#view-home').innerHTML = '';
    $('#view-explore').innerHTML = '';
    $('#view-chat').innerHTML = '';
    $('#view-story').innerHTML = '';
    $('#view-mine').innerHTML = '';
    $('#parentBody').innerHTML = '';
    closeNode();
    closeParent();
    closeDrawer();
    showOnboard();
    toast('已重置本地体验，可重新开箱激活');
  }

  /** 首屏后台预热：把剧本里的 节点→任务 映射准备好 */
  function preload() {
    loadHome().then(function (h) {
      var sid = h && h.today_adventure && h.today_adventure.scenario_id;
      if (sid) { S.scenarioId = sid; }
      return loadStory();
    }).catch(function () { /* 静默失败，各页面自会提示 */ });
  }

  /* ======================= 7. Tab 路由 ======================= */

  function go(tab) {
    S.tab = tab;
    $$('.screen').forEach(function (s) { s.classList.toggle('active', s.dataset.tab === tab); });
    $$('.tab').forEach(function (t) { t.classList.toggle('active', t.dataset.tab === tab); });
    var input = $('#chatInput');
    if (tab === 'chat') { input.removeAttribute('hidden'); input.classList.add('show'); }
    else { input.setAttribute('hidden', ''); input.classList.remove('show'); }
    var el = $('#s-' + tab);
    if (el) el.scrollTop = 0;
    if (!S.userId) { showOnboard(); return; }
    ensureTab(tab);
  }

  function ensureTab(tab, force) {
    if (tab === 'home') return renderHome(force);
    if (tab === 'explore') return renderExplore(force);
    if (tab === 'chat') return chatInit(force);
    if (tab === 'story') return renderStory(force);
    if (tab === 'mine') return renderMine(force);
  }

  /* ======================= 8. Tab1 · 旅伴首页 ======================= */

  function renderHome(force) {
    var box = $('#view-home');
    if (S.home && !force) { paintHome(S.home); return Promise.resolve(); }
    return withView(box, 'home', function () { return loadHome(force); }, paintHome);
  }

  function paintHome(d) {
    var box = $('#view-home');
    var user = d.user || {};
    var dev = d.device || {};
    var loc = d.location || {};
    var adv = d.today_adventure || {};
    var nodes = d.nearby_nodes || [];
    var acts = d.quick_actions || [];

    var html = '';

    /* 定位卡片 */
    html += '<div class="hero-top">' +
      '<div class="loc"><span class="loc-dot"></span><div>' +
      '<b>' + esc(loc.name || '正在定位…') + '</b>' +
      '<i>' + esc([loc.weather, loc.tip].filter(Boolean).join(' · ') || '准备出发') + '</i>' +
      '</div></div>' +
      '<div class="ic-btn" id="homeBell" role="button" aria-label="消息"><svg class="ic" viewBox="0 0 24 24">' +
      '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>' +
      '<span class="dot"></span></div>' +
      '</div>';

    /* 发光角色 + 气泡 */
    html += '<div class="mascot-wrap">' +
      '<div class="halo"></div><div class="halo-2"></div>' +
      '<div class="mascot"><span class="m-glint"></span><span class="m-emoji">' + esc(dev.emoji || user.avatar || '🧭') + '</span></div>' +
      '<div class="speech">' + esc(d.speech || '嗨！今天我们去哪儿冒险？') + '</div>' +
      '</div>';

    /* 名字徽章 + 状态药丸 */
    html += '<div class="name-badge"><b>' + esc(dev.nickname || S.deviceNick) + '</b>' +
      '<span class="lv">Lv.' + num(user.level, 1) + ' ' + esc(user.level_name || '初识伙伴') + '</span></div>';
    if (d.status_pill) html += '<div class="status-pill">' + esc(d.status_pill) + '</div>';

    /* 今日冒险
       第三段优先显示节点「所在地点」（如「大雁塔」）而不是节点名：
       第 3 章的章节名与节点名可能同名（都叫「密令现世」），
       显示地点既能避免重复，也更贴近原型的「第 3 章 · 密令现世 · 大雁塔」。 */
    var advTail = adv.node_place || adv.node_name || '';
    html += '<div class="sec"><div class="main-card">' +
      '<div class="mc-tag">今日冒险</div>' +
      '<div class="mc-title">' + esc(adv.title || '等待开启') + '</div>' +
      '<div class="mc-sub">第 ' + num(adv.chapter_idx, 1) + ' 章 · ' + esc(adv.chapter_title || '序章') +
      (advTail ? ' · ' + esc(advTail) : '') + '</div>' +
      '<div class="prog"><i style="width:' + clampPct(adv.percent) + '%"></i></div>' +
      '<div class="prog-row"><span>已探索 ' + num(adv.done_nodes) + '/' + num(adv.total_nodes) + ' 剧情点</span>' +
      '<span>' + clampPct(adv.percent) + '%</span></div>' +
      '<button class="btn-gold" id="homeContinue">' + (num(adv.percent) > 0 ? '继续冒险 →' : '开启冒险 →') + '</button>' +
      '</div></div>';

    /* 4 个快捷入口 */
    html += '<div class="sec"><div class="quick">';
    (acts.length ? acts : [
      { key: 'chat', label: 'AI对话' }, { key: 'task', label: '任务' },
      { key: 'badge', label: '徽章' }, { key: 'dress', label: '换装' }
    ]).forEach(function (a) {
      html += '<div class="qi" data-quick="' + esc(a.key) + '">' +
        '<div class="qi-ic"><svg class="ic" viewBox="0 0 24 24">' + (QUICK_ICON[a.key] || QUICK_ICON.chat) + '</svg></div>' +
        '<small>' + esc(a.label) + '</small></div>';
    });
    html += '</div></div>';

    /* 附近故事点 */
    html += '<div class="sec"><div class="sec-title"><b>附近的故事点</b><span>' + nodes.length + ' 个 ›</span></div>';
    if (!nodes.length) {
      html += '<div class="empty-note">附近暂时没有故事点<br>走到景区里，故事会自己找上你 🌿</div>';
    } else {
      nodes.forEach(function (n) {
        html += '<div class="sp-item" data-node="' + esc(n.node_id) + '">' +
          '<div class="sp-cover">' + esc(n.emoji || '🗺️') + '</div>' +
          '<div class="sp-body"><b>' + esc(n.name) + '</b><p>' +
          esc([n.kind_label, n.desc].filter(Boolean).join(' · ')) + '</p></div>' +
          '<div class="sp-dist">' + distLabel(n.distance_m) + '</div></div>';
      });
    }
    html += '</div>';

    /* 徽章进度提示 */
    if (d.badge_total) {
      html += '<div class="sec"><div class="card card-pad" style="display:flex;align-items:center;gap:12px;cursor:pointer" data-go-mine>' +
        '<div style="font-size:22px">🏅</div>' +
        '<div style="flex:1"><b style="font-size:13px;color:#fff">已收集 ' + num(d.badge_count) + ' / ' + num(d.badge_total) + ' 枚徽章</b>' +
        '<div class="bar-mini" style="margin-top:8px"><i style="width:' +
        clampPct(num(d.badge_count) / Math.max(1, num(d.badge_total)) * 100) + '%"></i></div></div>' +
        '<span style="color:var(--sub);font-size:16px">›</span></div></div>';
    }

    box.innerHTML = html;

    /* 交互绑定 */
    var bell = $('#homeBell');
    if (bell) bell.addEventListener('click', function () {
      toast(d.status_pill || '阿游正在你身边陪伴中 ✨');
    });
    var cont = $('#homeContinue');
    if (cont) cont.addEventListener('click', function () { go('story'); });
    $$('[data-quick]', box).forEach(function (el) {
      el.addEventListener('click', function () { quickAction(el.dataset.quick); });
    });
    $$('[data-node]', box).forEach(function (el) {
      el.addEventListener('click', function () { openNodeById(num(el.dataset.node), el); });
    });
    var toMine = $('[data-go-mine]', box);
    if (toMine) toMine.addEventListener('click', function () { go('mine'); });
  }

  function quickAction(key) {
    if (key === 'chat') return go('chat');
    if (key === 'badge') return go('mine');
    if (key === 'dress') return openDrawer();
    if (key === 'task') {
      /* 任务 → 打开当前进行中的任务节点 */
      return loadStory().then(function (st) {
        var target = findActiveTask(st);
        if (target) openTask(target.task_id, target.node_id);
        else { toast('当前没有进行中的任务，去剧本里看看 📖'); go('story'); }
      }).catch(function (err) { toast(err.message, 'err'); });
    }
    go('home');
  }

  /** 从剧本详情里找「进行中的任务」 */
  function findActiveTask(story) {
    if (!story || !story.chapters) return null;
    var now = null;
    story.chapters.forEach(function (ch) {
      if (ch.state === 'now') now = now || ch;
    });
    var pool = now ? [now] : story.chapters;
    for (var i = 0; i < pool.length; i++) {
      var nodes = pool[i].nodes || [];
      for (var j = 0; j < nodes.length; j++) {
        var nd = nodes[j];
        if (nd.current_task && nd.current_task.id) return { task_id: nd.current_task.id, node_id: nd.id };
      }
    }
    return null;
  }

  /** 首页/对话里的故事点 → 节点页（缺 task 时用定位触发兜底） */
  function openNodeById(nodeId, el) {
    var taskId = S.nodeTaskMap[nodeId];
    if (taskId) return openTask(taskId, nodeId);
    /* 契约未提供 node→task 直查，先用剧本详情再补一次，最后用位置上报触发 */
    loadStory().then(function () {
      if (S.nodeTaskMap[nodeId]) return openTask(S.nodeTaskMap[nodeId], nodeId);
      toast('正在感知这个位置的剧情…');
      return locateFlow(true).then(function (triggered) {
        var hit = (triggered || []).filter(function (t) { return num(t.node_id) === num(nodeId) && t.task; })[0];
        if (hit) return openTask(hit.task.id, hit.node_id);
        toast('这里的故事还没开启，先去附近走走 🌿');
      });
    }).catch(function (err) {
      toast(err.message, 'err');
      if (el) toast('该故事点暂时无法开启', 'err');
    });
  }

  /* ======================= 9. Tab2 · 探索故事地图 ======================= */

  function renderExplore(force) {
    var box = $('#view-explore');
    if (S.explore && !force) { paintExplore(S.explore); return Promise.resolve(); }
    return withView(box, 'explore', function () { return loadExplore(force); }, paintExplore);
  }

  function paintExplore(d) {
    var box = $('#view-explore');
    var st = d.stats || {};
    var nodes = (d.nodes || []).slice();
    var cities = d.cities || [];
    var total = num(st.total_cities, nodes.length || 1);
    var lit = num(st.lit_cities, 0);
    var pct = total ? lit / total : 0;
    var R = 24, C = 2 * Math.PI * R;              // 环形进度（SVG stroke-dasharray）
    var dash = (C * pct).toFixed(1) + ' ' + C.toFixed(1);

    var html = '';

    /* 顶部：标题 + 环形进度 */
    html += '<div class="ex-hero"><div class="ex-title">我的故事地图' +
      '<small>点亮每一座城市，收藏属于你的故事</small></div>' +
      '<div class="ex-ring"><svg viewBox="0 0 60 60">' +
      '<circle cx="30" cy="30" r="24" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="4"/>' +
      '<circle class="trk" cx="30" cy="30" r="24" fill="none" stroke="#E8B45A" stroke-width="4" stroke-linecap="round" ' +
      'stroke-dasharray="' + dash + '"/></svg><span>' + lit + '/' + total + '</span></div></div>';

    /* 中国地图节点图：深色底 + 发光路径 + 百分比定位节点 */
    html += '<div class="ex-map">';
    html += '<svg class="map-grid" viewBox="0 0 100 100" preserveAspectRatio="none">' +
      '<defs><linearGradient id="gridFade" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0%" stop-color="rgba(232,180,90,.22)"/><stop offset="100%" stop-color="rgba(79,160,140,.06)"/>' +
      '</linearGradient></defs>' +
      '<g stroke="url(#gridFade)" stroke-width=".3" fill="none">' +
      '<path d="M0 22h100M0 44h100M0 66h100M0 88h100"/>' +
      '<path d="M18 0v100M42 0v100M66 0v100M88 0v100"/>' +
      '</g></svg>';

    /* 发光路径连线：按 x 坐标把已解锁节点串成一条旅行路线 */
    var line = nodes.slice().sort(function (a, b) { return num(a.x) - num(b.x); });
    if (line.length > 1) {
      var dAttr = line.map(function (n, i) {
        return (i === 0 ? 'M' : 'L') + num(n.x) + ' ' + num(n.y);
      }).join(' ');
      html += '<svg class="map-links" viewBox="0 0 100 100" preserveAspectRatio="none">' +
        '<defs><linearGradient id="linkGrad" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0%" stop-color="#4FA08C"/><stop offset="55%" stop-color="#E8B45A"/>' +
        '<stop offset="100%" stop-color="#F2CC84"/></linearGradient></defs>' +
        '<path d="' + dAttr + '" vector-effect="non-scaling-stroke"/></svg>';
    }
    html += '<div class="veil"></div>';

    nodes.forEach(function (n) {
      var cls = n.state === 'done' ? 'done' : (n.state === 'ongoing' ? 'now' : 'locked');
      var icon = n.state === 'locked' ? '🔒' : (n.emoji || '🗺️');
      html += '<div class="node ' + cls + '" style="left:' + num(n.x) + '%;top:' + num(n.y) + '%" ' +
        'data-city="' + esc(n.city) + '" data-state="' + esc(n.state) + '" ' +
        'data-tip="' + esc(n.tooltip || (n.city + ' · ' + (n.scenario || ''))) + '">' +
        '<div class="pin">' + esc(icon) + '</div><small>' + esc(n.city) + '</small></div>';
    });
    html += '<div class="map-label">CHINA STORY MAP</div>';
    html += '</div>';

    /* 三格统计 */
    html += '<div class="ex-stat">' +
      '<div><b>' + lit + '</b><span>点亮城市</span></div>' +
      '<div><b>' + num(st.badges) + '</b><span>收集徽章</span></div>' +
      '<div><b>' + num(st.stories_done) + '</b><span>完成故事</span></div>' +
      '</div>';

    /* 城市故事卡片 */
    html += '<div class="sec"><div class="sec-title"><b>城市故事</b><span>' + cities.length + ' 个 ›</span></div>';
    if (!cities.length) {
      html += '<div class="empty-note">还没有城市故事<br>激活潮玩后，从最近的景区开始吧 ✨</div>';
    } else {
      cities.forEach(function (c) {
        var pill = c.state === 'done' ? '<div class="pill-done">已完成</div>'
          : (c.state === 'ongoing' ? '<div class="pill-now">探索中</div>' : '<div class="pill-lock">未解锁</div>');
        var bar = (c.state === 'locked') ? '' :
          '<div class="bar-mini"><i style="width:' + clampPct(c.progress_percent) + '%"></i></div>';
        html += '<div class="city-card" data-scenario="' + esc(c.scenario_id) + '" data-state="' + esc(c.state) + '">' +
          '<div class="cc-emoji">' + esc(c.emoji || '🗺️') + '</div>' +
          '<div class="cc-b"><b>' + esc(c.city + ' · ' + c.title) + '</b><p>' + esc(c.tagline || '') + '</p>' + bar + '</div>' +
          pill + '</div>';
      });
    }
    html += '</div>';

    box.innerHTML = html;

    $$('.node', box).forEach(function (el) {
      el.addEventListener('click', function () {
        toast(el.dataset.tip || (el.dataset.city + ' · 故事点'));
        if (el.dataset.state === 'locked') return;
        var hit = cities.filter(function (c) { return c.city === el.dataset.city; })[0];
        if (hit && hit.scenario_id) openScenario(hit.scenario_id);
      });
    });
    $$('.city-card', box).forEach(function (el) {
      el.addEventListener('click', function () {
        if (el.dataset.state === 'locked') { toast('前往该城市即可开启故事 🌏'); return; }
        openScenario(num(el.dataset.scenario, S.scenarioId));
      });
    });
  }

  function openScenario(id) {
    S.scenarioId = num(id, 1);
    S.story = null;
    go('story');
  }

  /* ======================= 10. Tab3 · AI 对话 ======================= */

  function chatInit(force) {
    var box = $('#view-chat');
    if (S.chatInited && !force) { paintChat(); return Promise.resolve(); }
    box.innerHTML = '<div class="chat-head"><div class="ch-ava">🧭</div>' +
      '<div class="ch-b"><b>' + esc(S.deviceNick) + '</b><i>在线 · 正在感知你的位置</i></div>' +
      '<div class="ch-tag">AI 智慧陪伴</div></div><div class="chat-body"><div class="typing"><i></i><i></i><i></i></div></div>';
    return api('/api/c/chat', {
      method: 'POST',
      body: { user_id: S.userId, lat: S.geo.lat, lng: S.geo.lng }
    }).then(function (res) {
      S.chat = [];
      pushMessages(res.messages);
      if (res.quest_card) pushQuest(res.quest_card);
      S.suggestions = res.suggestions || [];
      S.chatInited = true;
      paintChat();
    }).catch(function (err) {
      box.innerHTML = errorHTML(err && err.message);
      var btn = $('[data-retry]', box);
      if (btn) btn.addEventListener('click', function () { chatInit(true); });
    });
  }

  function pushMessages(list) {
    (list || []).forEach(function (m) {
      if (!m || !m.text) return;
      S.chat.push({ role: m.role === 'me' ? 'me' : 'ai', text: m.text, tm: m.tm || nowTime() });
    });
  }

  function pushQuest(q) {
    if (!q) return;
    S.chat = S.chat.filter(function (m) { return m.role !== 'quest'; });
    S.chat.push({ role: 'quest', quest: q, tm: nowTime() });
  }

  function paintChat() {
    var box = $('#view-chat');
    var html = '<div class="chat-head"><div class="ch-ava">🧭</div>' +
      '<div class="ch-b"><b>' + esc(S.deviceNick) + '</b><i>在线 · 正在感知你的位置</i></div>' +
      '<div class="ch-tag">AI 智慧陪伴</div></div>';

    html += '<div class="chat-body">';
    if (!S.chat.length) {
      html += '<div class="msg ai">嗨！我是' + esc(S.deviceNick) + ' 👋 我们边走边聊吧，你走到哪里，故事就发生在哪里～</div>';
    }
    S.chat.forEach(function (m) {
      if (m.role === 'quest') {
        var q = m.quest || {};
        html += '<div class="msg-card">' +
          '<div class="mck">' + esc(q.kicker || 'NEW QUEST · 新任务') + '</div>' +
          '<div class="mct">' + esc(q.title || '') + '</div>' +
          '<div class="mcs">' + esc(q.desc || '') + '</div>' +
          '<div class="mcb" data-accept="' + esc(q.task_id) + '" data-accept-node="' + esc(q.node_id || '') + '">' +
          esc(q.cta || '接受任务 →') + '</div></div>';
      } else if (m.role === 'sys') {
        html += '<div class="msg sys">' + esc(m.text) + '</div>';
      } else {
        html += '<div class="msg ' + (m.role === 'me' ? 'me' : 'ai') + '">' + esc(m.text) +
          (m.role === 'me' ? '<span class="tm">' + esc(m.tm || '') + '</span>' : '') + '</div>';
      }
    });
    html += '</div>';

    /* 快捷建议 chips */
    html += '<div class="chips">';
    (S.suggestions || []).forEach(function (s) {
      html += '<div class="chip" data-sug="' + esc(s) + '">' + esc(s) + '</div>';
    });
    html += '<div class="chip ghost" id="chipLocate">📍 上报位置，触发剧情</div>';
    html += '</div>';

    box.innerHTML = html;

    $$('[data-sug]', box).forEach(function (el) {
      el.addEventListener('click', function () { sendChat(el.dataset.sug); });
    });
    var cl = $('#chipLocate');
    if (cl) cl.addEventListener('click', function () { locateFlow(false); });
    $$('[data-accept]', box).forEach(function (el) {
      el.addEventListener('click', function () {
        el.textContent = '已接受 ✓';
        el.classList.add('done');
        toast('任务已加入你的冒险清单');
        openTask(num(el.dataset.accept), num(el.dataset.acceptNode, 0));
      });
    });
    scrollChat();
  }

  function scrollChat() {
    var sc = $('#s-chat');
    if (sc) sc.scrollTop = sc.scrollHeight;
  }

  function sendChat(text) {
    text = (text || '').trim();
    if (!text) return;
    S.chat.push({ role: 'me', text: text, tm: nowTime() });
    paintChat();
    showTyping();
    api('/api/c/chat', {
      method: 'POST',
      body: { user_id: S.userId, text: text, lat: S.geo.lat, lng: S.geo.lng }
    }).then(function (res) {
      removeTyping();
      pushMessages(res.messages);
      if (res.quest_card) pushQuest(res.quest_card);
      if (res.suggestions && res.suggestions.length) S.suggestions = res.suggestions;
      paintChat();
    }).catch(function (err) {
      removeTyping();
      toast(err.message || '消息发送失败，请重试', 'err');
    });
  }

  function showTyping() {
    var body = $('.chat-body');
    if (!body || $('.typing', body)) return;
    var t = document.createElement('div');
    t.className = 'typing';
    t.innerHTML = '<i></i><i></i><i></i>';
    body.appendChild(t);
    scrollChat();
  }

  function removeTyping() {
    var t = $('.typing');
    if (t && t.parentNode) t.parentNode.removeChild(t);
  }

  /** 位置上报：POST /api/c/locate，把触发到的节点作为 AI 消息插入对话流 */
  function locateFlow(silent) {
    if (!S.userId) return Promise.resolve([]);
    if (!silent) showLoading('正在感知你的位置…');
    return api('/api/c/locate', {
      method: 'POST',
      body: { user_id: S.userId, lat: S.geo.lat, lng: S.geo.lng }
    }).then(function (res) {
      if (!silent) hideLoading();
      var triggered = res.triggered || [];
      var parkName = (res.park && res.park.name) || '当前位置';
      S.chat.push({ role: 'sys', text: '📍 位置已上报 · ' + parkName, tm: nowTime() });

      triggered.forEach(function (t) {
        if (S.nodeTaskMap[t.node_id] === undefined && t.task) S.nodeTaskMap[t.node_id] = t.task.id;
        if (t.node_id !== undefined) {
          S.nodeNameMap[t.node_id] = S.nodeNameMap[t.node_id] || t.name;
          S.nodeStoryMap[t.node_id] = t.story_text || S.nodeStoryMap[t.node_id] || '';
          S.nodeKindMap[t.node_id] = S.nodeKindMap[t.node_id] || (t.kind_label || KIND_LABEL[t.kind] || 'STORY NODE');
        }
        S.chat.push({
          role: 'ai',
          text: t.ai_dialog || t.story_text || ('你来到了「' + t.name + '」，这里有一段故事在等你 ✨'),
          tm: nowTime()
        });
        if (t.task) {
          pushQuest({
            kicker: 'NEW QUEST · ' + (t.kind_label || '故事点'),
            title: t.name,
            desc: (t.story_text ? t.story_text + '\n' : '') + '任务：' + t.task.title +
              (t.task.type_label ? '（' + t.task.type_label + '）' : ''),
            cta: '接受任务 →',
            task_id: t.task.id,
            node_id: t.node_id
          });
        }
      });

      if (!triggered.length) {
        var near = res.nearby || [];
        S.chat.push({
          role: 'ai',
          text: near.length
            ? ('附近还有 ' + near.length + ' 个故事点，最近的是「' + near[0].name + '」，大约 ' + distLabel(near[0].distance_m) + '，我们走过去看看？')
            : '附近暂时没有新的故事点，我们换个方向走一走吧 🌿',
          tm: nowTime()
        });
      }

      if (S.tab === 'chat') paintChat();
      else if (!silent) toast(triggered.length ? ('触发了 ' + triggered.length + ' 个故事点 🎉') : '附近暂无新剧情节点的');
      invalidate();
      return triggered;
    }).catch(function (err) {
      if (!silent) hideLoading();
      toast(err.message || '位置上报失败，请重试', 'err');
      return [];
    });
  }

  /* ======================= 11. Tab4 · 剧本 ======================= */

  function renderStory(force) {
    var box = $('#view-story');
    if (S.story && !force) { paintStory(S.story); return Promise.resolve(); }
    return withView(box, 'story', function () { return loadStory(force); }, paintStory);
  }

  function paintStory(d) {
    var box = $('#view-story');
    var chapters = d.chapters || [];
    var cnt = num(d.chapters_count, chapters.length);
    var cur = num(d.current_chapter, 0);
    var html = '';

    /* 封面区 */
    html += '<div class="story-top">' +
      '<div class="story-kicker">' + esc(d.kicker || ('AI 剧本游 · ' + (d.city || ''))) + '</div>' +
      '<div class="story-name">' + esc(d.title || '剧本') + '</div>' +
      '<div class="story-meta">' + esc(d.subtitle || '') + (d.meta ? '<br>' + esc(d.meta) : '') + '</div>' +
      '<div class="story-tags">' +
      '<span>' + esc(d.city || '') + '</span>' +
      '<span>' + esc(d.emoji || '🗺️') + '</span>' +
      '<span>' + esc(d.age_band || '') + ' · ' + esc(d.age_label || '') + '</span>' +
      '<span>进度 ' + clampPct(d.progress_percent) + '%</span>' +
      '</div><div class="chap-bar">';
    for (var i = 1; i <= Math.max(cnt, chapters.length, 1); i++) {
      var cls = i < cur ? 'on' : (i === cur ? 'cur' : '');
      html += '<i class="' + cls + '"></i>';
    }
    html += '</div></div>';

    /* 剧情进度时间轴 */
    html += '<div class="sec"><div class="sec-title"><b>剧情进度</b><span>第 ' + cur + ' / ' + cnt + ' 章</span></div><div class="path">';
    if (!chapters.length) {
      html += '<div class="empty-note">剧本章节正在生成中，稍后再来看看 📖</div>';
    }
    chapters.forEach(function (ch) {
      var state = ch.state === 'done' ? 'done' : (ch.state === 'now' ? 'now' : '');
      var dot = ch.state === 'done' ? '✓' : (ch.state === 'now' ? '▶' : num(ch.idx));
      html += '<div class="path-item ' + state + '" data-chapter="' + num(ch.idx) + '">' +
        '<div class="path-dot">' + dot + '</div>' +
        '<div class="path-body"><div class="pb-t"><b>第 ' + num(ch.idx) + ' 章 · ' + esc(ch.title) + '</b>' +
        (ch.state === 'now' ? '<span class="tag-now">进行中</span>' : '') + '</div>' +
        '<p>' + esc(ch.summary || '') + '</p>';

      var nodes = ch.nodes || [];
      if (nodes.length) {
        html += '<div class="path-nodes">';
        nodes.forEach(function (nd) {
          var st = nd.state === 'done' ? 'done' : (nd.state === 'active' ? 'active' : '');
          var go = (nd.current_task && nd.current_task.id) ? '<span class="pn-go">去完成 ›</span>'
            : '<span class="pn-go">' + esc(nd.desc || '') + '</span>';
          html += '<div class="path-node ' + st + '" data-task="' + esc(nd.current_task ? nd.current_task.id : '') +
            '" data-node-id="' + esc(nd.id) + '"><span class="pn-dot"></span>' +
            esc(nd.name) + go + '</div>';
        });
        html += '</div>';
      }

      if (ch.state === 'now') {
        var tk = null;
        (ch.nodes || []).forEach(function (nd) { if (!tk && nd.current_task) tk = nd.current_task; });
        if (tk) {
          html += '<div class="path-task">🔍 当前任务：' + esc(tk.title) +
            (tk.progress ? '（' + esc(tk.progress) + '）' : '') + '</div>';
        }
      }
      html += '</div></div>';
    });
    html += '</div></div>';

    html += '<div style="margin-top:2px"><button class="btn-gold" id="storyContinue">继续冒险 →</button></div>';
    box.innerHTML = html;

    /* 绑定：节点 → 节点页；章节 → 提示 */
    $$('.path-node', box).forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        var tid = num(el.dataset.task, 0);
        if (tid) openTask(tid, num(el.dataset.nodeId, 0));
        else toast('这个剧情点还没有任务，走到附近就会触发 📍');
      });
    });
    $$('.path-item', box).forEach(function (el) {
      el.addEventListener('click', function () {
        var idx = num(el.dataset.chapter);
        toast('第 ' + idx + ' 章 · ' + (el.querySelector('b') ? el.querySelector('b').textContent.replace('第 ' + idx + ' 章 · ', '') : ''));
      });
    });
    var btn = $('#storyContinue');
    if (btn) btn.addEventListener('click', function () {
      var target = findActiveTask(d);
      if (target) openTask(target.task_id, target.node_id);
      else toast('所有章节都完成啦，去新的城市开启下一段故事 🌏');
    });
  }

  /* ======================= 12. Tab5 · 我的 ======================= */

  function renderMine(force) {
    var box = $('#view-mine');
    if (S.mine && !force) { paintMine(S.mine); return Promise.resolve(); }
    return withView(box, 'mine', function () { return loadMine(force); }, paintMine);
  }

  function paintMine(d) {
    var box = $('#view-mine');
    var u = d.user || {};
    var growth = d.growth || [];
    var badges = d.badges || [];
    var bs = d.badge_stat || {};
    var toy = d.toy || {};
    var entries = d.entries || [];
    var html = '';

    /* 头像 + 昵称 + 等级 + 旅行统计 */
    html += '<div class="profile"><div class="ava">' + esc(u.avatar || '🧭') + '</div>' +
      '<div class="pf-b"><b>' + esc(u.nickname || S.familyName) +
      '<span class="lv2">Lv.' + num(u.level, 1) + ' ' + esc(u.level_name || '初识伙伴') + '</span></b>' +
      '<p>已旅行 ' + num(u.travel_days) + ' 天 · 走过 ' + num(u.cities) + ' 座城市 · ' +
      esc(toy.nickname || S.deviceNick) + ' 陪伴中 · 成长值 ' + num(u.growth_total) + '</p></div></div>';

    /* 成长五维度 */
    html += '<div class="sec"><div class="sec-title"><b>成长维度</b><span>共 ' + num(u.growth_total) + ' 成长值</span></div><div class="grow">';
    if (!growth.length) {
      html += '<div class="empty-note" style="grid-column:1/-1">完成第一个任务，成长值就会长出来 🌱</div>';
    }
    growth.forEach(function (g) {
      var label = g.label || DIM_LABEL[g.dim] || g.dim;
      html += '<div><b>' + num(g.value) + '</b><span>' + esc(label) + '</span>' +
        '<div class="bar-mini"><i style="width:' + clampPct(g.value) + '%"></i></div></div>';
    });
    html += '</div></div>';

    /* 家长入口提示条（成长维度区块附近） */
    html += '<div class="pr-hint" id="mineParentHint">' +
      '<span class="pr-hint-ic">👨‍👩‍👧</span>' +
      '<span>家长可查看成长报告</span>' +
      '<span class="pr-hint-go">›</span></div>';

    /* 徽章墙 */
    html += '<div class="sec"><div class="sec-title"><b>我的徽章</b><span>' +
      num(bs.got, badges.filter(function (b) { return b.got; }).length) + ' / ' +
      num(bs.total, badges.length) + '</span></div><div class="badges">';
    if (!badges.length) {
      html += '<div class="empty-note" style="grid-column:1/-1">徽章墙空空如也，去冒险解锁第一枚吧 🏅</div>';
    }
    badges.forEach(function (b) {
      html += '<div class="badge' + (b.got ? ' got' : '') + '" data-badge="' + esc(b.name) + '">' +
        '<div class="b-ic">' + esc(b.emoji || '🏅') + '</div><small>' + esc(b.name) + '</small></div>';
    });
    html += '</div></div>';

    /* 我的潮玩 */
    html += '<div class="sec"><div class="sec-title"><b>我的潮玩</b><span id="mineDress">换装 ›</span></div>' +
      '<div class="city-card" id="mineToy"><div class="cc-emoji">🧭</div>' +
      '<div class="cc-b"><b>' + esc(toy.nickname || S.deviceNick) + ' · ' + esc(toy.outfit || '默认装扮') + '</b>' +
      '<p>' + esc(toy.sku_name || '') + ' · 已解锁 ' + num(toy.outfits) + ' 套服装 · ' + num(toy.gear) + ' 件装备</p></div>' +
      '<div class="pill-done">更换</div></div></div>';

    /* 设置列表（家长模式入口插在「设置」之前） */
    html += '<div class="sec"><div class="mine-list">';
    mineEntries(entries).forEach(function (e) {
      html += '<div class="mine-row" data-entry="' + esc(e.key) + '">' +
        '<div class="mr-ic"><svg class="ic" style="width:17px;height:17px" viewBox="0 0 24 24">' +
        (ENTRY_ICON[e.key] || ENTRY_ICON.settings) + '</svg></div>' +
        '<span class="mr-t">' + esc(e.label) + '</span>' +
        (e.value ? '<div class="mr-val">' + esc(e.value) + '</div>' : '') +
        '<span class="arrow">›</span></div>';
    });
    html += '</div></div>';

    box.innerHTML = html;

    /* 交互 */
    var toyCard = $('#mineToy');
    if (toyCard) toyCard.addEventListener('click', function () { openDrawer(); });
    var dress = $('#mineDress');
    if (dress) dress.addEventListener('click', function () { openDrawer(); });
    var pHint = $('#mineParentHint');
    if (pHint) pHint.addEventListener('click', function () { openParent(); });
    $$('.badge', box).forEach(function (el) {
      el.addEventListener('click', function () {
        toast(el.classList.contains('got') ? ('已获得徽章「' + el.dataset.badge + '」✨') : ('「' + el.dataset.badge + '」尚未获得，继续冒险吧 🔒'));
      });
    });
    $$('.mine-row', box).forEach(function (el) {
      el.addEventListener('click', function () { mineEntry(el.dataset.entry, d); });
    });
  }

  /** 「我的」页设置列表：在「设置」之前插入「家长模式」（不改动后端返回的其他项） */
  function mineEntries(entries) {
    var base = (entries && entries.length) ? entries.slice() : [
      { key: 'map', label: '我的旅行地图', value: '' },
      { key: 'fav', label: '我的收藏', value: '' },
      { key: 'honor', label: '成就与称号', value: '' },
      { key: 'settings', label: '设置', value: '' }
    ];
    var exists = false;
    base.forEach(function (e) { if (e && e.key === 'parent') exists = true; });
    if (!exists) {
      var item = { key: 'parent', label: '家长模式', value: '成长报告' };
      var at = -1;
      base.forEach(function (e, i) { if (at < 0 && e && e.key === 'settings') at = i; });
      if (at >= 0) base.splice(at, 0, item);
      else base.push(item);
    }
    return base;
  }

  function mineEntry(key, data) {
    if (key === 'map') { go('explore'); return; }
    if (key === 'settings') { resetLocal(); return; }
    if (key === 'parent') { openParent(); return; }
    var v = '';
    (data.entries || []).forEach(function (e) { if (e.key === key) v = e.value; });
    if (key === 'fav') { toast('我的收藏 · ' + (v || '0 件') + '（演示数据）'); return; }
    if (key === 'honor') { toast('成就与称号 · ' + (v || 'Lv.1') + '（演示数据）'); return; }
    toast('功能演示 · 原型示意');
  }

  /* ======================= 13. 换装抽屉 ======================= */

  function openDrawer() {
    var mask = $('#drawerMask');
    mask.classList.add('show');
    var body = $('#drawerBody');
    body.innerHTML = skeletonHTML();
    api('/api/c/wardrobe', { query: { user_id: S.userId } }).then(function (d) {
      paintDrawer(d);
    }).catch(function (err) {
      body.innerHTML = errorHTML(err && err.message);
      var btn = $('[data-retry]', body);
      if (btn) btn.addEventListener('click', function () { openDrawer(); });
    });
  }

  function closeDrawer() { $('#drawerMask').classList.remove('show'); }

  function paintDrawer(d) {
    var body = $('#drawerBody');
    var items = d.items || [];
    var gear = d.gear || [];
    $('#drawerSub').textContent = '当前：' + (d.current || '默认装扮');

    var html = '<div class="sec-title" style="margin-bottom:11px"><b>城市服装</b><span>' +
      items.length + ' 套</span></div><div class="dress-grid">';
    if (!items.length) html += '<div class="empty-note" style="grid-column:1/-1">暂时没有可换的装扮</div>';
    items.forEach(function (it) {
      var on = it.name === d.current;
      var lock = !it.unlocked || !it.owned;
      html += '<div class="dress-item' + (on ? ' on' : '') + (lock ? ' lock' : '') + '" data-item="' + esc(it.id) + '" ' +
        'data-name="' + esc(it.name) + '" data-city="' + esc(it.city || '') + '" data-lock="' + (lock ? '1' : '0') + '">' +
        (lock ? '<span class="d-lock">🔒</span>' : '') +
        '<div class="d-ic">' + esc(it.emoji || '👕') + '</div>' +
        '<small>' + esc(it.name) + '</small>' +
        '<small style="color:var(--sub-2)">' + (on ? '穿着中' : esc(it.city || '')) + '</small></div>';
    });
    html += '</div>';

    html += '<div class="sec-title" style="margin-top:20px;margin-bottom:6px"><b>探险装备</b><span>' + gear.length + ' 件</span></div>';
    if (gear.length) {
      html += '<div class="gear-row">';
      gear.forEach(function (g) {
        html += '<span class="gear-pill">' + esc(g.emoji || '🎒') + ' ' + esc(g.name) + (g.unlocked ? '' : ' 🔒') + '</span>';
      });
      html += '</div>';
    } else {
      html += '<div class="empty-note">还没有装备，完成任务可以解锁探险装备 🎒</div>';
    }

    body.innerHTML = html;

    $$('.dress-item', body).forEach(function (el) {
      el.addEventListener('click', function () {
        if (el.dataset.lock === '1') { toast('这套装扮还未解锁，去对应的城市冒险吧 🌏'); return; }
        if (el.classList.contains('on')) { toast('已经穿着这套装扮啦 ✨'); return; }
        var id = num(el.dataset.item, 0);
        showLoading('正在为 ' + S.deviceNick + ' 换装…');
        api('/api/c/wardrobe/equip', { method: 'POST', body: { user_id: S.userId, item_id: id } })
          .then(function (res) {
            hideLoading();
            toast('换装成功 · ' + (res.current || '新装扮'));
            S.home = null; S.mine = null;
            var cur = res.current;
            $$('.dress-item', body).forEach(function (x) {
              var isOn = x.dataset.name === cur;
              x.classList.toggle('on', isOn);
              var subs = x.querySelectorAll('small');
              if (subs[1]) subs[1].textContent = isOn ? '穿着中' : (x.dataset.city || '');
            });
            $('#drawerSub').textContent = '当前：' + (cur || '');
            if (S.tab === 'mine') renderMine(true);
            if (S.tab === 'home') renderHome(true);
          })
          .catch(function (err) { hideLoading(); toast(err.message || '换装失败，请重试', 'err'); });
      });
    });
  }

  /* ======================= 14. 节点剧情页（扩展视图） ======================= */

  function openSubpage(sel) {
    $(sel).classList.add('show');
  }
  function closeSubpage(sel) {
    $(sel).classList.remove('show');
  }

  function openTask(taskId, nodeId) {
    if (!taskId) { toast('这个剧情点还没有任务', 'err'); return; }
    S.taskNodeId = num(nodeId, 0) || null;
    S.photoNote = '';
    S.pickedOption = '';
    openSubpage('#page-node');
    $('#nodeNavSub').textContent = 'STORY NODE';
    $('#nodeNavTitle').textContent = S.nodeNameMap[S.taskNodeId] || '剧情节点';
    var box = $('#nodeBody');
    box.innerHTML = skeletonHTML();
    box.scrollTop = 0;

    api('/api/c/task/' + taskId, { query: { user_id: S.userId } }).then(function (task) {
      S.task = task;
      S.doneCount = num(task.done_count, 0);
      paintTask(task);
    }).catch(function (err) {
      box.innerHTML = errorHTML(err && err.message);
      var btn = $('[data-retry]', box);
      if (btn) btn.addEventListener('click', function () { openTask(taskId, nodeId); });
    });
  }

  function closeNode() { closeSubpage('#page-node'); }

  function paintTask(t) {
    var box = $('#nodeBody');
    var nodeId = S.taskNodeId;
    var kindLabel = S.nodeKindMap[nodeId] || KIND_LABEL[t.kind] || 'STORY NODE';
    var coverEmoji = TYPE_EMOJI[t.type] || '🗺️';
    var storyText = S.nodeStoryMap[nodeId] ||
      ('阿游说：靠得越近，我越能感觉到「' + (S.nodeNameMap[nodeId] || t.title) + '」这里的风里藏着一段还没讲完的故事……你来帮我看看好吗？');

    $('#nodeNavSub').textContent = kindLabel;
    $('#nodeNavTitle').textContent = S.nodeNameMap[nodeId] || t.title || '剧情节点';

    var rp = t.reward_preview || {};
    var gains = rp.growth || {};
    var gainTxt = Object.keys(gains).map(function (k) {
      return '<em>' + esc(DIM_LABEL[k] || k) + ' +' + num(gains[k]) + '</em>';
    }).join(' · ');

    var html = '';
    html += '<div class="np-cover"><div class="np-lines"></div>' +
      '<div class="np-kind">' + esc(kindLabel) + '</div>' +
      '<div class="np-trigger">' + esc(t.trigger_type ? ('触发：' + t.trigger_type) : (VERIFY_LABEL[t.verify_mode] || '')) + '</div>' +
      '<div class="np-emoji">' + esc(coverEmoji) + '</div></div>';

    html += '<h3 class="np-name">' + esc(t.title || '') + '</h3>';
    html += '<div class="np-meta">' +
      '<span>' + esc(t.type_label || t.type || '任务') + '</span>' +
      (t.age_band ? '<span>' + esc(t.age_band) + ' 岁</span>' : '') +
      '<span>' + esc(VERIFY_LABEL[t.verify_mode] || '判定方式') + '</span></div>';

    html += '<div class="np-story"><p id="npStory"></p></div>';

    html += '<div class="np-task">' +
      '<div class="np-task-head">' +
      '<span class="type-chip ' + (TYPE_CLASS[t.type] || 't-find') + '">' + esc(t.type_label || '任务') + '</span>' +
      (num(t.target_count) > 1 ? '<span class="np-count" id="npCount">' + S.doneCount + '/' + num(t.target_count) + '</span>' : '') +
      '</div>' +
      '<h4>' + esc(t.title || '') + '</h4>' +
      '<div class="np-desc">' + esc(t.desc || '') + '</div>';

    if (t.hint) {
      html += '<div class="hint" id="npHint"><button class="hint-toggle" id="hintToggle">查看阿游的提示 ▾</button>' +
        '<div class="hint-body">' + esc(t.hint) + '</div></div>';
    }

    /* 作答控件：按 verify_mode 渲染 */
    html += '<div class="answer-area" id="answerArea">' + answerHTML(t) + '</div>';

    if (gainTxt) {
      html += '<div class="reward-preview">完成奖励：' + gainTxt +
        (rp.badge ? ' · 徽章「' + esc(rp.badge) + '」' : '') + '</div>';
    }
    html += '</div>';

    html += '<div class="np-actions" id="npActions"></div>';

    box.innerHTML = html;

    /* 打字机效果（点击可跳过） */
    var storyEl = $('#npStory');
    typewriter(storyEl, storyText);

    /* 提示折叠 */
    var toggle = $('#hintToggle');
    if (toggle) toggle.addEventListener('click', function () {
      var h = $('#npHint');
      h.classList.toggle('open');
      toggle.textContent = h.classList.contains('open') ? '收起提示 ▴' : '查看阿游的提示 ▾';
    });

    bindAnswer(t);
  }

  /** 按 verify_mode 生成作答控件 */
  function answerHTML(t) {
    var mode = t.verify_mode || 'auto';
    if (mode === 'answer' && t.options && t.options.length) {
      var h = '<div class="opt-list" id="optList">';
      t.options.forEach(function (o) {
        h += '<button class="opt" data-opt="' + esc(o) + '"><span class="o-box"></span>' + esc(o) + '</button>';
      });
      h += '</div><div class="np-actions" style="margin-top:12px" id="optSubmitWrap">' +
        '<button class="btn-gold" id="btnSubmit">提交答案 →</button></div>';
      return h;
    }
    if (mode === 'keyword' || (mode === 'answer' && !(t.options && t.options.length))) {
      return '<input type="text" id="answerInput" placeholder="' +
        (mode === 'keyword' ? '写下你观察到的关键词…' : '写下你的答案…') + '" autocomplete="off">' +
        '<div class="np-actions"><button class="btn-gold" id="btnSubmit">提交答案 →</button></div>';
    }
    if (mode === 'photo') {
      return '<div class="shutter" id="shutter">' +
        '<span class="s-corner tl"></span><span class="s-corner tr"></span>' +
        '<span class="s-corner bl"></span><span class="s-corner br"></span>' +
        '<div class="scanline"></div>' +
        '<div class="s-ic">📷</div><p id="shutterTip">点击这里拍下你眼前的景物</p></div>' +
        '<div class="np-actions"><button class="btn-gold" id="btnSubmit" disabled>提交拍摄记录 →</button></div>';
    }
    /* auto：到达即完成 */
    return '<button class="btn-gold" id="btnSubmit">我已到达，标记完成 ✓</button>';
  }

  function bindAnswer(t) {
    var mode = t.verify_mode || 'auto';

    if (mode === 'answer' && t.options && t.options.length) {
      $$('.opt').forEach(function (el) {
        el.addEventListener('click', function () {
          $$('.opt').forEach(function (x) { x.classList.remove('on'); });
          el.classList.add('on');
          S.pickedOption = el.dataset.opt;
        });
      });
    }

    var shutter = $('#shutter');
    if (shutter) {
      shutter.addEventListener('click', function () {
        if (shutter.classList.contains('shot') || shutter.classList.contains('capturing')) return;
        shutter.classList.add('capturing');
        setTimeout(function () {
          shutter.classList.remove('capturing');
          shutter.classList.add('shot');
          $('#shutterTip').textContent = '已拍摄 · ' + nowTime() + '（模拟取景）';
          S.photoNote = '拍到了' + (t.type_label || '任务') + '目标：' + (t.title || '') + '（模拟拍摄 ' + nowTime() + '）';
          var btn = $('#btnSubmit');
          if (btn) btn.disabled = false;
          toast('照片已记录，可以提交啦 📸');
        }, 1150);
      });
    }

    var btn = $('#btnSubmit');
    if (btn) btn.addEventListener('click', function () { submitTask(t); });
    var input = $('#answerInput');
    if (input) input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submitTask(t); });
  }

  /** 去掉选项前缀（如「A. 莲花纹」→「莲花纹」），与后端精确匹配规则对齐 */
  function stripOptionPrefix(s) {
    return String(s || '').replace(/^[A-Da-d]\s*[\.、:：)）]\s*/, '').trim();
  }

  function submitTask(t) {
    if (S.submitting) return;
    var mode = t.verify_mode || 'auto';
    var body = { user_id: S.userId };

    if (mode === 'answer' && t.options && t.options.length) {
      if (!S.pickedOption) { toast('先选一个答案吧～', 'err'); return; }
      body.answer = stripOptionPrefix(S.pickedOption);
    } else if (mode === 'keyword' || mode === 'answer') {
      var v = ($('#answerInput') ? $('#answerInput').value : '').trim();
      if (!v) { toast('先写下你的答案吧～', 'err'); return; }
      body.answer = v;
    } else if (mode === 'photo') {
      if (!S.photoNote) { toast('先拍一张照片吧～', 'err'); return; }
      body.photo_note = S.photoNote;
    }

    var target = num(t.target_count, 0);
    if (target > 1) body.count = Math.min(S.doneCount + 1, target);

    S.submitting = true;
    var btn = $('#btnSubmit');
    if (btn) { btn.disabled = true; btn.textContent = '提交中…'; }
    showLoading('正在把发现告诉阿游…');

    api('/api/c/task/' + t.id + '/submit', { method: 'POST', body: body }).then(function (res) {
      hideLoading();
      S.submitting = false;
      if (btn) { btn.textContent = '已提交'; }
      if (res.pass) S.doneCount = body.count ? num(body.count) : S.doneCount + 1;
      invalidate();
      if (S.nodeTaskMap[S.taskNodeId]) { /* 保持映射，方便再次进入 */ }
      renderResult(res, t);
      celebrate(res);
      if (res.badge) showBadge(res.badge);
      if (res.level_up) {
        setTimeout(function () {
          toast('升级！Lv.' + num(res.level_up.level) + ' ' + (res.level_up.level_name || ''));
        }, 900);
      }
    }).catch(function (err) {
      hideLoading();
      S.submitting = false;
      if (btn) { btn.disabled = false; btn.textContent = '重新提交 →'; }
      toast(err.message || '提交失败，请重试', 'err');
    });
  }

  /** 结果反馈区 */
  function renderResult(res, t) {
    var host = $('#npActions');
    if (!host) return;
    var gains = res.growth_gain || {};
    var keys = Object.keys(gains);
    var gainHtml = keys.length
      ? '<div class="r-gains">' + keys.map(function (k, i) {
        return '<span class="gain-pill" style="animation-delay:' + (i * 90) + 'ms">+' +
          num(gains[k]) + ' ' + esc(DIM_LABEL[k] || k) + '</span>';
      }).join('') + '</div>'
      : '';

    var html = '<div class="result' + (res.pass ? '' : ' fail') + '">' +
      '<span class="r-ic">' + (res.pass ? '✨' : '💡') + '</span>' +
      '<b>' + (res.pass ? '任务完成！' : '再试一次，你可以的') + '</b>' +
      '<p>' + esc(res.feedback || (res.pass ? '你做得很好！' : '这次还差一点点，阿游陪你再来一次～')) + '</p>' +
      gainHtml +
      (res.badge ? '<div class="r-badge">🏅 解锁徽章：' + esc(res.badge.name) + '</div>' : '') +
      (res.growth_total ? '<div class="reward-preview" style="margin-top:10px">当前成长值 <em>' + num(res.growth_total) + '</em></div>' : '') +
      '</div>';

    html += '<div class="np-actions" style="margin-top:14px">';
    var target = num(t.target_count, 0);
    if (res.pass) {
      var pill = $('#npCount');
      if (pill) pill.textContent = S.doneCount + '/' + target;
      if (target > 1 && S.doneCount < target) {
        html += '<button class="btn-gold" id="btnAgain">继续任务（' + S.doneCount + '/' + target + '）→</button>';
      }
      if (res.node_completed) html += '<div class="msg sys" style="align-self:center">剧情节点已完成 ✓</div>';
      if (res.next_node) {
        html += '<button class="btn-gold" id="btnNext">下一站：' + esc(res.next_node.name) + ' →</button>';
      }
      html += '<button class="btn-ghost" id="btnBackStory">回到剧本 →</button>';
    } else {
      html += '<button class="btn-gold" id="btnRetry">再试一次 →</button>';
    }
    html += '</div>';

    host.innerHTML = html;

    var again = $('#btnAgain');
    if (again) again.addEventListener('click', function () { openTask(t.id, S.taskNodeId); });

    var next = $('#btnNext');
    if (next) next.addEventListener('click', function () {
      var nid = res.next_node.id;
      loadStory().then(function () {
        var tid = S.nodeTaskMap[nid];
        if (tid) openTask(tid, nid);
        else { closeNode(); go('story'); toast('下一站已经解锁，去剧本里看看 📖'); }
      }).catch(function () { closeNode(); go('story'); });
    });
    var back = $('#btnBackStory');
    if (back) back.addEventListener('click', function () { closeNode(); go('story'); });
    var retry = $('#btnRetry');
    if (retry) retry.addEventListener('click', function () { openTask(t.id, S.taskNodeId); });

    var body = $('#nodeBody');
    if (body) body.scrollTop = body.scrollHeight;
  }

  /** 金色粒子 + 光环 + 成长值飘字 */
  function celebrate(res) {
    if (!res.pass) return;
    var page = $('#page-node');
    var p = document.createElement('div');
    p.className = 'particles';
    for (var i = 0; i < 22; i++) {
      var s = document.createElement('i');
      s.style.left = (5 + Math.random() * 90) + '%';
      s.style.animationDelay = (Math.random() * 600) + 'ms';
      s.style.width = s.style.height = (3 + Math.random() * 6) + 'px';
      p.appendChild(s);
    }
    page.appendChild(p);

    var gains = res.growth_gain || {};
    var keys = Object.keys(gains);
    if (keys.length) {
      var g = document.createElement('div');
      g.className = 'gain-float';
      keys.forEach(function (k, i) {
        var sp = document.createElement('span');
        sp.textContent = '+' + num(gains[k]) + ' ' + (DIM_LABEL[k] || k);
        sp.style.animationDelay = (i * 140) + 'ms';
        g.appendChild(sp);
      });
      page.appendChild(g);
    }

    setTimeout(function () {
      if (p.parentNode) p.parentNode.removeChild(p);
      var gf = $('.gain-float', page);
      if (gf && gf.parentNode) gf.parentNode.removeChild(gf);
    }, 3000);
  }

  /** 徽章解锁弹窗（放大旋转入场） */
  function showBadge(b) {
    var mask = $('#modalMask');
    var pop = $('#badgePop');
    pop.innerHTML = '<div class="rays"></div>' +
      '<div class="kicker">BADGE UNLOCKED · 徽章解锁</div>' +
      '<div class="b-emoji">' + esc(b.emoji || '🏅') + '</div>' +
      '<h3>' + esc(b.name || '新徽章') + '</h3>' +
      '<p>' + esc(b.desc || '继续冒险，收集更多属于你的故事徽章') + '</p>' +
      '<button class="btn-gold" id="badgeOk">收下徽章 ✨</button>';
    mask.classList.add('show');
    var ok = $('#badgeOk');
    if (ok) ok.addEventListener('click', function () { mask.classList.remove('show'); });
    mask.onclick = function (e) { if (e.target === mask) mask.classList.remove('show'); };
  }

  /** 打字机 */
  function typewriter(el, text) {
    if (!el) return;
    text = String(text || '');
    el.textContent = '';
    var caret = document.createElement('span');
    caret.className = 'caret';
    el.appendChild(caret);
    var i = 0;
    var timer = setInterval(function () {
      if (i >= text.length) {
        clearInterval(timer);
        caret.remove();
        el.onclick = null;
        return;
      }
      caret.insertAdjacentText('beforebegin', text.charAt(i));
      i++;
    }, 26);
    el.onclick = function () {
      clearInterval(timer);
      el.textContent = text;
      el.onclick = null;
    };
  }

  /* ======================= 15. 家长模式 · 成长报告 =======================
   * 数据来源（docs/API.md 1A）：
   *   GET /api/c/parent/summary  家庭成长概览
   *   GET /api/c/parent/reports  可查看的旅行报告列表
   *   GET /api/c/parent/report   单次旅行报告（user_id + scenario_id）
   * 页面内所有数字均来自接口，前端不做任何统计口径的推算。
   * ==================================================================== */

  function setParentNav(title, sub) {
    $('#parentNavTitle').textContent = title || '家长模式';
    $('#parentNavSub').textContent = sub || '成长报告';
  }

  /** 地点文案去重。
   *
   * park_name 形如「西安 · 大唐不夜城」，已经包含城市名；此时直接用 park_name，
   * 既不能拼成「西安 · 西安 · 大唐不夜城」，也不能把「大唐不夜城」丢掉。
   * parts = [city, park_name, ...其它尾部字段]
   */
  function whereText(parts) {
    var city = parts[0] || '';
    var park = parts[1] || '';
    var head = '';
    if (park && city && park.indexOf(city) === 0) {
      head = park;                                   // park 已含城市名 → 直接用 park
    } else if (park) {
      head = city ? city + ' · ' + park : park;
    } else {
      head = city;
    }
    var out = [];
    if (head) out.push(head);
    for (var i = 2; i < parts.length; i++) { if (parts[i]) out.push(parts[i]); }
    return out.join(' · ');
  }

  /** 「地点 · 尾部信息」，优先使用后端给的去重字段 place_label。 */
  function placeLine(place, tail) {
    if (place && tail) return place + ' · ' + tail;
    return place || tail || '';
  }

  /** 进入家长模式（默认打开成长概览） */
  function openParent() {
    closeSubpage('#page-node');          // 避免与节点剧情页同时可见
    S.parentView = 'summary';
    S.parentScenarioId = null;
    setParentNav('家长模式', '成长报告');
    $('#parentBody').scrollTop = 0;
    openSubpage('#page-parent');
    renderParentSummary();
  }

  function closeParent() { closeSubpage('#page-parent'); }

  /** 返回：报告页 → 概览页 → 关闭子页面 */
  function parentBack() {
    if (S.parentView === 'report') {
      S.parentView = 'summary';
      S.parentScenarioId = null;
      setParentNav('家长模式', '成长报告');
      renderParentSummary();
      return;
    }
    closeParent();
  }

  /* ---------------- 16.1 成长概览 ---------------- */

  function renderParentSummary() {
    var box = $('#parentBody');
    if (S.parent) { paintParentSummary(S.parent); return Promise.resolve(); }
    return withView(box, 'parent', function () { return loadParent(true); }, paintParentSummary);
  }

  function paintParentSummary(data) {
    var box = $('#parentBody');
    var d = (data && data.summary) || {};
    var child = d.child || {};
    var dev = d.device || {};
    var nl = d.next_level || {};
    var overview = d.overview || [];
    var growth = d.growth || [];
    var weekly = d.weekly || {};
    var badges = d.badges_recent || [];
    var scenarios = d.scenarios || [];
    var suggestions = d.suggestions || [];
    var reports = (data && data.reports) || [];
    var html = '';

    /* ---- 1. 孩子档案卡 + 距离下一级 ---- */
    var total = num(child.growth_total, 0);
    var need = num(nl.need, 0);
    // 本级内进度优先用后端给的 percent（= (growth_total - floor) / (ceil - floor)）；
    // 老接口没有该字段时才退回「占下一级总量的比例」估算。
    var pctNext = nl.at_max ? 100
      : (nl.percent !== undefined && nl.percent !== null
        ? Math.round(clampPct(nl.percent))
        : (total + need > 0 ? Math.round(total / (total + need) * 100) : 0));
    html += '<div class="pr-hero"><div class="pr-top">' +
      '<div class="pr-ava">' + esc(child.avatar || '🧭') + '</div>' +
      '<div class="pr-nm"><b>' + esc(child.nickname || S.familyName) +
      '<span class="lv2">Lv.' + num(child.level, 1) + ' ' + esc(child.level_name || '初识伙伴') + '</span></b>' +
      '<p>' + esc(child.family_name || '') + (dev.nickname ? ' · ' + esc(dev.nickname) + ' 陪伴中' : '') + '</p>' +
      '<div class="pr-chips">' +
      (child.age_band ? '<span class="pr-chip">' + esc(child.age_band) + ' 岁 · ' + esc(child.age_label || '') + '</span>' : '') +
      '<span class="pr-chip g">已旅行 ' + num(child.travel_days) + ' 天</span>' +
      '<span class="pr-chip g">成长值 ' + total + '</span>' +
      '</div></div></div>';
    html += '<div class="pr-next">';
    if (nl.at_max) {
      html += '<div class="pr-next-row"><span>已到达最高等级 <em>Lv.' + num(nl.level, 1) + ' ' +
        esc(nl.name || child.level_name || '') + '</em></span></div>' +
        '<span class="pr-track"><i style="width:100%"></i></span>';
    } else {
      html += '<div class="pr-next-row"><span>距离 <em>Lv.' + (num(nl.level, 1) + 1) + ' ' +
        esc(nl.next_name || '') + '</em> 还差</span><em>' + need + ' 成长值</em></div>' +
        '<span class="pr-track"><i style="width:' + pctNext + '%"></i></span>' +
        '<div class="pr-next-foot"><span>成长值 ' + total + ' / ' + num(nl.ceil, total + need) + '</span>' +
        '<span>本级进度 ' + pctNext + '%</span></div>';
    }
    html += '</div></div>';

    /* ---- 2. 旅行报告列表（顶部入口，来自 /parent/reports） ---- */
    html += '<div class="sec"><div class="sec-title"><b>旅行报告</b><span>' +
      (data && data.reportsOk ? reports.length + ' 份 ›' : '') + '</span></div>';
    if (data && !data.reportsOk) {
      html += '<div class="pr-error"><span>报告列表加载失败：' + esc(data.reportsError || '') + '</span>' +
        '<button id="prReportsRetry">重试</button></div>';
    } else if (!reports.length) {
      html += '<div class="empty-note">还没有可查看的旅行报告<br>孩子开始第一段剧本游后，这里会自动生成 📖</div>';
    } else {
      html += '<div class="pr-reports">';
      reports.forEach(function (r) {
        html += '<div class="pr-rep-chip" data-report="' + esc(r.scenario_id) + '">' +
          '<b>' + esc(r.emoji || '🗺️') + ' ' + esc(r.title || '') + '</b>' +
          '<small>' + esc([r.city, r.status_label].filter(Boolean).join(' · ')) + '</small>' +
          '<div class="bar-mini"><i style="width:' + Math.round(clampPct(r.percent)) + '%"></i></div>' +
          '<div class="prc-foot"><span>' + Math.round(clampPct(r.percent)) + '%</span><span>' + esc(r.updated_at || '') + '</span></div>' +
          '</div>';
      });
      html += '</div>';
    }
    html += '</div>';

    /* ---- 3. 成长概览（6 指标，全部来自接口） ---- */
    html += '<div class="sec"><div class="sec-title"><b>成长概览</b><span>全部来自真实游玩记录</span></div>' +
      '<div class="pr-metrics">';
    if (!overview.length) {
      html += '<div class="empty-note" style="grid-column:1/-1">还没有积累成长数据</div>';
    }
    overview.forEach(function (o) {
      var hasOf = (o.of !== null && o.of !== undefined);
      var of = hasOf ? num(o.of, 0) : 0;
      var pct = hasOf && of > 0 ? Math.round(num(o.value) / of * 100) : 0;
      html += '<div class="pr-metric">' +
        '<div class="pm-v">' + num(o.value) +
        (hasOf ? '<small> / ' + of + ' ' + esc(o.unit || '') + '</small>'
          : '<small> ' + esc(o.unit || '') + '</small>') + '</div>' +
        '<div class="pm-l">' + esc(o.label || '') + '</div>' +
        (hasOf ? '<div class="bar-mini"><i style="width:' + pct + '%"></i></div>' : '') +
        '</div>';
    });
    html += '</div></div>';

    /* ---- 4. 成长画像（解读文字 + 五维横向条形图） ---- */
    html += '<div class="sec"><div class="sec-title"><b>成长画像</b><span>五维成长</span></div>';
    if (d.growth_note) html += '<div class="pr-note">' + esc(d.growth_note) + '</div>';
    html += '<div class="pr-bars">';
    growth.forEach(function (g) {
      html += '<div class="pr-bar-row">' +
        '<span class="prb-l">' + esc(g.label || DIM_LABEL[g.dim] || g.dim) + '</span>' +
        '<span class="pr-track"><i style="width:' + Math.round(clampPct(g.value)) + '%"></i></span>' +
        '<span class="prb-v">' + num(g.value) + '</span></div>';
    });
    html += '</div></div>';

    /* ---- 5. 近 7 天活跃度 ---- */
    var vals = weekly.values || [];
    var peak = num(weekly.peak, 0);
    var labs = weekly.labels || [];
    var days = weekly.days || [];
    html += '<div class="sec"><div class="sec-title"><b>近 7 天活跃度</b><span>每天通过的任务数</span></div>' +
      '<div class="card card-pad"><div class="pr-week">';
    if (!vals.length) {
      html += '<div class="empty-note">暂无近 7 天记录</div>';
    }
    vals.forEach(function (v, i) {
      var h = peak > 0 ? Math.max(6, Math.round(num(v) / peak * 100)) : 6;
      html += '<div class="pr-wcol' + (num(v) > 0 ? ' on' : '') + '">' +
        '<span class="pr-wv">' + (num(v) > 0 ? num(v) : '') + '</span>' +
        '<span class="pr-wtrack"><i class="pr-wbar" style="height:' + h + '%"></i></span>' +
        '<span class="pr-wl">' + esc(labs[i] || days[i] || '') + '</span></div>';
    });
    html += '</div><div class="pr-week-note">本周共完成 <em>' + num(weekly.total) + '</em> 个任务</div></div></div>';

    /* ---- 6. 近期获得的徽章 ---- */
    if (badges.length) {
      html += '<div class="sec"><div class="sec-title"><b>近期获得的徽章</b><span>' + badges.length + ' 枚</span></div>' +
        '<div class="pr-bstrip">';
      badges.forEach(function (b) {
        html += '<div class="pr-bmini"><div class="pb-e">' + esc(b.emoji || '🏅') + '</div>' +
          '<b>' + esc(b.name || '') + '</b>' +
          (b.rarity ? '<span class="pr-rar">' +
            esc(b.rarity_label || RARITY_LABEL[b.rarity] || b.rarity) + '</span>' : '') +
          '<small>' + esc(b.got_at || '') + '</small></div>';
      });
      html += '</div></div>';
    }

    /* ---- 7. 进行中的剧本（点击进入单次旅行报告） ---- */
    html += '<div class="sec"><div class="sec-title"><b>剧本进度</b><span>' + scenarios.length + ' 个 ›</span></div>';
    if (!scenarios.length) {
      html += '<div class="empty-note">孩子还没有开始任何剧本</div>';
    }
    scenarios.forEach(function (s) {
      var done = s.status === 'done';
      html += '<div class="pr-scn" data-report="' + esc(s.scenario_id) + '">' +
        '<div class="ps-e">' + esc(s.emoji || '🗺️') + '</div>' +
        '<div class="ps-b"><b>' + esc(s.title || '') +
        '<span class="' + (done ? 'pill-done' : 'pill-now') + '">' + esc(s.status_label || (done ? '已完成' : '进行中')) + '</span></b>' +
        '<small>' + esc(placeLine(s.place_label || whereText([s.city, s.park_name]),
          s.updated_at)) + '</small>' +
        '<div class="bar-mini"><i style="width:' + Math.round(clampPct(s.percent)) + '%"></i></div></div>' +
        '<span class="ps-go">›</span></div>';
    });
    html += '</div>';

    /* ---- 8. 亲子共玩建议 ---- */
    html += '<div class="sec"><div class="sec-title"><b>亲子共玩建议</b><span>' + suggestions.length + ' 条</span></div>' +
      '<div class="pr-advice">';
    if (!suggestions.length) {
      html += '<div class="empty-note">多玩几个任务，阿游就能给出针对性建议了 🌱</div>';
    }
    suggestions.forEach(function (s) {
      html += '<div class="pr-card">' +
        (s.label ? '<span class="pc-tag">' + esc(s.label) + '</span>' : '') +
        '<b>' + esc(s.title || '') + '</b>' +
        '<p>' + esc(s.advice || '') + '</p></div>';
    });
    html += '</div>';

    html += '<div class="pr-foot">报告数据来自孩子的真实游玩记录 · 家长模式</div>';

    box.innerHTML = html;

    /* 交互：报告入口 / 报告列表重试 */
    $$('[data-report]', box).forEach(function (el) {
      el.addEventListener('click', function () { openParentReport(num(el.dataset.report, 0)); });
    });
    var retry = $('#prReportsRetry');
    if (retry) retry.addEventListener('click', function () {
      S.parent = null;             // 失效缓存后整页重载（概览 + 报告列表）
      renderParentSummary();
    });
  }

  /* ---------------- 16.2 单次旅行报告 ---------------- */

  function openParentReport(scenarioId) {
    if (!scenarioId) { toast('报告不存在', 'err'); return; }
    S.parentView = 'report';
    S.parentScenarioId = scenarioId;
    $('#parentBody').scrollTop = 0;
    openSubpage('#page-parent');
    renderParentReport();
  }

  function renderParentReport() {
    var box = $('#parentBody');
    var sid = S.parentScenarioId;
    if (!sid) { S.parentView = 'summary'; renderParentSummary(); return Promise.resolve(); }
    return withView(box, 'parent', function () {
      return api('/api/c/parent/report', { query: { user_id: S.userId, scenario_id: sid } });
    }, paintParentReport);
  }

  function paintParentReport(d) {
    var box = $('#parentBody');
    var sc = d.scenario || {};
    var sm = d.summary || {};
    var chapters = d.chapters || [];
    var trail = d.trail || [];
    var knowledge = d.knowledge || [];
    var questions = d.questions || [];
    var gains = d.growth_gain || {};
    var badges = d.badges || [];
    var pct = clampPct(sm.percent);
    var R = 30;
    var C = 2 * Math.PI * R;
    var dash = (C * pct / 100).toFixed(1) + ' ' + C.toFixed(1);

    setParentNav(sc.title || '旅行报告',
      [sc.city, sc.age_label].filter(Boolean).join(' · ') || '旅行报告');

    var html = '';

    /* ---- 1. 报告头：进度环 + 4 个小指标 ---- */
    var dFrom = (sm.started_at || '').slice(0, 5) || '—';
    var dTo = (sm.updated_at || '').slice(0, 5) || '—';
    html += '<div class="pr-rhead"><div class="pr-rhead-top">' +
      '<div class="prh-e">' + esc(sc.emoji || '🗺️') + '</div>' +
      '<div class="prh-b"><b>' + esc(sc.title || '') + '</b>' +
      '<small>' + esc(sc.place_label || whereText([sc.city, sc.park_name])) + '</small>' +
      (sc.age_band ? '<small>' + esc(sc.age_band) + ' 岁 · ' + esc(sc.age_label || '') + '</small>' : '') +
      '</div>' +
      '<div class="pr-ring"><svg viewBox="0 0 76 76">' +
      '<circle cx="38" cy="38" r="30" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="5"/>' +
      '<circle cx="38" cy="38" r="30" fill="none" stroke="#E8B45A" stroke-width="5" stroke-linecap="round" ' +
      'stroke-dasharray="' + dash + '"/></svg>' +
      '<span class="prg-t"><b>' + pct + '%</b><small>' + esc(sm.status_label || '') + '</small></span></div>' +
      '</div>';

    var span = (sm.started_at || '') + ' ~ ' + (sm.updated_at || '');
    html += '<div class="pr-stats">' +
      '<div class="pr-stat"><b>' + num(sm.visited) + '/' + num(sm.total) + '</b><small>剧情点</small></div>' +
      '<div class="pr-stat"><b>' + num(sm.tasks_done) + '</b><small>完成任务</small></div>' +
      '<div class="pr-stat"><b>' + num(sm.minutes) + '</b><small>分钟</small></div>' +
      '<div class="pr-stat"><b class="tiny">' + esc(dFrom + ' ~ ' + dTo) + '</b><small>游玩时间</small></div>' +
      '</div>';
    html += '<div class="pr-span">🕒 <em>' + esc(span) + '</em>' +
      '<span>· 完成章节 ' + num(sm.chapters_done) + '/' + num(sm.chapters_total) + '</span></div>';
    if (sc.subtitle) html += '<div class="pr-span">📖 ' + esc(sc.subtitle) + '</div>';
    html += '</div>';

    /* ---- 2. 章节回顾 ---- */
    html += '<div class="sec"><div class="sec-title"><b>章节回顾</b><span>' + chapters.length + ' 章</span></div>';
    if (!chapters.length) {
      html += '<div class="empty-note">这个剧本还没有章节数据</div>';
    }
    chapters.forEach(function (c) {
      var cls = c.state === 'done' ? 'done' : (c.state === 'now' ? 'now' : '');
      var dot = c.state === 'done' ? '✓' : (c.state === 'now' ? '▶' : num(c.idx));
      var nodes = c.nodes || [];
      html += '<div class="pr-chap ' + cls + '"><div class="pc-h">' +
        '<span class="pc-d">' + dot + '</span>' +
        '<b>第 ' + num(c.idx) + ' 章 · ' + esc(c.title || '') + '</b></div>' +
        (c.summary ? '<p>' + esc(c.summary) + '</p>' : '');
      if (nodes.length) {
        html += '<div class="pr-nodes">';
        nodes.forEach(function (n) {
          var nd = n.state === 'done';
          html += '<div class="pr-node' + (nd ? ' done' : '') + '">' +
            '<span class="pn-c">' + (nd ? '✓' : '') + '</span>' + esc(n.name || '') +
            (n.place ? '<span class="pn-p">' + esc(n.place) + '</span>' : '') + '</div>';
        });
        html += '</div>';
      }
      html += '</div>';
    });
    html += '</div>';

    /* ---- 3. 旅行时间轴 ---- */
    html += '<div class="sec"><div class="sec-title"><b>旅行时间轴</b><span>' + trail.length + ' 条记录</span></div>';
    if (!trail.length) {
      html += '<div class="empty-note">还没有到访记录</div>';
    } else {
      html += '<div class="pr-trail">';
      trail.forEach(function (t) {
        var kind = t.type === 'task' ? (t.passed ? 'task' : 'fail') : 'visit';
        var icon = kind === 'task' ? '✓' : (kind === 'fail' ? '·' : '');
        html += '<div class="pr-ti ' + kind + '">' +
          '<span class="pr-tdot">' + icon + '</span>' +
          '<div class="pr-tb"><div class="pr-tm">' + esc(t.at || '') + '</div>' +
          '<b>' + esc(t.node || '') + '</b>' +
          '<div class="pr-ev ' + kind + '">' + esc(t.event || '') +
          (t.source ? ' · ' + esc(t.source) : '') + '</div></div></div>';
      });
      html += '</div>';
    }
    html += '</div>';

    /* ---- 4. 这次接触到的知识点（家长价值最高，视觉突出） ---- */
    html += '<div class="sec"><div class="sec-title"><b>这次接触到的知识点</b><span>' + knowledge.length + ' 条</span></div>';
    if (!knowledge.length) {
      html += '<div class="empty-note">这次旅行还没有反查到景区知识点<br>走到更多剧情点，报告会更丰富 📚</div>';
    } else {
      html += '<div class="pr-know">';
      knowledge.forEach(function (k) {
        html += '<div class="pr-knowcard">' +
          '<span class="pk-tag">' + esc(k.category_label || k.category || '知识点') + '</span>' +
          '<b>' + esc(k.title || '') + '</b>' +
          '<p>' + esc(k.point || '') + '</p>' +
          '<div class="pk-src">← 节点「' + esc(k.node || k.place || '') + '」' +
          (k.place && k.place !== k.node ? ' · ' + esc(k.place) : '') + '</div>' +
          '</div>';
      });
      html += '</div>';
    }
    html += '</div>';

    /* ---- 5. 回家路上可以问孩子 ---- */
    html += '<div class="sec"><div class="sec-title"><b>回家路上可以问孩子</b><span>' + questions.length + ' 个问题</span></div>' +
      '<div class="pr-asks">';
    if (!questions.length) {
      html += '<div class="empty-note">完成一个任务后，这里会出现可以照着念的问题 💬</div>';
    }
    questions.forEach(function (q) {
      html += '<div class="pr-ask"><span class="pa-q">?</span><p>' + esc(q) + '</p></div>';
    });
    html += '</div></div>';

    /* ---- 6. 本次成长 ---- */
    var dims = Object.keys(gains);
    html += '<div class="sec"><div class="sec-title"><b>本次成长</b><span>按维度累计</span></div>';
    if (dims.length) {
      html += '<div class="pr-gains">' + dims.map(function (k, i) {
        return '<span class="pr-gain" style="animation-delay:' + (i * 90) + 'ms">' +
          esc(DIM_LABEL[k] || k) + ' +' + num(gains[k]) + '</span>';
      }).join('') + '</div>';
    } else {
      html += '<div class="empty-note">这次旅行还没有获得成长值</div>';
    }
    html += '</div>';

    /* ---- 7. 获得的徽章 ---- */
    if (badges.length) {
      html += '<div class="sec"><div class="sec-title"><b>获得的徽章</b><span>' + badges.length + ' 枚</span></div>' +
        '<div class="badges">';
      badges.forEach(function (b) {
        html += '<div class="badge got" data-badge="' + esc(b.name) + '">' +
          '<div class="b-ic">' + esc(b.emoji || '🏅') + '</div><small>' + esc(b.name || '') + '</small></div>';
      });
      html += '</div></div>';
    }

    html += '<div class="np-actions" style="margin-top:16px">' +
      '<button class="btn-ghost" id="prBackSummary">← 返回成长概览</button></div>';
    html += '<div class="pr-foot">报告由孩子的真实游玩记录生成 · 家长模式</div>';

    box.innerHTML = html;

    var back = $('#prBackSummary');
    if (back) back.addEventListener('click', parentBack);
    $$('.badge', box).forEach(function (el) {
      el.addEventListener('click', function () {
        toast('已获得徽章「' + el.dataset.badge + '」✨');
      });
    });
  }

  /* ======================= 16. 事件绑定与启动 ======================= */

  function bindEvents() {
    /* Tab 切换 */
    $$('.tab').forEach(function (t) {
      t.addEventListener('click', function () { go(t.dataset.tab); });
    });

    /* 开箱引导 */
    $('#obStart').addEventListener('click', doActivate);
    $('#obSkip').addEventListener('click', skipOnboard);
    $('#obFill').addEventListener('click', function () {
      $('#obCode').value = DEMO_CODE;
      $('#obName').value = $('#obName').value.trim() || '阿游';
      toast('已填入演示激活码 ' + DEMO_CODE);
    });
    $('#obCode').addEventListener('keydown', function (e) { if (e.key === 'Enter') doActivate(); });
    $('#obName').addEventListener('keydown', function (e) { if (e.key === 'Enter') $('#obCode').focus(); });
    $('#obMascot').addEventListener('click', function () {
      toast('我在这里等你给我取名字 ✨');
    });

    /* 聊天输入 */
    $('#btnSend').addEventListener('click', function () {
      var v = $('#chatField').value;
      $('#chatField').value = '';
      sendChat(v);
    });
    $('#chatField').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        var v = $('#chatField').value;
        $('#chatField').value = '';
        sendChat(v);
      }
    });
    $('#btnVoice').addEventListener('click', function () {
      toast('语音陪伴开发中，先用文字和阿游聊聊吧 🎙️');
    });
    $('#btnLocate').addEventListener('click', function () { locateFlow(false); });

    /* 节点页返回 */
    $('#nodeBack').addEventListener('click', function () {
      closeNode();
      if (S.tab === 'home') renderHome(true);
      if (S.tab === 'mine') renderMine(true);
      if (S.tab === 'explore') renderExplore(true);
    });

    /* 抽屉返回 / 遮罩关闭 */
    $('#drawerBack').addEventListener('click', closeDrawer);
    $('#drawerMask').addEventListener('click', function (e) {
      if (e.target === $('#drawerMask')) closeDrawer();
    });

    /* 家长模式返回（报告页 → 概览页 → 关闭） */
    $('#parentBack').addEventListener('click', parentBack);

    /* 全局兜底：任何未捕获错误都不白屏 */
    window.addEventListener('error', function (e) {
      if (e && e.message) toast('页面出现小状况，请重试', 'err');
    });
    window.addEventListener('unhandledrejection', function () {
      toast('操作未完成，请重试', 'err');
    });
  }

  function boot() {
    bindEvents();
    S.deviceNick = (function () {
      try { return localStorage.getItem(LS.device) || '阿游'; } catch (e) { return '阿游'; }
    })();
    S.familyName = (function () {
      try { return localStorage.getItem(LS.family) || '小小探险家'; } catch (e) { return '小小探险家'; }
    })();

    var uid = null;
    try { uid = localStorage.getItem(LS.user); } catch (e) { uid = null; }

    if (uid) {
      S.userId = num(uid, DEMO_USER);
      hideOnboard();
      go('home');
      preload();
    } else {
      showOnboard();
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

})();
