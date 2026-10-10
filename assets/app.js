(function () {
  // 主题切换:auto → light → dark
  var root = document.documentElement, btn = document.getElementById('theme');
  if (btn) btn.addEventListener('click', function () {
    var cur = root.dataset.theme, dark = cur === 'dark' || (cur === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) {}
  });

  // 主题筛选 + 关键词搜索(纯客户端,基于页面里的 data-* 属性)
  var q = document.getElementById('q');
  if (!q) return;
  var items = [].slice.call(document.querySelectorAll('.item'));
  var issues = [].slice.call(document.querySelectorAll('section.issue'));
  var btns = [].slice.call(document.querySelectorAll('.f'));
  var status = document.getElementById('status'), empty = document.getElementById('empty');
  var topic = '';

  function apply() {
    var words = q.value.toLowerCase().split(/\s+/).filter(Boolean), n = 0;
    items.forEach(function (el) {
      var ok = (!topic || el.dataset.topics.split(' ').indexOf(topic) >= 0) &&
        words.every(function (w) { return el.dataset.text.indexOf(w) >= 0; });
      el.hidden = !ok; if (ok) n++;
    });
    issues.forEach(function (s) { s.hidden = !s.querySelector('.item:not([hidden])'); });
    empty.hidden = n > 0;
    status.textContent = (topic || words.length) ? '匹配 ' + n + ' 条' : '';
    var p = new URLSearchParams();
    if (topic) p.set('topic', topic);
    if (q.value) p.set('q', q.value);
    history.replaceState(null, '', p.toString() ? '?' + p : location.pathname);
  }
  btns.forEach(function (b) {
    b.addEventListener('click', function () {
      topic = b.dataset.topic;
      btns.forEach(function (x) { x.classList.toggle('active', x === b); });
      apply();
    });
  });
  q.addEventListener('input', apply);
  var p = new URLSearchParams(location.search);
  if (p.get('q')) q.value = p.get('q');
  if (p.get('topic')) {
    topic = p.get('topic');
    btns.forEach(function (x) { x.classList.toggle('active', x.dataset.topic === topic); });
  }
  apply();
})();
