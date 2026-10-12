/* 阅读站前端:主题、已读/收藏(localStorage)、展开卡片、筛选/搜索/排序、键盘快捷键、阅读模式、
   状态导入导出、全站搜索页(读取 search-index.json)。纯静态,无后端。 */
(function () {
  'use strict';
  var root = document.documentElement, body = document.body;
  var ROOT = body.dataset.root || '', KIND = body.dataset.kind || 'list';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return [].slice.call((c || document).querySelectorAll(s)); };

  // ───────── 主题 ─────────
  var tbtn = $('#theme');
  if (tbtn) tbtn.addEventListener('click', function () {
    var cur = root.dataset.theme, dark = cur === 'dark' || (cur === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) {}
  });

  // ───────── 状态存储:{v:1, read:{id:ts}, star:{id:ts}, snap:{id:{...}}} ─────────
  var KEY = 'digest.state.v1', mem = null;
  function emptyState() { return { v: 1, read: {}, star: {}, snap: {} }; }
  function loadState() {
    var s;
    try { s = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { s = mem; }
    if (!s || typeof s !== 'object') s = mem || emptyState();
    s.read = s.read || {}; s.star = s.star || {}; s.snap = s.snap || {};
    return s;
  }
  var state = loadState();
  function saveState() {
    mem = state;
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  window.addEventListener('storage', function (e) {
    if (e.key === KEY) { state = loadState(); refreshAll(); }
  });
  var now = function () { return Date.now(); };
  function isRead(id) { return !!state.read[id]; }
  function isStar(id) { return !!state.star[id]; }

  // ───────── 条目:从 DOM(静态页)或 search-index.json(搜索页)得到统一的数据对象 ─────────
  var items = [];   // {id, sec, topics[], date, key, text, source, el, data}
  function fromCard(el) {
    return { id: el.dataset.id, sec: el.dataset.sec, topics: el.dataset.topics.split('|'), dir: el.dataset.dir || '', date: el.dataset.date, key: el.dataset.key,
      text: el.dataset.text, source: el.dataset.source, el: el };
  }
  function itemText(d) {
    return [d.title, d.source, d.summary, (d.topics || []).join(' '), d.dir || '', d.date, d.ver || '', (d.tries || []).join(' '), d.why || '', d['try'] || ''].join(' ').toLowerCase();
  }
  function fromData(d) {
    return { id: d.id, sec: d.sec, topics: d.topics || [], dir: d.dir || '', date: d.date, key: d.key, text: itemText(d), source: d.source, el: null, data: d };
  }
  function snapOf(it) {
    var d = it.data;
    if (d) return { title: d.title, url: d.url, source: d.source, date: d.date, pub: d.pub, sec: d.sec, topics: d.topics, dir: d.dir, tc: d.tc, summary: (d.summary || '').slice(0, 400) };
    var el = it.el, a = $('a.orig', el);
    return { title: a.textContent, url: a.href, source: it.source, date: it.date, pub: '', sec: it.sec, topics: it.topics, dir: it.dir, tc: [], summary: ($('.summary', el).textContent || '').slice(0, 400) };
  }

  // ───────── 状态 → UI ─────────
  function applyCard(el) {
    var id = el.dataset.id, r = isRead(id), s = isStar(id);
    el.classList.toggle('read', r);
    el.classList.toggle('starred', s);
    var st = $('.star', el), rd = $('.rd', el);
    if (st) { st.setAttribute('aria-pressed', s ? 'true' : 'false'); st.textContent = s ? '★' : '☆'; st.title = s ? '取消收藏(s)' : '收藏(s)'; }
    if (rd) { rd.setAttribute('aria-pressed', r ? 'true' : 'false'); rd.textContent = r ? '✓ 已读(点此标为未读)' : '标记已读'; }
  }
  var ids = null;   // ids.json: {ue:[], picks:[], feeds:[]}
  function updateCounters() {
    var u = $('#unread'), t = $('#total');
    if (u && t) {
      var list = items.length ? items : $$('.item').map(fromCard);
      t.textContent = list.length;
      u.textContent = list.filter(function (i) { return !isRead(i.id); }).length;
    }
    if (ids) {
      ['ue', 'picks', 'feeds'].forEach(function (k) {
        var b = $('[data-badge="' + k + '"]'); if (!b) return;
        var n = ids[k].filter(function (i) { return !state.read[i]; }).length;
        b.textContent = n; b.hidden = !n; b.title = n + ' 条未读';
      });
      var sb = $('[data-badge="star"]');
      if (sb) { var n2 = Object.keys(state.star).length; sb.textContent = '★' + n2; sb.hidden = !n2; sb.title = n2 + ' 条收藏'; }
    }
  }
  function refreshAll() {
    $$('.item').forEach(applyCard);
    updateCounters();
    if (typeof run === 'function' && (F.st || KIND === 'search')) run(true);
  }

  // ───────── 动作 ─────────
  function itemOf(el) { var id = el.dataset.id; for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i]; return fromCard(el); }
  function setRead(id, v) { if (v) state.read[id] = now(); else delete state.read[id]; }
  function setStar(it, v) {
    if (v) { state.star[it.id] = now(); state.snap[it.id] = snapOf(it); } else { delete state.star[it.id]; delete state.snap[it.id]; }
  }
  function afterChange(el) {
    saveState();
    var id = el && el.dataset.id;   // 同一条内容可能同时出现在卡片和详情面板里,一起刷新
    $$('.item').forEach(function (x) { if (!id || x.dataset.id === id) applyCard(x); });
    updateCounters();
  }
  function toggleOpen(el, force) {
    var open = force === undefined ? !el.classList.contains('open') : force;
    el.classList.toggle('open', open);
    var t = $('.tog', el); if (t) { t.setAttribute('aria-expanded', open ? 'true' : 'false'); t.textContent = open ? '收起' : '展开全文'; }
    if (open && !isRead(el.dataset.id)) { setRead(el.dataset.id, true); afterChange(el); }
  }
  function openOriginal(el) {
    var a = $('a.orig', el); if (!a) return;
    window.open(a.href, '_blank', 'noopener');
    if (!isRead(el.dataset.id)) { setRead(el.dataset.id, true); afterChange(el); }
  }
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;
    var od = t.closest('.open-detail');
    if (od && KIND === 'mag' && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button)) {
      e.preventDefault(); openDetail(od.closest('.item')); return;
    }
    var nv = t.closest('[data-nav]');
    if (nv) { navDetail(+nv.dataset.nav); return; }
    if (t.closest('.dlg-x')) { closeDlg(); return; }
    var el = t.closest('.item'); if (!el) return;
    var b = t.closest('button');
    if (t.closest('a.orig')) { if (!isRead(el.dataset.id)) { setRead(el.dataset.id, true); afterChange(el); } return; }
    if (!b) return;
    if (b.classList.contains('star')) { setStar(itemOf(el), !isStar(el.dataset.id)); afterChange(el); }
    else if (b.classList.contains('rd')) { setRead(el.dataset.id, !isRead(el.dataset.id)); afterChange(el); }
    else if (b.classList.contains('tog')) toggleOpen(el);
    select(el.classList.contains('dlgitem') ? dlgTile : el, false);
  });

  // ───────── 杂志页:页内详情面板 ─────────
  var dlg = null, dlgTile = null, lastFocus = null;
  function hh(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function ensureDlg() {
    if (dlg) return dlg;
    dlg = hh('div', 'dlg'); dlg.hidden = true;
    dlg.setAttribute('role', 'dialog'); dlg.setAttribute('aria-modal', 'true'); dlg.setAttribute('aria-label', '内容详情');
    dlg.innerHTML = '<div class="dlg-back"></div><div class="dlg-panel" tabindex="-1"></div>';
    dlg.firstChild.addEventListener('click', closeDlg);
    body.appendChild(dlg);
    return dlg;
  }
  function openDetail(tile) {
    if (!tile) return;
    ensureDlg();
    var panel = dlg.lastChild, hid = $('.hid', tile);
    if (dlg.hidden) lastFocus = document.activeElement;
    panel.innerHTML = '';
    var x = hh('button', 'dlg-x', '×'); x.type = 'button'; x.setAttribute('aria-label', '关闭(Esc)'); panel.appendChild(x);
    var cv = $('.cover svg', tile);
    if (cv) {   // 插图按原比例居中,两侧用插图底色补齐
      var cw = hh('div', 'dlg-cover'), sv = cv.cloneNode(true); sv.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      cw.appendChild(sv); panel.appendChild(cw);
      var bgr = $('.bg', cv); if (bgr) cw.style.background = getComputedStyle(bgr).fill;
    }
    var it = hh('article', 'item dlgitem open');
    ['id', 'sec', 'topics', 'dir', 'date', 'key', 'source'].forEach(function (k) { it.dataset[k] = tile.dataset[k] || ''; });
    var kick = hh('div', 'kick'); var d1 = $('.kick .dir', tile); if (d1) kick.appendChild(d1.cloneNode(true));
    var s1 = $('.kick .sec', tile); if (s1) kick.appendChild(s1.cloneNode(true)); it.appendChild(kick);
    var oa = $('a.orig', hid);
    var h2 = hh('h2'); var ha = hh('a', 'orig', oa.textContent); ha.href = oa.href; ha.target = '_blank'; ha.rel = 'noopener noreferrer'; h2.appendChild(ha); it.appendChild(h2);
    var m = $('.meta', hid); if (m) it.appendChild(m.cloneNode(true));
    it.appendChild(hh('p', 'summary', $('.summary', tile).textContent));
    var mo = $('.more', hid); if (mo && mo.children.length) it.appendChild(mo.cloneNode(true));
    var acts = hh('div', 'acts');
    var a2 = hh('a', 'btn primary orig', '阅读原文 ↗'); a2.href = oa.href; a2.target = '_blank'; a2.rel = 'noopener noreferrer'; acts.appendChild(a2);
    var st = hh('button', 'star', '☆'); st.type = 'button'; st.setAttribute('aria-pressed', 'false'); st.setAttribute('aria-label', '收藏'); acts.appendChild(st);
    var rd = hh('button', 'btn rd', '标记已读'); rd.type = 'button'; rd.setAttribute('aria-pressed', 'false'); acts.appendChild(rd);
    acts.appendChild(hh('span', 'sp'));
    var pv = hh('button', 'btn sm', '← 上一篇'); pv.type = 'button'; pv.dataset.nav = '-1'; acts.appendChild(pv);
    var nx = hh('button', 'btn sm', '下一篇 →'); nx.type = 'button'; nx.dataset.nav = '1'; acts.appendChild(nx);
    it.appendChild(acts); panel.appendChild(it);
    dlgTile = tile; select(tile, false);
    if (!isRead(tile.dataset.id)) { setRead(tile.dataset.id, true); saveState(); }
    $$('.item').forEach(applyCard); updateCounters();
    dlg.hidden = false; root.classList.add('dlg-open'); panel.scrollTop = 0; panel.focus();
  }
  function closeDlg() {
    if (!dlg || dlg.hidden) return;
    dlg.hidden = true; root.classList.remove('dlg-open');
    if (dlgTile) { try { dlgTile.scrollIntoView({ block: 'nearest' }); } catch (e) {} }
    var f = lastFocus; lastFocus = null; if (f && f.focus) { try { f.focus({ preventScroll: true }); } catch (e) {} }
  }
  function navDetail(dir) {
    var list = visibleCards(); if (!list.length) return;
    var i = list.indexOf(dlgTile); i = Math.max(0, Math.min(list.length - 1, i + dir));
    openDetail(list[i]);
  }
  function dlgOpen() { return dlg && !dlg.hidden; }

  function toast(msg, undo) {
    var t = $('#toast'); if (!t) return;
    t.innerHTML = ''; var s = document.createElement('span'); s.textContent = msg; t.appendChild(s);
    if (undo) { var b = document.createElement('button'); b.type = 'button'; b.textContent = '撤销'; b.onclick = function () { undo(); t.hidden = true; }; t.appendChild(b); }
    t.hidden = false; clearTimeout(toast.tm); toast.tm = setTimeout(function () { t.hidden = true; }, 8000);
  }

  // ───────── 阅读模式 ─────────
  var rm = $('#readmode');
  function syncRM() { var on = root.classList.contains('reading'); if (rm) { rm.setAttribute('aria-pressed', on ? 'true' : 'false'); rm.textContent = on ? '退出阅读模式' : '阅读模式'; } }
  if (rm) rm.addEventListener('click', function () {
    var on = root.classList.toggle('reading');
    try { localStorage.setItem('digest.reading', on ? '1' : '0'); } catch (e) {}
    syncRM();
  });
  syncRM();

  // ───────── 键盘快捷键 ─────────
  var cur = null;
  function visibleCards() { return $$('.item:not(.dlgitem)').filter(function (e) { return !e.hidden && e.offsetParent !== null; }); }
  function select(el, scroll) {
    if (cur) cur.classList.remove('sel');
    cur = el; if (!el) return;
    el.classList.add('sel');
    if (scroll) el.scrollIntoView({ block: 'center', behavior: 'auto' });
  }
  document.addEventListener('keydown', function (e) {
    var tg = e.target, tag = tg && tg.tagName;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (tg && tg.isContentEditable)) { if (e.key === 'Escape') tg.blur(); return; }
    var k = e.key, list;
    if (dlgOpen()) {   // 详情面板打开时:Esc 关闭,j/k 上下篇,o/s/m 作用于当前这条,Tab 留在面板内
      if (k === 'Escape' || k === 'e') { closeDlg(); e.preventDefault(); return; }
      if (k === 'j' || k === 'k') { navDetail(k === 'j' ? 1 : -1); e.preventDefault(); return; }
      if (k === 'Tab') {
        var fs = $$('a[href],button', dlg.lastChild).filter(function (n) { return !n.disabled; });
        if (fs.length) { var fi = fs.indexOf(document.activeElement);
          if (e.shiftKey && (fi <= 0)) { fs[fs.length - 1].focus(); e.preventDefault(); }
          else if (!e.shiftKey && fi === fs.length - 1) { fs[0].focus(); e.preventDefault(); } }
        return;
      }
    }
    if (k === 'j' || k === 'k') {
      list = visibleCards(); if (!list.length) return;
      var i = cur ? list.indexOf(cur) : -1;
      if (k === 'j') {
        if (i === list.length - 1) { var mb = $('#more'); if (mb && !mb.hidden) { mb.click(); list = visibleCards(); } }
        i = Math.min(list.length - 1, i + 1);
      } else i = Math.max(0, i - 1);
      select(list[i], true); e.preventDefault();
    } else if (k === 'o' || k === 'Enter') {
      if (k === 'Enter' && (tag === 'BUTTON' || tag === 'A')) return;
      if (cur) { k === 'o' ? openOriginal(cur) : (KIND === 'mag' ? openDetail(cur) : toggleOpen(cur)); e.preventDefault(); }
    } else if (k === 'e' || k === ' ') { if (cur && !(k === ' ' && (tag === 'BUTTON' || tag === 'A'))) { KIND === 'mag' ? openDetail(cur) : toggleOpen(cur); e.preventDefault(); } }
    else if (k === 's') { if (cur) { setStar(itemOf(cur), !isStar(cur.dataset.id)); afterChange(cur); } }
    else if (k === 'm') { if (cur) { setRead(cur.dataset.id, !isRead(cur.dataset.id)); afterChange(cur); } }
    else if (k === '/') { var q = $('#q'); if (q) { q.focus(); q.select(); e.preventDefault(); } }
  });

  // ───────── 全部标记已读(带撤销) ─────────
  function markAll(list) {
    var prev = {}, n = 0;
    list.forEach(function (i) { if (!state.read[i.id]) { prev[i.id] = true; state.read[i.id] = now(); n++; } });
    if (!n) { toast('当前列表已经全部是已读'); return; }
    saveState(); refreshAll();
    toast('已把 ' + n + ' 条标为已读', function () { Object.keys(prev).forEach(function (id) { delete state.read[id]; }); saveState(); refreshAll(); });
  }

  // ───────── 导出 / 导入 ─────────
  function exportState() {
    var data = { app: 'ue-digest', version: 1, exported: new Date().toISOString(), read: state.read, star: state.star, snap: state.snap };
    var blob = new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'digest-state-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
    toast('已导出:已读 ' + Object.keys(state.read).length + ' 条,收藏 ' + Object.keys(state.star).length + ' 条');
  }
  function validImport(d) {
    return d && typeof d === 'object' && d.read && d.star && typeof d.read === 'object' && typeof d.star === 'object';
  }
  function importState(text, replace) {
    var d; try { d = JSON.parse(text); } catch (e) { toast('导入失败:不是有效的 JSON'); return false; }
    if (!validImport(d)) { toast('导入失败:文件格式不对(需要 read / star 字段)'); return false; }
    var snap = d.snap && typeof d.snap === 'object' ? d.snap : {};
    if (replace) { state = { v: 1, read: {}, star: {}, snap: {} }; }
    Object.keys(d.read).forEach(function (id) { state.read[id] = Math.max(state.read[id] || 0, +d.read[id] || 1); });
    Object.keys(d.star).forEach(function (id) { state.star[id] = Math.max(state.star[id] || 0, +d.star[id] || 1); if (snap[id]) state.snap[id] = snap[id]; });
    saveState(); refreshAll();
    toast((replace ? '已覆盖导入' : '已合并导入') + ':现有已读 ' + Object.keys(state.read).length + ' 条,收藏 ' + Object.keys(state.star).length + ' 条');
    return true;
  }
  var fileIn = $('#file'), importMode = 'merge';
  if (fileIn) {
    $('#export').addEventListener('click', exportState);
    $('#import').addEventListener('click', function () { importMode = 'merge'; fileIn.value = ''; fileIn.click(); });
    $('#importreplace').addEventListener('click', function () { importMode = 'replace'; fileIn.value = ''; fileIn.click(); });
    fileIn.addEventListener('change', function () {
      var f = fileIn.files[0]; if (!f) return;
      var r = new FileReader(); r.onload = function () { importState(String(r.result), importMode === 'replace'); }; r.readAsText(f);
    });
  }
  window.__digest = { importState: importState, getState: function () { return state; } };   // 便于测试

  // ───────── 筛选 / 搜索 / 排序 / 高亮 ─────────
  var F = { q: '', topic: '', sec: '', dir: '', st: '', from: '', to: '', sort: 'new', src: '' };
  var run = null;
  var qEl = $('#q');

  function words() { return F.q.toLowerCase().split(/\s+/).filter(Boolean); }
  function match(it, ws) {
    if (F.sec && it.sec !== F.sec) return false;
    if (F.dir && it.dir !== F.dir) return false;
    if (F.topic && it.topics.indexOf(F.topic) < 0) return false;
    if (F.src && it.source !== F.src) return false;
    if (F.from && it.date < F.from) return false;
    if (F.to && it.date > F.to) return false;
    if (F.st === 'unread' && isRead(it.id)) return false;
    if (F.st === 'star' && !isStar(it.id)) return false;
    for (var i = 0; i < ws.length; i++) if (it.text.indexOf(ws[i]) < 0) return false;
    return true;
  }
  function clearMarks(el) {
    $$('mark.hl', el).forEach(function (m) { var p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); });
  }
  function highlight(el, ws) {
    clearMarks(el);
    if (!ws.length) return;
    var re = new RegExp('(' + ws.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')', 'gi');
    var targets = $$('h3 a, .summary, .meta span, .more p, .more li, .more h4', el);
    targets.forEach(function (t) {
      var tw = document.createTreeWalker(t, NodeFilter.SHOW_TEXT, null), nodes = [], n;
      while ((n = tw.nextNode())) nodes.push(n);
      nodes.forEach(function (tn) {
        if (!re.test(tn.nodeValue)) return; re.lastIndex = 0;
        var frag = document.createDocumentFragment(), parts = tn.nodeValue.split(re);
        parts.forEach(function (p, i) {
          if (i % 2) { var m = document.createElement('mark'); m.className = 'hl'; m.textContent = p; frag.appendChild(m); }
          else if (p) frag.appendChild(document.createTextNode(p));
        });
        tn.parentNode.replaceChild(frag, tn);
      });
    });
    // 命中“更多”区域里的内容时自动展开,免得看不到高亮
    if ($('.more mark.hl', el) && !el.classList.contains('open')) toggleOpenSilent(el);
  }
  function toggleOpenSilent(el) {
    el.classList.add('open'); var t = $('.tog', el); if (t) { t.setAttribute('aria-expanded', 'true'); t.textContent = '收起'; }
  }
  function syncURL() {
    var p = new URLSearchParams();
    ['q', 'topic', 'sec', 'dir', 'st', 'from', 'to', 'src'].forEach(function (k) { if (F[k]) p.set(k, F[k]); });
    if (F.sort !== 'new') p.set('sort', F.sort);
    var s = p.toString();
    try { history.replaceState(null, '', s ? '?' + s : location.pathname); } catch (e) {}
  }
  function readControls() {
    if (qEl) F.q = qEl.value;
    ['from', 'to', 'src'].forEach(function (k) { var e = $('#' + k); if (e) F[k] = e.value; });
    var so = $('#sort'); if (so) F.sort = so.value;
  }
  function writeControls() {
    if (qEl) qEl.value = F.q;
    ['from', 'to', 'src'].forEach(function (k) { var e = $('#' + k); if (e) e.value = F[k]; });
    var so = $('#sort'); if (so) so.value = F.sort;
    $$('#topicf .f').forEach(function (b) { b.classList.toggle('active', (b.dataset.topic || '') === F.topic); });
    $$('#statusf .f').forEach(function (b) { b.classList.toggle('active', (b.dataset.st || '') === F.st); });
    $$('#secf .f').forEach(function (b) { b.classList.toggle('active', (b.dataset.sec || '') === F.sec); });
    $$('#dirf .f').forEach(function (b) { b.classList.toggle('active', (b.dataset.dir || '') === F.dir); });
    var adv = $('.adv'); if (adv && (F.from || F.to || F.src || F.sort !== 'new')) adv.open = true;
  }
  var cmp = function (a, b) { return a.key < b.key ? -1 : a.key > b.key ? 1 : 0; };

  function initFilters(isSearch) {
    var p = new URLSearchParams(location.search);
    ['q', 'topic', 'sec', 'dir', 'st', 'from', 'to', 'src'].forEach(function (k) { if (p.get(k)) F[k] = p.get(k); });
    if (p.get('sort') === 'old') F.sort = 'old';
    writeControls();
    function bind(sel, attr, key) {
      $$(sel).forEach(function (b) { b.addEventListener('click', function () { F[key] = b.dataset[attr] || ''; writeControls(); run(); }); });
    }
    bind('#topicf .f', 'topic', 'topic'); bind('#statusf .f', 'st', 'st'); bind('#secf .f', 'sec', 'sec'); bind('#dirf .f', 'dir', 'dir');
    var tm;
    if (qEl) qEl.addEventListener('input', function () { clearTimeout(tm); tm = setTimeout(function () { readControls(); run(); }, 120); });
    ['from', 'to', 'src', 'sort'].forEach(function (k) { var e = $('#' + k); if (e) e.addEventListener('change', function () { readControls(); run(); if (e.tagName === 'SELECT') e.blur(); }); });
    var rs = $('#resetf'); if (rs) rs.addEventListener('click', function () { F = { q: '', topic: '', sec: '', dir: '', st: '', from: '', to: '', sort: 'new', src: '' }; writeControls(); run(); });
    var ma = $('#markall'); if (ma) ma.addEventListener('click', function () { markAll(lastMatched); });
  }
  var lastMatched = [];

  // —— 静态列表页:直接显隐已有卡片
  function initStaticList() {
    items = $$('#list .item').map(fromCard);
    var listEl = $('#list'), sections = $$('section.issue', listEl), empty = $('#empty'), status = $('#status');
    var order = 'new';
    run = function (keep) {
      if (!keep) readControls();
      var ws = words();
      if (F.sort !== order) {   // 排序:按日期重排段落,段内按 key 重排
        order = F.sort;
        var secs = sections.slice().sort(function (a, b) { return a.dataset.date < b.dataset.date ? -1 : 1; });
        if (order === 'new') secs.reverse();
        secs.forEach(function (s) {
          listEl.appendChild(s);
          var its = $$('.item', s).sort(function (a, b) { return cmp({ key: a.dataset.key }, { key: b.dataset.key }); });
          if (order === 'new') its.reverse();
          its.forEach(function (e) { s.appendChild(e); });
        });
      }
      var n = 0; lastMatched = [];
      items.forEach(function (it) {
        var ok = match(it, ws); it.el.hidden = !ok;
        if (ok) { n++; lastMatched.push(it); }
        highlight(it.el, ok ? ws : []);
      });
      sections.forEach(function (s) { s.hidden = !$('.item:not([hidden])', s); });
      if (empty) empty.hidden = n > 0;
      var active = F.q || F.topic || F.dir || F.st || F.from || F.to || F.src;
      if (status) status.textContent = active ? '匹配 ' + n + ' 条(共 ' + items.length + ' 条)' : '';
      if (cur && cur.hidden) select(null);
      syncURL(); updateCounters();
    };
    initFilters(false);
    $$('.item').forEach(applyCard);
    run(true);
  }

  // —— 杂志页(首页 / 往期 / 方向页):卡片只负责展示,详情在页内面板里;没有筛选
  function initMag() {
    items = $$('.item.tile').map(fromCard);
    $$('.item').forEach(applyCard);
    lastMatched = items;
    var ma = $('#markall'); if (ma) ma.addEventListener('click', function () { markAll(items); });
    updateCounters();
  }

  // —— 日页面:不筛选,默认展开,只有计数和批量已读
  function initDay() {
    items = $$('#list .item').map(fromCard);
    $$('.item').forEach(function (el) { applyCard(el); el.classList.add('open'); var t = $('.tog', el); if (t) { t.setAttribute('aria-expanded', 'true'); t.textContent = '收起'; } });
    lastMatched = items;
    var ma = $('#markall'); if (ma) ma.addEventListener('click', function () { markAll(items); });
    updateCounters();
  }

  // —— 搜索页:从 search-index.json 渲染
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  var TOPIC_CLS = function (d, i) { return 't-' + ((d.tc && d.tc[i] !== undefined) ? d.tc[i] : 0); };
  function renderCard(it) {
    var d = it.data, a;
    var el = h('article', 'item');
    el.dataset.id = it.id; el.dataset.sec = it.sec; el.dataset.dir = it.dir || ''; el.dataset.topics = it.topics.join('|'); el.dataset.date = it.date; el.dataset.key = it.key; el.dataset.source = it.source;
    var hd = h('div', 'ihead'), h3 = h('h3'); a = h('a', 'orig', d.title); a.href = d.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; h3.appendChild(a); hd.appendChild(h3);
    var st = h('button', 'star', '☆'); st.type = 'button'; st.setAttribute('aria-label', '收藏'); st.setAttribute('aria-pressed', 'false'); hd.appendChild(st); el.appendChild(hd);
    var meta = h('div', 'meta');
    var sl = h('span', 'chip seclabel', (SECS[d.sec] || d.sec)); meta.appendChild(sl);
    [d.source, d.sec === 'feeds' ? '发布:' + d.pub : '发布:' + d.pub].forEach(function (t) { meta.appendChild(h('span', '', t)); });
    if (d.ver) meta.appendChild(h('span', '', '适用版本:' + d.ver));
    if (d.sec !== 'feeds') meta.appendChild(h('span', '', '收录:' + d.date));
    el.appendChild(meta);
    var chips = h('div', 'chips'); if (d.dir) chips.appendChild(h('span', 'chip dir d-' + ['图形渲染', '游戏开发', 'AI 工具'].indexOf(d.dir), d.dir)); (d.topics || []).forEach(function (t, i) { chips.appendChild(h('span', 'chip ' + TOPIC_CLS(d, i), t)); }); el.appendChild(chips);
    el.appendChild(h('p', 'summary', d.summary || '(没有摘要,点“阅读原文”查看)'));
    var more = h('div', 'more');
    if (d.why) { var w = h('div', 'why'); w.appendChild(h('h4', '', '为什么有用')); w.appendChild(h('p', '', d.why)); more.appendChild(w); }
    if (d['try']) { var t1 = h('div', 'try'); t1.appendChild(h('h4', '', '值得试')); t1.appendChild(h('p', '', d['try'])); more.appendChild(t1); }
    if (d.tries && d.tries.length) { var t2 = h('div', 'try'); t2.appendChild(h('h4', '', '值得试的点')); var ul = h('ul'); d.tries.forEach(function (x) { ul.appendChild(h('li', '', x)); }); t2.appendChild(ul); more.appendChild(t2); }
    el.appendChild(more);
    var acts = h('div', 'acts');
    var oa = h('a', 'btn primary orig', '阅读原文 ↗'); oa.href = d.url; oa.target = '_blank'; oa.rel = 'noopener noreferrer'; acts.appendChild(oa);
    if (d.comments) { var ca = h('a', 'btn', '评论 ↗'); ca.href = d.comments; ca.target = '_blank'; ca.rel = 'noopener noreferrer'; acts.appendChild(ca); }
    if (d.page) { var pa = h('a', 'btn', '所在页面'); pa.href = ROOT + d.page; acts.appendChild(pa); }
    var tg = h('button', 'btn tog', '展开全文'); tg.type = 'button'; tg.setAttribute('aria-expanded', 'false'); acts.appendChild(tg);
    var rd = h('button', 'btn rd', '标记已读'); rd.type = 'button'; rd.setAttribute('aria-pressed', 'false'); acts.appendChild(rd);
    el.appendChild(acts);
    return el;
  }
  var SECS = { ue: 'UE 日报', picks: '每日精选', feeds: '订阅源' };
  function initSearch() {
    var listEl = $('#list'), empty = $('#empty'), status = $('#status'), moreBtn = $('#more'), PAGE = 40, shown = PAGE;
    fetch(ROOT + 'search-index.json').then(function (r) { return r.json(); }).then(function (idx) {
      items = idx.items.map(fromData);
      var have = {}; items.forEach(function (i) { have[i.id] = 1; });
      // 已收藏但不在索引里的(例如订阅源里已过期被清理的条目),用收藏时保存的快照补上
      Object.keys(state.star).forEach(function (id) {
        var s = state.snap[id]; if (have[id] || !s) return;
        items.push(fromData({ id: id, sec: s.sec || 'feeds', title: s.title, url: s.url, source: s.source, pub: s.pub || s.date, date: s.date || '',
          key: (s.date || '') + '|00', topics: s.topics || [], tc: s.tc || [], summary: s.summary || '' }));
      });
      var lastKey = '';
      run = function (keep) {
        if (!keep) readControls();
        var ws = words(), res = items.filter(function (it) { return match(it, ws); });
        res.sort(function (a, b) { return cmp(a, b); });
        if (F.sort === 'new') res.reverse();
        lastMatched = res;
        var sig = JSON.stringify([F, ws]);
        if (sig !== lastKey) { shown = PAGE; lastKey = sig; }
        listEl.innerHTML = ''; cur = null;
        var sec = null, secDate = '';
        res.slice(0, shown).forEach(function (it) {
          if (it.date !== secDate || !sec) {
            secDate = it.date; sec = h('section', 'issue'); sec.dataset.date = it.date;
            var h2 = h('h2', '', it.date); sec.appendChild(h2); listEl.appendChild(sec);
          }
          if (!it.el) it.el = renderCard(it);
          sec.appendChild(it.el); applyCard(it.el); highlight(it.el, ws);
        });
        empty.hidden = res.length > 0;
        moreBtn.hidden = res.length <= shown;
        var unread = res.filter(function (i) { return !isRead(i.id); }).length;
        status.textContent = '匹配 ' + res.length + ' 条(其中未读 ' + unread + ' 条;全站共 ' + items.length + ' 条)' + (res.length > shown ? ',已显示前 ' + shown + ' 条' : '');
        syncURL(); updateCounters();
      };
      moreBtn.addEventListener('click', function () { shown += PAGE; run(true); });
      initFilters(true);
      run(true);
    }).catch(function () { status.textContent = '搜索索引加载失败(直接用 file:// 打开时浏览器会拦截,请通过网址访问)。'; });
  }

  // ───────── 启动 ─────────
  if (KIND === 'search') initSearch();
  else if (KIND === 'mag') initMag();
  else if (KIND === 'day') initDay();
  else if ($('#list')) initStaticList();
  $$('.item').forEach(applyCard);
  // 导航上的未读角标
  try {
    fetch(ROOT + 'ids.json').then(function (r) { return r.json(); }).then(function (j) { ids = j; updateCounters(); }).catch(function () { updateCounters(); });
  } catch (e) {}
  updateCounters();
  // 深链 #a-<id>:选中并(在日页面/归档页)展开对应条目
  if (/^#a-/.test(location.hash)) {
    var target = document.getElementById(location.hash.slice(1));
    if (target && KIND !== 'mag') { select(target, true); if (!target.classList.contains('open')) toggleOpenSilent(target); }
    else if (target && KIND === 'mag') { select(target, true); }
  }
})();
