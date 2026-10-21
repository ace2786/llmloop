#!/usr/bin/env python3
"""重建 60 题题库：27 条正样本（文档有答案）+ 33 条负样本（文档确实没有）。

为什么推翻旧题库：
  旧的 47 条反推题只有 4 个题干模板（"X 参数的默认值是多少"重复 15 次），
  等于 1 道题抄 47 遍，测不出检索/理解能力，也诊断不出「编造内容」。

新设计：
  正样本 27 条 —— 全部来自真实 Issue，文档能明确回答 → 测检索 + 理解
  负样本 33 条 —— 全部来自真实 Issue，文档确实没答案 → 测会不会老实说"资料里没有"

  ★ 负样本正好对应第 12 节要诊断的「编造内容」失败类型。

输出：data/questions_v2.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# ── 正样本：新的 16 条（逐条核过原文，quote 全库可查）────────────────────
NEW_POSITIVE = [
    {
        "issue": 1356,
        "question": "GeneratingArguments 中的 max_new_tokens 有默认值，任何情况下 max_length 都不会生效",
        "answer": "max_new_tokens 默认值为 1024，其说明是「生成文本的最大长度。设置 max_new_tokens 会覆盖 max_length」，所以只设 max_length 而不设 max_new_tokens 时，max_length 会被默认的 max_new_tokens 覆盖。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 生成参数¶",
        "evidence": "| max_length | int | 文本最大长度（包括输入文本和生成文本的长度）。 | 1024 |\n| max_new_tokens | int | 生成文本的最大长度。设置 max_new_tokens 会覆盖 max_length。 | 1024 |",
    },
    {
        "issue": 5759,
        "question": "请教下作者，目前新版代码关于 cutoff_len 是怎么处理的？",
        "answer": "cutoff_len 是输入的最大 token 数，超过该长度会被截断，默认值为 2048。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 数据参数¶",
        "evidence": "| cutoff_len | int | 输入的最大 token 数，超过该长度会被截断。 | 2048 |",
    },
    {
        "issue": 6314,
        "question": "为什么 DPO 训练时 ref_model 不指定为初始的 SFT 完的模型，而是用每个 batch 参数更新后的 policy model 来初始化呢？",
        "answer": "标准 DPO 需要 reference log-prob：全参训练会建立独立的 reference model；LoRA 训练复用 policy model 的基座权重，并在计算 reference log-prob 时禁用 adapter。所以 LoRA 场景下不是独立模型，而是复用 policy model 的基座。",
        "doc_location": "docs/zh/feature-guide/dpo.md > 偏好优化（DPO） > 参考模型",
        "evidence": "标准 DPO 需要 reference log-prob：全参训练会建立独立的 reference model；LoRA 训练复用 policy model 的基座权重，并在计算 reference log-prob 时禁用 adapter。",
    },
    {
        "issue": 3952,
        "question": "--cutoff_len 1024，截断长度设置的 1024，是指 1024 个字，还是 1024 个 token？",
        "answer": "是 token。cutoff_len 的定义是「输入的最大 token 数，超过该长度会被截断」，默认值 2048。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 数据参数¶",
        "evidence": "| cutoff_len | int | 输入的最大 token 数，超过该长度会被截断。 | 2048 |",
    },
    {
        "issue": 1283,
        "question": "如何使用 flash_attn2 进行加速训练？按照提示加了 --flash_attn 参数，但对比发现加不加这个参数训练速度都一样",
        "answer": "在训练配置文件中添加参数 `flash_attn: fa2`（而不是命令行只写 --flash_attn）。",
        "doc_location": "webdocs/advanced__acceleration.md > 加速¶ > FlashAttention¶",
        "evidence": "如果您想使用 FlashAttention，请在启动训练时在训练配置文件中添加以下参数：\n```\nflash_attn: fa2\n```",
    },
    {
        "issue": 1428,
        "question": "建议增加参数控制最大的保存 checkpoint 数量 save_total_limit",
        "answer": "该参数已存在：save_total_limit 控制最多保留多少个 checkpoint，超过数量限制时会自动删除较旧的 checkpoint，需配合 save_strategy 与 save_steps 使用。",
        "doc_location": "webdocs/getting_started__merge_lora.md > 模型保存、LoRA 合并与量化¶ > 模型保存¶ > Checkpoint 保存策略¶",
        "evidence": "`save_total_limit`：最多保留多少个 checkpoint，超过数量限制时会自动删除较旧的 checkpoint。",
    },
    {
        "issue": 7878,
        "question": "推理时 max_new_tokens 大小会影响输出结果吗？",
        "answer": "会。max_new_tokens 是生成文本的最大长度，默认 1024；设置 max_new_tokens 会覆盖 max_length，因此它直接决定输出的长度上限。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 生成参数¶",
        "evidence": "| max_new_tokens | int | 生成文本的最大长度。设置 max_new_tokens 会覆盖 max_length。 | 1024 |",
    },
    {
        "issue": 8993,
        "question": "freeze_trainable_layers 这个参数是什么含义？",
        "answer": "可训练层的数量：正数表示最后 n 层被设置为可训练的，负数表示前 n 层被设置为可训练的，默认值为 2。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 微调参数¶ > Freeze¶",
        "evidence": "| freeze_trainable_layers | int | 可训练层的数量。正数表示最后 n 层被设置为可训练的，负数表示前 n 层被设置为可训练的。 | 2 |",
    },
    {
        "issue": 9091,
        "question": "多机多卡，设置 data_shared_file_system 为 true 时每个 worker 都要算一遍 tokenize",
        "answer": "文档说明相反：data_shared_file_system 为 true 时数据集处理只在第一个 node 发生，为 false 时每个 node 都处理一次，默认 false。若出现每个 worker 都 tokenize，应检查该值是否被设为 false。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 数据参数¶",
        "evidence": "| data_shared_file_system | Optional[bool] | 多机多卡时，不同机器存放数据集的路径是否是共享文件系统。数据集处理在该值为true时只在第一个node发生，为false时在每个node都处理一次。 | false |",
    },
    {
        "issue": 1265,
        "question": "推理时候 --cutoff_len 和 --max_new_tokens 应该如何设置？",
        "answer": "cutoff_len 是输入的最大 token 数（默认 2048，超出截断）；max_new_tokens 是生成文本的最大长度（默认 1024，且会覆盖 max_length）。两者分别控制输入侧与输出侧的长度。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 数据参数¶ / 生成参数¶",
        "evidence": "| cutoff_len | int | 输入的最大 token 数，超过该长度会被截断。 | 2048 |\n| max_new_tokens | int | 生成文本的最大长度。设置 max_new_tokens 会覆盖 max_length。 | 1024 |",
    },
    {
        "issue": 9396,
        "question": "video_maxlen 和 cutoff_len 分别是什么含义？",
        "answer": "video_maxlen 是视频输入的最大采样帧数，默认 128；cutoff_len 是输入的最大 token 数，超过会被截断，默认 2048。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 模型参数¶ > 多模态模型¶ / 数据参数¶",
        "evidence": "| video_maxlen | int | 视频输入的最大采样帧数。 | 128 |\n| cutoff_len | int | 输入的最大 token 数，超过该长度会被截断。 | 2048 |",
    },
    {
        "issue": 1731,
        "question": "从 huggingface 中加载数据集时始终为 split=train，怎么指定其他 split？",
        "answer": "在数据集 YAML 的顶层条目里显式设置 `split` 字段。该字段默认值为 train，类型为 str。",
        "doc_location": "docs/zh/configuration/data.md > 数据参数 > DatasetInfo",
        "evidence": "| `split` | `str` | `train` | 数据集 split |",
    },
    {
        "issue": 4268,
        "question": "关于 packing 参数在 sft 阶段的疑问：为什么实际 batch 里的样本数和 micro_batch_size 对不上？",
        "answer": "因为动态策略中的 micro_batch_size 用于计算 token 预算，并不表示最终 batch 一定包含相同数量的样本。",
        "doc_location": "docs/zh/feature-guide/batching.md > 批处理策略",
        "evidence": "因此，动态策略中的 `micro_batch_size` 用于计算 token 预算，并不表示最终 batch 一定包含相同数量的样本。",
    },
    {
        "issue": 8075,
        "question": "请问在 lora 微调 qwen3 moe 模型时，如何设置 lora_target？",
        "answer": "lora_target 是应用 LoRA 方法的模块名称，使用逗号分隔多个模块，使用 all 指定所有模块，默认值为 all。",
        "doc_location": "webdocs/advanced__arguments.md > 参数介绍¶ > 微调参数¶ > LoRA¶",
        "evidence": "| lora_target | str | 应用 LoRA 方法的模块名称。使用逗号分隔多个模块，使用 all 指定所有模块。 | all |",
    },
    {
        "issue": 1567,
        "question": "Reward Modeling LoRA 训练能否支持 resume_from_checkpoint？",
        "answer": "支持。resume_from_checkpoint 接受 checkpoint 路径或 `auto`，默认 None；设为 auto 时从 output_dir 自动查找最新 checkpoint。",
        "doc_location": "docs/zh/configuration/training.md > 训练参数 > TrainingArguments > Checkpoint 与日志配置",
        "evidence": "| `resume_from_checkpoint` | `str \\| None` | `None` | checkpoint 路径或 `auto` |",
    },
    {
        "issue": 1407,
        "question": "seq_length 为什么是 8192，而 cutoff_len 设置为 4096 时？",
        "answer": "批处理策略中每个 micro-batch 的 token 预算 = cutoff_len × micro_batch_size。示例中 cutoff_len: 2048、micro_batch_size: 4，预算即为 2048 × 4 = 8192。",
        "doc_location": "docs/zh/feature-guide/batching.md > 批处理策略 > 配置示例",
        "evidence": "以下片段配置 `dynamic_padding_free`，每个 micro-batch 的 token 预算为 `2048 × 4 = 8192`：\n```yaml\nbatching_strategy: dynamic_padding_free\nmicro_batch_size: 4\ncutoff_len: 2048",
    },
]


def main() -> int:
    # ① 旧题库里已核过能用的 13 条（用户判 ✓ 的全部保留）
    #    id 7（Liger Kernel）和 id 10（lora_rank 2倍）曾因答案问题被排除，
    #    但答案已按文档原文修正，必须补回 —— 这两条是用户亲手勾的。
    #    注意：读 v1_backup，因为 questions.json 已经被换成 v3 了。
    src = DATA / "questions_v1_backup.json"
    if not src.exists():
        src = DATA / "questions.json"
    old = json.loads(src.read_text(encoding="utf-8"))
    OLD_KEEP = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    old_keep = []
    for q in old:
        if q["id"] in OLD_KEEP and q["source"] == "real":
            old_keep.append({
                "issue": int(str(q.get("origin", "0")).split("#")[-1].strip() or 0),
                "question": q["question"],
                "answer": q["answer"],
                "doc_location": q["doc_location"],
                "evidence": q.get("evidence", ""),
            })

    positive = old_keep + NEW_POSITIVE
    # 去重（同一 issue 只留一条）
    seen, pos = set(), []
    for p in positive:
        if p["issue"] in seen:
            continue
        seen.add(p["issue"])
        pos.append(p)

    print(f"正样本: 旧 {len(old_keep)} + 新 {len(NEW_POSITIVE)} → 去重后 {len(pos)} 条")
    out = DATA / "positive_questions.json"
    out.write_text(json.dumps(pos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"输出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
