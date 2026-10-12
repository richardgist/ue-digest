#!/usr/bin/env python3
"""抓取 feeds.json 里的外部 RSS/Atom 订阅源,去重后写入 data/feeds/entries.json(滚动保留最近 N 天)。
仅用 Python 3 标准库。某个源失败不会影响其他源,也不会丢掉它已有的旧条目。
用法:
  python3 fetch_feeds.py            # 抓取并更新 data/feeds/entries.json
  python3 fetch_feeds.py --check    # 只验证每个源能否抓取并解析,不写文件
  python3 fetch_feeds.py --check URL [URL...]   # 验证任意 URL(选新源用)
"""
import gzip, hashlib, html, json, re, sys, zlib
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urljoin

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "feeds.json"
STORE = ROOT / "data" / "feeds" / "entries.json"
TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (compatible; ue-digest-feed-reader/1.0; +https://richardgist.github.io/ue-digest/)"
SNIPPET = 500


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def text_of(el):
    return "".join(el.itertext()) if el is not None else ""


def clean(s, limit=None):
    """HTML → 纯文本(去标签、反转义、压缩空白)。"""
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(html.unescape(s)) if "&lt;" in s or "&amp;" in s else html.unescape(s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:，。；：") + "…" if " " in s[:limit] else s[:limit] + "…"
    return s


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
            if not m:
                return None
            d = datetime(int(m[1]), int(m[2]), int(m[3]))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    d = d.astimezone(TZ)
    if d > datetime.now(TZ) + timedelta(days=1):   # 源里偶尔有写错的未来日期,视为未知
        return None
    return d


def norm_url(u):
    p = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = p.path.rstrip("/") or "/"
    return f"{p.netloc.lower().removeprefix('www.')}{path}" + (("?" + urlencode(q)) if q else "")


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*;q=0.5",
        "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            data = gzip.decompress(data)
        elif enc == "deflate":
            data = zlib.decompress(data)
        return data, r.geturl()


def parse_feed(data, base):
    """解析 RSS 2.0 / RSS 1.0(RDF) / Atom,返回 (feed_title, [entry dict])。"""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # 去掉非法控制字符、以及根元素闭合标签之后的垃圾内容(有的站会在 </feed> 后注入 <script>)再试一次
        data = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", data)
        ends = list(re.finditer(rb"</(?:feed|rss|rdf:RDF)\s*>", data))
        if ends:
            data = data[: ends[-1].end()]
        root = ET.fromstring(data)
    kind = local(root.tag)
    if kind not in ("rss", "feed", "RDF"):
        raise ValueError(f"不是 RSS/Atom(根元素 {kind})")
    nodes = [e for e in root.iter() if local(e.tag) in ("item", "entry")]
    ftitle = ""
    holder = root.find("channel") if kind == "rss" else root
    for ch in (holder if holder is not None else []):
        if local(ch.tag) == "title":
            ftitle = clean(text_of(ch)); break
    out = []
    for n in nodes:
        f = {}
        links = []
        for ch in n:
            t = local(ch.tag)
            if t == "link":
                if ch.get("href"):
                    links.append((ch.get("rel") or "alternate", ch.get("href")))
                elif (ch.text or "").strip():
                    links.append(("alternate", ch.text.strip()))
            elif t == "guid" and (ch.text or "").strip().startswith("http") and ch.get("isPermaLink", "true") != "false":
                f.setdefault("guid", ch.text.strip())
            elif t in ("title", "pubDate", "published", "updated", "date", "comments"):
                f.setdefault(t, text_of(ch))
            elif t in ("description", "summary", "encoded", "content"):
                # content:encoded / content 通常是全文,优先 description/summary 做摘要;全文仅在没有摘要时用
                f.setdefault("sum_" + ("main" if t in ("description", "summary") else "full"), text_of(ch))
        alt = [h for r, h in links if r == "alternate"] or [h for r, h in links if r != "enclosure"]
        link = alt[0] if alt else f.get("guid", "")
        if not link:
            continue
        link = urljoin(base, link.strip())
        if not re.match(r"https?://", link):
            continue
        dt = parse_date(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        title = clean(f.get("title", ""))
        summ = clean(f.get("sum_main") or f.get("sum_full") or "", SNIPPET)
        m = re.match(r"Article URL: \S+ Comments URL: \S+ Points: (\d+) # Comments: (\d+)", summ)
        if m:   # Hacker News(hnrss)的固定格式 → 只留有用信息
            summ = f"Hacker News 热度:{m[1]} 分,{m[2]} 条评论"
        if not title:
            title = summ[:80] or link
        out.append({"title": title, "link": link, "date": dt.isoformat(timespec="minutes") if dt else None,
                    "summary": summ, "comments": (f.get("comments") or "").strip() or None})
    return ftitle, out


def eid(link):
    return hashlib.sha1(norm_url(link).encode()).hexdigest()[:12]


def fetch_one(feed):
    try:
        data, final = http_get(feed["url"])
        ftitle, entries = parse_feed(data, final)
        if not entries:
            raise ValueError("解析成功但没有条目")
        return feed, ftitle, entries, None
    except Exception as e:  # noqa: BLE001 — 单个源失败只记录
        return feed, "", [], f"{type(e).__name__}: {e}"


def load_config():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    feeds = []
    for g in cfg["groups"]:
        for f in g["feeds"]:
            feeds.append({**f, "topic": g["topic"]})
    return cfg, feeds


def main():
    args = sys.argv[1:]
    check = "--check" in args
    urls = [a for a in args if a != "--check"]
    if check and urls:
        for u in urls:
            _, t, es, err = fetch_one({"name": u, "url": u})
            print(("✗ " + err) if err else f"✓ {len(es)} 条,最新 {max((e['date'] or '') for e in es)[:10]}  《{t}》", u)
        return
    cfg, feeds = load_config()
    keep_days = int(cfg.get("keep_days", 30))
    now = datetime.now(TZ)
    old = {}
    status = {}
    if STORE.exists():
        st = json.loads(STORE.read_text(encoding="utf-8"))
        old = {e["id"]: e for e in st.get("entries", [])}
        status = st.get("status", {})
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(fetch_one, feeds))
    merged = dict(old)
    new_count = 0
    ok = bad = 0
    for feed, ftitle, entries, err in results:
        name = feed["name"]
        if err:
            bad += 1
            prev = status.get(name, {})
            status[name] = {**prev, "url": feed["url"], "topic": feed["topic"], "ok": False, "error": err,
                            "checked": now.isoformat(timespec="minutes")}
            print(f"✗ {name}: {err}")
            continue
        ok += 1
        cap = int(feed.get("max_per_feed", cfg.get("max_per_feed", 20)))
        dated = [e for e in entries if e["date"]]
        dated.sort(key=lambda e: e["date"], reverse=True)
        fcut = now - timedelta(days=int(feed.get("keep_days", keep_days)))
        picked = [e for e in dated if parse_date(e["date"]) >= fcut][:cap]   # 没有可靠日期的条目不收录
        n_new = 0
        for e in picked:
            i = eid(e["link"])
            rec = {"id": i, "title": e["title"], "link": e["link"], "summary": e["summary"], "source": name,
                   "topic": feed["topic"], "comments": e["comments"],
                   "date": e["date"] or (merged.get(i) or {}).get("date") or now.isoformat(timespec="minutes"),
                   "first_seen": (merged.get(i) or {}).get("first_seen") or now.isoformat(timespec="minutes")}
            if i not in merged:
                n_new += 1
            merged[i] = rec
        new_count += n_new
        status[name] = {"url": feed["url"], "topic": feed["topic"], "ok": True, "error": None, "title": ftitle,
                        "checked": now.isoformat(timespec="minutes"), "last_new": n_new}
        print(f"✓ {name}: 抓到 {len(entries)} 条,入库 {len(picked)} 条(新增 {n_new})")
    # 跨来源去重(同一链接只留一条,保留最早出现的),并清理超期
    final, seen = [], set()
    keep_by_name = {f["name"]: int(f.get("keep_days", keep_days)) for f in feeds}
    for e in sorted(merged.values(), key=lambda e: e["first_seen"]):
        d = parse_date(e["date"]) or now
        k = norm_url(e["link"])
        if d < now - timedelta(days=keep_by_name.get(e["source"], keep_days)) or k in seen:
            continue
        seen.add(k)
        final.append(e)
    names = {f["name"] for f in feeds}
    final = [e for e in final if e["source"] in names]          # 从配置里删掉的源,其条目一并移除
    status = {k: v for k, v in status.items() if k in names}
    final.sort(key=lambda e: e["date"], reverse=True)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    out = {"updated": now.isoformat(timespec="minutes"), "keep_days": keep_days, "status": status, "entries": final}
    STORE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"完成:{ok} 个源成功,{bad} 个失败;共保留 {len(final)} 条(本次新增 {new_count})→ {STORE.relative_to(ROOT)}")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
