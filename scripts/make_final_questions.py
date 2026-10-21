#!/usr/bin/env python3
"""生成最终 60 道题：17 道真实提问 + 43 道文档反推。

为什么反推（第 13 节退路原文）：
  「LlamaFactory 真实提问不够：用文档反推题目可以补充，
    但要单独标出来源，评测结论按来源分开报告。」

  实测：2000 条真实 Issue 里，能对应到文档答案的只有 17 条（可用率约 6%）。
  剩余 43 道从参数表反推——答案就是表格那一行，100% 确定，不存在歧义。

反推题的质量为什么可靠：
  参数表格式是「| 参数名 | 类型 | 说明 | 默认值 |」，
  题目问「默认值是多少/有什么作用」，答案就是对应单元格，不需要推理。

输出：data/questions.json
  每条含：id / question / answer / doc_location / split / source / origin
    source = "real"（真实提问）或 "doc-derived"（文档反推）
    origin = Issue 编号 或 参数名+文档位置
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SEED = 20261020
N_OPT, N_TEST = 30, 30
N_TOTAL = N_OPT + N_TEST

# 已确认可用的真实提问（用户人工核对 + 我逐条比对文档原文后剔除 4 条）
# 剔除：#9（问默认模板，文档讲自定义覆盖）、#191（问 label smoothing，文档讲 pref_loss）、
#       #238（问 ring attention，文档讲 flash-linear-attention）、#255（问 Dynamic LoRA，文档无）
REAL_IDS = [30, 34, 43, 88, 91, 107, 122, 135, 202, 208, 221, 244, 252]

# 参数名黑名单：太通用，反推出的题目没意义
BAD_PARAMS = {
    "model", "size", "name", "path", "type", "value", "data", "file", "config",
    "stage", "sft", "dpo", "rm", "ppo", "kto", "orpo", "template", "dataset",
    "true", "false", "none", "null", "all", "auto", "yes", "no", "user",
}


def parse_params() -> dict[str, dict]:
    """从所有 chunk 的表格行里抽出参数字典。"""
    params: dict[str, dict] = {}
    for line in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        for row in c["text"].split("\n"):
            if not row.startswith("| "):
                continue
            cells = [x.strip() for x in row.strip("|").split("|")]
            if len(cells) < 4:
                continue
            name = cells[0].strip("`* ")
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", name):
                continue
            if name in BAD_PARAMS:
                continue
            typ = cells[1].strip()
            desc = cells[2].strip()
            default = cells[3].strip()
            if len(desc) < 8:
                continue
            if not default or default in ("—", "-", "无"):
                continue
            old = params.get(name)
            if old and len(old["desc"]) >= len(desc):
                continue
            params[name] = {
                "type": typ,
                "desc": desc,
                "default": default,
                "path": c["path"],
                "heading": c["heading"],
            }
    return params


def make_question(name: str, p: dict, rng: random.Random) -> dict:
    """按参数生成一道题。答案严格取自表格单元格。"""
    typ = p["type"].replace("`", "")
    desc = p["desc"].rstrip("。")
    default = p["default"].replace("`", "")

    # 有 Literal[...] 的优先出「取值」题
    lit = re.search(r"Literal\[(.*?)\]", typ)
    if lit:
        choices = lit.group(1).replace("“", "").replace("”", "").replace('"', "")
        q = f"`{name}` 参数支持哪些取值？默认值是什么？"
        a = f"支持 {choices}；默认值为 {default}。"
        return {"question": q, "answer": a}

    style = rng.choice(["default", "purpose", "usage"])
    if style == "default":
        q = f"`{name}` 参数的默认值是多少？"
        a = f"默认值为 {default}。"
    elif style == "purpose":
        q = f"`{name}` 这个参数有什么作用？"
        a = f"{desc}。默认值为 {default}。"
    else:
        q = f"如何理解和使用 `{name}` 参数？"
        a = f"{desc}。默认值为 {default}。"
    return {"question": q, "answer": a}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-derived", type=int, default=43)
    ap.add_argument("--out", default=str(DATA / "questions.json"))
    args = ap.parse_args()

    rng = random.Random(SEED)

    # ── ① 真实提问 ──
    draft = {q["id"]: q for q in json.loads((DATA / "questions_draft.json").read_text(encoding="utf-8"))}
    located = json.loads((DATA / "located.json").read_text(encoding="utf-8"))
    drafts_ans = {}
    dp = DATA / "answer_drafts.json"
    if dp.exists():
        drafts_ans = json.loads(dp.read_text(encoding="utf-8"))

    params = parse_params()
    print(f"参数字典：{len(params)} 个可用参数")

    real = []
    for qid in REAL_IDS:
        q = draft.get(qid)
        if not q:
            print(f"  ⚠ 找不到 id={qid}")
            continue
        loc = located.get(str(qid)) or {}
        dr = drafts_ans.get(str(qid)) or {}
        answer = (dr.get("answer") or "").strip()
        if not answer or answer.upper() == "NONE":
            print(f"  ⚠ #{qid} 没有答案草稿，跳过")
            continue
        paths = loc.get("paths") or []
        heads = loc.get("heads") or []
        doc_loc = ""
        if paths:
            doc_loc = paths[0] + (" > " + heads[0] if heads and heads[0] else "")
        real.append(
            {
                "question": q["question"],
                "answer": answer,
                "doc_location": doc_loc,
                "source": "real",
                "origin": f"GitHub Issue #{q['issue']}",
            }
        )

    print(f"真实提问：{len(real)} 条")

    # ── ② 文档反推 ──
    # 优先选 desc 长、有默认值的参数，且避免同一节全是一个前缀
    names = sorted(params, key=lambda n: -len(params[n]["desc"]))
    rng.shuffle(names)
    names.sort(key=lambda n: -len(params[n]["desc"]))  # 稳定：长的优先

    derived = []
    used = set()
    for name in names:
        if len(derived) >= args.n_derived:
            break
        if name in used:
            continue
        used.add(name)
        p = params[name]
        item = make_question(name, p, rng)
        item.update(
            {
                "doc_location": p["path"] + " > " + p["heading"],
                "source": "doc-derived",
                "origin": f"文档反推 · {name}",
            }
        )
        derived.append(item)

    print(f"文档反推：{len(derived)} 条")

    allq = real + derived
    print(f"合计：{len(allq)} 条")
    if len(allq) != N_TOTAL:
        print(f"⚠ 不是 {N_TOTAL} 条，实际 {len(allq)} 条")

    # ── ③ 切分（固定种子）──
    order = list(range(len(allq)))
    rng.shuffle(order)
    opt_idx = set(order[:N_OPT])

    final = []
    for i, q in enumerate(allq):
        final.append(
            {
                "id": i + 1,
                "question": q["question"],
                "answer": q["answer"],
                "doc_location": q["doc_location"],
                "split": "optimize" if i in opt_idx else "test",
                "source": q["source"],
                "origin": q["origin"],
            }
        )
    final.sort(key=lambda x: x["id"])

    out = Path(args.out)
    out.write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter

    c = Counter((q["split"], q["source"]) for q in final)
    print()
    print("=" * 56)
    print(f"已生成 {out}")
    print(f"  优化用：{sum(1 for q in final if q['split'] == 'optimize')} 条")
    print(f"  测试用：{sum(1 for q in final if q['split'] == 'test')} 条")
    print(f"  来源：真实 {sum(1 for q in final if q['source'] == 'real')} 条"
          f" / 反推 {sum(1 for q in final if q['source'] == 'doc-derived')} 条")
    print(f"  随机种子：{SEED}")
    print()
    print("前 6 条预览：")
    for q in final[:6]:
        print(f"  [{q['split'][:4]}|{q['source'][:4]}] {q['question'][:56]}")
        print(f"        答案：{q['answer'][:66]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
