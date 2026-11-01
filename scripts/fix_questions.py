#!/usr/bin/env python3
"""修正 data/questions.json 里已发现的质量问题。

原则：每条修改都必须有文档原文支撑（evidence 字段），不能自己编。
改完自动复验：新答案里的参数名/数字必须能在新 evidence 里找到。

用法：
    python scripts/fix_questions.py --dry    # 只看会改什么
    python scripts/fix_questions.py          # 实际写入（自动备份）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QJSON = ROOT / "data" / "questions.json"

# issue → 修正内容。只写要改的字段。
PATCHES: dict[int, dict] = {
    # ① 问题把答案原样抄进去了 → 改写成真正的提问
    2633: {
        "question": "do_sample 参数设为 False 时，文本生成使用什么策略？",
        "answer": "使用贪心解码（greedy decoding）。do_sample 为 bool 类型、默认 True，控制是否使用采样策略生成文本。",
        "evidence": "| do_sample | bool | 是否使用采样策略生成文本。如果设置为 False，将使用 greedy decoding。 | True |",
    },
    # ② 答案只有「支持」两个字 → 补成可判分的完整答案
    9479: {
        "question": "支持 Qwen3-4B-Instruct-2507 的 KTO 训练吗？",
        "answer": "支持。仓库提供了 KTO 训练配置示例，其中 model_name_or_path 为 "
                  "Qwen/Qwen3-4B-Instruct-2507，stage 设为 kto。",
        "doc_location": "examples/train_lora/qwen3_lora_kto.yaml",
        "evidence": "### model\nmodel_name_or_path: Qwen/Qwen3-4B-Instruct-2507\ntrust_remote_code: true\n\n### method\nstage: kto",
    },
    # ③ 答案讲 wd、出处却是 learning_rate 行 → 换成 Muon 优化器那段，问题译中文
    5603: {
        "question": "如何设置 weight decay（权重衰减）？",
        "answer": "在配置的 optim_config 中设置 name: muon 启用 Muon 优化器，再用 wd 字段控制 weight decay，默认值 0.1。",
        "doc_location": "docs/zh/feature-guide/optimizer.md > 优化器 > Muon",
        "evidence": "设置 `optim_config.name: muon` 启用 Muon。Muon 对适合正交化更新的二维权重使用 Muon，"
                    "并将偏置、归一化参数、embedding、输出层和 LoRA 参数交给内部 AdamW。"
                    "以下为完整的 SFT 配置（`config.yaml`）：optim_config: name: muon wd: 0.1 momentum: 0.95",
    },
    # ④ 答非所问：问「只冻结 LLM」，答案讲 Freeze 是什么
    #    文档参数表里没有 freeze_language_model，只能改成文档能答的形式
    6484: {
        "question": "多模态模型训练时，视觉塔和多模态投影器默认会被冻结吗？",
        "answer": "会。freeze_vision_tower 与 freeze_multi_modal_projector 的默认值都是 True，"
                  "即默认冻结视觉塔与多模态投影器、只训练语言模型部分；设为 False 即可解冻。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 微调参数¶ > 基本参数¶",
        "evidence": "| freeze_vision_tower | bool | MLLM 训练时是否冻结视觉塔。 | True | "
                    "| freeze_multi_modal_projector | bool | MLLM 训练时是否冻结多模态投影器。 | True |",
    },
    # ⑤ 问题写成陈述句 → 改疑问句
    1356: {
        "question": "同时设置了 max_length 和 max_new_tokens，哪个生效？",
        "answer": "max_new_tokens 会覆盖 max_length。两者默认值都是 1024；只设 max_length 而不设 max_new_tokens 时，"
                  "会被默认的 max_new_tokens=1024 覆盖。",
    },
    # ⑥⑦⑧ 英文问题 → 译成中文（答案与 evidence 不动）
    6497: {"question": "多模态数据集中如何使用多张图片？"},
    3656: {"question": "如何用 accelerate 进行多机 SFT？"},
    5512: {"question": "Qwen2-VL 如何用 LoRA 同时训练 mm_proj 和 LLM 部分？"},
    # ⑨ 问题竟是整段 Python 报错原文，且与 #2633 撞题 → 改成「参数冲突」类
    2837: {
        "question": "do_sample 设为 False 时，temperature 和 top_p 还起作用吗？",
        "answer": "不起作用。do_sample 为 False 时使用 greedy decoding（贪心解码），不再进行采样；"
                  "temperature（默认 0.95）用于调整生成文本的随机性，top_p 用于控制候选 token 集合大小，"
                  "两者都只在采样模式下参与生成。",
        "evidence": "| do_sample | bool | 是否使用采样策略生成文本。如果设置为 False，将使用 greedy decoding。 | True | "
                    "| temperature | float | 用于调整生成文本的随机性。temperature 越高，生成的文本越随机；"
                    "temperature 越低，生成的文本越确定。 | 0.95 | "
                    "| top_p | float | 用于控制生成时候选 token 集合大小的参数。 | 0.7 |",
    },
    # ⑩ 问题是个标题不是提问
    10253: {
        "question": "如何为 Qwen3.5 启用 Liger Kernel 加速？",
        "evidence": "`kernel_config` 统一配置模型侧的融合算子加速。它可以替换单个算子，"
                    "也可以像 Liger Kernel 一样同时应用多个融合实现和训练优化。"
                    "`kernel_config.name` 接受一个加速实现名称，也接受逗号分隔的多个名称。"
                    "未设置 `kernel_config` 或设为 `null` 时，此入口不替换算子。",
    },
    # ⑪ 英文问题 + 答案里命令被压平粘连
    5416: {
        "question": "Qwen2-VL 7B 如何用命令行进行对话？",
        "answer": "您可以使用 `llamafactory-cli chat inference_config.yaml` 或 "
                  "`llamafactory-cli webchat inference_config.yaml` 进行推理与模型对话。"
                  "对话时配置文件只需指定原始模型 model_name_or_path 和 template。",
        "evidence": "您可以使用 `llamafactory-cli chat inference_config.yaml` 或 "
                    "`llamafactory-cli webchat inference_config.yaml` 进行推理与模型对话。"
                    "对话时配置文件只需指定原始模型 `model_name_or_path` 和 `template`。",
    },
}

BACKTICK = re.compile(r"`([^`]{1,40})`")
IDENT = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b")
NUM = re.compile(r"\b\d+(?:\.\d+)*\b")


def hard_entities(s: str) -> list[str]:
    out = [m.strip() for m in BACKTICK.findall(s) if m.strip()]
    out += [w for w in IDENT.findall(s) if "_" in w]
    out += [n for n in NUM.findall(s) if "." in n]
    seen, uniq = set(), []
    for e in out:
        k = e.lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def verify(rec: dict) -> list[str]:
    """新答案里的硬实体，必须在 evidence 里出现。返回缺失列表。"""
    ev = (rec.get("evidence") or "").lower()
    if not ev:
        return ["没有 evidence"]
    return [e for e in hard_entities(rec.get("answer") or "") if e.lower() not in ev]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    rows = json.loads(QJSON.read_text(encoding="utf-8"))
    by_issue = {r["issue"]: r for r in rows}

    changed, problems = 0, []
    for issue, patch in PATCHES.items():
        rec = by_issue.get(issue)
        if rec is None:
            problems.append(f"issue {issue} 不在题库里，跳过")
            continue

        before = {k: rec.get(k) for k in patch}
        for k, v in patch.items():
            rec[k] = v
        changed += 1

        missing = verify(rec)
        print(f"--- issue {issue}")
        for k in patch:
            old = str(before.get(k) or "")[:60].replace("\n", " ")
            new = str(rec.get(k) or "")[:60].replace("\n", " ")
            if old != new:
                print(f"    {k}: {old!r} → {new!r}")
        if missing:
            print(f"    ✗ 复验未通过，答案里这些在 evidence 找不到：{missing}")
            problems.append(f"issue {issue} 复验失败：{missing}")
        else:
            print("    ✓ 复验通过（答案实体都在 evidence 里）")

    print()
    print(f"共修改 {changed} 条")

    if problems:
        print(f"✗ {len(problems)} 个问题，未写入：")
        for p in problems:
            print("   -", p)
        return 1

    if a.dry:
        print("（--dry 模式，未写入）")
        return 0

    bak = QJSON.with_suffix(".json.bak")
    shutil.copy2(QJSON, bak)
    print(f"已备份：{bak.name}")
    QJSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入：{QJSON.relative_to(ROOT)}（{len(rows)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
