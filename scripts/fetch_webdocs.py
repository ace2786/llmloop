#!/usr/bin/env python3
"""抓取 LlamaFactory 在线中文文档站（readthedocs），转成 markdown 存本地。

为什么需要：
  仓库里的 docs/zh 只有 94 KB，是在线文档的简化版。
  在线站有 advanced/arguments（参数大全）、quantization、tuning_algorithms、
  model_support 等关键页面，仓库里根本没有。
  第 8.1 节也写明了在线版地址。

输出：data/webdocs/*.md
"""
from __future__ import annotations

import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://llamafactory.readthedocs.io/zh-cn/latest/"
OUT = Path(__file__).resolve().parent.parent / "data" / "webdocs"

PAGES = [
    "index.html",
    "getting_started/installation.html",
    "getting_started/data_preparation.html",
    "getting_started/sft.html",
    "getting_started/inference.html",
    "getting_started/eval.html",
    "getting_started/merge_lora.html",
    "getting_started/webui.html",
    "advanced/arguments.html",
    "advanced/model_support.html",
    "advanced/quantization.html",
    "advanced/acceleration.html",
    "advanced/trainers.html",
    "advanced/tuning_algorithms.html",
    "advanced/distributed.html",
    "advanced/monitor.html",
    "advanced/extras.html",
    "advanced/megatron_bridge.html",
    "advanced/best_practice/index.html",
]

SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "svg", "button", "form"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "tr", "br", "ul", "ol", "table", "blockquote"}


class MainExtractor(HTMLParser):
    """只提取 <article role="main"> 里的正文，转成 markdown 风格。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # 在 article 内部的嵌套深度
        self.in_article = False
        self.skip = 0
        self.out: list[str] = []
        self.pre = 0
        self.heading = 0
        self.buf: list[str] = []
        # 表格状态：按行累积单元格，每行输出一条 markdown 表格行
        self.in_table = False
        self.row: list[str] = []
        self.cell: list[str] | None = None

    # ---- 进入标签 ----
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article" and (a.get("role") == "main" or a.get("id") == "furo-main-content"):
            self.in_article = True
            self.depth = 1
            return
        if not self.in_article:
            return

        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return

        if tag == "table":
            self._flush()
            self.in_table = True
            self.out.append("\n")
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "pre":
            self.pre += 1
            self._flush()
            self.out.append("\n```\n")
        elif tag in ("h1", "h2", "h3", "h4"):
            self.heading = int(tag[1])
            self._flush()
        elif tag == "code" and not self.pre:
            self.buf.append("`")
        elif tag in BLOCK_TAGS and not self.in_table:
            self._flush()

    def handle_endtag(self, tag):
        if not self.in_article:
            return
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return

        if tag == "table":
            self._flush()
            self.in_table = False
            self.out.append("\n")
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr":
            if any(c for c in self.row):
                self.out.append("| " + " | ".join(self.row) + " |\n")
            self.row = []
        elif tag == "pre":
            self.pre = max(0, self.pre - 1)
            self._flush()
            self.out.append("\n```\n")
        elif tag in ("h1", "h2", "h3", "h4"):
            text = self._take()
            if text:
                self.out.append("\n" + "#" * self.heading + " " + text + "\n")
            self.heading = 0
        elif tag == "code" and not self.pre:
            self.buf.append("`")
        elif tag in BLOCK_TAGS and not self.in_table:
            self._flush()
        elif tag == "article":
            self._flush()
            self.in_article = False

    def handle_data(self, data):
        if not self.in_article or self.skip:
            return
        if self.pre:
            self.out.append(data)
            return
        t = re.sub(r"\s+", " ", data)
        if not t.strip():
            return
        if self.cell is not None:
            self.cell.append(t)
        elif not self.in_table:
            self.buf.append(t)

    # ---- 工具 ----
    def _take(self) -> str:
        t = "".join(self.buf).strip()
        self.buf = []
        return t

    def _flush(self):
        t = self._take()
        if t:
            self.out.append(t + "\n")

    def text(self) -> str:
        self._flush()
        s = "".join(self.out)
        s = re.sub(r"\n{3,}", "\n\n", s)
        s = re.sub(r"[ \t]{2,}", " ", s)
        return s.strip()


def fetch(url: str, retries: int = 3) -> str:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (doc-fetch)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            print(f"    重试 {i + 1}: {e}")
            time.sleep(2)
    return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    ok = 0

    for page in PAGES:
        url = BASE + page
        name = page.replace("/", "__").replace(".html", ".md")
        print(f"  {page} ...", end="", flush=True)

        html = fetch(url)
        if not html:
            print(" ✗ 抓取失败")
            continue

        p = MainExtractor()
        p.feed(html)
        text = p.text()

        if len(text) < 200:
            print(f" ✗ 正文太短（{len(text)} 字符），可能结构变了")
            continue

        (OUT / name).write_text(f"# 来源：{url}\n\n{text}\n", encoding="utf-8")
        total += len(text)
        ok += 1
        print(f" ✓ {len(text)} 字符")
        time.sleep(0.5)

    print()
    print("=" * 50)
    print(f"成功 {ok} / {len(PAGES)} 页，正文合计 {total} 字符（{total / 1024:.0f} KB）")
    print(f"输出目录：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
