#!/usr/bin/env python3
"""从文档参数表反推题目（老师第 13 节「退路」明确允许，需单独标来源）。

依据：
  · 第 6 节：题目类型包括「参数名和默认值」
  · 第 13 节：真实提问不够时「用文档反推题目可以补充，但要单独标出来源」
  · RAGAS 的做法：参考答案必须来自上下文，问题按场景变化（避免千篇一律）

本脚本只做「参数类」。每道题的答案严格取自参数表那一行，不加工、不推断。

问法用 4 种模板轮换，避免看起来像同一道题：
  1. `xxx` 默认值是多少？
  2. `xxx` 不填的话会用什么值？
  3. `xxx` 这个参数是做什么的？默认值多少？
  4. `xxx` 应该怎么设？默认是多少？

输出：data/questions_docsynth.json
用法：
    python scripts/gen_doc_questions.py            # 生成
    python scripts/gen_doc_questions.py --dry      # 只看统计
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 参数名黑名单：太通用，反推出的题目没意义（沿用 make_final_questions.py）
BAD_PARAMS = {
    "model", "size", "name", "path", "type", "value", "data", "file", "config",
    "stage", "sft", "dpo", "rm", "ppo", "kto", "orpo", "template", "dataset",
    "true", "false", "none", "null", "all", "auto", "yes", "no", "user",
    "output", "input", "text", "token", "prompt", "response", "label", "source",
    "target", "format", "version", "device", "mode", "method", "backend", "engine",
}


def looks_like_value(s: str) -> bool:
    """判断一个单元格像「默认值」还是像「说明文字」。

    默认值通常：True/False/None、数字、短枚举、不含中文。
    说明文字通常：含中文、较长。
    """
    t = s.strip().strip("`")
    if not t or len(t) > 30:
        return False
    if re.search(r"[\u4e00-\u9fff]", t):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.,\[\]\-\s/]+", t))


def parse_params() -> dict[str, dict]:
    """从所有 chunk 的表格行里抽参数。答案严格取自同一行。

    ★ 各表列顺序不统一：多数是 name|type|desc|default，
      但有的表是 name|type|default|desc。用「哪一列更像默认值」自动判定并交换。
    """
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
            c2, c3 = cells[2].strip(), cells[3].strip()

            # 列序识别：c3 像说明（含中文）而 c2 像值 → 说明是 default|desc 顺序，交换
            if re.search(r"[\u4e00-\u9fff]", c3) and not re.search(r"[\u4e00-\u9fff]", c2):
                desc, default = c3, c2
            else:
                desc, default = c2, c3

            if len(desc) < 8:          # 说明太短，撑不起一道题
                continue
            if not default or default in ("—", "-", "无", "None", "null"):
                continue
            if len(default) > 40:      # 默认值栏异常（多半是表格错位）
                continue
            old = params.get(name)
            if old and len(old["desc"]) >= len(desc):
                continue
            params[name] = {
                "type": typ, "desc": desc, "default": default,
                "path": c["path"], "heading": c["heading"], "row": row.strip(),
            }
    return params


def pick_style(name: str) -> int:
    """按参数名做稳定哈希选问法，保证每次生成结果一致。"""
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16) % 4


def build(name: str, p: dict) -> dict:
    typ = p["type"].replace("`", "")
    desc = p["desc"].rstrip("。")
    default = p["default"].replace("`", "").strip()
    lit = re.search(r"Literal\[(.*?)\]", typ)

    if lit:
        choices = lit.group(1).replace("“", "").replace("”", "").replace('"', "").strip()
        q = f"`{name}` 可以填哪些值？默认是哪个？"
        a = f"支持 {choices}；默认值为 {default}。"
    else:
        style = pick_style(name)
        if style == 0:
            q = f"`{name}` 默认值是多少？"
            a = f"默认值为 {default}。"
        elif style == 1:
            q = f"`{name}` 不填的话会用什么值？"
            a = f"不填时使用默认值 {default}。"
        elif style == 2:
            q = f"`{name}` 这个参数是做什么的？默认值多少？"
            a = f"{desc}。默认值为 {default}。"
        else:
            q = f"`{name}` 应该怎么设？默认是多少？"
            a = f"{desc}。默认值为 {default}。"

    loc = f"{p['path']} > {p['heading']}" if p["heading"] else p["path"]
    return {
        "question": q,
        "answer": a,
        "doc_location": loc,
        "evidence": p["row"],
        "source": "doc-synth",
        "origin": "文档参数表反推（第13节退路）",
        "param": name,
        "split": "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    params = parse_params()
    print(f"参数表里可用参数：{len(params)} 个")

    # 已用过的参数：现有 60 道题里出现过反引号参数名的，跳过
    existing = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    used: set[str] = set()
    for q in existing:
        for m in re.findall(r"`([a-z][a-z0-9_]{2,40})`", q.get("question", "") + q.get("answer", "")):
            used.add(m)
    print(f"现有题库已涉及参数：{len(used)} 个")

    fresh = {n: p for n, p in params.items() if n not in used}
    print(f"可新出题参数：{len(fresh)} 个")

    items = [build(n, p) for n, p in sorted(fresh.items())]
    print(f"生成题目：{len(items)} 道")

    from collections import Counter
    print("  问法分布：", dict(Counter("Literal" if "Literal" in params[i["param"]]["type"] else f"style{pick_style(i['param'])}" for i in items)))

    if a.dry:
        print()
        print("=== 抽样 10 道 ===")
        for it in items[:10]:
            print(f"  问：{it['question']}")
            print(f"     答：{it['answer'][:70]}")
            print(f"     出处：{it['doc_location'][:60]}")
        return 0

    dst = DATA / "questions_docsynth.json"
    dst.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写出：{dst.relative_to(ROOT)}")
    print()
    print("=== 抽样 8 道 ===")
    for it in items[:8]:
        print(f"  问：{it['question']}")
        print(f"     答：{it['answer'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
