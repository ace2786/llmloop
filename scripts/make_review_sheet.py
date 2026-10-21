#!/usr/bin/env python3
"""生成「候选题目核对表」——供人工逐条确认「答案能否在文档/示例配置里找到」。

核心改进：加入「参数名命中」信号。
  如果提问里出现的 snake_case 参数名（cutoff_len / save_steps / lora_target ...）
  真的出现在文档块里，那这道题的答案大概率就在那儿。

产出：
  data/review_sheet.md     人看的核对表
  data/review_sheet.json   机器读的
"""
import glob
import json
import os
import re

import jieba
import rank_bm25

CJK = re.compile(r"[\u4e00-\u9fff]")
DATA = os.path.expanduser("~/llmloop/data")
PARAM = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){1,3})\b")

OPS = re.compile(r"(NPU|昇腾|910|Ascend|MindSpore|多机|多卡|分布式|ray|deepspeed|fsdp|megatron|ktransformers|集群|卡住|卡死|hang)", re.I)
BUG = re.compile(r"(报错|错误|失败|OOM|显存不足|crash|Traceback|AssertionError|ValueError|TypeError|RuntimeError|ImportError|KeyError|IndexError|异常|崩溃|崩了|无法|不能用|没有效果|复读|乱码|不一致|不对|有误|缺失)", re.I)
USAGE = re.compile(r"(怎么|如何|怎样|什么|哪些|哪个|是否|能否|可以吗|请问|请教|求助|参数|默认|配置|设置|支持|区别|含义|作用|用法|方式|方法|步骤|how|what|which|does|support|usage|default)", re.I)
TOPIC = re.compile(r"(lora|qlora|sft|dpo|rm|ppo|kto|orpo|cpt|pretrain|dataset|数据|template|模板|tokenizer|量化|quant|export|导出|合并|merge|inference|推理|评估|eval|predict|学习率|lr|batch|epoch|显存|vram|显卡|deepseek|qwen|llama|glm|gemma|baichuan|internlm|yaml|参数|cutoff|packing|shuffle|metrics|logits|chat_template|flash|attention|gradient|checkpoint|lora_target)", re.I)


def tokenize(text):
    text = text.lower()
    en = re.findall(r"[a-z_][a-z0-9_.\-]{1,30}", text)
    zh = [w for w in jieba.cut(text) if CJK.search(w) and len(w) >= 2]
    return en + zh


def load_issues():
    files = glob.glob(os.path.join(DATA, "issues/page_*.json"))
    files += glob.glob(os.path.join(DATA, "issues/old/p*.json"))
    items, seen = [], set()
    for p in sorted(files):
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for it in data:
            n = it.get("number")
            if n in seen:
                continue
            seen.add(n)
            items.append(it)
    return items


def main():
    chunks = [json.loads(l) for l in open(os.path.join(DATA, "chunks.jsonl"), encoding="utf-8")]
    corpus = [tokenize(c["heading"] + "\n" + c["text"]) for c in chunks]
    bm25 = rank_bm25.BM25Okapi(corpus)

    # 文档全文中出现过的参数名集合（用于判断「问题问的参数文档里有没有」）
    doc_blob = "\n".join(c["heading"] + "\n" + c["text"] for c in chunks)
    doc_params = set(PARAM.findall(doc_blob.lower()))

    items = load_issues()
    issues = [i for i in items if "pull_request" not in i]

    rows = []
    for it in issues:
        title = (it.get("title") or "").strip()
        body = it.get("body") or ""
        if not title:
            continue
        if OPS.search(title) or OPS.search(body[:400]):
            continue
        if BUG.search(title):
            continue
        if not USAGE.search(title):
            continue
        if len(body.strip()) < 20:
            continue

        qtok = tokenize(title + "\n" + body[:600])
        if not qtok:
            continue
        scores = bm25.get_scores(qtok)
        order = scores.argsort()[::-1][:3]
        top = [
            {
                "score": round(float(scores[int(i)]), 2),
                "source": chunks[int(i)]["source"],
                "path": chunks[int(i)]["path"],
                "heading": chunks[int(i)]["heading"],
                "text": chunks[int(i)]["text"],
            }
            for i in order
        ]
        doc_top = next((t for t in top if t["source"] == "doc"), top[0])
        doc_score = doc_top["score"]

        # ★ 参数名命中：问题里的参数，文档里有没有
        asked = set(PARAM.findall(title.lower()))
        hit = {p for p in asked if p in doc_params}
        param_ratio = (len(hit) / len(asked)) if asked else 0.0

        topic = len({m.group(0).lower() for m in TOPIC.finditer(title + body[:300])})

        # 综合分：参数命中权重最高（最可靠的「可回答」信号）
        score = (
            param_ratio * 100
            + min(doc_score, 100) * 0.5
            + topic * 4
            + (10 if (it.get("comments") or 0) >= 1 else 0)
            + (8 if doc_top["source"] == "doc" else 0)
        )

        rows.append(
            {
                "number": it["number"],
                "title": title,
                "url": it.get("html_url"),
                "comments": it.get("comments") or 0,
                "created": (it.get("created_at") or "")[:10],
                "labels": [l.get("name") for l in (it.get("labels") or [])],
                "doc_score": round(doc_score, 1),
                "doc_path": doc_top["path"],
                "doc_heading": doc_top["heading"],
                "doc_text": doc_top["text"][:700],
                "params_asked": sorted(asked),
                "params_found": sorted(hit),
                "param_ratio": round(param_ratio, 2),
                "topic_hits": topic,
                "rank_score": round(score, 1),
                "body": body[:900],
            }
        )

    rows.sort(key=lambda r: -r["rank_score"])
    rows = rows[:120]

    with open(os.path.join(DATA, "review_sheet.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    # Markdown 核对表
    lines = [
        "# 第 1 周候选题目核对表",
        "",
        "用法：逐条看「问题」和「文档命中」，判断**答案是否真的能在这段文档里找到**。",
        "在 `判定` 列填 `✓`（可用）/ `✗`（不可用）/ `?`（需再查）。",
        "",
        f"共 {len(rows)} 条候选。排序依据：参数名命中 > 文档检索分 > 主题覆盖。",
        "",
        "| # | 判定 | Issue | 问题 | 文档命中 | 参数命中 |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        params = ", ".join(r["params_found"]) if r["params_found"] else "—"
        lines.append(
            "| %d |  | [#%s](%s) | %s | `%s`<br>%s | %s |"
            % (
                i,
                r["number"],
                r["url"],
                r["title"].replace("|", "\\|")[:90],
                r["doc_path"],
                (r["doc_heading"] or "").replace("|", "\\|")[:60],
                params,
            )
        )
    with open(os.path.join(DATA, "review_sheet.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("候选总数      :", len(rows))
    print("参数命中 > 0  :", sum(1 for r in rows if r["params_found"]))
    print("文档命中(高)  :", sum(1 for r in rows if r["doc_score"] >= 40))
    print("\n已写出:")
    print("  data/review_sheet.md")
    print("  data/review_sheet.json")

    print("\n=== 前 30 条 ===")
    for i, r in enumerate(rows[:30], 1):
        p = ",".join(r["params_found"]) or "-"
        print(
            "  %2d [%5.1f] #%-6s 参数[%s]  %s"
            % (i, r["rank_score"], r["number"], p, r["title"][:48])
        )
        print("        → %s | %s" % (r["doc_path"], (r["doc_heading"] or "")[:55]))


if __name__ == "__main__":
    main()
