# UE 周报阅读站

静态站点(纯 HTML/CSS/JS,无需构建工具),内容来自 `data/issues/*.json`,由 `build.py`(仅 Python 3 标准库)生成。
主题:渲染 / HLOD / 移动端。界面简体中文,自适应手机,明暗主题可切换(默认跟随系统)。

## 目录

| 路径 | 说明 |
|---|---|
| `data/issues/YYYY-MM-DD.json` | 每期数据(唯一的内容来源,请纳入版本管理) |
| `build.py` | 生成器:`index.html`、`issues/*.html`、`feed.xml` |
| `add_issue.py` | 校验并加入新一期,然后自动重建 |
| `config.json` | 站名、简介、`base_url`(RSS 用的绝对地址,部署后改成真实地址) |
| `assets/style.css`, `assets/app.js` | 样式;主题切换、主题筛选、关键词搜索(手写,可直接改) |
| `index.html`, `issues/`, `feed.xml` | 生成产物,不要手改 |

## 新增一期

1. 写一个 JSON 文件(例如 `/tmp/issue.json`),格式:

```json
{
  "date": "2026-10-17",
  "items": [
    {
      "title": "原文标题",
      "url": "https://example.com/post",
      "source": "来源名",
      "published": "2026-10-01",
      "ue_version": "UE 5.8",
      "summary": "摘要,只写原文能支撑的事实;区分编辑器开销与运行时帧率等。",
      "try_points": ["值得试的点 1", "值得试的点 2"],
      "topics": ["HLOD", "渲染"]
    }
  ]
}
```

   - `topics` 只能取 `渲染`、`HLOD`、`移动端`(可多选)。
   - 版本或发布日期原文没写时,如实填 `原文未标注` / `约 2026-08`,不要编造。
   - 文件名/`date` 用该期发布日期,同一天只能有一期。

2. 运行:

```bash
cd /workspace/ue-digest-site
python3 add_issue.py /tmp/issue.json        # 校验 → 写入 data/issues/DATE.json → 重建
python3 add_issue.py /tmp/issue.json --force # 覆盖同日期旧版本(修订用)
```

校验失败会给出具体字段错误且不写入任何文件。也可以直接把 JSON 放进 `data/issues/` 后运行 `python3 build.py`。

## 修改/删除某一期

直接编辑或删除 `data/issues/DATE.json`,然后 `python3 build.py`(已删除期的页面会被自动清理)。

## 本地预览

```bash
python3 -m http.server 8080 --bind 0.0.0.0   # 在本目录运行
# 打开 http://localhost:8080/
```

## 功能说明

- 首页:按期倒序,每条显示来源、发布时间、适用版本、摘要、值得试的点和原文链接。
- 主题筛选 + 关键词搜索(多个词用空格,同时满足),纯客户端,状态写入 URL(`?topic=HLOD&q=nanite`),可分享。
- 每期独立页面 `issues/DATE.html`,带上一期/下一期导航。
- RSS:`feed.xml`(最近 30 期)。`config.json` 的 `base_url` 必须是最终访问地址,否则 RSS 里的链接不对。

## 部署(可选)

产物都是静态文件,把整个目录(或仅 `index.html`、`issues/`、`assets/`、`feed.xml`)放到任何静态托管即可,例如 GitHub Pages、Cloudflare Pages、Netlify 或自己的 Nginx。部署前先把 `config.json` 的 `base_url` 改成真实地址并重新 `python3 build.py`。

## 每周例行任务步骤(自动化用)

1. 搜索并筛选 5 条资料,按上面的格式写成 JSON(`date` 为当天日期)。
2. `python3 /workspace/ue-digest-site/add_issue.py /tmp/issue.json`
3. 确认输出 `已生成:N 期…`,并检查 `curl -s localhost:8080/issues/DATE.html` 有内容(服务没起就先启动)。
4. 在周报消息里附上本期链接。
