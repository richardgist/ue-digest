#!/usr/bin/env python3
"""静态站生成器:
  · 首页 index.html = 最新一期(当天每日精选 + UE 日报合刊,杂志版式);editions/ = 往期合刊;direction/ = 三个方向页;archive.html = 往期列表
  · UE 日报:读取 data/issues/*.json,生成 issues/index.html、issues/*.html、feed.xml
  · 每日精选:读取 data/picks/*.json,生成 picks/index.html、picks/YYYY-MM-DD.html、picks/feed.xml
仅依赖 Python 3 标准库。用法: python3 build.py
"""
import json, re, sys, html
from urllib.parse import urlsplit, parse_qsl, urlencode
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "data" / "issues"
OUT_ISSUES = ROOT / "issues"
PICKS_DIR = ROOT / "data" / "picks"
OUT_PICKS = ROOT / "picks"
CATEGORIES = ["效率", "工具", "前沿"]
TOPICS = ["渲染", "HLOD", "移动端"]
TZ = timezone(timedelta(hours=8))
REQUIRED_ITEM = ["title", "url", "source", "published", "ue_version", "summary", "try_points", "topics"]


def esc(s):
    return html.escape(str(s), quote=True)


def validate(data, name=""):
    """校验一期数据,返回错误列表。"""
    errs = []
    d = data.get("date")
    if not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        errs.append("date 必须是 YYYY-MM-DD")
    else:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            errs.append("date 不是有效日期")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errs.append("items 必须是非空数组")
        return errs
    for i, it in enumerate(items, 1):
        p = f"items[{i}]"
        if not isinstance(it, dict):
            errs.append(f"{p} 必须是对象"); continue
        for k in REQUIRED_ITEM:
            if k not in it:
                errs.append(f"{p} 缺少字段 {k}")
        for k in ("title", "url", "source", "published", "ue_version", "summary"):
            if k in it and (not isinstance(it[k], str) or not it[k].strip()):
                errs.append(f"{p}.{k} 必须是非空字符串")
        if isinstance(it.get("url"), str) and not re.match(r"https?://", it["url"]):
            errs.append(f"{p}.url 必须以 http(s):// 开头")
        tp = it.get("try_points")
        if "try_points" in it and (not isinstance(tp, list) or not all(isinstance(x, str) for x in tp)):
            errs.append(f"{p}.try_points 必须是字符串数组")
        to = it.get("topics")
        if "topics" in it:
            if not isinstance(to, list) or not to:
                errs.append(f"{p}.topics 必须是非空数组")
            else:
                bad = [t for t in to if t not in TOPICS]
                if bad:
                    errs.append(f"{p}.topics 含非法值 {bad},可选 {TOPICS}")
    return errs


def load_issues():
    issues = []
    for f in sorted(ISSUES_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        errs = validate(data, f.name)
        if not errs and f.stem != data["date"]:
            errs.append(f"文件名 {f.name} 与 date {data['date']} 不一致")
        if errs:
            sys.exit(f"[错误] {f.name}:\n  - " + "\n  - ".join(errs))
        issues.append(data)
    issues.sort(key=lambda x: x["date"], reverse=True)
    return issues


def chips(topics, link_prefix=None):
    return "".join(f'<span class="chip t-{TOPICS.index(t)}">{esc(t)}</span>' for t in topics)


def build_feed(issues, cfg):
    base = cfg["base_url"].rstrip("/") + "/"
    now = format_datetime(datetime.now(TZ))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f'<title>{esc(cfg["site_title"])}</title><link>{esc(base)}</link>',
           f'<description>{esc(cfg["site_description"])}</description><language>{esc(cfg["language"])}</language>',
           f'<lastBuildDate>{now}</lastBuildDate>',
           f'<atom:link href="{esc(base)}feed.xml" rel="self" type="application/rss+xml"/>']
    for iss in issues[:30]:
        d = datetime.strptime(iss["date"], "%Y-%m-%d").replace(hour=8, minute=42, tzinfo=TZ)
        link = f'{base}issues/{iss["date"]}.html'
        lis = "".join(
            f'<li><a href="{esc(it["url"])}">{esc(it["title"])}</a>({esc(it["source"])} · {esc(it["ue_version"])})<br>{esc(it["summary"])}</li>'
            for it in iss["items"])
        desc = f"<ul>{lis}</ul>"
        out.append(f'<item><title>第 {iss["date"]} 期({len(iss["items"])} 条)</title><link>{esc(link)}</link>'
                   f'<guid isPermaLink="true">{esc(link)}</guid><pubDate>{format_datetime(d)}</pubDate>'
                   f'<description>{esc(desc)}</description></item>')
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


# ───────────── 每日精选 ─────────────
REQUIRED_PICK = ["title", "url", "source", "published", "category", "summary", "why_useful"]


def norm_url(u):
    """用于跨天去重的 URL 规范化:小写 host、去 fragment/utm_*/末尾斜杠、http→https。"""
    p = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = p.path.rstrip("/") or "/"
    return f"{p.netloc.lower().removeprefix('www.')}{path}" + (("?" + urlencode(q)) if q else "")


def validate_picks(data):
    errs = []
    d = data.get("date")
    if not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        errs.append("date 必须是 YYYY-MM-DD")
    else:
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            errs.append("date 不是有效日期")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errs.append("items 必须是非空数组")
        return errs
    seen = {}
    for i, it in enumerate(items, 1):
        p = f"items[{i}]"
        if not isinstance(it, dict):
            errs.append(f"{p} 必须是对象"); continue
        for k in REQUIRED_PICK:
            if k not in it:
                errs.append(f"{p} 缺少字段 {k}")
        for k in REQUIRED_PICK + ["try_it"]:
            if k in it and (not isinstance(it[k], str) or not it[k].strip()):
                errs.append(f"{p}.{k} 必须是非空字符串" + ("(try_it 可整体省略)" if k == "try_it" else ""))
        if isinstance(it.get("url"), str):
            if not re.match(r"https?://", it["url"]):
                errs.append(f"{p}.url 必须以 http(s):// 开头")
            else:
                n = norm_url(it["url"])
                if n in seen:
                    errs.append(f"{p}.url 与 items[{seen[n]}] 重复")
                seen[n] = i
        if "direction" in it and it["direction"] not in ("图形渲染", "游戏开发", "AI 工具"):
            errs.append(f"{p}.direction 非法值 {it['direction']!r},可选 图形渲染 / 游戏开发 / AI 工具(可省略,省略时自动判定)")
        if "category" in it and it["category"] not in CATEGORIES:
            errs.append(f"{p}.category 非法值 {it['category']!r},可选 {CATEGORIES}")
        extra = set(it) - set(REQUIRED_PICK) - {"try_it", "direction"}
        if extra:
            errs.append(f"{p} 含未知字段 {sorted(extra)}")
    return errs


def load_picks():
    days = []
    if PICKS_DIR.exists():
        for f in sorted(PICKS_DIR.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            errs = validate_picks(data)
            if not errs and f.stem != data["date"]:
                errs.append(f"文件名 {f.name} 与 date {data['date']} 不一致")
            if errs:
                sys.exit(f"[错误] picks/{f.name}:\n  - " + "\n  - ".join(errs))
            days.append(data)
    days.sort(key=lambda x: x["date"], reverse=True)
    return days


def find_duplicates(data, days):
    """返回 [(item标题, url, 已出现的日期)]:data 中的 URL 若已出现在 days 里的其他日期。"""
    seen = {}
    for day in days:
        if day["date"] == data.get("date"):
            continue
        for it in day["items"]:
            seen.setdefault(norm_url(it["url"]), day["date"])
    return [(it["title"], it["url"], seen[norm_url(it["url"])])
            for it in data["items"] if norm_url(it["url"]) in seen]


def build_picks_feed(days, cfg):
    base = cfg["base_url"].rstrip("/") + "/picks/"
    title = cfg.get("picks_title", "每日精选")
    now = format_datetime(datetime.now(TZ))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f'<title>{esc(title)}</title><link>{esc(base)}</link>',
           f'<description>{esc(cfg.get("picks_description", ""))}</description><language>{esc(cfg["language"])}</language>',
           f'<lastBuildDate>{now}</lastBuildDate>',
           f'<atom:link href="{esc(base)}feed.xml" rel="self" type="application/rss+xml"/>']
    for d in days[:60]:
        dt = datetime.strptime(d["date"], "%Y-%m-%d").replace(hour=9, minute=0, tzinfo=TZ)
        link = f'{base}{d["date"]}.html'
        lis = "".join(
            f'<li>[{esc(it["category"])}] <a href="{esc(it["url"])}">{esc(it["title"])}</a>({esc(it["source"])})<br>'
            f'{esc(it["summary"])}<br>为什么有用:{esc(it["why_useful"])}</li>' for it in d["items"])
        out.append(f'<item><title>每日精选 {d["date"]}({len(d["items"])} 条)</title><link>{esc(link)}</link>'
                   f'<guid isPermaLink="true">{esc(link)}</guid><pubDate>{format_datetime(dt)}</pubDate>'
                   f'<description>{esc("<ul>" + lis + "</ul>")}</description></item>')
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


def build_picks(cfg):
    days = load_picks()
    OUT_PICKS.mkdir(exist_ok=True)
    keep = {"index.html"} | {f'{d["date"]}.html' for d in days}
    for old in OUT_PICKS.glob("*.html"):
        if old.name not in keep:
            old.unlink()
    (OUT_PICKS / "index.html").write_text(build_picks_index(days, cfg), encoding="utf-8")
    for n, d in enumerate(days):
        (OUT_PICKS / f'{d["date"]}.html').write_text(build_pick_day(d, n, days, cfg), encoding="utf-8")
    (OUT_PICKS / "feed.xml").write_text(build_picks_feed(days, cfg), encoding="utf-8")
    # 跨天重复只警告(add_pick.py 写入时会拒绝)
    for d in days:
        for title, url, first in find_duplicates(d, [x for x in days if x["date"] < d["date"]]):
            print(f"[警告] {d['date']} 的《{title}》与 {first} 重复:{url}")
    print(f"已生成:每日精选 {len(days)} 天,{sum(len(d['items']) for d in days)} 条 → picks/index.html, picks/*.html, picks/feed.xml")




# ═════════════ 统一的卡片 / 杂志版式 / 页面框架 ═════════════
import hashlib, random
from itertools import zip_longest

FEEDS_DIR = ROOT / "data" / "feeds"
FEEDS_STORE = FEEDS_DIR / "entries.json"
OUT_FEEDS = ROOT / "feeds"
OUT_EDITIONS = ROOT / "editions"
OUT_DIRS = ROOT / "direction"
FEED_TOPICS_DEFAULT = ["图形渲染", "游戏开发", "AI 工具"]
WEEKDAYS = "一二三四五六日"
SEC_NAMES = {"ue": "UE 日报", "picks": "每日精选", "feeds": "订阅源"}
LATEST = ""   # 最新一期日期,main() 里设置,用于页头日期

# 三个关注方向:(页面 slug, 名称)
DIRECTIONS = [("rendering", "图形渲染"), ("game", "游戏开发"), ("ai", "AI 工具")]
DIR_NAMES = [n for _, n in DIRECTIONS]
DIR_SLUG = {n: s for s, n in DIRECTIONS}
DIR_SUB = {"图形渲染": "渲染管线、光照、HLOD 与图形技术", "游戏开发": "引擎、玩法与移动端实战",
           "AI 工具": "AI 编码代理、模型与效率工具"}

_KW = {
    "图形渲染": ["渲染", "着色", "光追", "光线追踪", "全局光照", "光照", "纹理", "材质", "网格", "高斯泼溅", "高斯", "图形",
              "render", "shader", "gpu$", "ray trac", "path trac", "nanite", "lumen", "hlod", "gaussian", "splat", "vulkan",
              "directx", "dx12$", "graphics", "raster", "lod$", "mesh", "texture", "lighting", "draw call", "post-process", "rtx"],
    "游戏开发": ["游戏", "引擎", "玩家", "关卡", "移动端", "手游", "主机", "game", "unity", "unreal", "godot", "ue5$", "gameplay",
              "steam", "engine", "mobile", "android", "ios$", "epic"],
    "AI 工具": ["ai$", "agent", "代理", "大模型", "模型", "提示词", "编码", "编程", "llm$", "claude", "gpt", "codex", "copilot",
              "cursor", "mcp$", "openai", "anthropic", "gemini", "prompt", "coding", "worktree", "machine learning", "hugging"],
}


def _kw_rx(words):
    parts = []
    for w in words:
        exact = w.endswith("$")
        w = w.rstrip("$")
        if re.fullmatch(r"[a-z0-9 \-]+", w):
            parts.append(r"(?<![a-z0-9])" + re.escape(w) + (r"(?![a-z0-9])" if exact else ""))
        else:
            parts.append(re.escape(w))
    return re.compile("|".join(parts))


_KW_RX = {n: _kw_rx(ws) for n, ws in _KW.items()}


def direction_of(it, kind):
    """给一条内容判定方向(图形渲染 / 游戏开发 / AI 工具)。数据里有合法的 direction 字段时优先;
    否则按 topics / category 加关键词打分,实在判不出来时归到 AI 工具。"""
    ex = it.get("direction")
    if ex in DIR_NAMES:
        return ex
    title = it.get("title", "").lower()
    body = " ".join([it.get("summary", ""), it.get("why_useful", ""), " ".join(it.get("try_points", [])), it.get("try_it", "")]).lower()
    score = {n: 3 * len(set(rx.findall(title))) + len(set(rx.findall(body))) for n, rx in _KW_RX.items()}
    if kind == "ue":
        score["游戏开发"] = 0   # UE 日报里每条都带 Unreal / engine,关键词没有区分度,只看 topics
        tp = set(it.get("topics", []))
        if tp & {"渲染", "HLOD"}:
            score["图形渲染"] += 3
        else:
            score["游戏开发"] += 3
    elif kind == "picks":
        if it.get("category") in ("效率", "工具"):
            score["AI 工具"] += 1
    best = max(DIR_NAMES, key=lambda n: (score[n], -DIR_NAMES.index(n)))
    return best if score[best] > 0 else "AI 工具"


def item_id(url):
    """条目稳定 ID(URL 规范化后取 sha1 前 12 位);同一篇文章在不同栏目里 ID 相同,已读/收藏状态共用。"""
    return hashlib.sha1(norm_url(url).encode()).hexdigest()[:12]


def feed_topics(cfg=None):
    try:
        fc = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))
        return [g["topic"] for g in fc["groups"]]
    except Exception:  # noqa: BLE001
        return FEED_TOPICS_DEFAULT


# ───────────── 程序生成的装饰插图(不是截图,按标题哈希确定性生成) ─────────────
def _iso_art(rnd):
    s = rnd.choice([24, 28, 32]); w = s * 0.866; hh = s / 2
    n = rnd.randint(5, 8)
    cells = sorted(rnd.sample([(i, j) for i in range(4) for j in range(4)], n), key=lambda c: (c[0] + c[1], c[0]))
    acc = rnd.randrange(n)
    cubes = []
    for idx, (i, j) in enumerate(cells):
        hgt = rnd.randint(1, 3)
        for k in range(hgt):
            cubes.append(((i - j) * w, (i + j) * hh - k * s, idx == acc and k == hgt - 1))
    xs = [c[0] for c in cubes]; ys = [c[1] for c in cubes]
    minx, maxx = min(xs) - w, max(xs) + w
    miny, maxy = min(ys) - s, max(ys) + s
    sc = min(1.0, 250 / (maxx - minx), 150 / (maxy - miny))
    tx = 160 - (minx + maxx) / 2 * sc; ty = 100 - (miny + maxy) / 2 * sc
    out = [f'<g transform="translate({tx:.1f} {ty:.1f}) scale({sc:.3f})">']
    f = lambda v: f"{v:.1f}"
    for x, y, a in cubes:
        top = f"{f(x)},{f(y - s)} {f(x + w)},{f(y - hh)} {f(x)},{f(y)} {f(x - w)},{f(y - hh)}"
        lef = f"{f(x - w)},{f(y - hh)} {f(x)},{f(y)} {f(x)},{f(y + s)} {f(x - w)},{f(y + hh)}"
        rig = f"{f(x)},{f(y)} {f(x + w)},{f(y - hh)} {f(x + w)},{f(y + hh)} {f(x)},{f(y + s)}"
        ct, cl, cr = ("fd3", "fd", "fd2") if a else ("fc", "fb", "fa")
        out.append(f'<polygon class="{ct} e" points="{top}"/><polygon class="{cl} e" points="{lef}"/><polygon class="{cr} e" points="{rig}"/>')
    out.append("</g>")
    return "".join(out)


def _tile_art(rnd):
    cols, rows, sz, gap = 8, 5, 28, 6
    x0 = (320 - (cols * sz + (cols - 1) * gap)) / 2; y0 = (200 - (rows * sz + (rows - 1) * gap)) / 2
    c, r = 0, rnd.randrange(rows); path = [(c, r)]
    while c < cols - 1:
        if rnd.random() < 0.4:
            nr = r + rnd.choice([-1, 1])
            if 0 <= nr < rows and (c, nr) not in path:
                r = nr; path.append((c, r)); continue
        c += 1; path.append((c, r))
    pset = set(path); out = []
    for cc in range(cols):
        for rr in range(rows):
            x = x0 + cc * (sz + gap); y = y0 + rr * (sz + gap)
            if (cc, rr) in pset:
                out.append(f'<rect class="fa" x="{x:.0f}" y="{y:.0f}" width="{sz}" height="{sz}" rx="7"/>')
            else:
                v = rnd.random()
                if v < 0.42:
                    out.append(f'<rect class="fc" x="{x:.0f}" y="{y:.0f}" width="{sz}" height="{sz}" rx="7"/>')
                elif v < 0.56:
                    out.append(f'<rect class="fb" x="{x:.0f}" y="{y:.0f}" width="{sz}" height="{sz}" rx="7"/>')
                else:
                    out.append(f'<circle class="fb o" cx="{x + sz / 2:.0f}" cy="{y + sz / 2:.0f}" r="3"/>')
    (sc_, sr), (ec, er) = path[0], path[-1]
    out.append(f'<circle class="fd e" cx="{x0 + sc_ * (sz + gap) + sz / 2:.0f}" cy="{y0 + sr * (sz + gap) + sz / 2:.0f}" r="10"/>')
    out.append(f'<rect class="fd e" x="{x0 + ec * (sz + gap) + 5:.0f}" y="{y0 + er * (sz + gap) + 5:.0f}" width="{sz - 10}" height="{sz - 10}" rx="4" transform="rotate(45 {x0 + ec * (sz + gap) + sz / 2:.0f} {y0 + er * (sz + gap) + sz / 2:.0f})"/>')
    return "".join(out)


def _node_art(rnd):
    pts = [(40 + gx * 80 + rnd.randint(-18, 18), 38 + gy * 62 + rnd.randint(-14, 14)) for gx in range(4) for gy in range(3)]
    pts = rnd.sample(pts, rnd.randint(7, 10))
    edges = set()
    for i, (x, y) in enumerate(pts):
        near = sorted((j for j in range(len(pts)) if j != i), key=lambda j: (pts[j][0] - x) ** 2 + (pts[j][1] - y) ** 2)
        for j in near[:rnd.choice([1, 2])]:
            edges.add((min(i, j), max(i, j)))
    hub = rnd.randrange(len(pts)); acc = rnd.randrange(len(pts))
    out = []
    for i, j in sorted(edges):
        out.append(f'<line class="sb" x1="{pts[i][0]}" y1="{pts[i][1]}" x2="{pts[j][0]}" y2="{pts[j][1]}"/>')
    hx, hy = pts[hub]
    out.append(f'<circle class="sa o" cx="{hx}" cy="{hy}" r="30" fill="none"/>')
    for i, (x, y) in enumerate(pts):
        if i == hub:
            out.append(f'<circle class="fa e" cx="{x}" cy="{y}" r="17"/>')
        else:
            cl = "fd" if i == acc else rnd.choice(["fb", "fc", "fa", "fb"])
            out.append(f'<circle class="{cl} e" cx="{x}" cy="{y}" r="{rnd.randint(6, 12)}"/>')
    return "".join(out)


def cover_svg(seed, direction):
    """确定性的装饰插图:同一个标题永远得到同一张图。风格随方向:图形渲染=等轴方块,游戏开发=瓦片地图,AI 工具=节点网络。"""
    h = hashlib.sha1(("cover:" + seed).encode()).digest()
    rnd = random.Random(int.from_bytes(h[:8], "big"))
    pal = h[8] % 3
    bx, by, br = rnd.choice([60, 260]), rnd.randint(40, 160), rnd.randint(70, 100)
    art = {"图形渲染": _iso_art, "游戏开发": _tile_art}.get(direction, _node_art)(rnd)
    return (f'<svg class="art p{pal}" viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">'
            f'<rect class="bg" width="320" height="200"/><circle class="fc o" cx="{bx}" cy="{by}" r="{br}"/>{art}</svg>')


# ───────────── 条目:统一数据 → 列表卡片 / 杂志卡片 ─────────────
def item_attrs(c):
    text = " ".join([c["title"], c["source"], c["summary"], " ".join(c["topics"]), c["dir"], c["date"], c.get("plain_more", "")])
    return (f'data-id="{c["id"]}" data-sec="{c["sec"]}" data-topics="{esc("|".join(c["topics"]))}" data-dir="{esc(c["dir"])}" '
            f'data-date="{c["date"]}" data-key="{esc(c["key"])}" data-source="{esc(c["source"])}" data-text="{esc(text.lower())}"')


def dir_chip(c):
    return f'<span class="chip dir d-{DIR_NAMES.index(c["dir"])}">{esc(c["dir"])}</span>'


def card(c):
    """列表卡片(归档页、日页面、订阅源、搜索共用)。c: id sec topics dir date key title url source summary meta chips more comments"""
    com = f'<a class="btn" href="{esc(c["comments"])}" target="_blank" rel="noopener noreferrer">评论 ↗</a>' if c.get("comments") else ""
    meta = "".join(f"<span>{esc(m)}</span>" for m in c["meta"])
    return (
        f'<article class="item" id="a-{c["id"]}" {item_attrs(c)}>'
        f'<div class="ihead"><h3><a class="orig" href="{esc(c["url"])}" target="_blank" rel="noopener noreferrer">{esc(c["title"])}</a></h3>'
        f'<button type="button" class="star" aria-pressed="false" aria-label="收藏" title="收藏(s)">☆</button></div>'
        f'<div class="meta">{meta}</div><div class="chips">{dir_chip(c)}{c["chips"]}</div>'
        f'<p class="summary">{esc(c["summary"])}</p><div class="more">{c["more"]}</div>'
        f'<div class="acts"><a class="btn primary orig" href="{esc(c["url"])}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a>{com}'
        f'<button type="button" class="btn tog" aria-expanded="false">展开全文</button>'
        f'<button type="button" class="btn rd" aria-pressed="false">标记已读</button></div>'
        f'</article>'
    )


def tile(c, role, num=None, prefix="", show_date=False, cap=False):
    """杂志卡片。role: hero | side | two | grid。数据属性与列表卡片一致,所以已读/收藏/快捷键/计数全部共用。
    标题和“阅读全文/了解详情”在 JS 下打开页内详情面板(含完整摘要、为什么有用、值得试、阅读原文、收藏、已读);
    无 JS 时跳转到所在日页面的对应条目。"""
    href = f'{prefix}{c["page"]}#a-{c["id"]}'
    sec = esc(c["seclabel"]) + (f' · {c["date"][5:]}' if show_date else "")
    numh = f'<span class="num">{num:02d}</span>' if num else ""
    act = (f'<a class="btn-read open-detail" href="{href}">阅读全文</a>' if role == "hero"
           else f'<a class="more-link open-detail" href="{href}">了解详情 <span aria-hidden="true">›</span></a>')
    capt = '<span class="cap">装饰插图 · 程序生成</span>' if cap else ""
    meta = "".join(f"<span>{esc(m)}</span>" for m in c["meta"])
    summ = c["summary"] or "(没有摘要,点“阅读原文”查看)"
    return (
        f'<article class="item tile {role}" id="a-{c["id"]}" {item_attrs(c)}>'
        f'<div class="cwrap"><a class="cover open-detail" href="{href}" tabindex="-1" aria-hidden="true">{cover_svg(c["title"], c["dir"])}</a>{capt}</div>'
        f'<div class="tbody"><div class="kick"><span class="dir d-{DIR_NAMES.index(c["dir"])}">{esc(c["dir"])}</span><span class="sec">{sec}</span>{numh}</div>'
        f'<h3><a class="open-detail" href="{href}">{esc(c["title"])}</a></h3>'
        f'<p class="summary">{esc(summ)}</p>'
        f'<div class="tact">{act}<button type="button" class="star" aria-pressed="false" aria-label="收藏" title="收藏(s)">☆</button></div></div>'
        f'<div class="hid" hidden><a class="orig" href="{esc(c["url"])}" target="_blank" rel="noopener noreferrer">{esc(c["title"])}</a>'
        f'<div class="meta">{meta}</div><div class="chips">{dir_chip(c)}{c["chips"]}</div><div class="more">{c["more"]}</div></div>'
        f'</article>'
    )


def c_ue(it, date, seq):
    tps = "".join(f"<li>{esc(t)}</li>" for t in it["try_points"])
    more = f'<div class="try"><h4>值得试的点</h4><ul>{tps}</ul></div>' if tps else ""
    return dict(
        id=item_id(it["url"]), sec="ue", topics=it["topics"], dir=direction_of(it, "ue"), date=date, key=f"{date}|{99 - seq:02d}",
        title=it["title"], url=it["url"], source=it["source"], summary=it["summary"],
        meta=[it["source"], f'发布:{it["published"]}', f'适用版本:{it["ue_version"]}'],
        chips="".join(f'<span class="chip t-{TOPICS.index(t)}">{esc(t)}</span>' for t in it["topics"]),
        more=more, plain_more=" ".join([it["ue_version"]] + it["try_points"]),
        seclabel="UE 日报", page=f"issues/{date}.html")


def c_pick(it, date, seq):
    why = f'<div class="why"><h4>为什么有用</h4><p>{esc(it["why_useful"])}</p></div>'
    tr = f'<div class="try"><h4>值得试</h4><p>{esc(it["try_it"])}</p></div>' if it.get("try_it") else ""
    return dict(
        id=item_id(it["url"]), sec="picks", topics=[it["category"]], dir=direction_of(it, "picks"), date=date, key=f"{date}|{99 - seq:02d}",
        title=it["title"], url=it["url"], source=it["source"], summary=it["summary"],
        meta=[it["source"], f'发布:{it["published"]}'],
        chips=f'<span class="chip t-{CATEGORIES.index(it["category"])}">{esc(it["category"])}</span>',
        more=why + tr, plain_more=it["why_useful"] + " " + it.get("try_it", ""),
        seclabel=f'每日精选 · {it["category"]}', page=f"picks/{date}.html")


def c_feed(e, ftopics):
    day = e["date"][:10]
    ti = ftopics.index(e["topic"]) if e["topic"] in ftopics else 0
    d = e["topic"] if e["topic"] in DIR_NAMES else direction_of(dict(title=e["title"], summary=e.get("summary", "")), "feeds")
    return dict(
        id=item_id(e["link"]), sec="feeds", topics=[e["topic"]], dir=d, date=day, key=e["date"],
        title=e["title"], url=e["link"], source=e["source"], summary=e["summary"] or "(源里没有摘要,点“阅读原文”查看)",
        meta=[e["source"], "发布:" + e["date"][:16].replace("T", " ")],
        chips=f'<span class="chip t-{ti}">{esc(e["topic"])}</span>', more="", comments=e.get("comments"),
        seclabel=f'订阅源 · {e["source"]}', page="feeds/index.html")


ue_card = lambda it, date, seq: card(c_ue(it, date, seq))
pick_card = lambda it, date, seq: card(c_pick(it, date, seq))
feed_card = lambda e, ftopics: card(c_feed(e, ftopics))


def tools_html(*, kind, topics=(), sec_filter=False, sources=(), placeholder="搜索关键词:标题、摘要、来源…", topic_groups=None):
    """kind: list | search | day | mag。list/search 有完整筛选;day 只有计数和批量已读。"""
    counter = ('<span id="counter" class="counter">未读 <b id="unread">0</b> / 共 <b id="total">0</b></span>'
               '<span class="sp"></span><button type="button" id="markall" class="btn sm">全部标记已读</button>'
               '<button type="button" id="readmode" class="btn sm" aria-pressed="false">阅读模式</button>')
    if kind == "day":
        return f'<div class="tools"><div class="bar2">{counter}</div><p class="keys">快捷键:j / k 上下条 · o 打开原文 · e 展开 · s 收藏 · m 已读/未读</p></div>'
    topic_btns = ""
    if topic_groups:
        for label, ts in topic_groups:
            topic_btns += f'<span class="glabel">{esc(label)}</span>' + "".join(
                f'<button type="button" class="f" data-topic="{esc(t)}">{esc(t)}</button>' for t in ts)
    else:
        topic_btns = "".join(f'<button type="button" class="f" data-topic="{esc(t)}">{esc(t)}</button>' for t in topics)
    sec_btns = ""
    if sec_filter:
        sec_btns = ('<div class="filters" id="secf" role="group" aria-label="栏目筛选"><button type="button" class="f active" data-sec="">全部栏目</button>'
                    + "".join(f'<button type="button" class="f" data-sec="{k}">{v}</button>' for k, v in SEC_NAMES.items()) + "</div>")
    dir_btns = ('<div class="filters" id="dirf" role="group" aria-label="方向筛选"><button type="button" class="f active" data-dir="">全部方向</button>'
                + "".join(f'<button type="button" class="f" data-dir="{n}">{n}</button>' for n in DIR_NAMES) + "</div>")
    src_sel = ""
    if sources:
        src_sel = ('<label>来源 <select id="src"><option value="">全部来源</option>'
                   + "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sources) + "</select></label>")
    return (
        f'<div class="tools" id="tools"><input id="q" type="search" placeholder="{esc(placeholder)}" aria-label="搜索">{sec_btns}{dir_btns}'
        f'<div class="filters" id="topicf" role="group" aria-label="主题筛选"><button type="button" class="f active" data-topic="">全部主题</button>{topic_btns}</div>'
        '<div class="filters" id="statusf" role="group" aria-label="状态筛选"><button type="button" class="f active" data-st="">全部</button>'
        '<button type="button" class="f" data-st="unread">只看未读</button><button type="button" class="f" data-st="star">★ 已收藏</button></div>'
        f'<div class="bar2">{counter}</div>'
        f'<details class="adv"><summary>更多筛选与数据</summary><div class="advbody">'
        '<div class="row"><label>起始日期 <input type="date" id="from"></label><label>截止日期 <input type="date" id="to"></label>'
        f'<label>排序 <select id="sort"><option value="new">最新优先</option><option value="old">最早优先</option></select></label>{src_sel}'
        '<button type="button" id="resetf" class="btn sm">清除筛选</button></div>'
        f'{data_row()}'
        '</div></details>'
        '<p id="status" class="status" aria-live="polite"></p>'
        '<p class="keys">快捷键:j / k 上下条 · o 打开原文 · e 展开 · s 收藏 · m 已读/未读 · / 搜索</p></div>')


def data_row():
    return ('<div class="row data"><button type="button" id="export" class="btn sm">导出已读/收藏(JSON)</button>'
            '<button type="button" id="import" class="btn sm">导入(合并)</button><button type="button" id="importreplace" class="btn sm">导入(覆盖)</button>'
            '<input type="file" id="file" accept="application/json,.json" hidden></div>'
            '<p class="note">已读和收藏只保存在当前浏览器(localStorage)。换设备或换浏览器前先导出,到另一边导入即可同步。</p>')


LOGO = ('<svg class="logo" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="18" fill="currentColor"/>'
        '<g fill="none" stroke="var(--logofg)" stroke-width="2.2" stroke-linecap="round"><path d="M10.5 12.5a8.5 8.5 0 0 0 0 11"/><path d="M25.5 12.5a8.5 8.5 0 0 1 0 11"/>'
        '<path d="M14.2 15a4.6 4.6 0 0 0 0 6"/><path d="M21.8 15a4.6 4.6 0 0 1 0 6"/></g><circle cx="18" cy="18" r="1.9" fill="var(--logofg)"/></svg>')

TAB_OF = {"ue": "archive", "picks": "archive", "feeds": "feeds", "search": "search", "home": "home", "archive": "archive",
          "rendering": "rendering", "game": "game", "ai": "ai"}


def page(title, body, prefix, cfg, desc="", section="ue", kind="list", headline="", tabs_right="", extra_foot=""):
    """prefix: 当前页面到站点根的相对前缀。section: home | rendering | game | ai | feeds | search | archive | ue | picks。
    kind: list | day | search | mag。headline: 杂志页的大标题 HTML(列表页为空)。tabs_right: 标签栏右侧的小工具。"""
    brand = cfg.get("brand_name", "每日阅读"); brand_sub = cfg.get("brand_sub", "DAILY READER")
    desc = desc or cfg.get("site_description", "")
    tab = TAB_OF.get(section, "home")
    tabs = [("home", "本期精选", f"{prefix}index.html", "")]
    tabs += [(s, n, f"{prefix}direction/{s}.html", "") for s, n in DIRECTIONS]
    tabs += [("feeds", "订阅源", f"{prefix}feeds/index.html", '<span class="badge" data-badge="feeds" hidden></span>'),
             ("search", "搜索", f"{prefix}search.html", '<span class="badge sb" data-badge="star" hidden></span>'),
             ("archive", "往期", f"{prefix}archive.html", "")]
    tabs_html = "".join(f'<a href="{h}"{" class=\"cur\" aria-current=\"page\"" if k == tab else ""}>{n}{b}</a>' for k, n, h, b in tabs)
    d = LATEST.replace("-", ".") if LATEST else ""
    foot = (f'<div class="foot-row"><span>每日更新 · 图形渲染 / 游戏开发 / AI 工具</span>'
            f'<span class="flinks">订阅 RSS:<a href="{prefix}feed.xml">UE 日报</a><a href="{prefix}picks/feed.xml">每日精选</a><a href="{prefix}feeds/feed.xml">订阅源聚合</a></span></div>'
            f'<div class="foot-row"><span class="flinks">归档:<a href="{prefix}picks/index.html">每日精选(可筛选)</a><a href="{prefix}issues/index.html">UE 日报(可筛选)</a>'
            f'<a href="{prefix}archive.html">全部往期</a></span></div>{extra_foot}')
    return f"""<!DOCTYPE html>
<html lang="{esc(cfg['language'])}" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="alternate" type="application/rss+xml" title="{esc(cfg["site_title"])}" href="{prefix}feed.xml">
<link rel="alternate" type="application/rss+xml" title="{esc(cfg.get("picks_title", "每日精选"))}" href="{prefix}picks/feed.xml">
<link rel="alternate" type="application/rss+xml" title="{esc(cfg.get("feeds_title", "订阅源"))}" href="{prefix}feeds/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 36 36%27%3E%3Ccircle cx=%2718%27 cy=%2718%27 r=%2718%27 fill=%27%231f5d4a%27/%3E%3Ccircle cx=%2718%27 cy=%2718%27 r=%273%27 fill=%27%23fff%27/%3E%3C/svg%3E">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>document.documentElement.classList.add('js');try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;if(localStorage.getItem('digest.reading')==='1')document.documentElement.classList.add('reading')}}catch(e){{}}</script>
</head>
<body data-root="{prefix}" data-kind="{kind}" data-section="{section}">
<header class="mast wrap">
<div class="mast-row">
<a class="brand" href="{prefix}index.html">{LOGO}<span class="bname"><b>{esc(brand)}</b><small>{esc(brand_sub)}</small></span></a>
<div class="mast-r"><span class="mdate">{d}</span><a class="arch" href="{prefix}archive.html">往期</a><button id="theme" type="button" aria-label="切换明暗主题" title="切换明暗主题">◐</button></div>
</div>
{headline}
<div class="tabrow"><nav class="tabs" aria-label="栏目">{tabs_html}</nav>{tabs_right}</div>
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">{foot}</footer>
<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def day_section(date, cards, heading_html, count):
    return (f'<section class="issue" data-date="{date}"><h2>{heading_html} <small>{count} 条</small></h2>{"".join(cards)}</section>')


# ───────────── 杂志版式(本期 / 往期某期 / 方向页) ─────────────
CN_NUM = {1: "一", 2: "两", 3: "三"}


def magazine(items, prefix, *, fill=(), archive_n=0, show_date=False, grid_title="继续阅读", eyebrow="KEEP EXPLORING", extra_grid=""):
    """items: 卡片数据列表(c dict)。第 1 条是头条,接着 3 条进“还有这三件事”,再 2 条双栏,其余 + fill 进“继续阅读”。"""
    if not items:
        return '<p class="empty">这一期还没有内容。</p>'
    hero, side, two, rest = items[0], items[1:4], items[4:6], list(items[6:])
    n = 1
    out = ['<div class="mag">']
    sd = ""
    if side:
        parts = []
        for c in side:
            n += 1
            parts.append(f'<li>{tile(c, "side", n, prefix, show_date)}</li>')
        sd = f'<aside class="side"><h2>还有这{CN_NUM.get(len(side), str(len(side)))}件事</h2><ol>{"".join(parts)}</ol></aside>'
    out.append(f'<div class="mag-top{"" if side else " solo"}">{tile(hero, "hero", 1, prefix, show_date, cap=True)}{sd}</div>')
    if two:
        parts = []
        for c in two:
            n += 1
            parts.append(tile(c, "two", n, prefix, show_date, cap=True))
        out.append(f'<div class="two-up{" one" if len(two) == 1 else ""}">{"".join(parts)}</div>')
    grid = []
    for c in rest:
        n += 1
        grid.append(tile(c, "grid", n, prefix, show_date))
    seen = {c["id"] for c in items}
    for c in fill:
        if len(grid) >= max(6, len(rest)):
            break
        if c["id"] not in seen:
            seen.add(c["id"]); grid.append(tile(c, "grid", None, prefix, True))
    if not grid and extra_grid:
        out.append(f'<section class="more-read nogrid">{extra_grid}</section>')
    elif grid:
        more = f'<a class="back-link" href="{prefix}archive.html">回看往期{f" · {archive_n} 期" if archive_n else ""} <span aria-hidden="true">›</span></a>'
        out.append(f'<section class="more-read"><div class="sechead"><div><span class="eyebrow">{eyebrow}</span><h2>{grid_title}</h2></div>{more}</div>'
                   f'<div class="grid">{"".join(grid)}</div>{extra_grid}</section>')
    out.append("</div>")
    return "".join(out)


def tabs_tools():
    return ('<div class="tabs-right"><span id="counter" class="counter">未读 <b id="unread">0</b> / 共 <b id="total">0</b></span>'
            '<button type="button" id="markall" class="tlink">全部已读</button>'
            '<button type="button" id="readmode" class="tlink" aria-pressed="false">阅读模式</button></div>')


def data_panel():
    return (f'<details class="adv datapanel"><summary>阅读数据:导出 / 导入已读与收藏</summary><div class="advbody">{data_row()}</div></details>'
            '<p class="keys">快捷键:j / k 上下条 · e / Enter 打开详情 · o 打开原文 · s 收藏 · m 已读/未读 · Esc 关闭</p>')


def zh_date(date):
    dt = datetime.strptime(date, "%Y-%m-%d")
    return f"{dt.year} 年 {dt.month} 月 {dt.day} 日 周{WEEKDAYS[dt.weekday()]}"


def build_editions_data(issues, days):
    """每个日期合成一期:每日精选与 UE 日报交替排列(这样头条 + 侧栏三条里两个栏目都有),按 id 去重。"""
    picks_by = {d["date"]: d["items"] for d in days}
    ue_by = {i["date"]: i["items"] for i in issues}
    eds = {}
    for date in sorted(set(picks_by) | set(ue_by), reverse=True):
        p = [c_pick(it, date, n) for n, it in enumerate(picks_by.get(date, []))]
        u = [c_ue(it, date, n) for n, it in enumerate(ue_by.get(date, []))]
        items, seen = [], set()
        for a, b in zip_longest(p, u):
            for c in (a, b):
                if c and c["id"] not in seen:
                    seen.add(c["id"]); items.append(c)
        eds[date] = dict(date=date, items=items, n_picks=len(p), n_ue=len(u))
    return eds


def edition_page(ed, ordered, idx, cfg, is_home):
    prefix = "" if is_home else "../"
    date = ed["date"]
    older = [c for e in ordered[idx + 1:] for c in e["items"]]
    head = ('<h1 class="hl">这一天，值得关注</h1>'
            f'<p class="sub">图形渲染 · 游戏开发 · AI 工具 动态<span class="sdate">{zh_date(date)} · {len(ed["items"])} 条'
            f'{"" if is_home else " · 往期"}</span></p>')
    nav = ""
    if not is_home:
        newer = ordered[idx - 1] if idx > 0 else None
        old = ordered[idx + 1] if idx + 1 < len(ordered) else None
        nav = ('<nav class="pager">' + (f'<a href="{old["date"]}.html">← 上一期 {old["date"]}</a>' if old else "<span></span>")
               + (f'<a href="{newer["date"]}.html">下一期 {newer["date"]} →</a>' if newer else "<span></span>") + "</nav>")
    day_links = ('<p class="daylinks">本期完整列表:'
                 + (f'<a href="{prefix}picks/{date}.html">每日精选 {ed["n_picks"]} 条</a>' if ed["n_picks"] else "")
                 + (f'<a href="{prefix}issues/{date}.html">UE 日报 {ed["n_ue"]} 条</a>' if ed["n_ue"] else "") + "</p>")
    body = magazine(ed["items"], prefix, fill=older, archive_n=len(ordered)) + day_links + nav + data_panel()
    title = f'{cfg.get("brand_name", "每日阅读")}' if is_home else f'{date} 期 - {cfg.get("brand_name", "每日阅读")}'
    return page(title, body, prefix, cfg, section="home" if is_home else "archive", kind="mag", headline=head, tabs_right=tabs_tools(),
                desc=f"{date} 期:" + "、".join(c["title"] for c in ed["items"][:3]))


def build_editions(eds, cfg):
    ordered = [eds[d] for d in sorted(eds, reverse=True)]
    OUT_EDITIONS.mkdir(exist_ok=True)
    keep = {f"{e['date']}.html" for e in ordered}
    for old in OUT_EDITIONS.glob("*.html"):
        if old.name not in keep:
            old.unlink()
    for i, e in enumerate(ordered):
        (OUT_EDITIONS / f'{e["date"]}.html').write_text(edition_page(e, ordered, i, cfg, False), encoding="utf-8")
    if ordered:
        (ROOT / "index.html").write_text(edition_page(ordered[0], ordered, 0, cfg, True), encoding="utf-8")
    print(f"已生成:首页(最新一期)+ {len(ordered)} 个往期页 → index.html, editions/*.html")
    return ordered


def build_directions(ordered, entries, cfg):
    OUT_DIRS.mkdir(exist_ok=True)
    ft = feed_topics(cfg)
    fcs = [c_feed(e, ft) for e in entries]
    for slug, name in DIRECTIONS:
        items = [c for e in ordered for c in e["items"] if c["dir"] == name][:24]
        feeds = [c for c in fcs if c["dir"] == name][:9]
        extra = ""
        if feeds:
            extra = (f'<div class="sechead sub2"><div><span class="eyebrow">FROM THE FEEDS</span><h2>订阅源动态</h2></div>'
                     f'<a class="back-link" href="../feeds/index.html?topic={name}">查看全部 <span aria-hidden="true">›</span></a></div>'
                     f'<div class="grid">{"".join(tile(c, "grid", None, "../", True) for c in feeds)}</div>')
        head = (f'<h1 class="hl">{name}</h1><p class="sub">{DIR_SUB[name]}<span class="sdate">'
                f'精选 {len(items)} 条{f" · 订阅源 {len(feeds)} 条" if feeds else ""}</span></p>')
        if items:
            body = magazine(items, "../", archive_n=len(ordered), show_date=True, grid_title="更多精选", eyebrow="MORE PICKS", extra_grid=extra)
        else:
            body = f'<div class="mag"><p class="empty">近期还没有「{name}」方向的精选。</p>{extra}</div>'
        body += (f'<p class="daylinks">在全站搜索里按方向筛选:<a href="../search.html?dir={name}">搜索「{name}」</a></p>' + data_panel())
        (OUT_DIRS / f"{slug}.html").write_text(
            page(f'{name} - {cfg.get("brand_name", "每日阅读")}', body, "../", cfg, section=slug, kind="mag", headline=head,
                 tabs_right=tabs_tools(), desc=DIR_SUB[name]), encoding="utf-8")
    print(f"已生成:方向页 {len(DIRECTIONS)} 个 → direction/*.html")


def build_archive(ordered, cfg):
    rows = []
    for e in ordered:
        d = datetime.strptime(e["date"], "%Y-%m-%d")
        hero = e["items"][0] if e["items"] else None
        cover = f'<a class="acover" href="editions/{e["date"]}.html" tabindex="-1" aria-hidden="true">{cover_svg(hero["title"], hero["dir"])}</a>' if hero else ""
        lis = "".join(f'<li><span class="dir d-{DIR_NAMES.index(c["dir"])}">{esc(c["dir"])}</span><a href="editions/{e["date"]}.html#a-{c["id"]}">{esc(c["title"])}</a></li>'
                      for c in e["items"][:4])
        more = f'<li class="amore">… 共 {len(e["items"])} 条</li>' if len(e["items"]) > 4 else ""
        links = ((f'<a href="picks/{e["date"]}.html">每日精选 {e["n_picks"]}</a>' if e["n_picks"] else "")
                 + (f'<a href="issues/{e["date"]}.html">UE 日报 {e["n_ue"]}</a>' if e["n_ue"] else ""))
        rows.append(f'<li class="arow"><a class="adate" href="editions/{e["date"]}.html"><b>{d.day:02d}</b><span>{d.year}.{d.month:02d} · 周{WEEKDAYS[d.weekday()]}</span></a>'
                    f'{cover}<div class="abody"><ul>{lis}{more}</ul><p class="ameta"><a class="open" href="editions/{e["date"]}.html">阅读本期 ›</a>{links}</p></div></li>')
    body = (f'<h1 class="title">往期</h1><p class="lead">共 {len(ordered)} 期。每期合并当天的每日精选与 UE 日报;完整列表(带筛选)见下面的归档入口。</p>'
            '<p class="arch-links"><a class="btn" href="picks/index.html">每日精选归档</a><a class="btn" href="issues/index.html">UE 日报归档</a>'
            '<a class="btn" href="feeds/index.html">订阅源</a><a class="btn" href="search.html">全站搜索 / 收藏</a></p>'
            f'<ol class="arch">{"".join(rows)}</ol>')
    (ROOT / "archive.html").write_text(page(f'往期 - {cfg.get("brand_name", "每日阅读")}', body, "", cfg, section="archive"), encoding="utf-8")
    print("已生成:archive.html")


# ───────────── UE 日报 / 每日精选 归档列表页与日页面 ─────────────
def build_index(issues, cfg):
    total = sum(len(i["items"]) for i in issues)
    secs = [day_section(iss["date"], [ue_card(it, iss["date"], n) for n, it in enumerate(iss["items"])],
                        f'<a href="{iss["date"]}.html">第 {iss["date"]} 期</a>', len(iss["items"])) for iss in issues]
    body = (f'<h1 class="title">{esc(cfg["site_title"])}</h1><p class="lead">{esc(cfg["site_description"])}。共 {len(issues)} 期 / {total} 条。</p>'
            + tools_html(kind="list", topics=TOPICS, placeholder="搜索关键词:标题、摘要、命令、版本…")
            + f'<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(f'{cfg["site_title"]} - {cfg.get("brand_name", "每日阅读")}', body, "../", cfg, section="ue")


def build_issue(iss, idx, issues, cfg):
    older = issues[idx + 1] if idx + 1 < len(issues) else None
    newer = issues[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 上一期 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">下一期 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(ue_card(it, iss["date"], n) for n, it in enumerate(iss["items"]))
    body = (f'<p class="crumb"><a href="index.html">← 全部期数</a> · <a href="../editions/{iss["date"]}.html">本日合订版</a></p><h1 class="title">第 {iss["date"]} 期</h1>'
            f'<p class="lead">本期 {len(iss["items"])} 条精选。</p>{tools_html(kind="day")}<section class="issue" id="list">{items}</section>{nav}')
    return page(f'第 {iss["date"]} 期 - {cfg["site_title"]}', body, "../", cfg, kind="day")


def build_picks_index(days, cfg):
    total = sum(len(d["items"]) for d in days)
    secs = [day_section(d["date"], [pick_card(it, d["date"], n) for n, it in enumerate(d["items"])],
                        f'<a href="{d["date"]}.html">{d["date"]}</a>', len(d["items"])) for d in days]
    body = (f'<h1 class="title">{esc(cfg.get("picks_title", "每日精选"))}</h1><p class="lead">{esc(cfg.get("picks_description", ""))}。共 {len(days)} 天 / {total} 条。</p>'
            + tools_html(kind="list", topics=CATEGORIES, placeholder="搜索关键词:标题、摘要、来源…")
            + f'<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(f'{cfg.get("picks_title", "每日精选")} - {cfg.get("brand_name", "每日阅读")}', body, "../", cfg, section="picks")


def build_pick_day(d, idx, days, cfg):
    older = days[idx + 1] if idx + 1 < len(days) else None
    newer = days[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 前一天 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">后一天 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(pick_card(it, d["date"], n) for n, it in enumerate(d["items"]))
    body = (f'<p class="crumb"><a href="index.html">← 全部精选</a> · <a href="../editions/{d["date"]}.html">本日合订版</a></p><h1 class="title">每日精选 {d["date"]}</h1>'
            f'<p class="lead">今日 {len(d["items"])} 条。</p>{tools_html(kind="day")}<section class="issue" id="list">{items}</section>{nav}')
    return page(f'每日精选 {d["date"]} - {cfg.get("brand_name", "每日阅读")}', body, "../", cfg, section="picks", kind="day")


# ───────────── 订阅源(外部 RSS/Atom 聚合) ─────────────
def load_feed_store():
    if FEEDS_STORE.exists():
        return json.loads(FEEDS_STORE.read_text(encoding="utf-8"))
    return {"updated": None, "status": {}, "entries": []}


def clean_entries(store):
    out = []
    for e in store.get("entries", []):
        if all(isinstance(e.get(k), str) and e[k] for k in ("title", "link", "date", "source", "topic")) and re.match(r"https?://", e["link"]):
            e = dict(e); e.setdefault("summary", ""); e["summary"] = e.get("summary") or ""
            out.append(e)
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def build_feeds_page(store, entries, cfg):
    ft = feed_topics(cfg)
    days = {}
    for e in entries:
        days.setdefault(e["date"][:10], []).append(e)
    secs = []
    for d in sorted(days, reverse=True):
        wd = WEEKDAYS[datetime.strptime(d, "%Y-%m-%d").weekday()]
        secs.append(day_section(d, [feed_card(e, ft) for e in days[d]], f"{d} 周{wd}", len(days[d])))
    upd = store.get("updated")
    st = store.get("status", {})
    rows = "".join(
        f'<li class="{"ok" if v.get("ok") else "bad"}"><b>{esc(n)}</b>({esc(v.get("topic", ""))}) '
        + ("✓ 正常" + (f',本次新增 {v.get("last_new", 0)} 条' if v.get("ok") else "") if v.get("ok") else f'✗ 失败:{esc(v.get("error", ""))}')
        + f' <span class="mute">检查于 {esc((v.get("checked") or "")[:16].replace("T", " "))}</span></li>' for n, v in st.items())
    status = f'<details class="feedstatus"><summary>订阅源状态({sum(1 for v in st.values() if v.get("ok"))}/{len(st)} 正常)</summary><ul>{rows}</ul></details>' if st else ""
    sources = sorted({e["source"] for e in entries})
    lead = (f'聚合 {len(st) or len(sources)} 个外部订阅源,保留最近约 {store.get("keep_days", 30)} 天,共 {len(entries)} 条;'
            f'最后更新 {esc((upd or "尚未抓取")[:16].replace("T", " "))}(北京时间)。外文条目保留原文标题与摘要。')
    body = (f'<h1 class="title">{esc(cfg.get("feeds_title", "订阅源"))}</h1><p class="lead">{lead}</p>{status}'
            + tools_html(kind="list", topics=ft, sources=sources, placeholder="搜索标题、摘要、来源…")
            + f'<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>{"没有匹配的内容。" if entries else "还没有抓取数据,运行 ./refresh_feeds.sh。"}</p>')
    return page(f'{cfg.get("feeds_title", "订阅源")} - {cfg.get("brand_name", "每日阅读")}', body, "../", cfg, section="feeds")


def build_feeds_rss(entries, cfg):
    base = cfg["base_url"].rstrip("/") + "/feeds/"
    title = cfg.get("feeds_title", "订阅源")
    now = format_datetime(datetime.now(TZ))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f'<title>{esc(title)}</title><link>{esc(base)}</link>',
           f'<description>{esc(cfg.get("feeds_description", ""))}</description><language>en</language>',
           f'<lastBuildDate>{now}</lastBuildDate>',
           f'<atom:link href="{esc(base)}feed.xml" rel="self" type="application/rss+xml"/>']
    for e in entries[:100]:
        dt = format_datetime(datetime.fromisoformat(e["date"]))
        out.append(f'<item><title>{esc(e["title"])}</title><link>{esc(e["link"])}</link>'
                   f'<guid isPermaLink="true">{esc(e["link"])}</guid><pubDate>{dt}</pubDate>'
                   f'<category>{esc(e["topic"])}</category><source url="{esc(base)}feed.xml">{esc(e["source"])}</source>'
                   f'<description>{esc(e["summary"])}</description></item>')
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


def build_feeds(cfg, store, entries):
    OUT_FEEDS.mkdir(exist_ok=True)
    (OUT_FEEDS / "index.html").write_text(build_feeds_page(store, entries, cfg), encoding="utf-8")
    (OUT_FEEDS / "feed.xml").write_text(build_feeds_rss(entries, cfg), encoding="utf-8")
    print(f"已生成:订阅源 {len(entries)} 条 → feeds/index.html, feeds/feed.xml")


# ───────────── 全站搜索页 + 搜索索引 ─────────────
def build_search_index(issues, days, entries, cfg):
    ft = feed_topics(cfg)
    items = []
    for iss in issues:
        for n, it in enumerate(iss["items"]):
            items.append(dict(id=item_id(it["url"]), sec="ue", title=it["title"], url=it["url"], source=it["source"],
                              pub=it["published"], date=iss["date"], key=f'{iss["date"]}|{99 - n:02d}', topics=it["topics"],
                              dir=direction_of(it, "ue"), tc=[TOPICS.index(t) for t in it["topics"]], summary=it["summary"], ver=it["ue_version"],
                              tries=it["try_points"], page=f'issues/{iss["date"]}.html'))
    for d in days:
        for n, it in enumerate(d["items"]):
            items.append(dict(id=item_id(it["url"]), sec="picks", title=it["title"], url=it["url"], source=it["source"],
                              pub=it["published"], date=d["date"], key=f'{d["date"]}|{99 - n:02d}', topics=[it["category"]],
                              dir=direction_of(it, "picks"), tc=[CATEGORIES.index(it["category"])], summary=it["summary"], why=it["why_useful"],
                              **({"try": it["try_it"]} if it.get("try_it") else {}), page=f'picks/{d["date"]}.html'))
    for e in entries:
        c = c_feed(e, ft)
        items.append(dict(id=c["id"], sec="feeds", title=e["title"], url=e["link"], source=e["source"],
                          pub=e["date"][:16].replace("T", " "), date=e["date"][:10], key=e["date"], topics=[e["topic"]], dir=c["dir"],
                          tc=[ft.index(e["topic"]) if e["topic"] in ft else 0], summary=e["summary"],
                          **({"comments": e["comments"]} if e.get("comments") else {}), page="feeds/index.html"))
    return {"generated": datetime.now(TZ).isoformat(timespec="minutes"), "secs": SEC_NAMES, "count": len(items), "items": items}


def build_search_page(cfg):
    ft = feed_topics(cfg)
    groups = [("UE 日报", TOPICS), ("每日精选", CATEGORIES), ("订阅源", ft)]
    body = ('<h1 class="title">搜索 / 收藏</h1><p class="lead">在 UE 日报、每日精选、订阅源的全部内容里统一搜索;也可以按方向筛选,或只看未读、已收藏(跨栏目)。</p>'
            + tools_html(kind="search", sec_filter=True, topic_groups=groups, placeholder="全文搜索:标题、摘要、来源、命令、版本…")
            + '<div id="list"></div><p id="empty" class="empty" hidden>没有匹配的内容。</p>'
              '<p class="center"><button type="button" id="more" class="btn" hidden>显示更多</button></p>')
    return page(f'搜索 / 收藏 - {cfg.get("brand_name", "每日阅读")}', body, "", cfg, section="search", kind="search")


def main():
    global LATEST
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    issues = load_issues()
    days = load_picks()
    LATEST = max([i["date"] for i in issues] + [d["date"] for d in days] or [""])
    OUT_ISSUES.mkdir(exist_ok=True)
    keep = {"index.html"} | {f'{i["date"]}.html' for i in issues}
    for old in OUT_ISSUES.glob("*.html"):
        if old.name not in keep:
            old.unlink()
    (OUT_ISSUES / "index.html").write_text(build_index(issues, cfg), encoding="utf-8")
    for n, iss in enumerate(issues):
        (OUT_ISSUES / f'{iss["date"]}.html').write_text(build_issue(iss, n, issues, cfg), encoding="utf-8")
    (ROOT / "feed.xml").write_text(build_feed(issues, cfg), encoding="utf-8")
    print(f"已生成:UE 日报 {len(issues)} 期,{sum(len(i['items']) for i in issues)} 条 → issues/index.html, issues/*.html, feed.xml")
    build_picks(cfg)
    store = load_feed_store()
    entries = clean_entries(store)
    build_feeds(cfg, store, entries)
    eds = build_editions_data(issues, days)
    ordered = build_editions(eds, cfg)
    build_directions(ordered, entries, cfg)
    build_archive(ordered, cfg)
    idx = build_search_index(issues, days, entries, cfg)
    (ROOT / "search-index.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "ids.json").write_text(json.dumps({
        "ue": [i["id"] for i in idx["items"] if i["sec"] == "ue"], "picks": [i["id"] for i in idx["items"] if i["sec"] == "picks"],
        "feeds": [i["id"] for i in idx["items"] if i["sec"] == "feeds"]}, separators=(",", ":")), encoding="utf-8")
    (ROOT / "search.html").write_text(build_search_page(cfg), encoding="utf-8")
    print(f"已生成:search.html, search-index.json({idx['count']} 条), ids.json")


if __name__ == "__main__":
    main()
