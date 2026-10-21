# 来源：https://llamafactory.readthedocs.io/zh-cn/latest/advanced/acceleration.html

# 加速¶
LlamaFactory 支持多种加速技术，包括：FlashAttention 、 Unsloth 、 Liger Kernel 。

## FlashAttention¶
FlashAttention 能够加快注意力机制的运算速度，同时减少对内存的使用。
如果您想使用 FlashAttention,请在启动训练时在训练配置文件中添加以下参数：

```
flash_attn: fa2

```

## Unsloth¶
Unsloth 框架支持 Llama, Mistral, Phi-3, Gemma, Yi, DeepSeek, Qwen等大语言模型并且支持 4-bit 和 16-bit 的 QLoRA/LoRA 微调，该框架在提高运算速度的同时还减少了显存占用。
如果您想使用 Unsloth, 请在启动训练时在训练配置文件中添加以下参数：

```
use_unsloth: True

```

## Liger Kernel¶
Liger Kernel 是一个大语言模型训练的性能优化框架, 可有效地提高吞吐量并减少内存占用。
如果您想使用 Liger Kernel,请在启动训练时在训练配置文件中添加以下参数：

```
enable_liger_kernel: True

```
