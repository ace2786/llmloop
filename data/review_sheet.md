# 第 1 周候选题目核对表

用法：逐条看「问题」和「文档命中」，判断**答案是否真的能在这段文档里找到**。
在 `判定` 列填 `✓`（可用）/ `✗`（不可用）/ `?`（需再查）。

共 120 条候选。排序依据：参数名命中 > 文档检索分 > 主题覆盖。

| # | 判定 | Issue | 问题 | 文档命中 | 参数命中 |
|---|---|---|---|---|---|
| 1 |  | [#9555](https://github.com/hiyouga/LlamaFactory/issues/9555) | Multimodal Image Dataset mllm_demo support system prompt？ | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | mllm_demo |
| 2 |  | [#3300](https://github.com/hiyouga/LlamaFactory/issues/3300) | 微调参数learning_rate，num_train_epochs 不生效 | `examples/README_zh.md`<br>目录 | num_train_epochs |
| 3 |  | [#6584](https://github.com/hiyouga/LlamaFactory/issues/6584) | How to set save_steps? I set a 15,000, and mine has more than 34,000 steps. I just trained | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | save_steps |
| 4 |  | [#5129](https://github.com/hiyouga/LlamaFactory/issues/5129) | ppo训练没有限制保存checkpoints数量功能。save_steps、save_strategy、save_total_limit没有任何作用。依然每步保存一个checkpo | `docs/zh/configuration/training.md`<br>训练参数 > TrainingArguments > Checkpoint 与日志配置 | save_steps |
| 5 |  | [#6761](https://github.com/hiyouga/LlamaFactory/issues/6761) | does `save_strategy` conflicts with `save_total_limit`? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | save_total_limit |
| 6 |  | [#6889](https://github.com/hiyouga/LlamaFactory/issues/6889) | Support apply_chat_template() | `docs/zh/feature-guide/inference.md`<br>推理 > 覆盖模型 Chat Template | — |
| 7 |  | [#4920](https://github.com/hiyouga/LlamaFactory/issues/4920) | 对微调的Qwen2-7B模型做量化，为什么使用量化后的模型推理时间变慢，显存占用无明显提升？ | `examples/README_zh.md`<br>目录 | — |
| 8 |  | [#1463](https://github.com/hiyouga/LlamaFactory/issues/1463) | 使用LLaMA-Factory训练文本分类模型是否可行？ | `docs/zh/configuration/index.md`<br>参数说明 > 参数分类 | — |
| 9 |  | [#10162](https://github.com/hiyouga/LlamaFactory/issues/10162) | 希望增加功能：使用tokenizer中的默认模板 | `docs/zh/feature-guide/inference.md`<br>推理 > 覆盖模型 Chat Template | — |
| 10 |  | [#2912](https://github.com/hiyouga/LlamaFactory/issues/2912) | 请问合并权重时如何选择指定的checkpoint | `docs/zh/feature-guide/index.md`<br>功能指南 > 模型保存与使用 | — |
| 11 |  | [#6746](https://github.com/hiyouga/LlamaFactory/issues/6746) | 能否支持在Qlora微调后直接导出int4等量化的模型 | `examples/README_zh.md`<br>目录 | — |
| 12 |  | [#6747](https://github.com/hiyouga/LlamaFactory/issues/6747) | 能否支持在Qlora微调后直接导出int4等量化的模型 | `examples/README_zh.md`<br>目录 | — |
| 13 |  | [#6099](https://github.com/hiyouga/LlamaFactory/issues/6099) | 使用命令行与qwen-2-2b-instruct交互，怎么上传图片。 | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | — |
| 14 |  | [#6573](https://github.com/hiyouga/LlamaFactory/issues/6573) | 如何对Qwen的量化版本模型做sft及dpo | `examples/README_zh.md`<br>目录 > 示例 > 合并 LoRA 适配器与模型量化 > 合并 LoRA 适配器 | — |
| 15 |  | [#4047](https://github.com/hiyouga/LlamaFactory/issues/4047) | Win11如何实现多 GPU LoRA 微调 | `examples/README_zh.md`<br>目录 | — |
| 16 |  | [#4021](https://github.com/hiyouga/LlamaFactory/issues/4021) | 训练参数没有说明，无从下手，能不能提供个参数说明文档 | `examples/extras/fsdp_qlora/llama3_lora_sft.yaml`<br>examples/extras/fsdp_qlora/llama3_lora_sft.yaml | — |
| 17 |  | [#2771](https://github.com/hiyouga/LlamaFactory/issues/2771) | LORA参数融合前后，推理的效果差距较大 | `docs/zh/quick_start.md`<br>快速开始 > 文档导航 | — |
| 18 |  | [#3635](https://github.com/hiyouga/LlamaFactory/issues/3635) | 微调完成后使用llama_factory的vllm和qwen官方的vllm部署方式启动返回的不一样 | `README_zh.md`<br>A3 + openEuler > 利用 vLLM 部署 OpenAI API | — |
| 19 |  | [#9522](https://github.com/hiyouga/LlamaFactory/issues/9522) | qwen3 function calling除了支持reasoning content之外，还能否支持content | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | — |
| 20 |  | [#10148](https://github.com/hiyouga/LlamaFactory/issues/10148) | Feature Request: Add freeze_audio_tower support for multimodal models (e.g. Qwen3-Omni) | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 21 |  | [#1665](https://github.com/hiyouga/LlamaFactory/issues/1665) | 请问--cutoff_len这个参数如果不想让文本被截断的话应该如何设置比较好 | `docs/zh/feature-guide/batching.md`<br>批处理策略 | — |
| 22 |  | [#2822](https://github.com/hiyouga/LlamaFactory/issues/2822) | 有一个40G的数据集，但是由于他太大，所以跑sft出很多问题。如果把数据集拆成多个小数据集，如何配置训练？ | `README_zh.md`<br>编译 & 安装 > 数据准备 | — |
| 23 |  | [#6737](https://github.com/hiyouga/LlamaFactory/issues/6737) | 请问：是否支持微调 DeepSeek-R1-Distill 系列模型？ | `README_zh.md`<br>quay.io > 安装 BitsAndBytes | — |
| 24 |  | [#10841](https://github.com/hiyouga/LlamaFactory/issues/10841) | 新手提问：微调 Qwen2.5-0.5B 最低需要什么显卡配置？ | `README_zh.md`<br>quay.io > 安装 BitsAndBytes | — |
| 25 |  | [#6580](https://github.com/hiyouga/LlamaFactory/issues/6580) | 增量）预训练、（多模态）指令监督微调、奖励模型训练、PPO 训练、DPO 训练、KTO 训练、ORPO 训练，经常提到的rlhf指的是哪几种训练方法 | `docs/zh/quick_start.md`<br>快速开始 > 选择运行命令 | — |
| 26 |  | [#6579](https://github.com/hiyouga/LlamaFactory/issues/6579) | 如何使用CPU进行推理？ | `README_zh.md`<br>A3 + openEuler > 利用 vLLM 部署 OpenAI API | — |
| 27 |  | [#5423](https://github.com/hiyouga/LlamaFactory/issues/5423) | [Question]support for quantization algorithms that are not performed on-the-fly | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 28 |  | [#10321](https://github.com/hiyouga/LlamaFactory/issues/10321) | 【Help】Qwen3 推理和非推理数据混合SFT应该怎么准备数据集和yaml文件？ | `README_zh.md`<br>编译 & 安装 > 数据准备 | — |
| 29 |  | [#6350](https://github.com/hiyouga/LlamaFactory/issues/6350) | 如何在 llama factory 中使用多个不同难度数据集实现课程式训练（Curriculum Learning） | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > 配置训练数据集 | — |
| 30 |  | [#6071](https://github.com/hiyouga/LlamaFactory/issues/6071) | 推理的cutoff len 设置为8092，但预测输出被限制在1024tokens | `examples/extras/nlg_eval/llama3_lora_predict.yaml`<br>examples/extras/nlg_eval/llama3_lora_predict.yaml | — |
| 31 |  | [#6558](https://github.com/hiyouga/LlamaFactory/issues/6558) | 【DPO相关】请问DPO训练结束后，应该如何进行推理呢？能使用类似SFT训练后推理的脚本吗 | `docs/zh/quick_start.md`<br>快速开始 > 选择运行命令 | — |
| 32 |  | [#10389](https://github.com/hiyouga/LlamaFactory/issues/10389) | Gemma4 needs transformers 5.5.0 but version check doesn't support it. | `README_zh.md`<br>编译 & 安装 | — |
| 33 |  | [#6484](https://github.com/hiyouga/LlamaFactory/issues/6484) | 如何指定只冻结 LLM 进行多模态模型的训练？ | `docs/zh/feature-guide/sft.md`<br>监督微调（SFT） > Freeze | — |
| 34 |  | [#5240](https://github.com/hiyouga/LlamaFactory/issues/5240) | 请问预训练数据tokenizer后可以存储吗，下次运行直接加载tokenizer后的数据，不用每次都在线tokenizer? | `docs/zh/quick_start.md`<br>快速开始 > 运行 SFT | — |
| 35 |  | [#6824](https://github.com/hiyouga/LlamaFactory/issues/6824) | 求助：如何对 DeepSeek R1 进行 SFT | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 36 |  | [#6458](https://github.com/hiyouga/LlamaFactory/issues/6458) | 相同dpo数据，相同训练配置和训练参数，在safe-rlhf框架训练完成以后回复正常，在llama-factory训练以后模型重复输出 | `docs/zh/feature-guide/rm.md`<br>奖励模型训练（RM） | — |
| 37 |  | [#5753](https://github.com/hiyouga/LlamaFactory/issues/5753) | Does llama factory support fine-tuning for binary classification tasks? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 38 |  | [#5512](https://github.com/hiyouga/LlamaFactory/issues/5512) | How to train the mm_proj and the LLM part with lora of Qwen2-VL | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 39 |  | [#6109](https://github.com/hiyouga/LlamaFactory/issues/6109) | 求助：模型qwen2.5-7b-instruct全量sft的时候，训练过程中loss突然变为0。 | `docs/zh/feature-guide/distributed_training.md`<br>分布式训练 > 配置多机启动 | — |
| 40 |  | [#6552](https://github.com/hiyouga/LlamaFactory/issues/6552) | How to Qwen2-vl dataset batched inference | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 41 |  | [#10673](https://github.com/hiyouga/LlamaFactory/issues/10673) | Feature Request: Support semantic-aware sequence packing for improved training efficiency | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 42 |  | [#6549](https://github.com/hiyouga/LlamaFactory/issues/6549) | 是否支持multi-turn dpo | `README_zh.md`<br>A3 + openEuler > 协议 | — |
| 43 |  | [#2837](https://github.com/hiyouga/LlamaFactory/issues/2837) | UserWarning('`do_sample` is set to `False`. However, `temperature` is set to `0.9` -- this | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 44 |  | [#6759](https://github.com/hiyouga/LlamaFactory/issues/6759) | 全参数微调的结果如何作为后续LoRA微调的base model | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 45 |  | [#10320](https://github.com/hiyouga/LlamaFactory/issues/10320) | Support for IQuestCoder model | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 46 |  | [#3420](https://github.com/hiyouga/LlamaFactory/issues/3420) | 如何在sft llama时 添加special token？ | `README_zh.md`<br>A3 + openEuler > 利用 vLLM 部署 OpenAI API > 使用 SwanLab 面板 | — |
| 47 |  | [#6352](https://github.com/hiyouga/LlamaFactory/issues/6352) | Can you support fast resume with streaming option? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 48 |  | [#4756](https://github.com/hiyouga/LlamaFactory/issues/4756) | 如何指定加载推理模型时的显卡 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 49 |  | [#9760](https://github.com/hiyouga/LlamaFactory/issues/9760) | 推理接口（API/CLI）是否支持返回生成的 Logits 或 Scores？ | `docs/zh/configuration/index.md`<br>参数说明 > 参数分类 | — |
| 50 |  | [#10604](https://github.com/hiyouga/LlamaFactory/issues/10604) | [Feature] Add support for Tencent Hunyuan Hy-MT2-1.8B/7B | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 51 |  | [#9550](https://github.com/hiyouga/LlamaFactory/issues/9550) | Support Tool calls datasets with thinking traces | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 52 |  | [#5540](https://github.com/hiyouga/LlamaFactory/issues/5540) | 用llamafactory chat加载qwen2-vl-72b模型推理视频效果很差的原因是什么？ | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 53 |  | [#10894](https://github.com/hiyouga/LlamaFactory/issues/10894) | CIG-SFT support | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 54 |  | [#459](https://github.com/hiyouga/LlamaFactory/issues/459) | LLaMA-2-70B在load时出现了mismatch问题，该如何解决呢？ | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 55 |  | [#5266](https://github.com/hiyouga/LlamaFactory/issues/5266) | 如何增加模型评估指标 | `README_zh.md`<br>克隆 bitsandbytes 仓库, Ascend NPU 目前在 multi-backend-refactor 中支 | — |
| 56 |  | [#6795](https://github.com/hiyouga/LlamaFactory/issues/6795) | qwen_7B ppo reward 呈现下降趋势，该如何调参？ | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 57 |  | [#3504](https://github.com/hiyouga/LlamaFactory/issues/3504) | full finetune问题：每次输出都会在json字段中带"human", 请问是系统提示词的原因啊嘛？ | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | — |
| 58 |  | [#973](https://github.com/hiyouga/LlamaFactory/issues/973) | PT和SFT的区别是什么？ | `docs/zh/feature-guide/index.md`<br>功能指南 > 训练任务 | — |
| 59 |  | [#4261](https://github.com/hiyouga/LlamaFactory/issues/4261) | 命令行如何中断训练及其恢复训练 | `docs/zh/feature-guide/model_saving.md`<br>模型保存与恢复 > 从 Checkpoint 恢复训练 | — |
| 60 |  | [#4763](https://github.com/hiyouga/LlamaFactory/issues/4763) | 请问OpenAI风格的API支持 Llava 的调用吗 | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | — |
| 61 |  | [#3945](https://github.com/hiyouga/LlamaFactory/issues/3945) | 请问下当前cutoff_len是直接截断句子并加上eos_token还是直接丢弃该条数据呢？ | `docs/zh/feature-guide/model_saving.md`<br>模型保存与恢复 > 从 Checkpoint 恢复训练 | — |
| 62 |  | [#5759](https://github.com/hiyouga/LlamaFactory/issues/5759) | 请教下作者，目前新版代码关于cutoff_len是怎么处理的？ | `README_zh.md`<br>A3 + openEuler > 协议 | — |
| 63 |  | [#2749](https://github.com/hiyouga/LlamaFactory/issues/2749) | 有计划支持LoRAMoE吗？ | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 64 |  | [#5844](https://github.com/hiyouga/LlamaFactory/issues/5844) | PISSA 训练完后如何进行推理 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 65 |  | [#6290](https://github.com/hiyouga/LlamaFactory/issues/6290) | 多模态大模型训练完成后，如何不借助webUI而是使用命令行或其他方式进行推理 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 66 |  | [#3862](https://github.com/hiyouga/LlamaFactory/issues/3862) | 请问现在支持流水线并行或者张量并行等模型并行的方式吗？不是数据并行 | `docs/zh/feature-guide/distributed_training.md`<br>分布式训练 > FSDPTurbo | — |
| 67 |  | [#3595](https://github.com/hiyouga/LlamaFactory/issues/3595) | 如何用自定义数据集进行性能评估 | `README_zh.md`<br>编译 & 安装 > 数据准备 | — |
| 68 |  | [#5683](https://github.com/hiyouga/LlamaFactory/issues/5683) | ppo的数据集格式应该是怎样的 | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 69 |  | [#6619](https://github.com/hiyouga/LlamaFactory/issues/6619) | webui参数加载、上传、推理处理速度很慢 | `examples/README_zh.md`<br>目录 | — |
| 70 |  | [#9660](https://github.com/hiyouga/LlamaFactory/issues/9660) | 多模态模型奖励模型以及强化学习的支持 | `docs/zh/quick_start.md`<br>快速开始 > 选择运行命令 | — |
| 71 |  | [#4960](https://github.com/hiyouga/LlamaFactory/issues/4960) | vllm inference "Bfloat16 is only supported on GPUs with compute capability of at least 8.0 | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 72 |  | [#6518](https://github.com/hiyouga/LlamaFactory/issues/6518) | 如果对Qwen2-vl进行DPO，对混合数据(部分数据有图片，部分数据无图片)进行训练，请问有实现这一部分吗？ | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 73 |  | [#9571](https://github.com/hiyouga/LlamaFactory/issues/9571) | 希望支持 HunyuanOCR。Add support for fine-tuning HunyuanOCR. | `README_zh.md`<br>A3 + openEuler > 协议 | — |
| 74 |  | [#6782](https://github.com/hiyouga/LlamaFactory/issues/6782) | Potential Support for Mistral Small 24B Models? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 75 |  | [#9540](https://github.com/hiyouga/LlamaFactory/issues/9540) | Dose vllm serve support Reward model trained by Llama Factory | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 76 |  | [#5830](https://github.com/hiyouga/LlamaFactory/issues/5830) | 如何同时使用yaml文件和命令行参数？ | `docs/zh/configuration/training.md`<br>训练参数 > TrainingArguments > 训练过程与精度 | — |
| 77 |  | [#10322](https://github.com/hiyouga/LlamaFactory/issues/10322) | 如何设置知道验证集数据是哪些 | `docs/zh/feature-guide/sft.md`<br>监督微调（SFT） > LoRA | — |
| 78 |  | [#10229](https://github.com/hiyouga/LlamaFactory/issues/10229) | how do you set nothink when using llamafactory's API | `README_zh.md`<br>A3 + openEuler > 利用 vLLM 部署 OpenAI API > 从魔乐社区下载 | — |
| 79 |  | [#2467](https://github.com/hiyouga/LlamaFactory/issues/2467) | Support for parquet datasets? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 80 |  | [#9761](https://github.com/hiyouga/LlamaFactory/issues/9761) | [Feature Request] Add support for Nanbeige4-3B-Base model | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 81 |  | [#6614](https://github.com/hiyouga/LlamaFactory/issues/6614) | 训练完之后，最后一个checkpoint和上一级目录的最终模型是否相同？ | `docs/zh/feature-guide/model_saving.md`<br>模型保存与恢复 > 不同后端的保存格式 | — |
| 82 |  | [#10679](https://github.com/hiyouga/LlamaFactory/issues/10679) | Can anybody explain what is v1? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 83 |  | [#10675](https://github.com/hiyouga/LlamaFactory/issues/10675) | _calculate_timestamps参数使用 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 84 |  | [#6147](https://github.com/hiyouga/LlamaFactory/issues/6147) | Does it support fine-tuning the PaliGemma model for object detection and segmentation? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 85 |  | [#6240](https://github.com/hiyouga/LlamaFactory/issues/6240) | 请问如何用vscode中的运行与调试对llama_factory进行debug呢，以sft阶段为例，应该怎么配置launch.json文件以及从哪个py文件开始debug？ | `docs/zh/quick_start.md`<br>快速开始 > 运行 SFT | — |
| 86 |  | [#5951](https://github.com/hiyouga/LlamaFactory/issues/5951) | [Help] 关于添加自定义模型训练支持 | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 87 |  | [#10153](https://github.com/hiyouga/LlamaFactory/issues/10153) | tokenzied_path 和 dataset 数据集参数的优先级 | `examples/README_zh.md`<br>目录 > 示例 > LoRA 微调 > 预处理数据集 | — |
| 88 |  | [#5467](https://github.com/hiyouga/LlamaFactory/issues/5467) | 如何自动保存checkpoint? | `docs/zh/feature-guide/model_saving.md`<br>模型保存与恢复 > 从 Checkpoint 恢复训练 | — |
| 89 |  | [#10524](https://github.com/hiyouga/LlamaFactory/issues/10524) | Support of higher vllm versions | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 90 |  | [#6481](https://github.com/hiyouga/LlamaFactory/issues/6481) | 如何进行API批量推理，batch interface | `docs/zh/feature-guide/inference.md`<br>推理 | — |
| 91 |  | [#5603](https://github.com/hiyouga/LlamaFactory/issues/5603) | How to implement weight decay towards the pre-trained model? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 92 |  | [#5661](https://github.com/hiyouga/LlamaFactory/issues/5661) | 【询问】在SFT&DPO训练中，是否可以自定义训练的special_tokens | `docs/zh/feature-guide/kernel_acceleration.md`<br>融合算子加速 | — |
| 93 |  | [#10614](https://github.com/hiyouga/LlamaFactory/issues/10614) | [Feature] Add support for Qwen-AgentWorld-35B-A3B | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 94 |  | [#4898](https://github.com/hiyouga/LlamaFactory/issues/4898) | 关于运用llama-factory中的deepseed全参数微调qwen2-7b-instruct面临问题 | `README_zh.md`<br>A3 + openEuler | — |
| 95 |  | [#6869](https://github.com/hiyouga/LlamaFactory/issues/6869) | Support for finetuning the convolutional layers of VLMs with lora | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 96 |  | [#9743](https://github.com/hiyouga/LlamaFactory/issues/9743) | 训练多模态模型function_call能力，如何构建数据集进行训练 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 97 |  | [#6927](https://github.com/hiyouga/LlamaFactory/issues/6927) | 现在LlamaFactory可以支持蒸馏训练吗？有计划支持吗？ | `docs/zh/feature-guide/batching.md`<br>批处理策略 > 使用约束 | — |
| 98 |  | [#4543](https://github.com/hiyouga/LlamaFactory/issues/4543) | how to authenticate to access huggingface | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 99 |  | [#10568](https://github.com/hiyouga/LlamaFactory/issues/10568) | Feature Proposal: Add FunASR ASR Support for Multimodal Training Data | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 100 |  | [#5822](https://github.com/hiyouga/LlamaFactory/issues/5822) | Qwen2-VL 微调不支持同时输入video和image么 | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 101 |  | [#6852](https://github.com/hiyouga/LlamaFactory/issues/6852) | 预测时，如果不想量化，怎么把权重分配到指定GPU上？ | `docs/zh/feature-guide/inference.md`<br>推理 > 启动 CLI 对话 | — |
| 102 |  | [#6724](https://github.com/hiyouga/LlamaFactory/issues/6724) | 预训练格式和sft微调格式是否可以同时进行微调？ | `README_zh.md`<br>编译 & 安装 > 数据准备 | — |
| 103 |  | [#10416](https://github.com/hiyouga/LlamaFactory/issues/10416) | loader.py does not support ignore_mismatched_sizes → breaks loading valid checkpoints (GLM | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 104 |  | [#5337](https://github.com/hiyouga/LlamaFactory/issues/5337) | 如何去打断点调试SFT, DPO流程 | `README_zh.md`<br>编译 & 安装 > 数据准备 > 快速开始 | — |
| 105 |  | [#6521](https://github.com/hiyouga/LlamaFactory/issues/6521) | 关于toolcall微调数据格式请教一下~ | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > DPO/RM 数据格式 | — |
| 106 |  | [#9657](https://github.com/hiyouga/LlamaFactory/issues/9657) | 为什么不使用tokenizer的apply_chat_template方法而是自定义一套template填充逻辑 | `docs/zh/feature-guide/inference.md`<br>推理 > 覆盖模型 Chat Template | — |
| 107 |  | [#5921](https://github.com/hiyouga/LlamaFactory/issues/5921) | 如何取部分数据集训练 | `docs/zh/feature-guide/data_preparation.md`<br>数据准备 > 组合多个数据集 | — |
| 108 |  | [#5891](https://github.com/hiyouga/LlamaFactory/issues/5891) | 如何添加额外的可训练参数？ | `docs/zh/configuration/model.md`<br>模型参数 > ModelArguments | — |
| 109 |  | [#6733](https://github.com/hiyouga/LlamaFactory/issues/6733) | 训练出错，参数参照的网上视频，工具也完整，请大佬帮忙看看问题，谢谢 | `README_zh.md`<br> | — |
| 110 |  | [#9713](https://github.com/hiyouga/LlamaFactory/issues/9713) | 为什么vision_model_keys不包括pos_embed | `README_zh.md`<br> | — |
| 111 |  | [#5214](https://github.com/hiyouga/LlamaFactory/issues/5214) | 请问使用全参训练出的checkpoint如何与原始模型的权重进行合并？ | `examples/merge_lora/qwen3vl_lora_sft.yaml`<br>examples/merge_lora/qwen3vl_lora_sft.yaml | — |
| 112 |  | [#6732](https://github.com/hiyouga/LlamaFactory/issues/6732) | How to jump a single sample？ | `README_zh.md`<br>A3 + openEuler | — |
| 113 |  | [#10411](https://github.com/hiyouga/LlamaFactory/issues/10411) | Support Training and Inference for audio-flamingo-next-think-hf | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 114 |  | [#6792](https://github.com/hiyouga/LlamaFactory/issues/6792) | 结合 GRPO 支持 DeepSeek-R1 等推理模型的复现，达到 huggingface open-r1 的类似效果 | `README_zh.md`<br>克隆 bitsandbytes 仓库, Ascend NPU 目前在 multi-backend-refactor 中支 | — |
| 115 |  | [#9762](https://github.com/hiyouga/LlamaFactory/issues/9762) | Add support for ds4sd/SmolDocling-256M-preview | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 116 |  | [#6776](https://github.com/hiyouga/LlamaFactory/issues/6776) | Template deepseekr1 does not exist | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 117 |  | [#6718](https://github.com/hiyouga/LlamaFactory/issues/6718) | please add bitune support | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 118 |  | [#6677](https://github.com/hiyouga/LlamaFactory/issues/6677) | How to print train mfu? | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 119 |  | [#3048](https://github.com/hiyouga/LlamaFactory/issues/3048) | 修改模型结构后，如何训练新的层 | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |
| 120 |  | [#10557](https://github.com/hiyouga/LlamaFactory/issues/10557) | [Feature] Add support for MiniCPM5-1B | `README_zh.md`<br>A3 + openEuler > 使用了 LlamaFactory 的项目 | — |