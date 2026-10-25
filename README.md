给做大模型应用的开发和测试人员用的「自动调优」平台：设定一个质量目标（比如测试集正确率 85%、幻觉率低于 5%），平台自动循环「评测 → 找出失败原因 → 提出修改（提示词、检索设置、示例、模型）→ 在没见过的题上重新评测」，变好才保留、变差就退回，达到目标、预算用完或需要人确认时停下。

> 毕业设计项目 · 基于评测驱动闭环优化的大模型应用自动调优系统设计与实现
>
> **当前进度：第 1 周**（手工跑通一次「评测 → 诊断 → 改进 → 重测」）

---

## 第 1 周在做什么

先把一轮循环**手工**跑通，每个数字都能复算；以后 F1 要做的，就是把这一轮自动化、并且反复跑。

| 步骤 | 状态 |
|---|---|
| 1. 环境：Python 3.12 + 2 个模型来源 | ✅ Ollama 本地 qwen3-4b + 智谱 glm-5.3-flash |
| 2. 60 道真实提问（含标准答案与文档位置） | ✅ 60 题，全部来自 GitHub Issue，编号可回溯 |
| 3. `week1.py`：BM25 检索 → 2 模型回答 → CSV | ✅ 已跑通（v0/v1/v2 三轮，共 300 条回答） |
| 4. 人工诊断 + 改一轮 | ✅ 诊断见 `out/diagnosis.md`，改了两轮（v1/v2） |
| 5. 重测 v0 / v1 | ✅ 优化集 + 测试集都测了，见 `out/report.md` |
| 6. 全程录屏 | ⬜ 待录 |
| 7. 仓库 + 每日提交 | 🟡 已提交 2 次 |
| 8. REPRO.md | ✅ |

### 第 1 周结果摘要

| 集合 | v0 | v1 | v2 |
|---|---|---|---|
| 优化集（54 条） | 56% | **80%**（p=0.0036） | — |
| 测试集（48 条） | **77%** | 71% | 60% |

**核心发现**：参数名加权「救极难题（8%→65%）、伤易题（100%→93%）」，
净效果取决于题集难度构成。详见 `out/report.md`。

---

## 快速开始

全部在 WSL（Ubuntu）里运行。**推荐用 `run.sh`，不用记命令。**

```bash
# 看当前进度（随时可以跑）
bash run.sh status

# 首次初始化：建环境 + 拉数据 + 建索引（只需一次）
bash run.sh init

# 跑 v0（只跑优化用 30 道，测试集保持封存）
bash run.sh v0

# 生成盲判表（遮掉版本和模型，防止判分偏袒）
bash run.sh blind

#   → 打开 out/to_grade.csv，只填「人工判分 / 失败原因 / 判断理由」三列

# 判完回填
bash run.sh merge

# 诊断改进后跑 v1
bash run.sh v1

# 改进做完，才跑测试集（会二次确认）
bash run.sh test

# 出报告（正确率、失败分布、回归题、预期对比）
bash run.sh report --prediction 10

# 提交前自检（扫密钥、扫 Mock、扫硬编码数字）
bash run.sh check
```

### 手工命令（想自己控制时）

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python rank_bm25 jieba openpyxl

.venv/bin/python scripts/build_index.py                 # 建索引
.venv/bin/python week1.py --split optimize --version v0  # 跑 v0
.venv/bin/python week1.py --split optimize --dry-run     # 只检索不调模型
```

**注意**：跑之前先 `set -a && source .env && set +a`（`source` 单独用不会导出变量，Python 读不到）。

---

## 第 1 周的完整流程

```
① 勾题      打开 D:\llmloop\待核对_265题.xlsx，勾 60 条并填答案
            → python scripts/import_review_xlsx.py --xlsx /mnt/d/llmloop/待核对_265题.xlsx
            → python scripts/build_questions.py --finalize

② 跑 v0     bash run.sh v0                     （约 40 分钟，60 题 × 2 模型）

③ 盲判      bash run.sh blind → 填 out/to_grade.csv → bash run.sh merge

④ 诊断      看失败原因分布，定改法，先写下预期（out/prediction.md）

⑤ 改一轮    改 lib/text.py 的分词 / week1.py 的 Retriever

⑥ 跑 v1     bash run.sh v1

⑦ 重测      bash run.sh test → 再盲判一轮

⑧ 出报告    bash run.sh report --prediction 10

⑨ 提交      bash run.sh check → git commit
```

---

## 目录结构

```
llmloop/
├── week1.py                 # 第 1 周主脚本：检索 → 多模型回答 → CSV
├── lib/
│   └── text.py              # 共享分词（索引与查询必须一致）
├── configs/
│   └── models.json          # 模型配置（API key 走环境变量）
├── scripts/
│   ├── fetch_issues.sh      # 拉 LlamaFactory Issues
│   ├── build_index.py       # 文档切块 + BM25 索引
│   ├── filter_issues.py     # Issue 初筛
│   ├── probe_retrieval.py   # 检索命中探测
│   ├── select_questions.py  # 候选题目排序
│   └── make_review_sheet.py # 生成人工核对表
├── data/                    # 数据（不进仓库，见 .gitignore）
│   ├── chunks.jsonl         # 检索索引
│   ├── questions.json       # 60 道题（人工填写标准答案）
│   └── review_sheet.md      # 候选核对表
├── models/                  # 本地模型（不进仓库）
├── out/                     # 评测输出 CSV
├── README.md
└── REPRO.md                 # 可行性五关 + 本机配置
```

---

## 数据来源与许可

| 数据 / 代码 | 来源 | 许可 |
|---|---|---|
| LlamaFactory 文档与示例配置 | [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory) | Apache-2.0 |
| 真实提问 | 同仓库 Issues / Discussions | 按 GitHub 与项目使用条款 |
| 本地模型 | [Qwen3-4B-GGUF](https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF) | Apache-2.0 |

后续阶段会用到：GEPA（MIT）、DSPy（MIT）、tinyBenchmarks（MIT）、LettuceDetect（MIT）、RAGTruth（MIT）、PUPA（按数据集说明）。

---

## 可复现性

模型回答本身会变，所以 `out/` 里的 CSV 保留了每条回答原文与检索到的段落；
别人拉下仓库、装好环境、跑同一条命令，能复算出同样的统计数字。

检索和分词是确定性的（BM25 + 固定分词），只有模型回答会因服务端版本变化而不同。

---

## 环境变量

API key 一律走环境变量，**不写进仓库**：

```bash
export ZHIPU_API_KEY=...        # 智谱开放平台
export SILICONFLOW_API_KEY=...  # 硅基流动
```
