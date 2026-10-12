# UE 日报 + 每日精选 + 订阅源 阅读站

静态站点(纯 HTML/CSS/JS,无后端、无需构建工具),内容来自 `data/` 下的 JSON,由 `build.py`(仅 Python 3 标准库)生成。
界面简体中文,自适应手机,明暗主题可切换(默认跟随系统)。
已发布在 GitHub Pages:<https://richardgist.github.io/ue-digest/>(仓库 `richardgist/ue-digest`)。

## 版式与页面结构(杂志风)

整站采用暖白纸张底 + 深绿强调 + 中文衬线标题的“每日一期”杂志版式(参考用户给的“每日信号”截图的**视觉风格**,站名是我们自己的,在 `config.json` 的 `brand_name` / `brand_sub` 改)。
字体只用系统字体栈(Noto Serif SC / 思源宋体 / 宋体 / Georgia 兜底),无外部 CDN。

页头:圆形 logo + 站名 + 日期 + “往期”;大标题“这一天,值得关注”;标签栏 **本期精选 / 图形渲染 / 游戏开发 / AI 工具 / 订阅源 / 搜索 / 往期**。

| 页面 | 入口 | 内容 |
|---|---|---|
| **本期精选(首页)** | `/` | 最新一期:当天**每日精选 + UE 日报合刊**,精选与 UE 日报交替排序。第 1 条是头条(大图 + “阅读全文”),接着 3 条进右侧“还有这三件事”,再 2 条双栏,其余及上一期的补位条目进“继续阅读”。 |
| **往期合刊** | `/editions/YYYY-MM-DD.html` | 同样的版式,某一天的合刊,带上一期 / 下一期 |
| **方向页** | `/direction/rendering.html`、`game.html`、`ai.html` | 某方向跨期的精选(最多 24 条,杂志版式)+ 该方向的订阅源最新 9 条 |
| **往期** | `/archive.html` | 按日期列出每一期(封面、前几条标题、方向、当天两个栏目的完整列表链接) |
| **每日精选归档** | `/picks/`、`/picks/DATE.html` | 原来的列表视图:筛选 / 展开 / 搜索 / 已读 / 收藏 |
| **UE 日报归档** | `/issues/`、`/issues/DATE.html` | 同上(原先在 `/`,现在移到 `/issues/`) |
| **订阅源** | `/feeds/` | 外部 RSS/Atom 聚合,时间线 |
| **搜索 / 收藏** | `/search.html` | 三个栏目全部内容的统一搜索,新增“方向”筛选(`?dir=图形渲染`) |

- **方向(图形渲染 / 游戏开发 / AI 工具)**:每条内容自动判定,不改数据格式。规则:UE 日报按 topics(渲染 / HLOD → 图形渲染,否则 → 游戏开发);其余按标题(权重 3)和摘要里的关键词打分(见 `build.py` 里的 `_KW`),效率 / 工具类稍偏 AI 工具,都判不出来时归 AI 工具;订阅源直接用它所属的主题。
  想手动指定:在每日精选的某条里加可选字段 `"direction": "图形渲染"`(或 `游戏开发` / `AI 工具`);UE 日报的条目同样可以加这个可选字段。
- **插图**:我们没有文章配图,所以每条内容用**程序生成的装饰插图**(`build.py` 的 `cover_svg`,按标题哈希确定性生成 SVG,同一标题永远同一张;图形渲染 = 等轴方块,游戏开发 = 瓦片地图,AI 工具 = 节点网络)。图下标注“装饰插图 · 程序生成”,不冒充截图;暗色模式自动换配色。
- **页内详情面板**:首页 / 往期合刊 / 方向页上点标题、“阅读全文”或“了解详情”,会弹出详情面板(完整摘要、为什么有用、值得试、阅读原文、收藏、已读、上一篇 / 下一篇;`Esc` 关闭)。没有 JS 时链接会跳到对应日页面里的那一条(`#a-<id>`)。
- 杂志页上的“导出 / 导入”在页面底部“阅读数据”折叠面板里;列表页(归档、订阅源、搜索)的位置不变。

## 栏目与数据

| 栏目 | 数据 | RSS |
|---|---|---|
| **UE 日报** | `data/issues/` | `/feed.xml` |
| **每日精选** | `data/picks/` | `/picks/feed.xml` |
| **订阅源** | `data/feeds/entries.json`(由 `feeds.json` 配置) | `/feeds/feed.xml` |
| **搜索 / 收藏** | `search-index.json`(构建时生成) | — |

## 目录

| 路径 | 说明 |
|---|---|
| `data/issues/YYYY-MM-DD.json` | UE 日报每期数据(内容来源,请纳入版本管理) |
| `data/picks/YYYY-MM-DD.json` | 每日精选每天的数据(内容来源,请纳入版本管理) |
| `build.py` | 生成器,整站一起生成(含订阅源页、搜索页、`search-index.json`、`ids.json`) |
| `fetch_feeds.py` | 抓取 `feeds.json` 里的外部订阅源,去重后写入 `data/feeds/entries.json`(详见下文“订阅源”) |
| `refresh_feeds.sh` | **一条命令**:抓取订阅源 + 重建整站(不发布) |
| `feeds.json` | 外部订阅源配置(按主题分组) |
| `data/feeds/entries.json` | 订阅源滚动数据:最近约 30 天的条目 + 每个源的抓取状态(纳入版本管理) |
| `add_issue.py` | 校验并加入新一期 UE 日报,然后自动重建 |
| `add_pick.py` | 校验并加入一天的每日精选(URL 与往日重复会拒绝),然后自动重建 |
| `publish.sh` | 提交并推送到 GitHub Pages(令牌从环境变量 `GITHUB_PAGES_TOKEN` 读取,不落盘) |
| `config.json` | 站名(`brand_name` / `brand_sub`)、UE 日报标题与简介、`base_url`(RSS 用的绝对地址)、每日精选栏目名和简介 |
| `assets/style.css`, `assets/app.js` | 样式;所有页面共用的前端逻辑(见“阅读功能”) |
| `index.html`, `editions/`, `direction/`, `archive.html`, `issues/`, `feed.xml`, `picks/`, `feeds/`, `search.html`, `search-index.json`, `ids.json` | 生成产物,不要手改 |

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

## 阅读功能(前端,全部在浏览器里完成)

- **可展开卡片**:默认显示标题、来源、发布日期、主题标签、摘要前几行和醒目的“阅读原文 ↗”;点“展开全文”显示完整摘要、“为什么有用”、“值得试(的点)”、适用版本。每期/每天的独立页面默认全部展开。
- **阅读模式**(工具栏按钮,记在 localStorage):单栏、更大字号和行距、全部展开。
- **键盘快捷键**:`j` / `k` 下一条 / 上一条,`o` 打开原文(新标签,并标为已读),`e`(或 Enter)展开/收起,`s` 收藏,`m` 已读/未读切换,`/` 跳到搜索框,`Esc` 退出输入框。
- **已读 / 收藏**:每条有 ☆ 收藏和“标记已读 / 已读”按钮;展开或打开原文会自动标已读。状态按**文章 URL 的哈希**记录,所以同一篇文章出现在不同栏目里状态是共享的。
  - 只存在当前浏览器的 `localStorage`(键 `digest.state.v1`),**不同设备/浏览器之间不会自动同步**。
  - 工具栏“更多筛选与数据”里可以**导出为 JSON**,在另一台设备上**导入(合并)**(取并集,保留较新的时间戳)或**导入(覆盖)**。
  - 收藏时会保存一份条目快照,所以订阅源里已被清理的旧条目,收藏后仍能在“搜索 / 收藏”页看到。
  - 工具栏有“未读 N / 共 M”计数、“全部标记已读”(只作用于当前筛选结果,带 8 秒撤销);导航栏显示每个栏目的未读数和收藏总数。
- **筛选与搜索**(列表页和搜索页相同,可组合):关键词(空格分隔,全部命中;命中处高亮;命中折叠区内容时自动展开)、主题/分类、状态(全部 / 只看未读 / 已收藏)、起止日期、排序(最新 / 最早优先)、订阅源页还能按来源筛选。状态写入 URL(如 `?topic=HLOD&q=nanite&st=unread&sort=old`),可分享。
- **全站搜索页** `/search.html`:读取构建时生成的 `search-index.json`(三个栏目全部条目,含摘要、为什么有用、值得试的点),额外可按栏目筛选;结果先显示 40 条,可“显示更多”。
- **每期/每天独立页面**:`issues/DATE.html`、`picks/DATE.html`,带上一期/下一期导航。订阅源是时间线(按天分组),页面顶部可展开“订阅源状态”(各源是否抓取成功)。
- **RSS**:`feed.xml`(UE 日报,最近 30 期)、`picks/feed.xml`(每日精选,最近 60 天)、`feeds/feed.xml`(订阅源聚合,最近 100 条)。`config.json` 的 `base_url` 必须是最终访问地址,否则 RSS 里的链接不对。

## 订阅源(外部 RSS/Atom 聚合)

- 配置:`feeds.json`,按主题分组(图形渲染 / 游戏开发 / AI 工具),每个源 `{name, url}`,可选 `max_per_feed`(每次最多收录条数)、`keep_days`(该源保留天数);顶层 `keep_days`(默认 30)、`max_per_feed`(默认 15)。
- 抓取:`python3 fetch_feeds.py`(仅标准库,支持 RSS 2.0 / RSS 1.0 / Atom,处理 gzip、HTML 摘要清洗、写错的未来日期、`</feed>` 后被注入的垃圾内容)。
  - 按规范化 URL 去重(跨源也去重),只保留有可靠发布日期且在保留期内的条目,存到 `data/feeds/entries.json`(标题 / 链接 / 日期 / 摘要片段(≤500 字)/ 来源 / 主题)。
  - 某个源失败不影响其他源,也不会丢它已有的旧条目;失败原因记录在 `entries.json` 的 `status` 里并显示在订阅源页。所有源都失败时命令返回非 0。
  - 从 `feeds.json` 删掉的源,其条目在下次抓取时一并移除。
- 验证一个新源能不能用:`python3 fetch_feeds.py --check https://example.com/feed.xml`(不写文件)。加进 `feeds.json` 前务必先验证。
- 一条命令刷新并重建:`./refresh_feeds.sh`。然后发布:`./publish.sh "说明"`。
- 已知不可用/没收录:Arm 图形博客(没有公开 RSS)、Anthropic(原 RSS 地址 404)、realtimerendering.com(Cloudflare 拦截)。不要收录长期不更新的源(如 Interplay of Light、Bart Wronski)。

## 本地预览

```bash
python3 -m http.server 8080 --bind 0.0.0.0   # 在本目录运行
# 打开 http://localhost:8080/
```

线上地址见上方。本地预览只是为了发布前检查,不是正式访问方式。所有链接都是相对路径,放在任何子路径下都能用(`search.html` 需要通过 http 访问,`file://` 下浏览器会拦截它读取 JSON)。

## 部署

站点发布在 GitHub Pages(`main` 分支根目录,仓库 `richardgist/ue-digest`)。发布:

```bash
cd /workspace/ue-digest-site
./publish.sh "提交说明"      # 需要环境变量 GITHUB_PAGES_TOKEN;只推送,令牌不写入文件或 remote
```

推送后 Pages 约 1 分钟更新。令牌过期或被撤销时推送会失败,需要用户重新授权。如果换到别的静态托管,把整个目录放上去,并把 `config.json` 的 `base_url` 改成真实地址后重新 `python3 build.py`。

## 每日例行任务步骤(自动化用)

**每个例行任务,在 `publish.sh` 之前先加一步刷新订阅源(UE 日报和每日精选任何一个先跑都行,重复运行无副作用):**

```bash
cd /workspace/ue-digest-site && ./refresh_feeds.sh
```

(`add_issue.py` / `add_pick.py` 本身会重建站点但**不会**抓订阅源;`refresh_feeds.sh` 才会。抓取失败的源只会在输出里报 ✗,不应中断流程;只有输出“0 个源成功”或命令非 0 才需要在给用户的消息里提一句。)

**UE 日报**
1. 搜索并筛选最多 5 条资料,按 UE 日报格式写成 JSON(`date` 为当天日期),没有值得收录的就不写。
2. `python3 add_issue.py /tmp/issue.json`
3. `./refresh_feeds.sh`
4. `./publish.sh "第 DATE 期"`,等 Pages 更新后确认 `https://richardgist.github.io/ue-digest/issues/DATE.html` 返回 200。

**每日精选**
1. 在效率方法 / 好用的工具 / 前沿信息三类里搜索,选 4–5 条真正有用的(兼顾图形渲染、游戏开发、AI 工具);每条 URL 都要实际打开确认内容,摘要只写原文支撑的事实。
2. 按上面的格式写 `/tmp/pick.json`。
3. `python3 add_pick.py /tmp/pick.json`(重复会被拒绝,换一条)。
4. `./refresh_feeds.sh`
5. `./publish.sh "每日精选 DATE"`,等待约 1 分钟,确认 `https://richardgist.github.io/ue-digest/picks/`、`https://richardgist.github.io/ue-digest/picks/DATE.html`、`https://richardgist.github.io/ue-digest/feeds/` 都返回 200。
6. 在给用户的消息里附上当天页面链接和各条要点。
