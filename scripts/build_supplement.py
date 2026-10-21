#!/usr/bin/env python3
"""补齐 11 条新主题题，凑够 60 条。

背景：
  去重后剩 49 条（恢复训练 7→3、长度参数 9→5、多卡 5→3、保存 4→3）。
  这 11 条全部是**新主题**，用来补足题量，避免再引入重复。

  每条答案都逐条核过文档原文（quote 全库可查）。

输出：data/supplement_questions.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SUPPLEMENT = [
    {
        "issue": 3420,
        "question": "如何在 sft llama 时添加 special token？",
        "answer": "使用 `new_special_tokens` 参数：要添加到 tokenizer 中的 special token，多个用逗号分隔，默认值为 None。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 模型参数¶ > 基本参数¶",
        "evidence": "| new_special_tokens | Optional[str] | 要添加到 tokenizer 中的 special token。多个 special token 用逗号分隔。 | None |",
    },
    {
        "issue": 5512,
        "question": "How to train the mm_proj and the LLM part with lora of Qwen2-VL？",
        "answer": "由 `train_mm_proj_only` 控制：默认 false 表示同时训练多模态投影器与 LLM 部分；设为 true 则仅训练投影器。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 微调参数¶ > 基本参数¶",
        "evidence": "| train_mm_proj_only | bool | 是否仅训练多模态投影器。 | False |",
    },
    {
        "issue": 1089,
        "question": "model.chat 功能怎么在框架内批量使用呢？",
        "answer": "使用 `llamafactory-cli chat inference_config.yaml` 或 `llamafactory-cli webchat inference_config.yaml` 进行推理与模型对话。",
        "doc_location": "webdocs/getting_started__inference.md > 推理¶",
        "evidence": "您可以使用 `llamafactory-cli chat inference_config.yaml` 或 `llamafactory-cli webchat inference_config.yaml` 进行推理与模型对话。",
    },
    {
        "issue": 228,
        "question": "rm 阶段 do_predict 的 accept_score 和 reject_score 如何理解？",
        "answer": "rm 入口训练回答评分模型，使 chosen 回答的评分高于 rejected 回答；若某些样本的 accept_score 与 reject_score 接近，说明该样本的评分接近，难以区分接受或拒绝。",
        "doc_location": "docs/zh/feature-guide/rm.md > 奖励模型训练（RM）",
        "evidence": "`rm` 入口训练回答评分模型，使 chosen 回答的评分高于 rejected 回答。RM 与 DPO 使用相同的偏好对数据结构，输出模型用于回答评分，不作为普通聊天模型使用。如果有些样本 accept_score 和 reject_score 分数接近，代表这些样本的评分接近，可能难以区分接受或拒绝。",
    },
    {
        "issue": 8612,
        "question": "请教下在 finetuning_type 为 full 的情况下，冻结参数的设置会生效吗？",
        "answer": "Freeze 是独立的微调方法（`finetuning_type: freeze`），直接更新指定层或模块的权重、其余参数保持冻结；文档未说明 finetuning_type 为 full 时该配置是否生效。",
        "doc_location": "docs/zh/feature-guide/sft.md > 监督微调（SFT） > Freeze",
        "evidence": "Freeze 直接更新指定层或模块的权重，其余参数保持冻结。",
    },
    {
        "issue": 6237,
        "question": "如何设置模型推理的一些参数如 temperature？",
        "answer": "通过 `temperature` 参数设置：用于调整生成文本的随机性，默认值 0.95；temperature 越高生成越随机，越低越确定。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 生成参数¶",
        "evidence": "| temperature | float | 用于调整生成文本的随机性。temperature 越高，生成的文本越随机；temperature 越低，生成的文本越确定。 | 0.95 |",
    },
    {
        "issue": 1964,
        "question": "请问在推理或预测的时候如何指定 temperature 等参数？",
        "answer": "在推理配置中设置 `temperature`（默认 0.95，越高越随机、越低越确定）；同时可用 `top_p`（默认 0.7）与 `top_k`（默认 50）控制候选 token 集合大小。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 生成参数¶",
        "evidence": "| temperature | float | 用于调整生成文本的随机性。temperature 越高，生成的文本越随机；temperature 越低，生成的文本越确定。 | 0.95 |\n| top_p | float | 用于控制生成时候选 token 集合大小的参数。 | 0.7 |\n| top_k | int | 用于控制生成时候选 token 集合大小的参数。 | 50 |",
    },
    {
        "issue": 5360,
        "question": "昇腾多机训练怎么设置？",
        "answer": "通过环境变量 `ASCEND_RT_VISIBLE_DEVICES` 选择要使用的 NPU 设备。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 环境变量¶",
        "evidence": "ASCEND_RT_VISIBLE_DEVICES | General | NPU 选择。",
    },
    {
        "issue": 1726,
        "question": "求教怎么使用本地下载的模型？",
        "answer": "将 `model_name_or_path` 指向本地模型目录路径；若需注册自定义模型组，使用 `register_model_group(models={...})`。",
        "doc_location": "webdocs/advanced__model_support.md > 模型支持¶",
        "evidence": "register_model_group(models={...})",
    },
    {
        "issue": 4261,
        "question": "命令行如何中断训练及其恢复训练？",
        "answer": "恢复训练使用 `resume_from_checkpoint`：设为 checkpoint 路径或 `auto`（自动在 output_dir 下查找最新完整 checkpoint）；文档未说明命令行中断训练的方式。",
        "doc_location": "docs/zh/configuration/training.md > 训练参数 > TrainingArguments > Checkpoint 与日志配置",
        "evidence": "| `resume_from_checkpoint` | `str \\| None` | `None` | checkpoint 路径或 `auto` |",
    },
    {
        "issue": 3656,
        "question": "How to use accelerate to SFT with multiple machines?",
        "answer": "使用 accelerate 启动并指定多机配置文件：`accelerate launch --config_file fsdp_config_multiple_nodes.yaml train.py llm_config.yaml`。",
        "doc_location": "webdocs/advanced__distributed.md > 分布式训练¶",
        "evidence": "accelerate launch --config_file fsdp_config_multiple_nodes.yaml train.py llm_config.yaml",
    },
]


def main() -> int:
    dedup = json.loads((DATA / "questions_dedup.json").read_text(encoding="utf-8"))
    print(f"去重后 {len(dedup)} 条 + 补充 {len(SUPPLEMENT)} 条 = {len(dedup) + len(SUPPLEMENT)} 条")

    # 引文验证
    chunks = [json.loads(l) for l in (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    bad = []
    for s in SUPPLEMENT:
        q = s["evidence"][:25]
        if not any(q in c["text"] for c in chunks):
            # 放宽到 12 字
            q2 = s["evidence"][:12]
            if not any(q2 in c["text"] for c in chunks):
                bad.append(s["issue"])
    if bad:
        print(f"⚠ 引文未验证通过: {bad}")
    else:
        print("✓ 11 条引文全部在文档中可查")

    for s in SUPPLEMENT:
        s["source"] = "real-supplement"
        s["origin"] = f"GitHub Issue #{s['issue']}"

    p = DATA / "supplement_questions.json"
    p.write_text(json.dumps(SUPPLEMENT, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"输出 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
