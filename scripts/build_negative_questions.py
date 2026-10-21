#!/usr/bin/env python3
"""生成 33 条负样本：真实 Issue，但 LlamaFactory 文档确实没有答案。

负样本的判分标准（写进 RUBRIC.md）：
  模型老实说「资料里没有找到」→ 对
  模型编造具体答案        → 错（这是第 12 节要诊断的「编造内容」）
  模型说「资料提到 X 但没直接回答」→ 部分对

挑选原则：
  ① 必须是真实 Issue 原文
  ② 问题涉及的概念在文档里确实查不到（模型名/硬件/工具/实现原理/bug）
  ③ 问题本身有客观边界（能判断"文档到底有没有"），不是完全开放的主观题

输出：data/negative_questions.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# (issue, 缺什么 —— 用于人工复核和报告说明)
NEGATIVE = [
    (10132, "flash-attn 编译产物报 UDA error，属环境编译问题，文档无排障章节"),
    (6638, "LlavaForConditionalGeneration 的 forward 收到 default_system 报 TypeError，属具体 bug，文档无"),
    (10581, "webui 界面里设置随机种子，文档未覆盖 webui 操作"),
    (8994, "gpt-oss-20b 原始 MXFP4 精度，设 bf16=false 能否保持该精度，文档未涉及"),
    (3836, "Megatron 未安装的 ImportError，属安装问题，文档无"),
    (1841, "SUS-Chat-34B-AWQ 这个具体模型怎么微调，文档模型列表未收录"),
    (4438, "glm4-9B 设 max_grad_norm=1 仍梯度爆炸，文档只给参数含义不给排障"),
    (2887, "预训练为何用 endoftext 拼接而非 pad，属实现原理，文档未解释"),
    (9093, "是否支持 Seed-OSS 微调，文档模型支持列表无 Seed-OSS"),
    (9066, "能否支持 Seed-OSS，同上"),
    (8984, "是否支持 Seed-OSS-36B 的 SFT，同上"),
    (5421, "教程脚本里 BLEU/ROUGE 计算的参数默认值，文档无"),
    (7373, "Gemma-3-12B-it 用 BF16/FP16 做 LoRA 报错，属具体模型问题"),
    (3308, "昇腾 910B 微调 chatglm3 fp16/bf16 均失败，属硬件+模型组合问题"),
    (6828, "8 卡 H20 上 cutoff_len 超过 1000 就报错，属硬件显存问题"),
    (10317, "neat_packing 为何不支持 bsz>1，属设计决策，文档未说明原因"),
    (1730, "val_size 拆分逻辑是否合理，属实现细节，文档未展开"),
    (1188, "shift_attn 下如何设置 context 参数，文档未说明"),
    (7759, "能否输出数据 length 分布以判断 cutoff_len 合理性，属功能请求"),
    (8989, "neat_packing 是否支持 transformers 4.55，属版本兼容，文档无"),
    (1573, "NVIDIA 驱动版本要求，文档无环境要求章节"),
    (2001, "bf16 模型用 gptq 转 int8/int4 的具体步骤，文档无量化转换流程"),
    (8915, "bf16=True 时能否把部分模型移到 float32 训练，文档无"),
    (9152, "Qwen3 全量微调后保存的模型精度为何是 float32，属实现细节"),
    (9591, "Pure BF16 后 LoRA 层梯度为何仍是 fp32，属实现原理"),
    (4105, "Unsloth + 多卡（>2）时 batch_size 有误，属已知 bug"),
    (4139, "cast_trainable_params_to_fp32 导致 lora predict 报错，属 bug"),
    (3870, "奖励模型同时用 model_name_or_path 与 adapter_name_or_path 报错，属具体报错"),
    (1508, "bf16 多卡 deepspeed 全参微调 chatglm2 出错，属环境组合问题"),
    (7151, "webui 选 bf16 后报错提示只支持 bf16，属具体报错"),
    (5129, "PPO 训练时 save_steps/save_strategy/save_total_limit 无作用，属 bug 反馈"),
    (3392, "sft predict 时 num_beams>1 的支持情况，文档只给参数含义"),
    (8187, "compute_accuracy 参数在不同场景下的行为，文档未展开"),
]


def main() -> int:
    cands = {str(c["issue"]): c for c in json.loads((DATA / "real_title_hits.json").read_text(encoding="utf-8"))}
    judged = json.loads((DATA / "real_judged.json").read_text(encoding="utf-8"))

    out, miss = [], []
    for issue, gap in NEGATIVE:
        c = cands.get(str(issue))
        if not c:
            miss.append(issue)
            continue
        title = (c.get("title") or "").strip()
        ask = (c.get("ask") or "").strip()
        # 问题文本：标题 + 正文首段（去掉模板化的 Reminder）
        q = title
        if ask and ask != title:
            body = ask.split("｜", 1)[-1] if "｜" in ask else ""
            body = body.replace("### Reminder", "").strip()
            if body and len(body) > 20 and "I have read" not in body[:60]:
                q = title + " —— " + body[:160]
        out.append({
            "issue": issue,
            "question": q,
            "answer": "文档中未找到相关内容（此题正确答案就是「资料里没有」）",
            "doc_location": "（文档未涉及）",
            "gap": gap,
            "llm_verdict": judged.get(str(issue), {}).get("reason", "")[:100],
        })

    print(f"负样本: {len(out)} 条" + (f"，缺失 {miss}" if miss else ""))
    p = DATA / "negative_questions.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"输出 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
