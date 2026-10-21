#!/usr/bin/env python3
"""从 2000 条 Issue 里选出「用法类 + 答案能在文档/示例配置里找到」的候选题目。

产出：
  data/question_candidates.json   按可回答性排序的候选（供人工核对）
"""
import glob
import json
import os
import re

import jieba
import rank_bm25

CJK = re.compile(r"[\u4e00-\u9fff]")
DATA = os.path.expanduser("~/llmloop/data")

# 排除：运维/分布式环境问题（答案通常在 issue 讨论里，不在文档）
OPS = re.compile(
    r"(NPU|昇腾|910|Ascend|MindSpore|多机|多卡|分布式|ray|deepspeed|fsdp|megatron|"
    r"ktransformers|集群|节点|卡住|卡死|hang)",
    re.I,
)
# 排除：报错/bug（不是用法提问）
BUG = re.compile(
    r"(报错|错误|失败|OOM|显存不足|crash|Traceback|AssertionError|ValueError|"
    r"TypeError|RuntimeError|ImportError|KeyError|IndexError|异常|崩溃|崩了|"
    r"无法|不能用|没有效果|复读|乱码|不一致|bug|BUG|Bug|不对|有误|缺失)",
    re.I,
)
# 用法提问标志
USAGE = re.compile(
    r"(怎么|如何|怎样|什么|哪些|哪个|是否|能否|可以吗|请问|请教|求助|"
    r"参数|默认|配置|设置|支持|区别|含义|作用|用法|方式|方法|步骤|"
    r"how|what|which|does|support|usage|default)",
    re.I,
)
# 文档覆盖的主题词（提高权重）
TOPIC = re.compile(
    r"(lora|qlora|sft|dpo|rm|ppo|kto|orpo|cpt|pretrain|"
    r"dataset|数据|template|模板|tokenizer|量化|quant|export|导出|合并|merge|"
    r"inference|推理|评估|eval|predict|学习率|lr|batch|epoch|"
    r"显存|vram|显卡|deepseek|qwen|llama|glm|gemma|baichuan|internlm|"
    r"yaml|参数|cutoff|packing|shuffle|metrics|logits|chat_template|"
    r"flash|attention|gradient|checkpoint|lora_target|fsdp|deepspeed)",
    re.I,
)


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
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
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
    chunks = []
    with open(os.path.join(DATA, "chunks.jsonl"), encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    corpus = [tokenize(c["heading"] + "\n" + c["text"]) for c in chunks]
    bm25 = rank_bm25.BM25Okapi(corpus)
    print("索引块数:", len(chunks))

    items = load_issues()
    print("Issue 总数:", len(items))
    issues = [i for i in items if "pull_request" not in i]
    print("去掉 PR 后:", len(issues))

    pool = []
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
        pool.append(it)

    print("通过初筛 :", len(pool))

    rows = []
    for it in pool:
        title = it["title"]
        body = it.get("body") or ""
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
                "heading": chunks[int(i)]["heading"][:90],
                "text": chunks[int(i)]["text"][:500],
            }
            for i in order
        ]
        doc_top = next((t for t in top if t["source"] == "doc"), None)
        doc_score = doc_top["score"] if doc_top else 0.0
        topic = len(set(m.group(0).lower() for m in TOPIC.finditer(title + body[:300])))

        # 可回答性评分：文档命中分 + 主题覆盖 + 有回答
        answerable = doc_score + topic * 6 + (8 if (it.get("comments") or 0) >= 1 else 0)

        rows.append(
            {
                "number": it["number"],
                "title": title,
                "url": it.get("html_url"),
                "comments": it.get("comments") or 0,
                "state": it.get("state"),
                "created": (it.get("created_at") or "")[:10],
                "labels": [l.get("name") for l in (it.get("labels") or [])],
                "doc_score": round(doc_score, 2),
                "topic_hits": topic,
                "answerable": round(answerable, 1),
                "body": body[:1200],
                "top3": top,
            }
        )

    rows.sort(key=lambda r: -r["answerable"])
    out = os.path.join(DATA, "question_candidates.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    print("\n可回答性 >= 60 :", sum(1 for r in rows if r["answerable"] >= 60))
    print("可回答性 >= 45 :", sum(1 for r in rows if r["answerable"] >= 45))
    print("可回答性 >= 30 :", sum(1 for r in rows if r["answerable"] >= 30))
    print("总候选        :", len(rows))
    print("\n已写出:", out)

    print("\n=== 前 40 条（可回答性排序）===")
    for r in rows[:40]:
        print(
            "  [%5.1f] #%-6s doc%5.1f topic%d  %s"
            % (r["answerable"], r["number"], r["doc_score"], r["topic_hits"], r["title"][:58])
        )
        print("           → %s | %s" % (r["top3"][0]["path"], r["top3"][0]["heading"][:60]))


if __name__ == "__main__":
    main()
