#!/usr/bin/env python3
"""静态站生成器:读取 data/issues/*.json,生成 index.html、issues/*.html、feed.xml。
仅依赖 Python 3 标准库。用法: python3 build.py
"""
import json, re, sys, html
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "data" / "issues"
OUT_ISSUES = ROOT / "issues"
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


def page(title, body, prefix, cfg, desc=""):
    return f"""<!DOCTYPE html>
<html lang="{esc(cfg['language'])}" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or cfg['site_description'])}">
<link rel="alternate" type="application/rss+xml" title="{esc(cfg['site_title'])}" href="{prefix}feed.xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
</head>
<body>
<header class="top"><div class="wrap bar">
<a class="brand" href="{prefix}index.html">{esc(cfg['site_title'])}</a>
<nav><a href="{prefix}feed.xml">RSS</a><button id="theme" type="button" aria-label="切换明暗主题">🌓</button></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">每周更新 · 主题:{' / '.join(TOPICS)} · <a href="{prefix}feed.xml">订阅 RSS</a></footer>
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


if __name__ == "__main__":
    main()
