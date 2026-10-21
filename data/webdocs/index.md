# 来源：https://llamafactory.readthedocs.io/zh-cn/latest/index.html

# Welcome to LlamaFactory!¶
LlamaFactory 是一个简单易用且高效的大型语言模型（Large Language Model）训练与微调平台。通过 LlamaFactory，可以在无需编写任何代码的前提下，在本地完成上百种预训练模型的微调，框架特性包括：
模型种类：LLaMA、LLaVA、Mistral、Mixtral-MoE、Qwen、Yi、Gemma、Baichuan、ChatGLM、Phi 等等。
训练算法：（增量）预训练、（多模态）指令监督微调、奖励模型训练、PPO 训练、DPO 训练、KTO 训练、ORPO 训练等等。
运算精度：16 比特全参数微调、冻结微调、LoRA 微调和基于 AQLM/AWQ/GPTQ/LLM.int8/HQQ/EETQ 的 2/3/4/5/6/8 比特 QLoRA 微调。
优化算法：GaLore、BAdam、DoRA、LongLoRA、LLaMA Pro、Mixture-of-Depths、LoRA+、LoftQ 和 PiSSA。
加速算子：FlashAttention-2 和 Unsloth。
推理引擎：Transformers 和 vLLM。
实验监控：LlamaBoard、TensorBoard、Wandb、MLflow、SwanLab 等等。

## Documentation¶
开始使用
安装
数据处理
WebUI
SFT 训练
模型保存、LoRA 合并与量化
推理
评估
常见问题
高级选项
加速
FlashAttention
Unsloth
Liger Kernel
调优算法
Full Parameter Fine-tuning
Freeze
LoRA
LoRA+
rsLoRA
DoRA
PiSSA
Galore
BAdam
分布训练
NativeDDP
单机多卡
多机多卡
DeepSpeed
单机多卡
多机多卡
DeepSpeed 配置文件
FSDP
单机多卡
多机多卡
FSDP2
Ray
单机多卡
多机多卡
Megatron Bridge
当前范围
安装
快速开始
并行与批大小
配置字段
并行
重计算与融合
优化器与精度
数据与 checkpoint
数据流
Checkpoint
LoRA
与 MCA 的区别
限制与排障
量化
PTQ
GPTQ
QAT
AWQ
AQLM
OFTQ
bitsandbytes
HQQ
EETQ
训练方法
Pre-training
Post-training
Supervised Fine-Tuning
RLHF
DPO
KTO
实验监控
LlamaBoard
SwanLab
TensorBoard
Wandb
MLflow
参数介绍
微调参数
基本参数
LoRA
RLHF
Freeze
Apollo
BAdam
GaLore
数据参数
模型参数
基本参数
多模态模型
vllm 推理
模型量化
模型导出
评估参数
生成参数
SwanLab 参数
训练参数
RAY
环境变量
模型支持
注册 template
多模态数据构建
提供模型路径
额外选项
LLaMA Pro
微调最佳实践
GPT-OSS
3步实现 GPT-OSS 的 LoRA 微调
多设备后端
NPU
NPU安装及配置
硬件配套和支持的操作系统
核心依赖说明
方式一：手动安装环境
方式二：Docker 预安装镜像
方式三：Docker 本地构建
NPU训练
支持设备
支持功能
快速开始
分布式训练
训练方式
性能优化
