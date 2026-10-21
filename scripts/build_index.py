#!/usr/bin/env python3
"""重建 BM25 索引（v2）：只收「用法文档」，排除运维/开发者内部文档。

v1 的问题：multi-backend/npu 那篇 NPU 安装文档在给几乎所有查询打分（BM25 长文档偏置）。
v2 改为白名单收录：
  - README_zh.md（模型列表、显存要求、快速上手）
  - docs/zh/quick_start.md
  - docs/zh/configuration/**（参数说明：training / data / model / inference / eval）
  - docs/zh/feature-guide/**（SFT / DPO / RM / 数据准备 / 模型导出 / 推理 / batching）
  - examples/README_zh.md
  - examples/**/*.yaml（示例配置）
"""
import glob
import json
import os
import re
import sys

import rank_bm25

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.text import tokenize  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")
ROOT = os.path.expanduser("~/llmloop/data/LlamaFactory-main")
OUT_DIR = os.path.expanduser("~/llmloop/data")

ALLOW_GLOBS = [
    "README_zh.md",
    "docs/zh/quick_start.md",
    "docs/zh/configuration/**/*.md",
    "docs/zh/feature-guide/**/*.md",
    "examples/README_zh.md",
]
# 只收「用户用法」示例，排除多机/昇腾/后端集成这类运维配置
EXAMPLE_DIRS = [
    "examples/train_lora",
    "examples/train_full",
    "examples/train_qlora",
    "examples/inference",
    "examples/merge_lora",
    "examples/extras",
]
# README 里这些段落是赞助/致谢，不含答案
SKIP_HEADING = re.compile(r"(亚马逊|引用|致谢|赞助|赞助商|Sponsor|贡献者|License|许可|Star|微信|公众号)")


def tokenize_legacy(text):
    """已废弃：改用 lib.text.tokenize（保留以免旧脚本报错）。"""
    return tokenize(text)


def chunk_markdown(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    chunks, stack, buf = [], [], []

    def flush():
        body = "\n".join(buf).strip()
        if len(body) >= 100:
            chunks.append({"heading": " > ".join(stack), "text": body})
        buf.clear()

    for line in lines:
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            flush()
            level = len(m.group(1))
            stack[:] = stack[: level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()

    out = []
    for c in chunks:
        if len(c["text"]) <= 800:
            out.append(c)
            continue
        cur = ""
        for p in re.split(r"\n\s*\n", c["text"]):
            if len(cur) + len(p) > 800 and cur:
                out.append({"heading": c["heading"], "text": cur.strip()})
                cur = ""
            cur += p + "\n\n"
        if cur.strip():
            out.append({"heading": c["heading"], "text": cur.strip()})
    return out


def chunk_yaml(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    rel = os.path.relpath(path, ROOT)
    if len(text) <= 1000:
        return [{"heading": rel, "text": text}]
    out, cur = [], ""
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            if cur.strip() and len(cur) > 350:
                out.append({"heading": rel, "text": cur.strip()})
                cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append({"heading": rel, "text": cur.strip()})
    return out


def main():
    md_files = []
    for g in ALLOW_GLOBS:
        md_files += glob.glob(os.path.join(ROOT, g), recursive=True)
    md_files = sorted(set(md_files))

    yaml_files = []
    for d in EXAMPLE_DIRS:
        yaml_files += glob.glob(os.path.join(ROOT, d, "**/*.yaml"), recursive=True)
    yaml_files = sorted(set(yaml_files))

    # ★ 在线文档站（readthedocs）
    web_files = sorted(glob.glob(os.path.join(OUT_DIR, "webdocs", "*.md")))

    print("收录 md   :", len(md_files))
    for p in md_files:
        print("   ", os.path.relpath(p, ROOT))
    print("收录 yaml :", len(yaml_files))
    print("收录 web  :", len(web_files))

    all_chunks = []
    for p in md_files:
        for c in chunk_markdown(p):
            if SKIP_HEADING.search(c["heading"]):
                continue
            c.update(source="doc", path=os.path.relpath(p, ROOT))
            all_chunks.append(c)
    for p in yaml_files:
        for c in chunk_yaml(p):
            c.update(source="example", path=os.path.relpath(p, ROOT))
            all_chunks.append(c)

    # ★ 在线文档站（readthedocs）——仓库里没有的关键页面：
    #   advanced/arguments（参数大全）、quantization、tuning_algorithms、model_support 等
    for p in web_files:
        for c in chunk_markdown(p):
            if SKIP_HEADING.search(c["heading"]):
                continue
            c.update(source="web", path="webdocs/" + os.path.basename(p))
            all_chunks.append(c)

    for i, c in enumerate(all_chunks):
        c["id"] = i

    with open(os.path.join(OUT_DIR, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    corpus = [tokenize(c["heading"] + "\n" + c["text"]) for c in all_chunks]
    meta = {
        "chunks": len(all_chunks),
        "doc_chunks": sum(1 for c in all_chunks if c["source"] == "doc"),
        "example_chunks": sum(1 for c in all_chunks if c["source"] == "example"),
        "web_chunks": sum(1 for c in all_chunks if c["source"] == "web"),
        "files": len(md_files) + len(yaml_files) + len(web_files),
        "avg_tokens": round(sum(len(t) for t in corpus) / max(len(corpus), 1), 1),
    }
    with open(os.path.join(OUT_DIR, "bm25_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print("\n=== 索引统计 ===")
    for k, v in meta.items():
        print("  %-15s %s" % (k, v))

    print("\n=== 按来源统计块数 ===")
    from collections import Counter

    for path, n in Counter(c["path"] for c in all_chunks).most_common(20):
        print("  %-52s %d" % (path, n))


if __name__ == "__main__":
    main()
