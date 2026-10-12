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


def item_html(it, date, with_issue_link=False):
    tps = "".join(f"<li>{esc(t)}</li>" for t in it["try_points"])
    tries = f'<div class="try"><h4>值得试的点</h4><ul>{tps}</ul></div>' if tps else ""
    text = " ".join([it["title"], it["source"], it["summary"], it["ue_version"], " ".join(it["try_points"]), " ".join(it["topics"]), date])
    return (
        f'<article class="item" data-topics="{esc(" ".join(it["topics"]))}" data-text="{esc(text.lower())}">'
        f'<h3><a href="{esc(it["url"])}" target="_blank" rel="noopener noreferrer">{esc(it["title"])}</a></h3>'
        f'<div class="meta"><span>{esc(it["source"])}</span><span>发布:{esc(it["published"])}</span>'
        f'<span class="ver">适用版本:{esc(it["ue_version"])}</span></div>'
        f'<div class="chips">{chips(it["topics"])}</div>'
        f'<p class="summary">{esc(it["summary"])}</p>{tries}'
        f'<p class="src"><a href="{esc(it["url"])}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a></p>'
        f'</article>'
    )


def page(title, body, prefix, cfg, desc="", section="ue"):
    """prefix: 当前页面到站点根目录的相对前缀('' 或 '../')。section: 'ue' | 'picks'。"""
    if section == "picks":
        brand_name, brand_href = cfg.get("picks_title", "每日精选"), f"{prefix}picks/index.html"
        feed_href, feed_title = f"{prefix}picks/feed.xml", cfg.get("picks_title", "每日精选")
        foot = f'每日更新 · 分类:{" / ".join(CATEGORIES)} · <a href="{prefix}picks/feed.xml">订阅 RSS</a>'
        desc = desc or cfg.get("picks_description", "")
    else:
        brand_name, brand_href = cfg["site_title"], f"{prefix}index.html"
        feed_href, feed_title = f"{prefix}feed.xml", cfg["site_title"]
        foot = f'每日更新 · 主题:{" / ".join(TOPICS)} · <a href="{prefix}feed.xml">订阅 RSS</a>'
        desc = desc or cfg["site_description"]
    cur = lambda n: ' class="cur" aria-current="page"' if n == section else ""
    return f"""<!DOCTYPE html>
<html lang="{esc(cfg['language'])}" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="alternate" type="application/rss+xml" title="{esc(feed_title)}" href="{feed_href}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
</head>
<body>
<header class="top"><div class="wrap bar">
<a class="brand" href="{brand_href}">{esc(brand_name)}</a>
<nav><a href="{prefix}index.html"{cur("ue")}>UE 日报</a><a href="{prefix}picks/index.html"{cur("picks")}>每日精选</a><a href="{feed_href}">RSS</a><button id="theme" type="button" aria-label="切换明暗主题">🌓</button></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">{foot}</footer>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def build_index(issues, cfg):
    total = sum(len(i["items"]) for i in issues)
    filt = ('<div class="tools"><input id="q" type="search" placeholder="搜索关键词:标题、摘要、命令、版本…" aria-label="搜索">'
            '<div class="filters" role="group" aria-label="主题筛选"><button type="button" class="f active" data-topic="">全部</button>'
            + "".join(f'<button type="button" class="f" data-topic="{t}">{t}</button>' for t in TOPICS)
            + '</div><p id="status" class="status" aria-live="polite"></p></div>')
    secs = []
    for iss in issues:
        items = "".join(item_html(it, iss["date"]) for it in iss["items"])
        secs.append(
            f'<section class="issue" data-date="{iss["date"]}">'
            f'<h2><a href="issues/{iss["date"]}.html">第 {iss["date"]} 期</a> <small>{len(iss["items"])} 条</small></h2>'
            f'{items}</section>')
    body = (f'<h1 class="title">{esc(cfg["site_title"])}</h1><p class="lead">{esc(cfg["site_description"])}。'
            f'共 {len(issues)} 期 / {total} 条。</p>{filt}<div id="list">{"".join(secs)}</div>'
            '<p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(cfg["site_title"], body, "", cfg)


def build_issue(iss, idx, issues, cfg):
    older = issues[idx + 1] if idx + 1 < len(issues) else None
    newer = issues[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 上一期 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">下一期 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(item_html(it, iss["date"]) for it in iss["items"])
    body = (f'<p class="crumb"><a href="../index.html">← 全部期数</a></p><h1 class="title">第 {iss["date"]} 期</h1>'
            f'<p class="lead">本期 {len(iss["items"])} 条精选。</p><section class="issue">{items}</section>{nav}')
    return page(f'第 {iss["date"]} 期 - {cfg["site_title"]}', body, "../", cfg)


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


def pick_html(it, date):
    why = f'<div class="why"><h4>为什么有用</h4><p>{esc(it["why_useful"])}</p></div>'
    tr = f'<div class="try"><h4>值得试</h4><p>{esc(it["try_it"])}</p></div>' if it.get("try_it") else ""
    text = " ".join([it["title"], it["source"], it["summary"], it["why_useful"], it.get("try_it", ""), it["category"], date])
    return (
        f'<article class="item" data-topics="{esc(it["category"])}" data-text="{esc(text.lower())}">'
        f'<h3><a href="{esc(it["url"])}" target="_blank" rel="noopener noreferrer">{esc(it["title"])}</a></h3>'
        f'<div class="meta"><span>{esc(it["source"])}</span><span>发布:{esc(it["published"])}</span></div>'
        f'<div class="chips"><span class="chip t-{CATEGORIES.index(it["category"])}">{esc(it["category"])}</span></div>'
        f'<p class="summary">{esc(it["summary"])}</p>{why}{tr}'
        f'<p class="src"><a href="{esc(it["url"])}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a></p>'
        f'</article>'
    )


def build_picks_index(days, cfg):
    total = sum(len(d["items"]) for d in days)
    filt = ('<div class="tools"><input id="q" type="search" placeholder="搜索关键词:标题、摘要、来源…" aria-label="搜索">'
            '<div class="filters" role="group" aria-label="分类筛选"><button type="button" class="f active" data-topic="">全部</button>'
            + "".join(f'<button type="button" class="f" data-topic="{c}">{c}</button>' for c in CATEGORIES)
            + '</div><p id="status" class="status" aria-live="polite"></p></div>')
    secs = []
    for d in days:
        items = "".join(pick_html(it, d["date"]) for it in d["items"])
        secs.append(
            f'<section class="issue" data-date="{d["date"]}">'
            f'<h2><a href="{d["date"]}.html">{d["date"]}</a> <small>{len(d["items"])} 条</small></h2>{items}</section>')
    body = (f'<h1 class="title">{esc(cfg.get("picks_title", "每日精选"))}</h1>'
            f'<p class="lead">{esc(cfg.get("picks_description", ""))}。共 {len(days)} 天 / {total} 条。</p>'
            f'{filt}<div id="list">{"".join(secs)}</div><p id="empty" class="empty" hidden>没有匹配的内容。</p>')
    return page(f'{cfg.get("picks_title", "每日精选")} - {cfg["site_title"]}', body, "../", cfg, section="picks")


def build_pick_day(d, idx, days, cfg):
    older = days[idx + 1] if idx + 1 < len(days) else None
    newer = days[idx - 1] if idx > 0 else None
    nav = '<nav class="pager">' + (f'<a href="{older["date"]}.html">← 前一天 {older["date"]}</a>' if older else '<span></span>') \
        + (f'<a href="{newer["date"]}.html">后一天 {newer["date"]} →</a>' if newer else '<span></span>') + '</nav>'
    items = "".join(pick_html(it, d["date"]) for it in d["items"])
    body = (f'<p class="crumb"><a href="index.html">← 全部精选</a></p><h1 class="title">每日精选 {d["date"]}</h1>'
            f'<p class="lead">今日 {len(d["items"])} 条。</p><section class="issue">{items}</section>{nav}')
    return page(f'每日精选 {d["date"]} - {cfg["site_title"]}', body, "../", cfg, section="picks")


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


if __name__ == "__main__":
    main()
