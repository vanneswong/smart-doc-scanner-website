# scripts

## indexnow.sh — IndexNow 自动提交

把站点 URL 批量推送给 Bing / Yandex 等支持 IndexNow 的搜索引擎，跳过长 sitemap 重新抓取等待。

### 前置条件

1. 仓库根目录存在 IndexNow 密钥文件：`<32位十六进制>.txt`，**文件名与内容必须完全一致**
   - 例如：`42d1883b2d654e86a37a660bbf8964bc.txt`
2. 该文件可公网访问：`https://<域名>/<密钥>.txt` 返回 200
3. 本机具备 `curl`、`python3`（仅用标准库）

### 常用命令

```bash
# 批量提交 sitemap.xml 中所有同域 URL（最常用）
./scripts/indexnow.sh

# 先预览，不真正发送
./scripts/indexnow.sh --dry-run

# 只提交本次 git 改动涉及的页面（适合部署后自动调用）
./scripts/indexnow.sh --changed-only

# 提交指定 URL（可多次 --url）
./scripts/indexnow.sh --url https://smartscanner.zynotes.cn/features.html

# 单条 GET 提交（keyLocation 作为 URL 参数）
./scripts/indexnow.sh --single --url https://smartscanner.zynotes.cn/
```

### 全部参数

| 参数 | 说明 |
| --- | --- |
| `--url <URL>` | 指定要提交的 URL，可重复；指定后不再自动读取 sitemap |
| `--single` | 使用 GET 单条提交模式（要求恰好 1 条 URL） |
| `--changed-only` | 仅提交 git 本次改动涉及的 `.html` 页面 |
| `--host <HOST>` | 覆盖域名（默认从 sitemap 推断） |
| `--key <KEY>` | 覆盖密钥（默认自动查找密钥文件） |
| `--endpoint <URL>` | 覆盖提交端点，可重复（默认 `api.indexnow.org` + `www.bing.com`） |
| `--sitemap <PATH>` | 指定 sitemap 路径 |
| `--dry-run` | 只打印将要发送的请求，不发送 |
| `--quiet` | 简要输出 |
| `-h, --help` | 查看帮助 |

### 环境变量

```bash
export INDEXNOW_HOST=smartscanner.zynotes.cn
export INDEXNOW_KEY=42d1883b2d654e86a37a660bbf8964bc
```

### 状态码

| 状态码 | 含义 |
| --- | --- |
| 200 | 提交成功，密钥校验通过 |
| 202 | 已接受，密钥校验进行中 |
| 400 | 请求格式错误 |
| 403 | 密钥无效（文件内容与 key 不一致） |
| 422 | URL 与 host 不匹配，或密钥文件不可访问 |
| 429 | 请求过于频繁 |

### 部署后自动提交

可在发布流程末尾追加：

```bash
./scripts/indexnow.sh --changed-only || true
```

> 注意：一个域名的 URL 必须单独提交。`scanner.zynotes.cn`（应用域名）需要在它自己的根目录放置密钥文件后才能提交。

## build_article.py — 文章页生成

把 `articles/src/*.md` 渲染成站点风格的文章页 `articles/<slug>.html`。

```bash
python3 scripts/build_article.py                        # 渲染全部文章
python3 scripts/build_article.py articles/src/foo.md    # 渲染指定文章
```

Markdown 文件头支持 front matter：

```yaml
---
title: 文章标题
slug: mobile-doc-to-scanner
description: 150-160 字的 meta description（同时用于 OG / Twitter / JSON-LD）
date: 2026-11-28
author: vanneswong
reading_time: 15
tags: 深度长文, 实现原理, 部署
cover: images/01-cover.jpg
summary: 列表页与文章页顶部摘要
---
```

生成的文章页包含：与全站一致的导航/页脚、文章 hero（面包屑 + 标签 + 摘要 + 作者/日期/阅读时长）、
封面图、右侧粘性目录（桌面端）、阅读进度条、配图题注、相关阅读卡片，以及 Article / BreadcrumbList 结构化数据。

新增一篇文章的流程：

1. 把 Markdown 放到 `articles/src/<slug>.md`，配图放 `articles/images/`；
2. 运行 `python3 scripts/build_article.py`；
3. 在 `news.html` 复制一个 `<article class="news-feature">` 区块，改标题/摘要/链接；
4. 在 `sitemap.xml` 与 `llms.txt` 各加一条；
5. 运行 `./scripts/indexnow.sh` 提交索引。
