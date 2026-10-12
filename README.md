# UE 日报 + 每日精选 阅读站

静态站点(纯 HTML/CSS/JS,无需构建工具),内容来自 `data/issues/*.json`,由 `build.py`(仅 Python 3 标准库)生成。
主题:渲染 / HLOD / 移动端。界面简体中文,自适应手机,明暗主题可切换(默认跟随系统)。

静态站点(纯 HTML/CSS/JS,无需构建工具),由 `build.py`(仅 Python 3 标准库)从 JSON 数据生成。界面简体中文,自适应手机,明暗主题可切换(默认跟随系统)。
站点已发布在 GitHub Pages:<https://richardgist.github.io/ue-digest/>(仓库 `richardgist/ue-digest`)。

两个栏目,顶部导航可互相切换:

| 栏目 | 入口 | 内容 | 数据目录 | RSS |
|---|---|---|---|---|
| **UE 日报** | `/` | UE 渲染 / HLOD / 移动端优化资料,每条带适用版本、值得试的点 | `data/issues/` | `/feed.xml` |
| **每日精选** | `/picks/` | 通用的有用输入:效率方法、好用的工具、前沿信息(科技 / AI / 游戏开发 / 图形 / 编程) | `data/picks/` | `/picks/feed.xml` |

## 目录

| 路径 | 说明 |
|---|---|
| `data/issues/YYYY-MM-DD.json` | UE 日报每期数据(内容来源,请纳入版本管理) |
| `data/picks/YYYY-MM-DD.json` | 每日精选每天的数据(内容来源,请纳入版本管理) |
| `build.py` | 生成器,两个栏目一起生成 |
| `add_issue.py` | 校验并加入新一期 UE 日报,然后自动重建 |
| `add_pick.py` | 校验并加入一天的每日精选(URL 与往日重复会拒绝),然后自动重建 |
| `publish.sh` | 提交并推送到 GitHub Pages(令牌从环境变量 `GITHUB_PAGES_TOKEN` 读取,不落盘) |
| `config.json` | 站名、简介、`base_url`(RSS 用的绝对地址)、每日精选栏目名和简介 |
| `assets/style.css`, `assets/app.js` | 样式;主题切换、分类/主题筛选、关键词搜索(两个栏目共用) |
| `index.html`, `issues/`, `feed.xml`, `picks/` | 生成产物,不要手改 |

## UE 日报:新增一期

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

## 每日精选:新增一天

1. 写一个 JSON 文件(例如 `/tmp/pick.json`):

```json
{
  "date": "2026-10-13",
  "items": [
    {
      "title": "原文标题",
      "url": "https://example.com/post",
      "source": "来源名",
      "published": "2026-10-10",
      "category": "工具",
      "summary": "摘要(简体中文),只写原文能支撑的事实;自己没验证的要说明。",
      "why_useful": "一句话说明对你为什么有用。",
      "try_it": "可选:具体可以怎么试(命令、步骤)。"
    }
  ]
}
```

   - `category` 只能取 `效率`、`工具`、`前沿`。`try_it` 可省略,其余字段必填。
   - 发布日期原文没写时如实填 `原文未标注`,不要编造。每条 URL 必须真实打开验证过。
   - 文件名/`date` 用当天日期,同一天只能有一份。一天建议 4–5 条,宁缺毋滥。

2. 运行:

```bash
cd /workspace/ue-digest-site
python3 add_pick.py /tmp/pick.json                      # 校验 → 写入 data/picks/DATE.json → 重建
python3 add_pick.py /tmp/pick.json --force              # 覆盖同日期旧版本(修订用)
python3 add_pick.py /tmp/pick.json --allow-duplicates   # URL 与往日重复时只警告(一般不要用)
```

URL 会做规范化后跨天比对(忽略 `www.`、`#片段`、`utm_*` 参数、末尾 `/`),与往日重复默认拒绝且不写入任何文件;同一天内重复也会被拒绝。

## 修改/删除

直接编辑或删除 `data/issues/DATE.json` 或 `data/picks/DATE.json`,然后 `python3 build.py`(已删除的页面会被自动清理)。

## 本地预览

```bash
python3 -m http.server 8080 --bind 0.0.0.0   # 在本目录运行
# 打开 http://localhost:8080/  (UE 日报)  和  http://localhost:8080/picks/  (每日精选)
```

线上地址见上方。本地预览只是为了发布前检查,不是正式访问方式。

## 功能说明

- 首页(两个栏目一致):按日期倒序;每条显示来源、发布时间、摘要、原文链接。UE 日报还有适用版本和值得试的点;每日精选还有“为什么有用”和可选的“值得试”。
- 筛选 + 关键词搜索(多个词用空格,同时满足),纯客户端,状态写入 URL(`?topic=HLOD&q=nanite`),可分享。UE 日报按主题(渲染 / HLOD / 移动端)筛选,每日精选按分类(效率 / 工具 / 前沿)筛选。
- 每期/每天独立页面(`issues/DATE.html`、`picks/DATE.html`),带上一期/下一期(前一天/后一天)导航。
- RSS:`feed.xml`(UE 日报,最近 30 期)、`picks/feed.xml`(每日精选,最近 60 天)。`config.json` 的 `base_url` 必须是最终访问地址,否则 RSS 里的链接不对。

## 部署

站点发布在 GitHub Pages(`main` 分支根目录,仓库 `richardgist/ue-digest`)。发布:

```bash
cd /workspace/ue-digest-site
./publish.sh "提交说明"      # 需要环境变量 GITHUB_PAGES_TOKEN;只推送,令牌不写入文件或 remote
```

推送后 Pages 约 1 分钟更新。令牌过期或被撤销时推送会失败,需要用户重新授权。如果换到别的静态托管,把整个目录放上去,并把 `config.json` 的 `base_url` 改成真实地址后重新 `python3 build.py`。

## 每日例行任务步骤(自动化用)

**UE 日报**
1. 搜索并筛选最多 5 条资料,按 UE 日报格式写成 JSON(`date` 为当天日期),没有值得收录的就不写。
2. `python3 add_issue.py /tmp/issue.json`
3. `./publish.sh "第 DATE 期"`,等 Pages 更新后确认 `https://richardgist.github.io/ue-digest/issues/DATE.html` 返回 200。

**每日精选**
1. 在效率方法 / 好用的工具 / 前沿信息三类里搜索,选 4–5 条真正有用的;每条 URL 都要实际打开确认内容,摘要只写原文支撑的事实。
2. 按上面的格式写 `/tmp/pick.json`。
3. `python3 add_pick.py /tmp/pick.json`(重复会被拒绝,换一条)。
4. `./publish.sh "每日精选 DATE"`,等待约 1 分钟,确认 `https://richardgist.github.io/ue-digest/picks/` 和 `https://richardgist.github.io/ue-digest/picks/DATE.html` 都返回 200。
5. 在给用户的消息里附上当天页面链接和各条要点。
