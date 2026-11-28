#!/usr/bin/env python3
"""
把 articles/src/*.md 渲染成站点风格的文章页 articles/<slug>.html

用法:
    python3 scripts/build_article.py                     # 渲染 src 下全部文章
    python3 scripts/build_article.py articles/src/x.md   # 渲染指定文章

Markdown 约定（front matter）:
    ---
    title: 标题
    slug: mobile-doc-to-scanner
    description: 140-160 字的 meta description
    date: 2026-11-28
    author: vanneswong
    reading_time: 15
    tags: 深度长文, 实现原理
    cover: images/01-cover.jpg
    summary: 列表页与文章页顶部摘要
    ---

支持的 Markdown 子集：h2/h3、段落、有序/无序列表、图片、引用、代码块、
行内 **粗体** / `代码` / [链接](url)、水平线。
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "articles" / "src"
OUT_DIR = ROOT / "articles"
BASE_URL = "https://smartscanner.zynotes.cn"
SITE_NAME = "智能文档扫描 Smart Document Scanner"
AUTHOR_URL = "https://github.com/vanneswong"


# --------------------------------------------------------------------- 工具
def slugify_anchor(text: str) -> str:
    """把 h2 文本变成锚点 id（保留中文，去掉标点）。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-")
    return text or "section"


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, body


def inline(text: str) -> str:
    """行内元素：先转义，再还原 markdown 语法。"""
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    return text


# --------------------------------------------------------------------- 渲染
def render_body(md: str) -> tuple[str, list[tuple[str, str]]]:
    """返回 (HTML, [(锚点, 标题)])"""
    lines = md.splitlines()
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    para: list[str] = []
    anchors: set[str] = set()

    def flush_para() -> None:
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(
                "<pre><code%s>%s</code></pre>"
                % (cls, html.escape("\n".join(code_lines)))
            )
            continue

        # 空行
        if not stripped:
            flush_para()
            i += 1
            continue

        # 水平线
        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            flush_para()
            out.append('<hr class="article-hr">')
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{2,4})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            text = m.group(2).strip()
            anchor = slugify_anchor(text)
            base = anchor
            n = 2
            while anchor in anchors:
                anchor = f"{base}-{n}"
                n += 1
            anchors.add(anchor)
            if level == 2:
                toc.append((anchor, re.sub(r"[*`]", "", text)))
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            flush_para()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % inline(" ".join(quote)))
            continue

        # 图片（独占一行）
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)
        if m:
            flush_para()
            alt, src = m.group(1), m.group(2)
            out.append(
                '<figure class="article-figure">'
                f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy" decoding="async">'
                f"<figcaption>{inline(alt)}</figcaption>"
                "</figure>"
            )
            i += 1
            continue

        # 无序列表
        if re.match(r"^[-*]\s+", stripped):
            flush_para()
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>%s</ul>" % "".join(f"<li>{inline(x)}</li>" for x in items))
            continue

        # 有序列表
        if re.match(r"^\d+[.)]\s+", stripped):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+[.)]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>%s</ol>" % "".join(f"<li>{inline(x)}</li>" for x in items))
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out), toc


# --------------------------------------------------------------------- 模板
NAV = """  <header class="nav" id="nav">
    <div class="nav-inner">
      <a class="brand" href="../index.html">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/>
            <path d="M7 12h10M9 9h6M9 15h6"/>
          </svg>
        </div>
        <span class="brand-text">
          <strong>智能文档扫描</strong>
          <span>SMART DOCUMENT SCANNER</span>
        </span>
      </a>
      <nav class="nav-links" aria-label="主导航">
        <a href="../index.html">首页</a>
        <a href="../features.html">功能</a>
        <a href="../pipeline.html">处理管线</a>
        <a href="../deploy.html">部署</a>
        <a href="../api.html">API</a>
        <a href="../notes.html">说明</a>
        <a href="../news.html" class="active" aria-current="page">新闻</a>
      </nav>
      <a class="btn small primary" href="https://scanner.zynotes.cn/" target="_blank" rel="noopener">在线使用</a>
      <a class="btn small ghost" href="https://github.com/vanneswong/smart-doc-scanner" target="_blank" rel="noopener">GitHub</a>
    </div>
  </header>"""

FOOTER = """  <footer class="footer">
    <div class="footer-inner">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/>
            <path d="M7 12h10M9 9h6M9 15h6"/>
          </svg>
        </div>
        <span class="brand-text">
          <strong>智能文档扫描</strong>
          <span>SMART DOCUMENT SCANNER</span>
        </span>
      </div>
      <nav class="footer-nav" aria-label="页脚导航">
        <a href="../index.html">首页</a>
        <a href="../features.html">功能</a>
        <a href="../pipeline.html">处理管线</a>
        <a href="../deploy.html">部署</a>
        <a href="../api.html">API</a>
        <a href="../notes.html">说明</a>
        <a href="../news.html">新闻</a>
      </nav>
      <p>OpenCV 边缘检测 · 透视变换 · 自适应阈值 · 所有图片仅在本机临时保存</p>
      <p class="copyright">
        © 2026 <a href="https://github.com/vanneswong" target="_blank" rel="noopener">vanneseong</a>
        <span class="sep">·</span>
        <a href="https://github.com/vanneswong" target="_blank" rel="noopener">https://github.com/vanneswong</a>
      </p>
    </div>
  </footer>"""

RELATED = """      <section class="article-related">
        <h2>继续了解</h2>
        <div class="more-grid">
          <a class="more-card" href="../features.html">
            <strong>核心功能</strong>
            <span>17 项能力逐项说明：找边、透视、去阴影、白底扫描、去手写与导出。</span>
            <em>查看功能 →</em>
          </a>
          <a class="more-card" href="../deploy.html">
            <strong>部署指南</strong>
            <span>一个容器跑起来：腾讯云 TCR 镜像或 Docker Compose 本地构建。</span>
            <em>查看部署 →</em>
          </a>
        </div>
      </section>"""


def build_page(md_path: Path) -> Path:
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)

    title = meta.get("title") or md_path.stem
    slug = meta.get("slug") or md_path.stem
    desc = meta.get("description", "")
    date = meta.get("date", "")
    author = meta.get("author", "vanneswong")
    reading = meta.get("reading_time", "")
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    cover = meta.get("cover", "")
    summary = meta.get("summary", "")
    url = f"{BASE_URL}/articles/{slug}.html"

    body_html, toc = render_body(body_md)

    date_display = date
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date)
    if m:
        date_display = f"{m.group(1)} 年 {int(m.group(2))} 月 {int(m.group(3))} 日"

    j_title = json.dumps(title, ensure_ascii=False)
    j_desc = json.dumps(desc, ensure_ascii=False)
    j_tags = json.dumps(tags, ensure_ascii=False)

    tag_html = "".join(f'<span class="news-tag">{html.escape(t)}</span>' for t in tags)
    toc_html = "".join(
        f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc
    )

    cover_block = ""
    if cover:
        cover_block = (
            '    <div class="article-cover">\n'
            f'      <img src="{cover}" alt="{html.escape(title)}" width="1600" height="681">\n'
            "    </div>\n"
        )

    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f766e">
  <title>{html.escape(title)} - 智能文档扫描</title>
  <meta name="description" content="{html.escape(desc)}">
  <meta name="keywords" content="智能文档扫描,文档扫描,自动找边,透视校正,去阴影,白底扫描,去彩色手写,多页PDF,自托管,Docker">
  <meta name="robots" content="index,follow">
  <meta name="author" content="{html.escape(author)}">
  <link rel="canonical" href="{url}">
  <link rel="stylesheet" href="../style.css">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link rel="icon" href="../favicon-32x32.png" type="image/png" sizes="32x32">
  <link rel="icon" href="../favicon-16x16.png" type="image/png" sizes="16x16">
  <link rel="apple-touch-icon" href="../apple-touch-icon.png">

  <!-- Open Graph -->
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:locale" content="zh_CN">
  <meta property="og:image" content="{BASE_URL}/articles/{cover}">
  <meta property="article:published_time" content="{date}">
  <meta property="article:author" content="{html.escape(author)}">

  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(title)}">
  <meta name="twitter:description" content="{html.escape(desc)}">
  <meta name="twitter:image" content="{BASE_URL}/articles/{cover}">

  <!-- 结构化数据 -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@graph": [
      {{
        "@type": "Article",
        "@id": "{url}#article",
        "headline": {j_title},
        "description": {j_desc},
        "image": "{BASE_URL}/articles/{cover}",
        "datePublished": "{date}",
        "dateModified": "{date}",
        "inLanguage": "zh-CN",
        "author": {{ "@type": "Person", "name": "{author}", "url": "{AUTHOR_URL}" }},
        "publisher": {{ "@type": "Organization", "name": "{SITE_NAME}" }},
        "isPartOf": {{ "@id": "{BASE_URL}/#website" }},
        "about": {{ "@id": "{BASE_URL}/#application" }}
      }},
      {{
        "@type": "BreadcrumbList",
        "itemListElement": [
          {{ "@type": "ListItem", "position": 1, "name": "首页", "item": "{BASE_URL}/" }},
          {{ "@type": "ListItem", "position": 2, "name": "新闻", "item": "{BASE_URL}/news.html" }},
          {{ "@type": "ListItem", "position": 3, "name": {j_title}, "item": "{url}" }}
        ]
      }}
    ]
  }}
  </script>
</head>
<body>

  <div class="read-progress" id="readProgress" aria-hidden="true"></div>

{NAV}

  <main>
    <section class="article-hero">
      <div class="article-hero-inner">
        <nav class="breadcrumb" aria-label="面包屑">
          <a href="../index.html">首页</a><span class="sep">/</span><a href="../news.html">新闻</a><span class="sep">/</span><span>{html.escape(title)}</span>
        </nav>
        <div class="article-badges">{tag_html}</div>
        <h1>{html.escape(title)}</h1>
        <p class="article-summary">{html.escape(summary)}</p>
        <div class="article-meta">
          <span class="who">{html.escape(author)}</span>
          <time datetime="{date}">{date_display}</time>
          {f"<span>{reading} 分钟阅读</span>" if reading else ""}
          <span>Python 3.12 · FastAPI · OpenCV</span>
        </div>
      </div>
    </section>

{cover_block}
    <div class="article-layout">
      <article class="article-main">
        <div class="article-body">
{body_html}
        </div>

        <p class="article-end">本文截图与示例文档均由项目实际处理管线生成；示例公司、人名与合同内容均为虚构。</p>

        <div class="article-actions">
          <a class="btn ghost" href="../news.html">← 返回新闻列表</a>
          <a class="btn primary" href="https://scanner.zynotes.cn/" target="_blank" rel="noopener">在线试用</a>
        </div>

{RELATED}
      </article>

      <aside class="article-toc" aria-label="文章目录">
        <h2>目录</h2>
        <ol>
{toc_html}
        </ol>
      </aside>
    </div>
  </main>

{FOOTER}

  <script src="../app.js"></script>
</body>
</html>
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    args = sys.argv[1:]
    files = [Path(a) for a in args] if args else sorted(SRC_DIR.glob("*.md"))
    if not files:
        print("没有找到待渲染的 Markdown（articles/src/*.md）")
        return 1
    for f in files:
        out = build_page(f)
        print(f"✓ {f.name} -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
