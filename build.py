#!/usr/bin/env python3
"""静态站生成器:
  · UE 日报:读取 data/issues/*.json,生成 index.html、issues/*.html、feed.xml
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
        if "category" in it and it["category"] not in CATEGORIES:
            errs.append(f"{p}.category 非法值 {it['category']!r},可选 {CATEGORIES}")
        extra = set(it) - set(REQUIRED_PICK) - {"try_it"}
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




# ═════════════ 统一的卡片 / 页面框架 / 工具栏(UE 日报、每日精选、订阅源、搜索共用) ═════════════
import hashlib

FEEDS_DIR = ROOT / "data" / "feeds"
FEEDS_STORE = FEEDS_DIR / "entries.json"
OUT_FEEDS = ROOT / "feeds"
FEED_TOPICS_DEFAULT = ["图形渲染", "游戏开发", "AI 工具"]
WEEKDAYS = "一二三四五六日"
SEC_NAMES = {"ue": "UE 日报", "picks": "每日精选", "feeds": "订阅源"}


def item_id(url):
    """条目稳定 ID(URL 规范化后取 sha1 前 12 位);同一篇文章在不同栏目里 ID 相同,已读/收藏状态共用。"""
    return hashlib.sha1(norm_url(url).encode()).hexdigest()[:12]


def feed_topics(cfg=None):
    try:
        fc = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))
        return [g["topic"] for g in fc["groups"]]
    except Exception:  # noqa: BLE001
        return FEED_TOPICS_DEFAULT


def card(c):
    """c: id sec topics tcs date key title url source summary meta(list[str]) chips(html) more(html) comments"""
    text = " ".join([c["title"], c["source"], c["summary"], " ".join(c["topics"]), c["date"], c.get("plain_more", "")])
    com = f'<a class="btn" href="{esc(c["comments"])}" target="_blank" rel="noopener noreferrer">评论 ↗</a>' if c.get("comments") else ""
    meta = "".join(f"<span>{esc(m)}</span>" for m in c["meta"])
    return (
        f'<article class="item" data-id="{c["id"]}" data-sec="{c["sec"]}" data-topics="{esc("|".join(c["topics"]))}" '
        f'data-date="{c["date"]}" data-key="{esc(c["key"])}" data-source="{esc(c["source"])}" data-text="{esc(text.lower())}">'
        f'<div class="ihead"><h3><a class="orig" href="{esc(c["url"])}" target="_blank" rel="noopener noreferrer">{esc(c["title"])}</a></h3>'
        f'<button type="button" class="star" aria-pressed="false" aria-label="收藏" title="收藏(s)">☆</button></div>'
        f'<div class="meta">{meta}</div><div class="chips">{c["chips"]}</div>'
        f'<p class="summary">{esc(c["summary"])}</p><div class="more">{c["more"]}</div>'
        f'<div class="acts"><a class="btn primary orig" href="{esc(c["url"])}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a>{com}'
        f'<button type="button" class="btn tog" aria-expanded="false">展开全文</button>'
        f'<button type="button" class="btn rd" aria-pressed="false">标记已读</button></div>'
        f'</article>'
    )


def ue_card(it, date, seq):
    tps = "".join(f"<li>{esc(t)}</li>" for t in it["try_points"])
    more = f'<div class="try"><h4>值得试的点</h4><ul>{tps}</ul></div>' if tps else ""
    return card(dict(
        id=item_id(it["url"]), sec="ue", topics=it["topics"], date=date, key=f"{date}|{99 - seq:02d}",
        title=it["title"], url=it["url"], source=it["source"], summary=it["summary"],
        meta=[it["source"], f'发布:{it["published"]}', f'适用版本:{it["ue_version"]}'],
        chips="".join(f'<span class="chip t-{TOPICS.index(t)}">{esc(t)}</span>' for t in it["topics"]),
        more=more, plain_more=" ".join([it["ue_version"]] + it["try_points"])))


def pick_card(it, date, seq):
    why = f'<div class="why"><h4>为什么有用</h4><p>{esc(it["why_useful"])}</p></div>'
    tr = f'<div class="try"><h4>值得试</h4><p>{esc(it["try_it"])}</p></div>' if it.get("try_it") else ""
    return card(dict(
        id=item_id(it["url"]), sec="picks", topics=[it["category"]], date=date, key=f"{date}|{99 - seq:02d}",
        title=it["title"], url=it["url"], source=it["source"], summary=it["summary"],
        meta=[it["source"], f'发布:{it["published"]}'],
        chips=f'<span class="chip t-{CATEGORIES.index(it["category"])}">{esc(it["category"])}</span>',
        more=why + tr, plain_more=it["why_useful"] + " " + it.get("try_it", "")))


def feed_card(e, ftopics):
    day = e["date"][:10]
    ti = ftopics.index(e["topic"]) if e["topic"] in ftopics else 0
    return card(dict(
        id=item_id(e["link"]), sec="feeds", topics=[e["topic"]], date=day, key=e["date"],
        title=e["title"], url=e["link"], source=e["source"], summary=e["summary"] or "(源里没有摘要,点“阅读原文”查看)",
        meta=[e["source"], "发布:" + e["date"][:16].replace("T", " ")],
        chips=f'<span class="chip t-{ti}">{esc(e["topic"])}</span>', more="", comments=e.get("comments")))


def tools_html(*, kind, topics=(), sec_filter=False, sources=(), placeholder="搜索关键词:标题、摘要、来源…", topic_groups=None):
    """kind: list | search | day。list/search 有完整筛选;day 只有计数和批量已读。"""
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
    src_sel = ""
    if sources:
        src_sel = ('<label>来源 <select id="src"><option value="">全部来源</option>'
                   + "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sources) + "</select></label>")
    return (
        f'<div class="tools" id="tools"><input id="q" type="search" placeholder="{esc(placeholder)}" aria-label="搜索">{sec_btns}'
        f'<div class="filters" id="topicf" role="group" aria-label="主题筛选"><button type="button" class="f active" data-topic="">全部主题</button>{topic_btns}</div>'
        '<div class="filters" id="statusf" role="group" aria-label="状态筛选"><button type="button" class="f active" data-st="">全部</button>'
        '<button type="button" class="f" data-st="unread">只看未读</button><button type="button" class="f" data-st="star">★ 已收藏</button></div>'
        f'<div class="bar2">{counter}</div>'
        '<details class="adv"><summary>更多筛选与数据</summary><div class="advbody">'
        '<div class="row"><label>起始日期 <input type="date" id="from"></label><label>截止日期 <input type="date" id="to"></label>'
        f'<label>排序 <select id="sort"><option value="new">最新优先</option><option value="old">最早优先</option></select></label>{src_sel}'
        '<button type="button" id="resetf" class="btn sm">清除筛选</button></div>'
        '<div class="row data"><button type="button" id="export" class="btn sm">导出已读/收藏(JSON)</button>'
        '<button type="button" id="import" class="btn sm">导入(合并)</button><button type="button" id="importreplace" class="btn sm">导入(覆盖)</button>'
        '<input type="file" id="file" accept="application/json,.json" hidden></div>'
        '<p class="note">已读和收藏只保存在当前浏览器(localStorage)。换设备或换浏览器前先导出,到另一边导入即可同步。</p>'
        '</div></details>'
        '<p id="status" class="status" aria-live="polite"></p>'
        '<p class="keys">快捷键:j / k 上下条 · o 打开原文 · e 展开 · s 收藏 · m 已读/未读 · / 搜索</p></div>')


def page(title, body, prefix, cfg, desc="", section="ue", kind="list"):
    """prefix: 当前页面到站点根的相对前缀。section: ue | picks | feeds | search。kind: list | day | search。"""
    if section == "picks":
        brand_name, brand_href = cfg.get("picks_title", "每日精选"), f"{prefix}picks/index.html"
        feed_href, feed_title = f"{prefix}picks/feed.xml", cfg.get("picks_title", "每日精选")
        foot = f'每日更新 · 分类:{" / ".join(CATEGORIES)} · <a href="{prefix}picks/feed.xml">订阅 RSS</a>'
        desc = desc or cfg.get("picks_description", "")
    elif section == "feeds":
        brand_name, brand_href = cfg.get("feeds_title", "订阅源"), f"{prefix}feeds/index.html"
        feed_href, feed_title = f"{prefix}feeds/feed.xml", cfg.get("feeds_title", "订阅源")
        foot = f'聚合外部 RSS/Atom · 配置见 feeds.json · <a href="{prefix}feeds/feed.xml">订阅聚合 RSS</a>'
        desc = desc or cfg.get("feeds_description", "")
    else:
        brand_name, brand_href = cfg["site_title"], f"{prefix}index.html"
        feed_href, feed_title = f"{prefix}feed.xml", cfg["site_title"]
        foot = f'每日更新 · 主题:{" / ".join(TOPICS)} · <a href="{prefix}feed.xml">订阅 RSS</a>'
        desc = desc or cfg["site_description"]
    cur = lambda n: ' class="cur" aria-current="page"' if n == section else ""
    badge = lambda k: f'<span class="badge" data-badge="{k}" hidden></span>'
    return f"""<!DOCTYPE html>
<html lang="{esc(cfg['language'])}" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="alternate" type="application/rss+xml" title="{esc(feed_title)}" href="{feed_href}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27%3E%3Ctext y=%27.9em%27 font-size=%2790%27%3E📚%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>document.documentElement.classList.add('js');try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;if(localStorage.getItem('digest.reading')==='1')document.documentElement.classList.add('reading')}}catch(e){{}}</script>
</head>
<body data-root="{prefix}" data-kind="{kind}" data-section="{section}">
<header class="top"><div class="wrap bar">
<a class="brand" href="{brand_href}">{esc(brand_name)}</a>
<nav><a href="{prefix}index.html"{cur("ue")}>UE 日报{badge("ue")}</a><a href="{prefix}picks/index.html"{cur("picks")}>每日精选{badge("picks")}</a><a href="{prefix}feeds/index.html"{cur("feeds")}>订阅源{badge("feeds")}</a><a href="{prefix}search.html"{cur("search")}>搜索 / 收藏{badge("star")}</a><a class="rss" href="{feed_href}">RSS</a></nav><button id="theme" type="button" aria-label="切换明暗主题">🌓</button>
</div></header>
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


def build_index(issues, cfg):
    total = sum(len(i["items"]) for i in issues)
    secs = [day_section(iss["date"], [ue_card(it, iss["date"], n) for n, it in enumerate(iss["items"])],
                        f'<a href="issues/{iss["date"]}.html">第 {iss["date"]} 期</a>', len(iss["items"])) for iss in issues]
    body = (f'<h1 class="title">{esc(cfg["site_title"])}</h1><p class="lead">{esc(cfg["site_description"])}。共 {len(issues)} 期 / {total} 条。</p>'
            + tools_html(kind="list", topics=TOPICS, placeholder="搜索关键词:标题、摘要、命令、版本…")
            + f'<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(cfg["site_title"], body, "", cfg, section="ue")


def build_issue(iss, idx, issues, cfg):
    older = issues[idx + 1] if idx + 1 < len(issues) else None
    newer = issues[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 上一期 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">下一期 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(ue_card(it, iss["date"], n) for n, it in enumerate(iss["items"]))
    body = (f'<p class="crumb"><a href="../index.html">← 全部期数</a></p><h1 class="title">第 {iss["date"]} 期</h1>'
            f'<p class="lead">本期 {len(iss["items"])} 条精选。</p>{tools_html(kind="day")}<section class="issue" id="list">{items}</section>{nav}')
    return page(f'第 {iss["date"]} 期 - {cfg["site_title"]}', body, "../", cfg, kind="day")


def build_picks_index(days, cfg):
    total = sum(len(d["items"]) for d in days)
    secs = [day_section(d["date"], [pick_card(it, d["date"], n) for n, it in enumerate(d["items"])],
                        f'<a href="{d["date"]}.html">{d["date"]}</a>', len(d["items"])) for d in days]
    body = (f'<h1 class="title">{esc(cfg.get("picks_title", "每日精选"))}</h1><p class="lead">{esc(cfg.get("picks_description", ""))}。共 {len(days)} 天 / {total} 条。</p>'
            + tools_html(kind="list", topics=CATEGORIES, placeholder="搜索关键词:标题、摘要、来源…")
            + f'<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(f'{cfg.get("picks_title", "每日精选")} - {cfg["site_title"]}', body, "../", cfg, section="picks")


def build_pick_day(d, idx, days, cfg):
    older = days[idx + 1] if idx + 1 < len(days) else None
    newer = days[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 前一天 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">后一天 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(pick_card(it, d["date"], n) for n, it in enumerate(d["items"]))
    body = (f'<p class="crumb"><a href="index.html">← 全部精选</a></p><h1 class="title">每日精选 {d["date"]}</h1>'
            f'<p class="lead">今日 {len(d["items"])} 条。</p>{tools_html(kind="day")}<section class="issue" id="list">{items}</section>{nav}')
    return page(f'每日精选 {d["date"]} - {cfg["site_title"]}', body, "../", cfg, section="picks", kind="day")


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
    return page(f'{cfg.get("feeds_title", "订阅源")} - {cfg["site_title"]}', body, "../", cfg, section="feeds")


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
                              tc=[TOPICS.index(t) for t in it["topics"]], summary=it["summary"], ver=it["ue_version"],
                              tries=it["try_points"], page=f'issues/{iss["date"]}.html'))
    for d in days:
        for n, it in enumerate(d["items"]):
            items.append(dict(id=item_id(it["url"]), sec="picks", title=it["title"], url=it["url"], source=it["source"],
                              pub=it["published"], date=d["date"], key=f'{d["date"]}|{99 - n:02d}', topics=[it["category"]],
                              tc=[CATEGORIES.index(it["category"])], summary=it["summary"], why=it["why_useful"],
                              **({"try": it["try_it"]} if it.get("try_it") else {}), page=f'picks/{d["date"]}.html'))
    for e in entries:
        items.append(dict(id=item_id(e["link"]), sec="feeds", title=e["title"], url=e["link"], source=e["source"],
                          pub=e["date"][:16].replace("T", " "), date=e["date"][:10], key=e["date"], topics=[e["topic"]],
                          tc=[ft.index(e["topic"]) if e["topic"] in ft else 0], summary=e["summary"],
                          **({"comments": e["comments"]} if e.get("comments") else {}), page="feeds/index.html"))
    return {"generated": datetime.now(TZ).isoformat(timespec="minutes"), "secs": SEC_NAMES, "count": len(items), "items": items}


def build_search_page(cfg):
    ft = feed_topics(cfg)
    groups = [("UE 日报", TOPICS), ("每日精选", CATEGORIES), ("订阅源", ft)]
    body = ('<h1 class="title">搜索 / 收藏</h1><p class="lead">在 UE 日报、每日精选、订阅源的全部内容里统一搜索;也可以只看未读或已收藏(跨栏目)。</p>'
            + tools_html(kind="search", sec_filter=True, topic_groups=groups, placeholder="全文搜索:标题、摘要、来源、命令、版本…")
            + '<div id="list"></div><p id="empty" class="empty" hidden>没有匹配的内容。</p>'
              '<p class="center"><button type="button" id="more" class="btn" hidden>显示更多</button></p>')
    return page(f'搜索 / 收藏 - {cfg["site_title"]}', body, "", cfg, section="search", kind="search")


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    issues = load_issues()
    OUT_ISSUES.mkdir(exist_ok=True)
    keep = {f'{i["date"]}.html' for i in issues}
    for old in OUT_ISSUES.glob("*.html"):
        if old.name not in keep:
            old.unlink()
    (ROOT / "index.html").write_text(build_index(issues, cfg), encoding="utf-8")
    for n, iss in enumerate(issues):
        (OUT_ISSUES / f'{iss["date"]}.html').write_text(build_issue(iss, n, issues, cfg), encoding="utf-8")
    (ROOT / "feed.xml").write_text(build_feed(issues, cfg), encoding="utf-8")
    print(f"已生成:{len(issues)} 期,{sum(len(i['items']) for i in issues)} 条 → index.html, issues/, feed.xml")
    build_picks(cfg)
    store = load_feed_store()
    entries = clean_entries(store)
    build_feeds(cfg, store, entries)
    days = load_picks()
    idx = build_search_index(issues, days, entries, cfg)
    (ROOT / "search-index.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "ids.json").write_text(json.dumps({
        "ue": [i["id"] for i in idx["items"] if i["sec"] == "ue"], "picks": [i["id"] for i in idx["items"] if i["sec"] == "picks"],
        "feeds": [i["id"] for i in idx["items"] if i["sec"] == "feeds"]}, separators=(",", ":")), encoding="utf-8")
    (ROOT / "search.html").write_text(build_search_page(cfg), encoding="utf-8")
    print(f"已生成:search.html, search-index.json({idx['count']} 条), ids.json")


if __name__ == "__main__":
    main()
