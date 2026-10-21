#!/usr/bin/env python3
"""把操作类挖掘结果并入正样本，凑够 60 条全正样本。

背景：
  第一轮只挖了「含参数名」的问题 → 27 条正样本，凑不够 60，被迫引入负样本。
  但老师第 8.1 ⑤ 明确要求「答案能在文档或示例配置里找到」，
  负样本（答案是「文档里没有」）字面上不符合。

  第二轮补挖「操作类」问题（如何合并、如何恢复、如何导出……），
  这些文档里全有答案，且标题不带参数名，所以第一轮漏掉了。

输出：data/op_positive.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 人工筛选后的 31 条（剔除答非所问 / 与已有题库重复的 / 答案不精确的）
# 去掉的两条：#69（部署 chat bot，答案拼了两段文档不精确）
#             #7276（顺序读多数据集，答案只给了 mix_strategy 枚举）
PICK = [
    4261, 5628, 7226, 3482, 6257, 3643, 7172, 7648, 1373, 5830, 4600,
    5682, 2822, 6484, 3656, 5416, 1429, 5356, 1128, 6198, 6558,
    5214, 1022, 1458, 67, 4306, 6497, 5530, 5479, 6390, 6026,
]

# 少量答案需要人工补正（LLM 抽得不完整）
FIX = {
    4261: "使用 `resume_from_checkpoint` 指定 checkpoint 路径，或在训练 YAML 中设置 `resume_from_checkpoint: auto`，从 output_dir 自动查找最新完整 checkpoint 恢复训练。",
    5628: "设置 `resume_from_checkpoint` 指向 checkpoint 路径（或 `auto`），即可恢复训练状态；该字段默认 None。",
    1022: "最长输入长度由 `cutoff_len` 控制（默认 2048，超出截断）；最大输出长度由 `max_new_tokens` 控制（默认 1024，会覆盖 max_length）。",
    7172: "设置 `save_only_model: true`，只保存模型权重、不保存优化器状态。",
    5530: "设置 `save_only_model: true`，deepspeed 训练时同样只保存模型权重。",
}


def main() -> int:
    judged = json.loads((DATA / "op_judged.json").read_text(encoding="utf-8"))
    cands = {str(c["issue"]): c for c in json.loads((DATA / "op_candidates.json").read_text(encoding="utf-8"))}

    out, miss = [], []
    for issue in PICK:
        k = str(issue)
        v = judged.get(k) or {}
        c = cands.get(k) or {}
        if not v.get("ok"):
            miss.append(issue)
            continue
        title = (c.get("title") or "").strip()
        ask = (c.get("ask") or "").strip()
        q = title
        if ask and ask != title:
            body = ask.split("｜", 1)[-1] if "｜" in ask else ""
            body = body.replace("### Reminder", "").strip()
            if body and len(body) > 20 and "I have read" not in body[:60]:
                q = title + " —— " + body[:150]
        path = str(v.get("path") or "")
        head = str(v.get("heading") or "")
        out.append({
            "issue": issue,
            "question": q,
            "answer": FIX.get(issue) or str(v.get("answer") or "").strip(),
            "doc_location": f"{path} > {head}" if path else "",
            "evidence": str(v.get("quote") or "").strip(),
        })

    print(f"生成 {len(out)} 条" + (f"，缺失 {miss}" if miss else ""))
    p = DATA / "op_positive.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"输出 {p}")
    for o in out[:6]:
        print("  #" + str(o["issue"]) + " " + o["question"][:56])
        print("     " + o["answer"][:88])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
