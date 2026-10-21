#!/usr/bin/env python3
"""从 LlamaFactory Issues 里筛选「用法类提问」候选（第 11 节步骤 2 用）。

筛选口径：
- 排除 Pull Request（issues 接口会把 PR 也返回）
- 优先中文、标题像提问、有正文、有回答（comments >= 1）
- 扣分：正文含 traceback / 堆栈（属于 bug 报告，不是用法提问）
"""
import glob
import json
import os
import re

CJK = re.compile(r"[\u4e00-\u9fff]")
Q_PAT = re.compile(
    r"(怎么|如何|怎样|为什么|为啥|能否|可以吗|是否|求助|请教|请问|"
    r"报错|错误|失败|不支持|找不到|怎么设置|怎么用|怎么配|"
    r"能不能|有没有|应该|\?|？)",
    re.I,
)
BUG_HINT = re.compile(r"(traceback|exception|error:|\.py\", line|at line)", re.I)
USAGE_LABEL = ("question", "usage", "help", "support", "documentation", "docs", "discussion")


def load(pattern):
    items = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if isinstance(data, list):
            items.extend(data)
    return items


def main():
    pattern = os.path.expanduser("~/llmloop/data/issues/page_*.json")
    items = load(pattern)
    print("原始条数   :", len(items))

    seen, uniq = set(), []
    for it in items:
        num = it.get("number")
        if num in seen:
            continue
        seen.add(num)
        uniq.append(it)
    print("去重后     :", len(uniq))

    issues = [i for i in uniq if "pull_request" not in i]
    print("其中 PR    :", len(uniq) - len(issues))
    print("其中 Issue :", len(issues))

    stat = {"中文": 0, "像提问": 0, "有正文": 0, "有回答": 0, "候选": 0}
    cands = []

    for it in issues:
        title = it.get("title") or ""
        body = it.get("body") or ""
        labels = [(l.get("name") or "").lower() for l in (it.get("labels") or [])]
        ncom = it.get("comments") or 0
        text = title + "\n" + body

        zh = bool(CJK.search(text))
        qlike = bool(Q_PAT.search(title))
        hasbody = len(body.strip()) >= 30
        hasans = ncom >= 1
        buggy = bool(BUG_HINT.search(body))
        labelhit = any(any(u in l for u in USAGE_LABEL) for l in labels)

        stat["中文"] += zh
        stat["像提问"] += qlike
        stat["有正文"] += hasbody
        stat["有回答"] += hasans

        score = 0
        score += 3 if zh else 0
        score += 2 if qlike else 0
        score += 1 if hasbody else 0
        score += 2 if hasans else 0
        score += 1 if labelhit else 0
        score -= 2 if buggy else 0
        score -= 1 if len(title) < 8 else 0

        if score >= 6:
            stat["候选"] += 1
            cands.append((score, it))

    print("\n=== 过滤统计 ===")
    for k, v in stat.items():
        print("  %-8s %d" % (k, v))

    cands.sort(key=lambda x: (-x[0], -(x[1].get("comments") or 0)))
    out = os.path.expanduser("~/llmloop/data/issue_candidates.json")
    payload = [
        {
            "score": s,
            "number": i["number"],
            "title": i["title"],
            "comments": i.get("comments"),
            "state": i.get("state"),
            "created": i.get("created_at"),
            "url": i.get("html_url"),
            "labels": [l.get("name") for l in (i.get("labels") or [])],
            "body": (i.get("body") or "")[:1500],
        }
        for s, i in cands
    ]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("\n候选已写出 :", out)
    print("候选条数   :", len(cands))

    print("\n=== 前 30 条预览 ===")
    for s, i in cands[:30]:
        print("  [%2d] #%-6s (%2d评) %s" % (s, i["number"], i.get("comments") or 0, i["title"][:64]))


if __name__ == "__main__":
    main()
