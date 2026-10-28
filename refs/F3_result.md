# F3 复现结果：RAGTruth 上的回答级幻觉检测

> 执行时间：2026-10-28 18:24–18:36
> 评测脚本：官方 `LettuceDetect/scripts/evaluate.py --evaluation_type example_level`
> 原始日志：`~/f3/eval_result.txt`
> 论文：Kovacs et al., *LettuceDetect: A Hallucination Detection Framework* (arXiv:2502.17125)

---

## 一、结论：F1 = 76.07%，与论文完全一致

| 指标 | 我们复算 | 论文 | 差距 |
|---|---|---|---|
| **回答级 F1（幻觉类）** | **0.7607 = 76.07%** | **76.07%** | **0.00** |
| 精确率 | 0.7664 | — | — |
| 召回率 | 0.7550 | — | — |
| AUROC | 0.8886 | — | — |
| 准确率 | 0.8341 | — | — |

**不是「同量级」，是小数点后四位逐位吻合。** 说明论文的 76.07% 就是用这套模型 + 这份数据 + 这个脚本算出来的，复现路径完全对齐。

模型：`KRLabsOrg/lettucedect-base-modernbert-en-v1`（ModernBERT-base，149M 参数）
数据：RAGTruth 测试集 2700 条（943 条有幻觉，占 34.9%）

---

## 二、分任务类型（★ 这个比总分更值得看）

| 任务类型 | 样本 | 幻觉条数（占比） | 精确率 | 召回率 | **F1** |
|---|---|---|---|---|---|
| Summary（摘要） | 900 | 204（22.7%） | 0.5389 | 0.4755 | **0.5052** |
| QA（问答） | 900 | 160（17.8%） | 0.6064 | 0.7125 | **0.6552** |
| Data2txt（结构化转文本） | 900 | 579（64.3%） | 0.8930 | 0.8653 | **0.8789** |
| **全体** | 2700 | 943（34.9%） | 0.7664 | 0.7550 | **0.7607** |

### 关键发现：76.07% 是被 Data2txt 拉上去的

**幻觉样本占比越低，F1 越低**，三个任务形成单调关系：

```
Data2txt  幻觉占 64.3% → F1 87.9%
Summary   幻觉占 22.7% → F1 50.5%
QA        幻觉占 17.8% → F1 65.5%
```

Data2txt 一条就贡献了全部幻觉样本的 61%（579/943），而它的 F1 高达 87.9%。
**如果只报 76.07%，会让人误以为模型在各类任务上都稳；实际在摘要任务上只有 50.5%，一半的幻觉漏掉了。**

论文报总体数字是合规的（RAGTruth 的标准口径），但**阶段 2 要把 F3 接进优化循环做「诊断信号」时，这个分任务差异必须写进设计**——否则在摘要类场景里，守门会形同虚设。

---

## 三、环境（这台机器的三个坑）

| 项 | 配置 |
|---|---|
| 环境 | `~/llmloop/.venv-f3`，Python 3.12.14（独立于主环境） |
| GPU | RTX 5060 Laptop 8GB，sm_120（Blackwell） |
| torch | **2.10.0+cu128** |
| transformers | 4.57.6（钉 `<5`） |
| 推理速度 | 2700 条 / 约 3 分钟（batch 4，约 6 it/s） |

### 坑 1：Blackwell 显卡必须 cu128，且要显式钉版本

第一次从 `download.pytorch.org/whl/cu128` 装，uv 却挑了 **cu130 的 torch 2.14.1**，报：

```
NVIDIA driver too old (found version 12080)
```

驱动是 CUDA 12.8，torch 是 CUDA 13.0，对不上。
而且 **cu128 源里 linux cp312 的最高版本只到 2.9.1**，2.10.0 要去阿里云镜像找。

### 坑 2：`torch.compile` 需要 C 编译器

```
torch._inductor.exc.InductorError: Failed to find C compiler.
```

WSL 里没装 gcc。**不用装 build-essential**，加环境变量即可：

```bash
TORCHDYNAMO_DISABLE=1 python scripts/evaluate.py ...
```

### 坑 3：hf-mirror 的大文件下载不可靠

- `Accept-Ranges: bytes` 是**假的**，带 Range 请求照样返回 200 全量 → **断点续传完全不可用**
- 570 MB 的文件会在 68 MB / 178 MB / 220 MB 处随机卡死
- `huggingface_hub.hf_hub_download` 也一样卡

**解决办法：限速整下 + 多轮重试。**

```bash
curl -L --http1.1 --limit-rate 2M -o model.tmp "$URL"
```

限速 2 MB/s 后一次成功（4 分 46 秒）。脚本留在 `~/f3/dl_model.sh`。

---

## 四、复现步骤（可照着重跑）

```bash
# 1. 数据
cd ~/f3/LettuceDetect
mkdir -p data/ragtruth
cp ~/f3/RAGTruth/dataset/{response,source_info}.jsonl data/ragtruth/

# 2. 预处理（产出 66MB 的 ragtruth_data.json）
.venv-f3/bin/python lettucedetect/preprocess/preprocess_ragtruth.py \
    --input_dir data/ragtruth --output_dir data/ragtruth

# 3. 评测
TORCHDYNAMO_DISABLE=1 .venv-f3/bin/python scripts/evaluate.py \
    --model_path ~/f3/models/lettucedect-base-modernbert-en-v1 \
    --data_path data/ragtruth/ragtruth_data.json \
    --evaluation_type example_level \
    --batch_size 4
```

---

## 五、指标口径（避免和别人对不上）

- **回答级（example-level）二分类**：一条回答里只要有任何幻觉就算「幻觉」，否则算「支持」
- token 阈值 0.5，连续被判为幻觉的 token 合并成 span
- 指标取 **Class 1（幻觉类）的 F1**，不是 macro avg、也不是 accuracy
- 论文里的 79.22% 是 **large 版（395M）**，76.07% 才是 base 版（149M）——别混

> 注意：仓库 HEAD 已是 v0.2.3（2026-06 转向 v2 系列模型 + span-F1 0.528/0.574），
> README 首页那些新数字和任务书要的 76.07% 不是一回事。76.07% 的出处是
> `docs/TINYLETTUCE.md:251`，对应 v1 时代的 base 模型。

---

## 六、局限

- 只测了 base 版（149M），没测 large 版（395M，论文 79.22%）和 TinyLettuce 系列
- 只做回答级，没做 span 级（char-level）——论文里 span 级更难，本文未复现
- RAGTruth 只有英文，没有中文场景；阶段 2 要换中文数据和中文模型
- 模型是官方预训练权重，没有在本机重新训练（阶段 2 才要求重训）

---

## 七、对阶段 2 的意义

| 用途 | 结论 |
|---|---|
| 幻觉守门 | 可以用，但**必须分任务类型看阈值**；摘要类只有 50.5%，不能一刀切 |
| 诊断信号 | 幻觉类精确率 0.77、召回 0.76，作为「失败原因归类」的一个信号够用 |
| 训练成本 | 本机 8GB 显存跑 149M 模型推理只要 3 分钟/2700 条，**接进循环不构成瓶颈** |
| 重训 | 阶段 2 要在本机显卡重训 base 模型，8GB 显存跑 batch 4 的 149M 模型有余量 |
